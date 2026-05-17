from __future__ import annotations

import json
import uuid
from typing import Any, Dict, List, Optional

from database import fetch_all, fetch_one, get_connection, utc_now
from services.ai_config_service import chat_completion
from agents.memory import create_memory, search_active_memories
from agents.prompts import LIBRARY_AGENT_SYSTEM_PROMPT, LIBRARY_AGENT_USER_PROMPT
from agents.tools import build_sources


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


def _fallback_answer(message: str, sources: List[Dict[str, Any]], memories: List[Dict[str, Any]]) -> str:
    lines = ["我先按本地库检索结果回答。"]
    if memories:
        lines.append(f"已使用 {len(memories)} 条已确认记忆作为偏好上下文。")
    if not sources:
        lines.append("没有在当前 SQLite 中找到明显匹配的仓库、Prompt 效果对或候选配对。")
        lines.append("可以换一个更具体的关键词，例如分类、场景、仓库名或视觉风格。")
        return "\n".join(lines)
    lines.append(f"找到 {len(sources)} 条相关来源：")
    for source in sources[:8]:
        data = source.get("data") or {}
        if source["type"] == "repo":
            lines.append(f"- 仓库：{source['title']}，分类 {data.get('category')}，效果对 {data.get('prompt_effect_pair_count') or 0} 个。")
        elif source["type"] == "prompt_pair":
            lines.append(f"- Prompt 效果对：{source['title']}，场景 {data.get('scenario')}，结论 {data.get('selection_status')}。")
        else:
            lines.append(f"- 候选配对：{source['title']}，分数 {data.get('match_score')}，状态 {data.get('review_status')}。")
    return "\n".join(lines)


async def chat_with_library_agent(message: str, thread_id: Optional[str] = None) -> Dict[str, Any]:
    clean = " ".join((message or "").strip().split())
    if not clean:
        raise ValueError("消息不能为空")
    actual_thread_id = _ensure_thread(thread_id, clean)
    _save_message(actual_thread_id, "user", clean)

    memories = search_active_memories(clean, limit=8)
    sources = build_sources(clean)[:12]
    actions = _maybe_create_memory(clean)

    try:
        result = await chat_completion(
            [
                {"role": "system", "content": LIBRARY_AGENT_SYSTEM_PROMPT},
                {
                    "role": "user",
                    "content": LIBRARY_AGENT_USER_PROMPT.format(
                        message=clean,
                        memories=_json_dumps(memories),
                        sources=_json_dumps(sources),
                    ),
                },
            ],
            max_tokens=1400,
        )
        answer = result["content"]
    except Exception:
        answer = _fallback_answer(clean, sources, memories)

    assistant_message = _save_message(actual_thread_id, "assistant", answer, sources=sources, actions=actions)
    return {
        "thread_id": actual_thread_id,
        "message": assistant_message,
        "sources": sources,
        "actions": actions,
    }
