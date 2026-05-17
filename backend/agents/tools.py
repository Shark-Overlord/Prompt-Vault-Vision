from __future__ import annotations

from typing import Any, Dict, List

from database import fetch_all, fetch_one


def _like_query(query: str) -> tuple[str, str]:
    clean = " ".join((query or "").strip().split())
    return clean, f"%{clean}%"


def search_repos(query: str, limit: int = 6) -> List[Dict[str, Any]]:
    clean, like = _like_query(query)
    if not clean:
        return []
    return fetch_all(
        """
        SELECT id, repo_name, owner, repo_url, category, quality_level, status, summary,
               prompt_effect_pair_count, last_checked_at
        FROM repos
        WHERE repo_name LIKE ? OR owner LIKE ? OR repo_url LIKE ? OR category LIKE ? OR summary LIKE ? OR notes LIKE ?
        ORDER BY prompt_effect_pair_count DESC, stars DESC, last_checked_at DESC
        LIMIT ?
        """,
        (like, like, like, like, like, like, limit),
    )


def search_prompt_pairs(query: str, limit: int = 6) -> List[Dict[str, Any]]:
    clean, like = _like_query(query)
    if not clean:
        return []
    return fetch_all(
        """
        SELECT id, repo_id, repo_name, repo_url, source_page_url, original_prompt,
               prompt_cn_explanation, category, scenario, quality_level,
               selection_status, effect_review, reusable_value, commercial_risk
        FROM prompt_effect_pairs
        WHERE original_prompt LIKE ? OR prompt_cn_explanation LIKE ? OR effect_review LIKE ?
              OR reusable_value LIKE ? OR scenario LIKE ? OR category LIKE ?
        ORDER BY CASE selection_status WHEN 'featured' THEN 0 WHEN 'normal' THEN 1 ELSE 2 END, updated_at DESC
        LIMIT ?
        """,
        (like, like, like, like, like, like, limit),
    )


def search_pair_candidates(query: str, limit: int = 6) -> List[Dict[str, Any]]:
    clean, like = _like_query(query)
    if not clean:
        return []
    return fetch_all(
        """
        SELECT id, repo_id, repo_name, repo_url, source_page_url, source_file,
               original_prompt, image_original_url, match_type, match_score,
               evidence, review_status, selection_status
        FROM pair_candidates
        WHERE original_prompt LIKE ? OR evidence LIKE ? OR source_file LIKE ? OR repo_name LIKE ?
        ORDER BY match_score DESC, updated_at DESC
        LIMIT ?
        """,
        (like, like, like, like, limit),
    )


def get_repo_brief(repo_id: int) -> Dict[str, Any] | None:
    return fetch_one("SELECT * FROM repos WHERE id = ?", (repo_id,))


def build_sources(query: str) -> List[Dict[str, Any]]:
    sources: List[Dict[str, Any]] = []
    for row in search_repos(query):
        sources.append({"type": "repo", "id": row["id"], "title": row["repo_name"], "data": row})
    for row in search_prompt_pairs(query):
        sources.append({"type": "prompt_pair", "id": row["id"], "title": row["repo_name"], "data": row})
    for row in search_pair_candidates(query):
        sources.append({"type": "pair_candidate", "id": row["id"], "title": row["repo_name"], "data": row})
    return sources
