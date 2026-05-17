from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query

from models.schemas import ScheduledTaskCreate, ScheduledTaskUpdate
from services.scheduler_service import (
    create_task,
    delete_task,
    get_task,
    list_task_runs,
    list_task_runs_paginated,
    list_tasks,
    list_tasks_paginated,
    run_task,
    update_task,
)


router = APIRouter(prefix="/api/scheduled-tasks", tags=["scheduled-tasks"])


@router.get("")
def get_scheduled_tasks(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    search: str | None = Query(default=None),
    status: str | None = Query(default=None),
):
    return list_tasks_paginated(page=page, page_size=page_size, search=search, status=status)


@router.get("/{task_id}")
def get_scheduled_task(task_id: int):
    task = get_task(task_id)
    if not task:
        raise HTTPException(status_code=404, detail="定时任务不存在")
    return task


@router.post("")
def post_scheduled_task(payload: ScheduledTaskCreate):
    try:
        return create_task(payload)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.patch("/{task_id}")
def patch_scheduled_task(task_id: int, payload: ScheduledTaskUpdate):
    try:
        task = update_task(task_id, payload)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    if not task:
        raise HTTPException(status_code=404, detail="定时任务不存在")
    return task


@router.delete("/{task_id}")
def delete_scheduled_task(task_id: int):
    if not delete_task(task_id):
        raise HTTPException(status_code=404, detail="定时任务不存在")
    return {"deleted": True}


@router.post("/{task_id}/run-now")
async def run_scheduled_task_now(task_id: int):
    try:
        return await run_task(task_id, trigger_type="manual")
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.get("/{task_id}/runs")
def get_scheduled_task_runs(
    task_id: int,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=50, ge=1, le=200),
    limit: int | None = Query(default=None, ge=1, le=200),
):
    if not get_task(task_id):
        raise HTTPException(status_code=404, detail="定时任务不存在")
    if limit is not None:
        return list_task_runs(task_id, limit=limit)
    return list_task_runs_paginated(task_id, page=page, page_size=page_size)
