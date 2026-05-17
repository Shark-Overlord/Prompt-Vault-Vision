from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, HTTPException

from models.schemas import RepoBatchRequest
from services.repo_scan_job_service import batch_delete_repo_scan_runs, cancel_repo_scan_run, get_repo_scan_run, list_all_repo_scan_runs


router = APIRouter(prefix="/api/repo-scan-runs", tags=["repo-scan-runs"])


@router.get("")
def list_scan_runs(
    page: int = 1,
    page_size: int = 30,
    status: Optional[str] = None,
    search: Optional[str] = None,
):
    return list_all_repo_scan_runs(page=page, page_size=page_size, status=status, search=search)


@router.post("/batch-delete")
def batch_delete_scan_runs(payload: RepoBatchRequest):
    if not payload.ids:
        raise HTTPException(status_code=400, detail="请选择要删除的扫描任务")
    return batch_delete_repo_scan_runs(payload.ids)


@router.get("/{run_id}")
def get_scan_run(run_id: int):
    run = get_repo_scan_run(run_id)
    if not run:
        raise HTTPException(status_code=404, detail="扫描任务不存在")
    return run


@router.post("/{run_id}/cancel")
def cancel_scan_run(run_id: int):
    run = cancel_repo_scan_run(run_id)
    if not run:
        raise HTTPException(status_code=404, detail="扫描任务不存在")
    return run
