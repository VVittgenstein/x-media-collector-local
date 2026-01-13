"""
Content-hash based deduplication for media downloads.

Implements "first wins" deduplication within an account:
- Media is processed from newest to oldest (by created_at)
- The first occurrence of a content hash is kept
- Subsequent occurrences with the same hash are skipped and counted as duplicates

The DedupIndex maintains an in-memory hash set for the current run and can
optionally load existing hashes from the account directory.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Optional

from ..fs.hashing import compute_file_hash
from ..fs.naming import parse_media_filename


class DedupResult(str, Enum):
    """Result of a deduplication check."""
    NEW = "new"              # Content is new, should be kept
    DUPLICATE = "duplicate"  # Content is a duplicate, should be skipped


@dataclass
class DedupCheckResult:
    """Result of checking a file for duplication."""
    result: DedupResult
    content_hash: str
    existing_file: Optional[Path] = None  # Path to existing file if duplicate


@dataclass
class DedupIndex:
    """
    In-memory index for content-hash based deduplication.

    Tracks content hashes seen during the current run and optionally
    loads existing hashes from previously downloaded files.

    Usage:
        # Create index for an account
        index = DedupIndex()

        # Optionally load existing files
        index.load_from_directory(images_dir)
        index.load_from_directory(videos_dir)

        # Check each new download
        result = index.check_and_register(content_hash)
        if result.result == DedupResult.DUPLICATE:
            # Skip this file
            skipped_count += 1
    """

    # Hash -> first file path that had this hash (for debugging/logging)
    _hash_to_file: dict[str, Path] = field(default_factory=dict)

    # Statistics
    _total_checked: int = 0
    _duplicates_found: int = 0

    def __post_init__(self):
        """Initialize mutable default fields."""
        if not hasattr(self, '_hash_to_file') or self._hash_to_file is None:
            self._hash_to_file = {}

    @property
    def known_hashes(self) -> frozenset[str]:
        """Get the set of all known content hashes."""
        return frozenset(self._hash_to_file.keys())

    @property
    def total_checked(self) -> int:
        """Total number of items checked for duplication."""
        return self._total_checked

    @property
    def duplicates_found(self) -> int:
        """Number of duplicates found and skipped."""
        return self._duplicates_found

    def is_known(self, content_hash: str) -> bool:
        """
        Check if a content hash is already known.

        Args:
            content_hash: The SHA-256 hash of the content.

        Returns:
            True if the hash has been seen before.
        """
        return content_hash.lower() in self._hash_to_file

    def register(self, content_hash: str, file_path: Path) -> None:
        """
        Register a new content hash.

        Args:
            content_hash: The SHA-256 hash of the content.
            file_path: Path to the file with this content.
        """
        normalized_hash = content_hash.lower()
        if normalized_hash not in self._hash_to_file:
            self._hash_to_file[normalized_hash] = file_path

    def check_and_register(
        self,
        content_hash: str,
        file_path: Optional[Path] = None,
    ) -> DedupCheckResult:
        """
        Check if content is a duplicate and register if new.

        This is the main deduplication method. Call this for each piece
        of content after computing its hash.

        Args:
            content_hash: The SHA-256 hash of the content.
            file_path: Path to the file (for tracking).

        Returns:
            DedupCheckResult indicating if content is new or duplicate.
        """
        self._total_checked += 1
        normalized_hash = content_hash.lower()

        if normalized_hash in self._hash_to_file:
            self._duplicates_found += 1
            return DedupCheckResult(
                result=DedupResult.DUPLICATE,
                content_hash=normalized_hash,
                existing_file=self._hash_to_file[normalized_hash],
            )

        # New content - register it
        if file_path:
            self._hash_to_file[normalized_hash] = file_path
        else:
            # Use a placeholder if no path provided
            self._hash_to_file[normalized_hash] = Path(f"<hash:{normalized_hash[:8]}>")

        return DedupCheckResult(
            result=DedupResult.NEW,
            content_hash=normalized_hash,
        )

    def load_from_directory(self, directory: Path) -> int:
        """
        Load content hashes from existing files in a directory.

        This is used to support "first wins" behavior where existing files
        from previous runs are considered as having won.

        Args:
            directory: Directory containing media files.

        Returns:
            Number of files loaded.
        """
        if not directory.exists():
            return 0

        loaded = 0
        for file_path in directory.iterdir():
            if not file_path.is_file():
                continue

            # Skip hidden files and non-media files
            if file_path.name.startswith('.'):
                continue

            try:
                content_hash = compute_file_hash(file_path)
                self.register(content_hash, file_path)
                loaded += 1
            except (IOError, OSError):
                # Skip files we can't read
                continue

        return loaded

    def load_from_directories(self, *directories: Path) -> int:
        """
        Load content hashes from multiple directories.

        Args:
            directories: Directories to load from.

        Returns:
            Total number of files loaded.
        """
        return sum(self.load_from_directory(d) for d in directories)

    def get_existing_file(self, content_hash: str) -> Optional[Path]:
        """
        Get the path to an existing file with the given hash.

        Args:
            content_hash: The content hash to look up.

        Returns:
            Path to the existing file, or None if not found.
        """
        return self._hash_to_file.get(content_hash.lower())

    def clear(self) -> None:
        """Clear all tracked hashes and reset statistics."""
        self._hash_to_file.clear()
        self._total_checked = 0
        self._duplicates_found = 0

    def stats(self) -> dict:
        """
        Get deduplication statistics.

        Returns:
            Dictionary with statistics.
        """
        return {
            "total_checked": self._total_checked,
            "duplicates_found": self._duplicates_found,
            "unique_hashes": len(self._hash_to_file),
        }
