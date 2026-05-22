from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import PurePosixPath
from typing import Any, Callable, Dict, Iterable, List, Optional, Sequence

from database import utc_now
from services.ai_config_service import chat_completion
from utils.image_utils import download_image, extract_markdown_image_urls


BAD_IMAGE_HINTS = ("badge", "logo", "icon", "avatar", "sponsor", "shields", "license", "build", "version", "workflow")
COMPONENT_LIBRARY_HINTS = (
    "component library",
    "ui component library",
    "ui kit",
    "registry",
    "shadcn",
    "design system",
    "blocks",
    "components for ai applications",
    "high-quality components",
    "customizable components",
)
DESIGN_SPEC_HINTS = (
    "design system",
    "design guidelines",
    "design rule",
    "style guide",
    "spacing",
    "typography",
    "layout",
    "grid",
    "design tokens",
    "visual hierarchy",
    "interaction guideline",
)
FRAMEWORK_HINTS: Sequence[tuple[str, tuple[str, ...]]] = (
    ("React", ("react", "jsx", "tsx")),
    ("Next.js", ("next.js", "nextjs", "app router")),
    ("Tailwind CSS", ("tailwind", "tailwindcss")),
    ("shadcn/ui", ("shadcn", "components.json", "registry")),
    ("Radix UI", ("radix", "@radix-ui")),
    ("Framer Motion", ("framer motion", "motion")),
    ("Vue", ("vue", "nuxt")),
    ("Svelte", ("svelte", "sveltekit")),
)
COMPONENT_FOCUS_HINTS: Sequence[tuple[str, tuple[str, ...]]] = (
    ("chat", ("chat", "message", "conversation", "assistant")),
    ("agent", ("agent", "tool", "reasoning", "steps", "source")),
    ("form", ("form", "input", "textarea", "upload")),
    ("navbar", ("navbar", "navigation", "nav bar")),
    ("sidebar", ("sidebar", "side nav")),
    ("card", ("card", "cards")),
    ("table", ("table", "data table")),
    ("dashboard", ("dashboard", "analytics")),
    ("modal", ("modal", "dialog", "drawer")),
    ("auth", ("login", "sign in", "auth")),
)
STYLE_HINTS: Sequence[tuple[str, tuple[str, ...]]] = (
    ("高级暗色", ("dark", "dark mode", "midnight", "slate")),
    ("AI 工具风", ("ai application", "agent", "assistant", "workspace")),
    ("极简", ("minimal", "clean", "simple")),
    ("玻璃质感", ("glass", "glassmorphism", "frosted")),
    ("SaaS", ("saas", "b2b", "workspace")),
    ("动效增强", ("motion", "animation", "transition")),
)
FRONTEND_TARGET_HINTS: Sequence[tuple[str, tuple[str, ...]]] = (
    ("AI 聊天应用", ("chat", "conversation", "message", "prompt input")),
    ("Agent 工作台", ("agent", "tool", "reasoning", "source", "steps")),
    ("SaaS 仪表盘", ("dashboard", "analytics", "workspace")),
    ("Landing Page", ("landing", "hero", "marketing", "pricing")),
    ("管理后台", ("admin", "settings", "data table")),
    ("设计系统", ("design system", "registry", "ui kit")),
)


@dataclass(frozen=True)
class WebUiRepoProfileCandidate:
    profile_type: str
    library_kind: str
    ui_stack: str
    supported_frontend_types: List[str]
    component_focus: List[str]
    style_keywords: List[str]
    reuse_mode: str
    summary_cn: str
    ai_summary_cn: str
    evidence: str
    ai_reason_cn: str
    confidence: int
    source_ai_config_id: Optional[int]
    screenshot_original_url: str


def _contains_any(text: str, hints: Iterable[str]) -> bool:
    lower = (text or "").lower()
    return any(hint.lower() in lower for hint in hints)


