"""
Tests for src/backend/net/retry.py

Covers:
- Exponential backoff retry logic
- Retryable HTTP status codes (429, 5xx)
- Custom RetryableError handling
- Max retries limit
"""

import asyncio
import unittest
from unittest.mock import Mock
from urllib.error import HTTPError

from src.backend.net.retry import (
    RetryConfig,
    RetryableError,
    with_retry,
    with_retry_async,
    _extract_status_code,
)


class TestRetryConfig(unittest.TestCase):
    """Tests for RetryConfig."""

    def test_default_values(self):
        """Default config uses conservative values."""
        config = RetryConfig()
        self.assertEqual(config.max_retries, 3)
        self.assertEqual(config.base_delay_s, 2.0)
        self.assertEqual(config.max_delay_s, 60.0)
        self.assertEqual(config.jitter_factor, 0.25)
        self.assertIn(429, config.retryable_status_codes)
        self.assertIn(500, config.retryable_status_codes)
        self.assertIn(502, config.retryable_status_codes)
        self.assertIn(503, config.retryable_status_codes)
        self.assertIn(504, config.retryable_status_codes)
        self.assertTrue(config.enabled)

    def test_compute_delay_exponential(self):
        """Delay should increase exponentially."""
        config = RetryConfig(base_delay_s=1.0, max_delay_s=100.0, jitter_factor=0.0)

        delay0 = config.compute_delay(0)  # 1 * 2^0 = 1
        delay1 = config.compute_delay(1)  # 1 * 2^1 = 2
        delay2 = config.compute_delay(2)  # 1 * 2^2 = 4

        self.assertEqual(delay0, 1.0)
        self.assertEqual(delay1, 2.0)
        self.assertEqual(delay2, 4.0)

    def test_compute_delay_capped_at_max(self):
        """Delay should be capped at max_delay_s."""
        config = RetryConfig(base_delay_s=10.0, max_delay_s=15.0, jitter_factor=0.0)

        delay0 = config.compute_delay(0)  # 10 * 2^0 = 10
        delay1 = config.compute_delay(1)  # 10 * 2^1 = 20 -> capped to 15
        delay2 = config.compute_delay(2)  # 10 * 2^2 = 40 -> capped to 15

        self.assertEqual(delay0, 10.0)
        self.assertEqual(delay1, 15.0)
        self.assertEqual(delay2, 15.0)

    def test_is_retryable_status(self):
        """Check retryable status codes."""
        config = RetryConfig()

        self.assertTrue(config.is_retryable_status(429))
        self.assertTrue(config.is_retryable_status(500))
        self.assertTrue(config.is_retryable_status(502))
        self.assertTrue(config.is_retryable_status(503))
        self.assertTrue(config.is_retryable_status(504))

        self.assertFalse(config.is_retryable_status(200))
        self.assertFalse(config.is_retryable_status(400))
        self.assertFalse(config.is_retryable_status(401))
        self.assertFalse(config.is_retryable_status(403))
        self.assertFalse(config.is_retryable_status(404))

    def test_to_persist_dict(self):
        """Config can be serialized."""
        config = RetryConfig(max_retries=5, base_delay_s=1.0)
        data = config.to_persist_dict()

        self.assertEqual(data["max_retries"], 5)
        self.assertEqual(data["base_delay_s"], 1.0)
        self.assertIsInstance(data["retryable_status_codes"], list)

    def test_from_persist_dict(self):
        """Config can be deserialized."""
        data = {
            "max_retries": 2,
            "base_delay_s": 0.5,
            "max_delay_s": 30.0,
            "retryable_status_codes": [429, 500],
        }
        config = RetryConfig.from_persist_dict(data)

        self.assertEqual(config.max_retries, 2)
        self.assertEqual(config.base_delay_s, 0.5)
        self.assertEqual(config.max_delay_s, 30.0)
        self.assertEqual(config.retryable_status_codes, {429, 500})


class TestRetryableError(unittest.TestCase):
    """Tests for RetryableError."""

    def test_retryable_error_with_status(self):
        """RetryableError can carry status code."""
        exc = RetryableError("rate limited", status_code=429)
        self.assertEqual(exc.status_code, 429)
        self.assertTrue(exc.should_retry)

    def test_retryable_error_no_retry(self):
        """RetryableError can be marked as non-retryable."""
        exc = RetryableError("fatal error", should_retry=False)
        self.assertFalse(exc.should_retry)


