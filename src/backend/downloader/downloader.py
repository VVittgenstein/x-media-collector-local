"""
Media downloader with proper naming, storage, and deduplication.

Downloads media files following the project's storage conventions:
- Directory structure: <root>/<handle>/{images,videos}/
- Filename: <tweetId>_<YYYY-MM-DD>_<hash6>.<ext>
- Deduplication: Content hash based, first wins

Processing order: Tweets are processed from newest to oldest (by created_at)
to ensure "first wins" deduplication is predictable.
"""

from __future__ import annotations

import logging
import os
import tempfile
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Optional, Callable, Any

from ..fs.storage import AccountStorageManager, MediaType
from ..fs.naming import generate_media_filename, get_extension_from_url
from ..fs.hashing import compute_bytes_hash, compute_file_hash, compute_hash6
from .dedup import DedupIndex


class DownloadStatus(str, Enum):
    """Status of a single download."""
    SUCCESS = "success"
    SKIPPED_DUPLICATE = "skipped_duplicate"
    FAILED = "failed"


@dataclass
class DownloadResult:
    """Result of a single media download."""
    status: DownloadStatus
    media_url: str
    tweet_id: str
    created_at: datetime
    media_type: MediaType

    # Set on success
    file_path: Optional[Path] = None
    content_hash: Optional[str] = None

    # Set on duplicate
    existing_file: Optional[Path] = None

    # Set on failure
    error: Optional[str] = None


@dataclass
class DownloadStats:
    """Statistics for a download run."""
    images_downloaded: int = 0
    videos_downloaded: int = 0
    skipped_duplicate: int = 0
    failed: int = 0

    # Tracking
    total_bytes: int = 0

    def increment(self, result: DownloadResult) -> None:
        """Update stats based on a download result."""
        if result.status == DownloadStatus.SUCCESS:
            if result.media_type == MediaType.IMAGE:
                self.images_downloaded += 1
            else:
                self.videos_downloaded += 1
        elif result.status == DownloadStatus.SKIPPED_DUPLICATE:
            self.skipped_duplicate += 1
        elif result.status == DownloadStatus.FAILED:
            self.failed += 1

    @property
    def total_downloaded(self) -> int:
        """Total files successfully downloaded."""
        return self.images_downloaded + self.videos_downloaded

    @property
    def total_processed(self) -> int:
        """Total items processed (downloaded + skipped + failed)."""
        return self.total_downloaded + self.skipped_duplicate + self.failed

    def to_dict(self) -> dict:
        """Convert to dictionary."""
        return {
            "images_downloaded": self.images_downloaded,
            "videos_downloaded": self.videos_downloaded,
            "skipped_duplicate": self.skipped_duplicate,
            "failed": self.failed,
            "total_bytes": self.total_bytes,
        }


@dataclass
class MediaIntent:
    """
    Intent to download a media file.

    This is the input to the downloader, containing all information
    needed to download and store a media file.
    """
    url: str
    tweet_id: str
    created_at: datetime
    media_type: MediaType
    extension: Optional[str] = None  # If None, inferred from URL
    width: Optional[int] = None
    height: Optional[int] = None
    needs_post_min_short_side_check: bool = False

    def get_extension(self) -> str:
        """Get the file extension, inferring from URL if needed."""
        if self.extension:
            return self.extension
        return get_extension_from_url(self.url)


# Type for download function: (url) -> bytes
DownloadFunc = Callable[[str], bytes]


