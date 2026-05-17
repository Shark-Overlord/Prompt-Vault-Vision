from __future__ import annotations

import json
import re
from typing import Any, Dict, List, Optional

from database import fetch_all, fetch_one, get_connection, paginate, utc_now


VALID_MEMORY_TYPES = {"user_preference", "scan_pattern", "review_decision", "query_context"}
VALID_MEMORY_STATUSES = {"pending_review", "active", "rejected", "archived", "disabled"}


def _clean_text(value: Optional[str]) -> str:
    return " ".join((value or "").strip().split())


def _sync_fts(conn, memory_id: int, content: str) -> None:
    conn.execute("DELETE FROM agent_memory_fts WHERE memory_id = ?", (memory_id,))
    conn.execute("INSERT INTO agent_memory_fts (memory_id, content) VALUES (?, ?)", (memory_id, content))


def _validate_memory_payload(data: Dict[str, Any], partial: bool = False) -> Dict[str, Any]:
    result = dict(data)
    memory_type = result.get("memory_type")
    if memory_type is not None and memory_type not in VALID_MEMORY_TYPES:
        raise ValueError("记忆类型无效")
    status = result.get("status")
    if status is not None and status not in VALID_MEMORY_STATUSES:
        raise ValueError("记忆状态无效")
    if not partial and not _clean_text(result.get("content")):
        raise ValueError("记忆内容不能为空")
    if result.get("content") is not None:
        result["content"] = _clean_text(result.get("content"))
    if result.get("content_json") is not None:
        try:
            json.loads(result["content_json"])
        except Exception as exc:
            raise ValueError("content_json 必须是合法 JSON 字符串") from exc
    return result


def list_memories(status: Optional[str] = None, memory_type: Optional[str] = None, repo_id: Optional[int] = None) -> List[Dict[str, Any]]:
    where = ["1 = 1"]
    params: List[Any] = []
    if status:
        where.append("status = ?")
        params.append(status)
    if memory_type:
        where.append("memory_type = ?")
        params.append(memory_type)
    if repo_id is not None:
        where.append("repo_id = ?")
        params.append(repo_id)
    return fetch_all(f"SELECT * FROM agent_memories WHERE {' AND '.join(where)} ORDER BY updated_at DESC, id DESC", tuple(params))


def list_memories_paginated(
    status: Optional[str] = None,
    memory_type: Optional[str] = None,
    repo_id: Optional[int] = None,
    page: int = 1,
    page_size: int = 20,
) -> Dict[str, Any]:
    where = ["1 = 1"]
    params: List[Any] = []
    if status:
        where.append("status = ?")
        params.append(status)
    if memory_type:
        where.append("memory_type = ?")
        params.append(memory_type)
    if repo_id is not None:
        where.append("repo_id = ?")
        params.append(repo_id)
    clause = " AND ".join(where)
    return paginate(
        f"SELECT * FROM agent_memories WHERE {clause} ORDER BY updated_at DESC, id DESC",
        f"SELECT COUNT(*) FROM agent_memories WHERE {clause}",
        tuple(params),
        page,
        page_size,
    )


def get_memory(memory_id: int) -> Optional[Dict[str, Any]]:
    return fetch_one("SELECT * FROM agent_memories WHERE id = ?", (memory_id,))


def create_memory(payload: Dict[str, Any]) -> Dict[str, Any]:
    data = _validate_memory_payload(payload)
    now = utc_now()
    with get_connection() as conn:
        cursor = conn.execute(
            """
            INSERT INTO agent_memories
                (memory_type, scope, repo_id, content, content_json, status, confidence, source, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                data.get("memory_type") or "user_preference",
                data.get("scope") or "global",
                data.get("repo_id"),
                data["content"],
                data.get("content_json"),
                data.get("status") or "pending_review",
                int(data.get("confidence") or 70),
                data.get("source") or "manual",
                now,
                now,
            ),
        )
        memory_id = int(cursor.lastrowid)
        _sync_fts(conn, memory_id, data["content"])
    return get_memory(memory_id) or {}


def update_memory(memory_id: int, payload: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    existing = get_memory(memory_id)
    if not existing:
        return None
    data = _validate_memory_payload(payload, partial=True)
    merged = dict(existing)
    for key, value in data.items():
        if value is not None:
            merged[key] = value
    now = utc_now()
    with get_connection() as conn:
        conn.execute(
            """
            UPDATE agent_memories
            SET memory_type = ?, scope = ?, repo_id = ?, content = ?, content_json = ?,
                status = ?, confidence = ?, source = ?, updated_at = ?
            WHERE id = ?
            """,
            (
                merged["memory_type"],
                merged["scope"],
                merged.get("repo_id"),
                merged["content"],
                merged.get("content_json"),
                merged["status"],
                int(merged.get("confidence") or 70),
                merged.get("source"),
                now,
                memory_id,
            ),
        )
        _sync_fts(conn, memory_id, merged["content"])
    return get_memory(memory_id)


def set_memory_status(memory_id: int, status: str) -> Optional[Dict[str, Any]]:
    if status not in VALID_MEMORY_STATUSES:
        raise ValueError("记忆状态无效")
    now = utc_now()
    with get_connection() as conn:
        row = conn.execute("SELECT id FROM agent_memories WHERE id = ?", (memory_id,)).fetchone()
        if not row:
            return None
        conn.execute("UPDATE agent_memories SET status = ?, updated_at = ? WHERE id = ?", (status, now, memory_id))
    return get_memory(memory_id)


def delete_memory(memory_id: int) -> bool:
    with get_connection() as conn:
        row = conn.execute("SELECT id FROM agent_memories WHERE id = ?", (memory_id,)).fetchone()
        if not row:
            return False
        conn.execute("DELETE FROM agent_memory_fts WHERE memory_id = ?", (memory_id,))
        conn.execute("DELETE FROM agent_memories WHERE id = ?", (memory_id,))
    return True


def search_active_memories(query: str, limit: int = 8, repo_id: Optional[int] = None) -> List[Dict[str, Any]]:
    clean = _clean_text(query)
    if not clean:
        return []
    tokens = re.findall(r"[\w\u4e00-\u9fff]+", clean)
    match_query = " OR ".join(tokens[:8]) if tokens else clean
    params: List[Any] = [match_query, limit]
    repo_filter = ""
    if repo_id is not None:
        repo_filter = " AND (m.repo_id IS NULL OR m.repo_id = ?)"
        params = [match_query, repo_id, limit]
    try:
        rows = fetch_all(
            f"""
            SELECT m.*
            FROM agent_memory_fts f
            JOIN agent_memories m ON m.id = f.memory_id
            WHERE agent_memory_fts MATCH ?
              AND m.status = 'active'
              {repo_filter}
            ORDER BY bm25(agent_memory_fts)
            LIMIT ?
            """,
            tuple(params),
        )
    except Exception:
        rows = []
    if rows:
        now = utc_now()
        ids = [row["id"] for row in rows]
        placeholders = ", ".join("?" for _ in ids)
        with get_connection() as conn:
            conn.execute(f"UPDATE agent_memories SET last_used_at = ? WHERE id IN ({placeholders})", (now, *ids))
        return rows

    like = f"%{clean}%"
    params = [like]
    where = "status = 'active' AND content LIKE ?"
    if repo_id is not None:
        where += " AND (repo_id IS NULL OR repo_id = ?)"
        params.append(repo_id)
    params.append(limit)
    return fetch_all(f"SELECT * FROM agent_memories WHERE {where} ORDER BY updated_at DESC LIMIT ?", tuple(params))
