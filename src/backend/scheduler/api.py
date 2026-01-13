from __future__ import annotations

from typing import Any, Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from src.shared.task_status import TaskStatus

from .scheduler import Scheduler, SchedulerConflictError


class RunRequestIn(BaseModel):
    handle: str = Field(min_length=1)
    account_config: dict[str, Any] = Field(default_factory=dict)


class CancelIn(BaseModel):
    handle: str = Field(min_length=1)


class HandleStateOut(BaseModel):
    handle: str
    status: TaskStatus
    run_id: Optional[str] = None
    queued_position: Optional[int] = None


class SchedulerSnapshotOut(BaseModel):
    max_concurrent: int
    running_count: int
    queued_count: int
    running: list[dict[str, str]]
    queued: list[dict[str, str]]
    handles: list[HandleStateOut]


def create_scheduler_router(*, scheduler: Scheduler) -> APIRouter:
    router = APIRouter(prefix="/api/scheduler", tags=["scheduler"])

    @router.get("/state", response_model=SchedulerSnapshotOut)
    async def get_state() -> SchedulerSnapshotOut:
        snap = await scheduler.snapshot()
        handles = [
            HandleStateOut(
                handle=h["handle"],
                status=h["status"],
                run_id=h.get("run_id"),
                queued_position=h.get("queued_position"),
            )
            for h in snap["handles"]
        ]
        return SchedulerSnapshotOut(
            max_concurrent=snap["max_concurrent"],
            running_count=snap["running_count"],
            queued_count=snap["queued_count"],
            running=snap["running"],
            queued=snap["queued"],
            handles=handles,
        )

    @router.get("/handles/{handle}", response_model=HandleStateOut)
    async def get_handle(handle: str) -> HandleStateOut:
        state = await scheduler.get_handle_state(handle=handle)
        return HandleStateOut(
            handle=state["handle"],
            status=state["status"],
            run_id=state.get("run_id"),
            queued_position=state.get("queued_position"),
        )

    @router.post("/start", response_model=HandleStateOut)
    async def start_run(body: RunRequestIn) -> HandleStateOut:
        try:
            await scheduler.enqueue(handle=body.handle, kind="start", account_config=body.account_config)
        except SchedulerConflictError as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

        state = await scheduler.get_handle_state(handle=body.handle)
        return HandleStateOut(
            handle=state["handle"],
            status=state["status"],
            run_id=state.get("run_id"),
            queued_position=state.get("queued_position"),
        )

    @router.post("/continue", response_model=HandleStateOut)
    async def continue_run(body: RunRequestIn) -> HandleStateOut:
        try:
            await scheduler.enqueue(handle=body.handle, kind="continue", account_config=body.account_config)
        except SchedulerConflictError as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

        state = await scheduler.get_handle_state(handle=body.handle)
        return HandleStateOut(
            handle=state["handle"],
            status=state["status"],
            run_id=state.get("run_id"),
            queued_position=state.get("queued_position"),
        )

    @router.post("/cancel", response_model=HandleStateOut)
    async def cancel_run(body: CancelIn) -> HandleStateOut:
        try:
            await scheduler.cancel(handle=body.handle)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

        state = await scheduler.get_handle_state(handle=body.handle)
        return HandleStateOut(
            handle=state["handle"],
            status=state["status"],
            run_id=state.get("run_id"),
            queued_position=state.get("queued_position"),
        )

    return router

