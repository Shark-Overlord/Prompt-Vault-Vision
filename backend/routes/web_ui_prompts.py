from __future__ import annotations

import json
from typing import Any, List, Optional

from fastapi import APIRouter, HTTPException

from database import fetch_one, get_connection, paginate, utc_now
from models.schemas import WebUiPromptCreate, WebUiPromptUpdate


router = APIRouter(prefix="/api/web-ui-prompts", tags=["web-ui-prompts"])


DB_FIELDS = [
    "repo_id",
    "repo_name",
    "repo_url",
    "source_page_url",
    "source_file",
    "source_heading",
    "line_start",
    "line_end",
    "asset_group",
    "asset_type",
    "library_kind",
    "component_type",
    "page_type",
    "framework",
    "prompt_text",
    "prompt_cn_translation",
    "design_rules",
    "ui_pattern",
    "screenshot_original_url",
    "screenshot_local_path",
    "screenshot_cloud_storage_url",
    "screenshot_hash",
    "tags_json",
    "quality_level",
    "selection_status",
    "reuse_value",
    "evidence",
    "confidence",
    "content_hash",
    "license",
    "commercial_risk",
    "generated_by",
    "notes",
]


def _encode_tags(tags: Optional[List[str]]) -> str:
    clean_tags = []
    for tag in tags or []:
        clean = tag.strip()
        if clean and clean not in clean_tags:
            clean_tags.append(clean)
    return json.dumps(clean_tags, ensure_ascii=False)


def _decode_tags(tags_json: Optional[str]) -> List[str]:
    if not tags_json:
        return []
    try:
        value = json.loads(tags_json)
    except json.JSONDecodeError:
        return []
    if not isinstance(value, list):
        return []
    return [str(item) for item in value if str(item).strip()]


def _row_to_api(row: Optional[dict[str, Any]]) -> Optional[dict[str, Any]]:
    if not row:
        return None
    item = dict(row)
    item["tags"] = _decode_tags(item.get("tags_json"))
    item.pop("tags_json", None)
    return item


def _complete_repo_fields(data: dict[str, Any]) -> dict[str, Any]:
    repo_id = data.get("repo_id")
    if not repo_id:
        return data
    repo = fetch_one("SELECT id, repo_name, repo_url, canonical_url FROM repos WHERE id = ?", (repo_id,))
    if not repo:
        raise HTTPException(status_code=400, detail="repo_id 指向的资源仓库不存在")
    data["repo_name"] = data.get("repo_name") or repo.get("repo_name")
    data["repo_url"] = data.get("repo_url") or repo.get("canonical_url") or repo.get("repo_url")
    return data


def _create_payload(payload: WebUiPromptCreate) -> dict[str, Any]:
    data = payload.model_dump()
    data["prompt_text"] = data["prompt_text"].strip()
    if not data["prompt_text"]:
        raise HTTPException(status_code=400, detail="prompt_text 不能为空")
    data["tags_json"] = _encode_tags(data.pop("tags", None))
    return _complete_repo_fields(data)


