import unittest
from datetime import datetime, timedelta, timezone

from src.shared.stats.metrics import compute_avg_speed, compute_runtime_s


class TestStatsMetrics(unittest.TestCase):
    def test_compute_runtime_s_returns_zero_without_started_at(self) -> None:
        now = datetime(2026, 1, 13, 12, 0, 0, tzinfo=timezone.utc)
        self.assertEqual(compute_runtime_s(None, None, now=now), 0.0)

    def test_compute_runtime_s_uses_started_at_and_finished_at(self) -> None:
        start = datetime(2026, 1, 13, 12, 0, 0, tzinfo=timezone.utc)
        end = start + timedelta(seconds=2.5)
        self.assertAlmostEqual(compute_runtime_s(start, end), 2.5, places=6)

    def test_compute_avg_speed_formula(self) -> None:
        runtime_s = 2.0
        self.assertEqual(compute_avg_speed(1, 2, 3, runtime_s), 3.0)

    def test_compute_avg_speed_zero_runtime(self) -> None:
        self.assertEqual(compute_avg_speed(1, 1, 1, 0.0), 0.0)


if __name__ == "__main__":
    unittest.main()

