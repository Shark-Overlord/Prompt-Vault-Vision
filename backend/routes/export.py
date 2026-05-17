from __future__ import annotations

from fastapi import APIRouter, HTTPException

from models.schemas import ExportRequest
from services.export_service import run_export


router = APIRouter(prefix="/api/export", tags=["export"])


@router.post("")
def export_data(payload: ExportRequest):
    try:
        return run_export(payload.format, payload.selection_status, payload.category)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

