from __future__ import annotations

import re
from datetime import datetime, timezone
from typing import Any, Dict, List, Tuple

from services.dedup_service import looks_like_forbidden_resource
from services.prompt_service import extract_prompt_candidates
from utils.image_utils import extract_markdown_image_urls


TARGET_HINTS: Dict[str, Tuple[str, ...]] = {
    "web_ui_prompt": (
        "web ui",
        "website ui",
        "frontend",
        "landing page",
        "dashboard ui",
        "ui prompt",
        "component prompt",
        "page prompt",
        "ui prompt library",
        "prompt examples",
        "react",
        "next.js",
        "nextjs",
        "framer motion",
        "shadcn",
        "tailwind",
        "hero section",
        "navbar",
        "pricing",
        "design system",
        "design tokens",
        "figma",
    ),
    "image_generation_prompt": (
        "image generation",
        "text to image",
        "ai image",
        "gpt image",
        "product image",
        "poster",
        "photography",
        "visual design",
        "prompt examples",
        "generated images",
        "effect examples",
    ),
    "skill_repository": (
        "ai skill",
        "agent skill",
        "claude skill",
        "chatgpt skill",
        "codex skill",
        "desktop ai skill",
        "mcp tool",
        "mcp server",
        "model context protocol",
        "agent tools",
        "tool calling",
        "llm tool",
        "llm agent toolkit",
        "ai workflow",
        "prompt workflow",
        "cursor rules",
        "claude code skill",
        ".cursor/rules",
        ".claude",
        "skill.json",
        "manifest",
        "tools/",
        "skills/",
    ),
    "video_generation_prompt": (
        "text to video",
        "image to video",
        "video generation",
        "video prompt",
        "cinematic",
        "storyboard",
        "short film",
        "camera movement",
        "product video",
        "runway",
        "veo3",
        "kling",
        "pika",
        "luma",
        "hailuo",
        "veo",
        "seedance",
        "wan",
    ),
}

PROMPT_SIGNAL_RE = re.compile(
    r"\b(prompt|positive prompt|negative prompt|image prompt|video prompt|text to image|text to video|image to image|copy this prompt|prompt template)\b|提示词|正向提示词|反向提示词|图像提示词|视频提示词",
    re.IGNORECASE,
)
SKILL_SIGNAL_RE = re.compile(
    r"\b(ai skill|agent skill|claude skill|chatgpt skill|codex skill|desktop ai skill|mcp tool|mcp server|model context protocol|agent tools|tool calling|llm tool|llm agent toolkit|ai workflow|prompt workflow|cursor rules|claude code skill|skill\.json|manifest|tools?|workflow|playbook)\b",
    re.IGNORECASE,
)
FENCED_PROMPT_RE = re.compile(r"```(?:prompt|text|txt)?\s*\n.{40,2500}?```", re.IGNORECASE | re.DOTALL)
LINK_RE = re.compile(r"\[[^\]]+\]\([^)]+\)|https?://", re.IGNORECASE)
TABLE_RE = re.compile(r"(?m)^\s*\|.+\|\s*$")
AD_HINT_RE = re.compile(r"\b(sponsor|buy now|coupon|discount|affiliate|promo|advertis(e|ing)|sale)\b|广告|推广|优惠券|返利", re.IGNORECASE)
REUSABLE_HINT_RE = re.compile(
    r"\b(template|examples?|collection|library|dataset|json|jsonl|csv|yaml|workflow|cookbook|guide|component|pattern|rule|toolkit|server|skill)\b|模板|案例|示例|合集|数据集|工作流|规范|工具",
    re.IGNORECASE,
)

WEB_UI_FRONTEND_HINTS = ("react", "next.js", "nextjs", "tailwind", "tailwind css", "shadcn", "framer motion", "html", "css", "typescript", "tsx", "jsx")
WEB_UI_WEBSITE_HINTS = (
    "website ui",
    "web ui",
    "landing page",
    "hero section",
    "navbar",
    "sidebar",
    "pricing",
    "dashboard ui",
    "component prompt",
    "page prompt",
    "ui prompt",
    "design system",
    "design tokens",
    "responsive layout",
)
WEB_UI_ASSET_HINTS = ("prompt library", "ui prompt library", "prompt examples", "prompt templates", "component prompt", "page prompt", "design system", "components/", "templates/", "examples/", "patterns/")
WEB_UI_NEGATIVE_HINTS = (
    "comfyui",
    "stable diffusion",
    "automatic1111",
    "a1111",
    "sd-webui",
    "sampler",
    "checkpoint",
    "vae",
    "lora",
    "prompt manager",
    "workflow tool",
    "workflow ui",
    "workflow node",
    "add node",
    "canvas",
    "promptserver",
    "dashboard viewer",
    "builder ui",
    "custom node",
    "plugin ui",
    "extension ui",
    "dashboard_html",
    "inpaint",
    "outpaint",
    "text to image",
    "image generation",
    "video generation",
)
SKILL_NEGATIVE_HINTS = (
    "midjourney",
    "stable diffusion model",
    "model weights",
    "checkpoint",
    "dataset",
    "paper list",
    "ui template",
    "landing page",
    "image prompt",
    "video prompt",
    "wormgpt",
)


