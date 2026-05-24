from __future__ import annotations

import asyncio
import json
import re
from typing import Any, Dict, List, Optional

from database import fetch_one, get_connection, paginate, row_to_dict, rows_to_dicts, utc_now
from services.ai_config_service import chat_completion


ACTIVE_RUN_STATUSES = {"queued", "running", "cancel_requested"}
VALID_SUGGESTION_STATUSES = {"pending_review", "accepted", "rejected", "failed", "superseded"}
STALE_TRANSLATION_MARKERS = [
    "该 Prompt 适合",
    "该 prompt 适合",
    "重点参考其主体描述",
    "原文需结合来源 License",
    "原文需要结合来源 License",
    "适合用于图像生成场景",
]

_queue: Optional[asyncio.Queue[int]] = None
_worker_task: Optional[asyncio.Task] = None


def _json_dumps(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False)


def _json_loads(value: Optional[str], fallback: Any = None) -> Any:
    if not value:
        return fallback
    try:
        return json.loads(value)
    except Exception:
        return fallback


def _clean_tag(value: str) -> str:
    return re.sub(r"\s+", "", (value or "").strip().strip("#，,、;；"))


def _normalize_tags(values: Any) -> List[str]:
    if isinstance(values, str):
        raw_items = re.split(r"[,，、;；\n]+", values)
    elif isinstance(values, list):
        raw_items = values
    else:
        raw_items = []
    result: List[str] = []
    seen: set[str] = set()
    for item in raw_items:
        tag = _clean_tag(str(item))
        if not tag or tag in seen:
            continue
        seen.add(tag)
        result.append(tag)
        if len(result) >= 5:
            break
    return result


def _translation_missing_sql(alias: str = "p") -> str:
    column = f"{alias}.prompt_cn_explanation"
    stale_checks = " OR ".join(f"{column} LIKE '%{marker}%'" for marker in STALE_TRANSLATION_MARKERS)
    return f"(COALESCE(TRIM({column}), '') = '' OR {stale_checks})"


def _looks_like_stale_translation(value: Optional[str]) -> bool:
    text = (value or "").strip()
    if not text:
        return True
    return any(marker in text for marker in STALE_TRANSLATION_MARKERS)


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


def _annotation_max_tokens(original_prompt: Optional[str]) -> int:
    prompt_length = len(original_prompt or "")
    return max(1400, min(5000, int(prompt_length * 0.9) + 1000))


def _row(run_id: int) -> Optional[Dict[str, Any]]:
    return fetch_one("SELECT * FROM annotation_runs WHERE id = ?", (run_id,))


def _active_run() -> Optional[Dict[str, Any]]:
    placeholders = ", ".join("?" for _ in ACTIVE_RUN_STATUSES)
    return fetch_one(
        f"SELECT * FROM annotation_runs WHERE status IN ({placeholders}) ORDER BY id DESC LIMIT 1",
        tuple(ACTIVE_RUN_STATUSES),
    )


def _update_run(run_id: int, **fields: Any) -> None:
    if not fields:
        return
    fields["updated_at"] = fields.get("updated_at") or utc_now()
    assignments = ", ".join(f"{key} = ?" for key in fields)
    with get_connection() as conn:
        conn.execute(f"UPDATE annotation_runs SET {assignments} WHERE id = ?", (*fields.values(), run_id))


def mark_stale_annotation_runs_failed() -> None:
    now = utc_now()
    with get_connection() as conn:
        conn.execute(
            """
            UPDATE annotation_runs
            SET status = 'failed',
                error = COALESCE(error, '后端服务重启，未完成标注任务已标记失败。'),
                finished_at = COALESCE(finished_at, ?),
                updated_at = ?
            WHERE status IN ('queued', 'running', 'cancel_requested')
            """,
            (now, now),
        )


def start_annotation_worker() -> None:
    global _queue, _worker_task
    if _worker_task and not _worker_task.done():
        return
    mark_stale_annotation_runs_failed()
    _queue = asyncio.Queue()
    _worker_task = asyncio.create_task(_worker_loop())


async def stop_annotation_worker() -> None:
    global _worker_task
    if not _worker_task:
        return
    _worker_task.cancel()
    try:
        await _worker_task
    except asyncio.CancelledError:
        pass
    _worker_task = None


