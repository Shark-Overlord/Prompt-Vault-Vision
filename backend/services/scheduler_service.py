from __future__ import annotations

import asyncio
import json
import re
import time
from datetime import datetime, time as dt_time, timedelta, timezone
from typing import Any, Dict, List, Optional

from database import DEFAULT_KEYWORDS, fetch_all, fetch_one, get_connection, row_to_dict, utc_now
from models.schemas import ScheduledTaskCreate, ScheduledTaskUpdate
from services.github_search_service import run_incremental_search


SCAN_INTERVAL_SECONDS = 30
MAX_PER_KEYWORD_LIMIT = 50
LOCAL_TZ = timezone(timedelta(hours=8), name="Asia/Shanghai")
TASK_TYPE_GITHUB = "github_incremental_search"
TASK_TYPE_REPO_SCAN = "repo_scan"
VALID_TASK_TYPES = {TASK_TYPE_GITHUB}
VALID_STATUSES = {"active", "paused"}
VALID_SCHEDULE_TYPES = {"interval_minutes", "daily_time", "weekly_time"}
VALID_REPO_CATEGORIES = {
    "web_ui_prompt",
    "image_generation_prompt",
    "image_editing_prompt",
    "video_generation_prompt",
}
TIME_RE = re.compile(r"^\d{2}:\d{2}$")
DEFAULT_TASK_CATEGORY_TIMES = {
    "web_ui_prompt": ("默认检索｜Web UI Prompt", "09:10"),
    "image_generation_prompt": ("默认检索｜图像生成 Prompt", "12:10"),
    "image_editing_prompt": ("默认检索｜图像编辑 Prompt", "15:10"),
    "video_generation_prompt": ("默认检索｜视频生成 Prompt", "18:10"),
}

_scheduler_task: Optional[asyncio.Task] = None
_task_locks: Dict[int, asyncio.Lock] = {}


def _json_dumps(value: Optional[List[str]]) -> Optional[str]:
    if value is None:
        return None
    cleaned = [item.strip() for item in value if item and item.strip()]
    return json.dumps(cleaned, ensure_ascii=False)


def _json_loads(value: Optional[str]) -> Optional[List[str]]:
    if not value:
        return None
    try:
        data = json.loads(value)
    except json.JSONDecodeError:
        return None
    if not isinstance(data, list):
        return None
    return [str(item) for item in data if str(item).strip()]


def _parse_utc(value: Optional[str]) -> Optional[datetime]:
    if not value:
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _format_utc(value: datetime) -> str:
    return value.astimezone(timezone.utc).replace(microsecond=0).isoformat()


def _parse_hhmm(value: Optional[str], field: str) -> dt_time:
    if not value or not TIME_RE.match(value):
        raise ValueError(f"{field} 必须使用 HH:MM 格式")
    hour, minute = [int(part) for part in value.split(":", 1)]
    if hour > 23 or minute > 59:
        raise ValueError(f"{field} 必须是有效时间")
    return dt_time(hour=hour, minute=minute, tzinfo=LOCAL_TZ)


def _task_to_public(task: Dict[str, Any]) -> Dict[str, Any]:
    public = dict(task)
    public["categories"] = _json_loads(public.get("categories"))
    public["keywords"] = _json_loads(public.get("keywords"))
    public["allow_anonymous"] = bool(public.get("allow_anonymous"))
    public["running"] = bool(public.get("running"))
    return public


