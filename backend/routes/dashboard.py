from __future__ import annotations

from fastapi import APIRouter

from services.dashboard_service import dashboard_stats


router = APIRouter(prefix="/api/dashboard", tags=["dashboard"])


@router.get("/stats")
def get_stats():
    return dashboard_stats()

