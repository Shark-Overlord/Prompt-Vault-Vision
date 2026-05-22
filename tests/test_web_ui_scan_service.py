import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend"))

import database
from services.web_ui_scan_service import extract_web_ui_assets, save_web_ui_assets


def test_extract_web_ui_prompt_from_markdown_heading_block():
    documents = [
        {
            "path": "docs/components.md",
            "content": """## Pricing Card

Prompt: Create a premium SaaS pricing card component using React and Tailwind with three tiers, subtle borders, clear CTA hierarchy and responsive spacing.
""",
            "raw_base_url": "https://raw.githubusercontent.com/example/repo/main/docs/",
            "source_page_url": "https://github.com/example/repo/blob/main/docs/components.md",
        }
    ]

    data = extract_web_ui_assets(documents)

    assert len(data["web_ui_assets"]) == 1
    asset = data["web_ui_assets"][0]
    assert asset.asset_group == "design_spec"
    assert asset.asset_type == "component_prompt"
    assert asset.component_type == "pricing"
    assert "React" in asset.framework
    assert "Tailwind CSS" in asset.framework
    assert asset.source_file == "docs/components.md"
    assert "Prompt 标签" in asset.evidence


def test_extract_web_ui_prompt_from_markdown_table_with_screenshot():
    documents = [
        {
            "path": "examples/ui.md",
            "content": """| Component | Prompt | Preview |
| --- | --- | --- |
| Dashboard table | Build a responsive dashboard data table UI with sticky header, compact filters, clean row density and shadcn style actions. | ![preview](./dashboard-table.png) |
""",
            "raw_base_url": "https://raw.githubusercontent.com/example/repo/main/examples/",
            "source_page_url": "https://github.com/example/repo/blob/main/examples/ui.md",
        }
    ]

    data = extract_web_ui_assets(documents)

    assert len(data["web_ui_assets"]) == 1
    asset = data["web_ui_assets"][0]
    assert asset.asset_group == "design_spec"
    assert asset.component_type == "table"
    assert asset.screenshot_original_url == "https://raw.githubusercontent.com/example/repo/main/examples/dashboard-table.png"
    assert "Markdown 表格" in asset.evidence


def test_extract_design_rule_asset_without_screenshot():
    documents = [
        {
            "path": "design-system/rules.md",
            "content": """## Layout Guidelines

Design rule: Web UI layout should use an 8px spacing rhythm, responsive grid columns, restrained card borders and clear visual hierarchy for dashboard pages.
""",
            "raw_base_url": "https://raw.githubusercontent.com/example/repo/main/design-system/",
            "source_page_url": "https://github.com/example/repo/blob/main/design-system/rules.md",
        }
    ]

    data = extract_web_ui_assets(documents)

    assert len(data["web_ui_assets"]) == 1
    asset = data["web_ui_assets"][0]
    assert asset.asset_group == "design_spec"
    assert asset.asset_type in {"design_rule", "layout_pattern"}
    assert not asset.screenshot_original_url


def test_component_library_repo_is_saved_as_repo_level_asset():
    documents = [
        {
            "path": "README.md",
            "content": """# Prompt Kit

Customizable, high-quality components for AI applications. Install with shadcn CLI and use the registry in your React app.

## Installation

```bash
npx shadcn@latest add prompt-kit/prompt-input
```
""",
            "raw_base_url": "https://raw.githubusercontent.com/ibelick/prompt-kit/main/",
            "source_page_url": "https://github.com/ibelick/prompt-kit/blob/main/README.md",
        },
        {
            "path": "components.json",
            "content": '{"$schema":"https://ui.shadcn.com/schema.json"}',
            "raw_base_url": "https://raw.githubusercontent.com/ibelick/prompt-kit/main/",
            "source_page_url": "https://github.com/ibelick/prompt-kit/blob/main/components.json",
        },
    ]

    data = extract_web_ui_assets(
        documents,
        repo_name="prompt-kit",
        repo_url="https://github.com/ibelick/prompt-kit",
        readme=documents[0]["content"],
    )

    assert len(data["web_ui_assets"]) == 1
    asset = data["web_ui_assets"][0]
    assert asset.asset_group == "component_library"
    assert asset.asset_type == "component_library"
    assert asset.library_kind == "shadcn_registry"
    assert "shadcn" in asset.prompt_text.lower() or "components" in asset.prompt_text.lower()


def test_bad_images_are_not_saved_as_web_ui_screenshot():
    documents = [
        {
            "path": "docs/hero.md",
            "content": """## Hero Section

Prompt: Create a landing page hero UI with React, Tailwind, strong headline hierarchy, polished CTA buttons and responsive layout.

![build badge](https://img.shields.io/badge/build-passing.svg)
""",
            "raw_base_url": "https://raw.githubusercontent.com/example/repo/main/docs/",
            "source_page_url": "https://github.com/example/repo/blob/main/docs/hero.md",
        }
    ]

    data = extract_web_ui_assets(documents)

    assert len(data["web_ui_assets"]) == 1
    assert data["web_ui_assets"][0].screenshot_original_url == ""


