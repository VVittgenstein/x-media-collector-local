"""
Task lifecycle management for Start New / Continue / Cancel operations.

Provides:
- StartMode: Actions for handling existing files on Start New
- CancelMode: Actions for handling files on Cancel Running
- Lifecycle operations API
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from .models import StartMode, CancelMode
from .operations import (
    check_existing_files,
    prepare_start_new,
    prepare_cancel_running,
    ExistingFilesInfo,
    StartPrepareResult,
    CancelPrepareResult,
)

if TYPE_CHECKING:
    from src.backend.fs import AccountStorageManager
    from fastapi import APIRouter  # pragma: no cover


def create_lifecycle_router(*, storage: "AccountStorageManager") -> "APIRouter":
    """
    Lazily import FastAPI router to keep non-web imports lightweight.
    """
    from .api import create_lifecycle_router as _create_lifecycle_router

    return _create_lifecycle_router(storage=storage)

__all__ = [
    "StartMode",
    "CancelMode",
    "check_existing_files",
    "prepare_start_new",
    "prepare_cancel_running",
    "ExistingFilesInfo",
    "StartPrepareResult",
    "CancelPrepareResult",
    "create_lifecycle_router",
]
