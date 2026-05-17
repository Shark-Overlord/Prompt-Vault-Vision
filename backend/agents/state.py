from __future__ import annotations

from typing import Any, Dict, List, Optional, TypedDict


class RepoScanState(TypedDict, total=False):
    repo_id: int
    ai_config_id: Optional[int]
    documents: List[Dict[str, str]]
    baseline: Dict[str, Any]
    template: Dict[str, Any]
    error: Optional[str]


class AgentState(TypedDict, total=False):
    thread_id: str
    message: str
    memories: List[Dict[str, Any]]
    sources: List[Dict[str, Any]]
    actions: List[Dict[str, Any]]
    response: str


class MemoryState(TypedDict, total=False):
    memory_type: str
    scope: str
    repo_id: Optional[int]
    content: str
    status: str
    confidence: int
