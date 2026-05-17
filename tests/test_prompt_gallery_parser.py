import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend"))

from services.prompt_service import extract_prompt_effect_pairs, split_markdown_content_blocks


def test_gallery_parser_pairs_prompt_section_with_html_image():
    markdown = """
### No. 1: Wide quote card

#### 📝 Prompt

Create a cinematic quote card with a realistic portrait, elegant typography, soft lighting,
balanced composition, premium editorial style, and a clean visual hierarchy for social media.

#### 🖼️ Generated Images

##### Image 1

<img src="https://example.com/output-1.jpg" width="700" alt="Wide quote card - Image 1">
"""

    pairs = extract_prompt_effect_pairs(markdown, base_url="", source_page_url="https://github.com/example/repo", limit=5)

    assert len(pairs) == 1
    assert pairs[0].relation_type == "direct_pair"
    assert pairs[0].confidence >= 90
    assert pairs[0].image_url == "https://example.com/output-1.jpg"
    assert "cinematic quote card" in pairs[0].prompt


def test_gallery_parser_supports_chinese_prompt_and_image_headings():
    markdown = """
### No. 2: 产品海报

#### 📝 提示词

Generate a premium product poster with clear subject, refined glass reflections, balanced
composition, dramatic but controlled lighting, realistic materials, and commercial visual polish.

#### 🖼️ 生成图片

<img src="./assets/product-poster.png" alt="产品海报效果图">
"""

    pairs = extract_prompt_effect_pairs(
        markdown,
        base_url="https://raw.githubusercontent.com/example/repo/HEAD/",
        source_page_url="https://github.com/example/repo",
        limit=5,
    )

    assert len(pairs) == 1
    assert pairs[0].image_url == "https://raw.githubusercontent.com/example/repo/HEAD/assets/product-poster.png"
    assert "产品海报" in pairs[0].evidence


def test_prompt_text_label_pairs_with_example_image_section():
    markdown = """
### Premium claw machine

* Model: gpt-4o
* Prompt Text: `Create a premium luxury claw machine product visual, cinematic lighting,
transparent glass, polished chrome, dramatic reflections, balanced composition, and commercial poster quality.`
* Example Image:

![premium claw machine](./images/claw-machine.png)
"""

    pairs = extract_prompt_effect_pairs(
        markdown,
        base_url="https://raw.githubusercontent.com/example/repo/HEAD/",
        source_page_url="https://github.com/example/repo",
        limit=5,
    )

    assert len(pairs) == 1
    assert pairs[0].relation_type == "direct_pair"
    assert "Create a premium luxury claw machine" in pairs[0].prompt
    assert not pairs[0].prompt.startswith("`")
    assert pairs[0].image_url.endswith("/images/claw-machine.png")


def test_table_prompt_image_pairs_are_direct_pairs():
    markdown = """
## Product prompt table

| Prompt | Output Image |
| --- | --- |
| Generate a premium product poster with glass reflections, clear subject, clean typography, balanced composition, and commercial lighting. | ![poster output](./poster.png) |
"""

    pairs = extract_prompt_effect_pairs(
        markdown,
        base_url="https://raw.githubusercontent.com/example/repo/HEAD/",
        source_page_url="https://github.com/example/repo",
        limit=5,
    )

    assert len(pairs) == 1
    assert pairs[0].relation_type == "direct_pair"
    assert pairs[0].confidence >= 88
    assert "Markdown 表格配对" in pairs[0].evidence


def test_image_filename_anchor_strengthens_markdown_pair_evidence():
    markdown = """
## Glass Speaker Product Poster

Prompt: Generate a premium glass speaker product poster with transparent material,
studio reflections, clean commercial composition, strong subject focus and polished lighting.

![glass speaker result](./outputs/glass-speaker-product-poster.png)
"""

    pairs = extract_prompt_effect_pairs(
        markdown,
        base_url="https://raw.githubusercontent.com/example/repo/HEAD/",
        source_page_url="https://github.com/example/repo",
        limit=5,
    )

    assert len(pairs) == 1
    assert pairs[0].filename_score >= 6
    assert "图片文件名/alt 锚点" in pairs[0].evidence


def test_workflow_screenshot_is_deprioritized_when_output_image_exists():
    markdown = """
### Text to Image Generation

Sample Prompt: Generate a cinematic product photo of a smartwatch on black glass,
soft rim light, realistic reflections, premium advertisement composition, high detail.

Example Images:

![workflow screenshot](./workflow-screenshot.png)
![generated output](./generated-output.png)
"""

    pairs = extract_prompt_effect_pairs(
        markdown,
        base_url="https://raw.githubusercontent.com/example/repo/HEAD/",
        source_page_url="https://github.com/example/repo",
        limit=5,
    )

    assert len(pairs) == 1
    assert pairs[0].image_url.endswith("/generated-output.png")


def test_markdown_blocks_split_case_sections_and_do_not_cross_pair():
    markdown = """
## Case 1: Glass Speaker

Prompt: Generate a premium glass speaker product poster with clean commercial composition,
transparent materials, studio lighting, realistic reflections and strong subject focus.

![glass speaker](./glass-speaker.png)

## Case 2: Watch Ad

Prompt: Generate a cinematic smartwatch advertisement with black glass reflections,
premium lighting, strong product focus and refined commercial style.

![watch ad](./watch-ad.png)
"""

    blocks = split_markdown_content_blocks(markdown)
    pairs = extract_prompt_effect_pairs(
        markdown,
        base_url="https://raw.githubusercontent.com/example/repo/main/",
        source_page_url="https://github.com/example/repo/blob/main/examples.md",
        limit=10,
    )

    assert len([block for block in blocks if block.kind == "case_section"]) == 2
    assert len(pairs) == 2
    assert pairs[0].image_url.endswith("/glass-speaker.png")
    assert pairs[1].image_url.endswith("/watch-ad.png")
    assert all("Case/Example" in pair.evidence for pair in pairs)
