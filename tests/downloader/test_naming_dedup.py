"""
Tests for naming and deduplication logic.

Acceptance criteria from T-20260113-test-naming-dedup:
1. Assert generated filename can be parsed to extract tweetId and YYYY-MM-DD
2. Assert hash6 equals first 6 characters of content hash
3. Simulate two writes of same content: first kept, second deleted and skipped_duplicate+1
"""

import tempfile
import unittest
from datetime import datetime
from pathlib import Path

# Add src to path for imports
import sys
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "src"))

from backend.fs.naming import (
    generate_media_filename,
    parse_media_filename,
    extract_tweet_id,
    get_extension_from_url,
)
from backend.fs.hashing import (
    compute_bytes_hash,
    compute_file_hash,
    compute_hash6,
    StreamHasher,
)
from backend.fs.storage import AccountStorageManager, MediaType
from backend.downloader.dedup import DedupIndex, DedupResult
from backend.downloader.downloader import (
    MediaDownloader,
    MediaIntent,
    DownloadStatus,
)


class TestNaming(unittest.TestCase):
    """Tests for file naming conventions."""

    def test_generate_filename_format(self):
        """Generated filename should follow <tweetId>_<YYYY-MM-DD>_<hash6>.<ext> format."""
        tweet_id = "1234567890123456789"
        created_at = datetime(2026, 1, 13, 10, 30, 0)
        hash6 = "a1b2c3"
        extension = "jpg"

        filename = generate_media_filename(tweet_id, created_at, hash6, extension)

        assert filename == "1234567890123456789_2026-01-13_a1b2c3.jpg"

    def test_parse_filename_extracts_tweet_id(self):
        """Parsed filename should correctly extract tweetId."""
        filename = "1234567890123456789_2026-01-13_a1b2c3.jpg"
        parsed = parse_media_filename(filename)

        assert parsed is not None
        assert parsed.tweet_id == "1234567890123456789"

    def test_parse_filename_extracts_date(self):
        """Parsed filename should correctly extract YYYY-MM-DD date."""
        filename = "1234567890123456789_2026-01-13_a1b2c3.jpg"
        parsed = parse_media_filename(filename)

        assert parsed is not None
        assert parsed.date == "2026-01-13"

    def test_parse_filename_extracts_hash6(self):
        """Parsed filename should correctly extract hash6."""
        filename = "1234567890123456789_2026-01-13_a1b2c3.jpg"
        parsed = parse_media_filename(filename)

        assert parsed is not None
        assert parsed.hash6 == "a1b2c3"

    def test_parse_filename_extracts_extension(self):
        """Parsed filename should correctly extract extension."""
        filename = "1234567890123456789_2026-01-13_a1b2c3.mp4"
        parsed = parse_media_filename(filename)

        assert parsed is not None
        assert parsed.extension == "mp4"

    def test_generate_and_parse_roundtrip(self):
        """Generate then parse should recover original components."""
        tweet_id = "9876543210987654321"
        created_at = datetime(2025, 6, 15, 14, 45, 0)
        hash6 = "f0e1d2"
        extension = "png"

        filename = generate_media_filename(tweet_id, created_at, hash6, extension)
        parsed = parse_media_filename(filename)

        assert parsed is not None
        assert parsed.tweet_id == tweet_id
        assert parsed.date == "2025-06-15"
        assert parsed.hash6 == hash6
        assert parsed.extension == extension

    def test_extract_tweet_id_helper(self):
        """extract_tweet_id should return just the tweet ID."""
        filename = "1234567890123456789_2026-01-13_a1b2c3.jpg"
        assert extract_tweet_id(filename) == "1234567890123456789"

    def test_invalid_filename_returns_none(self):
        """Invalid filename should return None when parsed."""
        assert parse_media_filename("invalid.jpg") is None
        assert parse_media_filename("no_date_hash.jpg") is None
        assert parse_media_filename("123_2026-01-13.jpg") is None  # Missing hash6

    def test_hash6_must_be_6_chars(self):
        """hash6 must be exactly 6 characters."""
        with self.assertRaisesRegex(ValueError, "exactly 6"):
            generate_media_filename("123", datetime.now(), "abc", "jpg")

        with self.assertRaisesRegex(ValueError, "exactly 6"):
            generate_media_filename("123", datetime.now(), "abcdefg", "jpg")

    def test_hash6_must_be_hex(self):
        """hash6 must be hexadecimal."""
        with self.assertRaisesRegex(ValueError, "hexadecimal"):
            generate_media_filename("123", datetime.now(), "ghijkl", "jpg")


