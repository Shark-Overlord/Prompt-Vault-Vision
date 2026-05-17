from __future__ import annotations

from fastapi import APIRouter

from database import fetch_all, get_connection, utc_now
from models.schemas import TagCreate


router = APIRouter(prefix="/api/tags", tags=["tags"])


@router.get("")
def list_tags():
    return fetch_all("SELECT * FROM tags ORDER BY name")


@router.post("")
def create_tag(payload: TagCreate):
    with get_connection() as conn:
        conn.execute(
            "INSERT OR IGNORE INTO tags (name, type, created_at) VALUES (?, ?, ?)",
            (payload.name.strip(), payload.type, utc_now()),
        )
        row = conn.execute("SELECT * FROM tags WHERE name = ?", (payload.name.strip(),)).fetchone()
        return dict(row)

