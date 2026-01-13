from __future__ import annotations

import tempfile
from contextlib import aclosing
from dataclasses import dataclass
from typing import Any, AsyncIterator, Optional, Sequence

from ..settings.models import Credentials
from .user_media_parser import extract_bottom_cursor, parse_user_media_tweets
from src.shared.filter_engine.models import Tweet


DEFAULT_USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/120.0.0.0 Safari/537.36"
)


@dataclass(frozen=True)
class ScrapePage:
    tweets: tuple[Tweet, ...]
    bottom_cursor: Optional[str] = None


def _cookie_string(credentials: Credentials) -> str:
    parts = [
        f"auth_token={credentials.auth_token.strip()}",
        f"ct0={credentials.ct0.strip()}",
    ]
    if credentials.twid and credentials.twid.strip():
        parts.append(f"twid={credentials.twid.strip()}")
    return "; ".join(parts)


class TwscrapeMediaScraper:
    """
    Scrape layer implementation backed by `twscrape`.

    The scraper yields pages (each page corresponds to one GraphQL response),
    which is a cursor-equivalent pagination mechanism.
    """

    def __init__(
        self,
        *,
        credentials: Credentials,
        proxy: Optional[str] = None,
        debug: bool = False,
        account_username: str = "xmc_cookie",
    ) -> None:
        self._credentials = credentials
        self._proxy = proxy
        self._debug = debug
        self._account_username = account_username

    async def iter_user_media_pages(
        self,
        *,
        handle: str,
        max_pages: Optional[int] = None,
    ) -> AsyncIterator[ScrapePage]:
        """
        Iterate UserMedia pages for a handle.

        Args:
            handle: X handle without leading @.
            max_pages: Optional debug limit.

        Yields:
            ScrapePage: parsed Tweets + extracted bottom cursor.
        """

        try:
            from twscrape import API  # type: ignore
        except Exception as exc:  # noqa: BLE001
            raise RuntimeError(
                "缺少依赖 twscrape：请先安装 requirements.txt（twscrape>=0.17.0）"
            ) from exc

        clean = (handle or "").strip().lstrip("@")
        if not clean:
            raise ValueError("handle 不能为空")

        if not self._credentials or not self._credentials.is_complete():
            raise RuntimeError("全局凭证未配置（需要 auth_token + ct0）")

        cookies = _cookie_string(self._credentials)

        with tempfile.TemporaryDirectory(prefix="xmc_twscrape_") as tmpdir:
            accounts_db = f"{tmpdir}/accounts.db"
            api = API(
                pool=accounts_db,
                debug=bool(self._debug),
                proxy=(self._proxy or None),
                raise_when_no_account=True,
            )

            await api.pool.add_account(
                self._account_username,
                "x",
                "xmc@example.com",
                "x",
                cookies=cookies,
                user_agent=DEFAULT_USER_AGENT,
            )

            user = await api.user_by_login(clean)
            if user is None:
                raise RuntimeError(f"未找到账号：{clean}")

            user_id = int(getattr(user, "id", 0) or 0)
            if not user_id:
                raise RuntimeError(f"无法解析 user_id：{clean}")

            page_count = 0
            async with aclosing(api.user_media_raw(user_id, limit=-1)) as gen:
                async for rep in gen:
                    page_count += 1
                    raw: Any = rep.json()
                    tweets = parse_user_media_tweets(raw if isinstance(raw, dict) else {})
                    cursor = extract_bottom_cursor(raw if isinstance(raw, dict) else {})
                    yield ScrapePage(tweets=tuple(tweets), bottom_cursor=cursor)
                    if max_pages is not None and page_count >= int(max_pages):
                        break

    async def collect_tweets(
        self,
        *,
        handle: str,
        max_pages: Optional[int] = None,
    ) -> list[Tweet]:
        tweets: list[Tweet] = []
        async for page in self.iter_user_media_pages(handle=handle, max_pages=max_pages):
            tweets.extend(page.tweets)

        # Ensure global stable ordering across pages.
        tweets.sort(key=lambda t: (-int(t.created_at.timestamp() * 1_000_000), t.tweet_id))
        return tweets

