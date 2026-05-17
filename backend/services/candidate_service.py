from __future__ import annotations

import csv
import io
import json
import posixpath
import re
from dataclasses import replace
from pathlib import PurePosixPath
from typing import Any, Callable, Dict, Iterable, List, Optional, Sequence, Tuple
from urllib.parse import urljoin, urlparse

from database import fetch_one, get_connection, paginate, utc_now
from services.dedup_service import content_hash
from services.prompt_service import (
    PromptEffectCandidate,
    build_cn_explanation,
    default_effect_review,
    extract_prompt_candidates,
    extract_prompt_effect_pairs,
    infer_scenario,
)
from utils.image_utils import download_image, extract_markdown_image_urls


SCAN_EXTENSIONS = {".md", ".mdx", ".json", ".jsonl", ".csv", ".yaml", ".yml"}
SCAN_DIRS = (
    "",
    "case",
    "case-template",
    "cases",
    "docs",
    "examples",
    "gpt-image-1",
    "prompts",
    "samples",
    "outputs",
    "output",
    "assets",
    "images",
    "screenshots",
)
PROMPT_KEYS = (
    "prompt",
    "prompt_cn",
    "prompt_zh",
    "prompt_en",
    "prompt_text",
    "positive_prompt",
    "negative_prompt",
    "image_prompt",
    "video_prompt",
    "text_prompt",
    "input",
    "instruction",
    "text",
)
IMAGE_KEYS = (
    "image",
    "image_url",
    "output_image",
    "result_image",
    "example_image",
    "img",
    "thumbnail",
    "preview",
    "result",
    "output",
    "before",
    "after",
    "demo",
    "screenshot",
    "cover",
    "poster",
)
IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp", ".gif"}
AUTO_SAVE_TYPES = {"direct_pair", "likely_pair", "before_after_pair", "workflow_output", "video_thumbnail"}
YAML_KEY_RE = re.compile(r"^(?P<indent>\s*)(?P<key>[A-Za-z0-9_-]+)\s*:\s*(?P<value>.*)$")
YAML_BLOCK_MARKERS = {"|", "|-", "|+", ">", ">-", ">+"}
FULL_SCAN_LIMIT = 1_000_000


def should_scan_path(path: str) -> bool:
    clean = path.replace("\\", "/").strip("/")
    if not clean:
        return False
    suffix = PurePosixPath(clean).suffix.lower()
    if suffix not in SCAN_EXTENSIONS:
        return False
    lowered = clean.lower()
    if lowered.startswith("node_modules/") or "/node_modules/" in lowered:
        return False
    if lowered.startswith(".git/") or "/.git/" in lowered:
        return False
    parts = lowered.split("/")
    if parts[0].startswith("readme"):
        return True
    return parts[0] in SCAN_DIRS or len(parts) == 1


def raw_base_for_path(owner: str, repo: str, branch: str, path: str) -> str:
    directory = posixpath.dirname(path.replace("\\", "/"))
    if directory:
        return f"https://raw.githubusercontent.com/{owner}/{repo}/{branch}/{directory}/"
    return f"https://raw.githubusercontent.com/{owner}/{repo}/{branch}/"


def blob_url_for_path(owner: str, repo: str, branch: str, path: str) -> str:
    clean_path = path.replace("\\", "/")
    return f"https://github.com/{owner}/{repo}/blob/{branch}/{clean_path}"


def _line_number(text: str, pos: int) -> int:
    return (text or "")[: max(0, pos)].count("\n") + 1


def _looks_like_url_or_image(value: Any) -> bool:
    if not isinstance(value, str):
        return False
    lower = value.strip().lower()
    if not lower:
        return False
    if lower.startswith(("http://", "https://", "./", "../", "/")):
        return True
    return PurePosixPath(urlparse(lower).path).suffix in IMAGE_EXTENSIONS


def _resolve_image(base_url: str, value: str) -> str:
    return urljoin(base_url, value.strip()) if base_url else value.strip()


def _strip_yaml_scalar(value: str) -> str:
    clean = (value or "").strip()
    if len(clean) >= 2 and clean[0] == clean[-1] and clean[0] in {"'", '"'}:
        clean = clean[1:-1]
    return clean.strip()


