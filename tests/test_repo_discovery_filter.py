import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend"))

from services.repo_discovery_filter import evaluate_repo_discovery_candidate


def repo_item(**overrides):
    item = {
        "name": "visual-prompts",
        "full_name": "maker/visual-prompts",
        "description": "AI image prompt examples with generated images",
        "topics": ["prompt", "image-generation"],
        "stargazers_count": 0,
        "forks_count": 0,
        "fork": False,
        "archived": False,
        "disabled": False,
        "license": {"spdx_id": "MIT"},
        "pushed_at": datetime.now(timezone.utc).isoformat(),
    }
    item.update(overrides)
    return item


def test_dense_prompt_repo_is_saved_without_star_requirement():
    readme = """
# GPT Image prompt examples

This repository is a reusable collection of text to image prompt examples with JSON-ready template structure.

| Title | Prompt | Result |
| --- | --- | --- |
| Product 01 | Prompt: Generate a photorealistic product image with clean studio lighting, sharp packaging details, commercial composition and white background. | ![product](outputs/product-01.png) |
| Poster 01 | Prompt: Create a commercial poster with cinematic lighting, bold typography area, layered composition and premium visual design. | ![poster](outputs/poster-01.png) |

## More prompts

Prompt: Generate an AI image of a premium skincare bottle on reflective acrylic, softbox lighting, editorial product photography, high detail.

Prompt: Create a visual design prompt for a futuristic dashboard hero image with dark background, precise glow, and elegant composition.
"""
    result = evaluate_repo_discovery_candidate(repo_item(stargazers_count=0), "image generation prompt", "image_generation_prompt", readme)

    assert result["decision"] == "save"
    assert result["score"] >= 65


def test_small_but_relevant_repo_enters_review_instead_of_being_hard_skipped():
    readme = """
# Product Image Prompts

Tiny but focused prompt set for GPT Image, with reusable template examples.

Prompt: Generate a luxury watch product photo on brushed metal, dramatic side lighting, crisp reflections, premium catalog composition.

Prompt: Create a clean product image for wireless earbuds, white acrylic surface, soft shadows, commercial photography style.

![watch result](images/watch-result.png)
"""
    result = evaluate_repo_discovery_candidate(repo_item(description="Small GPT Image product prompt set"), "product image prompt", "image_generation_prompt", readme)

    assert result["decision"] in {"save", "review"}
    assert result["status"] in {"ready_to_scan", "discovery_review"}


def test_link_only_repository_is_skipped():
    readme = "\n".join([f"- [tool {index}](https://example.com/{index})" for index in range(20)])
    result = evaluate_repo_discovery_candidate(
        repo_item(name="awesome-ai-links", full_name="maker/awesome-ai-links", description="Useful AI links", topics=[]),
        "image generation prompt",
        "image_generation_prompt",
        readme,
    )

    assert result["decision"] == "skip"
    assert "链接集合" in result["reason"]


def test_ad_like_repository_is_skipped():
    readme = """
# AI Growth Pack

Buy now and use this coupon discount. Sponsor promo sale for a third party SaaS.
No reusable prompt examples are included here.
"""
    result = evaluate_repo_discovery_candidate(
        repo_item(name="ai-growth-pack", full_name="maker/ai-growth-pack", description="sponsor coupon discount sale", topics=[]),
        "web ui prompt",
        "web_ui_prompt",
        readme,
    )

    assert result["decision"] == "skip"
    assert "广告" in result["reason"]


def test_archived_repository_is_hard_skipped():
    result = evaluate_repo_discovery_candidate(repo_item(archived=True), "image generation prompt", "image_generation_prompt", "Prompt: Generate a poster.")

    assert result["decision"] == "skip"
    assert result["status"] == "skipped"


def test_web_ui_prompt_library_repo_is_saved():
    readme = """
# UI Prompt Library

A prompt library for website UI and frontend design using React, Next.js, Tailwind CSS, shadcn/ui, and Framer Motion.

## Landing Page Prompt

Prompt: Create a premium SaaS landing page with a bold hero section, sticky navbar, pricing cards, testimonial grid, and polished CTA hierarchy.

## Components

- Hero section prompt
- Navbar prompt
- Pricing section prompt

Examples and templates live in components/ and examples/.
"""
    result = evaluate_repo_discovery_candidate(
        repo_item(
            name="ui-prompt-library",
            full_name="maker/ui-prompt-library",
            description="Website UI prompt library for React Tailwind shadcn",
            topics=["react", "tailwindcss", "shadcn-ui", "ui-prompts"],
        ),
        "web ui prompt library",
        "web_ui_prompt",
        readme,
    )

    assert result["decision"] == "save"
    assert result["status"] == "ready_to_scan"


def test_comfyui_dashboard_repo_is_skipped_for_web_ui_prompt_discovery():
    readme = """
# ComfyUI Ultimate Auto Sampler Config Grid Testing Suite

Visual UI for workflow nodes. Add Node -> sampling/testing -> Ultimate Config Builder.
Connect to sampler, checkpoint, VAE and LoRA inputs. Dashboard viewer renders dashboard_html in an iframe.

Prompt: test multiple image generation configs in one workflow.
"""
    result = evaluate_repo_discovery_candidate(
        repo_item(
            name="ComfyUI-Ultimate-Auto-Sampler-Config-Grid-Testing-Suite",
            full_name="maker/ComfyUI-Ultimate-Auto-Sampler-Config-Grid-Testing-Suite",
            description="Testing benchmarking tool for samplers, schedulers and prompts",
            topics=["comfyui", "workflow", "sampler", "dashboard"],
        ),
        "dashboard ui prompt",
        "web_ui_prompt",
        readme,
    )

    assert result["decision"] == "skip"
    assert "网站前端设计 Prompt" in result["reason"]


def test_comfyui_prompt_manager_is_skipped_for_web_ui_prompt_discovery():
    readme = """
# ComfyUI Prompt Manager

A comprehensive ComfyUI custom node with modern UI, dashboard viewer, prompt management system, workflow tools and image galleries.
"""
    result = evaluate_repo_discovery_candidate(
        repo_item(
            name="ComfyUI_PromptManager",
            full_name="maker/ComfyUI_PromptManager",
            description="Professional prompt management system for ComfyUI with dashboard analytics",
            topics=["comfyui", "workflow", "prompt-manager"],
        ),
        "web ui prompt",
        "web_ui_prompt",
        readme,
    )

    assert result["decision"] == "skip"
    assert "网站前端设计 Prompt" in result["reason"]



def test_video_prompt_repo_with_mp4_examples_is_saved():
    readme = """
# Awesome Veo3 Videos

This repository showcases generated videos, the prompts used for generation, and the resulting clips.

## Cases

### Case 1
- **Prompt:** Create an 8-second cinematic vlog clip with a fluffy yeti in snowy woods, dramatic close-up, handheld camera movement, and ambient forest sound design.
- **Video:**
https://github.com/user-attachments/assets/ef277203-5228-4ee4-8c1e-01cfac23741c
"""
    result = evaluate_repo_discovery_candidate(
        repo_item(
            name="awesome-veo3-videos",
            full_name="maker/awesome-veo3-videos",
            description="Curated Veo 3 prompt and generated video examples",
            topics=["veo3", "video-generation", "prompts"],
        ),
        "Veo prompt",
        "video_generation_prompt",
        readme,
    )

    assert result["decision"] in {"save", "review"}
    assert result["score"] >= 45
