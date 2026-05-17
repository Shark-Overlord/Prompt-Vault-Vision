import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend"))

from services.candidate_service import extract_candidate_data, should_scan_path


def test_should_scan_repo_content_paths():
    assert should_scan_path("README.md")
    assert should_scan_path("cases/1/case.yml")
    assert should_scan_path("case-template/case.yaml")
    assert should_scan_path("gpt-image-1/case.md")
    assert should_scan_path("docs/examples.md")
    assert should_scan_path("examples/prompts.json")
    assert should_scan_path("prompts/product.csv")
    assert not should_scan_path("node_modules/pkg/README.md")
    assert not should_scan_path("src/app.tsx")


def test_json_object_prompt_image_pair_is_direct_candidate():
    documents = [
        {
            "path": "examples/prompts.json",
            "content": '[{"prompt":"Generate a cinematic product poster with clear subject, premium lighting, clean composition and commercial polish.","image_url":"./outputs/poster.png"}]',
            "raw_base_url": "https://raw.githubusercontent.com/example/repo/main/examples/",
            "source_page_url": "https://github.com/example/repo/blob/main/examples/prompts.json",
        }
    ]

    data = extract_candidate_data(documents, "image_generation_prompt", total_pair_limit=5)

    assert len(data["pair_candidates"]) == 1
    pair = data["pair_candidates"][0]
    assert pair.relation_type == "direct_pair"
    assert pair.confidence == 94
    assert pair.image_url == "https://raw.githubusercontent.com/example/repo/main/examples/outputs/poster.png"
    assert "结构化对象配对" in pair.evidence


def test_csv_row_prompt_image_pair_is_direct_candidate():
    documents = [
        {
            "path": "samples/index.csv",
            "content": 'prompt,output\n"Generate a premium app UI dashboard with dark mode, glowing charts, clean cards and strong visual hierarchy",./dashboard.png\n',
            "raw_base_url": "https://raw.githubusercontent.com/example/repo/main/samples/",
            "source_page_url": "https://github.com/example/repo/blob/main/samples/index.csv",
        }
    ]

    data = extract_candidate_data(documents, "web_ui_prompt", total_pair_limit=5)

    assert len(data["pair_candidates"]) == 1
    pair = data["pair_candidates"][0]
    assert pair.confidence == 92
    assert "CSV 行配对" in pair.evidence


def test_yaml_case_file_with_image_before_multiline_prompt_is_direct_candidate():
    documents = [
        {
            "path": "cases/1/case.yml",
            "content": """title: Q版求婚场景
image: example_proposal_scene_q_realistic.png
alt_text: Q版求婚场景
prompt: |
  将照片里的两个人转换成Q版 3D人物，保持主体特征清晰，构图具有商业视觉质感，画面干净，光线柔和。
prompt_en: |
  Transform the two people in the photo into cute 3D characters with clear subject identity and polished commercial lighting.
""",
            "raw_base_url": "https://raw.githubusercontent.com/jamez-bondos/awesome-gpt4o-images/main/cases/1/",
            "source_page_url": "https://github.com/jamez-bondos/awesome-gpt4o-images/blob/main/cases/1/case.yml",
        }
    ]

    data = extract_candidate_data(documents, "image_generation_prompt", total_pair_limit=5)

    assert len(data["pair_candidates"]) == 1
    pair = data["pair_candidates"][0]
    assert pair.relation_type == "direct_pair"
    assert pair.confidence == 94
    assert pair.image_url == "https://raw.githubusercontent.com/jamez-bondos/awesome-gpt4o-images/main/cases/1/example_proposal_scene_q_realistic.png"
    assert pair.source_file == "cases/1/case.yml"
    assert pair.source_heading == "Q版求婚场景"
    assert pair.line_start == 4
    assert "YAML 对象强绑定" in pair.evidence


def test_extract_candidate_data_defaults_to_full_scan_without_pair_sampling_cap():
    documents = []
    for index in range(35):
        case_no = index + 1
        documents.append(
            {
                "path": f"cases/{case_no}/case.yml",
                "content": f"""title: Case {case_no}
image: output_{case_no}.png
prompt: |
  Generate a premium commercial visual case {case_no} with clear subject, polished lighting, reusable composition and strong product presentation.
""",
                "raw_base_url": f"https://raw.githubusercontent.com/example/repo/main/cases/{case_no}/",
                "source_page_url": f"https://github.com/example/repo/blob/main/cases/{case_no}/case.yml",
            }
        )

    data = extract_candidate_data(documents, "image_generation_prompt")

    assert len(data["pair_candidates"]) == 35
    assert data["pair_candidates"][0].source_file == "cases/1/case.yml"
    assert data["pair_candidates"][-1].source_file == "cases/35/case.yml"


def test_extract_candidate_data_keeps_markdown_pair_over_structured_duplicate_image():
    documents = [
        {
            "path": "README.md",
            "content": """### Case 1
#### Prompt
Generate a premium commercial visual with clear subject, polished lighting and reusable composition.
#### Generated image
![result](cases/1/output.png)
""",
            "raw_base_url": "https://raw.githubusercontent.com/example/repo/main/",
            "source_page_url": "https://github.com/example/repo/blob/main/README.md",
        },
        {
            "path": "cases/1/case.yml",
            "content": """title: Case 1
image: output.png
prompt: |
  Generate a premium commercial visual with clear subject, polished lighting and reusable composition.
""",
            "raw_base_url": "https://raw.githubusercontent.com/example/repo/main/cases/1/",
            "source_page_url": "https://github.com/example/repo/blob/main/cases/1/case.yml",
        },
    ]

    data = extract_candidate_data(documents, "image_generation_prompt")

    assert len(data["pair_candidates"]) == 1
    assert data["pair_candidates"][0].source_file == "README.md"
