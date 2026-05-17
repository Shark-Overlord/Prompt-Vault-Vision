from __future__ import annotations

from fastapi import APIRouter

from database import fetch_all
from models.schemas import GithubSearchRequest
from services.github_search_service import run_incremental_search


router = APIRouter(prefix="/api/search", tags=["search"])


@router.post("/github")
async def search_github(payload: GithubSearchRequest):
    return await run_incremental_search(
        categories=payload.categories,
        keywords=payload.keywords,
        per_keyword_limit=payload.per_keyword_limit,
        allow_anonymous=payload.allow_anonymous,
    )


@router.get("/logs")
def search_logs():
    return fetch_all("SELECT * FROM search_logs ORDER BY created_at DESC LIMIT 100")

