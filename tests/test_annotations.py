import asyncio
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend"))

import database
from services import annotation_service


@pytest.fixture()
def temp_annotation_db(tmp_path, monkeypatch):
    monkeypatch.setattr(database, "DB_PATH", tmp_path / "annotations.db")
    database.init_db()
    annotation_service._queue = asyncio.Queue()
    annotation_service._worker_task = None
    with database.get_connection() as conn:
        repo_cursor = conn.execute(
            """
            INSERT INTO repos (repo_name, owner, repo_url, canonical_url, created_at)
            VALUES ('repo', 'owner', 'https://github.com/a/b', 'https://github.com/a/b', 'now')
            """
        )
        repo_id = int(repo_cursor.lastrowid)
        cursor = conn.execute(
            """
            INSERT INTO prompt_effect_pairs
                (repo_id, repo_name, repo_url, source_page_url, original_prompt, prompt_cn_explanation,
                 image_local_path, category, scenario, selection_status, created_at, updated_at)
            VALUES
                (?, 'repo', 'https://github.com/a/b', 'https://github.com/a/b', 'A cinematic product poster with soft light', '',
                 'assets/images/demo.png', 'image_generation_prompt', 'poster', 'pending_review', 'now', 'now')
            """,
            (repo_id,),
        )
        pair_id = int(cursor.lastrowid)
    yield pair_id
    annotation_service._queue = None
    annotation_service._worker_task = None


def test_annotation_queue_returns_unannotated_pairs(temp_annotation_db):
    page = annotation_service.list_annotation_queue(page=1, page_size=10)

    assert page["total"] == 1
    assert page["items"][0]["id"] == temp_annotation_db
    assert page["items"][0]["annotation_status"] == "unannotated"


def test_stale_explanation_is_still_unannotated(temp_annotation_db):
    with database.get_connection() as conn:
        conn.execute(
            "UPDATE prompt_effect_pairs SET prompt_cn_explanation = ? WHERE id = ?",
            ("该 Prompt 适合用于图像生成场景，重点参考其主体描述。", temp_annotation_db),
        )
        conn.execute("INSERT INTO tags (name, type, created_at) VALUES ('产品海报', 'annotation', 'now')")
        tag_id = conn.execute("SELECT id FROM tags WHERE name = '产品海报'").fetchone()["id"]
        conn.execute("INSERT INTO pair_tags (pair_id, tag_id) VALUES (?, ?)", (temp_annotation_db, tag_id))

    unannotated = annotation_service.list_annotation_queue(page=1, page_size=10, annotation_status="unannotated")
    annotated = annotation_service.list_annotation_queue(page=1, page_size=10, annotation_status="annotated")

    assert unannotated["total"] == 1
    assert annotated["total"] == 0


def test_pending_suggestion_excludes_pair_from_default_annotation(temp_annotation_db):
    annotation_service._insert_suggestion(
        temp_annotation_db,
        {
            "status": "pending_review",
            "prompt_language": "english",
            "suggested_cn_explanation": "一张带有柔和光线的电影感产品海报。",
            "suggested_tags_json": '["产品海报"]',
            "image_type_cn": "产品海报",
            "reason_cn": "测试",
            "confidence": 90,
            "error": None,
        },
    )

    unannotated = annotation_service.list_annotation_queue(page=1, page_size=10, annotation_status="unannotated")
    has_suggestion = annotation_service.list_annotation_queue(page=1, page_size=10, annotation_status="has_suggestion")

    assert unannotated["total"] == 0
    assert has_suggestion["total"] == 1
    with pytest.raises(ValueError):
        annotation_service.create_annotation_run({"limit": 20, "annotation_status": "unannotated"})


