"""
API routes for task lifecycle operations.
"""

from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from src.backend.fs import AccountStorageManager

from .models import StartMode, CancelMode
from .operations import (
    check_existing_files,
    prepare_start_new,
    prepare_cancel_running,
)


class CheckExistingFilesOut(BaseModel):
    """Response for checking existing files."""
    handle: str
    has_files: bool
    image_count: int
    video_count: int
    total_count: int


class PrepareStartIn(BaseModel):
    """Request body for prepare start operation."""
    handle: str = Field(min_length=1)
    mode: StartMode


class PrepareStartOut(BaseModel):
    """Response for prepare start operation."""
    success: bool
    mode: StartMode
    files_deleted: int
    files_archived: int
    archive_path: Optional[str] = None
    error: Optional[str] = None


class PrepareCancelIn(BaseModel):
    """Request body for prepare cancel operation."""
    handle: str = Field(min_length=1)
    mode: CancelMode


class PrepareCancelOut(BaseModel):
    """Response for prepare cancel operation."""
    success: bool
    mode: CancelMode
    files_deleted: int
    error: Optional[str] = None


def create_lifecycle_router(*, storage: AccountStorageManager) -> APIRouter:
    """
    Create the lifecycle API router.

    Args:
        storage: The account storage manager.

    Returns:
        FastAPI router with lifecycle endpoints.
    """
    router = APIRouter(prefix="/api/lifecycle", tags=["lifecycle"])

    @router.get("/check/{handle}", response_model=CheckExistingFilesOut)
    async def check_existing(handle: str) -> CheckExistingFilesOut:
        """
        Check if an account has existing media files.

        This is called before Start New to determine if the user needs
        to choose how to handle existing files.
        """
        info = check_existing_files(storage, handle)
        return CheckExistingFilesOut(
            handle=handle,
            has_files=info.has_files,
            image_count=info.image_count,
            video_count=info.video_count,
            total_count=info.total_count,
        )

    @router.post("/prepare-start", response_model=PrepareStartOut)
    async def prepare_start(body: PrepareStartIn) -> PrepareStartOut:
        """
        Prepare for a Start New operation.

        This performs the file operations (delete/archive) before
        the actual task starts.
        """
        result = prepare_start_new(storage, body.handle, body.mode)

        if not result.success:
            raise HTTPException(status_code=500, detail=result.error)

        return PrepareStartOut(
            success=result.success,
            mode=result.mode,
            files_deleted=result.files_deleted,
            files_archived=result.files_archived,
            archive_path=result.archive_path,
            error=result.error,
        )

    @router.post("/prepare-cancel", response_model=PrepareCancelOut)
    async def prepare_cancel(body: PrepareCancelIn) -> PrepareCancelOut:
        """
        Prepare for a Cancel operation.

        This performs file cleanup (if DELETE mode) after cancelling
        a running task.
        """
        result = prepare_cancel_running(storage, body.handle, body.mode)

        if not result.success:
            raise HTTPException(status_code=500, detail=result.error)

        return PrepareCancelOut(
            success=result.success,
            mode=result.mode,
            files_deleted=result.files_deleted,
            error=result.error,
        )

    return router