def _topic_text(item: Dict[str, Any]) -> str:
    topics = item.get("topics") or []
    if isinstance(topics, list):
        return " ".join(str(topic) for topic in topics)
    return str(topics)


def _combined_text(item: Dict[str, Any], readme: str) -> str:
    return " ".join(
        part
        for part in (
            item.get("full_name") or item.get("name") or "",
            item.get("description") or "",
            _topic_text(item),
            readme or "",
        )
        if part
    )


def _count_unique_hints(text: str, hints: Tuple[str, ...]) -> int:
    lower = text.lower()
    return sum(1 for hint in hints if hint.lower() in lower)


def _web_ui_signal_counts(combined: str) -> Dict[str, int]:
    return {
        "frontend": _count_unique_hints(combined, WEB_UI_FRONTEND_HINTS),
        "website": _count_unique_hints(combined, WEB_UI_WEBSITE_HINTS),
        "asset": _count_unique_hints(combined, WEB_UI_ASSET_HINTS),
        "negative": _count_unique_hints(combined, WEB_UI_NEGATIVE_HINTS),
    }


def _is_recent_enough(pushed_at: str | None, days: int) -> bool:
    if not pushed_at:
        return False
    try:
        pushed = datetime.fromisoformat(pushed_at.replace("Z", "+00:00"))
    except ValueError:
        return False
    return (datetime.now(timezone.utc) - pushed).days <= days


def _hard_exclusion_reason(item: Dict[str, Any], readme: str, combined: str) -> str | None:
    name = item.get("full_name") or item.get("name") or ""
    description = item.get("description") or ""
    if item.get("archived") or item.get("disabled"):
        return "仓库已归档或不可用"
    if item.get("fork"):
        return "Fork 仓库默认不作为独立资源保存"
    if looks_like_forbidden_resource(name, f"{description} {readme[:12000]}"):
        return "命中禁止整理关键词"

    category = item.get("_discovery_category") or ""
    prompt_hits = len(PROMPT_SIGNAL_RE.findall(combined))
    skill_hits = len(SKILL_SIGNAL_RE.findall(combined))
    target_hits = sum(_count_unique_hints(combined, hints) for hints in TARGET_HINTS.values())
    readme_len = len(readme or "")
    if readme_len < 160 and prompt_hits == 0 and skill_hits == 0 and target_hits < 2:
        return "README 缺失或过短，且仓库名/描述缺少目标方向证据"

    link_count = len(LINK_RE.findall(readme or ""))
    prompt_candidates = extract_prompt_candidates(readme or "", limit=5)
    image_count = len(extract_markdown_image_urls(readme or "", base_url=""))
    if link_count >= 12 and not prompt_candidates and skill_hits == 0 and image_count == 0 and prompt_hits <= 2:
        return "README 更像链接集合，缺少可复用内容证据"

    ad_hits = len(AD_HINT_RE.findall(combined[:12000]))
    if ad_hits >= 3 and prompt_hits <= 1 and skill_hits <= 1:
        return "内容更像广告/推广仓库，缺少实际资源内容"

    lower = combined.lower()
    if category == "web_ui_prompt":
        web_ui_signals = _web_ui_signal_counts(combined)
        if "wormgpt" in lower:
            return "更像危险或越界工具仓库，不属于网站前端设计资产"
        if any(term in lower for term in ("comfyui", "automatic1111", "a1111", "stable diffusion", "sd-webui")) and (
            web_ui_signals["asset"] < 2 or web_ui_signals["frontend"] < 3
        ):
            return "更像图像工作流/模型工具仓库，不属于网站前端设计资产"
        if ("prompt manager" in lower or "prompt management system" in lower) and web_ui_signals["asset"] < 2:
            return "更像 Prompt 管理工具仓库，不是网站前端设计资产仓库"
        if web_ui_signals["negative"] >= 2 and web_ui_signals["frontend"] < 2 and web_ui_signals["website"] < 3:
            return "更像工具工作流 UI 面板仓库，不是网站前端设计资产"
    if category == "skill_repository":
        if any(term in lower for term in ("wormgpt", "malware", "exploit", "phishing")):
            return "命中高风险或越界工具线索，不作为 Skill 资产收集"
        if any(term in lower for term in ("model weights", "checkpoint", "dataset")) and skill_hits < 2:
            return "更像模型/数据集仓库，缺少 Skill 或工具工作流证据"
        if any(term in lower for term in ("landing page", "ui template", "portfolio template")) and skill_hits < 2:
            return "更像前端模板仓库，缺少 Skill 能力包证据"
    return None


