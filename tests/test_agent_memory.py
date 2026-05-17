import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend"))

import database
from agents.memory import create_memory, delete_memory, search_active_memories, set_memory_status
from agents.runtime import ensure_agent_runtime


def test_memory_requires_approval_before_search(tmp_path, monkeypatch):
    monkeypatch.setattr(database, "DB_PATH", tmp_path / "agent.db")
    database.init_db()

    memory = create_memory(
        {
            "memory_type": "user_preference",
            "content": "以后优先保留低商用风险、证据链清晰的 Prompt。",
            "status": "pending_review",
            "confidence": 80,
        }
    )

    assert search_active_memories("低商用风险") == []

    approved = set_memory_status(memory["id"], "active")
    assert approved["status"] == "active"
    assert search_active_memories("低商用风险")

    assert delete_memory(memory["id"]) is True


def test_agent_runtime_creates_checkpoint_db(tmp_path, monkeypatch):
    from agents import runtime

    monkeypatch.setattr(runtime, "CHECKPOINT_DB_PATH", tmp_path / "langgraph_checkpoints.db")
    ensure_agent_runtime()

    assert runtime.CHECKPOINT_DB_PATH.exists()