class TestHashing(unittest.TestCase):
    """Tests for content hashing."""

    def test_hash6_equals_first_6_chars(self):
        """hash6 should equal first 6 characters of full hash."""
        content = b"test content for hashing"
        full_hash = compute_bytes_hash(content)
        hash6 = compute_hash6(full_hash)

        assert hash6 == full_hash[:6]
        assert len(hash6) == 6

    def test_hash6_is_lowercase(self):
        """hash6 should always be lowercase."""
        # SHA-256 produces lowercase by default, but let's verify
        full_hash = "ABCDEF1234567890" * 4  # Fake uppercase hash
        hash6 = compute_hash6(full_hash)

        assert hash6 == "abcdef"
        assert hash6.islower()

    def test_file_hash_consistency(self):
        """Same content should always produce same hash."""
        content = b"consistent content test"

        with tempfile.NamedTemporaryFile(delete=False) as f:
            f.write(content)
            temp_path = Path(f.name)

        try:
            hash1 = compute_file_hash(temp_path)
            hash2 = compute_file_hash(temp_path)
            bytes_hash = compute_bytes_hash(content)

            assert hash1 == hash2
            assert hash1 == bytes_hash
        finally:
            temp_path.unlink()

    def test_stream_hasher_matches_bytes_hash(self):
        """StreamHasher should produce same hash as compute_bytes_hash."""
        content = b"stream hasher test content"

        hasher = StreamHasher()
        hasher.update(content)

        assert hasher.hexdigest() == compute_bytes_hash(content)
        assert hasher.hash6() == compute_hash6(compute_bytes_hash(content))


