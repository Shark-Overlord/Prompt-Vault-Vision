import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend"))

import pytest

import database
from agents.repo_template_graph import approve_template, build_file_profiles, create_template_record, get_active_template, reject_template, validate_template_content
from services.repo_scan_service import _select_template_documents


def test_template_approval_keeps_one_active(tmp_path, monkeypatch):
    monkeypatch.setattr(database, "DB_PATH", tmp_path / "templates.db")
    database.init_db()

    with database.get_connection() as conn:
        cursor = conn.execute(
            """
            INSERT INTO repos (repo_name, owner, repo_url, canonical_url, created_at)
            VALUES ('repo', 'owner', 'https://github.com/owner/repo', 'https://github.com/owner/repo', 'now')
            """
        )
        repo_id = int(cursor.lastrowid)

    content = {
        "scan_paths": ["README.md"],
        "prompt_field_names": ["prompt"],
        "image_field_names": ["image_url"],
        "section_hints": ["Prompt"],
        "exclude_image_keywords": ["logo"],
        "matching_notes": ["同一区块优先"],
        "risk_notes": ["License 待查"],
        "summary_cn": "测试模板",
        "confidence": 75,
    }
    first = create_template_record(repo_id, content, source_ai_config_id=None)
    second = create_template_record(repo_id, {**content, "summary_cn": "第二版"}, source_ai_config_id=None)

    assert first["status"] == "pending_review"
    assert approve_template(first["id"])["status"] == "active"
    assert approve_template(second["id"])["status"] == "active"
    assert get_active_template(repo_id)["id"] == second["id"]
    assert database.fetch_one("SELECT status FROM repo_scan_templates WHERE id = ?", (first["id"],))["status"] == "archived"
    assert reject_template(second["id"])["status"] == "rejected"


def test_markdown_file_profile_detects_prompt_image_pair():
    documents = [
        {
            "path": "examples/gallery.md",
            "content": """### Case 1
#### Prompt
Generate a premium commercial poster with clear product subject, polished lighting and reusable composition.
#### Generated Images
![result](./poster.png)
""",
            "raw_base_url": "https://raw.githubusercontent.com/example/repo/main/examples/",
            "source_page_url": "https://github.com/example/repo/blob/main/examples/gallery.md",
        }
    ]

    profiles = build_file_profiles(documents, "image_generation_prompt")

    assert len(profiles) == 1
    assert profiles[0]["file_type"] == "markdown"
    assert profiles[0]["path"] == "examples/gallery.md"
    assert profiles[0]["estimated_pair_count"] == 1
    assert "Case 1" in profiles[0]["headings"]


def test_v2_template_requires_markdown_targets_or_reason():
    with pytest.raises(ValueError):
        validate_template_content({"schema_version": 2, "secondary_target_files": ["cases/*/case.yml"]})

    content = validate_template_content(
        {
            "schema_version": 2,
            "primary_target_files": ["examples/*.md"],
            "secondary_target_files": ["cases/*/case.yml"],
            "markdown_strategies": ["prompt_then_image_section"],
            "prompt_locators": ["Prompt"],
            "image_locators": ["Generated Images"],
            "pairing_strategy": ["prompt_section_to_next_image_section"],
            "exclude_image_keywords": ["logo"],
            "evidence_rules": ["保留中文证据"],
            "summary_cn": "Markdown 优先模板",
            "confidence": 82,
        }
    )

    assert content["schema_version"] == 2
    assert content["primary_target_files"] == ["examples/*.md"]
    assert content["secondary_target_files"] == ["cases/*/case.yml"]


def test_template_document_selection_prioritizes_markdown_primary_targets():
    documents = [
        {"path": "cases/1/case.yml", "content": "", "raw_base_url": "", "source_page_url": ""},
        {"path": "examples/gallery.md", "content": "", "raw_base_url": "", "source_page_url": ""},
        {"path": "README.md", "content": "", "raw_base_url": "", "source_page_url": ""},
    ]
    template = {
        "schema_version": 2,
        "primary_target_files": ["README.md", "examples/*.md"],
        "secondary_target_files": ["cases/*/case.yml"],
    }

    selected, primary_count, secondary_count = _select_template_documents(documents, template)

    assert [document["path"] for document in selected] == ["examples/gallery.md", "README.md", "cases/1/case.yml"]
    assert primary_count == 2
    assert secondary_count == 1