def _dedent_yaml_block(lines: List[str]) -> str:
    meaningful_indents = [len(re.match(r"^\s*", line).group(0)) for line in lines if line.strip()]
    min_indent = min(meaningful_indents) if meaningful_indents else 0
    dedented = [line[min_indent:] if len(line) >= min_indent else "" for line in lines]
    return "\n".join(dedented).strip()


def _parse_simple_yaml_mapping(content: str) -> Tuple[Dict[str, str], Dict[str, Tuple[int, int]]]:
    values: Dict[str, str] = {}
    line_ranges: Dict[str, Tuple[int, int]] = {}
    lines = content.splitlines()
    index = 0

    while index < len(lines):
        match = YAML_KEY_RE.match(lines[index])
        if not match or match.group("indent"):
            index += 1
            continue

        key = match.group("key").lower()
        raw_value = (match.group("value") or "").strip()
        start_line = index + 1

        if raw_value in YAML_BLOCK_MARKERS:
            index += 1
            block_lines: List[str] = []
            while index < len(lines):
                next_match = YAML_KEY_RE.match(lines[index])
                if next_match and not next_match.group("indent"):
                    break
                block_lines.append(lines[index])
                index += 1
            values[key] = _dedent_yaml_block(block_lines)
            line_ranges[key] = (start_line, max(start_line, index))
            continue

        values[key] = _strip_yaml_scalar(raw_value)
        line_ranges[key] = (start_line, start_line)
        index += 1

    return values, line_ranges


def _extract_structured_pairs_from_object(
    obj: Any,
    base_url: str,
    source_page_url: str,
    source_file: str,
    heading: str,
    limit: int,
    path_label: str = "$",
    prompt_keys: Sequence[str] = PROMPT_KEYS,
    image_keys: Sequence[str] = IMAGE_KEYS,
) -> List[PromptEffectCandidate]:
    pairs: List[PromptEffectCandidate] = []
    if isinstance(obj, list):
        for index, item in enumerate(obj):
            pairs.extend(
                _extract_structured_pairs_from_object(
                    item,
                    base_url,
                    source_page_url,
                    source_file,
                    heading,
                    limit - len(pairs),
                    f"{path_label}[{index}]",
                    prompt_keys,
                    image_keys,
                )
            )
            if len(pairs) >= limit:
                break
        return pairs
    if not isinstance(obj, dict):
        return pairs

    lowered = {str(key).lower(): key for key in obj.keys()}
    prompt_key = next((lowered[key] for key in prompt_keys if key in lowered and isinstance(obj.get(lowered[key]), str)), None)
    image_key = next((lowered[key] for key in image_keys if key in lowered and _looks_like_url_or_image(obj.get(lowered[key]))), None)
    if prompt_key and image_key:
        prompt = " ".join(str(obj[prompt_key]).strip().split())
        image_url = _resolve_image(base_url, str(obj[image_key]))
        if len(prompt) >= 24:
            pairs.append(
                PromptEffectCandidate(
                    prompt=prompt,
                    image_url=image_url,
                    relation_type="direct_pair",
                    evidence=f"结构化对象配对：{source_file} 中 {path_label} 同时包含 prompt 字段和 {image_key} 图片字段，属于强绑定。",
                    confidence=94,
                    source_page_url=source_page_url,
                    source_file=source_file,
                    source_heading=heading,
                    structural_score=60,
                    distance_score=20,
                    filename_score=6,
                    semantic_score=8,
                    penalty_score=0,
                )
            )
    if len(pairs) >= limit:
        return pairs

    for key, value in obj.items():
        pairs.extend(_extract_structured_pairs_from_object(value, base_url, source_page_url, source_file, heading, limit - len(pairs), f"{path_label}.{key}", prompt_keys, image_keys))
        if len(pairs) >= limit:
            break
    return pairs


def _extract_json_pairs(content: str, base_url: str, source_page_url: str, source_file: str, limit: int, prompt_keys: Sequence[str], image_keys: Sequence[str]) -> List[PromptEffectCandidate]:
    pairs: List[PromptEffectCandidate] = []
    try:
        if source_file.lower().endswith(".jsonl"):
            rows = [json.loads(line) for line in content.splitlines() if line.strip()]
            return _extract_structured_pairs_from_object(rows, base_url, source_page_url, source_file, "JSONL", limit, prompt_keys=prompt_keys, image_keys=image_keys)
        data = json.loads(content)
    except Exception:
        return pairs
    return _extract_structured_pairs_from_object(data, base_url, source_page_url, source_file, "JSON", limit, prompt_keys=prompt_keys, image_keys=image_keys)