class MediaDownloader:
    """
    Downloads media files with proper naming, storage, and deduplication.

    Usage:
        downloader = MediaDownloader(
            storage=AccountStorageManager(download_root),
            handle="username",
            download_func=my_download_function,
        )

        # Optionally load existing files for dedup
        downloader.load_existing_files()

        # Download media (should be sorted newest to oldest)
        for intent in sorted_intents:
            result = downloader.download(intent)
            if result.status == DownloadStatus.SKIPPED_DUPLICATE:
                print(f"Skipped duplicate: {intent.url}")

        # Get statistics
        print(downloader.stats.to_dict())
    """

    def __init__(
        self,
        storage: AccountStorageManager,
        handle: str,
        download_func: DownloadFunc,
        *,
        ignore_replace: bool = False,
    ):
        """
        Initialize the downloader.

        Args:
            storage: Storage manager for directory structure.
            handle: Twitter handle for this account.
            download_func: Function to download content from a URL.
            ignore_replace: If True, enable ADR-0004 Ignore+Replace behavior:
                - Do NOT treat historical files as dedup winners
                - After successfully writing a new file, delete any historical files with same content hash
        """
        self._storage = storage
        self._handle = handle
        self._download_func = download_func
        self._ignore_replace = bool(ignore_replace)
        self._dedup = DedupIndex()
        self._stats = DownloadStats()
        self._paths = storage.ensure_account_dirs(handle)
        self._existing_hashes: dict[str, set[Path]] = {}
        self._existing_hashes_loaded = False

        self._log = logging.getLogger(__name__)

    @property
    def stats(self) -> DownloadStats:
        """Get download statistics."""
        return self._stats

    @property
    def dedup_index(self) -> DedupIndex:
        """Get the deduplication index."""
        return self._dedup

    def load_existing_files(self) -> int:
        """
        Load existing files for deduplication.

        Call this before downloading to support "first wins" behavior
        where existing files from previous runs are preserved.

        Returns:
            Number of existing files loaded.
        """
        return self._dedup.load_from_directories(
            self._paths.images,
            self._paths.videos,
        )

    def load_existing_files_for_replace(self) -> int:
        """
        Load existing files as "replace candidates" (Ignore+Replace mode).

        This scans existing media files and builds a mapping:
            content_hash -> {file_path, ...}

        Unlike `load_existing_files()`, this does NOT register hashes into the
        dedup index (because in Ignore+Replace mode, the current run wins).

        Returns:
            Number of existing files scanned (best-effort).
        """
        loaded = 0
        self._existing_hashes.clear()

        for directory in (self._paths.images, self._paths.videos):
            if not directory.exists():
                continue
            for file_path in directory.iterdir():
                if not file_path.is_file():
                    continue
                if file_path.name.startswith("."):
                    continue
                if file_path.suffix.lower() == ".tmp":
                    continue

                try:
                    content_hash = compute_file_hash(file_path)
                except (OSError, IOError):
                    continue

                normalized_hash = content_hash.lower()
                self._existing_hashes.setdefault(normalized_hash, set()).add(file_path)
                loaded += 1

        self._existing_hashes_loaded = True
        return loaded

    def download(self, intent: MediaIntent) -> DownloadResult:
        """
        Download a media file with deduplication.

        Args:
            intent: The media download intent.

        Returns:
            DownloadResult with status and details.
        """
        if self._ignore_replace and not self._existing_hashes_loaded:
            self.load_existing_files_for_replace()

        try:
            return self._download_impl(intent)
        except Exception as e:
            self._stats.failed += 1
            return DownloadResult(
                status=DownloadStatus.FAILED,
                media_url=intent.url,
                tweet_id=intent.tweet_id,
                created_at=intent.created_at,
                media_type=intent.media_type,
                error=str(e),
            )

    def _download_impl(self, intent: MediaIntent) -> DownloadResult:
        """Implementation of download with proper error handling."""
        # Get target directory
        target_dir = (
            self._paths.images
            if intent.media_type == MediaType.IMAGE
            else self._paths.videos
        )

        # Download content (sync; injected by caller)
        content = self._download_func(intent.url)

        # Compute content hash
        content_hash = compute_bytes_hash(content)
        hash6 = compute_hash6(content_hash)

        # Check for duplicate ("first wins")
        if self._dedup.is_known(content_hash):
            self._stats.skipped_duplicate += 1
            return DownloadResult(
                status=DownloadStatus.SKIPPED_DUPLICATE,
                media_url=intent.url,
                tweet_id=intent.tweet_id,
                created_at=intent.created_at,
                media_type=intent.media_type,
                content_hash=content_hash,
                existing_file=self._dedup.get_existing_file(content_hash),
            )

        # Generate filename
        extension = intent.get_extension()
        filename = generate_media_filename(
            tweet_id=intent.tweet_id,
            created_at=intent.created_at,
            hash6=hash6,
            extension=extension,
        )

        # Write to final location (write temp + atomic replace)
        final_path = target_dir / filename
        self._atomic_write_bytes(final_path, content)

        # Ignore+Replace: delete historical file(s) only after new file is safe
        if self._ignore_replace:
            self._delete_replaced_history_files(content_hash, final_path)

        # Update dedup index with actual path
        self._dedup.register(content_hash, final_path)

        # Update stats
        self._stats.total_bytes += len(content)
        if intent.media_type == MediaType.IMAGE:
            self._stats.images_downloaded += 1
        else:
            self._stats.videos_downloaded += 1

        return DownloadResult(
            status=DownloadStatus.SUCCESS,
            media_url=intent.url,
            tweet_id=intent.tweet_id,
            created_at=intent.created_at,
            media_type=intent.media_type,
            file_path=final_path,
            content_hash=content_hash,
        )

    def _atomic_write_bytes(self, final_path: Path, content: bytes) -> None:
        final_path.parent.mkdir(parents=True, exist_ok=True)
        fd, tmp_path_str = tempfile.mkstemp(
            dir=str(final_path.parent),
            prefix=f".{final_path.name}.",
            suffix=".tmp",
        )
        tmp_path = Path(tmp_path_str)
        try:
            with os.fdopen(fd, "wb") as f:
                f.write(content)
                f.flush()
                os.fsync(f.fileno())
            os.replace(tmp_path, final_path)
        finally:
            try:
                tmp_path.unlink()
            except FileNotFoundError:
                pass

    def _delete_replaced_history_files(self, content_hash: str, final_path: Path) -> None:
        normalized_hash = content_hash.lower()
        old_paths = self._existing_hashes.get(normalized_hash)
        if not old_paths:
            return

        survivors: set[Path] = {final_path}
        for old_path in list(old_paths):
            if old_path == final_path:
                continue
            try:
                old_path.unlink()
            except FileNotFoundError:
                continue
            except OSError as exc:
                self._log.warning("Ignore+Replace: failed to delete old file %s: %s", old_path, exc)
                survivors.add(old_path)

        self._existing_hashes[normalized_hash] = survivors

    def download_all(
        self,
        intents: list[MediaIntent],
        *,
        sort_newest_first: bool = True,
        on_progress: Optional[Callable[[int, int, DownloadResult], None]] = None,
    ) -> list[DownloadResult]:
        """
        Download multiple media files.

        Args:
            intents: List of media download intents.
            sort_newest_first: If True, sort by created_at descending (newest first)
                              to ensure "first wins" dedup is predictable.
            on_progress: Optional callback called after each download with
                        (current_index, total, result).

        Returns:
            List of DownloadResults in processing order.
        """
        if sort_newest_first:
            intents = sorted(intents, key=lambda i: i.created_at, reverse=True)

        results = []
        total = len(intents)

        for idx, intent in enumerate(intents):
            result = self.download(intent)
            results.append(result)

            if on_progress:
                on_progress(idx + 1, total, result)

        return results


def sort_intents_newest_first(intents: list[MediaIntent]) -> list[MediaIntent]:
    """
    Sort media intents from newest to oldest by created_at.

    This ordering is important for "first wins" deduplication to be predictable:
    - Newer tweets win over older tweets with same content hash
    - The behavior is explainable: "kept the most recent occurrence"

    Args:
        intents: List of media intents to sort.

    Returns:
        Sorted list (newest first).
    """
    return sorted(intents, key=lambda i: i.created_at, reverse=True)
