from __future__ import annotations

import json
import re
from pathlib import PurePosixPath
from typing import Any, Dict, List, Optional, Sequence

from database import fetch_all, fetch_one, get_connection, utc_now
from services.ai_config_service import chat_completion
from services.candidate_service import extract_candidate_data
from agents.prompts import REPO_TEMPLATE_SYSTEM_PROMPT, REPO_TEMPLATE_USER_PROMPT


def _json_dumps(data: Dict[str, Any]) -> str:
    return json.dumps(data, ensure_ascii=False, indent=2)


def _extract_json_object(text: str) -> Dict[str, Any]:
    clean = (text or "").strip()
    if clean.startswith("```"):
        clean = re.sub(r"^```(?:json)?", "", clean).strip()
        clean = re.sub(r"```$", "", clean).strip()
    start = clean.find("{")
    end = clean.rfind("}")
    if start >= 0 and end > start:
        clean = clean[start : end + 1]
    payload = json.loads(clean)
    if not isinstance(payload, dict):
        raise ValueError("AI 模板响应必须是 JSON 对象")
    return payload


def _as_string_list(value: Any, fallback: Sequence[str]) -> List[str]:
    if not isinstance(value, list):
        return list(fallback)
    cleaned = [str(item).strip() for item in value if str(item).strip()]
    return cleaned or list(fallback)


def _as_int(value: Any, default: int = 60) -> int:
    try:
        return max(0, min(int(value), 100))
    except Exception:
        return default


def validate_template_content(payload: Dict[str, Any]) -> Dict[str, Any]:
    if payload.get("schema_version") == 2 or "primary_target_files" in payload or "markdown_strategies" in payload:
        primary = _as_string_list(payload.get("primary_target_files"), [])
        no_markdown_reason = str(payload.get("no_markdown_pair_files_reason") or "").strip()
        if not primary and not no_markdown_reason:
            raise ValueError("AI 模板必须包含 primary_target_files，或说明没有 Markdown 配对文件的原因")
        content = {
            "schema_version": 2,
            "primary_target_files": primary,
            "secondary_target_files": _as_string_list(payload.get("secondary_target_files"), []),
            "markdown_strategies": _as_string_list(payload.get("markdown_strategies"), ["prompt_then_image_section", "table_same_row", "same_heading_section"]),
            "prompt_locators": _as_string_list(payload.get("prompt_locators"), ["Prompt", "提示词", "prompt"]),
            "image_locators": _as_string_list(payload.get("image_locators"), ["Generated Images", "Result", "Output", "image", "image_url"]),
            "pairing_strategy": _as_string_list(payload.get("pairing_strategy"), ["same_section", "prompt_section_to_next_image_section", "same_row"]),
            "exclude_image_keywords": _as_string_list(payload.get("exclude_image_keywords"), ["badge", "logo", "icon", "avatar", "sponsor"]),
            "evidence_rules": _as_string_list(payload.get("evidence_rules"), ["必须保留来源文件、来源页面、匹配类型、匹配分数和中文证据。"]),
            "no_markdown_pair_files_reason": no_markdown_reason,
            "summary_cn": str(payload.get("summary_cn") or "AI 生成的 Markdown 优先仓库扫描模板，待人工复查。").strip(),
            "confidence": _as_int(payload.get("confidence"), 60),
        }
        return content

    content = {
        "schema_version": 2,
        "primary_target_files": [path for path in _as_string_list(payload.get("scan_paths"), ["README.md", "docs", "examples", "prompts", "samples"]) if path.lower().endswith((".md", ".mdx")) or "*" in path],
        "secondary_target_files": [path for path in _as_string_list(payload.get("scan_paths"), []) if not path.lower().endswith((".md", ".mdx"))],
        "markdown_strategies": ["prompt_then_image_section", "table_same_row", "same_heading_section"],
        "prompt_locators": _as_string_list(payload.get("prompt_field_names"), ["prompt", "positive_prompt", "image_prompt", "video_prompt"]) + _as_string_list(payload.get("section_hints"), ["Prompt"]),
        "image_locators": _as_string_list(payload.get("image_field_names"), ["image", "image_url", "output", "result", "thumbnail"]) + _as_string_list(payload.get("section_hints"), ["Generated Images", "Output", "Result", "Example"]),
        "pairing_strategy": ["same_section", "same_row"],
        "exclude_image_keywords": _as_string_list(payload.get("exclude_image_keywords"), ["badge", "logo", "icon", "avatar", "sponsor"]),
        "evidence_rules": _as_string_list(payload.get("matching_notes"), ["优先同一结构区块内的 Prompt 与图片。"]) + _as_string_list(payload.get("risk_notes"), ["License 和商用风险需要人工复查。"]),
        "no_markdown_pair_files_reason": "",
        "summary_cn": str(payload.get("summary_cn") or "AI 生成的仓库专属扫描模板，待人工复查。").strip(),
        "confidence": _as_int(payload.get("confidence"), 60),
    }
    return content