def _extract_csv_pairs(content: str, base_url: str, source_page_url: str, source_file: str, limit: int, prompt_keys: Sequence[str], image_keys: Sequence[str]) -> List[PromptEffectCandidate]:
    pairs: List[PromptEffectCandidate] = []
    try:
        reader = csv.DictReader(io.StringIO(content))
    except Exception:
        return pairs
    for index, row in enumerate(reader, start=2):
        lowered = {str(key).lower(): key for key in (row or {}).keys()}
        prompt_key = next((lowered[key] for key in prompt_keys if key in lowered and row.get(lowered[key])), None)
        image_key = next((lowered[key] for key in image_keys if key in lowered and _looks_like_url_or_image(row.get(lowered[key]))), None)
        if not prompt_key or not image_key:
            continue
        prompt = " ".join(str(row[prompt_key]).strip().split())
        if len(prompt) < 24:
            continue
        image_url = _resolve_image(base_url, str(row[image_key]))
        pairs.append(
            PromptEffectCandidate(
                prompt=prompt,
                image_url=image_url,
                relation_type="direct_pair",
                evidence=f"CSV 行配对：{source_file} 第 {index} 行同时包含 prompt 列和 {image_key} 图片列，属于结构强绑定。",
                confidence=92,
                source_page_url=source_page_url,
                source_file=source_file,
                source_heading="CSV",
                line_start=index,
                line_end=index,
                structural_score=60,
                distance_score=20,
                filename_score=4,
                semantic_score=8,
                penalty_score=0,
            )
        )
        if len(pairs) >= limit:
            break
    return pairs


def _extract_yaml_pairs(content: str, base_url: str, source_page_url: str, source_file: str, limit: int, prompt_keys: Sequence[str], image_keys: Sequence[str]) -> List[PromptEffectCandidate]:
    pairs: List[PromptEffectCandidate] = []
    mapping, line_ranges = _parse_simple_yaml_mapping(content)
    prompt_key = next((key for key in prompt_keys if key in mapping and len(" ".join(mapping[key].split())) >= 24), None)
    image_key = next((key for key in image_keys if key in mapping and _looks_like_url_or_image(mapping[key])), None)

    if prompt_key and image_key:
        prompt = " ".join(mapping[prompt_key].split())
        image_value = mapping[image_key]
        prompt_range = line_ranges.get(prompt_key, (0, 0))
        image_range = line_ranges.get(image_key, (0, 0))
        heading = mapping.get("title") or mapping.get("name") or mapping.get("alt_text") or "YAML"
        pairs.append(
            PromptEffectCandidate(
                prompt=prompt,
                image_url=_resolve_image(base_url, image_value),
                relation_type="direct_pair",
                evidence=f"YAML 对象强绑定：{source_file} 同一顶层对象同时包含 {prompt_key} 提示词字段和 {image_key} 图片字段，字段顺序不影响匹配，属于明确 Prompt-效果图配对。",
                confidence=94,
                source_page_url=source_page_url,
                source_file=source_file,
                source_heading=heading,
                line_start=prompt_range[0],
                line_end=max(prompt_range[1], image_range[1]),
                structural_score=60,
                distance_score=20,
                filename_score=6,
                semantic_score=8,
                penalty_score=0,
            )
        )
        return pairs[:limit]

    prompt_line: Optional[Tuple[int, str]] = None
    for index, line in enumerate(content.splitlines(), start=1):
        match = re.match(r"\s*([A-Za-z0-9_-]+)\s*:\s*(.+?)\s*$", line)
        if not match:
            continue
        key = match.group(1).lower()
        value = match.group(2).strip().strip("\"'")
        if key in prompt_keys and len(value) >= 24:
            prompt_line = (index, value)
        elif key in image_keys and prompt_line and _looks_like_url_or_image(value):
            pairs.append(
                PromptEffectCandidate(
                    prompt=" ".join(prompt_line[1].split()),
                    image_url=_resolve_image(base_url, value),
                    relation_type="likely_pair",
                    evidence=f"YAML 邻近字段配对：{source_file} 中 prompt 字段与 {key} 图片字段相邻，需人工复查。",
                    confidence=78,
                    source_page_url=source_page_url,
                    source_file=source_file,
                    source_heading="YAML",
                    line_start=prompt_line[0],
                    line_end=index,
                    structural_score=46,
                    distance_score=18,
                    filename_score=4,
                    semantic_score=6,
                    penalty_score=0,
                )
            )
            prompt_line = None
        if len(pairs) >= limit:
            break
    return pairs


