from __future__ import annotations

import json
import uuid
from typing import Any, Dict, List, Optional

from database import fetch_all, fetch_one, get_connection, utc_now
from agents.memory import create_memory, search_active_memories
from agents.tools import build_sources, infer_library_tool_plan, normalize_library_tool_plan
from services.ai_config_service import chat_completion


def _json_dumps(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False)


def _json_loads(value: Optional[str], fallback: Any) -> Any:
    if not value:
        return fallback
    try:
        return json.loads(value)
    except Exception:
        return fallback


def _ensure_thread(thread_id: Optional[str], message: str) -> str:
    now = utc_now()
    if thread_id:
        existing = fetch_one("SELECT * FROM agent_threads WHERE id = ?", (thread_id,))
        if existing:
            with get_connection() as conn:
                conn.execute("UPDATE agent_threads SET updated_at = ? WHERE id = ?", (now, thread_id))
            return thread_id
    new_id = str(uuid.uuid4())
    title = " ".join(message.strip().split())[:40] or "新会话"
    with get_connection() as conn:
        conn.execute(
            "INSERT INTO agent_threads (id, title, status, created_at, updated_at) VALUES (?, ?, 'active', ?, ?)",
            (new_id, title, now, now),
        )
    return new_id


def _save_message(thread_id: str, role: str, content: str, sources: Optional[List[Dict[str, Any]]] = None, actions: Optional[List[Dict[str, Any]]] = None) -> Dict[str, Any]:
    now = utc_now()
    with get_connection() as conn:
        cursor = conn.execute(
            """
            INSERT INTO agent_messages (thread_id, role, content, sources_json, actions_json, created_at)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (thread_id, role, content, _json_dumps(sources or []), _json_dumps(actions or []), now),
        )
        message_id = int(cursor.lastrowid)
        conn.execute("UPDATE agent_threads SET updated_at = ? WHERE id = ?", (now, thread_id))
    row = fetch_one("SELECT * FROM agent_messages WHERE id = ?", (message_id,)) or {}
    row["sources"] = _json_loads(row.get("sources_json"), [])
    row["actions"] = _json_loads(row.get("actions_json"), [])
    return row


def list_threads() -> List[Dict[str, Any]]:
    return fetch_all("SELECT * FROM agent_threads ORDER BY updated_at DESC")


def list_messages(thread_id: str) -> List[Dict[str, Any]]:
    rows = fetch_all("SELECT * FROM agent_messages WHERE thread_id = ? ORDER BY id ASC", (thread_id,))
    for row in rows:
        row["sources"] = _json_loads(row.get("sources_json"), [])
        row["actions"] = _json_loads(row.get("actions_json"), [])
    return rows


def delete_thread(thread_id: str) -> bool:
    with get_connection() as conn:
        row = conn.execute("SELECT id FROM agent_threads WHERE id = ?", (thread_id,)).fetchone()
        if not row:
            return False
        conn.execute("DELETE FROM agent_messages WHERE thread_id = ?", (thread_id,))
        conn.execute("DELETE FROM agent_threads WHERE id = ?", (thread_id,))
    return True


def _maybe_create_memory(message: str) -> List[Dict[str, Any]]:
    text = " ".join((message or "").split())
    if not text:
        return []
    triggers = ("记住", "以后", "我希望", "我喜欢", "偏好", "不要", "优先")
    if not any(token in text for token in triggers):
        return []
    memory = create_memory(
        {
            "memory_type": "user_preference",
            "scope": "global",
            "content": text,
            "status": "pending_review",
            "confidence": 65,
            "source": "agent_suggested",
        }
    )
    return [{"type": "review_memory", "memory_id": memory["id"], "label": "确认是否保存为长期记忆"}]


def _extract_json_object(text: str) -> Dict[str, Any]:
    raw = (text or "").strip()
    if not raw:
        return {}
    if raw.startswith("```"):
        raw = raw.strip("`").strip()
        if raw.lower().startswith("json"):
            raw = raw[4:].strip()
    try:
        value = json.loads(raw)
        return value if isinstance(value, dict) else {}
    except json.JSONDecodeError:
        pass
    start = raw.find("{")
    end = raw.rfind("}")
    if start >= 0 and end > start:
        try:
            value = json.loads(raw[start : end + 1])
            return value if isinstance(value, dict) else {}
        except json.JSONDecodeError:
            return {}
    return {}


async def _plan_query_with_ai(message: str, fallback_plan: Dict[str, Any]) -> Dict[str, Any]:
    planner_prompt = """
你是本地视觉 Prompt 资产库的查询规划智能体。你只负责理解用户语义并输出 JSON，不负责回答结果。

根据用户问题判断：
1. 用户想干什么 intent，可选 find_prompt、find_repo、review_candidates、compare、export_hint。
2. 应该查哪类资产 categories，可选 web_ui_prompt、image_generation_prompt、skill_repository、video_generation_prompt。
3. 应该调用哪些工具 tools，可选 web_ui_prompt_search、visual_prompt_pair_search、skill_repo_search、repo_search、pair_candidate_search。
4. 应该去哪些 SQLite 表 target_tables，可选 web_ui_repo_profiles、prompt_effect_pairs、skill_repo_profiles、repos、pair_candidates。
5. 需要用哪些中英文模糊关键词 expanded_keywords，尤其要补充风格同义词。
6. 如果用户说“卡通风格提示词”，通常是 image_generation_prompt，不是 Web UI。

只输出 JSON，字段：
{
  "intent": [],
  "focus": "",
  "categories": [],
  "scenarios": [],
  "tools": [],
  "target_tables": [],
  "expanded_keywords": [],
  "reason": ""
}
"""
    try:
        result = await chat_completion(
            [
                {"role": "system", "content": planner_prompt},
                {
                    "role": "user",
                    "content": json.dumps(
                        {
                            "user_message": message,
                            "rule_fallback_plan": fallback_plan,
                            "examples": [
                                {
                                    "message": "卡通风格提示词 找找",
                                    "expected": {
                                        "categories": ["image_generation_prompt"],
                                        "tools": ["visual_prompt_pair_search"],
                                        "target_tables": ["prompt_effect_pairs"],
                                        "expanded_keywords": ["卡通", "cartoon", "动漫", "动画", "插画", "illustration", "anime"],
                                    },
                                },
                                {
                                    "message": "找 dashboard 的 Web UI Prompt",
                                    "expected": {
                                        "categories": ["web_ui_prompt"],
                                        "tools": ["web_ui_prompt_search"],
                                        "target_tables": ["web_ui_repo_profiles"],
                                        "expanded_keywords": ["dashboard", "仪表盘", "Web UI", "组件"],
                                    },
                                },
                            ],
                        },
                        ensure_ascii=False,
                    ),
                },
            ],
            temperature=0,
            max_tokens=700,
        )
        ai_plan = _extract_json_object(result.get("content") or "")
        ai_plan["planner_mode"] = "ai"
        return normalize_library_tool_plan(message, ai_plan, fallback_plan)
    except Exception as exc:
        plan = normalize_library_tool_plan(message, None, fallback_plan)
        plan["planner_mode"] = "rules_fallback"
        plan["planner_reason"] = f"AI 查询规划失败，已使用规则回退：{exc}"
        return plan


def _fallback_answer(message: str, sources: List[Dict[str, Any]], memories: List[Dict[str, Any]], tool_plan: Optional[Dict[str, Any]] = None) -> str:
    tool_plan = tool_plan or {}
    lines = ["## 查询理解"]
    lines.append(f"- 原始需求：{message}")
    if tool_plan.get("planner_mode"):
        mode_label = "AI 语义规划" if tool_plan.get("planner_mode") == "ai" else "规则回退"
        lines.append(f"- 规划方式：{mode_label}")
    if tool_plan.get("planner_reason"):
        lines.append(f"- 规划依据：{tool_plan['planner_reason']}")
    if tool_plan.get("focus"):
        lines.append(f"- 判断目标：{tool_plan['focus']}")
    if tool_plan.get("intent"):
        lines.append(f"- 用户意图：{', '.join(tool_plan['intent'])}")
    if tool_plan.get("target_tables"):
        lines.append(f"- 查询位置：{', '.join(tool_plan['target_tables'])}")
    if tool_plan.get("tools"):
        lines.append("")
        lines.append("## 使用工具")
        for tool in tool_plan.get("tools", []):
            lines.append(f"- `{tool}`")
    if tool_plan.get("expanded_keywords"):
        lines.append("")
        lines.append("## 模糊关键词")
        lines.append(" ".join(f"`{term}`" for term in tool_plan.get("expanded_keywords", [])[:12]))
    if memories:
        lines.append("")
        lines.append(f"> 已使用 {len(memories)} 条已确认记忆作为偏好上下文。")
    lines.append("")
    lines.append("## 查询结果")
    if not sources:
        lines.append("当前 SQLite 中没有找到足够匹配的结果。")
        lines.append("")
        lines.append("可以尝试：")
        lines.append("- 换同义词，例如 `卡通`、`cartoon`、`动漫`、`插画`。")
        lines.append("- 先扫描更多图像生成类仓库，再回来查询。")
        lines.append("- 如果你知道来源仓库，可以在资源库中单独扫描该仓库。")
        return "\n".join(lines)
    lines.append(f"找到 **{len(sources)}** 条相关结果。")
    lines.append("")
    for index, source in enumerate(sources[:8], start=1):
        data = source.get("data") or {}
        external_url = source.get("external_url") or data.get("source_page_url") or data.get("repo_url") or ""
        open_link = f" | [打开来源]({external_url})" if external_url else ""
        local_link = f"[在本地界面查看](agent-source://{source['type']}/{source['id']})"
        if source["type"] == "repo":
            lines.append(f"### {index}. {source['title']}")
            lines.append(f"- 类型：资源仓库")
            lines.append(f"- 分类：`{data.get('category') or '-'}`")
            lines.append(f"- 摘要：{data.get('summary') or '-'}")
            lines.append(f"- 链接：{local_link}{open_link}")
        elif source["type"] == "web_ui_prompt":
            lines.append(f"### {index}. {source['title']}")
            lines.append(f"- 类型：Web UI 资产")
            lines.append(f"- 资产类型：`{data.get('asset_type') or '-'}`")
            lines.append(f"- 框架：{data.get('framework') or '-'}")
            lines.append(f"- 内容：{(data.get('prompt_cn_translation') or data.get('prompt_text') or source.get('snippet') or '')[:260]}")
            lines.append(f"- 链接：{local_link}{open_link}")
        elif source["type"] == "skill_repo":
            lines.append(f"### {index}. {source['title']}")
            lines.append("- 类型：Skill 仓库资产")
            lines.append(f"- Skill 类型：`{data.get('skill_type') or '-'}`")
            lines.append(f"- 目标平台：{data.get('target_platform') or '-'}")
            lines.append(f"- 运行栈：{data.get('runtime_stack') or '-'}")
            lines.append(f"- 摘要：{data.get('ai_summary_cn') or data.get('summary_cn') or source.get('snippet') or '-'}")
            lines.append(f"- 链接：{local_link}{open_link}")
        elif source["type"] == "prompt_pair":
            prompt = data.get("prompt_cn_explanation") or data.get("original_prompt") or source.get("snippet") or ""
            lines.append(f"### {index}. {source['title']}")
            lines.append(f"- 类型：Prompt 效果对")
            lines.append(f"- 分类：`{data.get('category') or '-'}`")
            lines.append(f"- 场景：`{data.get('scenario') or '-'}`")
            lines.append(f"- 筛选结论：`{data.get('selection_status') or '-'}`")
            lines.append(f"- Prompt 摘要：{str(prompt)[:300]}")
            lines.append(f"- 链接：{local_link}{open_link}")
        else:
            lines.append(f"### {index}. {source['title']}")
            lines.append(f"- 类型：候选配对")
            lines.append(f"- 匹配分数：`{data.get('match_score') or '-'}`")
            lines.append(f"- 状态：`{data.get('review_status') or '-'}`")
            lines.append(f"- 证据：{data.get('evidence') or source.get('snippet') or '-'}")
            lines.append(f"- 链接：{local_link}{open_link}")
        lines.append("")
    return "\n".join(lines)


async def chat_with_library_agent(message: str, thread_id: Optional[str] = None) -> Dict[str, Any]:
    clean = " ".join((message or "").strip().split())
    if not clean:
        raise ValueError("消息不能为空")
    actual_thread_id = _ensure_thread(thread_id, clean)
    _save_message(actual_thread_id, "user", clean)

    memories = search_active_memories(clean, limit=8)
    fallback_plan = infer_library_tool_plan(clean)
    tool_plan = await _plan_query_with_ai(clean, fallback_plan)
    sources = build_sources(clean, plan=tool_plan)[:12]
    actions = _maybe_create_memory(clean)

    answer = _fallback_answer(clean, sources, memories, tool_plan)

    assistant_message = _save_message(actual_thread_id, "assistant", answer, sources=sources, actions=actions)
    return {
        "thread_id": actual_thread_id,
        "message": assistant_message,
        "sources": sources,
        "actions": actions,
        "tool_plan": tool_plan,
    }
