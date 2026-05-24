from __future__ import annotations

import json
from typing import List, Optional

from fastapi import APIRouter, HTTPException, Query

from database import fetch_all, fetch_one, get_connection, paginate, utc_now
from models.schemas import PromptPairBatchUpdate, PromptPairPatch


router = APIRouter(prefix="/api/prompt-pairs", tags=["prompt-pairs"])


STALE_TRANSLATION_MARKERS = [
    "该 Prompt 适合",
    "该 prompt 适合",
    "重点参考其主体描述",
    "原文需结合来源 License",
    "原文需要结合来源 License",
    "适合用于图像生成场景",
    "适合用于视频生成场景",
]


LATEST_PENDING_SUGGESTION_SELECT = """
    (SELECT s.id
     FROM prompt_pair_annotation_suggestions s
     WHERE s.pair_id = prompt_effect_pairs.id AND s.status = 'pending_review'
     ORDER BY COALESCE(s.updated_at, s.created_at) DESC, s.id DESC
     LIMIT 1) AS latest_annotation_suggestion_id,
    (SELECT s.status
     FROM prompt_pair_annotation_suggestions s
     WHERE s.pair_id = prompt_effect_pairs.id AND s.status = 'pending_review'
     ORDER BY COALESCE(s.updated_at, s.created_at) DESC, s.id DESC
     LIMIT 1) AS latest_annotation_suggestion_status,
    (SELECT s.suggested_cn_explanation
     FROM prompt_pair_annotation_suggestions s
     WHERE s.pair_id = prompt_effect_pairs.id AND s.status = 'pending_review'
     ORDER BY COALESCE(s.updated_at, s.created_at) DESC, s.id DESC
     LIMIT 1) AS latest_suggested_cn_explanation,
    (SELECT s.suggested_tags_json
     FROM prompt_pair_annotation_suggestions s
     WHERE s.pair_id = prompt_effect_pairs.id AND s.status = 'pending_review'
     ORDER BY COALESCE(s.updated_at, s.created_at) DESC, s.id DESC
     LIMIT 1) AS latest_suggested_tags_json,
    (SELECT s.image_type_cn
     FROM prompt_pair_annotation_suggestions s
     WHERE s.pair_id = prompt_effect_pairs.id AND s.status = 'pending_review'
     ORDER BY COALESCE(s.updated_at, s.created_at) DESC, s.id DESC
     LIMIT 1) AS latest_suggested_image_type_cn,
    (SELECT s.reason_cn
     FROM prompt_pair_annotation_suggestions s
     WHERE s.pair_id = prompt_effect_pairs.id AND s.status = 'pending_review'
     ORDER BY COALESCE(s.updated_at, s.created_at) DESC, s.id DESC
     LIMIT 1) AS latest_suggested_reason_cn
"""


def _parse_suggested_tags(value: Optional[str]) -> List[dict]:
    if not value:
        return []
    try:
        payload = json.loads(value)
    except Exception:
        return []
    if not isinstance(payload, list):
        return []
    tags = []
    for index, item in enumerate(payload):
        name = str(item).strip()
        if name and name not in [tag["name"] for tag in tags]:
            tags.append({"id": -(index + 1), "name": name, "type": "annotation_draft", "created_at": ""})
    return tags


def _looks_like_stale_translation(value: Optional[str]) -> bool:
    text = str(value or "").strip()
    if not text:
        return False
    return any(marker in text for marker in STALE_TRANSLATION_MARKERS)


def _has_valid_translation(value: Optional[str]) -> bool:
    text = str(value or "").strip()
    return bool(text and not _looks_like_stale_translation(text))


def _valid_translation_sql(column: str = "prompt_cn_explanation") -> str:
    escaped_markers = [marker.replace("'", "''") for marker in STALE_TRANSLATION_MARKERS]
    stale_checks = " OR ".join(f"{column} LIKE '%{marker}%'" for marker in escaped_markers)
    return f"(TRIM(COALESCE({column}, '')) != '' AND NOT ({stale_checks}))"


def _has_latest_draft(pair: dict) -> bool:
    draft_text = str(pair.get("latest_suggested_cn_explanation") or "").strip()
    draft_tags = _parse_suggested_tags(pair.get("latest_suggested_tags_json"))
    return bool(pair.get("latest_annotation_suggestion_id") and draft_text and not _looks_like_stale_translation(draft_text) and draft_tags)


def _attach_tags(pair: dict) -> dict:
    tags = fetch_all(
        """
        SELECT tags.*
        FROM tags
        JOIN pair_tags ON pair_tags.tag_id = tags.id
        WHERE pair_tags.pair_id = ?
        ORDER BY tags.name
        """,
        (pair["id"],),
    )
    pair["tags"] = tags
    pair["tag_count"] = len(tags)
    pair["latest_suggested_tags"] = _parse_suggested_tags(pair.get("latest_suggested_tags_json"))
    pair["annotation_display_status"] = "formal" if tags and _has_valid_translation(pair.get("prompt_cn_explanation")) else "draft" if _has_latest_draft(pair) else "none"
    return pair


