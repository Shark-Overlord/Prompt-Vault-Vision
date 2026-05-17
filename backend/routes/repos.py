from __future__ import annotations

import sqlite3
from typing import Optional
from urllib.parse import urlparse

from fastapi import APIRouter, Body, HTTPException, Query

from database import fetch_one, get_connection, paginate, utc_now
from models.schemas import RepoBatchRequest, RepoCreate, RepoScanRequest, RepoUpdate
from services.dedup_service import normalize_github_url
from services.repo_scan_job_service import create_repo_scan_run, list_repo_scan_runs
from services.repo_scan_service import RepoScanError


router = APIRouter(prefix="/api/repos", tags=["repos"])


def _parse_github_owner_repo(url: str) -> tuple[Optional[str], Optional[str]]:
    normalized = normalize_github_url(url) or url
    parts = urlparse(normalized).path.strip("/").split("/")
    if len(parts) >= 2:
        return parts[0], parts[1]
    return None, None


def _repo_payload(payload: RepoCreate | RepoUpdate, existing: Optional[dict] = None) -> dict:
    data = existing.copy() if existing else {}
    incoming = payload.model_dump(exclude_unset=True)
    data.update({key: value for key, value in incoming.items() if value is not None})

    repo_url = (data.get("repo_url") or "").strip()
    canonical_url = normalize_github_url(data.get("canonical_url") or repo_url)
    if not canonical_url:
        raise HTTPException(status_code=400, detail="repo_url 必须是有效的 GitHub 仓库地址")

    owner, repo_name = _parse_github_owner_repo(canonical_url)
    data["repo_url"] = repo_url or canonical_url
    data["canonical_url"] = canonical_url
    data["owner"] = (data.get("owner") or owner or "").strip()
    data["repo_name"] = (data.get("repo_name") or repo_name or "").strip()
    if not data["owner"] or not data["repo_name"]:
        raise HTTPException(status_code=400, detail="无法从仓库地址解析 owner/repo")

    data.setdefault("stars", 0)
    data.setdefault("forks", 0)
    data.setdefault("license", "unknown")
    data.setdefault("is_fork", 0)
    data.setdefault("parent_repo", None)
    data.setdefault("resource_type", "github_repo")
    data.setdefault("category", "image_generation_prompt")
    data.setdefault("quality_level", "pending_review")
    data.setdefault("status", "pending_review")
    data.setdefault("summary", "")
    data.setdefault("notes", "")
    return data


def _unique_positive_ids(ids: list[int]) -> list[int]:
    seen: set[int] = set()
    result: list[int] = []
    for repo_id in ids:
        try:
            value = int(repo_id)
        except (TypeError, ValueError):
            continue
        if value <= 0 or value in seen:
            continue
        seen.add(value)
        result.append(value)
    return result


def _delete_repo_records(conn: sqlite3.Connection, repo_id: int) -> None:
    pair_ids = [row["id"] for row in conn.execute("SELECT id FROM prompt_effect_pairs WHERE repo_id = ?", (repo_id,)).fetchall()]
    if pair_ids:
        placeholders = ", ".join("?" for _ in pair_ids)
        conn.execute(f"DELETE FROM pair_tags WHERE pair_id IN ({placeholders})", tuple(pair_ids))
    conn.execute("DELETE FROM prompt_effect_pairs WHERE repo_id = ?", (repo_id,))
    conn.execute("DELETE FROM pair_candidates WHERE repo_id = ?", (repo_id,))
    conn.execute("DELETE FROM prompt_candidates WHERE repo_id = ?", (repo_id,))
    conn.execute("DELETE FROM image_candidates WHERE repo_id = ?", (repo_id,))
    conn.execute("DELETE FROM repo_scan_runs WHERE repo_id = ?", (repo_id,))
    conn.execute("DELETE FROM repo_scan_templates WHERE repo_id = ?", (repo_id,))
    memory_ids = [row["id"] for row in conn.execute("SELECT id FROM agent_memories WHERE repo_id = ?", (repo_id,)).fetchall()]
    if memory_ids:
        placeholders = ", ".join("?" for _ in memory_ids)
        conn.execute(f"DELETE FROM agent_memory_fts WHERE memory_id IN ({placeholders})", tuple(memory_ids))
    conn.execute("DELETE FROM agent_memories WHERE repo_id = ?", (repo_id,))
    conn.execute("DELETE FROM assets WHERE repo_id = ?", (repo_id,))
    conn.execute("DELETE FROM repos WHERE id = ?", (repo_id,))


