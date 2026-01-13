"""
Lifecycle operations for managing task file states.
"""

from __future__ import annotations

from pathlib import Path
from typing import NamedTuple

from src.backend.fs import AccountStorageManager, MediaType
from src.backend.fs.archive_zip import archive_account_files, delete_account_files

from .models import StartMode, CancelMode


class ExistingFilesInfo(NamedTuple):
    """Information about existing files in an account directory."""
    has_files: bool
    image_count: int
    video_count: int
    total_count: int


class StartPrepareResult(NamedTuple):
    """Result of preparing for a Start New operation."""
    success: bool
    mode: StartMode
    files_deleted: int
    files_archived: int
    archive_path: str | None
    error: str | None


class CancelPrepareResult(NamedTuple):
    """Result of preparing for a Cancel operation."""
    success: bool
    mode: CancelMode
    files_deleted: int
    error: str | None


def check_existing_files(
    storage: AccountStorageManager,
    handle: str,
) -> ExistingFilesInfo:
    """
    Check if an account has existing media files.

    Args:
        storage: The account storage manager.
        handle: The Twitter handle.

    Returns:
        ExistingFilesInfo with file counts.
    """
    image_files = storage.list_media_files(handle, MediaType.IMAGE)
    video_files = storage.list_media_files(handle, MediaType.VIDEO)

    image_count = len(image_files)
    video_count = len(video_files)
    total_count = image_count + video_count

    return ExistingFilesInfo(
        has_files=total_count > 0,
        image_count=image_count,
        video_count=video_count,
        total_count=total_count,
    )


def prepare_start_new(
    storage: AccountStorageManager,
    handle: str,
    mode: StartMode,
) -> StartPrepareResult:
    """
    Prepare for a Start New operation based on the selected mode.

    Args:
        storage: The account storage manager.
        handle: The Twitter handle.
        mode: The start mode (DELETE, IGNORE_REPLACE, or PACK).

    Returns:
        StartPrepareResult with operation details.
    """
    paths = storage.get_account_paths(handle)

    if mode == StartMode.IGNORE_REPLACE:
        # No preparation needed, files will be handled during run
        return StartPrepareResult(
            success=True,
            mode=mode,
            files_deleted=0,
            files_archived=0,
            archive_path=None,
            error=None,
        )

    if mode == StartMode.DELETE:
        try:
            files_deleted = delete_account_files(paths.images, paths.videos)
            return StartPrepareResult(
                success=True,
                mode=mode,
                files_deleted=files_deleted,
                files_archived=0,
                archive_path=None,
                error=None,
            )
        except OSError as e:
            return StartPrepareResult(
                success=False,
                mode=mode,
                files_deleted=0,
                files_archived=0,
                archive_path=None,
                error=f"Failed to delete files: {e}",
            )

    if mode == StartMode.PACK:
        try:
            # Ensure account root exists
            paths.root.mkdir(parents=True, exist_ok=True)

            result = archive_account_files(
                account_root=paths.root,
                images_dir=paths.images,
                videos_dir=paths.videos,
                handle=handle,
            )

            if result is None:
                # No files to archive
                return StartPrepareResult(
                    success=True,
                    mode=mode,
                    files_deleted=0,
                    files_archived=0,
                    archive_path=None,
                    error=None,
                )

            return StartPrepareResult(
                success=True,
                mode=mode,
                files_deleted=result.files_archived,  # Files are deleted after archiving
                files_archived=result.files_archived,
                archive_path=str(result.zip_path),
                error=None,
            )
        except OSError as e:
            return StartPrepareResult(
                success=False,
                mode=mode,
                files_deleted=0,
                files_archived=0,
                archive_path=None,
                error=f"Failed to archive files: {e}",
            )

    # Shouldn't reach here
    return StartPrepareResult(
        success=False,
        mode=mode,
        files_deleted=0,
        files_archived=0,
        archive_path=None,
        error=f"Unknown start mode: {mode}",
    )


def prepare_cancel_running(
    storage: AccountStorageManager,
    handle: str,
    mode: CancelMode,
) -> CancelPrepareResult:
    """
    Prepare for a Cancel operation based on the selected mode.

    Note: For DELETE mode, this deletes ALL files in the account directory,
    not just files from the current run. This is a simplified implementation.
    A more sophisticated implementation would track which files were created
    in the current run.

    Args:
        storage: The account storage manager.
        handle: The Twitter handle.
        mode: The cancel mode (KEEP or DELETE).

    Returns:
        CancelPrepareResult with operation details.
    """
    if mode == CancelMode.KEEP:
        return CancelPrepareResult(
            success=True,
            mode=mode,
            files_deleted=0,
            error=None,
        )

    if mode == CancelMode.DELETE:
        paths = storage.get_account_paths(handle)
        try:
            files_deleted = delete_account_files(paths.images, paths.videos)
            return CancelPrepareResult(
                success=True,
                mode=mode,
                files_deleted=files_deleted,
                error=None,
            )
        except OSError as e:
            return CancelPrepareResult(
                success=False,
                mode=mode,
                files_deleted=0,
                error=f"Failed to delete files: {e}",
            )

    return CancelPrepareResult(
        success=False,
        mode=mode,
        files_deleted=0,
        error=f"Unknown cancel mode: {mode}",
    )
