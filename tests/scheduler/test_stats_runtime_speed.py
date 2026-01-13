import asyncio
import tempfile
import unittest
from pathlib import Path

import sys

sys.path.insert(0, str(Path(__file__).parent.parent.parent / "src"))

from backend.scheduler.config import SchedulerConfig
from backend.scheduler.models import Run
from backend.scheduler.scheduler import Scheduler
from shared.task_status import TaskStatus


class TestSchedulerRuntimeAndSpeed(unittest.TestCase):
    def test_runtime_excludes_queued_time_and_speed_formula(self) -> None:
        async def run_test():
            with tempfile.TemporaryDirectory() as tmpdir:
                runs_dir = Path(tmpdir) / "runs"
                started: dict[str, asyncio.Event] = {}
                release: dict[str, asyncio.Event] = {}

                async def runner(run: Run) -> None:
                    handle = run.handle
                    if handle in started:
                        started[handle].set()
                    if handle in release:
                        await release[handle].wait()

                scheduler = Scheduler(
                    config=SchedulerConfig(max_concurrent=1),
                    runs_dir=runs_dir,
                    runner=runner,
                )

                started["first"] = asyncio.Event()
                started["second"] = asyncio.Event()
                release["first"] = asyncio.Event()
                release["second"] = asyncio.Event()

                await scheduler.enqueue(handle="first", kind="start", account_config={})
                await asyncio.sleep(0.01)
                second_run = await scheduler.enqueue(handle="second", kind="start", account_config={})

                await asyncio.wait_for(started["first"].wait(), timeout=1.0)

                snap = await scheduler.snapshot()
                second_state = next(h for h in snap["handles"] if h["handle"] == "second")
                self.assertEqual(second_state["status"], TaskStatus.QUEUED)
                self.assertEqual(second_state["runtime_s"], 0.0)

                # Keep "first" running so "second" accrues queued time.
                await asyncio.sleep(0.25)
                release["first"].set()

                await asyncio.wait_for(started["second"].wait(), timeout=1.0)

                # When it just turned Running, runtime should be near 0 (queued time excluded).
                snap = await scheduler.snapshot()
                second_state = next(h for h in snap["handles"] if h["handle"] == "second")
                self.assertEqual(second_state["status"], TaskStatus.RUNNING)
                self.assertLess(second_state["runtime_s"], 0.15)

                # Set deterministic counters and validate avg_speed formula.
                second_run.download_stats = {
                    "images_downloaded": 1,
                    "videos_downloaded": 2,
                    "skipped_duplicate": 3,
                    "failed": 0,
                    "total_bytes": 0,
                }
                await asyncio.sleep(0.2)
                snap = await scheduler.snapshot()
                second_state = next(h for h in snap["handles"] if h["handle"] == "second")
                runtime_s = float(second_state["runtime_s"])
                expected = (1 + 2 + 3) / runtime_s if runtime_s > 0 else 0.0
                self.assertAlmostEqual(second_state["avg_speed"], expected, places=9)

                release["second"].set()
                await asyncio.sleep(0.05)

        asyncio.run(run_test())


if __name__ == "__main__":
    unittest.main()