def _natural_document_path_key(path: str) -> List[Any]:
    return [int(part) if part.isdigit() else part for part in re.split(r"(\d+)", path)]


def _document_scan_priority(document: Dict[str, str]) -> Tuple[int, List[Any]]:
    path = (document.get("path") or "").replace("\\", "/").lower()
    suffix = PurePosixPath(path).suffix.lower()
    if suffix in {".md", ".mdx"}:
        return (0, _natural_document_path_key(path))
    if suffix in {".json", ".jsonl", ".csv", ".yaml", ".yml"}:
        return (1, _natural_document_path_key(path))
    if path.startswith(("examples/", "prompts/", "samples/")):
        return (2, _natural_document_path_key(path))
    return (3, _natural_document_path_key(path))


def _remaining_limit(current_count: int, total_limit: Optional[int]) -> int:
    if total_limit is None:
        return FULL_SCAN_LIMIT
    return max(0, total_limit - current_count)


def _template_string_values(template: Optional[Dict[str, Any]], keys: Sequence[str]) -> List[str]:
    values: List[str] = []
    if not template:
        return values
    for key in keys:
        raw = template.get(key)
        if isinstance(raw, list):
            values.extend(str(item).strip() for item in raw if str(item).strip())
        elif isinstance(raw, str) and raw.strip():
            values.append(raw.strip())
    return values


def _merge_keys(base: Sequence[str], extra: Sequence[str]) -> Tuple[str, ...]:
    merged: List[str] = []
    for key in [*extra, *base]:
        clean = str(key).strip().lower()
        if clean and clean not in merged:
            merged.append(clean)
    return tuple(merged)


def extract_candidate_data(
    documents: Sequence[Dict[str, str]],
    category: str,
    total_pair_limit: Optional[int] = None,
    template: Optional[Dict[str, Any]] = None,
    progress_callback: Optional[Callable[[Dict[str, Any]], None]] = None,
) -> Dict[str, Any]:
    prompt_candidates: List[str] = []
    preview_images: List[str] = []
    pair_candidates: List[PromptEffectCandidate] = []
    seen_pairs: set[Tuple[str, str]] = set()
    seen_image_urls: set[str] = set()
    prompt_keys = _merge_keys(PROMPT_KEYS, _template_string_values(template, ("prompt_locators", "prompt_field_names")))
    image_keys = _merge_keys(IMAGE_KEYS, _template_string_values(template, ("image_locators", "image_field_names")))

    sorted_documents = sorted(documents, key=_document_scan_priority)
    total_files = len(sorted_documents)
    for index, document in enumerate(sorted_documents, start=1):
        if total_pair_limit is not None and len(pair_candidates) >= total_pair_limit:
            break
        path = document["path"]
        content = document["content"]
        base_url = document.get("raw_base_url") or ""
        source_page_url = document.get("source_page_url") or ""
        suffix = PurePosixPath(path).suffix.lower()
        pair_limit = _remaining_limit(len(pair_candidates), total_pair_limit)

        prompt_candidates.extend(extract_prompt_candidates(content, limit=50))
        if suffix in {".md", ".mdx"}:
            preview_images.extend(extract_markdown_image_urls(content, base_url=base_url))
            pairs = extract_prompt_effect_pairs(content, base_url=base_url, source_page_url=source_page_url, limit=pair_limit)
        elif suffix in {".json", ".jsonl"}:
            pairs = _extract_json_pairs(content, base_url, source_page_url, path, pair_limit, prompt_keys, image_keys)
        elif suffix == ".csv":
            pairs = _extract_csv_pairs(content, base_url, source_page_url, path, pair_limit, prompt_keys, image_keys)
        elif suffix in {".yaml", ".yml"}:
            pairs = _extract_yaml_pairs(content, base_url, source_page_url, path, pair_limit, prompt_keys, image_keys)
        else:
            pairs = []

        for pair in pairs:
            key = (pair.prompt, pair.image_url)
            if key in seen_pairs:
                continue
            if pair.image_url in seen_image_urls:
                continue
            seen_pairs.add(key)
            seen_image_urls.add(pair.image_url)
            pair_candidates.append(
                replace(
                    pair,
                    source_file=pair.source_file or path,
                    source_page_url=pair.source_page_url or source_page_url,
                )
            )
            if total_pair_limit is not None and len(pair_candidates) >= total_pair_limit:
                break
        if progress_callback:
            progress_callback(
                {
                    "total_files": total_files,
                    "processed_files": index,
                    "current_file": path,
                    "prompt_candidates": len(prompt_candidates),
                    "pair_candidates": len(pair_candidates),
                    "total_images": len(preview_images) + len({pair.image_url for pair in pair_candidates}),
                }
            )

    return {
        "prompt_candidates": list(dict.fromkeys(prompt_candidates)),
        "preview_images": list(dict.fromkeys(preview_images)),
        "pair_candidates": pair_candidates if total_pair_limit is None else pair_candidates[:total_pair_limit],
    }


