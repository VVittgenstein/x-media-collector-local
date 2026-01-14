from __future__ import annotations

import tempfile
import json
import re
from dataclasses import dataclass
from typing import Any, AsyncIterator, Optional

from src.backend.net.throttle import Throttle
from ..settings.models import Credentials
from .user_media_parser import extract_bottom_cursor, parse_user_media_tweets, _iter_timeline_tweet_results
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
        throttle: Optional[Throttle] = None,
        debug: bool = False,
        account_username: str = "xmc_cookie",
    ) -> None:
        self._credentials = credentials
        self._proxy = proxy
        self._throttle = throttle
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
            from twscrape import xclid  # type: ignore
            from twscrape.api import OP_UserMedia, GQL_URL, GQL_FEATURES  # type: ignore
            from twscrape.queue_client import QueueClient  # type: ignore
            from twscrape.utils import encode_params  # type: ignore
        except Exception as exc:  # noqa: BLE001
            raise RuntimeError(
                "缺少依赖 twscrape：请先安装 requirements.txt（twscrape>=0.17.0）"
            ) from exc

        # twscrape 0.17.0: XClientTxId 解析依赖 x.com 首页内联脚本里的 chunk 映射。
        # 近期该映射从 JSON 变为 JS object literal（包含未加引号的 key），导致 json.loads 失败并触发：
        #   "Failed to parse scripts"
        # 这里做一次轻量 monkey patch，兼容两种格式，避免上游库不可用。
        if not getattr(getattr(xclid, "get_scripts_list", None), "__xmc_patched__", False):
            original_get_scripts_list = xclid.get_scripts_list

            def _get_scripts_list_compat(text: str):  # type: ignore
                try:
                    raw = text.split('e=>e+"."+', 1)[1].split('[e]+"a.js"', 1)[0]
                except Exception as exc:  # noqa: BLE001
                    raise Exception("Failed to parse scripts") from exc

                # Fast path: original behavior (JSON object)
                try:
                    for k, v in json.loads(raw).items():
                        yield xclid.script_url(k, f"{v}a")
                    return
                except Exception:
                    pass

                # Fallback: JS object literal with unquoted identifier keys
                pair_re = re.compile(
                    r'(?:\"(?P<qkey>[^\"]+)\"|(?P<ukey>[A-Za-z0-9_]+))\s*:\s*\"(?P<val>[0-9a-f]+)\"'
                )
                parsed: dict[str, str] = {}
                for m in pair_re.finditer(raw):
                    key = m.group("qkey") or m.group("ukey")
                    if not key:
                        continue
                    parsed[key] = m.group("val")

                if not parsed:
                    # Preserve original error string for twscrape retry/lock logic.
                    raise Exception("Failed to parse scripts")

                for k, v in parsed.items():
                    yield xclid.script_url(k, f"{v}a")

            setattr(_get_scripts_list_compat, "__xmc_patched__", True)
            xclid.get_scripts_list = _get_scripts_list_compat  # type: ignore
            setattr(xclid.get_scripts_list, "__xmc_original__", original_get_scripts_list)

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
                raise_when_no_account=False,
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

            # NOTE:
            # twscrape 0.17.0 的 `API.user_media_raw()` 翻页依赖 `get_by_path(..., "entries")`，
            # 在部分新响应结构下会错误命中“仅包含 cursor 的 entries”，导致误判为无内容并提前结束。
            # 这里改为：直接用 Bottom cursor 驱动分页，并用我们自己的解析器抽取 tweets/cursor。
            cursor: Optional[str] = None
            seen_cursors: set[str] = set()
            empty_tweet_results_pages = 0
            page_count = 0

            async with QueueClient(api.pool, "UserMedia", debug=bool(self._debug), proxy=(self._proxy or None)) as client:
                while True:
                    if self._throttle is not None:
                        await self._throttle.wait_async()

                    variables: dict[str, Any] = {
                        "userId": str(user_id),
                        "count": 40,
                        "includePromotedContent": False,
                        "withClientEventToken": False,
                        "withBirdwatchNotes": False,
                        "withVoice": True,
                        "withV2Timeline": True,
                    }
                    if cursor:
                        variables["cursor"] = cursor

                    params: dict[str, Any] = {
                        "variables": variables,
                        "features": dict(GQL_FEATURES),
                        "fieldToggles": {"withArticlePlainText": False},
                    }

                    rep = await client.get(f"{GQL_URL}/{OP_UserMedia}", params=encode_params(params))
                    if rep is None:
                        raise RuntimeError("UserMedia 请求失败（可能会话失效/账号不可用/触发风控），请稍后重试或降低频率")

                    raw: Any = rep.json()
                    page_obj = raw if isinstance(raw, dict) else {}
                    tweets = parse_user_media_tweets(page_obj)
                    next_cursor = extract_bottom_cursor(page_obj)

                    if not tweets:
                        # `UserMedia` 为空通常意味着到达末尾（仅剩 cursor），或上游结构变化导致解析失效。
                        # 若检测到有 Tweet 结果但解析后无媒体，则提示用户重试/升级。
                        if any(True for _ in _iter_timeline_tweet_results(page_obj)):
                            raise RuntimeError("UserMedia 解析异常：检测到推文但未提取到媒体（可能上游结构更新）")
                        empty_tweet_results_pages += 1
                    else:
                        empty_tweet_results_pages = 0

                    page_count += 1
                    yield ScrapePage(tweets=tuple(tweets), bottom_cursor=next_cursor)

                    if max_pages is not None and page_count >= int(max_pages):
                        break

                    if not next_cursor:
                        break
                    if empty_tweet_results_pages >= 2:
                        break
                    if next_cursor in seen_cursors:
                        break
                    seen_cursors.add(next_cursor)
                    cursor = next_cursor

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