def validate_task_payload(data: Dict[str, Any]) -> Dict[str, Any]:
    name = (data.get("name") or "").strip()
    if not name:
        raise ValueError("任务名称不能为空")

    task_type = data.get("task_type") or TASK_TYPE_GITHUB
    if task_type not in VALID_TASK_TYPES:
        raise ValueError("定时任务只支持 GitHub 仓库发现；仓库内容扫描请在资源库页面手动或批量执行")

    status = data.get("status") or "paused"
    if status not in VALID_STATUSES:
        raise ValueError("任务状态只能是 active 或 paused")

    schedule_type = data.get("schedule_type")
    if schedule_type not in VALID_SCHEDULE_TYPES:
        raise ValueError("计划类型必须是 interval_minutes、daily_time 或 weekly_time")

    interval_minutes = data.get("interval_minutes")
    daily_time = data.get("daily_time")
    weekly_day = data.get("weekly_day")
    weekly_time = data.get("weekly_time")

    if schedule_type == "interval_minutes":
        if interval_minutes is None or int(interval_minutes) <= 0:
            raise ValueError("interval_minutes 必须大于 0")
        interval_minutes = int(interval_minutes)
        daily_time = None
        weekly_day = None
        weekly_time = None
    elif schedule_type == "daily_time":
        _parse_hhmm(daily_time, "daily_time")
        interval_minutes = None
        weekly_day = None
        weekly_time = None
    else:
        if weekly_day is None or int(weekly_day) < 0 or int(weekly_day) > 6:
            raise ValueError("weekly_day 必须是 0-6，0 表示周一")
        _parse_hhmm(weekly_time, "weekly_time")
        interval_minutes = None
        daily_time = None
        weekly_day = int(weekly_day)

    per_keyword_limit = min(max(int(data.get("per_keyword_limit") or 5), 1), MAX_PER_KEYWORD_LIMIT)
    categories = data.get("categories")
    if categories:
        invalid_categories = [category for category in categories if category not in VALID_REPO_CATEGORIES]
        if invalid_categories:
            raise ValueError("定时任务只能检索 Web UI、图像生成、图像编辑、视频生成这四类仓库")

    return {
        **data,
        "name": name,
        "task_type": task_type,
        "status": status,
        "schedule_type": schedule_type,
        "interval_minutes": interval_minutes,
        "daily_time": daily_time,
        "weekly_day": weekly_day,
        "weekly_time": weekly_time,
        "timezone": "Asia/Shanghai",
        "per_keyword_limit": per_keyword_limit,
        "allow_anonymous": 1 if data.get("allow_anonymous") else 0,
    }


def calculate_next_run_at(task: Dict[str, Any], from_dt: Optional[datetime] = None) -> Optional[str]:
    if task.get("status") != "active":
        return None

    now_utc = (from_dt or datetime.now(timezone.utc)).astimezone(timezone.utc)
    now_local = now_utc.astimezone(LOCAL_TZ)
    schedule_type = task.get("schedule_type")

    if schedule_type == "interval_minutes":
        minutes = int(task.get("interval_minutes") or 0)
        if minutes <= 0:
            return None
        return _format_utc(now_utc + timedelta(minutes=minutes))

    if schedule_type == "daily_time":
        target_time = _parse_hhmm(task.get("daily_time"), "daily_time")
        next_local = datetime.combine(now_local.date(), target_time)
        if next_local <= now_local:
            next_local += timedelta(days=1)
        return _format_utc(next_local)

    if schedule_type == "weekly_time":
        target_time = _parse_hhmm(task.get("weekly_time"), "weekly_time")
        target_day = int(task.get("weekly_day"))
        days_ahead = (target_day - now_local.weekday()) % 7
        next_local = datetime.combine(now_local.date() + timedelta(days=days_ahead), target_time)
        if next_local <= now_local:
            next_local += timedelta(days=7)
        return _format_utc(next_local)

    return None


def list_tasks() -> List[Dict[str, Any]]:
    return [_task_to_public(row) for row in fetch_all("SELECT * FROM scheduled_tasks ORDER BY updated_at DESC, id DESC")]


def list_tasks_paginated(page: int = 1, page_size: int = 20, search: Optional[str] = None, status: Optional[str] = None) -> Dict[str, Any]:
    page = max(1, int(page or 1))
    page_size = min(max(1, int(page_size or 20)), 100)
    offset = (page - 1) * page_size
    where = ["1 = 1"]
    params: List[Any] = []
    if search:
        where.append("(name LIKE ? OR categories LIKE ? OR keywords LIKE ? OR last_summary LIKE ? OR last_error LIKE ?)")
        term = f"%{search}%"
        params.extend([term, term, term, term, term])
    if status:
        where.append("status = ?")
        params.append(status)
    clause = " AND ".join(where)
    with get_connection() as conn:
        total = int(conn.execute(f"SELECT COUNT(*) FROM scheduled_tasks WHERE {clause}", tuple(params)).fetchone()[0])
        rows = conn.execute(
            f"SELECT * FROM scheduled_tasks WHERE {clause} ORDER BY updated_at DESC, id DESC LIMIT ? OFFSET ?",
            (*params, page_size, offset),
        ).fetchall()
    return {
        "items": [_task_to_public(row_to_dict(row) or {}) for row in rows],
        "page": page,
        "page_size": page_size,
        "total": total,
    }


def get_task(task_id: int) -> Optional[Dict[str, Any]]:
    task = fetch_one("SELECT * FROM scheduled_tasks WHERE id = ?", (task_id,))
    return _task_to_public(task) if task else None


