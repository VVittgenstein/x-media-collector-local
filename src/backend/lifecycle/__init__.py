"""
Task lifecycle management for Start New / Continue / Cancel operations.

Provides:
- StartMode: Actions for handling existing files on Start New
- CancelMode: Actions for handling files on Cancel Running
- Lifecycle operations API
"""

from .models import StartMode, CancelMode
from .operations import (
    check_existing_files,
    prepare_start_new,
    prepare_cancel_running,
    ExistingFilesInfo,
    StartPrepareResult,
    CancelPrepareResult,
)
from .api import create_lifecycle_router

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
