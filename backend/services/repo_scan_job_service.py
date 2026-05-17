from __future__ import annotations

import asyncio
import json
from typing import Any, Dict, Optional

from database import fetch_all, fetch_one, get_connection, paginate, utc_now
from services.repo_scan_service import RepoScanCancelled, RepoScanError, scan_repo_by_id


_queue: Optional[asyncio.Queue[int]] = None
_worker_task: Optional[asyncio.Task] = None
ACTIVE_RUN_STATUSES = {"queued", "running", "cancel_requested"}


def _row(run_id: int) -> Optional[Dict[str, Any]]:
    return fetch_one("SELECT * FROM repo_scan_runs WHERE id = ?", (run_id,))


def _update(run_id: int, **fields: Any) -> None:
    if not fields:
        return
    fields["updated_at"] = fields.get("updated_at") or utc_now()
    assignments = ", ".join(f"{key} = ?" for key in fields)
    with get_connection() as conn:
        conn.execute(f"UPDATE repo_scan_runs SET {assignments} WHERE id = ?", (*fields.values(), run_id))


def mark_stale_runs_failed() -> None:
    now = utc_now()
    with get_connection() as conn:
        conn.execute(
            """
            UPDATE repo_scan_runs
            SET status = 'failed',
                error = COALESCE(error, '后端服务重启，未完成扫描任务已标记失败。'),
                finished_at = COALESCE(finished_at, ?),
                updated_at = ?
            WHERE status IN ('queued', 'running', 'cancel_requested')
            """,
            (now, now),
        )


def start_repo_scan_worker() -> None:
    global _queue, _worker_task
    if _worker_task and not _worker_task.done():
        return
    mark_stale_runs_failed()
    _queue = asyncio.Queue()
    _worker_task = asyncio.create_task(_worker_loop())


async def stop_repo_scan_worker() -> None:
    global _worker_task
    if not _worker_task:
        return
    _worker_task.cancel()
    try:
        await _worker_task
    except asyncio.CancelledError:
        pass
    _worker_task = None


