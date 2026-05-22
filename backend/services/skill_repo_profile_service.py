from __future__ import annotations

import json
import re
from dataclasses import dataclass
from typing import Any, Callable, Dict, Iterable, List, Optional, Sequence

from database import utc_now
from services.ai_config_service import chat_completion


SKILL_TYPE_HINTS: Sequence[tuple[str, tuple[str, ...]]] = (
    ("mcp_server", ("mcp server", "model context protocol", "mcp.json", "tools/list")),
    ("agent_toolkit", ("agent toolkit", "agent tools", "tool calling", "function calling", "tools/")),
    ("claude_skill", ("claude skill", ".claude", "claude code", "claude desktop")),
    ("codex_skill", ("codex skill", ".codex", "codex")),
    ("cursor_rule_pack", ("cursor rules", ".cursor/rules", "cursor rule")),
    ("desktop_ai_skill", ("desktop ai skill", "desktop automation", "local skill")),
    ("workflow_pack", ("workflow", "automation workflow", "playbook", "recipe")),
)

PLATFORM_HINTS: Sequence[tuple[str, tuple[str, ...]]] = (
    ("Claude", ("claude", ".claude")),
    ("Codex", ("codex", ".codex")),
    ("Cursor", ("cursor", ".cursor")),
    ("ChatGPT", ("chatgpt", "gpt", "openai")),
    ("MCP", ("mcp", "model context protocol")),
    ("Local Desktop", ("desktop", "local", "windows", "macos")),
    ("Generic Agent", ("agent", "llm", "tool calling")),
)

STACK_HINTS: Sequence[tuple[str, tuple[str, ...]]] = (
    ("Python", ("python", "pyproject.toml", "requirements.txt", ".py")),
    ("Node.js", ("node", "typescript", "package.json", "npm", "pnpm", ".ts")),
    ("Docker", ("docker", "dockerfile", "docker compose")),
    ("Shell", ("bash", "powershell", ".sh", ".ps1")),
    ("MCP", ("mcp", "model context protocol")),
    ("LangChain", ("langchain", "langgraph")),
)

CAPABILITY_HINTS: Sequence[tuple[str, tuple[str, ...]]] = (
    ("网页抓取", ("scrape", "crawler", "browser", "playwright", "web search")),
    ("文件处理", ("file", "filesystem", "document", "pdf", "docx", "spreadsheet")),
    ("代码开发", ("code", "repository", "git", "pull request", "tests")),
    ("数据查询", ("database", "sqlite", "sql", "query")),
    ("自动化执行", ("automation", "workflow", "schedule", "task")),
    ("内容生成", ("generate", "writing", "markdown", "report")),
    ("工具调用", ("tool", "function calling", "mcp server")),
    ("知识检索", ("rag", "search", "retrieval", "memory")),
)

INPUT_HINTS: Sequence[tuple[str, tuple[str, ...]]] = (
    ("文本需求", ("prompt", "instruction", "query", "message")),
    ("文件", ("file", "path", "document", "pdf", "image")),
    ("URL", ("url", "webpage", "website", "link")),
    ("代码仓库", ("repo", "repository", "github")),
    ("结构化数据", ("json", "yaml", "csv", "sqlite")),
)

OUTPUT_HINTS: Sequence[tuple[str, tuple[str, ...]]] = (
    ("Markdown", ("markdown", ".md", "report")),
    ("JSON", ("json", "schema")),
    ("文件产物", ("output file", "artifact", "save")),
    ("工具结果", ("tool result", "response")),
    ("代码修改", ("patch", "commit", "pull request")),
)

USE_CASE_HINTS: Sequence[tuple[str, tuple[str, ...]]] = (
    ("桌面 AI Skill", ("skill", "desktop", "local")),
    ("Agent 工具包", ("agent", "toolkit", "tool calling")),
    ("MCP 工具服务", ("mcp", "server")),
    ("开发辅助", ("code", "repo", "git", "test")),
    ("资料整理", ("document", "markdown", "knowledge", "memory")),
    ("自动化工作流", ("automation", "workflow", "schedule")),
)

