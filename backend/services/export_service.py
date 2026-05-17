from __future__ import annotations

import csv
import json
from pathlib import Path
from typing import Dict, Iterable, List, Optional

from database import PROJECT_ROOT, fetch_all, utc_now


EXPORT_DIR = PROJECT_ROOT / "exports"


def _featured_pairs(selection_status: str = "featured", category: Optional[str] = None) -> List[Dict]:
    where = ["selection_status = ?"]
    params: List[str] = [selection_status]
    if category:
        where.append("category = ?")
        params.append(category)
    sql = f"""
        SELECT * FROM prompt_effect_pairs
        WHERE {' AND '.join(where)}
        ORDER BY updated_at DESC, created_at DESC
    """
    return fetch_all(sql, tuple(params))


def export_markdown(selection_status: str = "featured", category: Optional[str] = None) -> Path:
    EXPORT_DIR.mkdir(parents=True, exist_ok=True)
    rows = _featured_pairs(selection_status, category)
    path = EXPORT_DIR / "featured_prompts.md"
    lines = ["# 精选 Prompt 库", "", f"- 导出时间：{utc_now()}", f"- 筛选结论：{selection_status}", ""]
    for row in rows:
        lines.extend(
            [
                f"## {row.get('repo_name') or '未命名 Prompt'}",
                "",
                f"- 来源：{row.get('source_page_url') or row.get('repo_url') or ''}",
                f"- 分类：{row.get('category') or ''}",
                f"- 场景：{row.get('scenario') or ''}",
                f"- 推荐等级：{row.get('quality_level') or ''}",
                f"- 效果图：{row.get('image_local_path') or ''}",
                "",
                "### Prompt",
                "",
                row.get("original_prompt") or "",
                "",
                "### 中文解释",
                "",
                row.get("prompt_cn_explanation") or "",
                "",
                "### 效果评价",
                "",
                row.get("effect_review") or "",
                "",
                "### 使用建议",
                "",
                row.get("reusable_value") or "",
                "",
            ]
        )
    path.write_text("\n".join(lines), encoding="utf-8")
    return path


def export_json(selection_status: str = "featured", category: Optional[str] = None) -> Path:
    EXPORT_DIR.mkdir(parents=True, exist_ok=True)
    rows = _featured_pairs(selection_status, category)
    payload = [
        {
            "title": row.get("repo_name") or "",
            "category": row.get("category") or "",
            "scenario": row.get("scenario") or "",
            "prompt": row.get("original_prompt") or "",
            "image_path": row.get("image_local_path") or "",
            "effect_review": row.get("effect_review") or "",
            "selection_status": row.get("selection_status") or "",
            "source_url": row.get("source_page_url") or row.get("repo_url") or "",
            "license": row.get("license") or "",
            "commercial_risk": row.get("commercial_risk") or "",
        }
        for row in rows
    ]
    path = EXPORT_DIR / "pairs_index.json"
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return path


def export_skill(selection_status: str = "featured", category: Optional[str] = None) -> Path:
    EXPORT_DIR.mkdir(parents=True, exist_ok=True)
    rows = _featured_pairs(selection_status, category)
    payload = {
        "skill_name": "visual_prompt_library",
        "description": "本地视觉 Prompt 精选库",
        "items": [
            {
                "task_type": row.get("task_type") or row.get("category") or "",
                "scenario": row.get("scenario") or "",
                "prompt": row.get("original_prompt") or "",
                "usage_note": row.get("reusable_value") or row.get("prompt_cn_explanation") or "",
                "example_image": row.get("image_local_path") or "",
            }
            for row in rows
        ],
    }
    path = EXPORT_DIR / "skill_export.json"
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return path


def export_csv(selection_status: str = "featured", category: Optional[str] = None) -> Path:
    EXPORT_DIR.mkdir(parents=True, exist_ok=True)
    rows = _featured_pairs(selection_status, category)
    path = EXPORT_DIR / "featured_prompts.csv"
    fields = ["repo_name", "category", "scenario", "quality_level", "selection_status", "original_prompt", "image_local_path", "source_page_url", "license", "commercial_risk"]
    with path.open("w", encoding="utf-8-sig", newline="") as fp:
        writer = csv.DictWriter(fp, fieldnames=fields)
        writer.writeheader()
        for row in rows:
            writer.writerow({field: row.get(field) or "" for field in fields})
    return path


def run_export(fmt: str, selection_status: str = "featured", category: Optional[str] = None) -> Dict[str, str]:
    fmt = fmt.lower()
    if fmt == "markdown":
        path = export_markdown(selection_status, category)
    elif fmt == "json":
        path = export_json(selection_status, category)
    elif fmt == "skill":
        path = export_skill(selection_status, category)
    elif fmt == "csv":
        path = export_csv(selection_status, category)
    else:
        raise ValueError(f"不支持的导出格式：{fmt}")
    return {"path": str(path.relative_to(PROJECT_ROOT)).replace("\\", "/"), "format": fmt}