def _score_prompt_density(readme: str, combined: str) -> Tuple[int, List[str]]:
    reasons: List[str] = []
    prompt_candidates = extract_prompt_candidates(readme or "", limit=80)
    prompt_signal_hits = len(PROMPT_SIGNAL_RE.findall(readme or combined))
    fenced_hits = len(FENCED_PROMPT_RE.findall(readme or ""))
    table_prompt_hits = sum(1 for line in TABLE_RE.findall(readme or "") if "prompt" in line.lower() or "提示词" in line)
    score = min(35, len(prompt_candidates) * 7 + min(prompt_signal_hits, 12) * 2 + min(fenced_hits, 4) * 4 + min(table_prompt_hits, 5) * 2)
    if prompt_candidates:
        reasons.append(f"识别到 {len(prompt_candidates)} 条 README Prompt 候选")
    elif prompt_signal_hits:
        reasons.append(f"识别到 {prompt_signal_hits} 处 Prompt 关键词")
    if fenced_hits:
        reasons.append(f"识别到 {fenced_hits} 个疑似 Prompt 代码块")
    if table_prompt_hits:
        reasons.append(f"识别到 {table_prompt_hits} 行疑似 Prompt 表格")
    return score, reasons


def _score_skill_density(readme: str, combined: str) -> Tuple[int, List[str]]:
    reasons: List[str] = []
    skill_hits = len(SKILL_SIGNAL_RE.findall(readme or combined))
    path_hits = len(re.findall(r"\b(tools/|skills/|servers/|scripts/|\.cursor/rules|\.claude|skill\.json|mcp\.json)\b", combined, re.IGNORECASE))
    config_hits = len(re.findall(r"\b(package\.json|pyproject\.toml|requirements\.txt|dockerfile|manifest|schema)\b", combined, re.IGNORECASE))
    score = min(35, min(skill_hits, 12) * 3 + min(path_hits, 8) * 3 + min(config_hits, 6) * 2)
    if skill_hits:
        reasons.append(f"识别到 {skill_hits} 个 Skill/Agent/MCP 能力线索")
    if path_hits:
        reasons.append(f"识别到 {path_hits} 个工具或 Skill 目录/配置线索")
    if config_hits:
        reasons.append(f"识别到 {config_hits} 个运行配置线索")
    return score, reasons


def _score_target_relevance(category: str, keyword: str, combined: str) -> Tuple[int, List[str]]:
    hints = TARGET_HINTS.get(category, ())
    hint_hits = _count_unique_hints(combined, hints)
    keyword_tokens = [token for token in re.split(r"[^a-zA-Z0-9\u4e00-\u9fff]+", keyword.lower()) if len(token) >= 2]
    keyword_hits = sum(1 for token in keyword_tokens if token in combined.lower())
    reasons: List[str] = []
    if category == "web_ui_prompt":
        web_ui_signals = _web_ui_signal_counts(combined)
        score = min(
            25,
            web_ui_signals["frontend"] * 5
            + web_ui_signals["website"] * 4
            + min(web_ui_signals["asset"], 3) * 3
            + min(keyword_hits, 4) * 2
            - min(web_ui_signals["negative"], 3) * 4,
        )
        if web_ui_signals["frontend"]:
            reasons.append(f"命中 {web_ui_signals['frontend']} 个前端技术栈线索")
        if web_ui_signals["website"]:
            reasons.append(f"命中 {web_ui_signals['website']} 个网站 UI 资产线索")
        if web_ui_signals["asset"]:
            reasons.append(f"命中 {web_ui_signals['asset']} 个资产组织线索")
        if web_ui_signals["negative"]:
            reasons.append(f"命中 {web_ui_signals['negative']} 个非网站 UI 负面线索")
    elif category == "skill_repository":
        negative_hits = _count_unique_hints(combined, SKILL_NEGATIVE_HINTS)
        score = min(25, hint_hits * 4 + min(keyword_hits, 4) * 2 - min(negative_hits, 4) * 3)
        score = max(0, score)
        if hint_hits:
            reasons.append(f"命中 {hint_hits} 个 Skill/Agent/MCP 方向关键词")
        if negative_hits:
            reasons.append(f"命中 {negative_hits} 个非 Skill 资产负面线索")
    else:
        score = min(25, hint_hits * 4 + min(keyword_hits, 4) * 2)
        if hint_hits:
            reasons.append(f"与 {category} 命中 {hint_hits} 个方向关键词")
    if keyword_hits:
        reasons.append(f"与搜索词命中 {keyword_hits} 个词片段")
    return score, reasons