def create_task(payload: ScheduledTaskCreate) -> Dict[str, Any]:
    data = validate_task_payload(payload.model_dump())
    now = utc_now()
    next_run_at = calculate_next_run_at(data)
    with get_connection() as conn:
        cursor = conn.execute(
            """
            INSERT INTO scheduled_tasks
                (name, task_type, status, schedule_type, interval_minutes, daily_time, weekly_day, weekly_time,
                 timezone, categories, keywords, per_keyword_limit, allow_anonymous, next_run_at,
                 created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                data["name"],
                data["task_type"],
                data["status"],
                data["schedule_type"],
                data["interval_minutes"],
                data["daily_time"],
                data["weekly_day"],
                data["weekly_time"],
                data["timezone"],
                _json_dumps(data.get("categories")),
                _json_dumps(data.get("keywords")),
                data["per_keyword_limit"],
                data["allow_anonymous"],
                next_run_at,
                now,
                now,
            ),
        )
        task_id = int(cursor.lastrowid)
    task = get_task(task_id)
    if not task:
        raise ValueError("任务创建失败")
    return task


def ensure_default_category_tasks() -> List[Dict[str, Any]]:
    now = utc_now()
    created: List[Dict[str, Any]] = []
    keywords_by_category: Dict[str, List[str]] = {}
    for keyword, category in DEFAULT_KEYWORDS:
        keywords_by_category.setdefault(category, []).append(keyword)

    with get_connection() as conn:
        existing_names = {
            row["name"]
            for row in conn.execute(
                "SELECT name FROM scheduled_tasks WHERE name LIKE '默认检索｜%'"
            ).fetchall()
        }

        for category, (name, daily_time) in DEFAULT_TASK_CATEGORY_TIMES.items():
            if name in existing_names:
                continue
            data = validate_task_payload(
                {
                    "name": name,
                    "task_type": TASK_TYPE_GITHUB,
                    "status": "paused",
                    "schedule_type": "daily_time",
                    "daily_time": daily_time,
                    "categories": [category],
                    "keywords": keywords_by_category.get(category, []),
                    "per_keyword_limit": 30,
                    "allow_anonymous": False,
                }
            )
            next_run_at = calculate_next_run_at(data)
            cursor = conn.execute(
                """
                INSERT INTO scheduled_tasks
                    (name, task_type, status, schedule_type, interval_minutes, daily_time, weekly_day, weekly_time,
                     timezone, categories, keywords, per_keyword_limit, allow_anonymous, next_run_at,
                     created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    data["name"],
                    data["task_type"],
                    data["status"],
                    data["schedule_type"],
                    data["interval_minutes"],
                    data["daily_time"],
                    data["weekly_day"],
                    data["weekly_time"],
                    data["timezone"],
                    _json_dumps(data.get("categories")),
                    _json_dumps(data.get("keywords")),
                    data["per_keyword_limit"],
                    data["allow_anonymous"],
                    next_run_at,
                    now,
                    now,
                ),
            )
            created.append({"id": int(cursor.lastrowid), "name": name, "category": category})

        conn.execute(
            """
            UPDATE scheduled_tasks
            SET status = 'paused',
                next_run_at = NULL,
                running = 0,
                last_summary = COALESCE(last_summary, '') || char(10) || ?,
                updated_at = ?
            WHERE name = 'GitHub 增量搜索'
              AND categories IS NULL
              AND keywords IS NULL
              AND status = 'active'
            """,
            ("已由四类默认检索任务取代，避免全量关键词任务反复产生低质量跳过记录。", now),
        )
        conn.execute(
            """
            UPDATE scheduled_tasks
            SET status = 'paused',
                next_run_at = NULL,
                running = 0,
                last_summary = COALESCE(last_summary, '') || char(10) || ?,
                updated_at = ?
            WHERE task_type = 'repo_scan'
            """,
            ("资源库内容扫描已从定时任务移除；请在资源库页面对仓库执行手动或批量扫描。", now),
        )

    return created


def repair_stale_next_run_times(from_dt: Optional[datetime] = None) -> int:
    base = (from_dt or datetime.now(timezone.utc)).astimezone(timezone.utc)
    now = _format_utc(base)
    repaired = 0
    active_tasks = fetch_all(
        """
        SELECT * FROM scheduled_tasks
        WHERE status = 'active'
          AND task_type = ?
          AND running = 0
        """,
        (TASK_TYPE_GITHUB,),
    )
    with get_connection() as conn:
        for task in active_tasks:
            next_dt = _parse_utc(task.get("next_run_at"))
            if next_dt and next_dt > base:
                continue
            public_task = _task_to_public(task)
            next_run_at = calculate_next_run_at(public_task, base)
            conn.execute(
                "UPDATE scheduled_tasks SET next_run_at = ?, updated_at = ? WHERE id = ?",
                (next_run_at, now, task["id"]),
            )
            repaired += 1
    return repaired


