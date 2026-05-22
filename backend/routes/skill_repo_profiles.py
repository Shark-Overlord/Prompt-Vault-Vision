from __future__ import annotations

import json
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException

from database import fetch_one, get_connection, paginate, utc_now
from models.schemas import SkillRepoProfileUpdate


router = APIRouter(prefix="/api/skill-repo-profiles", tags=["skill-repo-profiles"])


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
    item["capabilities"] = _json_loads(item.pop("capabilities_json", None))
    item["input_types"] = _json_loads(item.pop("input_types_json", None))
    item["output_types"] = _json_loads(item.pop("output_types_json", None))
    item["use_cases"] = _json_loads(item.pop("use_cases_json", None))
    item["tools"] = _json_loads(item.pop("tools_json", None))
    item["tags"] = _json_loads(item.pop("tags_json", None))
    return item


@router.get("")
def list_skill_repo_profiles(
    page: int = 1,
    page_size: int = 24,
    search: Optional[str] = None,
    skill_type: Optional[str] = None,
    target_platform: Optional[str] = None,
    selection_status: Optional[str] = None,
    quality_level: Optional[str] = None,
):
    where = ["1 = 1"]
    params: List[object] = []
    if search:
        where.append(
            """(
                repo_name LIKE ? OR repo_url LIKE ? OR skill_type LIKE ? OR target_platform LIKE ?
                OR runtime_stack LIKE ? OR capabilities_json LIKE ? OR input_types_json LIKE ?
                OR output_types_json LIKE ? OR use_cases_json LIKE ? OR tools_json LIKE ?
                OR install_method LIKE ? OR configuration_notes LIKE ? OR reuse_mode LIKE ?
                OR summary_cn LIKE ? OR ai_summary_cn LIKE ? OR evidence LIKE ? OR ai_reason_cn LIKE ?
                OR tags_json LIKE ? OR notes LIKE ?
            )"""
        )
        term = f"%{search}%"
        params.extend([term] * 19)
    if skill_type:
        where.append("skill_type = ?")
        params.append(skill_type)
    if target_platform:
        where.append("target_platform LIKE ?")
        params.append(f"%{target_platform}%")
    if selection_status:
        where.append("selection_status = ?")
        params.append(selection_status)
    if quality_level:
        where.append("quality_level = ?")
        params.append(quality_level)
    clause = " AND ".join(where)
    result = paginate(
        f"SELECT * FROM skill_repo_profiles WHERE {clause} ORDER BY COALESCE(confidence, 0) DESC, updated_at DESC, id DESC",
        f"SELECT COUNT(*) FROM skill_repo_profiles WHERE {clause}",
        tuple(params),
        page,
        page_size,
    )
    result["items"] = [_row_to_api(item) for item in result["items"]]
    return result


@router.get("/{profile_id}")
def get_skill_repo_profile(profile_id: int):
    item = _row_to_api(fetch_one("SELECT * FROM skill_repo_profiles WHERE id = ?", (profile_id,)))
    if not item:
        raise HTTPException(status_code=404, detail="Skill 仓库画像不存在")
    return item


@router.patch("/{profile_id}")
def update_skill_repo_profile(profile_id: int, payload: SkillRepoProfileUpdate):
    existing = fetch_one("SELECT * FROM skill_repo_profiles WHERE id = ?", (profile_id,))
    if not existing:
        raise HTTPException(status_code=404, detail="Skill 仓库画像不存在")
    data = payload.model_dump(exclude_unset=True)
    list_fields = {
        "capabilities": "capabilities_json",
        "input_types": "input_types_json",
        "output_types": "output_types_json",
        "use_cases": "use_cases_json",
        "tools": "tools_json",
        "tags": "tags_json",
    }
    for public_key, db_key in list_fields.items():
        if public_key in data:
            data[db_key] = _json_dumps(data.pop(public_key))
    allowed = {
        "skill_type",
        "target_platform",
        "runtime_stack",
        "capabilities_json",
        "input_types_json",
        "output_types_json",
        "use_cases_json",
        "tools_json",
        "install_method",
        "configuration_notes",
        "reuse_mode",
        "summary_cn",
        "ai_summary_cn",
        "evidence",
        "ai_reason_cn",
        "tags_json",
        "confidence",
        "quality_level",
        "selection_status",
        "commercial_risk",
        "notes",
    }
    updates = {key: value for key, value in data.items() if key in allowed}
    if not updates:
        return get_skill_repo_profile(profile_id)
    updates["updated_at"] = utc_now()
    assignments = ", ".join(f"{key} = ?" for key in updates)
    with get_connection() as conn:
        conn.execute(f"UPDATE skill_repo_profiles SET {assignments} WHERE id = ?", (*updates.values(), profile_id))
    return get_skill_repo_profile(profile_id)
