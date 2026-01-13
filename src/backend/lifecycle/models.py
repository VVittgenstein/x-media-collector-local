"""
Models for task lifecycle operations.
"""

from __future__ import annotations

from enum import Enum


class StartMode(str, Enum):
    """
    Mode for handling existing files when starting a new task.

    - DELETE: Delete all existing files and start fresh
    - IGNORE_REPLACE: Keep existing files, new run will replace duplicates (by hash)
    - PACK: Archive existing files to zip and start fresh
    """
    DELETE = "delete"
    IGNORE_REPLACE = "ignore_replace"
    PACK = "pack"


class CancelMode(str, Enum):
    """
    Mode for handling files when cancelling a running task.

    - KEEP: Keep all downloaded files (partial progress preserved)
    - DELETE: Delete all files downloaded in this run
    """
    KEEP = "keep"
    DELETE = "delete"