def test_technical_ui_workflow_docs_are_not_saved_as_web_ui_assets():
    documents = [
        {
            "path": "README.md",
            "content": """## Basic Setup

1. **Add the Node:** Right-click on the canvas -> `Add Node` -> `sampling/testing` -> `Ultimate Config Builder`
2. **Connect to Sampler:** Connect the `configs_json` output to the sampler input.
3. **Start Building:** The Config Builder UI writes JSON for the workflow and the dashboard viewer renders `dashboard_html`.
""",
            "raw_base_url": "https://raw.githubusercontent.com/example/repo/main/",
            "source_page_url": "https://github.com/example/repo/blob/main/README.md",
        }
    ]

    data = extract_web_ui_assets(documents)

    assert data["web_ui_assets"] == []


def test_excluded_meta_docs_are_not_saved_even_with_ui_keywords():
    documents = [
        {
            "path": "CONTRIBUTING.md",
            "content": """## PR checklist

- Update the Builder UI in `web/conf_builder/conf-builder-config-management.js`
- Add default state migration in `conf-builder-main.js`
- Restart ComfyUI and run pytest
""",
            "raw_base_url": "https://raw.githubusercontent.com/example/repo/main/",
            "source_page_url": "https://github.com/example/repo/blob/main/CONTRIBUTING.md",
        }
    ]

    data = extract_web_ui_assets(documents)

    assert data["web_ui_assets"] == []


def test_markdown_table_reference_rows_are_not_saved_as_web_ui_prompts():
    documents = [
        {
            "path": "components/README.md",
            "content": """| Name | Prompt |
| --- | --- |
| Frosted Card | [card-frosted-glass.md](./card-frosted-glass.md) |
| Liquid Navbar | [navbar-liquid-glass.md](./navbar-liquid-glass.md) |
""",
            "raw_base_url": "https://raw.githubusercontent.com/example/repo/main/components/",
            "source_page_url": "https://github.com/example/repo/blob/main/components/README.md",
        }
    ]

    data = extract_web_ui_assets(documents)

    assert data["web_ui_assets"] == []


def test_readme_feature_blocks_without_explicit_prompt_are_not_saved():
    documents = [
        {
            "path": "README.md",
            "content": """## Features

This platform generates websites from text, includes real-time preview, responsive UI generation, and project download support.

## Usage

Enter a description of the website, refine it in the editor, and export the codebase when finished.
""",
            "raw_base_url": "https://raw.githubusercontent.com/example/repo/main/",
            "source_page_url": "https://github.com/example/repo/blob/main/README.md",
        }
    ]

    data = extract_web_ui_assets(documents)

    assert data["web_ui_assets"] == []


def test_save_web_ui_assets_deduplicates_by_content_hash(tmp_path, monkeypatch):
    monkeypatch.setattr(database, "DB_PATH", tmp_path / "web_ui_scan.db")
    database.init_db()
    with database.get_connection() as conn:
        cursor = conn.execute(
            """
            INSERT INTO repos (repo_name, owner, repo_url, canonical_url, category, created_at)
            VALUES ('repo', 'owner', 'https://github.com/owner/repo', 'https://github.com/owner/repo', 'web_ui_prompt', 'now')
            """
        )
        repo_id = int(cursor.lastrowid)

    documents = [
        {
            "path": "docs/components.md",
            "content": "## Hero\n\nPrompt: Create a landing page hero UI with React and Tailwind, polished CTA buttons, responsive layout and strong hierarchy.",
            "raw_base_url": "https://raw.githubusercontent.com/owner/repo/main/docs/",
            "source_page_url": "https://github.com/owner/repo/blob/main/docs/components.md",
        }
    ]
    data = extract_web_ui_assets(documents)
    record = {
        "repo_name": "repo",
        "repo_url": "https://github.com/owner/repo",
        "license": "MIT",
        "_web_ui_assets": data["web_ui_assets"],
    }

    with database.get_connection() as conn:
        first = asyncio.run(save_web_ui_assets(conn, repo_id, record))
        second = asyncio.run(save_web_ui_assets(conn, repo_id, record))

    rows = database.fetch_all("SELECT * FROM web_ui_prompts WHERE repo_id = ?", (repo_id,))
    assert first["web_ui_prompts_added"] == 1
    assert second["web_ui_prompts_added"] == 0
    assert second["web_ui_prompts_skipped"] == 1
    assert len(rows) == 1
