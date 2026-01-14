"""
Exponential backoff retry logic for handling transient errors (429, 5xx).

Conservative defaults to minimize risk of rate limiting or account restrictions.
"""

from __future__ import annotations

import asyncio
import logging
import random
import time
from dataclasses import dataclass, field
from typing import Callable, Optional, Set, TypeVar

# Conservative defaults
DEFAULT_MAX_RETRIES = 3
DEFAULT_BASE_DELAY_S = 2.0
DEFAULT_MAX_DELAY_S = 60.0
DEFAULT_JITTER_FACTOR = 0.25  # 25% jitter on top of computed delay

# HTTP status codes that trigger retry
DEFAULT_RETRYABLE_STATUS_CODES = frozenset({429, 500, 502, 503, 504})

T = TypeVar("T")
logger = logging.getLogger(__name__)


class RetryableError(Exception):
    """
    Exception indicating a retryable error.

    Attributes:
        status_code: Optional HTTP status code.
        message: Human-readable error message.
        should_retry: Whether this error should trigger retry logic.
    """

    def __init__(
        self,
        message: str,
        *,
        status_code: Optional[int] = None,
        should_retry: bool = True,
    ) -> None:
        super().__init__(message)
        self.status_code = status_code
        self.should_retry = should_retry


@dataclass
class RetryConfig:
    """
    Configuration for retry with exponential backoff.

    Attributes:
        max_retries: Maximum number of retry attempts (0 = no retries).
        base_delay_s: Initial delay before first retry.
        max_delay_s: Maximum delay cap (exponential backoff won't exceed this).
        jitter_factor: Random jitter as fraction of computed delay (0.0-1.0).
        retryable_status_codes: HTTP status codes that should trigger retry.
        enabled: If False, retry logic is disabled.
    """
    max_retries: int = DEFAULT_MAX_RETRIES
    base_delay_s: float = DEFAULT_BASE_DELAY_S
    max_delay_s: float = DEFAULT_MAX_DELAY_S
    jitter_factor: float = DEFAULT_JITTER_FACTOR
    retryable_status_codes: Set[int] = field(
        default_factory=lambda: set(DEFAULT_RETRYABLE_STATUS_CODES)
    )
    enabled: bool = True

    def to_persist_dict(self) -> dict:
        return {
            "max_retries": self.max_retries,
            "base_delay_s": self.base_delay_s,
            "max_delay_s": self.max_delay_s,
            "jitter_factor": self.jitter_factor,
            "retryable_status_codes": sorted(self.retryable_status_codes),
            "enabled": self.enabled,
        }

    @classmethod
    def from_persist_dict(cls, data: dict) -> "RetryConfig":
        max_retries = data.get("max_retries", DEFAULT_MAX_RETRIES)
        base_delay = data.get("base_delay_s", DEFAULT_BASE_DELAY_S)
        max_delay = data.get("max_delay_s", DEFAULT_MAX_DELAY_S)
        jitter_factor = data.get("jitter_factor", DEFAULT_JITTER_FACTOR)
        status_codes = data.get("retryable_status_codes", list(DEFAULT_RETRYABLE_STATUS_CODES))
        enabled = data.get("enabled", True)

        try:
            max_retries = int(max_retries)
        except (TypeError, ValueError):
            max_retries = DEFAULT_MAX_RETRIES

        try:
            base_delay = float(base_delay)
        except (TypeError, ValueError):
            base_delay = DEFAULT_BASE_DELAY_S

        try:
            max_delay = float(max_delay)
        except (TypeError, ValueError):
            max_delay = DEFAULT_MAX_DELAY_S

        try:
            jitter_factor = float(jitter_factor)
        except (TypeError, ValueError):
            jitter_factor = DEFAULT_JITTER_FACTOR

        if isinstance(status_codes, (list, tuple)):
            parsed_codes = set()
            for code in status_codes:
                try:
                    parsed_codes.add(int(code))
                except (TypeError, ValueError):
                    pass
            if not parsed_codes:
                parsed_codes = set(DEFAULT_RETRYABLE_STATUS_CODES)
        else:
            parsed_codes = set(DEFAULT_RETRYABLE_STATUS_CODES)

        return cls(
            max_retries=max(0, max_retries),
            base_delay_s=max(0.1, base_delay),
            max_delay_s=max(1.0, max_delay),
            jitter_factor=max(0.0, min(1.0, jitter_factor)),
            retryable_status_codes=parsed_codes,
            enabled=bool(enabled),
        )

    def compute_delay(self, attempt: int) -> float:
        """
        Compute delay for given attempt using exponential backoff with jitter.

        Args:
            attempt: Current attempt number (0-indexed).

        Returns:
            Delay in seconds before next retry.
        """
        # Exponential backoff: base * 2^attempt
        delay = self.base_delay_s * (2 ** attempt)

        # Cap at max delay
        delay = min(delay, self.max_delay_s)

        # Add jitter
        jitter = delay * random.uniform(0, self.jitter_factor)
        return delay + jitter

    def is_retryable_status(self, status_code: int) -> bool:
        """Check if HTTP status code should trigger retry."""
        return status_code in self.retryable_status_codes


