import asyncio
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend"))

import database
from services import repo_scan_job_service


@pytest.fixture()
def temp_repo_scan_db(tmp_path, monkeypatch):
    monkeypatch.setattr(database, "DB_PATH", tmp_path / "repo_scan_jobs.db")
    database.init_db()
    repo_scan_job_service._queue = asyncio.Queue()
    repo_scan_job_service._worker_task = None
    with database.get_connection() as conn:
        cursor = conn.execute(
            """
            INSERT INTO repos (repo_name, owner, repo_url, canonical_url, created_at)
            VALUES ('repo', 'owner', 'https://github.com/owner/repo', 'https://github.com/owner/repo', 'now')
            """
        )
        repo_id = int(cursor.lastrowid)
    yield repo_id
    repo_scan_job_service._queue = None
    repo_scan_job_service._worker_task = None


def test_create_scan_run_returns_queued_run_without_blocking(temp_repo_scan_db):
    run = repo_scan_job_service.create_repo_scan_run(temp_repo_scan_db, {"scan_mode": "template"})

    assert run["run_id"] > 0
    assert run["repo_id"] == temp_repo_scan_db
    assert run["status"] == "queued"
    assert run["progress_percent"] == 0

    persisted = repo_scan_job_service.get_repo_scan_run(run["run_id"])
    assert persisted["status"] == "queued"
    assert "template" in persisted["options_json"]


def test_cancel_queued_scan_run_marks_it_canceled(temp_repo_scan_db):
    run = repo_scan_job_service.create_repo_scan_run(temp_repo_scan_db, {})

    canceled = repo_scan_job_service.cancel_repo_scan_run(run["run_id"])

    assert canceled["status"] == "canceled"
    assert canceled["cancel_requested"] == 1
    assert canceled["finished_at"]


def test_list_all_scan_runs_includes_repo_metadata(temp_repo_scan_db):
    run = repo_scan_job_service.create_repo_scan_run(temp_repo_scan_db, {})

    page = repo_scan_job_service.list_all_repo_scan_runs(page=1, page_size=10, status="queued", search="owner")

    assert page["total"] == 1
    assert page["items"][0]["id"] == run["run_id"]
    assert page["items"][0]["repo_name"] == "repo"
    assert page["items"][0]["repo_owner"] == "owner"


def test_batch_delete_scan_runs_skips_active_runs(temp_repo_scan_db):
    queued = repo_scan_job_service.create_repo_scan_run(temp_repo_scan_db, {})
    failed = repo_scan_job_service.create_repo_scan_run(temp_repo_scan_db, {})
    with database.get_connection() as conn:
        conn.execute("UPDATE repo_scan_runs SET status = 'failed' WHERE id = ?", (failed["run_id"],))

    result = repo_scan_job_service.batch_delete_repo_scan_runs([queued["run_id"], failed["run_id"], 9999])

    assert result["deleted_count"] == 1
    assert result["deleted_ids"] == [failed["run_id"]]
    assert result["skipped_count"] == 1
    assert result["missing_ids"] == [9999]
    assert repo_scan_job_service.get_repo_scan_run(queued["run_id"])["status"] == "queued"
    assert repo_scan_job_service.get_repo_scan_run(failed["run_id"]) is None


def test_mark_stale_scan_runs_failed(temp_repo_scan_db):
    run = repo_scan_job_service.create_repo_scan_run(temp_repo_scan_db, {})

    repo_scan_job_service.mark_stale_runs_failed()

    failed = repo_scan_job_service.get_repo_scan_run(run["run_id"])
    assert failed["status"] == "failed"
    assert failed["finished_at"]
