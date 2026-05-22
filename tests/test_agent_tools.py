import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend"))

from agents.tools import infer_library_tool_plan


def test_tool_plan_detects_web_ui_prompt_search():
    plan = infer_library_tool_plan("帮我找一下 Web UI dashboard 组件 Prompt")

    assert "web_ui_prompt_search" in plan["tools"]
    assert plan["categories"] == ["web_ui_prompt"]
    assert "dashboard" in plan["scenarios"]


def test_tool_plan_detects_image_generation_prompt_search():
    plan = infer_library_tool_plan("我需要适合商品库的海报 Prompt")

    assert "visual_prompt_pair_search" in plan["tools"]
    assert "image_generation_prompt" in plan["categories"]
    assert "poster" in plan["scenarios"]
    assert "海报" in plan["terms"]


def test_tool_plan_expands_cartoon_style_to_image_generation_keywords():
    plan = infer_library_tool_plan("卡通风格提示词 找找")

    assert plan["tools"] == ["visual_prompt_pair_search"]
    assert plan["categories"] == ["image_generation_prompt"]
    assert "卡通" in plan["expanded_keywords"]
    assert "cartoon" in plan["expanded_keywords"]
    assert "插画" in plan["expanded_keywords"]


def test_tool_plan_detects_pair_candidate_search():
    plan = infer_library_tool_plan("哪些候选配对需要人工复查，证据链是否足够")

    assert plan["tools"] == ["pair_candidate_search"]
    assert plan["wants_candidate"] is True


def test_tool_plan_detects_repo_search():
    plan = infer_library_tool_plan("找一下值得复扫的 GitHub 仓库")

    assert "repo_search" in plan["tools"]
    assert plan["wants_repo"] is True