def _queue_where(filters: Dict[str, Any]) -> tuple[str, List[Any]]:
    where = ["p.image_local_path IS NOT NULL", "p.image_local_path != ''"]
    params: List[Any] = []
    search = (filters.get("search") or "").strip()
    if search:
        term = f"%{search}%"
        where.append("(p.repo_name LIKE ? OR p.original_prompt LIKE ? OR p.prompt_cn_explanation LIKE ?)")
        params.extend([term, term, term])
    if filters.get("category"):
        where.append("p.category = ?")
        params.append(filters["category"])
    if filters.get("scenario"):
        where.append("p.scenario = ?")
        params.append(filters["scenario"])
    if filters.get("selection_status"):
        where.append("p.selection_status = ?")
        params.append(filters["selection_status"])

    annotation_status = filters.get("annotation_status") or "unannotated"
    translation_missing = _translation_missing_sql("p")
    if annotation_status == "unannotated":
        where.append(f"({translation_missing} OR COALESCE(t.tag_count, 0) = 0)")
        where.append("COALESCE(s.latest_suggestion_status, '') != 'pending_review'")
    elif annotation_status == "annotated":
        where.append(f"NOT {translation_missing} AND COALESCE(t.tag_count, 0) > 0")
    elif annotation_status == "has_suggestion":
        where.append("s.latest_suggestion_status = 'pending_review'")
    return " AND ".join(where), params


def _queue_select_sql(where_clause: str) -> str:
    translation_missing = _translation_missing_sql("p")
    return f"""
        SELECT
            p.*,
            COALESCE(t.tag_count, 0) AS tag_count,
            s.latest_suggestion_id,
            s.latest_suggestion_status,
            CASE
                WHEN s.latest_suggestion_status = 'pending_review' THEN 'has_suggestion'
                WHEN NOT {translation_missing} AND COALESCE(t.tag_count, 0) > 0 THEN 'annotated'
                ELSE 'unannotated'
            END AS annotation_status
        FROM prompt_effect_pairs p
        LEFT JOIN (
            SELECT pair_id, COUNT(*) AS tag_count
            FROM pair_tags
            GROUP BY pair_id
        ) t ON t.pair_id = p.id
        LEFT JOIN (
            SELECT ps.pair_id, ps.id AS latest_suggestion_id, ps.status AS latest_suggestion_status
            FROM prompt_pair_annotation_suggestions ps
            JOIN (
                SELECT pair_id, MAX(id) AS max_id
                FROM prompt_pair_annotation_suggestions
                GROUP BY pair_id
            ) latest ON latest.max_id = ps.id
        ) s ON s.pair_id = p.id
        WHERE {where_clause}
    """


def list_annotation_queue(
    page: int = 1,
    page_size: int = 24,
    search: Optional[str] = None,
    category: Optional[str] = None,
    scenario: Optional[str] = None,
    selection_status: Optional[str] = None,
    annotation_status: str = "unannotated",
) -> Dict[str, Any]:
    where, params = _queue_where(
        {
            "search": search,
            "category": category,
            "scenario": scenario,
            "selection_status": selection_status,
            "annotation_status": annotation_status,
        }
    )
    base = _queue_select_sql(where)
    return paginate(
        f"{base} ORDER BY p.updated_at DESC, p.id DESC",
        f"SELECT COUNT(*) FROM ({base}) q",
        tuple(params),
        page,
        page_size,
    )


def _select_pair_ids_for_run(options: Dict[str, Any]) -> List[int]:
    allow_pending_suggestions = bool(options.get("allow_pending_suggestions"))
    explicit_ids = []
    for raw_id in options.get("pair_ids") or []:
        try:
            pair_id = int(raw_id)
        except (TypeError, ValueError):
            continue
        if pair_id > 0 and pair_id not in explicit_ids:
            explicit_ids.append(pair_id)
    limit = min(max(int(options.get("limit") or 20), 1), 200)
    if explicit_ids:
        placeholders = ", ".join("?" for _ in explicit_ids)
        pending_filter = ""
        if not allow_pending_suggestions:
            pending_filter = """
                  AND NOT EXISTS (
                      SELECT 1
                      FROM prompt_pair_annotation_suggestions ps
                      WHERE ps.pair_id = prompt_effect_pairs.id
                        AND ps.status = 'pending_review'
                  )
            """
        with get_connection() as conn:
            rows = conn.execute(
                f"""
                SELECT id
                FROM prompt_effect_pairs
                WHERE id IN ({placeholders})
                  AND image_local_path IS NOT NULL
                  AND image_local_path != ''
                  {pending_filter}
                ORDER BY id DESC
                LIMIT ?
                """,
                (*explicit_ids, limit),
            ).fetchall()
        return [int(row["id"]) for row in rows]

    where, params = _queue_where(options)
    base = _queue_select_sql(where)
    pending_filter = ""
    if not allow_pending_suggestions:
        pending_filter = """
        WHERE NOT EXISTS (
            SELECT 1
            FROM prompt_pair_annotation_suggestions ps
            WHERE ps.pair_id = q.id
              AND ps.status = 'pending_review'
        )
        """
    with get_connection() as conn:
        rows = conn.execute(f"SELECT id FROM ({base}) q {pending_filter} ORDER BY updated_at DESC, id DESC LIMIT ?", (*params, limit)).fetchall()
    return [int(row["id"]) for row in rows]