def _pick_many(text: str, hint_groups: Sequence[tuple[str, tuple[str, ...]]], limit: int = 6) -> List[str]:
    result: List[str] = []
    for label, hints in hint_groups:
        if _contains_any(text, hints) and label not in result:
            result.append(label)
        if len(result) >= limit:
            break
    return result


def _json_dumps(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False)


def _extract_json_object(text: str) -> Dict[str, Any]:
    cleaned = (text or "").strip()
    if cleaned.startswith("```"):
        cleaned = re.sub(r"^```(?:json)?\s*", "", cleaned, flags=re.IGNORECASE)
        cleaned = re.sub(r"\s*```$", "", cleaned)
    try:
        payload = json.loads(cleaned)
        return payload if isinstance(payload, dict) else {}
    except Exception:
        pass
    match = re.search(r"\{.*\}", cleaned, flags=re.DOTALL)
    if not match:
        return {}
    try:
        payload = json.loads(match.group(0))
    except Exception:
        return {}
    return payload if isinstance(payload, dict) else {}


def _clean_sentence(text: str, max_len: int = 260) -> str:
    value = re.sub(r"\s+", " ", (text or "").strip())
    return value[:max_len].strip()


def _path_probe(documents: Sequence[Dict[str, str]]) -> str:
    return " ".join((doc.get("path") or "").lower() for doc in documents)


def _repo_probe(repo_name: str, readme: str, documents: Sequence[Dict[str, str]]) -> str:
    return f"{repo_name}\n{readme[:12000]}\n{_path_probe(documents)}"


def _infer_profile_type(probe: str) -> str:
    component_score = 0
    if _contains_any(probe, COMPONENT_LIBRARY_HINTS):
        component_score += 2
    if _contains_any(probe, ("components/", "registry/", "blocks/", "components.json", "ui kit")):
        component_score += 2
    if _contains_any(probe, ("install", "usage", "import", "npx shadcn")):
        component_score += 1

    design_score = 0
    if _contains_any(probe, DESIGN_SPEC_HINTS):
        design_score += 2
    if _contains_any(probe, ("tokens/", "guidelines/", "patterns/", "style guide")):
        design_score += 2

    return "component_library" if component_score >= design_score else "design_spec"


def _infer_library_kind(probe: str) -> str:
    lower = probe.lower()
    if "shadcn" in lower or "components.json" in lower or "registry" in lower:
        return "shadcn_registry"
    if "design system" in lower:
        return "design_system_library"
    if "blocks" in lower:
        return "blocks_library"
    return "component_collection"


def _infer_ui_stack(probe: str) -> str:
    found = [label for label, hints in FRAMEWORK_HINTS if _contains_any(probe, hints)]
    return " + ".join(found[:4])


def _find_preview_image(readme: str, documents: Sequence[Dict[str, str]]) -> str:
    candidates: List[str] = []
    for document in documents:
        path = (document.get("path") or "").lower()
        base_url = document.get("raw_base_url") or ""
        if path == "readme.md":
            candidates.extend(extract_markdown_image_urls(document.get("content") or "", base_url=base_url))
    if not candidates:
        base_url = ""
        if documents:
            base_url = documents[0].get("raw_base_url") or ""
        candidates.extend(extract_markdown_image_urls(readme, base_url=base_url))
    for url in candidates:
        if not _contains_any(url, BAD_IMAGE_HINTS):
            return url
    return ""


def _readme_summary(readme: str, fallback: str) -> str:
    text = re.sub(r"```.*?```", " ", readme or "", flags=re.DOTALL)
    text = re.sub(r"!\[[^\]]*\]\([^)]+\)", " ", text)
    parts = [re.sub(r"\s+", " ", part).strip() for part in re.split(r"\n\s*\n", text)]
    for part in parts:
        clean = part.strip("#>-* ").strip()
        lower = clean.lower()
        if len(clean) < 36 or len(clean) > 240:
            continue
        if lower.startswith(("npm ", "npx ", "pnpm ", "yarn ", "import ", "export ", "git clone")):
            continue
        if _contains_any(lower, ("installation", "usage", "getting started", "quickstart")):
            continue
        return clean
    return fallback


