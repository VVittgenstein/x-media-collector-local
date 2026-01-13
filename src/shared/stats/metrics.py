from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional


def _ensure_utc(dt: datetime) -> datetime:
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def compute_runtime_s(
    started_at: Optional[datetime],
    finished_at: Optional[datetime],
    *,
    now: Optional[datetime] = None,
) -> float:
    """
    Compute runtime in seconds.

    Contract:
    - Runtime starts when entering Running (started_at).
    - Queued time must not be included (started_at should be None while Queued).
    """
    if started_at is None:
        return 0.0

    if now is None:
        now = datetime.now(timezone.utc)

    start = _ensure_utc(started_at)
    end = _ensure_utc(finished_at) if finished_at is not None else _ensure_utc(now)

    runtime_s = (end - start).total_seconds()
    return max(0.0, float(runtime_s))


def compute_avg_speed(
    images_downloaded: int,
    videos_downloaded: int,
    skipped_duplicate: int,
    runtime_s: float,
) -> float:
    """
    avg_speed = (images_downloaded + videos_downloaded + skipped_duplicate) / runtime
    (runtime > 0)
    """
    if runtime_s <= 0:
        return 0.0

    total = int(images_downloaded) + int(videos_downloaded) + int(skipped_duplicate)
    return float(total) / float(runtime_s)