def create_repo_scan_run(repo_id: int, options: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    repo = fetch_one("SELECT id FROM repos WHERE id = ?", (repo_id,))
    if not repo:
        raise RepoScanError(404, "资源不存在")
    if _queue is None:
        raise RepoScanError(500, "扫描队列尚未启动")
    now = utc_now()
    options = options or {}
    with get_connection() as conn:
        cursor = conn.execute(
            """
            INSERT INTO repo_scan_runs
                (repo_id, use_ai, template_id, status, progress_percent, current_file,
                 options_json, created_at, updated_at)
            VALUES (?, ?, ?, 'queued', 0, '等待扫描队列执行', ?, ?, ?)
            """,
            (
                repo_id,
                1 if options.get("use_ai") or options.get("generate_template") or options.get("scan_mode") == "generate_ai_template" else 0,
                options.get("template_id"),
                json.dumps(options, ensure_ascii=False),
                now,
                now,
            ),
        )
        run_id = int(cursor.lastrowid)
    _queue.put_nowait(run_id)
    run = _row(run_id) or {}
    return {"run_id": run_id, "status": run.get("status"), "repo_id": repo_id, "queued_at": run.get("created_at"), **run}


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
        _update(run_id, status="canceled", finished_at=utc_now(), progress_percent=0, current_file="已取消")
        return
    options: Dict[str, Any] = {}
    try:
        options = json.loads(run.get("options_json") or "{}")
    except Exception:
        options = {}
    options["_run_id"] = run_id
    now = utc_now()
    _update(run_id, status="running", started_at=now, updated_at=now, progress_percent=1, current_file="开始扫描")
    try:
        await scan_repo_by_id(int(run["repo_id"]), options)
    except RepoScanCancelled as exc:
        _update(run_id, status="canceled", error=str(exc), finished_at=utc_now(), current_file="已取消", cancel_requested=1)
    except RepoScanError as exc:
        _update(run_id, status="failed", error=exc.detail, finished_at=utc_now(), current_file="扫描失败")
    except Exception as exc:
        _update(run_id, status="failed", error=str(exc), finished_at=utc_now(), current_file="扫描失败")


def get_repo_scan_run(run_id: int) -> Optional[Dict[str, Any]]:
    return _row(run_id)


def list_all_repo_scan_runs(
    page: int = 1,
    page_size: int = 30,
    status: Optional[str] = None,
    search: Optional[str] = None,
) -> Dict[str, Any]:
    where = ["1 = 1"]
    params: list[Any] = []
    if status and status != "all":
        where.append("r.status = ?")
        params.append(status)
    if search:
        term = f"%{search.strip()}%"
        where.append(
            """(
                repo.repo_name LIKE ? OR repo.owner LIKE ? OR repo.repo_url LIKE ?
                OR r.current_file LIKE ? OR r.summary LIKE ? OR r.error LIKE ?
            )"""
        )
        params.extend([term, term, term, term, term, term])
    clause = " AND ".join(where)
    return paginate(
        f"""
        SELECT
            r.*,
            repo.repo_name AS repo_name,
            repo.owner AS repo_owner,
            repo.repo_url AS repo_url,
            repo.category AS repo_category
        FROM repo_scan_runs r
        LEFT JOIN repos repo ON repo.id = r.repo_id
        WHERE {clause}
        ORDER BY r.id DESC
        """,
        f"""
        SELECT COUNT(*)
        FROM repo_scan_runs r
        LEFT JOIN repos repo ON repo.id = r.repo_id
        WHERE {clause}
        """,
        tuple(params),
        page,
        page_size,
    )


def list_repo_scan_runs(repo_id: int, limit: int = 20) -> list[Dict[str, Any]]:
    return fetch_all(
        """
        SELECT * FROM repo_scan_runs
        WHERE repo_id = ?
        ORDER BY id DESC
        LIMIT ?
        """,
        (repo_id, max(1, min(int(limit or 20), 100))),
    )


def batch_delete_repo_scan_runs(ids: list[int]) -> Dict[str, Any]:
    seen: set[int] = set()
    cleaned_ids: list[int] = []
    for raw_id in ids:
        try:
            run_id = int(raw_id)
        except (TypeError, ValueError):
            continue
        if run_id <= 0 or run_id in seen:
            continue
        seen.add(run_id)
        cleaned_ids.append(run_id)

    if not cleaned_ids:
        return {
            "deleted": True,
            "requested_count": 0,
            "deleted_count": 0,
            "deleted_ids": [],
            "skipped_count": 0,
            "skipped": [],
            "missing_ids": [],
        }

    placeholders = ", ".join("?" for _ in cleaned_ids)
    with get_connection() as conn:
        rows = conn.execute(
            f"SELECT id, status FROM repo_scan_runs WHERE id IN ({placeholders})",
            tuple(cleaned_ids),
        ).fetchall()
        existing = {int(row["id"]): row["status"] for row in rows}
        missing_ids = [run_id for run_id in cleaned_ids if run_id not in existing]
        skipped = [
            {"id": run_id, "status": status, "reason": "任务仍在排队、运行或取消中，不能直接删除"}
            for run_id, status in existing.items()
            if status in ACTIVE_RUN_STATUSES
        ]
        skipped_ids = {item["id"] for item in skipped}
        deleted_ids = [run_id for run_id in cleaned_ids if run_id in existing and run_id not in skipped_ids]
        if deleted_ids:
            delete_placeholders = ", ".join("?" for _ in deleted_ids)
            conn.execute(f"DELETE FROM repo_scan_runs WHERE id IN ({delete_placeholders})", tuple(deleted_ids))

    return {
        "deleted": True,
        "requested_count": len(cleaned_ids),
        "deleted_count": len(deleted_ids),
        "deleted_ids": deleted_ids,
        "skipped_count": len(skipped),
        "skipped": skipped,
        "missing_ids": missing_ids,
    }


def cancel_repo_scan_run(run_id: int) -> Optional[Dict[str, Any]]:
    run = _row(run_id)
    if not run:
        return None
    if run["status"] == "queued":
        _update(run_id, status="canceled", cancel_requested=1, finished_at=utc_now(), current_file="已取消")
    elif run["status"] == "running":
        _update(run_id, status="cancel_requested", cancel_requested=1, current_file="正在取消")
    return _row(run_id)
