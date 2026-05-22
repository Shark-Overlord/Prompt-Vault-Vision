import asyncio
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend"))

import database
from models.schemas import ScheduledTaskCreate, ScheduledTaskUpdate
from services import scheduler_service


@pytest.fixture()
def temp_scheduler_db(tmp_path, monkeypatch):
    monkeypatch.setattr(database, "DB_PATH", tmp_path / "scheduler.db")
    database.init_db()
    scheduler_service._task_locks.clear()
    yield
    scheduler_service._task_locks.clear()


def test_calculate_next_run_at_interval_daily_weekly():
    base = datetime(2026, 5, 16, 0, 0, tzinfo=timezone.utc)

    assert scheduler_service.calculate_next_run_at(
        {"status": "active", "schedule_type": "interval_minutes", "interval_minutes": 30},
        base,
    ) == "2026-05-16T00:30:00+00:00"

    assert scheduler_service.calculate_next_run_at(
        {"status": "active", "schedule_type": "daily_time", "daily_time": "09:00"},
        base,
    ) == "2026-05-16T01:00:00+00:00"

    assert scheduler_service.calculate_next_run_at(
        {"status": "active", "schedule_type": "weekly_time", "weekly_day": 5, "weekly_time": "09:00"},
        base,
    ) == "2026-05-16T01:00:00+00:00"


def test_scheduled_task_crud(temp_scheduler_db):
    task = scheduler_service.create_task(
        ScheduledTaskCreate(
            name="测试增量搜索",
            status="active",
            schedule_type="interval_minutes",
            interval_minutes=15,
            categories=["image_generation_prompt"],
            keywords=["poster prompt"],
            per_keyword_limit=99,
            allow_anonymous=True,
        )
    )

    assert task["id"] > 0
    assert task["per_keyword_limit"] == 50
    assert task["allow_anonymous"] is True
    assert task["next_run_at"]

    updated = scheduler_service.update_task(task["id"], ScheduledTaskUpdate(status="paused"))
    assert updated["status"] == "paused"
    assert updated["next_run_at"] is None

    assert scheduler_service.list_task_runs(task["id"]) == []
    assert scheduler_service.delete_task(task["id"]) is True
    assert scheduler_service.delete_task(task["id"]) is False


def test_run_now_records_github_auth_failure(temp_scheduler_db, monkeypatch):
    async def fake_incremental_search(**kwargs):
        return {"status": "needs_token", "summary": "未连接 GitHub，定时任务失败。"}

    monkeypatch.setattr(scheduler_service, "run_incremental_search", fake_incremental_search)
    task = scheduler_service.create_task(
        ScheduledTaskCreate(
            name="未授权搜索",
            status="paused",
            schedule_type="interval_minutes",
            interval_minutes=60,
            allow_anonymous=False,
        )
    )

    run = asyncio.run(scheduler_service.run_task(task["id"], trigger_type="manual"))

    assert run["status"] == "failed"
    assert "未连接 GitHub" in run["error"]
    refreshed = scheduler_service.get_task(task["id"])
    assert refreshed["running"] is False
    assert refreshed["last_status"] == "failed"


def test_overlap_run_is_skipped(temp_scheduler_db):
    task = scheduler_service.create_task(
        ScheduledTaskCreate(
            name="重叠任务",
            status="active",
            schedule_type="interval_minutes",
            interval_minutes=60,
        )
    )
    next_run_at = task["next_run_at"]
    with database.get_connection() as conn:
        conn.execute("UPDATE scheduled_tasks SET running = 1 WHERE id = ?", (task["id"],))

    run = asyncio.run(scheduler_service.run_task(task["id"], trigger_type="manual"))
    refreshed = scheduler_service.get_task(task["id"])

    assert run["status"] == "skipped"
    assert refreshed["last_status"] == "skipped"
    assert refreshed["next_run_at"] == next_run_at


def test_repair_stale_next_run_times_moves_active_tasks_forward(temp_scheduler_db):
    base = datetime(2026, 5, 17, 2, 0, tzinfo=timezone.utc)
    task = scheduler_service.create_task(
        ScheduledTaskCreate(
            name="stale interval task",
            status="active",
            schedule_type="interval_minutes",
            interval_minutes=15,
        )
    )
    with database.get_connection() as conn:
        conn.execute(
            "UPDATE scheduled_tasks SET next_run_at = ? WHERE id = ?",
            ((base - timedelta(minutes=5)).isoformat(), task["id"]),
        )

    repaired = scheduler_service.repair_stale_next_run_times(base)
    refreshed = scheduler_service.get_task(task["id"])

    assert repaired == 1
    assert refreshed["next_run_at"] == "2026-05-17T02:15:00+00:00"


def test_default_category_tasks_are_seeded_and_broad_task_is_paused(temp_scheduler_db):
    broad = scheduler_service.create_task(
        ScheduledTaskCreate(
            name="GitHub 增量搜索",
            status="active",
            schedule_type="interval_minutes",
            interval_minutes=5,
            per_keyword_limit=5,
        )
    )

    created = scheduler_service.ensure_default_category_tasks()
    tasks = scheduler_service.list_tasks()
    default_tasks = [task for task in tasks if task["name"].startswith("默认检索｜")]
    broad_refreshed = scheduler_service.get_task(broad["id"])

    assert len(created) == 4
    assert len(default_tasks) == 4
    assert {task["categories"][0] for task in default_tasks} == {
        "web_ui_prompt",
        "image_generation_prompt",
        "skill_repository",
        "video_generation_prompt",
    }
    assert all(task["status"] == "paused" for task in default_tasks)
    assert all(task["next_run_at"] is None for task in default_tasks)
    assert all(task["keywords"] for task in default_tasks)
    assert broad_refreshed["status"] == "paused"