def _candidate_review_status(candidate: PromptEffectCandidate, license_value: str) -> Tuple[str, str]:
    reasons: List[str] = []
    if candidate.confidence < 85:
        reasons.append("匹配分数低于 85，需要人工确认")
    if candidate.relation_type != "direct_pair":
        reasons.append(f"匹配类型为 {candidate.relation_type}")
    if not license_value or license_value.lower() in {"unknown", "noassertion"}:
        reasons.append("License 不清晰")
    if not candidate.evidence:
        reasons.append("缺少匹配证据")
    if reasons:
        return "pending_review", "；".join(reasons)
    return "auto_saved", "结构证据充分，已自动保存，同时保留候选记录"


async def save_pair_candidates(
    conn,
    repo_id: int,
    record: Dict[str, Any],
    limit: Optional[int] = None,
    progress_callback: Optional[Callable[[Dict[str, Any]], None]] = None,
) -> Tuple[int, int]:
    saved = 0
    images_added = 0
    now = utc_now()
    category = record.get("category") or "unknown"
    license_value = record.get("license") or "unknown"
    candidates = record.get("_pair_candidates") or []
    if limit is not None:
        candidates = candidates[:limit]

    for candidate in candidates:
        if progress_callback:
            progress_callback({"current_file": candidate.source_file, "phase": "download_candidate_image"})
        asset = await download_image(candidate.image_url)
        if not asset:
            if progress_callback:
                progress_callback({"error_count_delta": 1})
            continue

        asset_row = conn.execute("SELECT * FROM assets WHERE image_hash = ?", (asset["image_hash"],)).fetchone()
        if asset_row:
            asset_id = asset_row["id"]
            image_local_path = asset_row["image_local_path"]
            thumbnail_local_path = asset_row["thumbnail_local_path"]
        else:
            cursor = conn.execute(
                """
                INSERT OR IGNORE INTO assets
                    (repo_id, image_original_url, image_local_path, thumbnail_local_path, image_hash, source_page_url,
                     asset_type, width, height, file_size, description, commercial_risk, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    repo_id,
                    candidate.image_url,
                    asset["image_local_path"],
                    asset["thumbnail_local_path"],
                    asset["image_hash"],
                    candidate.source_page_url,
                    "pair_candidate_image",
                    asset["width"],
                    asset["height"],
                    asset["file_size"],
                    f"候选 Prompt-效果图匹配图片；类型：{candidate.relation_type}；分数：{candidate.confidence}",
                    "unknown",
                    now,
                ),
            )
            asset_id = int(cursor.lastrowid or 0)
            image_local_path = asset["image_local_path"]
            thumbnail_local_path = asset["thumbnail_local_path"]
            images_added += 1
            if progress_callback:
                progress_callback({"downloaded_images_delta": 1, "images_added": images_added})

        prompt_hash = content_hash(candidate.prompt)
        conn.execute(
            """
            INSERT OR IGNORE INTO prompt_candidates
                (repo_id, repo_name, repo_url, source_page_url, source_file, source_heading, line_start, line_end,
                 original_prompt, prompt_type, context, content_hash, status, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                repo_id,
                record["repo_name"],
                record["repo_url"],
                candidate.source_page_url,
                candidate.source_file,
                candidate.source_heading,
                candidate.line_start,
                candidate.line_end,
                candidate.prompt,
                category,
                candidate.evidence,
                prompt_hash,
                "candidate",
                now,
            ),
        )
        prompt_row = conn.execute(
            """
            SELECT id FROM prompt_candidates
            WHERE repo_id = ? AND source_file = ? AND line_start = ? AND content_hash = ?
            """,
            (repo_id, candidate.source_file, candidate.line_start, prompt_hash),
        ).fetchone()
        prompt_candidate_id = prompt_row["id"] if prompt_row else None

        filename = PurePosixPath(urlparse(candidate.image_url).path).name
        conn.execute(
            """
            INSERT OR IGNORE INTO image_candidates
                (repo_id, source_page_url, source_file, source_heading, line_start, image_original_url, image_resolved_url,
                 image_local_path, thumbnail_local_path, image_hash, width, height, file_size, alt_text, caption, context,
                 filename, asset_id, status, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                repo_id,
                candidate.source_page_url,
                candidate.source_file,
                candidate.source_heading,
                candidate.line_start,
                candidate.image_url,
                candidate.image_url,
                image_local_path,
                thumbnail_local_path,
                asset["image_hash"],
                asset["width"],
                asset["height"],
                asset["file_size"],
                "",
                "",
                candidate.evidence,
                filename,
                asset_id,
                "candidate",
                now,
            ),
        )
        image_row = conn.execute(
            """
            SELECT id FROM image_candidates
            WHERE repo_id = ? AND source_file = ? AND image_resolved_url = ?
            """,
            (repo_id, candidate.source_file, candidate.image_url),
        ).fetchone()
        image_candidate_id = image_row["id"] if image_row else None

        review_status, review_reason = _candidate_review_status(candidate, license_value)
        cursor = conn.execute(
            """
            INSERT OR IGNORE INTO pair_candidates
                (repo_id, repo_name, repo_url, source_page_url, source_file, source_heading, prompt_candidate_id,
                 image_candidate_id, original_prompt, image_original_url, image_local_path, image_hash, match_type,
                 match_score, structural_score, distance_score, filename_score, semantic_score, penalty_score,
                 evidence, review_status, review_reason, selection_status, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                repo_id,
                record["repo_name"],
                record["repo_url"],
                candidate.source_page_url,
                candidate.source_file,
                candidate.source_heading,
                prompt_candidate_id,
                image_candidate_id,
                candidate.prompt,
                candidate.image_url,
                image_local_path,
                asset["image_hash"],
                candidate.relation_type,
                candidate.confidence,
                candidate.structural_score,
                candidate.distance_score,
                candidate.filename_score,
                candidate.semantic_score,
                candidate.penalty_score,
                candidate.evidence,
                review_status,
                review_reason,
                "pending_review",
                now,
                now,
            ),
        )
        if cursor.rowcount:
            saved += 1

    return saved, images_added


