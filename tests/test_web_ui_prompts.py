import sys
from pathlib import Path

import pytest
from fastapi import HTTPException

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend"))

import database
from models.schemas import RepoCreate, WebUiPromptCreate, WebUiPromptUpdate
from routes import repos, web_ui_prompts


@pytest.fixture()
def temp_web_ui_db(tmp_path, monkeypatch):
    monkeypatch.setattr(database, "DB_PATH", tmp_path / "web_ui_prompts.db")
    database.init_db()
    repo = repos.create_repo(
        RepoCreate(
            repo_url="https://github.com/example/web-ui-prompts",
            category="web_ui_prompt",
            summary="Web UI prompt examples",
        )
    )
    return repo["id"]


def test_init_db_creates_web_ui_prompts_table(temp_web_ui_db):
    row = database.fetch_one("SELECT name FROM sqlite_master WHERE type='table' AND name='web_ui_prompts'")

    assert row["name"] == "web_ui_prompts"


def test_web_ui_prompt_crud(temp_web_ui_db):
    created = web_ui_prompts.create_web_ui_prompt(
        WebUiPromptCreate(
            repo_id=temp_web_ui_db,
            source_file="docs/components.md",
            source_heading="Pricing Card",
            asset_type="component_prompt",
            component_type="pricing_card",
            page_type="landing_page",
            framework="React + Tailwind",
            prompt_text="Create a premium SaaS pricing section with three plans and clear hierarchy.",
            prompt_cn_translation="创建一个高级 SaaS 定价区块，包含三个套餐和清晰层级。",
            tags=["定价区块", "SaaS", "组件", "定价区块"],
            confidence=88,
            selection_status="normal",
        )
    )

    assert created["id"] > 0
    assert created["repo_name"] == "web-ui-prompts"
    assert created["repo_url"] == "https://github.com/example/web-ui-prompts"
    assert created["tags"] == ["定价区块", "SaaS", "组件"]

    page = web_ui_prompts.list_web_ui_prompts(search="pricing", asset_type="component_prompt", repo_id=temp_web_ui_db)
    assert page["total"] == 1
    assert page["items"][0]["component_type"] == "pricing_card"

    updated = web_ui_prompts.update_web_ui_prompt(
        created["id"],
        WebUiPromptUpdate(
            quality_level="featured",
            selection_status="featured",
            tags=["精选组件", "SaaS"],
        ),
    )
    assert updated["quality_level"] == "featured"
    assert updated["tags"] == ["精选组件", "SaaS"]

    deleted = web_ui_prompts.delete_web_ui_prompt(created["id"])
    assert deleted == {"deleted": True, "id": created["id"]}
    with pytest.raises(HTTPException):
        web_ui_prompts.get_web_ui_prompt(created["id"])
