import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend"))

from services.ai_pair_assist_service import assist_record_pair_candidates
from services.prompt_service import PromptEffectCandidate


def test_qwen_assist_keeps_low_confidence_candidate_pending(monkeypatch):
    async def fake_chat_completion(*args, **kwargs):
        return {
            "content": """
            {
              "match_decision": "likely_pair",
              "confidence_adjustment": 10,
              "should_save": true,
              "needs_review": true,
              "evidence_cn": "Prompt 和图片位于同一 Case 块内，图片文件名与案例标题存在重合，但缺少明确 caption。",
              "risk_notes": "License 待确认。"
            }
            """,
            "config": {"id": 1},
            "raw": {},
        }

    monkeypatch.setattr("services.ai_pair_assist_service.chat_completion", fake_chat_completion)
    candidate = PromptEffectCandidate(
        prompt="Generate a premium glass speaker product poster with clean commercial composition and polished lighting.",
        image_url="https://example.com/glass-speaker.png",
        relation_type="likely_pair",
        evidence="Case/Example 标题块：Glass Speaker；该块存在多个 Prompt 或多张图片，属于复杂内容块。",
        confidence=76,
        source_page_url="https://github.com/example/repo/blob/main/examples.md",
        source_file="examples.md",
        source_heading="Glass Speaker",
        structural_score=44,
        distance_score=18,
        filename_score=6,
        semantic_score=6,
        penalty_score=0,
    )

    record = asyncio.run(assist_record_pair_candidates({"_pair_candidates": [candidate]}, ai_config_id=1))
    assisted = record["_pair_candidates"][0]

    assert record["_ai_assisted_pairs"] == 1
    assert assisted.relation_type == "likely_pair"
    assert assisted.confidence == 84
    assert "Qwen 8B 辅助判断" in assisted.evidence
    assert "仍需人工复查" in assisted.evidence
