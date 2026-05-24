from __future__ import annotations

import json
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException

from database import fetch_one, get_connection, paginate, utc_now
from models.schemas import WebUiRepoProfileUpdate


router = APIRouter(prefix="/api/web-ui-repo-profiles", tags=["web-ui-repo-profiles"])


def _json_loads(value: Optional[str]) -> List[str]:
    if not value:
        return []
    try:
        payload = json.loads(value)
    except Exception:
        return []
    if not isinstance(payload, list):
        return []
    return [str(item) for item in payload if str(item).strip()]


def _json_dumps(values: Optional[List[str]]) -> str:
    clean: List[str] = []
    for value in values or []:
        text = str(value).strip()
        if text and text not in clean:
            clean.append(text)
    return json.dumps(clean, ensure_ascii=False)


def _row_to_api(row: Optional[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    if not row:
        return None
    item = dict(row)
    item["supported_frontend_types"] = _json_loads(item.pop("supported_frontend_types_json", None))
    item["component_focus"] = _json_loads(item.pop("component_focus_json", None))
    item["style_keywords"] = _json_loads(item.pop("style_keywords_json", None))
    return item


@router.get("")
def list_web_ui_repo_profiles(
    page: int = 1,
    page_size: int = 24,
    search: Optional[str] = None,
    profile_type: Optional[str] = None,
    library_kind: Optional[str] = None,
    selection_status: Optional[str] = None,
    quality_level: Optional[str] = None,
    has_screenshot: Optional[bool] = None,
):
    where = ["1 = 1"]
    params: List[object] = []
    if search:
        where.append(
            """(
                repo_name LIKE ? OR repo_url LIKE ? OR profile_type LIKE ? OR library_kind LIKE ?
                OR ui_stack LIKE ? OR supported_frontend_types_json LIKE ? OR component_focus_json LIKE ?
                OR style_keywords_json LIKE ? OR reuse_mode LIKE ? OR summary_cn LIKE ? OR ai_summary_cn LIKE ?
                OR evidence LIKE ? OR ai_reason_cn LIKE ? OR notes LIKE ?
            )"""
        )
        term = f"%{search}%"
        params.extend([term] * 14)
    if profile_type:
        where.append("profile_type = ?")
        params.append(profile_type)
    if library_kind:
        where.append("library_kind = ?")
        params.append(library_kind)
    if selection_status:
        where.append("selection_status = ?")
        params.append(selection_status)
    if quality_level:
        where.append("quality_level = ?")
        params.append(quality_level)
    if has_screenshot is not None:
        where.append(
            "screenshot_local_path IS NOT NULL AND screenshot_local_path != ''"
            if has_screenshot
            else "(screenshot_local_path IS NULL OR screenshot_local_path = '')"
        )
    clause = " AND ".join(where)
    result = paginate(
        f"SELECT * FROM web_ui_repo_profiles WHERE {clause} ORDER BY COALESCE(confidence, 0) DESC, updated_at DESC, id DESC",
        f"SELECT COUNT(*) FROM web_ui_repo_profiles WHERE {clause}",
        tuple(params),
        page,
        page_size,
    )
    result["items"] = [_row_to_api(item) for item in result["items"]]
    return result


@router.get("/{profile_id}")
def get_web_ui_repo_profile(profile_id: int):
    item = _row_to_api(fetch_one("SELECT * FROM web_ui_repo_profiles WHERE id = ?", (profile_id,)))
    if not item:
        raise HTTPException(status_code=404, detail="Web UI 仓库画像不存在")
    return item


@router.patch("/{profile_id}")
def update_web_ui_repo_profile(profile_id: int, payload: WebUiRepoProfileUpdate):
    existing = fetch_one("SELECT * FROM web_ui_repo_profiles WHERE id = ?", (profile_id,))
    if not existing:
        raise HTTPException(status_code=404, detail="Web UI 仓库画像不存在")
    data = payload.model_dump(exclude_unset=True)
    if "supported_frontend_types" in data:
        data["supported_frontend_types_json"] = _json_dumps(data.pop("supported_frontend_types"))
    if "component_focus" in data:
        data["component_focus_json"] = _json_dumps(data.pop("component_focus"))
    if "style_keywords" in data:
        data["style_keywords_json"] = _json_dumps(data.pop("style_keywords"))
    allowed = {
        "profile_type",
        "library_kind",
        "ui_stack",
        "supported_frontend_types_json",
        "component_focus_json",
        "style_keywords_json",
        "reuse_mode",
        "summary_cn",
        "ai_summary_cn",
        "evidence",
        "ai_reason_cn",
        "confidence",
        "screenshot_cloud_storage_url",
        "quality_level",
        "selection_status",
        "commercial_risk",
        "notes",
    }
    updates = {key: value for key, value in data.items() if key in allowed}
    if not updates:
        return get_web_ui_repo_profile(profile_id)
    updates["updated_at"] = utc_now()
    assignments = ", ".join(f"{key} = ?" for key in updates)
    with get_connection() as conn:
        conn.execute(f"UPDATE web_ui_repo_profiles SET {assignments} WHERE id = ?", (*updates.values(), profile_id))
    return get_web_ui_repo_profile(profile_id)
