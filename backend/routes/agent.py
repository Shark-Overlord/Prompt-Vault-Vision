from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, HTTPException, Query

from agents.library_agent_graph import chat_with_library_agent, delete_thread, list_messages, list_threads
from agents.memory import create_memory, delete_memory, list_memories_paginated, set_memory_status, update_memory
from models.schemas import AgentChatRequest, AgentMemoryCreate, AgentMemoryUpdate


router = APIRouter(prefix="/api/agent", tags=["agent"])


@router.post("/chat")
async def chat(payload: AgentChatRequest):
    try:
        return await chat_with_library_agent(payload.message, payload.thread_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/threads")
def get_threads():
    return list_threads()


@router.get("/threads/{thread_id}/messages")
def get_thread_messages(thread_id: str):
    return list_messages(thread_id)


@router.delete("/threads/{thread_id}")
def remove_thread(thread_id: str):
    deleted = delete_thread(thread_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="智能体会话不存在")
    return {"deleted": True, "thread_id": thread_id}


@router.get("/memories")
def get_memories(
    status: Optional[str] = Query(default=None),
    memory_type: Optional[str] = Query(default=None),
    repo_id: Optional[int] = Query(default=None),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
):
    return list_memories_paginated(status=status, memory_type=memory_type, repo_id=repo_id, page=page, page_size=page_size)


@router.post("/memories")
def post_memory(payload: AgentMemoryCreate):
    try:
        return create_memory(payload.model_dump())
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.patch("/memories/{memory_id}")
def patch_memory(memory_id: int, payload: AgentMemoryUpdate):
    try:
        memory = update_memory(memory_id, payload.model_dump(exclude_unset=True))
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    if not memory:
        raise HTTPException(status_code=404, detail="记忆不存在")
    return memory


@router.post("/memories/{memory_id}/approve")
def approve_memory(memory_id: int):
    memory = set_memory_status(memory_id, "active")
    if not memory:
        raise HTTPException(status_code=404, detail="记忆不存在")
    return memory


@router.post("/memories/{memory_id}/reject")
def reject_memory(memory_id: int):
    memory = set_memory_status(memory_id, "rejected")
    if not memory:
        raise HTTPException(status_code=404, detail="记忆不存在")
    return memory


@router.delete("/memories/{memory_id}")
def remove_memory(memory_id: int):
    deleted = delete_memory(memory_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="记忆不存在")
    return {"deleted": True, "id": memory_id}