def _fallback_frontend_targets(profile_type: str, probe: str) -> List[str]:
    targets = _pick_many(probe, FRONTEND_TARGET_HINTS, limit=5)
    if targets:
        return targets
    if profile_type == "component_library":
        return ["网站前端界面", "AI 聊天应用", "SaaS 仪表盘"]
    return ["前端设计规范", "设计系统", "网站界面约束"]


async def _ai_enrich_profile(
    *,
    repo_name: str,
    repo_url: str,
    profile_type: str,
    library_kind: str,
    ui_stack: str,
    component_focus: List[str],
    style_keywords: List[str],
    fallback_summary: str,
    readme: str,
    documents: Sequence[Dict[str, str]],
    ai_config_id: Optional[int],
) -> Dict[str, Any]:
    payload = {
        "task": "分析前端组件仓库适合开发什么前端",
        "repo": {
            "name": repo_name,
            "url": repo_url,
            "profile_type": profile_type,
            "library_kind": library_kind,
            "ui_stack": ui_stack,
            "component_focus": component_focus,
            "style_keywords": style_keywords,
            "readme_excerpt": readme[:8000],
            "top_paths": [doc.get("path") for doc in documents[:40]],
            "fallback_summary": fallback_summary,
        },
        "required_output_schema": {
            "summary_cn": "一句中文总结",
            "frontend_targets": ["适合开发什么前端，3到6项中文短语"],
            "reuse_mode": "可直接接入|参考改造|风格参考",
            "style_keywords": ["4到6个中文风格词"],
            "reason_cn": "为什么适合这些前端",
            "confidence": "0-100 integer",
        },
    }
    result = await chat_completion(
        [
            {
                "role": "system",
                "content": "你是前端组件仓库标注助手。只返回 JSON，不要 Markdown。不要解释代码实现，只判断这个仓库适合用来开发什么前端。",
            },
            {"role": "user", "content": _json_dumps(payload)},
        ],
        ai_config_id=ai_config_id,
        temperature=0.1,
        max_tokens=900,
    )
    content = _extract_json_object(result.get("content") or "")
    return {
        "summary_cn": _clean_sentence(str(content.get("summary_cn") or fallback_summary)),
        "frontend_targets": [str(item).strip() for item in (content.get("frontend_targets") or []) if str(item).strip()][:6],
        "reuse_mode": _clean_sentence(str(content.get("reuse_mode") or ""))[:40],
        "style_keywords": [str(item).strip() for item in (content.get("style_keywords") or []) if str(item).strip()][:6],
        "reason_cn": _clean_sentence(str(content.get("reason_cn") or "")),
        "confidence": max(0, min(int(content.get("confidence") or 75), 100)),
        "source_ai_config_id": (result.get("config") or {}).get("id"),
    }


