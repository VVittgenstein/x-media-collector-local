"""
Tests for src/backend/net/throttle.py

Covers:
- Throttle with configurable min_interval and jitter
- Sync and async wait methods
- Disabled throttle behavior
"""

import time
import asyncio
import unittest

from src.backend.net.throttle import Throttle, ThrottleConfig


class TestThrottleConfig(unittest.TestCase):
    """Tests for ThrottleConfig."""

    def test_default_values(self):
        """Default config uses conservative values."""
        config = ThrottleConfig()
        self.assertEqual(config.min_interval_s, 1.5)
        self.assertEqual(config.jitter_max_s, 1.0)
        self.assertTrue(config.enabled)

    def test_to_persist_dict(self):
        """Config can be serialized to dict."""
        config = ThrottleConfig(min_interval_s=2.0, jitter_max_s=0.5, enabled=False)
        data = config.to_persist_dict()
        self.assertEqual(data["min_interval_s"], 2.0)
        self.assertEqual(data["jitter_max_s"], 0.5)
        self.assertFalse(data["enabled"])

    def test_from_persist_dict(self):
        """Config can be deserialized from dict."""
        data = {"min_interval_s": 3.0, "jitter_max_s": 0.8, "enabled": True}
        config = ThrottleConfig.from_persist_dict(data)
        self.assertEqual(config.min_interval_s, 3.0)
        self.assertEqual(config.jitter_max_s, 0.8)
        self.assertTrue(config.enabled)

    def test_from_persist_dict_with_invalid_values(self):
        """Invalid values fall back to defaults."""
        data = {"min_interval_s": "invalid", "jitter_max_s": None}
        config = ThrottleConfig.from_persist_dict(data)
        self.assertEqual(config.min_interval_s, 1.5)
        self.assertEqual(config.jitter_max_s, 1.0)

    def test_from_persist_dict_negative_clipped_to_zero(self):
        """Negative values are clipped to 0."""
        data = {"min_interval_s": -5.0, "jitter_max_s": -1.0}
        config = ThrottleConfig.from_persist_dict(data)
        self.assertEqual(config.min_interval_s, 0.0)
        self.assertEqual(config.jitter_max_s, 0.0)


class TestThrottle(unittest.TestCase):
    """Tests for Throttle class."""

    def test_first_request_only_jitter(self):
        """First request should only add jitter, not min_interval."""
        config = ThrottleConfig(min_interval_s=10.0, jitter_max_s=0.1, enabled=True)
        throttle = Throttle(config)

        start = time.monotonic()
        throttle.wait()
        elapsed = time.monotonic() - start

        # Should be at most jitter (0.1s), not min_interval (10s)
        self.assertLess(elapsed, 1.0)

    def test_subsequent_request_respects_min_interval(self):
        """Second request should wait for min_interval."""
        config = ThrottleConfig(min_interval_s=0.1, jitter_max_s=0.0, enabled=True)
        throttle = Throttle(config)

        # First request
        throttle.wait()

        # Second request should wait
        start = time.monotonic()
        throttle.wait()
        elapsed = time.monotonic() - start

        # Should wait at least min_interval
        self.assertGreaterEqual(elapsed, 0.09)  # Allow small tolerance

    def test_disabled_throttle_no_wait(self):
        """Disabled throttle should not wait."""
        config = ThrottleConfig(min_interval_s=10.0, jitter_max_s=5.0, enabled=False)
        throttle = Throttle(config)

        # First request
        start = time.monotonic()
        throttle.wait()
        elapsed1 = time.monotonic() - start

        # Second request immediately
        start = time.monotonic()
        throttle.wait()
        elapsed2 = time.monotonic() - start

        self.assertLess(elapsed1, 0.01)
        self.assertLess(elapsed2, 0.01)

    def test_reset(self):
        """Reset should clear last request time."""
        config = ThrottleConfig(min_interval_s=10.0, jitter_max_s=0.0, enabled=True)
        throttle = Throttle(config)

        # First request
        throttle.wait()

        # Reset
        throttle.reset()

        # Should not wait 10s for min_interval after reset
        start = time.monotonic()
        throttle.wait()
        elapsed = time.monotonic() - start

        self.assertLess(elapsed, 1.0)


class TestThrottleAsync(unittest.TestCase):
    """Tests for async throttle methods."""

    def test_wait_async(self):
        """Async wait should work similarly to sync wait."""

        async def run_test():
            config = ThrottleConfig(min_interval_s=0.1, jitter_max_s=0.0, enabled=True)
            throttle = Throttle(config)

            # First request
            await throttle.wait_async()

            # Second request should wait
            start = time.monotonic()
            await throttle.wait_async()
            elapsed = time.monotonic() - start

            return elapsed

        elapsed = asyncio.run(run_test())
        self.assertGreaterEqual(elapsed, 0.09)


if __name__ == "__main__":
    unittest.main()
