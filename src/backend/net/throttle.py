"""
Request throttling with configurable minimum interval and random jitter.

Conservative defaults to minimize risk of rate limiting or account restrictions.
"""

from __future__ import annotations

import asyncio
import random
import time
from dataclasses import dataclass
from typing import Optional


# Conservative defaults (can be tuned based on real-world experience)
DEFAULT_MIN_INTERVAL_S = 1.5  # Minimum seconds between requests
DEFAULT_JITTER_MAX_S = 1.0    # Random jitter up to this value (added to min_interval)


@dataclass
class ThrottleConfig:
    """
    Configuration for request throttling.

    Attributes:
        min_interval_s: Minimum seconds between requests.
        jitter_max_s: Maximum random jitter added to min_interval.
        enabled: If False, throttling is disabled (for testing).
    """
    min_interval_s: float = DEFAULT_MIN_INTERVAL_S
    jitter_max_s: float = DEFAULT_JITTER_MAX_S
    enabled: bool = True

    def to_persist_dict(self) -> dict:
        return {
            "min_interval_s": self.min_interval_s,
            "jitter_max_s": self.jitter_max_s,
            "enabled": self.enabled,
        }

    @classmethod
    def from_persist_dict(cls, data: dict) -> "ThrottleConfig":
        min_interval = data.get("min_interval_s", DEFAULT_MIN_INTERVAL_S)
        jitter_max = data.get("jitter_max_s", DEFAULT_JITTER_MAX_S)
        enabled = data.get("enabled", True)

        try:
            min_interval = float(min_interval)
        except (TypeError, ValueError):
            min_interval = DEFAULT_MIN_INTERVAL_S

        try:
            jitter_max = float(jitter_max)
        except (TypeError, ValueError):
            jitter_max = DEFAULT_JITTER_MAX_S

        return cls(
            min_interval_s=max(0.0, min_interval),
            jitter_max_s=max(0.0, jitter_max),
            enabled=bool(enabled),
        )


class Throttle:
    """
    Thread-safe request throttler with minimum interval and random jitter.

    Usage:
        throttle = Throttle()

        # Sync usage
        throttle.wait()
        make_request()

        # Async usage
        await throttle.wait_async()
        await make_async_request()

    The throttler ensures requests are spaced at least `min_interval_s` apart,
    with an additional random jitter of up to `jitter_max_s` seconds.
    """

    def __init__(self, config: Optional[ThrottleConfig] = None) -> None:
        self._config = config or ThrottleConfig()
        self._last_request_time: Optional[float] = None
        self._lock = asyncio.Lock()

    @property
    def config(self) -> ThrottleConfig:
        return self._config

    def _compute_delay(self) -> float:
        """Compute the delay needed before next request."""
        if not self._config.enabled:
            return 0.0

        now = time.monotonic()

        if self._last_request_time is None:
            # First request, only add jitter
            jitter = random.uniform(0, self._config.jitter_max_s)
            return jitter

        elapsed = now - self._last_request_time
        base_delay = self._config.min_interval_s - elapsed

        if base_delay <= 0:
            # Already past minimum interval, just add jitter
            jitter = random.uniform(0, self._config.jitter_max_s)
            return jitter

        # Need to wait + jitter
        jitter = random.uniform(0, self._config.jitter_max_s)
        return base_delay + jitter

    def wait(self) -> float:
        """
        Block (sync) until it's safe to make the next request.

        Returns:
            The actual delay waited (in seconds).
        """
        delay = self._compute_delay()
        if delay > 0:
            time.sleep(delay)
        self._last_request_time = time.monotonic()
        return delay

    async def wait_async(self) -> float:
        """
        Wait (async) until it's safe to make the next request.

        Returns:
            The actual delay waited (in seconds).
        """
        async with self._lock:
            delay = self._compute_delay()
            if delay > 0:
                await asyncio.sleep(delay)
            self._last_request_time = time.monotonic()
            return delay

    def reset(self) -> None:
        """Reset the throttler state (for testing)."""
        self._last_request_time = None