def test_explicit_regenerate_can_include_pending_suggestion(temp_annotation_db):
    annotation_service._insert_suggestion(
        temp_annotation_db,
        {
            "status": "pending_review",
            "prompt_language": "english",
            "suggested_cn_explanation": "一张带有柔和光线的电影感产品海报。",
            "suggested_tags_json": '["产品海报"]',
            "image_type_cn": "产品海报",
            "reason_cn": "测试",
            "confidence": 90,
            "error": None,
        },
    )

    run = annotation_service.create_annotation_run(
        {"limit": 1, "pair_ids": [temp_annotation_db], "allow_pending_suggestions": True}
    )

    assert run["status"] == "queued"
    assert run["total_items"] == 1


def test_create_annotation_run_returns_queued_run(temp_annotation_db):
    run = annotation_service.create_annotation_run({"limit": 20, "annotation_status": "unannotated"})

    assert run["id"] > 0
    assert run["status"] == "queued"
    assert run["total_items"] == 1
    assert str(temp_annotation_db) in run["options_json"]


def test_active_annotation_run_blocks_new_run(temp_annotation_db):
    run = annotation_service.create_annotation_run({"limit": 20, "annotation_status": "unannotated"})

    with pytest.raises(ValueError):
        annotation_service.create_annotation_run({"limit": 20, "annotation_status": "unannotated"})

    assert annotation_service.get_annotation_run(run["id"])["status"] == "queued"


def test_update_finished_annotation_run_options(temp_annotation_db):
    run = annotation_service.create_annotation_run({"limit": 20, "annotation_status": "unannotated"})
    with database.get_connection() as conn:
        conn.execute("UPDATE annotation_runs SET status = 'succeeded' WHERE id = ?", (run["id"],))

    updated = annotation_service.update_annotation_run(run["id"], {"limit": 5, "ai_config_id": None})

    assert updated["status"] == "succeeded"
    assert '"limit": 5' in updated["options_json"]


def test_update_active_annotation_run_is_blocked(temp_annotation_db):
    run = annotation_service.create_annotation_run({"limit": 20, "annotation_status": "unannotated"})

    with pytest.raises(ValueError):
        annotation_service.update_annotation_run(run["id"], {"limit": 5})


def test_rerun_finished_annotation_run_creates_new_run(temp_annotation_db):
    run = annotation_service.create_annotation_run({"limit": 20, "annotation_status": "unannotated"})
    with database.get_connection() as conn:
        conn.execute("UPDATE annotation_runs SET status = 'succeeded' WHERE id = ?", (run["id"],))

    rerun = annotation_service.rerun_annotation_run(run["id"])

    assert rerun["id"] != run["id"]
    assert rerun["status"] == "queued"


def test_delete_finished_annotation_run_keeps_suggestions(temp_annotation_db):
    run = annotation_service.create_annotation_run({"limit": 20, "annotation_status": "unannotated"})
    suggestion = annotation_service._insert_suggestion(
        temp_annotation_db,
        {
            "status": "pending_review",
            "prompt_language": "english",
            "suggested_cn_explanation": "一张带有柔和光线的电影感产品海报。",
            "suggested_tags_json": '["产品海报"]',
            "image_type_cn": "产品海报",
            "reason_cn": "测试",
            "confidence": 90,
            "error": None,
        },
        run_id=run["id"],
    )
    with database.get_connection() as conn:
        conn.execute("UPDATE annotation_runs SET status = 'succeeded' WHERE id = ?", (run["id"],))

    deleted = annotation_service.delete_annotation_run(run["id"])
    suggestion_row = database.fetch_one("SELECT run_id FROM prompt_pair_annotation_suggestions WHERE id = ?", (suggestion["id"],))

    assert deleted["id"] == run["id"]
    assert annotation_service.get_annotation_run(run["id"]) is None
    assert suggestion_row["run_id"] is None


