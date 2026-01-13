from __future__ import annotations

import asyncio
import time
from pathlib import Path
from typing import Any, Awaitable, Callable, Optional
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from src.backend.downloader.downloader import DownloadStatus, MediaDownloader, MediaIntent
from src.backend.fs.storage import AccountStorageManager, MediaType
from src.backend.scheduler.models import Run
from src.backend.settings.store import SettingsStore
from src.backend.scraper.twscrape_scraper import DEFAULT_USER_AGENT, TwscrapeMediaScraper
from src.shared.filter_engine.engine import apply_filters
from src.shared.filter_engine.models import DownloadIntent, FilterConfig, MediaKind


def _build_filter_config(account_config: dict[str, Any]) -> FilterConfig:
    """
    Frontend account config (camelCase) -> FilterEngine FilterConfig (snake_case).
    """

    start_date = account_config.get("startDate", account_config.get("start_date"))
    end_date = account_config.get("endDate", account_config.get("end_date"))
    media_type = account_config.get("mediaType", account_config.get("media_type", "both"))
    min_short_side = account_config.get("minShortSide", account_config.get("min_short_side"))
    include_quote = account_config.get(
        "includeQuoteMediaInReply",
        account_config.get("include_quote_media_in_reply", False),
    )

    source_types: list[str] | None = None
    raw_source_types = account_config.get("sourceTypes", account_config.get("source_types"))
    if isinstance(raw_source_types, dict):
        source_types = []
        for k, v in raw_source_types.items():
            if bool(v):
                source_types.append(str(k))
    elif isinstance(raw_source_types, (list, tuple)):
        source_types = [str(v) for v in raw_source_types]

    payload = {
        "start_date": start_date,
        "end_date": end_date,
        "media_type": media_type,
        "source_types": source_types,
        "include_quote_media_in_reply": bool(include_quote),
        "min_short_side": min_short_side,
    }
    return FilterConfig.from_dict(payload)


def _to_media_intent(intent: DownloadIntent) -> MediaIntent:
    media_type = MediaType.IMAGE if intent.kind == MediaKind.IMAGE else MediaType.VIDEO
    return MediaIntent(
        url=intent.url,
        tweet_id=intent.tweet_id,
        created_at=intent.tweet_created_at,
        media_type=media_type,
        width=intent.width,
        height=intent.height,
        needs_post_min_short_side_check=intent.needs_post_min_short_side_check,
    )


def _download_bytes_with_retries(
    url: str,
    *,
    timeout_s: float = 30.0,
    retries: int = 2,
    backoff_s: float = 1.5,
) -> bytes:
    headers = {
        "User-Agent": DEFAULT_USER_AGENT,
        "Accept": "*/*",
        "Referer": "https://x.com/",
    }

    last_exc: Optional[BaseException] = None
    for attempt in range(retries + 1):
        try:
            req = Request(url, headers=headers)
            with urlopen(req, timeout=timeout_s) as resp:
                return resp.read()
        except HTTPError as exc:
            last_exc = exc
            status = int(getattr(exc, "code", 0) or 0)
            if status in (429, 500, 502, 503, 504) and attempt < retries:
                time.sleep(backoff_s * (2**attempt))
                continue
            raise
        except URLError as exc:
            last_exc = exc
            if attempt < retries:
                time.sleep(backoff_s * (2**attempt))
                continue
            raise

    if last_exc is not None:
        raise RuntimeError(str(last_exc))
    raise RuntimeError("download failed")


async def run_account_pipeline(*, run: Run, store: SettingsStore) -> None:
    """
    Single-account runner: scrape -> filter -> download.

    Note:
    - Scraping is async (twscrape).
    - Downloading is done in threads to avoid blocking the event loop.
    """

    settings = store.load()
    if not settings.credentials or not settings.credentials.is_complete():
        raise RuntimeError("全局凭证未配置（需要 auth_token + ct0）")

    handle = (run.handle or "").strip().lstrip("@")
    if not handle:
        raise ValueError("handle 不能为空")

    download_root = Path(settings.download_root)
    storage = AccountStorageManager(download_root)
    downloader = MediaDownloader(
        storage=storage,
        handle=handle,
        download_func=_download_bytes_with_retries,
    )

    # Cross-run dedup (first wins) by loading existing files.
    await asyncio.to_thread(downloader.load_existing_files)

    scraper = TwscrapeMediaScraper(credentials=settings.credentials)
    tweets = await scraper.collect_tweets(handle=handle)

    filter_config = _build_filter_config(run.account_config or {})
    filter_result = apply_filters(tweets, filter_config)

    media_intents: list[MediaIntent] = []
    for it in filter_result.intents:
        media_intents.append(_to_media_intent(it))

    # Preserve Filter Engine ordering (stable + aligns with trigger_created_at sorting).
    results = []
    for intent in media_intents:
        results.append(await asyncio.to_thread(downloader.download, intent))

    failed = [r for r in results if r.status == DownloadStatus.FAILED]
    if failed:
        downloaded = sum(1 for r in results if r.status == DownloadStatus.SUCCESS)
        skipped = sum(1 for r in results if r.status == DownloadStatus.SKIPPED_DUPLICATE)
        examples = "; ".join(
            f"{r.tweet_id}:{r.media_url} -> {r.error or 'unknown error'}"
            for r in failed[:3]
        )
        raise RuntimeError(
            f"download failures: {len(failed)}/{len(results)} failed "
            f"(downloaded={downloaded}, skipped_duplicate={skipped}). "
            f"examples: {examples}"
        )


def create_account_runner(*, store: SettingsStore) -> Callable[[Run], Awaitable[None]]:
    async def _runner(run: Run) -> None:
        await run_account_pipeline(run=run, store=store)

    return _runner