class TestWithRetry(unittest.TestCase):
    """Tests for with_retry function."""

    def test_success_no_retry(self):
        """Successful function should not retry."""
        call_count = 0

        def success_func():
            nonlocal call_count
            call_count += 1
            return "result"

        result = with_retry(success_func, config=RetryConfig(max_retries=3))

        self.assertEqual(result, "result")
        self.assertEqual(call_count, 1)

    def test_retry_on_retryable_error(self):
        """Should retry on RetryableError."""
        call_count = 0

        def failing_then_success():
            nonlocal call_count
            call_count += 1
            if call_count < 3:
                raise RetryableError("temporary error")
            return "success"

        config = RetryConfig(max_retries=5, base_delay_s=0.01, jitter_factor=0.0)
        result = with_retry(failing_then_success, config=config)

        self.assertEqual(result, "success")
        self.assertEqual(call_count, 3)

    def test_retry_exhausted(self):
        """Should raise after max retries exhausted."""
        call_count = 0

        def always_fail():
            nonlocal call_count
            call_count += 1
            raise RetryableError("persistent error")

        config = RetryConfig(max_retries=2, base_delay_s=0.01, jitter_factor=0.0)

        with self.assertRaises(RetryableError):
            with_retry(always_fail, config=config)

        self.assertEqual(call_count, 3)  # 1 initial + 2 retries

    def test_non_retryable_error_not_retried(self):
        """Non-retryable errors should not trigger retry."""
        call_count = 0

        def non_retryable():
            nonlocal call_count
            call_count += 1
            raise ValueError("non-retryable")

        config = RetryConfig(max_retries=5, base_delay_s=0.01)

        with self.assertRaises(ValueError):
            with_retry(non_retryable, config=config)

        self.assertEqual(call_count, 1)

    def test_disabled_retry(self):
        """Disabled retry should not retry."""
        call_count = 0

        def failing():
            nonlocal call_count
            call_count += 1
            raise RetryableError("error")

        config = RetryConfig(max_retries=5, enabled=False)

        with self.assertRaises(RetryableError):
            with_retry(failing, config=config)

        self.assertEqual(call_count, 1)

    def test_on_retry_callback(self):
        """on_retry callback should be called before each retry."""
        retry_calls = []

        def failing_twice():
            if len(retry_calls) < 2:
                raise RetryableError("error")
            return "done"

        def on_retry(attempt, exc, delay):
            retry_calls.append((attempt, str(exc), delay))

        config = RetryConfig(max_retries=3, base_delay_s=0.01, jitter_factor=0.0)
        result = with_retry(failing_twice, config=config, on_retry=on_retry)

        self.assertEqual(result, "done")
        self.assertEqual(len(retry_calls), 2)
        self.assertEqual(retry_calls[0][0], 0)  # First retry attempt
        self.assertEqual(retry_calls[1][0], 1)  # Second retry attempt


class TestExtractStatusCode(unittest.TestCase):
    """Tests for _extract_status_code helper."""

    def test_extract_from_http_error(self):
        """Extract status from HTTPError.code."""
        exc = HTTPError("url", 429, "rate limited", {}, None)
        self.assertEqual(_extract_status_code(exc), 429)

    def test_extract_returns_none_for_regular_exception(self):
        """Regular exceptions should return None."""
        exc = ValueError("error")
        self.assertIsNone(_extract_status_code(exc))


class TestWithRetryAsync(unittest.TestCase):
    """Tests for with_retry_async function."""

    def test_async_retry(self):
        """Async retry should work like sync retry."""

        async def run_test():
            call_count = 0

            async def failing_then_success():
                nonlocal call_count
                call_count += 1
                if call_count < 2:
                    raise RetryableError("temporary")
                return "done"

            config = RetryConfig(max_retries=3, base_delay_s=0.01, jitter_factor=0.0)
            result = await with_retry_async(failing_then_success, config=config)

            return result, call_count

        result, call_count = asyncio.run(run_test())
        self.assertEqual(result, "done")
        self.assertEqual(call_count, 2)


if __name__ == "__main__":
    unittest.main()