def with_retry(
    func: Callable[[], T],
    *,
    config: Optional[RetryConfig] = None,
    on_retry: Optional[Callable[[int, Exception, float], None]] = None,
) -> T:
    """
    Execute a function with retry and exponential backoff (sync).

    Args:
        func: Function to execute.
        config: Retry configuration.
        on_retry: Optional callback called before each retry with
                  (attempt, exception, delay).

    Returns:
        The result of func().

    Raises:
        The last exception if all retries are exhausted.
    """
    cfg = config or RetryConfig()

    if not cfg.enabled:
        return func()

    last_exc: Optional[Exception] = None

    for attempt in range(cfg.max_retries + 1):
        try:
            return func()
        except RetryableError as exc:
            last_exc = exc
            if not exc.should_retry or attempt >= cfg.max_retries:
                raise
            delay = cfg.compute_delay(attempt)
            if on_retry:
                on_retry(attempt, exc, delay)
            else:
                logger.warning(
                    "Retry %d/%d after %.2fs: %s",
                    attempt + 1,
                    cfg.max_retries,
                    delay,
                    exc,
                )
            time.sleep(delay)
        except Exception as exc:
            # Check if it's an HTTP error with retryable status
            status = _extract_status_code(exc)
            if status is not None and cfg.is_retryable_status(status):
                last_exc = exc
                if attempt >= cfg.max_retries:
                    raise
                delay = cfg.compute_delay(attempt)
                if on_retry:
                    on_retry(attempt, exc, delay)
                else:
                    logger.warning(
                        "Retry %d/%d after %.2fs (HTTP %d): %s",
                        attempt + 1,
                        cfg.max_retries,
                        delay,
                        status,
                        exc,
                    )
                time.sleep(delay)
            else:
                raise

    if last_exc is not None:
        raise last_exc
    raise RuntimeError("Retry logic error: no result or exception")


async def with_retry_async(
    func: Callable[[], T],
    *,
    config: Optional[RetryConfig] = None,
    on_retry: Optional[Callable[[int, Exception, float], None]] = None,
) -> T:
    """
    Execute an async function with retry and exponential backoff.

    Args:
        func: Async function to execute.
        config: Retry configuration.
        on_retry: Optional callback called before each retry with
                  (attempt, exception, delay).

    Returns:
        The result of func().

    Raises:
        The last exception if all retries are exhausted.
    """
    cfg = config or RetryConfig()

    if not cfg.enabled:
        result = func()
        if asyncio.iscoroutine(result):
            return await result
        return result

    last_exc: Optional[Exception] = None

    for attempt in range(cfg.max_retries + 1):
        try:
            result = func()
            if asyncio.iscoroutine(result):
                return await result
            return result
        except RetryableError as exc:
            last_exc = exc
            if not exc.should_retry or attempt >= cfg.max_retries:
                raise
            delay = cfg.compute_delay(attempt)
            if on_retry:
                on_retry(attempt, exc, delay)
            else:
                logger.warning(
                    "Retry %d/%d after %.2fs: %s",
                    attempt + 1,
                    cfg.max_retries,
                    delay,
                    exc,
                )
            await asyncio.sleep(delay)
        except Exception as exc:
            status = _extract_status_code(exc)
            if status is not None and cfg.is_retryable_status(status):
                last_exc = exc
                if attempt >= cfg.max_retries:
                    raise
                delay = cfg.compute_delay(attempt)
                if on_retry:
                    on_retry(attempt, exc, delay)
                else:
                    logger.warning(
                        "Retry %d/%d after %.2fs (HTTP %d): %s",
                        attempt + 1,
                        cfg.max_retries,
                        delay,
                        status,
                        exc,
                    )
                await asyncio.sleep(delay)
            else:
                raise

    if last_exc is not None:
        raise last_exc
    raise RuntimeError("Retry logic error: no result or exception")


def _extract_status_code(exc: Exception) -> Optional[int]:
    """Try to extract HTTP status code from various exception types."""
    # urllib.error.HTTPError
    if hasattr(exc, "code"):
        try:
            return int(exc.code)
        except (TypeError, ValueError):
            pass

    # requests.exceptions.HTTPError (if using requests)
    if hasattr(exc, "response") and hasattr(exc.response, "status_code"):
        try:
            return int(exc.response.status_code)
        except (TypeError, ValueError):
            pass

    # aiohttp.ClientResponseError
    if hasattr(exc, "status"):
        try:
            return int(exc.status)
        except (TypeError, ValueError):
            pass

    # httpx.HTTPStatusError
    if hasattr(exc, "response") and hasattr(exc.response, "status_code"):
        try:
            return int(exc.response.status_code)
        except (TypeError, ValueError):
            pass

    return None
