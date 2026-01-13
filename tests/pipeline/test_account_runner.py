import unittest
import asyncio
from datetime import datetime
from pathlib import Path
import tempfile
from types import SimpleNamespace
from unittest.mock import patch

from src.backend.downloader.downloader import DownloadResult, DownloadStatus
from src.backend.fs.storage import MediaType
from src.backend.pipeline.account_runner import _to_media_intent, run_account_pipeline
from src.backend.scheduler.models import Run
from src.backend.settings.models import Credentials, GlobalSettings
from src.backend.settings.store import SettingsStore
from src.shared.filter_engine.models import DownloadIntent, MediaKind
from src.shared.task_status import TaskStatus


class TestAccountRunnerIntentMapping(unittest.TestCase):
    def test_to_media_intent_preserves_width_height_and_post_check_flag(self) -> None:
        intent = DownloadIntent(
            media_id="m1",
            kind=MediaKind.VIDEO,
            url="https://example.com/v.mp4",
            width=None,
            height=None,
            tweet_id="t1",
            tweet_created_at=datetime(2026, 1, 13, 12, 0, 0),
            trigger_tweet_id="t1",
            trigger_created_at=datetime(2026, 1, 13, 12, 0, 0),
            origin="self",
            needs_post_min_short_side_check=True,
        )

        media_intent = _to_media_intent(intent)
        self.assertEqual(media_intent.url, intent.url)
        self.assertEqual(media_intent.tweet_id, intent.tweet_id)
        self.assertEqual(media_intent.created_at, intent.tweet_created_at)
        self.assertEqual(media_intent.media_type, MediaType.VIDEO)
        self.assertIsNone(media_intent.width)
        self.assertIsNone(media_intent.height)
        self.assertTrue(media_intent.needs_post_min_short_side_check)


class TestAccountRunnerDownloadFailurePropagation(unittest.TestCase):
    def test_run_account_pipeline_raises_when_downloads_fail(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp_path = Path(tmpdir)
            download_root = tmp_path / "downloads"
            store = SettingsStore(path=tmp_path / "config.json")
            store.save(
                GlobalSettings(
                    credentials=Credentials(auth_token="a", ct0="b"),
                    download_root=str(download_root),
                )
            )

            run = Run(
                run_id="r1",
                handle="testuser",
                kind="start",
                account_config={},
                status=TaskStatus.QUEUED,
                created_at=datetime(2026, 1, 13, 12, 0, 0),
                updated_at=datetime(2026, 1, 13, 12, 0, 0),
            )

            filter_result = SimpleNamespace(
                intents=[
                    DownloadIntent(
                        media_id="m1",
                        kind=MediaKind.IMAGE,
                        url="https://example.com/a.jpg",
                        width=None,
                        height=None,
                        tweet_id="t1",
                        tweet_created_at=datetime(2026, 1, 13, 12, 0, 0),
                        trigger_tweet_id="t1",
                        trigger_created_at=datetime(2026, 1, 13, 12, 0, 0),
                        origin="self",
                        needs_post_min_short_side_check=False,
                    )
                ]
            )

            async def fake_collect_tweets(self, *, handle: str, max_pages=None):  # noqa: ANN001
                return []

            def fake_apply_filters(tweets, config):  # noqa: ANN001
                return filter_result

            def fake_download(self, intent):  # noqa: ANN001
                return DownloadResult(
                    status=DownloadStatus.FAILED,
                    media_url=intent.url,
                    tweet_id=intent.tweet_id,
                    created_at=intent.created_at,
                    media_type=intent.media_type,
                    error="boom",
                )

            async def fake_to_thread(func, /, *args, **kwargs):  # noqa: ANN001
                return func(*args, **kwargs)

            with (
                patch(
                    "src.backend.pipeline.account_runner.TwscrapeMediaScraper.collect_tweets",
                    new=fake_collect_tweets,
                ),
                patch(
                    "src.backend.pipeline.account_runner.apply_filters",
                    new=fake_apply_filters,
                ),
                patch(
                    "src.backend.pipeline.account_runner.MediaDownloader.download",
                    new=fake_download,
                ),
                patch(
                    "src.backend.pipeline.account_runner.asyncio.to_thread",
                    new=fake_to_thread,
                ),
            ):
                with self.assertRaisesRegex(RuntimeError, "download failures"):
                    asyncio.run(run_account_pipeline(run=run, store=store))


if __name__ == "__main__":
    unittest.main()
