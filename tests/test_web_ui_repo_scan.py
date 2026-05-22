import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend"))

import database
from services import repo_scan_service


def test_web_ui_repo_scan_writes_repo_profiles_not_effect_pairs(tmp_path, monkeypatch):
    monkeypatch.setattr(database, "DB_PATH", tmp_path / "web_ui_repo_scan.db")
    database.init_db()
    with database.get_connection() as conn:
        cursor = conn.execute(
            """
            INSERT INTO repos (repo_name, owner, repo_url, canonical_url, category, created_at)
            VALUES ('repo', 'owner', 'https://github.com/owner/repo', 'https://github.com/owner/repo', 'web_ui_prompt', 'now')
            """
        )
        repo_id = int(cursor.lastrowid)

    async def fake_load_repo_context(_repo_id):
        repo = database.fetch_one("SELECT * FROM repos WHERE id = ?", (_repo_id,))
        item = {
            "name": "repo",
            "html_url": "https://github.com/owner/repo",
            "description": "Web UI prompts",
            "stargazers_count": 12,
            "forks_count": 1,
            "fork": False,
            "pushed_at": "2026-05-17T00:00:00Z",
            "owner": {"login": "owner"},
            "license": {"spdx_id": "MIT"},
        }
        readme = "# Web UI Prompts"
        documents = [
            {
                "path": "docs/components.md",
                "content": "## Pricing Card\n\nPrompt: Create a premium SaaS pricing card component using React and Tailwind with three tiers, subtle borders, clear CTA hierarchy and responsive spacing.",
                "raw_base_url": "https://raw.githubusercontent.com/owner/repo/main/docs/",
                "source_page_url": "https://github.com/owner/repo/blob/main/docs/components.md",
            }
        ]
        return dict(repo), item, readme, documents, "owner/repo"

    monkeypatch.setattr(repo_scan_service, "_load_repo_context", fake_load_repo_context)

    result = asyncio.run(repo_scan_service.scan_repo_by_id(repo_id, {}))
    result_again = asyncio.run(repo_scan_service.scan_repo_by_id(repo_id, {}))

    profile_count = database.fetch_one("SELECT COUNT(*) AS count FROM web_ui_repo_profiles WHERE repo_id = ?", (repo_id,))["count"]
    pair_count = database.fetch_one("SELECT COUNT(*) AS count FROM prompt_effect_pairs WHERE repo_id = ?", (repo_id,))["count"]

    assert result["scan_mode"] == "web_ui_rules"
    assert result["web_ui_profiles_added"] == 1
    assert result_again["web_ui_profiles_updated"] == 1
    assert result["web_ui_profile_type"] in {"component_library", "design_spec"}
    assert profile_count == 1
    assert pair_count == 0
