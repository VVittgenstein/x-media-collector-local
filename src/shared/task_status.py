"""
Task status enum shared across backend modules and tests.

Contract (ADR-0002):
    Idle / Queued / Running / Done / Failed / Cancelled
"""

from __future__ import annotations

from enum import Enum


class TaskStatus(str, Enum):
    IDLE = "Idle"
    QUEUED = "Queued"
    RUNNING = "Running"
    DONE = "Done"
    FAILED = "Failed"
    CANCELLED = "Cancelled"

    def is_locked(self) -> bool:
        return self in (TaskStatus.QUEUED, TaskStatus.RUNNING)