def list_pair_candidates(
    page: int = 1,
    page_size: int = 24,
    search: Optional[str] = None,
    review_status: Optional[str] = None,
    match_type: Optional[str] = None,
    repo_id: Optional[int] = None,
) -> Dict[str, Any]:
    where = ["1 = 1"]
    params: List[Any] = []
    if search:
        term = f"%{search}%"
        where.append("(repo_name LIKE ? OR original_prompt LIKE ? OR evidence LIKE ? OR source_file LIKE ?)")
        params.extend([term, term, term, term])
    if review_status:
        where.append("review_status = ?")
        params.append(review_status)
    if match_type:
        where.append("match_type = ?")
        params.append(match_type)
    if repo_id:
        where.append("repo_id = ?")
        params.append(repo_id)
    clause = " AND ".join(where)
    return paginate(
        f"SELECT * FROM pair_candidates WHERE {clause} ORDER BY match_score DESC, updated_at DESC, id DESC",
        f"SELECT COUNT(*) FROM pair_candidates WHERE {clause}",
        tuple(params),
        page,
        page_size,
    )


def get_pair_candidate(candidate_id: int) -> Optional[Dict[str, Any]]:
    return fetch_one("SELECT * FROM pair_candidates WHERE id = ?", (candidate_id,))


def update_pair_candidate_status(candidate_id: int, review_status: str, review_reason: Optional[str] = None) -> Dict[str, Any]:
    now = utc_now()
    with get_connection() as conn:
        conn.execute(
            """
            UPDATE pair_candidates
            SET review_status = ?, review_reason = COALESCE(?, review_reason), updated_at = ?
            WHERE id = ?
            """,
            (review_status, review_reason, now, candidate_id),
        )
    candidate = get_pair_candidate(candidate_id)
    if not candidate:
        raise ValueError("候选配对不存在")
    return candidate


