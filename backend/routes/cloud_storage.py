from __future__ import annotations

from typing import List, Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from services.cloud_storage_service import (
    cancel_upload_run,
    create_upload_run,
    get_cloud_storage_status,
    get_upload_run,
    list_upload_runs,
)


router = APIRouter(prefix="/api/cloud-storage", tags=["cloud-storage"])


class CloudUploadRequest(BaseModel):
    asset_ids: Optional[List[int]] = None
    only_missing: bool = True
    include_thumbnails: bool = True
    asset_type: Optional[str] = None
    limit: Optional[int] = Field(default=None, ge=1, le=10000)


@router.get("/status")
def cloud_storage_status():
    return get_cloud_storage_status()


@router.post("/upload-assets")
def upload_assets(payload: CloudUploadRequest):
    try:
        return create_upload_run(payload.model_dump(exclude_none=True))
    except RuntimeError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.get("/upload-runs")
def upload_runs(page: int = 1, page_size: int = 20, status: Optional[str] = None):
    return list_upload_runs(page=page, page_size=page_size, status=status)


@router.get("/upload-runs/{run_id}")
def upload_run(run_id: int):
    run = get_upload_run(run_id)
    if not run:
        raise HTTPException(status_code=404, detail="上传任务不存在")
    return run


@router.post("/upload-runs/{run_id}/cancel")
def cancel_run(run_id: int):
    try:
        return cancel_upload_run(run_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