CONCRETE_USE_CASE_HINTS: Sequence[tuple[str, tuple[str, ...]]] = (
    ("微信公众号文章撰写", ("wechat", "official account", "公众号", "微信文章", "draft/add", "thumb_media_id")),
    ("小红书图文笔记生成", ("xiaohongshu", "rednote", "小红书", "note writing", "social post")),
    ("短视频脚本策划", ("short video", "tiktok", "douyin", "reels", "script", "storyboard", "短视频", "抖音")),
    ("网页内容抓取与摘要", ("scrape", "crawler", "playwright", "browser", "webpage", "website", "网页抓取")),
    ("PDF 文档总结", ("pdf", "document summary", "docling", "文档总结", "论文总结")),
    ("表格数据分析", ("spreadsheet", "excel", "xlsx", "csv", "data analysis", "表格")),
    ("GitHub 仓库代码审查", ("pull request", "code review", "github", "repository", "diff", "代码审查")),
    ("本地文件批量整理", ("filesystem", "file management", "batch rename", "local files", "文件整理")),
    ("MCP 工具服务接入", ("mcp server", "model context protocol", "tools/list", "mcp.json")),
    ("AI Agent 工具调用", ("tool calling", "function calling", "agent tools", "agent toolkit")),
    ("自动化任务调度", ("schedule", "cron", "automation workflow", "task runner", "定时任务")),
    ("知识库检索问答", ("rag", "retrieval", "knowledge base", "vector", "memory", "知识库")),
    ("图片生成素材整理", ("image generation", "prompt", "visual asset", "stable diffusion", "图片生成")),
    ("视频生成分镜整理", ("video generation", "camera movement", "storyboard", "runway", "veo", "kling", "视频生成")),
)


@dataclass(frozen=True)
class SkillRepoProfileCandidate:
    skill_type: str
    target_platform: str
    runtime_stack: str
    capabilities: List[str]
    input_types: List[str]
    output_types: List[str]
    use_cases: List[str]
    tools: List[str]
    install_method: str
    configuration_notes: str
    reuse_mode: str
    summary_cn: str
    ai_summary_cn: str
    evidence: str
    ai_reason_cn: str
    tags: List[str]
    confidence: int
    source_ai_config_id: Optional[int]


def _contains_any(text: str, hints: Iterable[str]) -> bool:
    lower = (text or "").lower()
    return any(hint.lower() in lower for hint in hints)


def _pick_many(text: str, hint_groups: Sequence[tuple[str, tuple[str, ...]]], limit: int = 8) -> List[str]:
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


def _clean_text(text: str, max_len: int = 320) -> str:
    value = re.sub(r"\s+", " ", (text or "").strip())
    return value[:max_len].strip()


def _repo_probe(repo_name: str, readme: str, documents: Sequence[Dict[str, str]]) -> str:
    paths = " ".join((document.get("path") or "") for document in documents[:120])
    snippets = "\n".join((document.get("content") or "")[:1200] for document in documents[:10])
    return f"{repo_name}\n{readme[:12000]}\n{paths}\n{snippets}"


def _infer_one(text: str, hint_groups: Sequence[tuple[str, tuple[str, ...]]], fallback: str) -> str:
    for label, hints in hint_groups:
        if _contains_any(text, hints):
            return label
    return fallback


def _infer_runtime_stack(probe: str) -> str:
    stack = _pick_many(probe, STACK_HINTS, limit=5)
    return " + ".join(stack)


def _extract_install_method(readme: str) -> str:
    lines = []
    for line in (readme or "").splitlines():
        clean = line.strip()
        lower = clean.lower()
        if not clean:
            continue
        if any(token in lower for token in ("npm install", "pip install", "uvx ", "docker ", "git clone", "npx ", "pnpm ", "uv pip")):
            lines.append(clean)
        if len(lines) >= 3:
            break
    return "\n".join(lines)


def _extract_tool_names(documents: Sequence[Dict[str, str]]) -> List[str]:
    names: List[str] = []
    for document in documents:
        path = (document.get("path") or "").replace("\\", "/")
        lower = path.lower()
        if any(part in lower for part in ("tools/", "skills/", "servers/", "scripts/", ".cursor/rules", ".claude")):
            stem = path.rsplit("/", 1)[-1].rsplit(".", 1)[0]
            if stem and stem not in names:
                names.append(stem)
        if len(names) >= 12:
            break
    return names


def _fallback_summary(repo_name: str, skill_type: str, capabilities: List[str]) -> str:
    capability_text = "、".join(capabilities[:4]) if capabilities else "可复用能力"
    return f"{repo_name} 是一个 {skill_type} 类型的 Skill 仓库，主要可用于{capability_text}。"