def _attach_tags_to_items(items: List[dict]) -> List[dict]:
    if not items:
        return items
    ids = [int(item["id"]) for item in items]
    placeholders = ", ".join("?" for _ in ids)
    rows = fetch_all(
        f"""
        SELECT pair_tags.pair_id, tags.id, tags.name, tags.type, tags.created_at
        FROM pair_tags
        JOIN tags ON pair_tags.tag_id = tags.id
        WHERE pair_tags.pair_id IN ({placeholders})
        ORDER BY tags.name
        """,
        tuple(ids),
    )
    grouped = {item_id: [] for item_id in ids}
    for row in rows:
        grouped.setdefault(int(row["pair_id"]), []).append(
            {
                "id": row["id"],
                "name": row["name"],
                "type": row["type"],
                "created_at": row["created_at"],
            }
        )
    for item in items:
        tags = grouped.get(int(item["id"]), [])
        item["tags"] = tags
        item["tag_count"] = len(tags)
        item["latest_suggested_tags"] = _parse_suggested_tags(item.get("latest_suggested_tags_json"))
        item["annotation_display_status"] = "formal" if tags and _has_valid_translation(item.get("prompt_cn_explanation")) else "draft" if _has_latest_draft(item) else "none"
    return items


@router.get("")
def list_prompt_pairs(
    page: int = 1,
    page_size: int = 24,
    search: Optional[str] = None,
    category: Optional[str] = None,
    scenario: Optional[str] = None,
    quality_level: Optional[str] = None,
    selection_status: Optional[str] = None,
    visual_asset_type: Optional[str] = None,
    commercial_risk: Optional[str] = None,
    tag_search: Optional[str] = None,
    annotated: Optional[bool] = Query(default=None),
    has_translation: Optional[bool] = Query(default=None),
    has_tags: Optional[bool] = Query(default=None),
    favorite_only: Optional[bool] = Query(default=None),
    has_image: Optional[bool] = Query(default=None),
    repo_id: Optional[int] = None,
):
    where = ["1 = 1"]
    params: List[object] = []
    if search:
        where.append(
            """
            (
                repo_name LIKE ?
                OR original_prompt LIKE ?
                OR prompt_cn_explanation LIKE ?
                OR effect_review LIKE ?
                OR EXISTS (
                    SELECT 1
                    FROM pair_tags
                    JOIN tags ON pair_tags.tag_id = tags.id
                    WHERE pair_tags.pair_id = prompt_effect_pairs.id
                    AND tags.name LIKE ?
                )
                OR EXISTS (
                    SELECT 1
                    FROM prompt_pair_annotation_suggestions s
                    WHERE s.pair_id = prompt_effect_pairs.id
                    AND s.status = 'pending_review'
                    AND (s.suggested_cn_explanation LIKE ? OR s.suggested_tags_json LIKE ? OR s.image_type_cn LIKE ?)
                )
            )
            """
        )
        term = f"%{search}%"
        params.extend([term, term, term, term, term, term, term, term])
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
    if visual_asset_type:
        where.append("visual_asset_type = ?")
        params.append(visual_asset_type)
    if commercial_risk:
        where.append("commercial_risk = ?")
        params.append(commercial_risk)
    if tag_search:
        where.append(
            """
            (
                EXISTS (
                    SELECT 1
                    FROM pair_tags
                    JOIN tags ON pair_tags.tag_id = tags.id
                    WHERE pair_tags.pair_id = prompt_effect_pairs.id
                    AND tags.name LIKE ?
                )
                OR EXISTS (
                    SELECT 1
                    FROM prompt_pair_annotation_suggestions s
                    WHERE s.pair_id = prompt_effect_pairs.id
                    AND s.status = 'pending_review'
                    AND s.suggested_tags_json LIKE ?
                )
            )
            """
        )
        params.extend([f"%{tag_search}%", f"%{tag_search}%"])
    translation_clause = _valid_translation_sql("prompt_cn_explanation")
    tags_clause = "EXISTS (SELECT 1 FROM pair_tags WHERE pair_tags.pair_id = prompt_effect_pairs.id)"
    draft_translation_clause = _valid_translation_sql("s.suggested_cn_explanation")
    draft_annotation_clause = f"""
        EXISTS (
            SELECT 1
            FROM prompt_pair_annotation_suggestions s
            WHERE s.pair_id = prompt_effect_pairs.id
            AND s.status = 'pending_review'
            AND {draft_translation_clause}
            AND TRIM(COALESCE(s.suggested_tags_json, '')) NOT IN ('', '[]')
        )
    """
    display_annotation_clause = f"(({translation_clause} AND {tags_clause}) OR {draft_annotation_clause})"
    if has_translation is not None:
        where.append(translation_clause if has_translation else f"NOT ({translation_clause})")
    if has_tags is not None:
        where.append(tags_clause if has_tags else f"NOT ({tags_clause})")
    if annotated is not None:
        where.append(display_annotation_clause if annotated else f"NOT ({display_annotation_clause})")
    if favorite_only:
        where.append("selection_status = 'featured'")
    if has_image is not None:
        where.append("image_local_path IS NOT NULL AND image_local_path != ''" if has_image else "(image_local_path IS NULL OR image_local_path = '')")
    if repo_id:
        where.append("repo_id = ?")
        params.append(repo_id)
    clause = " AND ".join(where)
    result = paginate(
        f"SELECT prompt_effect_pairs.*, {LATEST_PENDING_SUGGESTION_SELECT} FROM prompt_effect_pairs WHERE {clause} ORDER BY updated_at DESC, id DESC",
        f"SELECT COUNT(*) FROM prompt_effect_pairs WHERE {clause}",
        tuple(params),
        page,
        page_size,
    )
    result["items"] = _attach_tags_to_items(result["items"])
    return result