def _score_evidence_quality(category: str, readme: str) -> Tuple[int, List[str]]:
    reasons: List[str] = []
    image_count = len(extract_markdown_image_urls(readme or "", base_url=""))
    table_count = len(TABLE_RE.findall(readme or ""))
    section_hits = len(re.findall(r"\b(example|examples|demo|showcase|gallery|result|output|case|video)\b", readme or "", re.IGNORECASE))
    video_count = len(re.findall(r"https?://[^\s<>()]+(?:\.mp4|\.mov|\.webm|\.m4v|\.avi)\b|github\.com/user-attachments/assets/", readme or "", re.IGNORECASE))
    if category == "skill_repository":
        config_count = len(re.findall(r"\b(package\.json|pyproject\.toml|requirements\.txt|dockerfile|manifest|skill\.json|mcp\.json)\b", readme or "", re.IGNORECASE))
        tool_section_count = len(re.findall(r"\b(install|configuration|usage|tools?|capabilities|workflow|examples?)\b", readme or "", re.IGNORECASE))
        score = min(20, min(config_count, 5) * 3 + min(tool_section_count, 8) * 2 + min(table_count, 4))
        if config_count:
            reasons.append(f"README 包含 {config_count} 个运行/配置证据")
        if tool_section_count:
            reasons.append(f"README 包含 {tool_section_count} 个安装/能力/用法章节线索")
    elif category == "video_generation_prompt":
        score = min(20, min(video_count, 5) * 4 + min(table_count, 4) * 2 + min(section_hits, 5) * 2)
        if video_count:
            reasons.append(f"README 包含 {video_count} 个视频证据")
    else:
        score = min(20, min(image_count, 5) * 3 + min(table_count, 4) * 2 + min(section_hits, 5))
        if image_count:
            reasons.append(f"README 包含 {image_count} 张图片")
    if table_count:
        reasons.append(f"README 包含 {table_count} 行表格")
    if section_hits:
        reasons.append(f"README 包含 {section_hits} 个示例/输出章节线索")
    return score, reasons


def _score_reusable_value(combined: str) -> Tuple[int, List[str]]:
    hits = len(REUSABLE_HINT_RE.findall(combined))
    score = min(10, hits * 2)
    if hits:
        return score, [f"识别到 {hits} 个模板/案例/工具/结构化复用线索"]
    return 0, []


def _score_repo_health(item: Dict[str, Any]) -> Tuple[int, List[str]]:
    reasons: List[str] = []
    stars = int(item.get("stargazers_count") or 0)
    license_info = item.get("license") or {}
    license_value = license_info.get("spdx_id") if isinstance(license_info, dict) else None
    score = 0
    if stars >= 500:
        score += 4
    elif stars >= 100:
        score += 3
    elif stars >= 10:
        score += 2
    elif stars >= 1:
        score += 1
    if stars:
        reasons.append(f"仓库有 {stars} stars，Star 只作为轻量加分")
    if _is_recent_enough(item.get("pushed_at"), 90):
        score += 4
        reasons.append("最近 90 天内更新")
    elif _is_recent_enough(item.get("pushed_at"), 365):
        score += 2
        reasons.append("最近一年内更新")
    if license_value and license_value.upper() not in {"NOASSERTION", "UNKNOWN"}:
        score += 2
        reasons.append(f"GitHub License: {license_value}")
    return min(10, score), reasons


