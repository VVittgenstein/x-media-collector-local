"""
Account storage directory structure management.

Directory structure:
    <download_root>/<handle>/images/
    <download_root>/<handle>/videos/
"""

from __future__ import annotations

from enum import Enum
from pathlib import Path
from typing import NamedTuple


class MediaType(str, Enum):
    """Type of media being stored."""
    IMAGE = "images"
    VIDEO = "videos"


class AccountPaths(NamedTuple):
    """Paths for an account's media storage."""
    root: Path        # <download_root>/<handle>/
    images: Path      # <download_root>/<handle>/images/
    videos: Path      # <download_root>/<handle>/videos/


class AccountStorageManager:
    """
    Manages directory structure for account media storage.

    Each account has a fixed directory structure:
        <download_root>/<handle>/images/
        <download_root>/<handle>/videos/
    """

    def __init__(self, download_root: Path):
        """
        Initialize the storage manager.

        Args:
            download_root: The root directory for all downloads.
        """
        self._download_root = Path(download_root).resolve()

    @property
    def download_root(self) -> Path:
        """Get the download root directory."""
        return self._download_root

    def get_account_paths(self, handle: str) -> AccountPaths:
        """
        Get the paths for an account's media storage.

        Args:
            handle: The Twitter handle (without @).

        Returns:
            AccountPaths with root, images, and videos paths.
        """
        account_root = self._download_root / handle
        return AccountPaths(
            root=account_root,
            images=account_root / MediaType.IMAGE.value,
            videos=account_root / MediaType.VIDEO.value,
        )

    def ensure_account_dirs(self, handle: str) -> AccountPaths:
        """
        Ensure the account directories exist, creating them if needed.

        Args:
            handle: The Twitter handle (without @).

        Returns:
            AccountPaths with the created directories.

        Raises:
            OSError: If directories cannot be created.
        """
        paths = self.get_account_paths(handle)
        paths.images.mkdir(parents=True, exist_ok=True)
        paths.videos.mkdir(parents=True, exist_ok=True)
        return paths

    def get_media_dir(self, handle: str, media_type: MediaType) -> Path:
        """
        Get the directory for a specific media type.

        Args:
            handle: The Twitter handle (without @).
            media_type: The type of media (IMAGE or VIDEO).

        Returns:
            Path to the media directory.
        """
        return self._download_root / handle / media_type.value

    def account_exists(self, handle: str) -> bool:
        """
        Check if an account directory already exists.

        Args:
            handle: The Twitter handle (without @).

        Returns:
            True if the account root directory exists.
        """
        return (self._download_root / handle).exists()

    def has_existing_files(self, handle: str) -> bool:
        """
        Check if an account has any existing media files.

        Args:
            handle: The Twitter handle (without @).

        Returns:
            True if there are any files in images/ or videos/ directories.
        """
        paths = self.get_account_paths(handle)

        # Check images directory
        if paths.images.exists():
            if any(paths.images.iterdir()):
                return True

        # Check videos directory
        if paths.videos.exists():
            if any(paths.videos.iterdir()):
                return True

        return False

    def list_media_files(self, handle: str, media_type: MediaType) -> list[Path]:
        """
        List all media files for an account.

        Args:
            handle: The Twitter handle (without @).
            media_type: The type of media (IMAGE or VIDEO).

        Returns:
            List of paths to media files.
        """
        media_dir = self.get_media_dir(handle, media_type)
        if not media_dir.exists():
            return []
        return [f for f in media_dir.iterdir() if f.is_file()]