class TestDedup(unittest.TestCase):
    """Tests for deduplication logic."""

    def test_first_content_is_new(self):
        """First occurrence of content should be marked as new."""
        index = DedupIndex()
        content_hash = "abcdef1234567890" * 4

        result = index.check_and_register(content_hash)

        assert result.result == DedupResult.NEW

    def test_second_content_is_duplicate(self):
        """Second occurrence of same content should be marked as duplicate."""
        index = DedupIndex()
        content_hash = "abcdef1234567890" * 4

        result1 = index.check_and_register(content_hash, Path("/first/file.jpg"))
        result2 = index.check_and_register(content_hash, Path("/second/file.jpg"))

        assert result1.result == DedupResult.NEW
        assert result2.result == DedupResult.DUPLICATE
        assert result2.existing_file == Path("/first/file.jpg")

    def test_different_content_both_new(self):
        """Different content hashes should both be marked as new."""
        index = DedupIndex()
        hash1 = "a" * 64
        hash2 = "b" * 64

        result1 = index.check_and_register(hash1)
        result2 = index.check_and_register(hash2)

        assert result1.result == DedupResult.NEW
        assert result2.result == DedupResult.NEW

    def test_stats_track_duplicates(self):
        """Statistics should correctly track duplicates."""
        index = DedupIndex()
        content_hash = "c" * 64

        index.check_and_register(content_hash)
        index.check_and_register(content_hash)
        index.check_and_register(content_hash)

        assert index.total_checked == 3
        assert index.duplicates_found == 2

    def test_load_from_directory(self):
        """Loading from directory should populate hash index."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create test files
            file1 = Path(tmpdir) / "file1.jpg"
            file2 = Path(tmpdir) / "file2.jpg"
            file1.write_bytes(b"content one")
            file2.write_bytes(b"content two")

            index = DedupIndex()
            loaded = index.load_from_directory(Path(tmpdir))

            assert loaded == 2
            assert len(index.known_hashes) == 2

            # New download with same content should be duplicate
            hash1 = compute_bytes_hash(b"content one")
            result = index.check_and_register(hash1)
            assert result.result == DedupResult.DUPLICATE


class TestDownloaderDedup(unittest.TestCase):
    """Tests for downloader with deduplication."""

    def test_first_wins_keeps_first_download(self):
        """First download should be kept, second with same content skipped."""
        with tempfile.TemporaryDirectory() as tmpdir:
            storage = AccountStorageManager(Path(tmpdir))
            handle = "testuser"

            # Mock download function returning same content
            same_content = b"identical image content"
            download_func = lambda url: same_content

            downloader = MediaDownloader(storage, handle, download_func)

            # First download
            intent1 = MediaIntent(
                url="https://example.com/image1.jpg",
                tweet_id="111",
                created_at=datetime(2026, 1, 13, 12, 0, 0),
                media_type=MediaType.IMAGE,
            )
            result1 = downloader.download(intent1)

            # Second download with same content
            intent2 = MediaIntent(
                url="https://example.com/image2.jpg",
                tweet_id="222",
                created_at=datetime(2026, 1, 13, 11, 0, 0),
                media_type=MediaType.IMAGE,
            )
            result2 = downloader.download(intent2)

            # First should succeed, second should be duplicate
            assert result1.status == DownloadStatus.SUCCESS
            assert result2.status == DownloadStatus.SKIPPED_DUPLICATE

            # Stats should reflect this
            assert downloader.stats.images_downloaded == 1
            assert downloader.stats.skipped_duplicate == 1

    def test_skipped_duplicate_count_increments(self):
        """skipped_duplicate stat should increment for each duplicate."""
        with tempfile.TemporaryDirectory() as tmpdir:
            storage = AccountStorageManager(Path(tmpdir))
            handle = "testuser"

            same_content = b"duplicate content"
            download_func = lambda url: same_content

            downloader = MediaDownloader(storage, handle, download_func)

            # Download same content 5 times
            for i in range(5):
                intent = MediaIntent(
                    url=f"https://example.com/image{i}.jpg",
                    tweet_id=str(i),
                    created_at=datetime(2026, 1, 13, 12 - i, 0, 0),
                    media_type=MediaType.IMAGE,
                )
                downloader.download(intent)

            # 1 success + 4 duplicates
            assert downloader.stats.images_downloaded == 1
            assert downloader.stats.skipped_duplicate == 4

    def test_different_content_all_downloaded(self):
        """Different content should all be downloaded."""
        with tempfile.TemporaryDirectory() as tmpdir:
            storage = AccountStorageManager(Path(tmpdir))
            handle = "testuser"

            content_counter = [0]
            def download_func(url):
                content_counter[0] += 1
                return f"unique content {content_counter[0]}".encode()

            downloader = MediaDownloader(storage, handle, download_func)

            # Download 3 different images
            for i in range(3):
                intent = MediaIntent(
                    url=f"https://example.com/image{i}.jpg",
                    tweet_id=str(i),
                    created_at=datetime(2026, 1, 13, 12 - i, 0, 0),
                    media_type=MediaType.IMAGE,
                )
                downloader.download(intent)

            assert downloader.stats.images_downloaded == 3
            assert downloader.stats.skipped_duplicate == 0

    def test_filename_contains_correct_hash6(self):
        """Downloaded file should have correct hash6 in filename."""
        with tempfile.TemporaryDirectory() as tmpdir:
            storage = AccountStorageManager(Path(tmpdir))
            handle = "testuser"

            content = b"specific content for hash test"
            expected_hash = compute_bytes_hash(content)
            expected_hash6 = expected_hash[:6]

            download_func = lambda url: content

            downloader = MediaDownloader(storage, handle, download_func)

            intent = MediaIntent(
                url="https://example.com/image.jpg",
                tweet_id="12345",
                created_at=datetime(2026, 1, 13, 12, 0, 0),
                media_type=MediaType.IMAGE,
            )
            result = downloader.download(intent)

            assert result.status == DownloadStatus.SUCCESS
            assert result.file_path is not None

            # Parse filename and verify hash6
            parsed = parse_media_filename(result.file_path.name)
            assert parsed is not None
            assert parsed.hash6 == expected_hash6

    def test_newest_first_sorting(self):
        """download_all with sort_newest_first should process newest first."""
        with tempfile.TemporaryDirectory() as tmpdir:
            storage = AccountStorageManager(Path(tmpdir))
            handle = "testuser"

            # Same content for all - only first (newest) should be kept
            same_content = b"same for all"
            download_func = lambda url: same_content

            downloader = MediaDownloader(storage, handle, download_func)

            intents = [
                MediaIntent(
                    url="https://example.com/oldest.jpg",
                    tweet_id="100",
                    created_at=datetime(2026, 1, 10, 12, 0, 0),
                    media_type=MediaType.IMAGE,
                ),
                MediaIntent(
                    url="https://example.com/newest.jpg",
                    tweet_id="300",
                    created_at=datetime(2026, 1, 13, 12, 0, 0),
                    media_type=MediaType.IMAGE,
                ),
                MediaIntent(
                    url="https://example.com/middle.jpg",
                    tweet_id="200",
                    created_at=datetime(2026, 1, 11, 12, 0, 0),
                    media_type=MediaType.IMAGE,
                ),
            ]

            results = downloader.download_all(intents, sort_newest_first=True)

            # First result (newest) should succeed
            assert results[0].status == DownloadStatus.SUCCESS
            assert results[0].tweet_id == "300"  # Newest

            # Others should be duplicates
            assert results[1].status == DownloadStatus.SKIPPED_DUPLICATE
            assert results[2].status == DownloadStatus.SKIPPED_DUPLICATE


class TestStorageDirectory(unittest.TestCase):
    """Tests for storage directory structure."""

    def test_account_directory_structure(self):
        """Account directories should follow <root>/<handle>/{images,videos}/."""
        with tempfile.TemporaryDirectory() as tmpdir:
            storage = AccountStorageManager(Path(tmpdir))
            handle = "testuser"

            paths = storage.ensure_account_dirs(handle)

            assert paths.root == Path(tmpdir) / "testuser"
            assert paths.images == Path(tmpdir) / "testuser" / "images"
            assert paths.videos == Path(tmpdir) / "testuser" / "videos"

            # Directories should exist
            assert paths.images.exists()
            assert paths.videos.exists()

    def test_media_type_routing(self):
        """Images and videos should go to correct directories."""
        with tempfile.TemporaryDirectory() as tmpdir:
            storage = AccountStorageManager(Path(tmpdir))
            handle = "testuser"

            content_counter = [0]
            def download_func(url):
                content_counter[0] += 1
                return f"content {content_counter[0]}".encode()

            downloader = MediaDownloader(storage, handle, download_func)

            # Download an image
            image_intent = MediaIntent(
                url="https://example.com/image.jpg",
                tweet_id="111",
                created_at=datetime(2026, 1, 13, 12, 0, 0),
                media_type=MediaType.IMAGE,
            )
            image_result = downloader.download(image_intent)

            # Download a video
            video_intent = MediaIntent(
                url="https://example.com/video.mp4",
                tweet_id="222",
                created_at=datetime(2026, 1, 13, 11, 0, 0),
                media_type=MediaType.VIDEO,
            )
            video_result = downloader.download(video_intent)

            # Check directories
            assert image_result.file_path.parent.name == "images"
            assert video_result.file_path.parent.name == "videos"