def _repo_summary(repo: Dict[str, Any], documents: Sequence[Dict[str, str]]) -> str:
    sorted_documents = sorted(documents, key=lambda document: (0 if PurePosixPath((document.get("path") or "").lower()).suffix in {".md", ".mdx"} else 1, document.get("path") or ""))
    file_lines = []
    for document in sorted_documents[:40]:
        content = document.get("content") or ""
        file_lines.append(f"- {document.get('path')}: {len(content)} chars")
    return "\n".join(
        [
            f"仓库：{repo.get('owner')}/{repo.get('repo_name')}",
            f"分类：{repo.get('category')}",
            f"说明：{repo.get('summary') or ''}",
            "可扫描文件：",
            *file_lines,
        ]
    )[:6000]


def _count_markdown_tables(content: str) -> int:
    return len(re.findall(r"(?m)^\s*\|.+\|\s*$", content or ""))


def _markdown_headings(content: str) -> List[str]:
    headings = re.findall(r"(?m)^#{1,6}\s+(.+?)\s*$", content or "")
    return [heading.strip()[:90] for heading in headings[:24]]


def _count_markdown_images(content: str) -> int:
    markdown_images = len(re.findall(r"!\[[^\]]*\]\([^)]+\)", content or ""))
    html_images = len(re.findall(r"<img\b", content or "", re.IGNORECASE))
    return markdown_images + html_images


def _content_snippets(content: str, limit: int = 3) -> List[str]:
    snippets: List[str] = []
    for match in re.finditer(r"(?i)(prompt|提示词|generated images?|result|output|效果图|生成图|image)", content or ""):
        start = max(0, match.start() - 140)
        end = min(len(content), match.end() + 220)
        snippet = " ".join((content[start:end] or "").split())
        if snippet and snippet not in snippets:
            snippets.append(snippet[:420])
        if len(snippets) >= limit:
            break
    return snippets


def build_file_profiles(documents: Sequence[Dict[str, str]], category: str) -> List[Dict[str, Any]]:
    profiles: List[Dict[str, Any]] = []
    for document in documents:
        path = document.get("path") or ""
        content = document.get("content") or ""
        suffix = PurePosixPath(path.lower()).suffix
        if suffix not in {".md", ".mdx", ".json", ".jsonl", ".csv", ".yaml", ".yml"}:
            continue

        extracted = extract_candidate_data([document], category)
        pairs = extracted.get("pair_candidates") or []
        prompt_candidates = extracted.get("prompt_candidates") or []
        image_count = _count_markdown_images(content) if suffix in {".md", ".mdx"} else len(pairs)
        profile = {
            "path": path,
            "file_type": "markdown" if suffix in {".md", ".mdx"} else suffix.lstrip("."),
            "char_count": len(content),
            "prompt_candidate_count": len(prompt_candidates),
            "image_candidate_count": image_count,
            "estimated_pair_count": len(pairs),
            "headings": _markdown_headings(content) if suffix in {".md", ".mdx"} else [],
            "table_line_count": _count_markdown_tables(content) if suffix in {".md", ".mdx"} else 0,
            "pair_samples": [
                {
                    "match_type": pair.relation_type,
                    "match_score": pair.confidence,
                    "evidence": pair.evidence[:220],
                    "image_url": pair.image_url,
                }
                for pair in pairs[:3]
            ],
            "context_snippets": _content_snippets(content),
        }
        if profile["prompt_candidate_count"] > 0 and (profile["image_candidate_count"] > 0 or profile["estimated_pair_count"] > 0):
            profiles.append(profile)
        elif profile["estimated_pair_count"] > 0:
            profiles.append(profile)

    profiles.sort(key=lambda profile: (0 if profile["file_type"] == "markdown" else 1, -int(profile["estimated_pair_count"]), profile["path"]))
    return profiles


def _file_profiles_summary(profiles: Sequence[Dict[str, Any]]) -> str:
    lines: List[str] = []
    for profile in profiles[:40]:
        lines.append(
            f"- {profile['path']} | {profile['file_type']} | prompts {profile['prompt_candidate_count']} | images {profile['image_candidate_count']} | estimated_pairs {profile['estimated_pair_count']}"
        )
        if profile.get("headings"):
            lines.append(f"  headings: {', '.join(profile['headings'][:10])}")
        if profile.get("pair_samples"):
            lines.append("  pair_samples:")
            for sample in profile["pair_samples"][:2]:
                lines.append(f"    - {sample['match_type']} score {sample['match_score']} | {sample['evidence']}")
        if profile.get("context_snippets"):
            lines.append(f"  context: {profile['context_snippets'][0]}")
    return "\n".join(lines)[:12000]


def _baseline_summary(record: Dict[str, Any]) -> str:
    pairs = record.get("_pair_candidates") or []
    pair_lines = []
    for pair in pairs[:8]:
        pair_lines.append(
            f"- {pair.source_file or ''} | {pair.relation_type} | score {pair.confidence} | {pair.evidence[:180]}"
        )
    return "\n".join(
        [
            f"扫描文件数：{len(record.get('_scanned_files') or [])}",
            f"Prompt 候选数：{len(record.get('_prompt_candidates') or [])}",
            f"配对候选数：{len(pairs)}",
            "配对样例：",
            *pair_lines,
        ]
    )[:5000]