def test_execute_run_creates_pending_suggestion(temp_annotation_db, monkeypatch):
    async def fake_chat_completion(*args, **kwargs):
        return {
            "content": '{"prompt_language":"english","cn_explanation":"一张带有柔和光线的电影感产品海报。","tags_cn":["产品海报","柔和光线","电影感","商业视觉"],"image_type_cn":"产品海报","confidence":88,"reason_cn":"标签来自原始 Prompt 中的 product poster、soft light 和 cinematic。"}'
        }

    monkeypatch.setattr(annotation_service, "chat_completion", fake_chat_completion)
    run = annotation_service.create_annotation_run({"limit": 1, "annotation_status": "unannotated"})

    asyncio.run(annotation_service._execute_run(run["id"]))

    refreshed = annotation_service.get_annotation_run(run["id"])
    suggestions = annotation_service.list_annotation_suggestions(page=1, page_size=10)
    assert refreshed["status"] == "succeeded"
    assert refreshed["created_suggestions"] == 1
    assert suggestions["total"] == 1
    assert suggestions["items"][0]["suggested_cn_explanation"] == "一张带有柔和光线的电影感产品海报。"


def test_accept_suggestion_updates_pair_and_tags(temp_annotation_db, monkeypatch):
    suggestion = annotation_service._insert_suggestion(
        temp_annotation_db,
        {
            "status": "pending_review",
            "prompt_language": "english",
            "suggested_cn_explanation": "一张带有柔和光线的电影感产品海报。",
            "suggested_tags_json": '["产品海报","商业视觉"]',
            "image_type_cn": "产品海报",
            "reason_cn": "测试",
            "confidence": 90,
            "error": None,
        },
    )

    accepted = annotation_service.accept_annotation_suggestion(suggestion["id"])
    pair = database.fetch_one("SELECT prompt_cn_explanation FROM prompt_effect_pairs WHERE id = ?", (temp_annotation_db,))
    tags = database.fetch_all(
        """
        SELECT tags.name
        FROM tags
        JOIN pair_tags ON pair_tags.tag_id = tags.id
        WHERE pair_tags.pair_id = ?
        ORDER BY tags.name
        """,
        (temp_annotation_db,),
    )

    assert accepted["status"] == "accepted"
    assert pair["prompt_cn_explanation"] == "一张带有柔和光线的电影感产品海报。"
    assert [tag["name"] for tag in tags] == ["产品海报", "商业视觉"]


def test_accept_stale_explanation_suggestion_is_blocked(temp_annotation_db):
    suggestion = annotation_service._insert_suggestion(
        temp_annotation_db,
        {
            "status": "pending_review",
            "prompt_language": "english",
            "suggested_cn_explanation": "该 Prompt 适合用于图像生成场景，重点参考其主体描述。",
            "suggested_tags_json": '["产品海报"]',
            "image_type_cn": "产品海报",
            "reason_cn": "测试",
            "confidence": 90,
            "error": None,
        },
    )

    with pytest.raises(ValueError):
        annotation_service.accept_annotation_suggestion(suggestion["id"])

    pair = database.fetch_one("SELECT prompt_cn_explanation FROM prompt_effect_pairs WHERE id = ?", (temp_annotation_db,))
    assert pair["prompt_cn_explanation"] == ""


def test_reject_suggestion_does_not_update_pair(temp_annotation_db):
    suggestion = annotation_service._insert_suggestion(
        temp_annotation_db,
        {
            "status": "pending_review",
            "prompt_language": "english",
            "suggested_cn_explanation": "不应写入",
            "suggested_tags_json": '["标签"]',
            "image_type_cn": "",
            "reason_cn": "",
            "confidence": 70,
            "error": None,
        },
    )

    rejected = annotation_service.reject_annotation_suggestion(suggestion["id"])
    pair = database.fetch_one("SELECT prompt_cn_explanation FROM prompt_effect_pairs WHERE id = ?", (temp_annotation_db,))

    assert rejected["status"] == "rejected"
    assert pair["prompt_cn_explanation"] == ""


def test_cancel_running_annotation_run(temp_annotation_db):
    run = annotation_service.create_annotation_run({"limit": 1, "annotation_status": "unannotated"})
    with database.get_connection() as conn:
        conn.execute("UPDATE annotation_runs SET status = 'running' WHERE id = ?", (run["id"],))

    canceled = annotation_service.cancel_annotation_run(run["id"])

    assert canceled["status"] == "cancel_requested"
    assert canceled["cancel_requested"] == 1