def create_annotation_run(options: Dict[str, Any]) -> Dict[str, Any]:
    if _queue is None:
        raise ValueError("标注任务队列尚未启动")
    active = _active_run()
    if active:
        raise ValueError(f"已有标注任务 #{active['id']} 正在运行或排队，请先等待完成或取消后再创建新任务。")
    pair_ids = _select_pair_ids_for_run(options)
    if not pair_ids:
        raise ValueError("没有可标注的 Prompt 效果图")
    now = utc_now()
    stored_options = dict(options)
    stored_options["pair_ids"] = pair_ids
    with get_connection() as conn:
        cursor = conn.execute(
            """
            INSERT INTO annotation_runs
                (status, total_items, processed_items, created_suggestions, ai_config_id,
                 options_json, created_at, updated_at, cancel_requested)
            VALUES ('queued', ?, 0, 0, ?, ?, ?, ?, 0)
            """,
            (
                len(pair_ids),
                options.get("ai_config_id"),
                _json_dumps(stored_options),
                now,
                now,
            ),
        )
        run_id = int(cursor.lastrowid)
    _queue.put_nowait(run_id)
    return get_annotation_run(run_id) or {}


def list_annotation_runs(page: int = 1, page_size: int = 20, status: Optional[str] = None) -> Dict[str, Any]:
    where = ["1 = 1"]
    params: List[Any] = []
    if status:
        where.append("status = ?")
        params.append(status)
    clause = " AND ".join(where)
    return paginate(
        f"SELECT * FROM annotation_runs WHERE {clause} ORDER BY id DESC",
        f"SELECT COUNT(*) FROM annotation_runs WHERE {clause}",
        tuple(params),
        page,
        page_size,
    )


def get_annotation_run(run_id: int) -> Optional[Dict[str, Any]]:
    return _row(run_id)