def _specific_use_cases(probe: str, fallback: List[str]) -> List[str]:
    concrete = _pick_many(probe, CONCRETE_USE_CASE_HINTS, limit=8)
    if concrete:
        return concrete
    generic_to_concrete = {
        "开发辅助": "GitHub 仓库代码审查",
        "资料整理": "PDF 文档总结",
        "自动化工作流": "自动化任务调度",
        "MCP 工具服务": "MCP 工具服务接入",
        "Agent 工具包": "AI Agent 工具调用",
        "桌面 AI Skill": "本地文件批量整理",
    }
    result: List[str] = []
    for item in fallback:
        mapped = generic_to_concrete.get(item, item)
        if mapped not in result:
            result.append(mapped)
    return result[:6]


def _unique_limited(values: Iterable[str], limit: int = 8) -> List[str]:
    result: List[str] = []
    for value in values:
        text = str(value).strip()
        if text and text not in result:
            result.append(text)
        if len(result) >= limit:
            break
    return result


async def _ai_enrich_profile(
    *,
    repo_name: str,
    repo_url: str,
    readme: str,
    documents: Sequence[Dict[str, str]],
    fallback: Dict[str, Any],
    ai_config_id: Optional[int],
) -> Dict[str, Any]:
    payload = {
        "task": "分析 GitHub Skill 仓库，判断它适合做什么 AI Skill 或 Agent 工具",
        "repo": {
            "name": repo_name,
            "url": repo_url,
            "readme_excerpt": readme[:9000],
            "top_paths": [document.get("path") for document in documents[:80]],
            "fallback": fallback,
        },
        "required_output_schema": {
            "summary_cn": "一句中文总结",
            "skill_type": "mcp_server/agent_toolkit/claude_skill/codex_skill/cursor_rule_pack/desktop_ai_skill/workflow_pack/other",
            "target_platform": "Claude/Codex/Cursor/ChatGPT/MCP/Local Desktop/Generic Agent",
            "runtime_stack": "Python + Node.js 等",
            "capabilities": ["4-8 个中文能力标签"],
            "input_types": ["输入类型"],
            "output_types": ["输出类型"],
            "use_cases": ["3-6 个具体需求场景，例如微信公众号文章撰写、PDF 文档总结、GitHub 仓库代码审查"],
            "tools": ["仓库提供的工具或技能名称"],
            "install_method": "安装方式摘要",
            "configuration_notes": "配置要求摘要",
            "reuse_mode": "可直接接入/参考改造/只作研究参考",
            "tags": ["4-8 个中文标签"],
            "commercial_risk": "low/medium/high/unknown",
            "reason_cn": "判断理由",
            "confidence": "0-100 integer",
        },
    }
    result = await chat_completion(
        [
            {
                "role": "system",
                "content": (
                    "你是 AI Skill 仓库标注助手。只返回 JSON，不要 Markdown。"
                    "重点判断仓库整体能力、适用平台、复用方式和风险。"
                    "use_cases 必须是非常具体的用户需求场景，例如微信公众号文章撰写、网页内容抓取与摘要、PDF 文档总结；"
                    "不要只写开发辅助、资料整理、自动化工作流这类泛标签。"
                ),
            },
            {"role": "user", "content": _json_dumps(payload)},
        ],
        ai_config_id=ai_config_id,
        temperature=0.1,
        max_tokens=1200,
    )
    content = _extract_json_object(result.get("content") or "")
    return {
        "summary_cn": _clean_text(str(content.get("summary_cn") or fallback["summary_cn"])),
        "skill_type": _clean_text(str(content.get("skill_type") or fallback["skill_type"]), 80),
        "target_platform": _clean_text(str(content.get("target_platform") or fallback["target_platform"]), 120),
        "runtime_stack": _clean_text(str(content.get("runtime_stack") or fallback["runtime_stack"]), 120),
        "capabilities": [str(item).strip() for item in (content.get("capabilities") or []) if str(item).strip()][:8],
        "input_types": [str(item).strip() for item in (content.get("input_types") or []) if str(item).strip()][:8],
        "output_types": [str(item).strip() for item in (content.get("output_types") or []) if str(item).strip()][:8],
        "use_cases": [str(item).strip() for item in (content.get("use_cases") or []) if str(item).strip()][:8],
        "tools": [str(item).strip() for item in (content.get("tools") or []) if str(item).strip()][:12],
        "install_method": _clean_text(str(content.get("install_method") or fallback["install_method"]), 500),
        "configuration_notes": _clean_text(str(content.get("configuration_notes") or fallback["configuration_notes"]), 500),
        "reuse_mode": _clean_text(str(content.get("reuse_mode") or fallback["reuse_mode"]), 80),
        "tags": [str(item).strip() for item in (content.get("tags") or []) if str(item).strip()][:8],
        "commercial_risk": _clean_text(str(content.get("commercial_risk") or "unknown"), 40),
        "reason_cn": _clean_text(str(content.get("reason_cn") or "")),
        "confidence": max(0, min(int(content.get("confidence") or 75), 100)),
        "source_ai_config_id": (result.get("config") or {}).get("id"),
    }