def list_templates(repo_id: int) -> List[Dict[str, Any]]:
    return fetch_all("SELECT * FROM repo_scan_templates WHERE repo_id = ? ORDER BY updated_at DESC, id DESC", (repo_id,))


def get_template(template_id: int) -> Optional[Dict[str, Any]]:
    return fetch_one("SELECT * FROM repo_scan_templates WHERE id = ?", (template_id,))


def get_active_template(repo_id: int) -> Optional[Dict[str, Any]]:
    return fetch_one(
        """
        SELECT * FROM repo_scan_templates
        WHERE repo_id = ? AND status = 'active'
        ORDER BY approved_at DESC, updated_at DESC, id DESC
        LIMIT 1
        """,
        (repo_id,),
    )


def create_template_record(
    repo_id: int,
    content: Dict[str, Any],
    source_ai_config_id: Optional[int],
    status: str = "pending_review",
    notes: Optional[str] = None,
) -> Dict[str, Any]:
    now = utc_now()
    current = fetch_one("SELECT MAX(template_version) AS version FROM repo_scan_templates WHERE repo_id = ?", (repo_id,))
    version = int((current or {}).get("version") or 0) + 1
    with get_connection() as conn:
        cursor = conn.execute(
            """
            INSERT INTO repo_scan_templates
                (repo_id, template_version, status, content_json, summary_cn, confidence,
                 source_ai_config_id, created_at, updated_at, notes)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                repo_id,
                version,
                status,
                _json_dumps(content),
                content.get("summary_cn"),
                int(content.get("confidence") or 60),
                source_ai_config_id,
                now,
                now,
                notes,
            ),
        )
        template_id = int(cursor.lastrowid)
    return get_template(template_id) or {}


async def generate_template_from_scan(
    repo: Dict[str, Any],
    documents: Sequence[Dict[str, str]],
    record: Dict[str, Any],
    ai_config_id: Optional[int] = None,
) -> Dict[str, Any]:
    file_profiles = build_file_profiles(documents, repo.get("category") or "")
    messages = [
        {"role": "system", "content": REPO_TEMPLATE_SYSTEM_PROMPT},
        {
            "role": "user",
            "content": REPO_TEMPLATE_USER_PROMPT.format(
                repo_summary=_repo_summary(repo, documents),
                file_profiles=_file_profiles_summary(file_profiles),
                baseline_summary=_baseline_summary(record),
            ),
        },
    ]
    result = await chat_completion(messages, ai_config_id=ai_config_id, temperature=0.1, max_tokens=1600)
    content = validate_template_content(_extract_json_object(result["content"]))
    return create_template_record(
        int(repo["id"]),
        content,
        source_ai_config_id=ai_config_id or (result.get("config") or {}).get("id"),
        status="pending_review",
        notes="AI 生成，等待人工批准后成为 active 模板。",
    )


def update_template(template_id: int, payload: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    existing = get_template(template_id)
    if not existing:
        return None
    status = payload.get("status") or existing["status"]
    if status not in {"pending_review", "active", "rejected", "archived"}:
        raise ValueError("模板状态无效")
    content_json = payload.get("content_json") or existing["content_json"]
    try:
        content = validate_template_content(json.loads(content_json))
    except Exception as exc:
        raise ValueError("content_json 必须是合法模板 JSON") from exc
    now = utc_now()
    with get_connection() as conn:
        conn.execute(
            """
            UPDATE repo_scan_templates
            SET status = ?, content_json = ?, summary_cn = ?, confidence = ?, notes = ?, updated_at = ?
            WHERE id = ?
            """,
            (
                status,
                _json_dumps(content),
                payload.get("summary_cn") or content.get("summary_cn"),
                int(payload.get("confidence") if payload.get("confidence") is not None else content.get("confidence") or 60),
                payload.get("notes") if payload.get("notes") is not None else existing.get("notes"),
                now,
                template_id,
            ),
        )
    return get_template(template_id)


def approve_template(template_id: int) -> Optional[Dict[str, Any]]:
    existing = get_template(template_id)
    if not existing:
        return None
    now = utc_now()
    with get_connection() as conn:
        conn.execute(
            "UPDATE repo_scan_templates SET status = 'archived', updated_at = ? WHERE repo_id = ? AND status = 'active' AND id != ?",
            (now, existing["repo_id"], template_id),
        )
        conn.execute(
            "UPDATE repo_scan_templates SET status = 'active', approved_at = ?, updated_at = ? WHERE id = ?",
            (now, now, template_id),
        )
    return get_template(template_id)


def reject_template(template_id: int) -> Optional[Dict[str, Any]]:
    existing = get_template(template_id)
    if not existing:
        return None
    now = utc_now()
    with get_connection() as conn:
        conn.execute("UPDATE repo_scan_templates SET status = 'rejected', updated_at = ? WHERE id = ?", (now, template_id))
    return get_template(template_id)