def evaluate_repo_discovery_candidate(item: Dict[str, Any], keyword: str, category: str, readme: str) -> Dict[str, Any]:
    combined = _combined_text(item, readme)
    item_with_category = dict(item)
    item_with_category["_discovery_category"] = category
    hard_reason = _hard_exclusion_reason(item_with_category, readme, combined)
    if hard_reason:
        return {
            "decision": "skip",
            "score": 0,
            "status": "skipped",
            "quality_level": "rejected",
            "reason": hard_reason,
            "reasons": [hard_reason],
            "breakdown": {
                "prompt_density": 0,
                "target_relevance": 0,
                "evidence_quality": 0,
                "reusable_value": 0,
                "repo_health": 0,
            },
        }

    if category == "skill_repository":
        prompt_density, prompt_reasons = _score_skill_density(readme, combined)
    else:
        prompt_density, prompt_reasons = _score_prompt_density(readme, combined)
    target_relevance, target_reasons = _score_target_relevance(category, keyword, combined)
    evidence_quality, evidence_reasons = _score_evidence_quality(category, readme)
    reusable_value, reusable_reasons = _score_reusable_value(combined)
    repo_health, health_reasons = _score_repo_health(item)
    score = prompt_density + target_relevance + evidence_quality + reusable_value + repo_health
    reasons = [*prompt_reasons, *target_reasons, *evidence_reasons, *reusable_reasons, *health_reasons]

    web_ui_signals = _web_ui_signal_counts(combined) if category == "web_ui_prompt" else None
    if web_ui_signals:
        if web_ui_signals["frontend"] >= 3 and web_ui_signals["website"] >= 3 and web_ui_signals["asset"] >= 2:
            score += 6
            reasons.append("网站前端资产证据集中，提升发现分数")
        if web_ui_signals["frontend"] == 0:
            score -= 12
            reasons.append("缺少明确前端技术栈证据，降低发现分数")
        if web_ui_signals["asset"] == 0:
            score -= 8
            reasons.append("缺少资产组织证据，降低发现分数")
        if web_ui_signals["negative"] >= 1 and web_ui_signals["website"] < 3:
            score -= 10
            reasons.append("存在工具/工作流 UI 倾向，降低发现分数")

    if category == "skill_repository":
        skill_hits = len(SKILL_SIGNAL_RE.findall(combined))
        if skill_hits >= 4:
            score += 6
            reasons.append("Skill/Agent/MCP 证据集中，提升发现分数")
        if skill_hits == 0:
            score -= 16
            reasons.append("缺少 Skill/Agent/MCP 能力证据，降低发现分数")
        if _count_unique_hints(combined, SKILL_NEGATIVE_HINTS) >= 2:
            score -= 8
            reasons.append("存在非 Skill 资产倾向，降低发现分数")

    score = max(0, score)
    if score >= 65:
        decision = "save"
        status = "ready_to_scan"
        quality_level = "pending_review"
        reason = "发现分数达到入库阈值，进入资源库等待仓库扫描"
    elif score >= 45:
        decision = "review"
        status = "discovery_review"
        quality_level = "candidate_review"
        reason = "发现分数中等，保留为待观察仓库，避免错过小而美资源"
    else:
        decision = "skip"
        status = "skipped"
        quality_level = "rejected"
        reason = "发现分数低于阈值，暂不写入资源库"

    if web_ui_signals and decision == "save":
        if web_ui_signals["frontend"] < 1 or web_ui_signals["website"] < 2 or web_ui_signals["asset"] < 1:
            decision = "review"
            status = "discovery_review"
            quality_level = "candidate_review"
            reason = "更像网站前端相关仓库，但前端资产证据不足，先进入待观察"

    if category == "skill_repository" and decision == "save":
        if len(SKILL_SIGNAL_RE.findall(combined)) < 2:
            decision = "review"
            status = "discovery_review"
            quality_level = "candidate_review"
            reason = "更像 AI 工具相关仓库，但 Skill 能力证据不足，先进入待观察"

    return {
        "decision": decision,
        "score": int(score),
        "status": status,
        "quality_level": quality_level,
        "reason": reason,
        "reasons": reasons or [reason],
        "breakdown": {
            "prompt_density": int(prompt_density),
            "target_relevance": int(target_relevance),
            "evidence_quality": int(evidence_quality),
            "reusable_value": int(reusable_value),
            "repo_health": int(repo_health),
        },
    }