def accept_pair_candidate(candidate_id: int, selection_status: str = "pending_review") -> Dict[str, Any]:
    candidate = get_pair_candidate(candidate_id)
    if not candidate:
        raise ValueError("候选配对不存在")
    repo = fetch_one("SELECT * FROM repos WHERE id = ?", (candidate["repo_id"],))
    if not repo:
        raise ValueError("候选配对所属仓库不存在")

    now = utc_now()
    category = repo.get("category") or "unknown"
    with get_connection() as conn:
        duplicate = conn.execute(
            """
            SELECT id FROM prompt_effect_pairs
            WHERE repo_id = ? AND image_hash = ? AND original_prompt = ?
            """,
            (candidate["repo_id"], candidate["image_hash"], candidate["original_prompt"]),
        ).fetchone()
        if duplicate:
            pair_id = duplicate["id"]
        else:
            review = f"{default_effect_review(True, candidate['match_type'])}\n证据：{candidate['evidence']}"
            cursor = conn.execute(
                """
                INSERT INTO prompt_effect_pairs
                    (repo_id, repo_name, repo_url, source_page_url, original_prompt, prompt_cn_explanation,
                     image_original_url, image_local_path, image_hash, task_type, category, scenario, visual_style,
                     quality_level, selection_status, effect_review, reusable_value, license, commercial_risk,
                     pair_relation_type, pair_evidence, pair_confidence, generated_by,
                     local_note_path, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    candidate["repo_id"],
                    candidate["repo_name"],
                    candidate["repo_url"],
                    candidate["source_page_url"],
                    candidate["original_prompt"],
                    build_cn_explanation(candidate["original_prompt"], category),
                    candidate["image_original_url"],
                    candidate["image_local_path"],
                    candidate["image_hash"],
                    category,
                    category,
                    infer_scenario(category, candidate["original_prompt"]),
                    "待人工整理",
                    "pending_review",
                    selection_status,
                    review,
                    "候选匹配已被接受，可作为 Prompt 效果样本继续复查和精选。",
                    repo.get("license") or "unknown",
                    "unknown",
                    candidate["match_type"],
                    candidate["evidence"],
                    candidate["match_score"],
                    "pair_candidate_review",
                    None,
                    now,
                    now,
                ),
            )
            pair_id = int(cursor.lastrowid)
        conn.execute(
            """
            UPDATE pair_candidates
            SET review_status = 'accepted', selection_status = ?, created_pair_id = ?, updated_at = ?
            WHERE id = ?
            """,
            (selection_status, pair_id, now, candidate_id),
        )
        pair_count = conn.execute("SELECT COUNT(*) FROM prompt_effect_pairs WHERE repo_id = ?", (candidate["repo_id"],)).fetchone()[0]
        conn.execute(
            """
            UPDATE repos
            SET has_prompt_effect_pairs = CASE WHEN ? > 0 THEN 1 ELSE 0 END,
                prompt_effect_pair_count = ?
            WHERE id = ?
            """,
            (pair_count, pair_count, candidate["repo_id"]),
        )
    refreshed = get_pair_candidate(candidate_id)
    if not refreshed:
        raise ValueError("候选配对不存在")
    return refreshed
