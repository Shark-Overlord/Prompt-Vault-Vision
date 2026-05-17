from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import Any, Optional

from database import PROJECT_ROOT


CHECKPOINT_DB_PATH = PROJECT_ROOT / "data" / "langgraph_checkpoints.db"


def ensure_agent_runtime() -> None:
    """Create the checkpoint database even when LangGraph packages are not installed yet."""
    CHECKPOINT_DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(CHECKPOINT_DB_PATH) as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS agent_runtime_meta (
                key TEXT PRIMARY KEY,
                value TEXT
            )
            """
        )
        conn.execute(
            "INSERT OR REPLACE INTO agent_runtime_meta (key, value) VALUES ('checkpoint_path', ?)",
            (str(CHECKPOINT_DB_PATH),),
        )


def get_langgraph_checkpointer() -> Optional[Any]:
    ensure_agent_runtime()
    try:
        from langgraph.checkpoint.sqlite import SqliteSaver  # type: ignore
    except Exception:
        return None
    conn = sqlite3.connect(CHECKPOINT_DB_PATH, check_same_thread=False)
    return SqliteSaver(conn)


def langgraph_available() -> bool:
    try:
        import langgraph  # noqa: F401
    except Exception:
        return False
    return True
