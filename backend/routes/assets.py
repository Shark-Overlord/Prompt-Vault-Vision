from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, HTTPException

from database import fetch_one, get_connection, paginate, utc_now
from models.schemas import AssetPatch


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


@router.patch("/{asset_id}")
def update_asset(asset_id: int, patch: AssetPatch):
    existing = fetch_one("SELECT * FROM assets WHERE id = ?", (asset_id,))
    if not existing:
        raise HTTPException(status_code=404, detail="图片资产不存在")
    data = patch.model_dump(exclude_unset=True)
    allowed = {
        "cloud_storage_url",
        "thumbnail_cloud_storage_url",
        "cloud_storage_provider",
        "cloud_storage_bucket",
        "cloud_storage_region",
        "cloud_storage_key",
        "commercial_risk",
        "description",
    }
    updates = {key: value for key, value in data.items() if key in allowed}
    if "cloud_storage_url" in updates and updates["cloud_storage_url"]:
        updates["cloud_uploaded_at"] = utc_now()
    if not updates:
        return get_asset(asset_id)
    assignments = ", ".join(f"{key} = ?" for key in updates)
    image_hash = existing.get("image_hash")
    with get_connection() as conn:
        conn.execute(f"UPDATE assets SET {assignments} WHERE id = ?", (*updates.values(), asset_id))
        if image_hash and "cloud_storage_url" in updates:
            cloud_url = updates["cloud_storage_url"]
            conn.execute("UPDATE prompt_effect_pairs SET cloud_storage_url = ?, updated_at = ? WHERE image_hash = ?", (cloud_url, utc_now(), image_hash))
            conn.execute("UPDATE pair_candidates SET cloud_storage_url = ?, updated_at = ? WHERE image_hash = ?", (cloud_url, utc_now(), image_hash))
            conn.execute("UPDATE image_candidates SET cloud_storage_url = ? WHERE image_hash = ?", (cloud_url, image_hash))
            conn.execute("UPDATE web_ui_prompts SET screenshot_cloud_storage_url = ?, updated_at = ? WHERE screenshot_hash = ?", (cloud_url, utc_now(), image_hash))
            conn.execute("UPDATE web_ui_repo_profiles SET screenshot_cloud_storage_url = ?, updated_at = ? WHERE screenshot_hash = ?", (cloud_url, utc_now(), image_hash))
    return get_asset(asset_id)