@router.get("")
def list_web_ui_prompts(
    page: int = 1,
    page_size: int = 24,
    search: Optional[str] = None,
    repo_id: Optional[int] = None,
    asset_group: Optional[str] = None,
    asset_type: Optional[str] = None,
    library_kind: Optional[str] = None,
    component_type: Optional[str] = None,
    page_type: Optional[str] = None,
    framework: Optional[str] = None,
    quality_level: Optional[str] = None,
    selection_status: Optional[str] = None,
    commercial_risk: Optional[str] = None,
    has_screenshot: Optional[bool] = None,
):
    where = ["1 = 1"]
    params: List[object] = []
    if search:
        where.append(
            """(
                repo_name LIKE ? OR source_file LIKE ? OR source_heading LIKE ? OR component_type LIKE ?
                OR page_type LIKE ? OR framework LIKE ? OR prompt_text LIKE ? OR prompt_cn_translation LIKE ?
                OR design_rules LIKE ? OR ui_pattern LIKE ? OR reuse_value LIKE ? OR evidence LIKE ? OR notes LIKE ?
            )"""
        )
        term = f"%{search}%"
        params.extend([term] * 13)
    if repo_id:
        where.append("repo_id = ?")
        params.append(repo_id)
    if asset_group:
        where.append("asset_group = ?")
        params.append(asset_group)
    if asset_type:
        where.append("asset_type = ?")
        params.append(asset_type)
    if library_kind:
        where.append("library_kind = ?")
        params.append(library_kind)
    if component_type:
        where.append("component_type = ?")
        params.append(component_type)
    if page_type:
        where.append("page_type = ?")
        params.append(page_type)
    if framework:
        where.append("framework = ?")
        params.append(framework)
    if quality_level:
        where.append("quality_level = ?")
        params.append(quality_level)
    if selection_status:
        where.append("selection_status = ?")
        params.append(selection_status)
    if commercial_risk:
        where.append("commercial_risk = ?")
        params.append(commercial_risk)
    if has_screenshot is not None:
        where.append(
            "screenshot_local_path IS NOT NULL AND screenshot_local_path != ''"
            if has_screenshot
            else "(screenshot_local_path IS NULL OR screenshot_local_path = '')"
        )
    clause = " AND ".join(where)
    result = paginate(
        f"SELECT * FROM web_ui_prompts WHERE {clause} ORDER BY updated_at DESC, id DESC",
        f"SELECT COUNT(*) FROM web_ui_prompts WHERE {clause}",
        tuple(params),
        page,
        page_size,
    )
    result["items"] = [_row_to_api(item) for item in result["items"]]
    return result


@router.get("/{prompt_id}")
def get_web_ui_prompt(prompt_id: int):
    item = _row_to_api(fetch_one("SELECT * FROM web_ui_prompts WHERE id = ?", (prompt_id,)))
    if not item:
        raise HTTPException(status_code=404, detail="Web UI Prompt 不存在")
    return item


@router.post("")
def create_web_ui_prompt(payload: WebUiPromptCreate):
    data = _create_payload(payload)
    now = utc_now()
    data["created_at"] = now
    data["updated_at"] = now
    fields = [*DB_FIELDS, "created_at", "updated_at"]
    placeholders = ", ".join("?" for _ in fields)
    with get_connection() as conn:
        cursor = conn.execute(
            f"INSERT INTO web_ui_prompts ({', '.join(fields)}) VALUES ({placeholders})",
            tuple(data.get(field) for field in fields),
        )
        prompt_id = int(cursor.lastrowid)
    return get_web_ui_prompt(prompt_id)


@router.patch("/{prompt_id}")
def update_web_ui_prompt(prompt_id: int, payload: WebUiPromptUpdate):
    existing = fetch_one("SELECT * FROM web_ui_prompts WHERE id = ?", (prompt_id,))
    if not existing:
        raise HTTPException(status_code=404, detail="Web UI Prompt 不存在")
    data = payload.model_dump(exclude_unset=True)
    if "prompt_text" in data and data["prompt_text"] is not None:
        data["prompt_text"] = data["prompt_text"].strip()
        if not data["prompt_text"]:
            raise HTTPException(status_code=400, detail="prompt_text 不能为空")
    if "tags" in data:
        data["tags_json"] = _encode_tags(data.pop("tags"))
    data = _complete_repo_fields(data)
    allowed = [field for field in DB_FIELDS if field in data]
    updates = [f"{field} = ?" for field in allowed]
    params = [data[field] for field in allowed]
    updates.append("updated_at = ?")
    params.append(utc_now())
    with get_connection() as conn:
        conn.execute(f"UPDATE web_ui_prompts SET {', '.join(updates)} WHERE id = ?", (*params, prompt_id))
    return get_web_ui_prompt(prompt_id)


@router.delete("/{prompt_id}")
def delete_web_ui_prompt(prompt_id: int):
    existing = fetch_one("SELECT id FROM web_ui_prompts WHERE id = ?", (prompt_id,))
    if not existing:
        raise HTTPException(status_code=404, detail="Web UI Prompt 不存在")
    with get_connection() as conn:
        conn.execute("DELETE FROM web_ui_prompts WHERE id = ?", (prompt_id,))
    return {"deleted": True, "id": prompt_id}
