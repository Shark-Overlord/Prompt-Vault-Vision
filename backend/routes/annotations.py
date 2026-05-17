from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, HTTPException, Query

from models.schemas import AnnotationRunCreate, AnnotationRunUpdate, AnnotationSuggestionPatch
from services.annotation_service import (
    accept_annotation_suggestion,
    cancel_annotation_run,
    create_annotation_run,
    delete_annotation_run,
    get_annotation_run,
    get_annotation_suggestion,
    list_annotation_queue,
    list_annotation_runs,
    list_annotation_suggestions,
    reject_annotation_suggestion,
    rerun_annotation_run,
    update_annotation_run,
    update_annotation_suggestion,
)


router = APIRouter(tags=["annotations"])


@router.get("/api/annotations/queue")
def get_annotation_queue(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=24, ge=1, le=100),
    search: Optional[str] = None,
    category: Optional[str] = None,
    scenario: Optional[str] = None,
    selection_status: Optional[str] = None,
    annotation_status: str = "unannotated",
):
    return list_annotation_queue(
        page=page,
        page_size=page_size,
        search=search,
        category=category,
        scenario=scenario,
        selection_status=selection_status,
        annotation_status=annotation_status,
    )


@router.post("/api/annotation-runs")
def post_annotation_run(payload: AnnotationRunCreate):
    try:
        return create_annotation_run(payload.model_dump())
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/api/annotation-runs")
def get_annotation_runs(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    status: Optional[str] = None,
):
    return list_annotation_runs(page=page, page_size=page_size, status=status)


@router.get("/api/annotation-runs/{run_id}")
def get_annotation_run_detail(run_id: int):
    run = get_annotation_run(run_id)
    if not run:
        raise HTTPException(status_code=404, detail="标注任务不存在")
    return run


@router.patch("/api/annotation-runs/{run_id}")
def patch_annotation_run(run_id: int, payload: AnnotationRunUpdate):
    try:
        run = update_annotation_run(run_id, payload.model_dump(exclude_unset=True))
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    if not run:
        raise HTTPException(status_code=404, detail="标注任务不存在")
    return run


@router.delete("/api/annotation-runs/{run_id}")
def delete_annotation_run_route(run_id: int):
    try:
        run = delete_annotation_run(run_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    if not run:
        raise HTTPException(status_code=404, detail="标注任务不存在")
    return {"deleted": True, "id": run_id}


@router.post("/api/annotation-runs/{run_id}/rerun")
def rerun_annotation_run_route(run_id: int):
    try:
        run = rerun_annotation_run(run_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    if not run:
        raise HTTPException(status_code=404, detail="标注任务不存在")
    return run


@router.post("/api/annotation-runs/{run_id}/pause")
def pause_annotation_run_route(run_id: int):
    run = cancel_annotation_run(run_id)
    if not run:
        raise HTTPException(status_code=404, detail="标注任务不存在")
    return run


@router.post("/api/annotation-runs/{run_id}/cancel")
def cancel_annotation_run_route(run_id: int):
    run = cancel_annotation_run(run_id)
    if not run:
        raise HTTPException(status_code=404, detail="标注任务不存在")
    return run


@router.get("/api/annotation-suggestions")
def get_annotation_suggestions(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    status: Optional[str] = None,
    search: Optional[str] = None,
    run_id: Optional[int] = None,
):
    return list_annotation_suggestions(page=page, page_size=page_size, status=status, search=search, run_id=run_id)


@router.get("/api/annotation-suggestions/{suggestion_id}")
def get_annotation_suggestion_detail(suggestion_id: int):
    suggestion = get_annotation_suggestion(suggestion_id)
    if not suggestion:
        raise HTTPException(status_code=404, detail="标注草稿不存在")
    return suggestion


@router.patch("/api/annotation-suggestions/{suggestion_id}")
def patch_annotation_suggestion(suggestion_id: int, payload: AnnotationSuggestionPatch):
    suggestion = update_annotation_suggestion(suggestion_id, payload.model_dump(exclude_unset=True))
    if not suggestion:
        raise HTTPException(status_code=404, detail="标注草稿不存在")
    return suggestion


@router.post("/api/annotation-suggestions/{suggestion_id}/accept")
def accept_annotation_suggestion_route(suggestion_id: int):
    try:
        suggestion = accept_annotation_suggestion(suggestion_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    if not suggestion:
        raise HTTPException(status_code=404, detail="标注草稿不存在")
    return suggestion


@router.post("/api/annotation-suggestions/{suggestion_id}/reject")
def reject_annotation_suggestion_route(suggestion_id: int):
    suggestion = reject_annotation_suggestion(suggestion_id)
    if not suggestion:
        raise HTTPException(status_code=404, detail="标注草稿不存在")
    return suggestion