@router.get("")
def list_repos(
    page: int = 1,
    page_size: int = 20,
    search: Optional[str] = None,
    category: Optional[str] = None,
    quality_level: Optional[str] = None,
    status: Optional[str] = None,
    has_images: Optional[bool] = Query(default=None),
    pending_review: Optional[bool] = Query(default=None),
):
    where = ["1 = 1"]
    params = []
    if search:
        where.append(
            """(
                repo_name LIKE ? OR owner LIKE ? OR repo_url LIKE ? OR canonical_url LIKE ?
                OR license LIKE ? OR category LIKE ? OR summary LIKE ? OR notes LIKE ?
            )"""
        )
        term = f"%{search}%"
        params.extend([term, term, term, term, term, term, term, term])
    if category:
        where.append("category = ?")
        params.append(category)
    if quality_level:
        where.append("quality_level = ?")
        params.append(quality_level)
    if status:
        where.append("status = ?")
        params.append(status)
    if has_images is not None:
        where.append("has_preview_images = ?")
        params.append(1 if has_images else 0)
    if pending_review:
        where.append("(status = 'pending_review' OR quality_level = 'pending_review')")
    clause = " AND ".join(where)
    return paginate(
        f"SELECT * FROM repos WHERE {clause} ORDER BY last_checked_at DESC, stars DESC",
        f"SELECT COUNT(*) FROM repos WHERE {clause}",
        tuple(params),
        page,
        page_size,
    )


@router.post("")
def create_repo(payload: RepoCreate):
    data = _repo_payload(payload)
    now = utc_now()
    try:
        with get_connection() as conn:
            cursor = conn.execute(
                """
                INSERT INTO repos
                    (repo_name, owner, repo_url, canonical_url, stars, forks, license, is_fork, parent_repo,
                     resource_type, category, quality_level, status, summary, local_note_path, content_hash,
                     has_preview_images, has_prompt_effect_pairs, prompt_effect_pair_count, duplicate_of, similar_to,
                     last_checked_at, last_updated_at, created_at, notes)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, NULL, NULL, 0, 0, 0, NULL, NULL, ?, NULL, ?, ?)
                """,
                (
                    data["repo_name"],
                    data["owner"],
                    data["repo_url"],
                    data["canonical_url"],
                    int(data.get("stars") or 0),
                    int(data.get("forks") or 0),
                    data.get("license") or "unknown",
                    int(data.get("is_fork") or 0),
                    data.get("parent_repo"),
                    data.get("resource_type") or "github_repo",
                    data.get("category") or "image_generation_prompt",
                    data.get("quality_level") or "pending_review",
                    data.get("status") or "pending_review",
                    data.get("summary") or "",
                    now,
                    now,
                    data.get("notes") or "",
                ),
            )
            repo_id = int(cursor.lastrowid)
    except sqlite3.IntegrityError as exc:
        raise HTTPException(status_code=409, detail="该仓库已存在于资源库") from exc
    return fetch_one("SELECT * FROM repos WHERE id = ?", (repo_id,))


@router.post("/batch-delete")
def batch_delete_repos(payload: RepoBatchRequest):
    ids = _unique_positive_ids(payload.ids)
    if not ids:
        raise HTTPException(status_code=400, detail="请选择要删除的仓库")

    placeholders = ", ".join("?" for _ in ids)
    with get_connection() as conn:
        rows = conn.execute(f"SELECT id, repo_name FROM repos WHERE id IN ({placeholders})", tuple(ids)).fetchall()
        existing_ids = [int(row["id"]) for row in rows]
        for repo_id in existing_ids:
            _delete_repo_records(conn, repo_id)

    existing_set = set(existing_ids)
    missing_ids = [repo_id for repo_id in ids if repo_id not in existing_set]
    return {
        "deleted": True,
        "requested_count": len(ids),
        "deleted_count": len(existing_ids),
        "ids": existing_ids,
        "missing_ids": missing_ids,
    }


