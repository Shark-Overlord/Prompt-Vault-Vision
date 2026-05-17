from __future__ import annotations

from typing import List, Optional

from fastapi import APIRouter, HTTPException, Query

from database import fetch_all, fetch_one, get_connection, paginate, utc_now
from models.schemas import PromptPairPatch


router = APIRouter(prefix="/api/prompt-pairs", tags=["prompt-pairs"])


@router.get("")
def list_prompt_pairs(
    page: int = 1,
    page_size: int = 24,
    search: Optional[str] = None,
    category: Optional[str] = None,
    scenario: Optional[str] = None,
    quality_level: Optional[str] = None,
    selection_status: Optional[str] = None,
    commercial_risk: Optional[str] = None,
    has_image: Optional[bool] = Query(default=None),
    repo_id: Optional[int] = None,
):
    where = ["1 = 1"]
    params: List[object] = []
    if search:
        where.append("(repo_name LIKE ? OR original_prompt LIKE ? OR prompt_cn_explanation LIKE ? OR effect_review LIKE ?)")
        term = f"%{search}%"
        params.extend([term, term, term, term])
    if category:
        where.append("category = ?")
        params.append(category)
    if scenario:
        where.append("scenario = ?")
        params.append(scenario)
    if quality_level:
        where.append("quality_level = ?")
        params.append(quality_level)
    if selection_status:
        where.append("selection_status = ?")
        params.append(selection_status)
    if commercial_risk:
        where.append("commercial_risk = ?")
        params.append(commercial_risk)
    if has_image is not None:
        where.append("image_local_path IS NOT NULL AND image_local_path != ''" if has_image else "(image_local_path IS NULL OR image_local_path = '')")
    if repo_id:
        where.append("repo_id = ?")
        params.append(repo_id)
    clause = " AND ".join(where)
    return paginate(
        f"SELECT * FROM prompt_effect_pairs WHERE {clause} ORDER BY updated_at DESC, id DESC",
        f"SELECT COUNT(*) FROM prompt_effect_pairs WHERE {clause}",
        tuple(params),
        page,
        page_size,
    )


@router.get("/{pair_id}")
def get_prompt_pair(pair_id: int):
    pair = fetch_one("SELECT * FROM prompt_effect_pairs WHERE id = ?", (pair_id,))
    if not pair:
        raise HTTPException(status_code=404, detail="Prompt 效果对不存在")
    tags = fetch_all(
        """
        SELECT tags.*
        FROM tags
        JOIN pair_tags ON pair_tags.tag_id = tags.id
        WHERE pair_tags.pair_id = ?
        ORDER BY tags.name
        """,
        (pair_id,),
    )
    pair["tags"] = tags
    return pair


@router.patch("/{pair_id}")
def update_prompt_pair(pair_id: int, patch: PromptPairPatch):
    existing = fetch_one("SELECT * FROM prompt_effect_pairs WHERE id = ?", (pair_id,))
    if not existing:
        raise HTTPException(status_code=404, detail="Prompt 效果对不存在")
    updates = []
    params: List[object] = []
    allowed = [
        "selection_status",
        "quality_level",
        "effect_review",
        "reusable_value",
        "commercial_risk",
        "prompt_cn_explanation",
    ]
    data = patch.model_dump(exclude_unset=True)
    for field in allowed:
        if field in data and data[field] is not None:
            updates.append(f"{field} = ?")
            params.append(data[field])
    updates.append("updated_at = ?")
    params.append(utc_now())
    with get_connection() as conn:
        conn.execute(f"UPDATE prompt_effect_pairs SET {', '.join(updates)} WHERE id = ?", (*params, pair_id))
        if patch.tags is not None:
            conn.execute("DELETE FROM pair_tags WHERE pair_id = ?", (pair_id,))
            for name in patch.tags:
                clean = name.strip()
                if not clean:
                    continue
                conn.execute("INSERT OR IGNORE INTO tags (name, type, created_at) VALUES (?, 'custom', ?)", (clean, utc_now()))
                tag_row = conn.execute("SELECT id FROM tags WHERE name = ?", (clean,)).fetchone()
                if tag_row:
                    conn.execute("INSERT OR IGNORE INTO pair_tags (pair_id, tag_id) VALUES (?, ?)", (pair_id, tag_row["id"]))
    return get_prompt_pair(pair_id)

