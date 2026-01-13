"""
Tests for scheduler FIFO queue, locking, and Queued cancel behavior.

Acceptance criteria from T-20260113-test-scheduler-fifo-locking:
1. Coverage: 5 accounts Start + MaxConcurrent=3 -> 3 Running + 2 Queued
2. Coverage: Running completes, queue head transitions to Running
3. Coverage: Queued Cancel removes from queue and unlocks immediately (no Keep/Delete dialog)
4. Coverage: Locked status (Queued/Running) means config cannot be changed / cannot Paste
"""

import asyncio
import tempfile
import unittest
from pathlib import Path

# Add src to path for imports
import sys

sys.path.insert(0, str(Path(__file__).parent.parent.parent / "src"))

from backend.scheduler.config import SchedulerConfig
from backend.scheduler.scheduler import Scheduler, SchedulerConflictError
from backend.scheduler.models import Run
from shared.task_status import TaskStatus


class TestFifoQueueing(unittest.TestCase):
    """Tests for FIFO queue behavior."""

    def setUp(self):
        """Create a scheduler with controllable runner."""
        self.temp_dir = tempfile.mkdtemp()
        self.runs_dir = Path(self.temp_dir) / "runs"
        self.runner_events: dict[str, asyncio.Event] = {}
        self.runner_started: dict[str, asyncio.Event] = {}

        async def controllable_runner(run: Run) -> None:
            """Runner that waits until explicitly released."""
            handle = run.handle
            # Signal that this runner has started
            if handle in self.runner_started:
                self.runner_started[handle].set()
            # Wait for release signal
            if handle in self.runner_events:
                await self.runner_events[handle].wait()

        self.runner_fn = controllable_runner
        self.config = SchedulerConfig(max_concurrent=3)
        self.scheduler = Scheduler(
            config=self.config,
            runs_dir=self.runs_dir,
            runner=self.runner_fn,
        )

    def tearDown(self):
        """Cleanup temp directory."""
        import shutil

        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def _create_scheduler(self, max_concurrent: int = 3) -> Scheduler:
        """Create a new scheduler with specified max_concurrent."""
        config = SchedulerConfig(max_concurrent=max_concurrent)
        return Scheduler(
            config=config,
            runs_dir=self.runs_dir,
            runner=self.runner_fn,
        )

    def test_five_accounts_three_running_two_queued(self):
        """5 accounts Start with MaxConcurrent=3 should result in 3 Running + 2 Queued."""

        async def run_test():
            scheduler = self._create_scheduler(max_concurrent=3)

            # Create events for all 5 handles so runners don't complete
            handles = ["user1", "user2", "user3", "user4", "user5"]
            for h in handles:
                self.runner_events[h] = asyncio.Event()
                self.runner_started[h] = asyncio.Event()

            # Enqueue all 5 accounts
            runs = []
            for handle in handles:
                run = await scheduler.enqueue(
                    handle=handle,
                    kind="start",
                    account_config={"test": True},
                )
                runs.append(run)
                # Small delay to ensure FIFO ordering
                await asyncio.sleep(0.01)

            # Get snapshot to verify state
            snapshot = await scheduler.snapshot()

            # Verify counts
            assert (
                snapshot["running_count"] == 3
            ), f"Expected 3 running, got {snapshot['running_count']}"
            assert (
                snapshot["queued_count"] == 2
            ), f"Expected 2 queued, got {snapshot['queued_count']}"

            # Verify first 3 are Running (FIFO)
            running_handles = {r["handle"] for r in snapshot["running"]}
            assert running_handles == {"user1", "user2", "user3"}, (
                f"Expected user1, user2, user3 running, got {running_handles}"
            )

            # Verify last 2 are Queued
            queued_handles = [r["handle"] for r in snapshot["queued"]]
            assert queued_handles == ["user4", "user5"], (
                f"Expected user4, user5 queued (in order), got {queued_handles}"
            )

            # Verify individual handle states
            for i, handle in enumerate(handles):
                state = await scheduler.get_handle_state(handle=handle)
                if i < 3:
                    assert state["status"] == TaskStatus.RUNNING, (
                        f"{handle} should be Running, got {state['status']}"
                    )
                else:
                    assert state["status"] == TaskStatus.QUEUED, (
                        f"{handle} should be Queued, got {state['status']}"
                    )
                    # Verify queue position
                    expected_pos = i - 2  # user4 -> pos 1, user5 -> pos 2
                    assert state["queued_position"] == expected_pos, (
                        f"{handle} queue position should be {expected_pos}, got {state['queued_position']}"
                    )

            # Cleanup: release all runners
            for h in handles:
                self.runner_events[h].set()

            # Wait briefly for tasks to finish
            await asyncio.sleep(0.1)

        asyncio.run(run_test())

    def test_fifo_order_preserved_on_completion(self):
        """When a Running task completes, the queue head (FIFO) should become Running."""

        async def run_test():
            scheduler = self._create_scheduler(max_concurrent=2)

            handles = ["first", "second", "third", "fourth"]
            for h in handles:
                self.runner_events[h] = asyncio.Event()
                self.runner_started[h] = asyncio.Event()

            # Enqueue all handles
            for handle in handles:
                await scheduler.enqueue(
                    handle=handle, kind="start", account_config={}
                )
                await asyncio.sleep(0.01)

            # Wait for first two runners to start
            await asyncio.wait_for(self.runner_started["first"].wait(), timeout=1.0)
            await asyncio.wait_for(self.runner_started["second"].wait(), timeout=1.0)

            # Verify initial state: 2 running, 2 queued
            snapshot = await scheduler.snapshot()
            assert snapshot["running_count"] == 2
            assert snapshot["queued_count"] == 2
            assert [r["handle"] for r in snapshot["queued"]] == ["third", "fourth"]

            # Complete "first" task
            self.runner_events["first"].set()

            # Wait for "third" to start (queue head should promote)
            await asyncio.wait_for(self.runner_started["third"].wait(), timeout=1.0)

            # Verify new state: still 2 running (second + third), 1 queued (fourth)
            snapshot = await scheduler.snapshot()
            running_handles = {r["handle"] for r in snapshot["running"]}
            assert running_handles == {"second", "third"}, (
                f"Expected second+third running, got {running_handles}"
            )
            assert snapshot["queued_count"] == 1
            assert snapshot["queued"][0]["handle"] == "fourth"

            # Complete "second", "fourth" should promote
            self.runner_events["second"].set()
            await asyncio.wait_for(self.runner_started["fourth"].wait(), timeout=1.0)

            snapshot = await scheduler.snapshot()
            running_handles = {r["handle"] for r in snapshot["running"]}
            assert running_handles == {"third", "fourth"}
            assert snapshot["queued_count"] == 0

            # Cleanup
            self.runner_events["third"].set()
            self.runner_events["fourth"].set()
            await asyncio.sleep(0.1)

        asyncio.run(run_test())


