from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from services.candidate_service import accept_pair_candidate, get_pair_candidate, list_pair_candidates, update_pair_candidate_status


router = APIRouter(prefix="/api/pair-candidates", tags=["pair-candidates"])


class PairCandidateStatusPatch(BaseModel):
    review_status: str
    review_reason: Optional[str] = None


class PairCandidateAcceptRequest(BaseModel):
    selection_status: str = "pending_review"


@router.get("")
def list_candidates(
    page: int = 1,
    page_size: int = 24,
    search: Optional[str] = None,
    review_status: Optional[str] = None,
    match_type: Optional[str] = None,
    repo_id: Optional[int] = None,
):
    return list_pair_candidates(
        page=page,
        page_size=page_size,
        search=search,
        review_status=review_status,
        match_type=match_type,
        repo_id=repo_id,
    )


@router.get("/{candidate_id}")
def get_candidate(candidate_id: int):
    candidate = get_pair_candidate(candidate_id)
    if not candidate:
        raise HTTPException(status_code=404, detail="候选配对不存在")
    return candidate


@router.patch("/{candidate_id}")
def update_candidate(candidate_id: int, patch: PairCandidateStatusPatch):
    try:
        return update_pair_candidate_status(candidate_id, patch.review_status, patch.review_reason)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.post("/{candidate_id}/accept")
def accept_candidate(candidate_id: int, payload: PairCandidateAcceptRequest):
    try:
        return accept_pair_candidate(candidate_id, payload.selection_status)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.post("/{candidate_id}/reject")
def reject_candidate(candidate_id: int):
    try:
        return update_pair_candidate_status(candidate_id, "rejected", "人工拒绝该候选配对")
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
