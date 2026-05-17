from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, HTTPException

from database import fetch_one, paginate


router = APIRouter(prefix="/api/assets", tags=["assets"])


@router.get("")
def list_assets(
    page: int = 1,
    page_size: int = 24,
    repo_id: Optional[int] = None,
    search: Optional[str] = None,
    category: Optional[str] = None,
):
    where = ["1 = 1"]
    params = []
    if repo_id:
        where.append("assets.repo_id = ?")
        params.append(repo_id)
    if search:
        where.append("(assets.description LIKE ? OR repos.repo_name LIKE ? OR repos.summary LIKE ?)")
        term = f"%{search}%"
        params.extend([term, term, term])
    if category:
        where.append("repos.category = ?")
        params.append(category)
    clause = " AND ".join(where)
    select_sql = f"""
        SELECT
            assets.*,
            repos.repo_name,
            repos.repo_url,
            repos.category AS repo_category,
            repos.status AS repo_status
        FROM assets
        LEFT JOIN repos ON repos.id = assets.repo_id
        WHERE {clause}
        ORDER BY assets.created_at DESC, assets.id DESC
    """
    count_sql = f"""
        SELECT COUNT(*)
        FROM assets
        LEFT JOIN repos ON repos.id = assets.repo_id
        WHERE {clause}
    """
    return paginate(select_sql, count_sql, tuple(params), page, page_size)


@router.get("/{asset_id}")
def get_asset(asset_id: int):
    asset = fetch_one("SELECT * FROM assets WHERE id = ?", (asset_id,))
    if not asset:
        raise HTTPException(status_code=404, detail="图片资产不存在")
    return asset