def update_annotation_run(run_id: int, payload: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    run = _row(run_id)
    if not run:
        return None
    if run["status"] in ACTIVE_RUN_STATUSES:
        raise ValueError("运行中或排队中的标注任务不能修改，请先暂停任务。")
    options = _json_loads(run.get("options_json"), {}) or {}
    if "limit" in payload and payload["limit"] is not None:
        options["limit"] = min(max(int(payload["limit"]), 1), 200)
        options.pop("pair_ids", None)
    if "ai_config_id" in payload:
        options["ai_config_id"] = payload.get("ai_config_id")
    if "allow_pending_suggestions" in payload and payload["allow_pending_suggestions"] is not None:
        options["allow_pending_suggestions"] = bool(payload["allow_pending_suggestions"])
    if payload.get("annotation_status"):
        options["annotation_status"] = payload["annotation_status"]
    updates = {
        "ai_config_id": options.get("ai_config_id"),
        "options_json": _json_dumps(options),
        "updated_at": utc_now(),
    }
    _update_run(run_id, **updates)
    return _row(run_id)


def rerun_annotation_run(run_id: int) -> Optional[Dict[str, Any]]:
    run = _row(run_id)
    if not run:
        return None
    options = _json_loads(run.get("options_json"), {}) or {}
    return create_annotation_run(options)


def delete_annotation_run(run_id: int) -> Optional[Dict[str, Any]]:
    run = _row(run_id)
    if not run:
        return None
    if run["status"] in ACTIVE_RUN_STATUSES:
        raise ValueError("运行中或排队中的标注任务不能删除，请先暂停任务。")
    with get_connection() as conn:
        conn.execute("UPDATE prompt_pair_annotation_suggestions SET run_id = NULL WHERE run_id = ?", (run_id,))
        conn.execute("DELETE FROM annotation_runs WHERE id = ?", (run_id,))
    return run


def cancel_annotation_run(run_id: int) -> Optional[Dict[str, Any]]:
    run = _row(run_id)
    if not run:
        return None
    if run["status"] == "queued":
        _update_run(run_id, status="canceled", cancel_requested=1, finished_at=utc_now(), error="用户取消")
    elif run["status"] == "running":
        _update_run(run_id, status="cancel_requested", cancel_requested=1)
    elif run["status"] == "cancel_requested":
        _update_run(run_id, cancel_requested=1)
    return _row(run_id)


async def _worker_loop() -> None:
    assert _queue is not None
    while True:
        run_id = await _queue.get()
        try:
            await _execute_run(run_id)
        finally:
            _queue.task_done()


async def _execute_run(run_id: int) -> None:
    run = _row(run_id)
    if not run:
        return
    if run.get("cancel_requested") or run.get("status") == "canceled":
        _update_run(run_id, status="canceled", finished_at=utc_now(), error="用户取消")
        return

    options = _json_loads(run.get("options_json"), {}) or {}
    pair_ids = [int(pair_id) for pair_id in options.get("pair_ids") or []]
    ai_config_id = options.get("ai_config_id")
    now = utc_now()
    _update_run(run_id, status="running", started_at=now, updated_at=now)

    created = 0
    processed = 0
    try:
        for pair_id in pair_ids:
            refreshed = _row(run_id)
            if refreshed and (refreshed.get("cancel_requested") or refreshed.get("status") == "cancel_requested"):
                _update_run(run_id, status="canceled", current_pair_id=pair_id, processed_items=processed, created_suggestions=created, finished_at=utc_now(), error="用户取消")
                return
            _update_run(run_id, current_pair_id=pair_id)
            pair = _get_pair_for_annotation(pair_id)
            if not pair:
                processed += 1
                _update_run(run_id, processed_items=processed)
                continue
            suggestion = await generate_annotation_suggestion(pair, run_id=run_id, ai_config_id=ai_config_id)
            processed += 1
            if suggestion.get("status") == "pending_review":
                created += 1
            _update_run(run_id, processed_items=processed, created_suggestions=created)
        _update_run(run_id, status="succeeded", current_pair_id=None, processed_items=processed, created_suggestions=created, finished_at=utc_now())
    except Exception as exc:
        _update_run(run_id, status="failed", error=str(exc), processed_items=processed, created_suggestions=created, finished_at=utc_now())


def _get_pair_for_annotation(pair_id: int) -> Optional[Dict[str, Any]]:
    pair = fetch_one("SELECT * FROM prompt_effect_pairs WHERE id = ?", (pair_id,))
    if not pair:
        return None
    tags = _pair_tags(pair_id)
    pair["tags"] = tags
    return pair


def _pair_tags(pair_id: int) -> List[Dict[str, Any]]:
    with get_connection() as conn:
        rows = conn.execute(
            """
            SELECT tags.*
            FROM tags
            JOIN pair_tags ON pair_tags.tag_id = tags.id
            WHERE pair_tags.pair_id = ?
            ORDER BY tags.name
            """,
            (pair_id,),
        ).fetchall()
    return rows_to_dicts(rows)


async def generate_annotation_suggestion(pair: Dict[str, Any], run_id: Optional[int] = None, ai_config_id: Optional[int] = None) -> Dict[str, Any]:
    original_prompt = str(pair.get("original_prompt") or "")
    system_prompt = (
        "你是视觉 Prompt 资产库的中文翻译与标签标注助手。"
        "cn_explanation 必须是 original_prompt 的忠实中文翻译，不是理解后的解释、摘要、优化版或新 Prompt。"
        "不要新增原文没有的信息，不要删减关键视觉元素、镜头、材质、风格、构图、参数或约束。"
        "如果原文包含模型名、参数、英文风格词、专有名词、括号、序号、列表结构，请尽量保留结构与信息，只把可翻译的英文自然译成中文。"
        "标签才从原始 Prompt 中提炼，必须是中文关键词，数量 4 到 5 个。"
        "只返回 JSON，不要 Markdown。"
    )
    user_payload = {
        "task": "为 Prompt 效果图生成待人工确认的中文翻译和中文标签",
        "pair": {
            "id": pair.get("id"),
            "repo_name": pair.get("repo_name"),
            "category": pair.get("category"),
            "scenario": pair.get("scenario"),
            "visual_style": pair.get("visual_style"),
            "original_prompt": original_prompt,
            "current_cn_explanation": pair.get("prompt_cn_explanation"),
            "current_tags": [tag.get("name") for tag in pair.get("tags") or []],
        },
        "required_output_schema": {
            "prompt_language": "english|chinese|mixed|unknown",
            "cn_explanation": "original_prompt 的忠实中文翻译；不是解释、概括、改写或重新创作",
            "tags_cn": ["4到5个中文关键词"],
            "image_type_cn": "这类效果图类型，例如产品海报、写实摄影、UI界面、电影感视频帧",
            "confidence": "0-100 integer",
            "reason_cn": "中文说明：标签是从原始 Prompt 的哪些关键词提炼出来的",
        },
    }
    try:
        result = await chat_completion(
            [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": _json_dumps(user_payload)},
            ],
            ai_config_id=ai_config_id,
            temperature=0.1,
            max_tokens=_annotation_max_tokens(original_prompt),
        )
        raw_content = result.get("content") or ""
        payload = _extract_json_object(raw_content)
        cn_explanation = str(payload.get("cn_explanation") or payload.get("suggested_cn_explanation") or "").strip()
        tags = _normalize_tags(payload.get("tags_cn") or payload.get("tags") or [])
        if not cn_explanation or not tags:
            preview = re.sub(r"\s+", " ", raw_content).strip()[:500]
            raise ValueError(f"AI 返回缺少 cn_explanation 或 tags_cn，未生成有效标注草稿。返回片段：{preview}")
        suggestion = {
            "prompt_language": str(payload.get("prompt_language") or "unknown")[:40],
            "suggested_cn_explanation": cn_explanation,
            "suggested_tags_json": _json_dumps(tags),
            "image_type_cn": str(payload.get("image_type_cn") or "").strip(),
            "reason_cn": str(payload.get("reason_cn") or "").strip(),
            "confidence": max(0, min(int(payload.get("confidence") or 70), 100)),
            "status": "pending_review",
            "error": None,
        }
    except Exception as exc:
        suggestion = {
            "prompt_language": "unknown",
            "suggested_cn_explanation": "",
            "suggested_tags_json": "[]",
            "image_type_cn": "",
            "reason_cn": "",
            "confidence": 0,
            "status": "failed",
            "error": str(exc),
        }
    return _insert_suggestion(int(pair["id"]), suggestion, run_id=run_id)


def _insert_suggestion(pair_id: int, suggestion: Dict[str, Any], run_id: Optional[int] = None) -> Dict[str, Any]:
    now = utc_now()
    with get_connection() as conn:
        conn.execute(
            """
            UPDATE prompt_pair_annotation_suggestions
            SET status = 'superseded', updated_at = ?
            WHERE pair_id = ? AND status = 'pending_review'
            """,
            (now, pair_id),
        )
        cursor = conn.execute(
            """
            INSERT INTO prompt_pair_annotation_suggestions
                (run_id, pair_id, status, prompt_language, suggested_cn_explanation,
                 suggested_tags_json, image_type_cn, reason_cn, confidence, error, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                run_id,
                pair_id,
                suggestion["status"],
                suggestion["prompt_language"],
                suggestion["suggested_cn_explanation"],
                suggestion["suggested_tags_json"],
                suggestion["image_type_cn"],
                suggestion["reason_cn"],
                suggestion["confidence"],
                suggestion["error"],
                now,
                now,
            ),
        )
        suggestion_id = int(cursor.lastrowid)
    return get_annotation_suggestion(suggestion_id) or {}


def list_annotation_suggestions(
    page: int = 1,
    page_size: int = 20,
    status: Optional[str] = None,
    search: Optional[str] = None,
    run_id: Optional[int] = None,
) -> Dict[str, Any]:
    where = ["1 = 1"]
    params: List[Any] = []
    if status and status != "all":
        where.append("s.status = ?")
        params.append(status)
    if run_id:
        where.append("s.run_id = ?")
        params.append(run_id)
    if search:
        term = f"%{search.strip()}%"
        where.append("(p.repo_name LIKE ? OR p.original_prompt LIKE ? OR s.suggested_cn_explanation LIKE ? OR s.suggested_tags_json LIKE ?)")
        params.extend([term, term, term, term])
    clause = " AND ".join(where)
    return paginate(
        f"""
        SELECT
            s.*,
            p.repo_name,
            p.repo_url,
            p.original_prompt,
            p.prompt_cn_explanation,
            p.image_local_path,
            p.category,
            p.scenario,
            p.selection_status
        FROM prompt_pair_annotation_suggestions s
        JOIN prompt_effect_pairs p ON p.id = s.pair_id
        WHERE {clause}
        ORDER BY s.id DESC
        """,
        f"""
        SELECT COUNT(*)
        FROM prompt_pair_annotation_suggestions s
        JOIN prompt_effect_pairs p ON p.id = s.pair_id
        WHERE {clause}
        """,
        tuple(params),
        page,
        page_size,
    )


def get_annotation_suggestion(suggestion_id: int) -> Optional[Dict[str, Any]]:
    return fetch_one(
        """
        SELECT
            s.*,
            p.repo_name,
            p.repo_url,
            p.original_prompt,
            p.prompt_cn_explanation,
            p.image_local_path,
            p.category,
            p.scenario,
            p.selection_status
        FROM prompt_pair_annotation_suggestions s
        JOIN prompt_effect_pairs p ON p.id = s.pair_id
        WHERE s.id = ?
        """,
        (suggestion_id,),
    )


def update_annotation_suggestion(suggestion_id: int, payload: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    existing = get_annotation_suggestion(suggestion_id)
    if not existing:
        return None
    updates = []
    params: List[Any] = []
    if "suggested_cn_explanation" in payload and payload["suggested_cn_explanation"] is not None:
        updates.append("suggested_cn_explanation = ?")
        params.append(str(payload["suggested_cn_explanation"]).strip())
    if "suggested_tags" in payload and payload["suggested_tags"] is not None:
        updates.append("suggested_tags_json = ?")
        params.append(_json_dumps(_normalize_tags(payload["suggested_tags"])))
    for field in ["image_type_cn", "reason_cn", "confidence"]:
        if field in payload and payload[field] is not None:
            updates.append(f"{field} = ?")
            params.append(payload[field])
    if not updates:
        return existing
    updates.append("updated_at = ?")
    params.append(utc_now())
    with get_connection() as conn:
        conn.execute(f"UPDATE prompt_pair_annotation_suggestions SET {', '.join(updates)} WHERE id = ?", (*params, suggestion_id))
    return get_annotation_suggestion(suggestion_id)


def accept_annotation_suggestion(suggestion_id: int) -> Optional[Dict[str, Any]]:
    suggestion = get_annotation_suggestion(suggestion_id)
    if not suggestion:
        return None
    if _looks_like_stale_translation(suggestion.get("suggested_cn_explanation")):
        raise ValueError("中文翻译仍像解释型文案，请编辑为原始 Prompt 的忠实中文翻译后再接受。")
    tags = _normalize_tags(_json_loads(suggestion.get("suggested_tags_json"), []))
    now = utc_now()
    with get_connection() as conn:
        conn.execute(
            "UPDATE prompt_effect_pairs SET prompt_cn_explanation = ?, updated_at = ? WHERE id = ?",
            (suggestion.get("suggested_cn_explanation") or "", now, suggestion["pair_id"]),
        )
        conn.execute("DELETE FROM pair_tags WHERE pair_id = ?", (suggestion["pair_id"],))
        for tag in tags:
            conn.execute("INSERT OR IGNORE INTO tags (name, type, created_at) VALUES (?, 'annotation', ?)", (tag, now))
            tag_row = conn.execute("SELECT id FROM tags WHERE name = ?", (tag,)).fetchone()
            if tag_row:
                conn.execute("INSERT OR IGNORE INTO pair_tags (pair_id, tag_id) VALUES (?, ?)", (suggestion["pair_id"], tag_row["id"]))
        conn.execute(
            "UPDATE prompt_pair_annotation_suggestions SET status = 'accepted', accepted_at = ?, updated_at = ? WHERE id = ?",
            (now, now, suggestion_id),
        )
    return get_annotation_suggestion(suggestion_id)


def reject_annotation_suggestion(suggestion_id: int) -> Optional[Dict[str, Any]]:
    suggestion = get_annotation_suggestion(suggestion_id)
    if not suggestion:
        return None
    now = utc_now()
    with get_connection() as conn:
        conn.execute("UPDATE prompt_pair_annotation_suggestions SET status = 'rejected', updated_at = ? WHERE id = ?", (now, suggestion_id))
    return get_annotation_suggestion(suggestion_id)
