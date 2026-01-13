from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Optional

from src.backend.lifecycle.models import StartMode
from src.shared.task_status import TaskStatus


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def format_utc_z(dt: datetime) -> str:
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


@dataclass
class Run:
    run_id: str
    handle: str
    kind: str  # "start" | "continue"
    account_config: dict[str, Any]
    status: TaskStatus
    created_at: datetime
    updated_at: datetime
    start_mode: Optional[StartMode] = None
    error: Optional[str] = None

    def to_public_dict(self) -> dict[str, Any]:
        return {
            "run_id": self.run_id,
            "handle": self.handle,
            "kind": self.kind,
            "status": self.status.value,
            "created_at": format_utc_z(self.created_at),
            "updated_at": format_utc_z(self.updated_at),
            "start_mode": self.start_mode.value if self.start_mode is not None else None,
            "error": self.error,
            "account_config": self.account_config,
        }