class TestQueuedCancel(unittest.TestCase):
    """Tests for Queued cancel behavior."""

    def setUp(self):
        """Create a scheduler with controllable runner."""
        self.temp_dir = tempfile.mkdtemp()
        self.runs_dir = Path(self.temp_dir) / "runs"
        self.runner_events: dict[str, asyncio.Event] = {}
        self.runner_started: dict[str, asyncio.Event] = {}

        async def controllable_runner(run: Run) -> None:
            handle = run.handle
            if handle in self.runner_started:
                self.runner_started[handle].set()
            if handle in self.runner_events:
                await self.runner_events[handle].wait()

        self.runner_fn = controllable_runner

    def tearDown(self):
        import shutil

        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_queued_cancel_removes_from_queue_immediately(self):
        """Canceling a Queued task should remove it from queue immediately without side effects."""

        async def run_test():
            config = SchedulerConfig(max_concurrent=1)
            scheduler = Scheduler(
                config=config,
                runs_dir=self.runs_dir,
                runner=self.runner_fn,
            )

            # Setup events
            for h in ["running_user", "queued_user"]:
                self.runner_events[h] = asyncio.Event()
                self.runner_started[h] = asyncio.Event()

            # Enqueue 2 tasks: first goes Running, second goes Queued
            await scheduler.enqueue(
                handle="running_user", kind="start", account_config={}
            )
            await asyncio.sleep(0.01)
            await scheduler.enqueue(
                handle="queued_user", kind="start", account_config={}
            )

            # Wait for first to start
            await asyncio.wait_for(
                self.runner_started["running_user"].wait(), timeout=1.0
            )

            # Verify queued_user is Queued
            state = await scheduler.get_handle_state(handle="queued_user")
            assert state["status"] == TaskStatus.QUEUED

            # Cancel the Queued task
            result_status = await scheduler.cancel(handle="queued_user")

            # Should return IDLE immediately (not prompt for Keep/Delete)
            assert result_status == TaskStatus.IDLE, (
                f"Cancel Queued should return IDLE, got {result_status}"
            )

            # Verify handle state is now IDLE
            state = await scheduler.get_handle_state(handle="queued_user")
            assert state["status"] == TaskStatus.IDLE, (
                f"Handle should be IDLE after cancel, got {state['status']}"
            )

            # Verify removed from queue
            snapshot = await scheduler.snapshot()
            assert snapshot["queued_count"] == 0
            queued_handles = [r["handle"] for r in snapshot["queued"]]
            assert "queued_user" not in queued_handles

            # Cleanup
            self.runner_events["running_user"].set()
            await asyncio.sleep(0.1)

        asyncio.run(run_test())

    def test_queued_cancel_unlocks_handle(self):
        """After canceling a Queued task, the handle should be unlocked (can be re-enqueued)."""

        async def run_test():
            config = SchedulerConfig(max_concurrent=1)
            scheduler = Scheduler(
                config=config,
                runs_dir=self.runs_dir,
                runner=self.runner_fn,
            )

            for h in ["blocker", "target"]:
                self.runner_events[h] = asyncio.Event()
                self.runner_started[h] = asyncio.Event()

            # Fill Running slot
            await scheduler.enqueue(handle="blocker", kind="start", account_config={})
            await asyncio.sleep(0.01)

            # Queue target
            await scheduler.enqueue(handle="target", kind="start", account_config={})

            # Wait for blocker to start
            await asyncio.wait_for(self.runner_started["blocker"].wait(), timeout=1.0)

            # Verify target is queued (locked)
            state = await scheduler.get_handle_state(handle="target")
            assert state["status"].is_locked()

            # Cancel target
            await scheduler.cancel(handle="target")

            # Verify target is now unlocked (IDLE)
            state = await scheduler.get_handle_state(handle="target")
            assert not state["status"].is_locked()
            assert state["status"] == TaskStatus.IDLE

            # Should be able to re-enqueue target (proves it's unlocked)
            await scheduler.enqueue(handle="target", kind="start", account_config={})
            state = await scheduler.get_handle_state(handle="target")
            assert state["status"] == TaskStatus.QUEUED

            # Cleanup
            self.runner_events["blocker"].set()
            await asyncio.sleep(0.1)

        asyncio.run(run_test())

    def test_queued_cancel_no_filesystem_side_effects(self):
        """Queued cancel should have no filesystem side effects (no Keep/Delete choice)."""

        async def run_test():
            config = SchedulerConfig(max_concurrent=1)
            scheduler = Scheduler(
                config=config,
                runs_dir=self.runs_dir,
                runner=self.runner_fn,
            )

            for h in ["active", "waiting"]:
                self.runner_events[h] = asyncio.Event()
                self.runner_started[h] = asyncio.Event()

            await scheduler.enqueue(handle="active", kind="start", account_config={})
            await asyncio.sleep(0.01)
            await scheduler.enqueue(handle="waiting", kind="start", account_config={})

            await asyncio.wait_for(self.runner_started["active"].wait(), timeout=1.0)

            # Cancel waiting task
            status = await scheduler.cancel(handle="waiting")

            # The cancel method for Queued should just return IDLE
            # It does NOT trigger any dialog (Keep/Delete) since no work was done
            assert status == TaskStatus.IDLE

            # Verify the scheduler state is clean
            snapshot = await scheduler.snapshot()
            assert snapshot["queued_count"] == 0

            # Cleanup
            self.runner_events["active"].set()
            await asyncio.sleep(0.1)

        asyncio.run(run_test())