async def build_skill_repo_profile(
    *,
    repo_name: str,
    repo_url: str,
    readme: str,
    documents: Sequence[Dict[str, str]],
    ai_config_id: Optional[int] = None,
    progress_callback: Optional[Callable[[Dict[str, Any]], None]] = None,
) -> SkillRepoProfileCandidate:
    probe = _repo_probe(repo_name, readme, documents)
    skill_type = _infer_one(probe, SKILL_TYPE_HINTS, "other")
    target_platform = " / ".join(_pick_many(probe, PLATFORM_HINTS, limit=3)) or "Generic Agent"
    runtime_stack = _infer_runtime_stack(probe)
    capabilities = _pick_many(probe, CAPABILITY_HINTS, limit=8)
    input_types = _pick_many(probe, INPUT_HINTS, limit=6)
    output_types = _pick_many(probe, OUTPUT_HINTS, limit=6)
    use_cases = _specific_use_cases(probe, _pick_many(probe, USE_CASE_HINTS, limit=6))
    tools = _extract_tool_names(documents)
    install_method = _extract_install_method(readme)
    configuration_notes = "需要结合 README 检查 API Key、环境变量、依赖和运行权限。"
    reuse_mode = "参考改造"
    tags = [*use_cases[:3], *capabilities[:3], skill_type, target_platform.split(" / ")[0]]
    summary_cn = _fallback_summary(repo_name, skill_type, capabilities)
    ai_summary_cn = ""
    ai_reason_cn = ""
    confidence = 68
    source_ai_config_id: Optional[int] = None
    commercial_risk = "unknown"

    if progress_callback:
        progress_callback({"current_file": "README.md", "phase": "skill_repo_profile_rules"})

    fallback = {
        "summary_cn": summary_cn,
        "skill_type": skill_type,
        "target_platform": target_platform,
        "runtime_stack": runtime_stack,
        "capabilities": capabilities,
        "input_types": input_types,
        "output_types": output_types,
        "use_cases": use_cases,
        "tools": tools,
        "install_method": install_method,
        "configuration_notes": configuration_notes,
        "reuse_mode": reuse_mode,
        "tags": tags,
    }
    try:
        if progress_callback:
            progress_callback({"current_file": "AI 标注 Skill 仓库能力", "phase": "skill_repo_profile_ai"})
        ai_result = await _ai_enrich_profile(
            repo_name=repo_name,
            repo_url=repo_url,
            readme=readme,
            documents=documents,
            fallback=fallback,
            ai_config_id=ai_config_id,
        )
        summary_cn = ai_result["summary_cn"] or summary_cn
        ai_summary_cn = ai_result["summary_cn"] or ""
        skill_type = ai_result["skill_type"] or skill_type
        target_platform = ai_result["target_platform"] or target_platform
        runtime_stack = ai_result["runtime_stack"] or runtime_stack
        capabilities = ai_result["capabilities"] or capabilities
        input_types = ai_result["input_types"] or input_types
        output_types = ai_result["output_types"] or output_types
        use_cases = ai_result["use_cases"] or use_cases
        use_cases = _specific_use_cases(f"{probe}\n{' '.join(use_cases)}", use_cases)
        tools = ai_result["tools"] or tools
        install_method = ai_result["install_method"] or install_method
        configuration_notes = ai_result["configuration_notes"] or configuration_notes
        reuse_mode = ai_result["reuse_mode"] or reuse_mode
        tags = _unique_limited([*use_cases[:3], *(ai_result["tags"] or tags)], limit=8)
        commercial_risk = ai_result["commercial_risk"] or commercial_risk
        ai_reason_cn = ai_result["reason_cn"] or ""
        confidence = ai_result["confidence"] or confidence
        source_ai_config_id = ai_result["source_ai_config_id"]
    except Exception as exc:
        ai_reason_cn = f"AI 标注失败，已回退规则判断：{str(exc)[:300]}"

    evidence = (
        f"仓库级扫描：基于 README、目录结构和配置文件判断为 {skill_type}。"
        f"目标平台：{target_platform or '未明确'}；运行栈：{runtime_stack or '未明确'}；"
        f"能力线索：{', '.join(capabilities) if capabilities else '未明确'}。"
    )
    return SkillRepoProfileCandidate(
        skill_type=skill_type,
        target_platform=target_platform,
        runtime_stack=runtime_stack,
        capabilities=capabilities,
        input_types=input_types,
        output_types=output_types,
        use_cases=use_cases,
        tools=tools,
        install_method=install_method,
        configuration_notes=configuration_notes,
        reuse_mode=reuse_mode,
        summary_cn=summary_cn,
        ai_summary_cn=ai_summary_cn,
        evidence=evidence,
        ai_reason_cn=ai_reason_cn,
        tags=tags,
        confidence=confidence,
        source_ai_config_id=source_ai_config_id,
    )


