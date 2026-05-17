from __future__ import annotations

import json
import re
from dataclasses import replace
from pathlib import PurePosixPath
from typing import Any, Dict, Optional
from urllib.parse import urlparse

from services.ai_config_service import chat_completion
from services.prompt_service import PromptEffectCandidate


ASSIST_MIN_SCORE = 65
ASSIST_MAX_RULE_SCORE = 84
ASSIST_OUTPUT_MAX_SCORE = 84
VALID_MATCH_TYPES = {
    "direct_pair",
    "likely_pair",
    "style_reference",
    "workflow_output",
    "before_after_pair",
    "video_thumbnail",
    "unclear",
}


def _needs_ai_assist(candidate: PromptEffectCandidate) -> bool:
    if ASSIST_MIN_SCORE <= candidate.confidence <= ASSIST_MAX_RULE_SCORE:
        return True
    if "复杂内容块" in (candidate.evidence or ""):
        return True
    return False


def _extract_json_object(text: str) -> Dict[str, Any]:
    cleaned = (text or "").strip()
    if cleaned.startswith("```"):
        cleaned = re.sub(r"^```(?:json)?\s*", "", cleaned, flags=re.IGNORECASE)
        cleaned = re.sub(r"\s*```$", "", cleaned)
    try:
        payload = json.loads(cleaned)
        return payload if isinstance(payload, dict) else {}
    except Exception:
        pass
    match = re.search(r"\{.*\}", cleaned, flags=re.DOTALL)
    if not match:
        return {}
    try:
        payload = json.loads(match.group(0))
    except Exception:
        return {}
    return payload if isinstance(payload, dict) else {}


def _compact_candidate(candidate: PromptEffectCandidate) -> Dict[str, Any]:
    image_name = PurePosixPath(urlparse(candidate.image_url).path).name
    return {
        "source_file": candidate.source_file,
        "source_heading": candidate.source_heading,
        "line_start": candidate.line_start,
        "line_end": candidate.line_end,
        "prompt": candidate.prompt[:1800],
        "image_url": candidate.image_url,
        "image_filename": image_name,
        "rule_match_type": candidate.relation_type,
        "rule_match_score": candidate.confidence,
        "rule_evidence_cn": candidate.evidence,
        "scores": {
            "structural_score": candidate.structural_score,
            "distance_score": candidate.distance_score,
            "filename_score": candidate.filename_score,
            "semantic_score": candidate.semantic_score,
            "penalty_score": candidate.penalty_score,
        },
    }


def _apply_ai_decision(candidate: PromptEffectCandidate, payload: Dict[str, Any]) -> PromptEffectCandidate:
    decision = str(payload.get("match_decision") or candidate.relation_type).strip()
    if decision not in VALID_MATCH_TYPES:
        decision = candidate.relation_type

    evidence = str(payload.get("evidence_cn") or payload.get("reason") or "").strip()
    risk = str(payload.get("risk_notes") or "").strip()
    should_save = bool(payload.get("should_save", True))
    try:
        adjustment = int(payload.get("confidence_adjustment") or 0)
    except (TypeError, ValueError):
        adjustment = 0

    if should_save:
        score = max(ASSIST_MIN_SCORE, min(ASSIST_OUTPUT_MAX_SCORE, candidate.confidence + adjustment))
    else:
        score = min(candidate.confidence, ASSIST_MIN_SCORE - 1)
        decision = "unclear"

    ai_evidence = "Qwen 8B 辅助判断："
    ai_evidence += evidence or "模型未给出有效中文理由，仅保留规则证据。"
    if risk:
        ai_evidence += f" 风险提示：{risk}"
    ai_evidence += " 该判断只作为辅助，仍需人工复查。"

    return replace(
        candidate,
        relation_type=decision,
        confidence=score,
        evidence=f"{candidate.evidence}\n{ai_evidence}",
        semantic_score=min(20, candidate.semantic_score + 4),
    )


async def assist_record_pair_candidates(
    record: Dict[str, Any],
    ai_config_id: Optional[int] = None,
    max_items: int = 24,
) -> Dict[str, Any]:
    candidates = list(record.get("_pair_candidates") or [])
    if not candidates:
        return record

    updated: list[PromptEffectCandidate] = []
    assisted_count = 0
    first_error: Optional[str] = None
    system_prompt = (
        "你是视觉 Prompt 资产库的配对审核助手。规则引擎已经完成 Markdown 切块和初步配对。"
        "你只能基于给定 JSON 判断 Prompt 与图片路径/alt/标题/证据是否可能对应，不能想象图片内容，不能扩大到全文。"
        "请只返回 JSON，不要 Markdown。"
    )

    for candidate in candidates:
        if assisted_count >= max_items or not _needs_ai_assist(candidate):
            updated.append(candidate)
            continue

        user_payload = {
            "task": "判断该低置信 Prompt-图片候选是否应保留为待复查配对",
            "rules": [
                "如果结构证据不足或只是 gallery 展示，should_save=false 或 match_decision=unclear。",
                "如果同一 Case/标题/列表项内且图片文件名、alt、标题有线索，可返回 likely_pair。",
                "不要把 Qwen 判断直接当成精选结论，needs_review 通常应为 true。",
            ],
            "candidate": _compact_candidate(candidate),
            "required_output_schema": {
                "match_decision": "direct_pair|likely_pair|style_reference|workflow_output|before_after_pair|video_thumbnail|unclear",
                "confidence_adjustment": "integer between -20 and 10",
                "should_save": "boolean",
                "needs_review": "boolean",
                "evidence_cn": "中文证据，说明为什么这样判断",
                "risk_notes": "中文风险提示，可为空",
            },
        }

        try:
            result = await chat_completion(
                [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": json.dumps(user_payload, ensure_ascii=False)},
                ],
                ai_config_id=ai_config_id,
                temperature=0,
                max_tokens=600,
            )
            payload = _extract_json_object(result.get("content") or "")
            updated.append(_apply_ai_decision(candidate, payload))
            assisted_count += 1
        except Exception as exc:
            first_error = first_error or str(exc)
            updated.append(candidate)
            break

    if len(updated) < len(candidates):
        updated.extend(candidates[len(updated):])

    next_record = dict(record)
    next_record["_pair_candidates"] = updated
    next_record["_ai_assisted_pairs"] = assisted_count
    if first_error:
        next_record["_ai_assist_error"] = first_error
    return next_record