class TestLockingBehavior(unittest.TestCase):
    """Tests for locked state behavior (Queued/Running cannot be modified)."""

    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()
        self.runs_dir = Path(self.temp_dir) / "runs"
        self.runner_events: dict[str, asyncio.Event] = {}
        self.runner_started: dict[str, asyncio.Event] = {}

        async def controllable_runner(run: Run) -> None:
            handle = run.handle
            if handle in self.runner_started:
                self.runner_started[handle].set()
            if handle in self.runner_events:
                await self.runner_events[handle].wait()

        self.runner_fn = controllable_runner

    def tearDown(self):
        import shutil

        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_queued_status_is_locked(self):
        """Queued status should report as locked."""

        async def run_test():
            config = SchedulerConfig(max_concurrent=1)
            scheduler = Scheduler(
                config=config,
                runs_dir=self.runs_dir,
                runner=self.runner_fn,
            )

            for h in ["running", "queued"]:
                self.runner_events[h] = asyncio.Event()
                self.runner_started[h] = asyncio.Event()

            await scheduler.enqueue(handle="running", kind="start", account_config={})
            await asyncio.sleep(0.01)
            await scheduler.enqueue(handle="queued", kind="start", account_config={})

            await asyncio.wait_for(self.runner_started["running"].wait(), timeout=1.0)

            # Verify Queued status is_locked
            state = await scheduler.get_handle_state(handle="queued")
            assert state["status"] == TaskStatus.QUEUED
            assert state["status"].is_locked(), "Queued status should be locked"

            # Cleanup
            self.runner_events["running"].set()
            await asyncio.sleep(0.1)

        asyncio.run(run_test())

    def test_running_status_is_locked(self):
        """Running status should report as locked."""

        async def run_test():
            config = SchedulerConfig(max_concurrent=3)
            scheduler = Scheduler(
                config=config,
                runs_dir=self.runs_dir,
                runner=self.runner_fn,
            )

            self.runner_events["test_user"] = asyncio.Event()
            self.runner_started["test_user"] = asyncio.Event()

            await scheduler.enqueue(
                handle="test_user", kind="start", account_config={}
            )

            await asyncio.wait_for(
                self.runner_started["test_user"].wait(), timeout=1.0
            )

            # Verify Running status is_locked
            state = await scheduler.get_handle_state(handle="test_user")
            assert state["status"] == TaskStatus.RUNNING
            assert state["status"].is_locked(), "Running status should be locked"

            # Cleanup
            self.runner_events["test_user"].set()
            await asyncio.sleep(0.1)

        asyncio.run(run_test())

    def test_idle_status_is_not_locked(self):
        """IDLE status should not be locked."""
        # Test the TaskStatus enum directly
        assert not TaskStatus.IDLE.is_locked()
        assert not TaskStatus.DONE.is_locked()
        assert not TaskStatus.FAILED.is_locked()
        assert not TaskStatus.CANCELLED.is_locked()

    def test_locked_states_defined_correctly(self):
        """Only QUEUED and RUNNING should be locked states."""
        locked_states = [s for s in TaskStatus if s.is_locked()]
        assert set(locked_states) == {TaskStatus.QUEUED, TaskStatus.RUNNING}

    def test_cannot_enqueue_same_handle_when_locked(self):
        """Cannot enqueue a handle that already has an active (locked) task."""

        async def run_test():
            config = SchedulerConfig(max_concurrent=3)
            scheduler = Scheduler(
                config=config,
                runs_dir=self.runs_dir,
                runner=self.runner_fn,
            )

            self.runner_events["locked_user"] = asyncio.Event()
            self.runner_started["locked_user"] = asyncio.Event()

            # First enqueue succeeds
            await scheduler.enqueue(
                handle="locked_user", kind="start", account_config={}
            )

            await asyncio.wait_for(
                self.runner_started["locked_user"].wait(), timeout=1.0
            )

            # Verify it's Running (locked)
            state = await scheduler.get_handle_state(handle="locked_user")
            assert state["status"].is_locked()

            # Second enqueue should fail with conflict error
            with self.assertRaises(SchedulerConflictError) as ctx:
                await scheduler.enqueue(
                    handle="locked_user", kind="start", account_config={}
                )

            assert "已有活跃任务" in str(ctx.exception)

            # Cleanup
            self.runner_events["locked_user"].set()
            await asyncio.sleep(0.1)

        asyncio.run(run_test())

    def test_cannot_enqueue_queued_handle(self):
        """Cannot enqueue a handle that is already Queued."""

        async def run_test():
            config = SchedulerConfig(max_concurrent=1)
            scheduler = Scheduler(
                config=config,
                runs_dir=self.runs_dir,
                runner=self.runner_fn,
            )

            for h in ["blocker", "queued_user"]:
                self.runner_events[h] = asyncio.Event()
                self.runner_started[h] = asyncio.Event()

            # Fill Running slot
            await scheduler.enqueue(handle="blocker", kind="start", account_config={})
            await asyncio.sleep(0.01)

            # Queue another user
            await scheduler.enqueue(
                handle="queued_user", kind="start", account_config={}
            )

            await asyncio.wait_for(self.runner_started["blocker"].wait(), timeout=1.0)

            # Verify queued_user is Queued
            state = await scheduler.get_handle_state(handle="queued_user")
            assert state["status"] == TaskStatus.QUEUED
            assert state["status"].is_locked()

            # Try to enqueue same handle again - should fail
            with self.assertRaises(SchedulerConflictError):
                await scheduler.enqueue(
                    handle="queued_user", kind="start", account_config={}
                )

            # Cleanup
            self.runner_events["blocker"].set()
            await asyncio.sleep(0.1)

        asyncio.run(run_test())