def update_task(task_id: int, payload: ScheduledTaskUpdate) -> Optional[Dict[str, Any]]:
    existing = fetch_one("SELECT * FROM scheduled_tasks WHERE id = ?", (task_id,))
    if not existing:
        return None

    merged = _task_to_public(existing)
    data = payload.model_dump(exclude_unset=True)
    for key, value in data.items():
        merged[key] = value

    validated = validate_task_payload(merged)
    next_run_at = calculate_next_run_at(validated)
    now = utc_now()
    with get_connection() as conn:
        conn.execute(
            """
            UPDATE scheduled_tasks
            SET name = ?, status = ?, schedule_type = ?, interval_minutes = ?, daily_time = ?,
                weekly_day = ?, weekly_time = ?, timezone = ?, categories = ?, keywords = ?,
                per_keyword_limit = ?, allow_anonymous = ?, next_run_at = ?, updated_at = ?
            WHERE id = ?
            """,
            (
                validated["name"],
                validated["status"],
                validated["schedule_type"],
                validated["interval_minutes"],
                validated["daily_time"],
                validated["weekly_day"],
                validated["weekly_time"],
                validated["timezone"],
                _json_dumps(validated.get("categories")),
                _json_dumps(validated.get("keywords")),
                validated["per_keyword_limit"],
                validated["allow_anonymous"],
                next_run_at,
                now,
                task_id,
            ),
        )
    return get_task(task_id)


def delete_task(task_id: int) -> bool:
    with get_connection() as conn:
        existing = conn.execute("SELECT id FROM scheduled_tasks WHERE id = ?", (task_id,)).fetchone()
        if not existing:
            return False
        conn.execute("DELETE FROM task_runs WHERE task_id = ?", (task_id,))
        conn.execute("DELETE FROM scheduled_tasks WHERE id = ?", (task_id,))
    _task_locks.pop(task_id, None)
    return True


def list_task_runs(task_id: int, limit: int = 50) -> List[Dict[str, Any]]:
    return fetch_all("SELECT * FROM task_runs WHERE task_id = ? ORDER BY created_at DESC LIMIT ?", (task_id, limit))


def list_task_runs_paginated(task_id: int, page: int = 1, page_size: int = 50) -> Dict[str, Any]:
    page = max(1, int(page or 1))
    page_size = min(max(1, int(page_size or 50)), 200)
    offset = (page - 1) * page_size
    with get_connection() as conn:
        total = int(conn.execute("SELECT COUNT(*) FROM task_runs WHERE task_id = ?", (task_id,)).fetchone()[0])
        rows = conn.execute(
            "SELECT * FROM task_runs WHERE task_id = ? ORDER BY created_at DESC LIMIT ? OFFSET ?",
            (task_id, page_size, offset),
        ).fetchall()
    return {
        "items": [row_to_dict(row) or {} for row in rows],
        "page": page,
        "page_size": page_size,
        "total": total,
    }


def _insert_skipped_run(task: Dict[str, Any], trigger_type: str, reason: str, advance_schedule: bool = True) -> Dict[str, Any]:
    now = utc_now()
    next_run_at = calculate_next_run_at(task) if advance_schedule else task.get("next_run_at")
    with get_connection() as conn:
        cursor = conn.execute(
            """
            INSERT INTO task_runs
                (task_id, task_name, task_type, trigger_type, status, started_at, finished_at,
                 duration_ms, summary, error, result_json, created_at)
            VALUES (?, ?, ?, ?, 'skipped', ?, ?, 0, ?, ?, NULL, ?)
            """,
            (task["id"], task["name"], task["task_type"], trigger_type, now, now, reason, reason, now),
        )
        conn.execute(
            """
            UPDATE scheduled_tasks
            SET next_run_at = ?, last_run_at = ?, last_finished_at = ?, last_status = 'skipped',
                last_summary = ?, last_error = ?, updated_at = ?
            WHERE id = ?
            """,
            (next_run_at, now, now, reason, reason, now, task["id"]),
        )
        run_id = int(cursor.lastrowid)
    return fetch_one("SELECT * FROM task_runs WHERE id = ?", (run_id,)) or {}