async def build_web_ui_repo_profile(
    *,
    repo_name: str,
    repo_url: str,
    readme: str,
    documents: Sequence[Dict[str, str]],
    ai_config_id: Optional[int] = None,
    progress_callback: Optional[Callable[[Dict[str, Any]], None]] = None,
) -> WebUiRepoProfileCandidate:
    probe = _repo_probe(repo_name, readme, documents)
    profile_type = _infer_profile_type(probe)
    library_kind = _infer_library_kind(probe) if profile_type == "component_library" else ""
    ui_stack = _infer_ui_stack(probe)
    component_focus = _pick_many(probe, COMPONENT_FOCUS_HINTS, limit=6)
    style_keywords = _pick_many(probe, STYLE_HINTS, limit=6)
    screenshot_original_url = _find_preview_image(readme, documents)
    fallback_summary = _readme_summary(
        readme,
        f"{repo_name} 是一个面向网站前端的{'组件库' if profile_type == 'component_library' else '设计规范'}仓库。",
    )
    summary_cn = fallback_summary
    ai_summary_cn = ""
    ai_reason_cn = ""
    reuse_mode = "参考改造"
    supported_frontend_types = _fallback_frontend_targets(profile_type, probe)
    confidence = 72 if profile_type == "component_library" else 68
    source_ai_config_id: Optional[int] = None

    if progress_callback:
        progress_callback({"current_file": "README.md", "phase": "web_ui_repo_profile_rules"})

    if profile_type == "component_library":
        try:
            if progress_callback:
                progress_callback({"current_file": "AI 标注组件库适用前端", "phase": "web_ui_repo_profile_ai"})
            ai_result = await _ai_enrich_profile(
                repo_name=repo_name,
                repo_url=repo_url,
                profile_type=profile_type,
                library_kind=library_kind,
                ui_stack=ui_stack,
                component_focus=component_focus,
                style_keywords=style_keywords,
                fallback_summary=fallback_summary,
                readme=readme,
                documents=documents,
                ai_config_id=ai_config_id,
            )
            if ai_result.get("summary_cn"):
                ai_summary_cn = ai_result["summary_cn"]
                summary_cn = ai_result["summary_cn"]
            if ai_result.get("frontend_targets"):
                supported_frontend_types = ai_result["frontend_targets"]
            if ai_result.get("reuse_mode"):
                reuse_mode = ai_result["reuse_mode"]
            if ai_result.get("style_keywords"):
                style_keywords = ai_result["style_keywords"]
            ai_reason_cn = ai_result.get("reason_cn") or ""
            confidence = ai_result.get("confidence") or confidence
            source_ai_config_id = ai_result.get("source_ai_config_id")
        except Exception as exc:
            ai_reason_cn = f"AI 标注失败，已回退规则判断：{str(exc)[:300]}"

    evidence = (
        f"仓库级扫描：基于 README、根目录结构与技术栈判断其属于{'组件库' if profile_type == 'component_library' else '设计规范'}；"
        f"技术栈 {ui_stack or '未明确'}；组件焦点 {', '.join(component_focus) if component_focus else '未明确'}。"
    )
    return WebUiRepoProfileCandidate(
        profile_type=profile_type,
        library_kind=library_kind,
        ui_stack=ui_stack,
        supported_frontend_types=supported_frontend_types,
        component_focus=component_focus,
        style_keywords=style_keywords,
        reuse_mode=reuse_mode,
        summary_cn=summary_cn,
        ai_summary_cn=ai_summary_cn,
        evidence=evidence,
        ai_reason_cn=ai_reason_cn,
        confidence=confidence,
        source_ai_config_id=source_ai_config_id,
        screenshot_original_url=screenshot_original_url,
    )


