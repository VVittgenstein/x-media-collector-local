import tempfile
import unittest
from datetime import datetime
from pathlib import Path

from src.backend.downloader.downloader import DownloadStatus, MediaDownloader, MediaIntent
from src.backend.fs.hashing import compute_bytes_hash, compute_hash6
from src.backend.fs.naming import generate_media_filename
from src.backend.fs.storage import AccountStorageManager, MediaType


def _write_existing_image(
    *,
    storage: AccountStorageManager,
    handle: str,
    tweet_id: str,
    created_at: datetime,
    content: bytes,
    extension: str = "jpg",
) -> Path:
    paths = storage.ensure_account_dirs(handle)
    content_hash = compute_bytes_hash(content)
    filename = generate_media_filename(
        tweet_id=tweet_id,
        created_at=created_at,
        hash6=compute_hash6(content_hash),
        extension=extension,
    )
    path = paths.images / filename
    path.write_bytes(content)
    return path


def _list_media_files(directory: Path) -> list[Path]:
    return sorted(
        [
            p
            for p in directory.iterdir()
            if p.is_file() and not p.name.startswith(".") and p.suffix.lower() != ".tmp"
        ]
    )


class TestIgnoreReplace(unittest.TestCase):
    def test_s1_same_tweet_same_content_replaces_in_place(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            storage = AccountStorageManager(Path(tmpdir))
            handle = "alice"
            content = b"same content"
            created_at = datetime(2026, 1, 10, 12, 0, 0)

            old_path = _write_existing_image(
                storage=storage,
                handle=handle,
                tweet_id="1234567890",
                created_at=created_at,
                content=content,
            )

            downloader = MediaDownloader(
                storage=storage,
                handle=handle,
                download_func=lambda url: content,
                ignore_replace=True,
            )
            downloader.load_existing_files_for_replace()

            intent = MediaIntent(
                url="https://example.com/img.jpg",
                tweet_id="1234567890",
                created_at=created_at,
                media_type=MediaType.IMAGE,
            )
            result = downloader.download(intent)
            self.assertEqual(result.status, DownloadStatus.SUCCESS)

            files = _list_media_files(old_path.parent)
            self.assertEqual(len(files), 1)
            self.assertEqual(files[0].name, old_path.name)
            self.assertEqual(files[0].read_bytes(), content)

    def test_s2_same_content_different_tweet_deletes_old_and_keeps_new(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            storage = AccountStorageManager(Path(tmpdir))
            handle = "bob"
            content = b"same content"

            old_path = _write_existing_image(
                storage=storage,
                handle=handle,
                tweet_id="1111111111",
                created_at=datetime(2026, 1, 5, 12, 0, 0),
                content=content,
            )

            downloader = MediaDownloader(
                storage=storage,
                handle=handle,
                download_func=lambda url: content,
                ignore_replace=True,
            )
            downloader.load_existing_files_for_replace()

            new_created_at = datetime(2026, 1, 12, 12, 0, 0)
            new_intent = MediaIntent(
                url="https://example.com/new.jpg",
                tweet_id="2222222222",
                created_at=new_created_at,
                media_type=MediaType.IMAGE,
            )

            result = downloader.download(new_intent)
            self.assertEqual(result.status, DownloadStatus.SUCCESS)

            self.assertFalse(old_path.exists())

            content_hash = compute_bytes_hash(content)
            expected_name = generate_media_filename(
                tweet_id="2222222222",
                created_at=new_created_at,
                hash6=compute_hash6(content_hash),
                extension="jpg",
            )
            expected_path = old_path.parent / expected_name
            self.assertTrue(expected_path.exists())

            files = _list_media_files(old_path.parent)
            self.assertEqual(files, [expected_path])

    def test_s4_current_run_dedup_happens_before_cross_run_replace(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            storage = AccountStorageManager(Path(tmpdir))
            handle = "dave"
            content = b"dup content"

            old_path = _write_existing_image(
                storage=storage,
                handle=handle,
                tweet_id="4444444444",
                created_at=datetime(2026, 1, 1, 12, 0, 0),
                content=content,
            )

            downloader = MediaDownloader(
                storage=storage,
                handle=handle,
                download_func=lambda url: content,
                ignore_replace=True,
            )
            downloader.load_existing_files_for_replace()

            newest_created_at = datetime(2026, 1, 12, 12, 0, 0)
            intent_newest = MediaIntent(
                url="https://example.com/newest.jpg",
                tweet_id="5555555555",
                created_at=newest_created_at,
                media_type=MediaType.IMAGE,
            )
            intent_older = MediaIntent(
                url="https://example.com/older.jpg",
                tweet_id="6666666666",
                created_at=datetime(2026, 1, 11, 12, 0, 0),
                media_type=MediaType.IMAGE,
            )

            result1 = downloader.download(intent_newest)
            result2 = downloader.download(intent_older)

            self.assertEqual(result1.status, DownloadStatus.SUCCESS)
            self.assertEqual(result2.status, DownloadStatus.SKIPPED_DUPLICATE)

            self.assertFalse(old_path.exists())

            content_hash = compute_bytes_hash(content)
            expected_name = generate_media_filename(
                tweet_id="5555555555",
                created_at=newest_created_at,
                hash6=compute_hash6(content_hash),
                extension="jpg",
            )
            expected_path = old_path.parent / expected_name
            self.assertTrue(expected_path.exists())
            self.assertEqual(result2.existing_file, expected_path)

            files = _list_media_files(old_path.parent)
            self.assertEqual(files, [expected_path])


if __name__ == "__main__":
    unittest.main()