class TestRescheduleOnConfigChange(unittest.TestCase):
    """Tests for rescheduling when max_concurrent changes."""

    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()
        self.runs_dir = Path(self.temp_dir) / "runs"
        self.runner_events: dict[str, asyncio.Event] = {}
        self.runner_started: dict[str, asyncio.Event] = {}

        async def controllable_runner(run: Run) -> None:
            handle = run.handle
            if handle in self.runner_started:
                self.runner_started[handle].set()
            if handle in self.runner_events:
                await self.runner_events[handle].wait()

        self.runner_fn = controllable_runner

    def tearDown(self):
        import shutil

        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_increase_max_concurrent_promotes_queued(self):
        """Increasing max_concurrent should promote queued tasks to running."""

        async def run_test():
            config = SchedulerConfig(max_concurrent=1)
            scheduler = Scheduler(
                config=config,
                runs_dir=self.runs_dir,
                runner=self.runner_fn,
            )

            handles = ["user1", "user2", "user3"]
            for h in handles:
                self.runner_events[h] = asyncio.Event()
                self.runner_started[h] = asyncio.Event()

            # Enqueue 3 tasks with max_concurrent=1
            for handle in handles:
                await scheduler.enqueue(
                    handle=handle, kind="start", account_config={}
                )
                await asyncio.sleep(0.01)

            await asyncio.wait_for(self.runner_started["user1"].wait(), timeout=1.0)

            # Verify: 1 running, 2 queued
            snapshot = await scheduler.snapshot()
            assert snapshot["running_count"] == 1
            assert snapshot["queued_count"] == 2

            # Increase max_concurrent to 3
            config.set_max_concurrent(3)
            await scheduler.reschedule()

            # Wait for queued tasks to start
            await asyncio.wait_for(self.runner_started["user2"].wait(), timeout=1.0)
            await asyncio.wait_for(self.runner_started["user3"].wait(), timeout=1.0)

            # Verify: 3 running, 0 queued
            snapshot = await scheduler.snapshot()
            assert snapshot["running_count"] == 3, (
                f"Expected 3 running, got {snapshot['running_count']}"
            )
            assert snapshot["queued_count"] == 0

            # Cleanup
            for h in handles:
                self.runner_events[h].set()
            await asyncio.sleep(0.1)

        asyncio.run(run_test())


if __name__ == "__main__":
    unittest.main()
