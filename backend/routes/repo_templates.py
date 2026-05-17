from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, HTTPException

from agents.repo_template_graph import approve_template, get_template, list_templates, reject_template, update_template
from models.schemas import RepoScanTemplatePatch
from services.repo_scan_service import RepoScanError, generate_repo_template_for_repo


router = APIRouter(tags=["repo-scan-templates"])


@router.get("/api/repos/{repo_id}/scan-templates")
def get_repo_scan_templates(repo_id: int):
    return list_templates(repo_id)


@router.post("/api/repos/{repo_id}/scan-template/generate")
async def post_repo_scan_template(repo_id: int, ai_config_id: Optional[int] = None):
    try:
        return await generate_repo_template_for_repo(repo_id, ai_config_id=ai_config_id)
    except RepoScanError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.detail) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.patch("/api/repo-scan-templates/{template_id}")
def patch_repo_scan_template(template_id: int, payload: RepoScanTemplatePatch):
    try:
        template = update_template(template_id, payload.model_dump(exclude_unset=True))
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    if not template:
        raise HTTPException(status_code=404, detail="扫描模板不存在")
    return template


@router.post("/api/repo-scan-templates/{template_id}/approve")
def approve_repo_scan_template(template_id: int):
    template = approve_template(template_id)
    if not template:
        raise HTTPException(status_code=404, detail="扫描模板不存在")
    return template


@router.post("/api/repo-scan-templates/{template_id}/reject")
def reject_repo_scan_template(template_id: int):
    template = reject_template(template_id)
    if not template:
        raise HTTPException(status_code=404, detail="扫描模板不存在")
    return template


@router.get("/api/repo-scan-templates/{template_id}")
def get_repo_scan_template(template_id: int):
    template = get_template(template_id)
    if not template:
        raise HTTPException(status_code=404, detail="扫描模板不存在")
    return template
