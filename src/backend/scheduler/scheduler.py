from __future__ import annotations

import asyncio
import json
import uuid
from pathlib import Path
from typing import Any, Awaitable, Callable, Optional

from src.backend.lifecycle.models import StartMode
from src.shared.task_status import TaskStatus

from .config import SchedulerConfig
from .models import Run, utc_now


class SchedulerConflictError(RuntimeError):
    pass


RunnerFn = Callable[[Run], Awaitable[None]]


async def _default_runner(run: Run) -> None:
    """
    MVP placeholder runner.

    Later tasks will replace this with the real scrape+filter+download pipeline.
    """
    # 让队列行为在 UI 上可观察：默认跑 6 秒（可被取消）。
    for _ in range(12):
        await asyncio.sleep(0.5)


class Scheduler:
    """
    In-memory FIFO scheduler with per-handle mutual exclusion.

    - Global FIFO queue
    - MaxConcurrent gate (from SchedulerConfig)
    - One active run per handle (Queued/Running)
    """

    def __init__(
        self,
        *,
        config: SchedulerConfig,
        runs_dir: Path,
        runner: RunnerFn | None = None,
    ) -> None:
        self._config = config
        self._runs_dir = Path(runs_dir)
        self._runner: RunnerFn = runner or _default_runner

        self._lock = asyncio.Lock()
        self._queue: list[str] = []
        self._running_tasks: dict[str, asyncio.Task[None]] = {}
        self._runs: dict[str, Run] = {}
        self._active_run_by_handle: dict[str, str] = {}
        self._handle_status: dict[str, TaskStatus] = {}

    # ---------------------------------------------------------------------
    # Public API
    # ---------------------------------------------------------------------

    async def enqueue(
        self,
        *,
        handle: str,
        kind: str,
        account_config: dict[str, Any],
        start_mode: Optional[StartMode] = None,
    ) -> Run:
        if not handle or not handle.strip():
            raise ValueError("handle 不能为空")
        if kind not in ("start", "continue"):
            raise ValueError("kind 必须是 start 或 continue")

        if kind != "start":
            start_mode = None

        async with self._lock:
            if handle in self._active_run_by_handle:
                raise SchedulerConflictError(f"账号 {handle} 已有活跃任务（Queued/Running）")

            run_id = str(uuid.uuid4())
            now = utc_now()

            # FIFO: 只要队列非空，新来的任务必须排到队尾，不能“插队”直接 Running。
            should_queue = bool(self._queue) or len(self._running_tasks) >= self._config.max_concurrent
            status = TaskStatus.QUEUED if should_queue else TaskStatus.RUNNING
            run = Run(
                run_id=run_id,
                handle=handle,
                kind=kind,
                account_config=dict(account_config or {}),
                status=status,
                created_at=now,
                updated_at=now,
                start_mode=start_mode,
                error=None,
            )

            self._runs[run_id] = run
            self._active_run_by_handle[handle] = run_id
            self._handle_status[handle] = status
            self._persist_run(run)

            if status == TaskStatus.QUEUED:
                self._queue.append(run_id)
            else:
                self._start_run_locked(run_id)

            # 兜底：如果 max_concurrent 被调大且队列里有任务，尽量补齐。
            self._try_start_queued_locked()

            return run

    async def cancel(self, *, handle: str) -> TaskStatus:
        if not handle or not handle.strip():
            raise ValueError("handle 不能为空")

        async with self._lock:
            run_id = self._active_run_by_handle.get(handle)
            if not run_id:
                return self._handle_status.get(handle, TaskStatus.IDLE)

            run = self._runs.get(run_id)
            if not run:
                self._active_run_by_handle.pop(handle, None)
                self._handle_status[handle] = TaskStatus.IDLE
                return TaskStatus.IDLE

            if run.status == TaskStatus.QUEUED:
                self._queue = [rid for rid in self._queue if rid != run_id]
                self._runs.pop(run_id, None)
                self._active_run_by_handle.pop(handle, None)
                self._handle_status[handle] = TaskStatus.IDLE
                return TaskStatus.IDLE

            if run.status == TaskStatus.RUNNING:
                task = self._running_tasks.get(run_id)
                if task and not task.done():
                    task.cancel()
                # 状态将在 runner wrapper 收敛；这里先返回当前视图，避免 UI 闪烁。
                return TaskStatus.RUNNING

            # 非活跃状态（理论上不会进入）
            self._active_run_by_handle.pop(handle, None)
            self._handle_status[handle] = run.status
            return run.status

    async def get_handle_state(self, *, handle: str) -> dict[str, Any]:
        if not handle or not handle.strip():
            raise ValueError("handle 不能为空")

        async with self._lock:
            status = self._handle_status.get(handle, TaskStatus.IDLE)
            run_id = self._active_run_by_handle.get(handle)
            queued_position: Optional[int] = None
            if run_id and run_id in self._queue:
                queued_position = self._queue.index(run_id) + 1

            return {
                "handle": handle,
                "status": status,
                "run_id": run_id,
                "queued_position": queued_position,
            }

    async def snapshot(self) -> dict[str, Any]:
        async with self._lock:
            queue_handles = []
            for rid in self._queue:
                run = self._runs.get(rid)
                if not run:
                    continue
                queue_handles.append({"run_id": rid, "handle": run.handle})

            running_handles = []
            for rid in self._running_tasks.keys():
                run = self._runs.get(rid)
                if not run:
                    continue
                running_handles.append({"run_id": rid, "handle": run.handle})

            handles = []
            for handle, status in sorted(self._handle_status.items()):
                run_id = self._active_run_by_handle.get(handle)
                queued_position: Optional[int] = None
                if run_id and run_id in self._queue:
                    queued_position = self._queue.index(run_id) + 1
                handles.append(
                    {
                        "handle": handle,
                        "status": status,
                        "run_id": run_id,
                        "queued_position": queued_position,
                    }
                )

            return {
                "max_concurrent": self._config.max_concurrent,
                "running_count": len(self._running_tasks),
                "queued_count": len(self._queue),
                "running": running_handles,
                "queued": queue_handles,
                "handles": handles,
            }

    async def reschedule(self) -> None:
        """
        Called when max_concurrent changes (or as a manual kick) to fill available slots.
        """
        async with self._lock:
            self._try_start_queued_locked()

    # ---------------------------------------------------------------------
    # Internals (lock must be held where indicated)
    # ---------------------------------------------------------------------

    def _persist_run(self, run: Run) -> None:
        try:
            self._runs_dir.mkdir(parents=True, exist_ok=True)
            path = self._runs_dir / f"{run.run_id}.json"
            path.write_text(json.dumps(run.to_public_dict(), ensure_ascii=False, indent=2), encoding="utf-8")
        except Exception:
            # 持久化失败不应阻塞调度（MVP：内存状态为准）。
            return

    def _start_run_locked(self, run_id: str) -> None:
        run = self._runs.get(run_id)
        if not run:
            return

        run.status = TaskStatus.RUNNING
        run.updated_at = utc_now()
        self._handle_status[run.handle] = TaskStatus.RUNNING
        self._persist_run(run)

        task = asyncio.create_task(self._run_wrapper(run_id), name=f"xmc-run-{run.handle}-{run_id}")
        self._running_tasks[run_id] = task

    def _try_start_queued_locked(self) -> None:
        while len(self._running_tasks) < self._config.max_concurrent and self._queue:
            run_id = self._queue.pop(0)
            run = self._runs.get(run_id)
            if not run:
                continue
            if run.status != TaskStatus.QUEUED:
                continue
            self._start_run_locked(run_id)

    async def _run_wrapper(self, run_id: str) -> None:
        run = self._runs.get(run_id)
        if not run:
            return

        final_status: TaskStatus
        error: Optional[str] = None
        try:
            await self._runner(run)
            final_status = TaskStatus.DONE
        except asyncio.CancelledError:
            final_status = TaskStatus.CANCELLED
        except Exception as exc:  # noqa: BLE001 - MVP: surface as string to UI
            final_status = TaskStatus.FAILED
            error = str(exc)

        await self._finish_run(run_id, final_status=final_status, error=error)

    async def _finish_run(self, run_id: str, *, final_status: TaskStatus, error: Optional[str]) -> None:
        async with self._lock:
            run = self._runs.get(run_id)
            if not run:
                self._running_tasks.pop(run_id, None)
                return

            handle = run.handle
            run.status = final_status
            run.error = error
            run.updated_at = utc_now()
            self._persist_run(run)

            self._running_tasks.pop(run_id, None)
            if self._active_run_by_handle.get(handle) == run_id:
                self._active_run_by_handle.pop(handle, None)
            self._handle_status[handle] = final_status

            self._try_start_queued_locked()
