"""
Archive utilities for packing account media files into zip archives.

Used by Pack&Restart lifecycle action to preserve existing files before a fresh run.
"""

from __future__ import annotations

import zipfile
from datetime import datetime, timezone
from pathlib import Path
from typing import NamedTuple


class ArchiveResult(NamedTuple):
    """Result of an archive operation."""
    zip_path: Path
    files_archived: int
    bytes_archived: int


def generate_archive_name(handle: str) -> str:
    """
    Generate a timestamped archive filename.

    Format: {handle}_archive_{YYYYMMDD_HHMMSS}.zip

    Args:
        handle: The Twitter handle.

    Returns:
        Archive filename string.
    """
    now = datetime.now(timezone.utc)
    timestamp = now.strftime("%Y%m%d_%H%M%S")
    return f"{handle}_archive_{timestamp}.zip"


def archive_account_files(
    account_root: Path,
    images_dir: Path,
    videos_dir: Path,
    handle: str,
) -> ArchiveResult | None:
    """
    Archive all media files from an account directory into a zip file.

    The zip file is created in the account root directory.
    After archiving, the original files are deleted (but not the directories).

    Args:
        account_root: Path to the account root directory.
        images_dir: Path to the images subdirectory.
        videos_dir: Path to the videos subdirectory.
        handle: The Twitter handle (used for naming the archive).

    Returns:
        ArchiveResult with archive path and statistics, or None if no files to archive.

    Raises:
        OSError: If archive creation or file operations fail.
    """
    # Collect all files to archive
    files_to_archive: list[tuple[Path, str]] = []  # (full_path, archive_name)

    if images_dir.exists():
        for f in images_dir.iterdir():
            if f.is_file():
                files_to_archive.append((f, f"images/{f.name}"))

    if videos_dir.exists():
        for f in videos_dir.iterdir():
            if f.is_file():
                files_to_archive.append((f, f"videos/{f.name}"))

    if not files_to_archive:
        return None

    # Create archive
    archive_name = generate_archive_name(handle)
    zip_path = account_root / archive_name

    bytes_archived = 0

    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
        for file_path, archive_name_in_zip in files_to_archive:
            zf.write(file_path, archive_name_in_zip)
            bytes_archived += file_path.stat().st_size

    # Delete original files after successful archiving
    for file_path, _ in files_to_archive:
        file_path.unlink()

    return ArchiveResult(
        zip_path=zip_path,
        files_archived=len(files_to_archive),
        bytes_archived=bytes_archived,
    )


def delete_account_files(
    images_dir: Path,
    videos_dir: Path,
) -> int:
    """
    Delete all media files from an account directory.

    Directories are preserved, only files are deleted.

    Args:
        images_dir: Path to the images subdirectory.
        videos_dir: Path to the videos subdirectory.

    Returns:
        Number of files deleted.

    Raises:
        OSError: If file deletion fails.
    """
    files_deleted = 0

    if images_dir.exists():
        for f in images_dir.iterdir():
            if f.is_file():
                f.unlink()
                files_deleted += 1

    if videos_dir.exists():
        for f in videos_dir.iterdir():
            if f.is_file():
                f.unlink()
                files_deleted += 1

    return files_deleted
