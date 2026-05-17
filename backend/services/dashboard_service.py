from __future__ import annotations

from database import fetch_all, fetch_one


def dashboard_stats():
    counts = fetch_one(
        """
        SELECT
            (SELECT COUNT(*) FROM repos) AS repo_count,
            (SELECT COUNT(*) FROM prompt_effect_pairs) AS pair_count,
            (SELECT COUNT(*) FROM prompt_effect_pairs WHERE selection_status = 'featured') AS featured_count,
            (SELECT COUNT(*) FROM prompt_effect_pairs WHERE selection_status = 'pending_review' OR commercial_risk = 'unknown') AS pending_count,
            (SELECT COUNT(*) FROM repos WHERE date(created_at) = date('now')) AS today_new_count,
            (SELECT COUNT(*) FROM repos WHERE date(last_checked_at) = date('now')) AS today_updated_count
        """
    ) or {}
    categories = fetch_all(
        """
        SELECT category, COUNT(*) AS count
        FROM repos
        GROUP BY category
        ORDER BY count DESC
        """
    )
    recent_pairs = fetch_all(
        """
        SELECT id, repo_name, category, scenario, quality_level, selection_status, image_local_path, original_prompt
        FROM prompt_effect_pairs
        WHERE image_local_path IS NOT NULL AND image_local_path != ''
        ORDER BY created_at DESC
        LIMIT 8
        """
    )
    logs = fetch_all(
        """
        SELECT *
        FROM search_logs
        ORDER BY created_at DESC
        LIMIT 6
        """
    )
    return {
        "counts": counts,
        "categories": categories,
        "recent_pairs": recent_pairs,
        "logs": logs,
    }