@router.post("/batch-scan")
def batch_scan_repos(payload: RepoBatchRequest):
    ids = _unique_positive_ids(payload.ids)
    if not ids:
        raise HTTPException(status_code=400, detail="请选择要扫描的仓库")
    if len(ids) > 50:
        raise HTTPException(status_code=400, detail="单次批量扫描最多支持 50 个仓库")

    runs = []
    failed = []
    for repo_id in ids:
        try:
            run = create_repo_scan_run(repo_id, {})
        except RepoScanError as exc:
            failed.append({"repo_id": repo_id, "status_code": exc.status_code, "error": exc.detail})
            continue
        except Exception as exc:
            failed.append({"repo_id": repo_id, "status_code": 500, "error": str(exc)})
            continue
        runs.append(run)
    return {
        "status": "ok" if not failed else "partial",
        "summary": f"已创建 {len(runs)} 个扫描任务，失败 {len(failed)} 个。任务将按队列依次执行。",
        "requested_count": len(ids),
        "queued_count": len(runs),
        "failed_count": len(failed),
        "runs": runs,
        "results": runs,
        "failed": failed,
    }


@router.get("/{repo_id}")
def get_repo(repo_id: int):
    repo = fetch_one("SELECT * FROM repos WHERE id = ?", (repo_id,))
    if not repo:
        raise HTTPException(status_code=404, detail="资源不存在")
    return repo


@router.patch("/{repo_id}")
def update_repo(repo_id: int, payload: RepoUpdate):
    existing = fetch_one("SELECT * FROM repos WHERE id = ?", (repo_id,))
    if not existing:
        raise HTTPException(status_code=404, detail="资源不存在")
    data = _repo_payload(payload, dict(existing))
    now = utc_now()
    try:
        with get_connection() as conn:
            conn.execute(
                """
                UPDATE repos
                SET repo_name = ?, owner = ?, repo_url = ?, canonical_url = ?, stars = ?, forks = ?,
                    license = ?, is_fork = ?, parent_repo = ?, resource_type = ?, category = ?,
                    quality_level = ?, status = ?, summary = ?, notes = ?, last_checked_at = ?, last_updated_at = ?
                WHERE id = ?
                """,
                (
                    data["repo_name"],
                    data["owner"],
                    data["repo_url"],
                    data["canonical_url"],
                    int(data.get("stars") or 0),
                    int(data.get("forks") or 0),
                    data.get("license") or "unknown",
                    int(data.get("is_fork") or 0),
                    data.get("parent_repo"),
                    data.get("resource_type") or "github_repo",
                    data.get("category") or "image_generation_prompt",
                    data.get("quality_level") or "pending_review",
                    data.get("status") or "pending_review",
                    data.get("summary") or "",
                    data.get("notes") or "",
                    now,
                    data.get("last_updated_at"),
                    repo_id,
                ),
            )
    except sqlite3.IntegrityError as exc:
        raise HTTPException(status_code=409, detail="该仓库 canonical_url 与现有资源重复") from exc
    return fetch_one("SELECT * FROM repos WHERE id = ?", (repo_id,))


@router.delete("/{repo_id}")
def delete_repo(repo_id: int):
    repo = fetch_one("SELECT * FROM repos WHERE id = ?", (repo_id,))
    if not repo:
        raise HTTPException(status_code=404, detail="资源不存在")
    with get_connection() as conn:
        _delete_repo_records(conn, repo_id)
    return {"deleted": True, "id": repo_id}


@router.post("/{repo_id}/scan")
def scan_repo(repo_id: int, payload: Optional[RepoScanRequest] = Body(default=None)):
    try:
        return create_repo_scan_run(repo_id, payload.model_dump() if payload else None)
    except RepoScanError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.detail) from exc


@router.get("/{repo_id}/scan-runs")
def get_repo_scan_runs(repo_id: int, limit: int = 20):
    if not fetch_one("SELECT id FROM repos WHERE id = ?", (repo_id,)):
        raise HTTPException(status_code=404, detail="资源不存在")
    return list_repo_scan_runs(repo_id, limit=limit)