async def save_skill_repo_profile(conn, repo_id: int, repo_name: str, repo_url: str, profile: SkillRepoProfileCandidate) -> Dict[str, Any]:
    now = utc_now()
    existing = conn.execute("SELECT * FROM skill_repo_profiles WHERE repo_id = ?", (repo_id,)).fetchone()
    payload = {
        "repo_name": repo_name,
        "repo_url": repo_url,
        "skill_type": profile.skill_type,
        "target_platform": profile.target_platform,
        "runtime_stack": profile.runtime_stack,
        "capabilities_json": _json_dumps(profile.capabilities),
        "input_types_json": _json_dumps(profile.input_types),
        "output_types_json": _json_dumps(profile.output_types),
        "use_cases_json": _json_dumps(profile.use_cases),
        "tools_json": _json_dumps(profile.tools),
        "install_method": profile.install_method,
        "configuration_notes": profile.configuration_notes,
        "reuse_mode": profile.reuse_mode,
        "summary_cn": profile.summary_cn,
        "ai_summary_cn": profile.ai_summary_cn,
        "evidence": profile.evidence,
        "ai_reason_cn": profile.ai_reason_cn,
        "tags_json": _json_dumps(profile.tags),
        "confidence": profile.confidence,
        "source_ai_config_id": profile.source_ai_config_id,
        "last_scanned_at": now,
        "updated_at": now,
    }
    if existing:
        manual_fields = {"quality_level", "selection_status", "commercial_risk", "notes"}
        merged = dict(payload)
        for field in manual_fields:
            merged[field] = existing[field]
        assignments = ", ".join(f"{key} = ?" for key in merged)
        conn.execute(f"UPDATE skill_repo_profiles SET {assignments} WHERE repo_id = ?", (*merged.values(), repo_id))
        return {"action": "updated", "skill_type": profile.skill_type}

    conn.execute(
        """
        INSERT INTO skill_repo_profiles
            (repo_id, repo_name, repo_url, skill_type, target_platform, runtime_stack, capabilities_json,
             input_types_json, output_types_json, use_cases_json, tools_json, install_method, configuration_notes,
             reuse_mode, summary_cn, ai_summary_cn, evidence, ai_reason_cn, tags_json, confidence,
             source_ai_config_id, quality_level, selection_status, commercial_risk, last_scanned_at,
             created_at, updated_at, notes)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            repo_id,
            repo_name,
            repo_url,
            profile.skill_type,
            profile.target_platform,
            profile.runtime_stack,
            _json_dumps(profile.capabilities),
            _json_dumps(profile.input_types),
            _json_dumps(profile.output_types),
            _json_dumps(profile.use_cases),
            _json_dumps(profile.tools),
            profile.install_method,
            profile.configuration_notes,
            profile.reuse_mode,
            profile.summary_cn,
            profile.ai_summary_cn,
            profile.evidence,
            profile.ai_reason_cn,
            _json_dumps(profile.tags),
            profile.confidence,
            profile.source_ai_config_id,
            "pending_review",
            "pending_review",
            "unknown",
            now,
            now,
            now,
            "",
        ),
    )
    return {"action": "added", "skill_type": profile.skill_type}
