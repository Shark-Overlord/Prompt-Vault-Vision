import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend"))

from database import init_db, fetch_one


def test_init_db_creates_core_tables():
    init_db()
    row = fetch_one("SELECT name FROM sqlite_master WHERE type='table' AND name='repos'")
    assert row["name"] == "repos"