async def run_task(task_id: int, trigger_type: str = "manual") -> Dict[str, Any]:
    task = get_task(task_id)
    if not task:
        raise ValueError("定时任务不存在")

    lock = _task_locks.setdefault(task_id, asyncio.Lock())
    if lock.locked() or task.get("running"):
        return _insert_skipped_run(task, trigger_type, "上一次任务仍在运行，本次触发已跳过。", trigger_type == "scheduled")

    async with lock:
        task = get_task(task_id)
        if not task:
            raise ValueError("定时任务不存在")
        if task.get("running"):
            return _insert_skipped_run(task, trigger_type, "上一次任务仍在运行，本次触发已跳过。", trigger_type == "scheduled")

        started_at = utc_now()
        start_ticks = time.perf_counter()
        start_next_run_at = calculate_next_run_at(task) if trigger_type == "scheduled" else task.get("next_run_at")
        with get_connection() as conn:
            cursor = conn.execute(
                """
                INSERT INTO task_runs
                    (task_id, task_name, task_type, trigger_type, status, started_at, created_at)
                VALUES (?, ?, ?, ?, 'started', ?, ?)
                """,
                (task["id"], task["name"], task["task_type"], trigger_type, started_at, started_at),
            )
            conn.execute(
                "UPDATE scheduled_tasks SET running = 1, next_run_at = ?, last_run_at = ?, updated_at = ? WHERE id = ?",
                (start_next_run_at, started_at, started_at, task["id"]),
            )
            run_id = int(cursor.lastrowid)

        status = "success"
        summary = ""
        error = None
        result: Dict[str, Any] = {}
        try:
            if task.get("task_type") != TASK_TYPE_GITHUB:
                status = "skipped"
                summary = "旧的资源库扫描定时任务已停用；仓库内容扫描请在资源库页面手动或批量执行。"
                result = {"status": "skipped", "summary": summary}
            else:
                result = await run_incremental_search(
                    categories=task.get("categories"),
                    keywords=task.get("keywords"),
                    per_keyword_limit=int(task.get("per_keyword_limit") or 5),
                    allow_anonymous=bool(task.get("allow_anonymous")),
                )
                summary = str(result.get("summary") or result.get("status") or "GitHub 仓库发现完成。")
                if result.get("status") == "needs_token":
                    status = "failed"
                    error = summary
        except Exception as exc:
            status = "failed"
            summary = "定时任务执行失败。"
            error = str(exc)
            result = {"status": "error", "error": error}

        finished_at = utc_now()
        duration_ms = int((time.perf_counter() - start_ticks) * 1000)
        refreshed = get_task(task_id) or task
        next_run_at = calculate_next_run_at(refreshed, _parse_utc(finished_at) or datetime.now(timezone.utc))
        with get_connection() as conn:
            conn.execute(
                """
                UPDATE task_runs
                SET status = ?, finished_at = ?, duration_ms = ?, summary = ?, error = ?, result_json = ?
                WHERE id = ?
                """,
                (status, finished_at, duration_ms, summary, error, json.dumps(result, ensure_ascii=False), run_id),
            )
            conn.execute(
                """
                UPDATE scheduled_tasks
                SET running = 0,
                    next_run_at = ?,
                    last_finished_at = ?,
                    last_status = ?,
                    last_summary = ?,
                    last_error = ?,
                    updated_at = ?
                WHERE id = ?
                """,
                (next_run_at, finished_at, status, summary, error, finished_at, task_id),
            )
        return fetch_one("SELECT * FROM task_runs WHERE id = ?", (run_id,)) or {}


async def scan_due_tasks() -> None:
    now = utc_now()
    due_tasks = fetch_all(
        """
        SELECT * FROM scheduled_tasks
        WHERE status = 'active'
          AND next_run_at IS NOT NULL
          AND next_run_at <= ?
        ORDER BY next_run_at ASC, id ASC
        """,
        (now,),
    )
    for task in due_tasks:
        asyncio.create_task(run_task(int(task["id"]), trigger_type="scheduled"))


async def _scheduler_loop() -> None:
    while True:
        try:
            await scan_due_tasks()
        except Exception as exc:
            print(f"[scheduler] scan failed: {exc}")
        await asyncio.sleep(SCAN_INTERVAL_SECONDS)


def start_scheduler() -> None:
    global _scheduler_task
    if _scheduler_task and not _scheduler_task.done():
        return
    ensure_default_category_tasks()
    with get_connection() as conn:
        conn.execute("UPDATE scheduled_tasks SET running = 0 WHERE running = 1")
        conn.execute(
            """
            UPDATE scheduled_tasks
            SET status = 'paused', next_run_at = NULL, running = 0, updated_at = ?
            WHERE task_type = 'repo_scan'
            """,
            (utc_now(),),
        )
    repair_stale_next_run_times()
    _scheduler_task = asyncio.create_task(_scheduler_loop())


async def stop_scheduler() -> None:
    global _scheduler_task
    if not _scheduler_task:
        return
    _scheduler_task.cancel()
    try:
        await _scheduler_task
    except asyncio.CancelledError:
        pass
    _scheduler_task = None