async def save_web_ui_repo_profile(
    conn,
    repo_id: int,
    repo_name: str,
    repo_url: str,
    profile: WebUiRepoProfileCandidate,
    progress_callback: Optional[Callable[[Dict[str, Any]], None]] = None,
) -> Dict[str, Any]:
    now = utc_now()
    screenshot_local_path = ""
    screenshot_hash = ""
    screenshots_added = 0

    if profile.screenshot_original_url:
        if progress_callback:
            progress_callback({"current_file": "README 预览图", "phase": "download_web_ui_repo_screenshot"})
        downloaded = await download_image(profile.screenshot_original_url)
        if downloaded:
            asset_row = conn.execute("SELECT * FROM assets WHERE image_hash = ?", (downloaded["image_hash"],)).fetchone()
            if asset_row:
                screenshot_local_path = asset_row["image_local_path"]
                screenshot_hash = asset_row["image_hash"]
            else:
                conn.execute(
                    """
                    INSERT OR IGNORE INTO assets
                        (repo_id, image_original_url, image_local_path, thumbnail_local_path, image_hash, source_page_url,
                         asset_type, width, height, file_size, description, commercial_risk, created_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        repo_id,
                        profile.screenshot_original_url,
                        downloaded["image_local_path"],
                        downloaded["thumbnail_local_path"],
                        downloaded["image_hash"],
                        repo_url,
                        "web_ui_repo_screenshot",
                        downloaded["width"],
                        downloaded["height"],
                        downloaded["file_size"],
                        f"Web UI 仓库截图：{repo_name}",
                        "unknown",
                        now,
                    ),
                )
                screenshot_local_path = downloaded["image_local_path"]
                screenshot_hash = downloaded["image_hash"]
                screenshots_added += 1
                if progress_callback:
                    progress_callback({"downloaded_images_delta": 1, "images_added": screenshots_added})
        elif progress_callback:
            progress_callback({"error_count_delta": 1})

    existing = conn.execute("SELECT * FROM web_ui_repo_profiles WHERE repo_id = ?", (repo_id,)).fetchone()
    payload = {
        "repo_name": repo_name,
        "repo_url": repo_url,
        "profile_type": profile.profile_type,
        "library_kind": profile.library_kind,
        "ui_stack": profile.ui_stack,
        "supported_frontend_types_json": _json_dumps(profile.supported_frontend_types),
        "component_focus_json": _json_dumps(profile.component_focus),
        "style_keywords_json": _json_dumps(profile.style_keywords),
        "reuse_mode": profile.reuse_mode,
        "summary_cn": profile.summary_cn,
        "ai_summary_cn": profile.ai_summary_cn,
        "evidence": profile.evidence,
        "ai_reason_cn": profile.ai_reason_cn,
        "confidence": profile.confidence,
        "source_ai_config_id": profile.source_ai_config_id,
        "screenshot_original_url": profile.screenshot_original_url,
        "screenshot_local_path": screenshot_local_path,
        "screenshot_hash": screenshot_hash,
        "last_scanned_at": now,
        "updated_at": now,
    }

    if existing:
        manual_fields = {"quality_level", "selection_status", "commercial_risk", "notes"}
        merged = dict(payload)
        for field in manual_fields:
            merged[field] = existing[field]
        assignments = ", ".join(f"{key} = ?" for key in merged)
        conn.execute(f"UPDATE web_ui_repo_profiles SET {assignments} WHERE repo_id = ?", (*merged.values(), repo_id))
        return {"action": "updated", "screenshots_added": screenshots_added, "profile_type": profile.profile_type}

    conn.execute(
        """
        INSERT INTO web_ui_repo_profiles
            (repo_id, repo_name, repo_url, profile_type, library_kind, ui_stack, supported_frontend_types_json,
             component_focus_json, style_keywords_json, reuse_mode, summary_cn, ai_summary_cn, evidence, ai_reason_cn,
             confidence, source_ai_config_id, screenshot_original_url, screenshot_local_path, screenshot_hash,
             quality_level, selection_status, commercial_risk, last_scanned_at, created_at, updated_at, notes)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            repo_id,
            repo_name,
            repo_url,
            profile.profile_type,
            profile.library_kind,
            profile.ui_stack,
            _json_dumps(profile.supported_frontend_types),
            _json_dumps(profile.component_focus),
            _json_dumps(profile.style_keywords),
            profile.reuse_mode,
            profile.summary_cn,
            profile.ai_summary_cn,
            profile.evidence,
            profile.ai_reason_cn,
            profile.confidence,
            profile.source_ai_config_id,
            profile.screenshot_original_url,
            screenshot_local_path,
            screenshot_hash,
            "pending_review",
            "pending_review",
            "unknown",
            now,
            now,
            now,
            "",
        ),
    )
    return {"action": "added", "screenshots_added": screenshots_added, "profile_type": profile.profile_type}