@router.post("/batch-update")
def batch_update_prompt_pairs(payload: PromptPairBatchUpdate):
    ids = [int(item) for item in payload.ids if int(item) > 0]
    if not ids:
        raise HTTPException(status_code=400, detail="No prompt pairs selected")
    placeholders = ", ".join("?" for _ in ids)
    data = payload.model_dump(exclude_unset=True)
    updates = []
    params: List[object] = []
    for field in ["selection_status", "quality_level", "visual_asset_type"]:
        value = data.get(field)
        if value is not None:
            updates.append(f"{field} = ?")
            params.append(value)
    if data.get("visual_asset_type") is not None:
        updates.append("visual_asset_type_source = ?")
        params.append("manual")
        updates.append("visual_asset_type_confidence = ?")
        params.append(100)
        updates.append("visual_asset_type_reason = ?")
        params.append("User batch-set the visual asset type in the image generation asset library.")
    if updates:
        updates.append("updated_at = ?")
        params.append(utc_now())
    now = utc_now()
    with get_connection() as conn:
        existing = conn.execute(f"SELECT id FROM prompt_effect_pairs WHERE id IN ({placeholders})", tuple(ids)).fetchall()
        existing_ids = [int(row["id"]) for row in existing]
        if updates and existing_ids:
            existing_placeholders = ", ".join("?" for _ in existing_ids)
            conn.execute(
                f"UPDATE prompt_effect_pairs SET {', '.join(updates)} WHERE id IN ({existing_placeholders})",
                (*params, *existing_ids),
            )
        if payload.tags is not None and existing_ids:
            clean_tags = []
            for name in payload.tags:
                clean = name.strip()
                if clean and clean not in clean_tags:
                    clean_tags.append(clean)
            for pair_id in existing_ids:
                conn.execute("DELETE FROM pair_tags WHERE pair_id = ?", (pair_id,))
                for clean in clean_tags:
                    conn.execute("INSERT OR IGNORE INTO tags (name, type, created_at) VALUES (?, 'custom', ?)", (clean, now))
                    tag_row = conn.execute("SELECT id FROM tags WHERE name = ?", (clean,)).fetchone()
                    if tag_row:
                        conn.execute("INSERT OR IGNORE INTO pair_tags (pair_id, tag_id) VALUES (?, ?)", (pair_id, tag_row["id"]))
    existing_set = set(existing_ids)
    return {
        "updated": True,
        "requested_count": len(ids),
        "updated_count": len(existing_ids),
        "ids": existing_ids,
        "missing_ids": [item for item in ids if item not in existing_set],
    }


@router.get("/{pair_id}")
def get_prompt_pair(pair_id: int):
    pair = fetch_one(f"SELECT prompt_effect_pairs.*, {LATEST_PENDING_SUGGESTION_SELECT} FROM prompt_effect_pairs WHERE id = ?", (pair_id,))
    if not pair:
        raise HTTPException(status_code=404, detail="Prompt pair not found")
    return _attach_tags(pair)


@router.patch("/{pair_id}")
def update_prompt_pair(pair_id: int, patch: PromptPairPatch):
    existing = fetch_one("SELECT * FROM prompt_effect_pairs WHERE id = ?", (pair_id,))
    if not existing:
        raise HTTPException(status_code=404, detail="Prompt pair not found")
    updates = []
    params: List[object] = []
    allowed = [
        "selection_status",
        "quality_level",
        "effect_review",
        "reusable_value",
        "commercial_risk",
        "prompt_cn_explanation",
        "visual_asset_type",
        "visual_asset_type_confidence",
        "visual_asset_type_reason",
        "cloud_storage_url",
    ]
    data = patch.model_dump(exclude_unset=True)
    for field in allowed:
        if field in data and data[field] is not None:
            updates.append(f"{field} = ?")
            params.append(data[field])
    if "visual_asset_type" in data and data["visual_asset_type"] is not None:
        updates.append("visual_asset_type_source = ?")
        params.append("manual")
    updates.append("updated_at = ?")
    params.append(utc_now())
    with get_connection() as conn:
        conn.execute(f"UPDATE prompt_effect_pairs SET {', '.join(updates)} WHERE id = ?", (*params, pair_id))
        if "cloud_storage_url" in data and existing.get("image_hash"):
            conn.execute(
                "UPDATE assets SET cloud_storage_url = ?, cloud_uploaded_at = ? WHERE image_hash = ?",
                (data["cloud_storage_url"], utc_now() if data["cloud_storage_url"] else None, existing["image_hash"]),
            )
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
