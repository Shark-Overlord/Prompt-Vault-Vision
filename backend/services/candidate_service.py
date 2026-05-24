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
    extract_prompt_video_pairs,
    infer_scenario,
)
from utils.image_utils import download_image, download_video_preview, extract_markdown_image_urls


SCAN_EXTENSIONS = {".md", ".mdx", ".json", ".jsonl", ".csv", ".yaml", ".yml", ".toml", ".txt", ".prompt"}
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
    "components",
    "design-system",
    "design_system",
    "images",
    "patterns",
    "screenshots",
    "tools",
    "skills",
    "servers",
    "scripts",
    ".cursor",
    ".claude",
)
LOOSE_TEXT_SCAN_DIRS = {"docs", "examples", "prompts", "components", "design-system", "design_system", "patterns", "samples"}
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
VIDEO_KEYS = (
    "video",
    "video_url",
    "video_urls",
    "output_video",
    "result_video",
    "example_video",
    "clip",
    "clip_url",
    "demo_video",
    "preview_video",
    "mp4",
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
    if suffix in {".txt", ".prompt"}:
        return len(parts) > 1 and parts[0] in LOOSE_TEXT_SCAN_DIRS
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


def _looks_like_url_or_video(value: Any) -> bool:
    if not isinstance(value, str):
        return False
    lower = value.strip().lower()
    if not lower:
        return False
    if "github.com/user-attachments/assets/" in lower:
        return True
    if lower.startswith(("http://", "https://", "./", "../", "/")):
        ext = PurePosixPath(urlparse(lower).path).suffix.lower()
        return ext in {".mp4", ".mov", ".webm", ".m4v", ".avi"} or "github.com/user-attachments/assets/" in lower
    return PurePosixPath(urlparse(lower).path).suffix.lower() in {".mp4", ".mov", ".webm", ".m4v", ".avi"}


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
    video_key = next((lowered[key] for key in image_keys if key in lowered and _looks_like_url_or_video(obj.get(lowered[key]))), None)
    media_key = image_key or video_key
    if prompt_key and media_key:
        prompt = " ".join(str(obj[prompt_key]).strip().split())
        image_url = _resolve_image(base_url, str(obj[media_key]))
        if len(prompt) >= 24:
            media_label = "视频" if video_key and media_key == video_key else "图片"
            pairs.append(
                PromptEffectCandidate(
                    prompt=prompt,
                    image_url=image_url,
                    relation_type="direct_pair",
                    evidence=f"结构化对象配对：{source_file} 中 {path_label} 同时包含 prompt 字段和 {media_key} {media_label}字段，属于强绑定。",
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
        video_key = next((lowered[key] for key in image_keys if key in lowered and _looks_like_url_or_video(row.get(lowered[key]))), None)
        media_key = image_key or video_key
        if not prompt_key or not media_key:
            continue
        prompt = " ".join(str(row[prompt_key]).strip().split())
        if len(prompt) < 24:
            continue
        image_url = _resolve_image(base_url, str(row[media_key]))
        media_label = "视频" if video_key and media_key == video_key else "图片"
        pairs.append(
            PromptEffectCandidate(
                prompt=prompt,
                image_url=image_url,
                relation_type="direct_pair",
                evidence=f"CSV 行配对：{source_file} 第 {index} 行同时包含 prompt 列和 {media_key} {media_label}列，属于结构强绑定。",
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
    video_key = next((key for key in image_keys if key in mapping and _looks_like_url_or_video(mapping[key])), None)
    media_key = image_key or video_key

    if prompt_key and media_key:
        prompt = " ".join(mapping[prompt_key].split())
        media_value = mapping[media_key]
        prompt_range = line_ranges.get(prompt_key, (0, 0))
        media_range = line_ranges.get(media_key, (0, 0))
        heading = mapping.get("title") or mapping.get("name") or mapping.get("alt_text") or "YAML"
        media_label = "视频" if video_key and media_key == video_key else "图片"
        pairs.append(
            PromptEffectCandidate(
                prompt=prompt,
                image_url=_resolve_image(base_url, media_value),
                relation_type="direct_pair",
                evidence=f"YAML 对象强绑定：{source_file} 同一顶层对象同时包含 {prompt_key} 提示词字段和 {media_key} {media_label}字段，字段顺序不影响匹配。",
                confidence=94,
                source_page_url=source_page_url,
                source_file=source_file,
                source_heading=heading,
                line_start=prompt_range[0],
                line_end=max(prompt_range[1], media_range[1]),
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
        elif key in image_keys and prompt_line and (_looks_like_url_or_image(value) or _looks_like_url_or_video(value)):
            media_label = "视频" if _looks_like_url_or_video(value) else "图片"
            pairs.append(
                PromptEffectCandidate(
                    prompt=" ".join(prompt_line[1].split()),
                    image_url=_resolve_image(base_url, value),
                    relation_type="likely_pair",
                    evidence=f"YAML 邻近字段配对：{source_file} 中 prompt 字段与 {key} {media_label}字段相邻，需要人工复查。",
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


NUMBERED_VIDEO_CASE_RE = re.compile(r"(?im)^###\s+(?:No\.?|Case)\s*(?P<case_id>\d+)\b[^\n]*$")
PROMPT_SECTION_RE = re.compile(r"(?im)^#{4,6}\s+.*?\bprompt\b.*$")


def _extract_numbered_case_prompts_from_markdown(document: Dict[str, str]) -> Dict[str, Dict[str, Any]]:
    content = document.get("content") or ""
    matches = list(NUMBERED_VIDEO_CASE_RE.finditer(content))
    results: Dict[str, Dict[str, Any]] = {}
    for index, match in enumerate(matches):
        case_id = match.group("case_id")
        block_start = match.start()
        block_end = matches[index + 1].start() if index + 1 < len(matches) else len(content)
        block = content[block_start:block_end]
        prompt = ""
        prompt_heading = PROMPT_SECTION_RE.search(block)
        if prompt_heading:
            prompt_block = block[prompt_heading.end():]
            prompt_candidates = extract_prompt_candidates(prompt_block, limit=3)
            if prompt_candidates:
                prompt = prompt_candidates[0]
        if not prompt:
            prompt_candidates = extract_prompt_candidates(block, limit=3)
            if prompt_candidates:
                prompt = prompt_candidates[0]
        if not prompt:
            continue
        prompt_pos = block.find(prompt)
        line_start = _line_number(content, block_start + max(prompt_pos, 0))
        line_end = line_start + max(prompt.count("\n"), 0)
        results[case_id] = {
            "prompt": prompt,
            "source_file": document.get("path") or "",
            "source_page_url": document.get("source_page_url") or "",
            "source_heading": _clean_heading(match.group(0)),
            "line_start": line_start,
            "line_end": line_end,
        }
    return results


def _clean_heading(text: str) -> str:
    return re.sub(r"^#+\s*", "", (text or "").strip())


def _extract_numbered_video_map(document: Dict[str, str]) -> Dict[str, str]:
    path = (document.get("path") or "").lower()
    if not path.endswith((".json", ".jsonl")):
        return {}
    try:
        payload = json.loads(document.get("content") or "{}")
    except Exception:
        return {}
    candidates: Dict[str, Any] = {}
    if isinstance(payload, dict):
        for key in ("prompts", "videos", "video_urls", "results"):
            if isinstance(payload.get(key), dict):
                candidates = payload[key]
                break
        if not candidates:
            candidates = payload
    result: Dict[str, str] = {}
    if not isinstance(candidates, dict):
        return result
    base_url = document.get("raw_base_url") or ""
    for key, value in candidates.items():
        case_id = str(key).strip()
        if not re.fullmatch(r"\d+", case_id):
            continue
        if not _looks_like_url_or_video(value):
            continue
        result[case_id] = _resolve_image(base_url, str(value))
    return result


def _extract_cross_file_numbered_video_pairs(documents: Sequence[Dict[str, str]], limit: Optional[int]) -> List[PromptEffectCandidate]:
    prompt_cases: Dict[str, Dict[str, Any]] = {}
    video_map: Dict[str, str] = {}
    for document in documents:
        path = (document.get("path") or "").lower()
        if path.endswith((".md", ".mdx")):
            prompt_cases.update(_extract_numbered_case_prompts_from_markdown(document))
        elif path.endswith((".json", ".jsonl")):
            video_map.update(_extract_numbered_video_map(document))

    pairs: List[PromptEffectCandidate] = []
    max_count = FULL_SCAN_LIMIT if limit is None else max(0, int(limit))
    for case_id, payload in prompt_cases.items():
        video_url = video_map.get(case_id)
        if not video_url:
            continue
        pairs.append(
            PromptEffectCandidate(
                prompt=payload["prompt"],
                image_url=video_url,
                relation_type="direct_pair",
                evidence=f"跨文件编号配对：Markdown 案例 {case_id} 提供 Prompt，结构化文件提供同编号视频链接，属于强绑定。",
                confidence=96,
                source_page_url=payload["source_page_url"],
                source_file=payload["source_file"],
                source_heading=payload["source_heading"],
                line_start=payload["line_start"],
                line_end=payload["line_end"],
                structural_score=62,
                distance_score=20,
                filename_score=8,
                semantic_score=6,
                penalty_score=0,
            )
        )
        if len(pairs) >= max_count:
            break
    return pairs


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
    seen_media_urls: set[str] = set()
    prompt_keys = _merge_keys(PROMPT_KEYS, _template_string_values(template, ("prompt_locators", "prompt_field_names")))
    media_keys = _merge_keys((*IMAGE_KEYS, *VIDEO_KEYS), _template_string_values(template, ("image_locators", "image_field_names", "video_locators", "video_field_names")))

    sorted_documents = sorted(documents, key=_document_scan_priority)
    total_files = len(sorted_documents)

    if category == "video_generation_prompt":
        cross_file_pairs = _extract_cross_file_numbered_video_pairs(sorted_documents, total_pair_limit)
        for pair in cross_file_pairs:
            key = (pair.prompt, pair.image_url)
            if key in seen_pairs or pair.image_url in seen_media_urls:
                continue
            seen_pairs.add(key)
            seen_media_urls.add(pair.image_url)
            pair_candidates.append(pair)

    for index, document in enumerate(sorted_documents, start=1):
        if total_pair_limit is not None and len(pair_candidates) >= total_pair_limit:
            break
        path_value = document["path"]
        content = document["content"]
        base_url = document.get("raw_base_url") or ""
        source_page_url = document.get("source_page_url") or ""
        suffix = PurePosixPath(path_value).suffix.lower()
        pair_limit = _remaining_limit(len(pair_candidates), total_pair_limit)

        prompt_candidates.extend(extract_prompt_candidates(content, limit=50))
        if suffix in {".md", ".mdx"}:
            preview_images.extend(extract_markdown_image_urls(content, base_url=base_url))
            if category == "video_generation_prompt":
                pairs = extract_prompt_video_pairs(content, base_url=base_url, source_page_url=source_page_url, limit=pair_limit)
            else:
                pairs = extract_prompt_effect_pairs(content, base_url=base_url, source_page_url=source_page_url, limit=pair_limit)
        elif suffix in {".json", ".jsonl"}:
            pairs = _extract_json_pairs(content, base_url, source_page_url, path_value, pair_limit, prompt_keys, media_keys)
        elif suffix == ".csv":
            pairs = _extract_csv_pairs(content, base_url, source_page_url, path_value, pair_limit, prompt_keys, media_keys)
        elif suffix in {".yaml", ".yml"}:
            pairs = _extract_yaml_pairs(content, base_url, source_page_url, path_value, pair_limit, prompt_keys, media_keys)
        else:
            pairs = []

        for pair in pairs:
            key = (pair.prompt, pair.image_url)
            if key in seen_pairs:
                continue
            if pair.image_url in seen_media_urls:
                continue
            seen_pairs.add(key)
            seen_media_urls.add(pair.image_url)
            pair_candidates.append(
                replace(
                    pair,
                    source_file=pair.source_file or path_value,
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
                    "current_file": path_value,
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
        if not asset and category == "video_generation_prompt":
            asset = await download_video_preview(candidate.image_url)
        if not asset:
            if progress_callback:
                progress_callback({"error_count_delta": 1})
            continue

        asset_row = conn.execute("SELECT * FROM assets WHERE image_hash = ?", (asset["image_hash"],)).fetchone()
        if asset_row:
            asset_id = asset_row["id"]
            image_local_path = asset_row["image_local_path"]
            thumbnail_local_path = asset_row["thumbnail_local_path"]
            cloud_storage_url = asset_row["cloud_storage_url"]
            thumbnail_cloud_storage_url = asset_row["thumbnail_cloud_storage_url"]
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
            cloud_storage_url = None
            thumbnail_cloud_storage_url = None
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
                 image_local_path, cloud_storage_url, thumbnail_local_path, thumbnail_cloud_storage_url, image_hash, width, height, file_size,
                 alt_text, caption, context, filename, asset_id, status, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
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
                cloud_storage_url,
                thumbnail_local_path,
                thumbnail_cloud_storage_url,
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
                 image_candidate_id, original_prompt, image_original_url, image_local_path, cloud_storage_url, image_hash, match_type,
                 match_score, structural_score, distance_score, filename_score, semantic_score, penalty_score,
                 evidence, review_status, review_reason, selection_status, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
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
                cloud_storage_url,
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
                     image_original_url, image_local_path, cloud_storage_url, image_hash, task_type, category, scenario, visual_style,
                     quality_level, selection_status, effect_review, reusable_value, license, commercial_risk,
                     pair_relation_type, pair_evidence, pair_confidence, generated_by,
                     local_note_path, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
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
                    candidate.get("cloud_storage_url"),
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
