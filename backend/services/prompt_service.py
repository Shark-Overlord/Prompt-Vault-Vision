from __future__ import annotations

import re
import html
from dataclasses import dataclass
from pathlib import PurePosixPath
from typing import List
from urllib.parse import urljoin, urlparse


PROMPT_LABEL_RE = re.compile(
    r"(?:^|\n)\s*(?:[-*]\s*)?(?:\*\*)?"
    r"(?P<label>prompt text|sample prompt|full prompt|exact prompt|text prompt|positive prompt|negative prompt|user prompt|image prompt|video prompt|input prompt|prompt template|prompt|提示词|正向提示词|反向提示词)"
    r"(?:\*\*)?\s*[:：]\s*(?:\*\*)?\s*(?P<prompt>.{24,2400}?)(?=\n\s*\n|#{1,6}\s|!\[|<img\b|```|\n\s*(?:[-*]\s*)?(?:\*\*)?(?:example images?|generated images?|image|output|result|source|author|model)(?:\*\*)?\s*[:：]|$)",
    re.IGNORECASE | re.DOTALL,
)

FENCED_RE = re.compile(r"```(?P<lang>[a-zA-Z0-9_-]*)\s*\n(?P<body>.*?)```", re.IGNORECASE | re.DOTALL)
HEADING_RE = re.compile(r"(?m)^(?P<marks>#{1,6})\s+(?P<title>.+?)\s*$")
IMAGE_RE = re.compile(r"!\[(?P<alt>[^\]]*)\]\((?P<url>[^)\s]+)(?:\s+\"[^\"]*\")?\)", re.IGNORECASE)
LINK_RE = re.compile(r"(?<!\!)\[(?P<label>[^\]]+)\]\((?P<url>[^)\s]+)(?:\s+\"[^\"]*\")?\)", re.IGNORECASE)
HTML_IMAGE_RE = re.compile(r"<img\b(?P<attrs>[^>]*)>", re.IGNORECASE | re.DOTALL)
HTML_VIDEO_RE = re.compile(r"<video\b(?P<attrs>[^>]*)>", re.IGNORECASE | re.DOTALL)
HTML_SOURCE_RE = re.compile(r"<source\b(?P<attrs>[^>]*)>", re.IGNORECASE | re.DOTALL)
URL_RE = re.compile(r"https?://[^\s<>()]+", re.IGNORECASE)
HTML_ATTR_RE = re.compile(
    r"""(?P<name>[a-zA-Z_:][-a-zA-Z0-9_:.]*)\s*=\s*(?:"(?P<double>[^"]*)"|'(?P<single>[^']*)'|(?P<bare>[^\s>]+))""",
    re.IGNORECASE,
)
GALLERY_ENTRY_RE = re.compile(r"(?m)^###\s+(?:No\.\s*\d+\s*[:：-]\s*)?(?P<title>.+?)\s*$")
GALLERY_PROMPT_HEADING_RE = re.compile(r"(?im)^#{4,6}\s+.*?(?:prompt|提示词|提示語|提示|正向提示).*?$")
GALLERY_IMAGE_HEADING_RE = re.compile(r"(?im)^#{4,6}\s+.*?(?:generated images?|images?|生成图片|生成圖|效果图|效果圖|输出图|输出圖片).*?$")

CODE_LANGS = {
    "bash",
    "shell",
    "sh",
    "powershell",
    "ps1",
    "python",
    "py",
    "javascript",
    "js",
    "typescript",
    "ts",
    "tsx",
    "jsx",
    "json",
    "yaml",
    "yml",
    "toml",
    "ini",
    "sql",
}

BAD_IMAGE_HINTS = (
    "badge",
    "shields.io",
    "license.svg",
    "stars.svg",
    "forks.svg",
    "workflow",
    "actions",
    "logo",
    "avatar",
    "icon",
    "opengraph",
    "og-image",
    "social",
    "cover",
    "banner",
)

PAIR_SECTION_HINTS = (
    "prompt",
    "example",
    "examples",
    "case",
    "gallery",
    "showcase",
    "result",
    "results",
    "output",
    "before",
    "after",
    "demo",
    "效果",
    "案例",
    "示例",
    "输出",
    "结果",
)

IMAGE_PAIR_HINTS = (
    "result",
    "output",
    "generated",
    "generation",
    "effect",
    "example",
    "demo",
    "preview",
    "before",
    "after",
    "screenshot",
    "效果",
    "输出",
    "结果",
    "示例",
    "预览",
)

VIDEO_SECTION_HINTS = (
    "video",
    "generated video",
    "result video",
    "output video",
    "video result",
    "clip",
    "demo video",
    "sample video",
    "user-attachments/assets",
    "veo",
    "kling",
    "runway",
    "seedance",
    "wan",
)

VIDEO_LABEL_HINTS = (
    "video",
    "clip",
    "demo",
    "result",
    "output",
    "generated",
    "preview",
)

WORKFLOW_SCREENSHOT_HINTS = (
    "workflow",
    "node graph",
    "nodegraph",
    "comfyui",
    "screenshot",
    "screen shot",
)

PROMPT_QUALITY_HINTS = (
    "create",
    "generate",
    "design",
    "render",
    "make",
    "imagine",
    "photorealistic",
    "cinematic",
    "scene",
    "video",
    "camera",
    "shot",
    "clip",
    "motion",
    "seconds",
    "landing",
    "dashboard",
    "poster",
    "product",
    "style",
    "composition",
    "lighting",
    "构图",
    "生成",
    "设计",
    "风格",
    "镜头",
    "海报",
)

COMMAND_HINTS = (
    "pnpm ",
    "npm ",
    "yarn ",
    "pip ",
    "python ",
    "node ",
    "cargo ",
    "git ",
    "cd ",
    "mkdir ",
    "src/",
    "import ",
    "from ",
    "def ",
    "class ",
)

DOC_INSTRUCTION_HINTS = (
    "remember, to update",
    "open a cli",
    "open a terminal",
    "enter the following",
    "run the command",
    "install the",
    "download the",
    "clone the",
)


@dataclass(frozen=True)
class PromptCandidate:
    text: str
    start: int
    end: int
    heading: str
    source: str


@dataclass(frozen=True)
class ImageCandidate:
    url: str
    alt: str
    start: int
    end: int
    heading: str
    context: str


@dataclass(frozen=True)
class VideoCandidate:
    url: str
    label: str
    start: int
    end: int
    heading: str
    context: str


@dataclass(frozen=True)
class MarkdownContentBlock:
    kind: str
    title: str
    start: int
    end: int
    text: str
    line_start: int
    line_end: int


@dataclass(frozen=True)
class PromptEffectCandidate:
    prompt: str
    image_url: str
    relation_type: str
    evidence: str
    confidence: int
    source_page_url: str
    source_file: str = ""
    source_heading: str = ""
    line_start: int = 0
    line_end: int = 0
    structural_score: int = 0
    distance_score: int = 0
    filename_score: int = 0
    semantic_score: int = 0
    penalty_score: int = 0


CASE_TITLE_RE = re.compile(r"(?i)(?:^|\b)(case|example|demo|sample|prompt|no\.?\s*\d+|\d+[.)])(?:\b|$)")
DELIMITER_RE = re.compile(r"(?m)^\s*(?:-{3,}|\*{3,}|_{3,})\s*$")
LIST_ITEM_RE = re.compile(r"(?m)^(?P<indent>\s*)(?:[-*+]|\d+[.)])\s+")


def _clean_text(text: str) -> str:
    return " ".join((text or "").strip().split())


def _clean_prompt_body(text: str) -> str:
    stripped = (text or "").strip()
    fenced = FENCED_RE.search(stripped)
    if fenced and stripped[: fenced.start()].strip() == "" and stripped[fenced.end():].strip() == "":
        stripped = fenced.group("body")
    else:
        stripped = "\n".join(line for line in stripped.splitlines() if not line.strip().startswith("```"))
    stripped = stripped.strip()
    if len(stripped) >= 2 and stripped.startswith("`") and stripped.endswith("`"):
        stripped = stripped.strip("`").strip()
    return _clean_text(stripped)


def _current_heading(markdown: str, pos: int) -> str:
    heading = ""
    for match in HEADING_RE.finditer(markdown[:pos]):
        heading = _clean_text(match.group("title"))
    return heading


def _line_number(text: str, pos: int) -> int:
    return (text or "")[: max(0, pos)].count("\n") + 1


def _section_bounds(markdown: str, pos: int) -> tuple[int, int]:
    headings = list(HEADING_RE.finditer(markdown))
    start = 0
    end = len(markdown)
    current_level = 0
    for index, match in enumerate(headings):
        if match.start() <= pos:
            start = match.start()
            current_level = len(match.group("marks"))
            continue
        if match.start() > pos and (current_level == 0 or len(match.group("marks")) <= current_level):
            end = match.start()
            break
    return start, end


def _contains_any(text: str, hints: tuple[str, ...]) -> bool:
    lower = text.lower()
    return any(hint.lower() in lower for hint in hints)


def _is_bad_image(url: str, alt: str) -> bool:
    probe = f"{url} {alt}".lower()
    return any(hint in probe for hint in BAD_IMAGE_HINTS)


def _image_pair_penalty(image: ImageCandidate) -> int:
    probe = f"{image.alt} {image.url} {image.context[:240]}".lower()
    if any(hint in probe for hint in WORKFLOW_SCREENSHOT_HINTS):
        return 12
    return 0


def _looks_like_video_url(url: str, label: str = "", context: str = "") -> bool:
    lower_url = (url or "").lower()
    path = urlparse(lower_url).path
    if PurePosixPath(path).suffix.lower() in {".mp4", ".mov", ".webm", ".m4v", ".avi"}:
        return True
    if "github.com/user-attachments/assets/" in lower_url and _contains_any(f"{label} {context}", VIDEO_SECTION_HINTS):
        return True
    return False


def _slug_tokens(text: str) -> set[str]:
    clean = re.sub(r"[^a-zA-Z0-9\u4e00-\u9fff]+", " ", (text or "").lower())
    return {token for token in clean.split() if len(token) >= 2}


def _image_anchor_tokens(image: ImageCandidate) -> set[str]:
    path = PurePosixPath(urlparse(image.url).path)
    stem = re.sub(r"[-_]+", " ", path.stem)
    return _slug_tokens(f"{stem} {image.alt}")


def _anchor_match_score(image: ImageCandidate, prompt_text: str, heading: str) -> tuple[int, str]:
    tokens = _image_anchor_tokens(image)
    if not tokens:
        return 0, ""
    target_tokens = _slug_tokens(f"{heading} {prompt_text[:500]}")
    overlap = tokens & target_tokens
    if len(overlap) >= 2:
        return 10, f"图片文件名/alt 锚点与 Prompt 或标题存在重合：{', '.join(sorted(overlap)[:4])}"
    if len(overlap) == 1 and heading:
        return 6, f"图片文件名/alt 锚点与标题存在重合：{next(iter(overlap))}"
    return 0, ""


def _block_kind_for_heading(title: str, level: int) -> str:
    if CASE_TITLE_RE.search(title or ""):
        return "case_section"
    return "heading_section"


def _has_prompt_and_image_signal(text: str) -> bool:
    if not text or not (IMAGE_RE.search(text) or HTML_IMAGE_RE.search(text)):
        return False
    probe = text[:4000].lower()
    if any(hint in probe for hint in ("prompt", "positive prompt", "image prompt", "video prompt", "生成提示词", "提示词")):
        return True
    return any(hint in probe for hint in PROMPT_QUALITY_HINTS)


def _has_prompt_and_video_signal(text: str) -> bool:
    if not text:
        return False
    probe = text[:4000].lower()
    has_video = False
    if "github.com/user-attachments/assets/" in probe:
        has_video = _contains_any(probe, VIDEO_SECTION_HINTS)
    if not has_video:
        for match in LINK_RE.finditer(text):
            label = _clean_text(match.group("label"))
            url = match.group("url").strip()
            if _looks_like_video_url(url, label, probe) or (_contains_any(label, VIDEO_LABEL_HINTS) and "http" in url):
                has_video = True
                break
    if not has_video:
        for match in URL_RE.finditer(text):
            if _looks_like_video_url(match.group(0).strip(), "", probe):
                has_video = True
                break
    if not has_video and (HTML_VIDEO_RE.search(text) or HTML_SOURCE_RE.search(text)):
        has_video = True
    if not has_video:
        return False
    if any(hint in probe for hint in ("prompt", "positive prompt", "video prompt", "提示词", "视频提示词")):
        return True
    return any(hint in probe for hint in PROMPT_QUALITY_HINTS)


def split_markdown_content_blocks(markdown: str, media_mode: str = "image") -> List[MarkdownContentBlock]:
    text = markdown or ""
    blocks: List[MarkdownContentBlock] = []
    seen: set[tuple[str, int, int]] = set()

    def add_block(kind: str, title: str, start: int, end: int) -> None:
        start = max(0, start)
        end = min(len(text), max(start, end))
        block_text = text[start:end].strip()
        has_signal = _has_prompt_and_video_signal(block_text) if media_mode == "video" else _has_prompt_and_image_signal(block_text)
        if len(block_text) < 24 or not has_signal:
            return
        key = (kind, start, end)
        if key in seen:
            return
        seen.add(key)
        blocks.append(
            MarkdownContentBlock(
                kind=kind,
                title=_clean_text(title),
                start=start,
                end=end,
                text=text[start:end],
                line_start=_line_number(text, start),
                line_end=_line_number(text, end),
            )
        )

    headings = list(HEADING_RE.finditer(text))
    for index, heading in enumerate(headings):
        level = len(heading.group("marks"))
        title = heading.group("title")
        end = len(text)
        for next_heading in headings[index + 1:]:
            if len(next_heading.group("marks")) <= level:
                end = next_heading.start()
                break
        add_block(_block_kind_for_heading(title, level), title, heading.start(), end)

    delimiter_matches = list(DELIMITER_RE.finditer(text))
    if delimiter_matches:
        delimiter_positions = [0, *[match.end() for match in delimiter_matches], len(text)]
        delimiter_starts = [0, *[match.start() for match in delimiter_matches], len(text)]
        for index in range(len(delimiter_positions) - 1):
            start = delimiter_positions[index]
            end = delimiter_starts[index + 1]
            add_block("delimiter_block", _current_heading(text, start), start, end)

    list_items = list(LIST_ITEM_RE.finditer(text))
    for index, item in enumerate(list_items):
        start = item.start()
        end = list_items[index + 1].start() if index + 1 < len(list_items) else len(text)
        add_block("list_item_block", _current_heading(text, start), start, end)

    if not headings:
        add_block("root_block", "", 0, len(text))

    blocks.sort(key=lambda block: (block.start, block.end - block.start, block.kind))
    return blocks


def _parse_html_attrs(attrs: str) -> dict[str, str]:
    parsed: dict[str, str] = {}
    for match in HTML_ATTR_RE.finditer(attrs or ""):
        value = match.group("double") or match.group("single") or match.group("bare") or ""
        parsed[match.group("name").lower()] = html.unescape(value.strip())
    return parsed


def _is_probable_prompt(text: str, max_length: int = 1600) -> bool:
    clean = _clean_text(text)
    if not (24 <= len(clean) <= max_length):
        return False
    lower = clean.lower()
    if lower.startswith(("![", "<img", "#")) or "### " in clean[:120] or "## " in clean[:120]:
        return False
    if lower.startswith(COMMAND_HINTS):
        return False
    command_hits = sum(1 for hint in COMMAND_HINTS if hint in lower[:240])
    if command_hits >= 2:
        return False
    if "http" in lower[:100]:
        return False
    if re.match(r"^\d+[.)]\s", clean) and not _contains_any(clean, PROMPT_QUALITY_HINTS):
        return False
    if any(hint in lower[:280] for hint in DOC_INSTRUCTION_HINTS) and not _contains_any(clean, PROMPT_QUALITY_HINTS):
        return False
    if not _contains_any(clean, PROMPT_QUALITY_HINTS) and len(clean.split()) < 10:
        return False
    return True


def extract_prompt_candidates(markdown: str, limit: int = 5) -> List[str]:
    return [candidate.text for candidate in _extract_prompt_candidates_with_positions(markdown, limit)]


def _extract_prompt_candidates_with_positions(markdown: str, limit: int = 20) -> List[PromptCandidate]:
    candidates: List[PromptCandidate] = []
    seen: set[str] = set()

    for match in PROMPT_LABEL_RE.finditer(markdown or ""):
        prompt = _clean_prompt_body(match.group("prompt"))
        if _is_probable_prompt(prompt) and prompt not in seen:
            seen.add(prompt)
            candidates.append(
                PromptCandidate(
                    text=prompt,
                    start=match.start("prompt"),
                    end=match.end("prompt"),
                    heading=_current_heading(markdown, match.start()),
                    source="label",
                )
            )
        if len(candidates) >= limit:
            return candidates

    for match in FENCED_RE.finditer(markdown or ""):
        lang = (match.group("lang") or "").lower()
        if lang in CODE_LANGS:
            continue
        prefix = markdown[max(0, match.start() - 260): match.start()]
        heading = _current_heading(markdown, match.start())
        if not _contains_any(f"{prefix} {heading}", PAIR_SECTION_HINTS):
            continue
        prompt = _clean_prompt_body(match.group("body"))
        if _is_probable_prompt(prompt) and prompt not in seen:
            seen.add(prompt)
            candidates.append(
                PromptCandidate(
                    text=prompt,
                    start=match.start("body"),
                    end=match.end("body"),
                    heading=heading,
                    source="fenced_prompt_context",
                )
            )
        if len(candidates) >= limit:
            break
    return candidates


def _extract_image_candidates(markdown: str, base_url: str) -> List[ImageCandidate]:
    images: List[ImageCandidate] = []
    seen_urls: set[str] = set()
    for match in IMAGE_RE.finditer(markdown or ""):
        alt = _clean_text(match.group("alt"))
        raw_url = match.group("url").strip()
        if raw_url.startswith("#"):
            continue
        url = urljoin(base_url, raw_url) if base_url else raw_url
        if _is_bad_image(url, alt) or url in seen_urls:
            continue
        seen_urls.add(url)
        start = max(0, match.start() - 320)
        end = min(len(markdown), match.end() + 320)
        images.append(
            ImageCandidate(
                url=url,
                alt=alt,
                start=match.start(),
                end=match.end(),
                heading=_current_heading(markdown, match.start()),
                context=_clean_text(markdown[start:end]),
            )
        )

    for match in HTML_IMAGE_RE.finditer(markdown or ""):
        attrs = _parse_html_attrs(match.group("attrs"))
        raw_url = (attrs.get("src") or attrs.get("data-src") or "").strip()
        alt = _clean_text(attrs.get("alt") or attrs.get("title") or "")
        if not raw_url or raw_url.startswith("#"):
            continue
        url = urljoin(base_url, raw_url) if base_url else raw_url
        if _is_bad_image(url, alt) or url in seen_urls:
            continue
        seen_urls.add(url)
        start = max(0, match.start() - 320)
        end = min(len(markdown), match.end() + 320)
        images.append(
            ImageCandidate(
                url=url,
                alt=alt,
                start=match.start(),
                end=match.end(),
                heading=_current_heading(markdown, match.start()),
                context=_clean_text(markdown[start:end]),
            )
        )

    images.sort(key=lambda image: image.start)
    return images


def _extract_video_candidates(markdown: str, base_url: str) -> List[VideoCandidate]:
    videos: List[VideoCandidate] = []
    seen_urls: set[str] = set()
    text = markdown or ""

    def add_candidate(raw_url: str, label: str, start: int, end: int) -> None:
        if not raw_url or raw_url.startswith("#"):
            return
        url = urljoin(base_url, raw_url) if base_url else raw_url
        context_start = max(0, start - 320)
        context_end = min(len(text), end + 320)
        context = _clean_text(text[context_start:context_end])
        heading = _current_heading(text, start)
        clean_label = _clean_text(label)
        if not _looks_like_video_url(url, clean_label, f"{heading} {context}") and not _contains_any(f"{clean_label} {heading} {context}", VIDEO_SECTION_HINTS):
            return
        if url in seen_urls:
            return
        seen_urls.add(url)
        videos.append(
            VideoCandidate(
                url=url,
                label=clean_label,
                start=start,
                end=end,
                heading=heading,
                context=context,
            )
        )

    for match in LINK_RE.finditer(text):
        add_candidate(match.group("url").strip(), match.group("label"), match.start(), match.end())

    for match in URL_RE.finditer(text):
        add_candidate(match.group(0).strip(), "", match.start(), match.end())

    for pattern in (HTML_VIDEO_RE, HTML_SOURCE_RE):
        for match in pattern.finditer(text):
            attrs = _parse_html_attrs(match.group("attrs"))
            raw_url = (attrs.get("src") or attrs.get("data-src") or "").strip()
            label = attrs.get("title") or attrs.get("aria-label") or "video"
            add_candidate(raw_url, label, match.start(), match.end())

    videos.sort(key=lambda item: item.start)
    return videos


def _video_anchor_match_score(video: VideoCandidate, prompt_text: str, heading: str) -> tuple[int, str]:
    path = PurePosixPath(urlparse(video.url).path)
    stem = re.sub(r"[-_]+", " ", path.stem)
    tokens = _slug_tokens(f"{stem} {video.label}")
    if not tokens:
        return 0, ""
    target_tokens = _slug_tokens(f"{heading} {prompt_text[:500]}")
    overlap = tokens & target_tokens
    if len(overlap) >= 2:
        return 10, f"视频文件名或标签与 Prompt/标题存在命名重合：{', '.join(sorted(overlap)[:4])}"
    if len(overlap) == 1 and heading:
        token = next(iter(overlap))
        return 6, f"视频文件名或标签与标题存在命名重合：{token}"
    return 0, ""


def _extract_gallery_prompt_effect_pairs(markdown: str, base_url: str, source_page_url: str, limit: int) -> List[PromptEffectCandidate]:
    pairs: List[PromptEffectCandidate] = []
    seen: set[tuple[str, str]] = set()
    entries = list(GALLERY_ENTRY_RE.finditer(markdown or ""))
    if not entries:
        return pairs

    for index, entry in enumerate(entries):
        block_start = entry.end()
        block_end = entries[index + 1].start() if index + 1 < len(entries) else len(markdown)
        block = markdown[block_start:block_end]
        prompt_heading = GALLERY_PROMPT_HEADING_RE.search(block)
        if not prompt_heading:
            continue

        prompt_body_start = prompt_heading.end()
        next_heading = HEADING_RE.search(block, prompt_body_start)
        prompt_body_end = next_heading.start() if next_heading else len(block)
        prompt = _clean_prompt_body(block[prompt_body_start:prompt_body_end])
        if not _is_probable_prompt(prompt, max_length=6000):
            continue

        image_search_start = prompt_body_end
        image_heading = GALLERY_IMAGE_HEADING_RE.search(block, prompt_body_end)
        if image_heading:
            image_search_start = image_heading.end()
        image_block = block[image_search_start:]
        images = _extract_image_candidates(image_block, base_url)
        if not images:
            continue

        title = _clean_text(entry.group("title"))
        for image in images:
            key = (prompt, image.url)
            if key in seen:
                continue
            seen.add(key)
            anchor_score, anchor_evidence = _anchor_match_score(image, prompt, title)
            pairs.append(
                PromptEffectCandidate(
                    prompt=prompt,
                    image_url=image.url,
                    relation_type="direct_pair",
                    evidence=f"编号案例块：{title or '未命名案例'}；Prompt 小节与生成图片小节直接配对；图片 alt/path：{image.alt or image.url}" + (f"；{anchor_evidence}" if anchor_evidence else ""),
                    confidence=min(98, 94 + anchor_score),
                    source_page_url=source_page_url,
                    source_heading=title,
                    line_start=_line_number(markdown, block_start + prompt_body_start),
                    line_end=_line_number(markdown, block_start + prompt_body_end),
                    structural_score=60,
                    distance_score=18,
                    filename_score=8 + anchor_score,
                    semantic_score=8,
                    penalty_score=0,
                )
            )
            break

        if len(pairs) >= limit:
            break

    return pairs


def _split_table_row(line: str) -> List[str]:
    stripped = line.strip()
    if not stripped.startswith("|") or not stripped.endswith("|"):
        return []
    return [_clean_text(cell) for cell in stripped.strip("|").split("|")]


def _is_table_separator(line: str) -> bool:
    cells = _split_table_row(line)
    return bool(cells) and all(re.fullmatch(r":?-{3,}:?", cell.replace(" ", "")) for cell in cells)


def _table_column_indices(headers: List[str], hints: tuple[str, ...]) -> List[int]:
    return [index for index, header in enumerate(headers) if _contains_any(header, hints)]


def _extract_table_prompt_effect_pairs(markdown: str, base_url: str, source_page_url: str, limit: int) -> List[PromptEffectCandidate]:
    pairs: List[PromptEffectCandidate] = []
    lines = (markdown or "").splitlines()
    offset = 0
    line_offsets: List[int] = []
    for line in lines:
        line_offsets.append(offset)
        offset += len(line) + 1

    index = 0
    while index < len(lines) - 2 and len(pairs) < limit:
        headers = _split_table_row(lines[index])
        if not headers or not _is_table_separator(lines[index + 1]):
            index += 1
            continue

        prompt_columns = _table_column_indices(headers, ("prompt", "提示词", "正向提示"))
        image_columns = _table_column_indices(headers, ("image", "images", "preview", "result", "output", "effect", "效果图", "生成图", "输出图"))
        if not prompt_columns or not image_columns:
            index += 1
            continue

        row_index = index + 2
        while row_index < len(lines):
            cells = _split_table_row(lines[row_index])
            if not cells or len(cells) < max(max(prompt_columns), max(image_columns)) + 1:
                break

            prompt = ""
            for prompt_column in prompt_columns:
                prompt = _clean_prompt_body(cells[prompt_column])
                if _is_probable_prompt(prompt, max_length=4000):
                    break
            if not _is_probable_prompt(prompt, max_length=4000):
                row_index += 1
                continue

            image_candidates: List[ImageCandidate] = []
            for image_column in image_columns:
                image_candidates.extend(_extract_image_candidates(cells[image_column], base_url))
            if not image_candidates:
                row_index += 1
                continue

            image = sorted(image_candidates, key=_image_pair_penalty)[0]
            title = _current_heading(markdown, line_offsets[index])
            anchor_score, anchor_evidence = _anchor_match_score(image, prompt, title)
            pairs.append(
                PromptEffectCandidate(
                    prompt=prompt,
                    image_url=image.url,
                    relation_type="direct_pair",
                    evidence=f"Markdown 表格配对：{title or '未命名表格'}；Prompt 列与图片/结果列位于同一行；图片 alt/path：{image.alt or image.url}" + (f"；{anchor_evidence}" if anchor_evidence else ""),
                    confidence=min(96, max(78, 90 + anchor_score - _image_pair_penalty(image))),
                    source_page_url=source_page_url,
                    source_heading=title,
                    line_start=row_index + 1,
                    line_end=row_index + 1,
                    structural_score=60,
                    distance_score=20,
                    filename_score=6 + anchor_score,
                    semantic_score=4,
                    penalty_score=_image_pair_penalty(image),
                )
            )
            row_index += 1

        index = max(row_index, index + 1)

    return pairs


def _block_structural_score(block: MarkdownContentBlock, prompt_count: int, image_count: int) -> int:
    base = {
        "case_section": 52,
        "heading_section": 44,
        "delimiter_block": 42,
        "list_item_block": 48,
        "root_block": 36,
    }.get(block.kind, 38)
    if prompt_count == 1 and image_count == 1:
        return min(58, base + 8)
    if prompt_count == image_count and prompt_count > 1:
        return min(52, base + 3)
    return base


def _block_kind_label(kind: str) -> str:
    return {
        "case_section": "Case/Example 标题块",
        "heading_section": "Markdown 标题块",
        "delimiter_block": "分隔符内容块",
        "list_item_block": "列表项内容块",
        "root_block": "根内容块",
    }.get(kind, kind)


def _score_block_pair(
    block: MarkdownContentBlock,
    prompt: PromptCandidate,
    image: ImageCandidate,
    prompt_count: int,
    image_count: int,
) -> tuple[int, str, int, int, int, int, int, str]:
    distance = min(abs(image.start - prompt.end), abs(prompt.start - image.end))
    distance_score = max(0, 20 - min(distance // 140, 20))
    structural_score = _block_structural_score(block, prompt_count, image_count)
    anchor_score, anchor_evidence = _anchor_match_score(image, prompt.text, block.title or prompt.heading)
    semantic_score = 6 if _contains_any(prompt.text, PROMPT_QUALITY_HINTS) else 2
    penalty = _image_pair_penalty(image)
    if prompt_count > 1 and image_count > 1 and prompt_count != image_count:
        penalty += 8
    if image_count > 3 and prompt_count == 1:
        penalty += 6
    score = structural_score + distance_score + anchor_score + semantic_score - penalty
    score = max(0, min(score, 98))
    relation = "direct_pair" if score >= 85 else "likely_pair" if score >= 65 else "unclear"
    complex_note = "；该块存在多个 Prompt 或多张图片，属于复杂内容块，低置信时需要 Qwen 8B 辅助判断。" if (prompt_count > 1 or image_count > 1) else ""
    evidence = (
        f"{_block_kind_label(block.kind)}：{block.title or prompt.heading or '未命名块'}；"
        f"块内 Prompt 数 {prompt_count}，图片数 {image_count}；"
        f"Prompt 与图片距离 {distance} 字符；图片 alt/path：{image.alt or image.url}"
        f"{'；' + anchor_evidence if anchor_evidence else ''}{complex_note}"
    )
    return score, relation, structural_score, distance_score, anchor_score, semantic_score, penalty, evidence


def _extract_block_prompt_effect_pairs(markdown: str, base_url: str, source_page_url: str, limit: int) -> List[PromptEffectCandidate]:
    pairs: List[PromptEffectCandidate] = []
    seen: set[tuple[str, str]] = set()
    blocks = split_markdown_content_blocks(markdown)

    for block in blocks:
        if len(pairs) >= limit:
            break
        prompts = _extract_prompt_candidates_with_positions(block.text, limit=200)
        images = _extract_image_candidates(block.text, base_url)
        if not prompts or not images:
            continue

        local_pairs: List[tuple[PromptCandidate, ImageCandidate]] = []
        if len(prompts) == len(images) and len(prompts) > 1:
            local_pairs = list(zip(prompts, images))
        else:
            used_local_images: set[str] = set()
            for prompt in prompts:
                ranked: List[tuple[int, ImageCandidate]] = []
                for image in images:
                    if image.url in used_local_images:
                        continue
                    distance = min(abs(image.start - prompt.end), abs(prompt.start - image.end))
                    anchor_score, _ = _anchor_match_score(image, prompt.text, block.title or prompt.heading)
                    ranked.append((distance - anchor_score * 180 + _image_pair_penalty(image) * 80, image))
                if not ranked:
                    continue
                image = sorted(ranked, key=lambda item: item[0])[0][1]
                used_local_images.add(image.url)
                local_pairs.append((prompt, image))

        for prompt, image in local_pairs:
            key = (prompt.text, image.url)
            if key in seen:
                continue
            score, relation, structural_score, distance_score, filename_score, semantic_score, penalty_score, evidence = _score_block_pair(
                block,
                prompt,
                image,
                len(prompts),
                len(images),
            )
            if score < 65:
                continue
            seen.add(key)
            pairs.append(
                PromptEffectCandidate(
                    prompt=prompt.text,
                    image_url=image.url,
                    relation_type=relation,
                    evidence=evidence,
                    confidence=score,
                    source_page_url=source_page_url,
                    source_heading=block.title or prompt.heading,
                    line_start=block.line_start + _line_number(block.text, prompt.start) - 1,
                    line_end=block.line_start + _line_number(block.text, prompt.end) - 1,
                    structural_score=structural_score,
                    distance_score=distance_score,
                    filename_score=filename_score,
                    semantic_score=semantic_score,
                    penalty_score=penalty_score,
                )
            )
            if len(pairs) >= limit:
                break

    return pairs


def extract_prompt_effect_pairs(markdown: str, base_url: str, source_page_url: str, limit: int = 10) -> List[PromptEffectCandidate]:
    gallery_pairs = _extract_gallery_prompt_effect_pairs(markdown, base_url, source_page_url, limit)
    if len(gallery_pairs) >= limit:
        return gallery_pairs[:limit]

    table_pairs = _extract_table_prompt_effect_pairs(markdown, base_url, source_page_url, limit - len(gallery_pairs))

    prompt_scan_limit = max(40, min(limit * 2, 10_000))
    prompts = _extract_prompt_candidates_with_positions(markdown, limit=prompt_scan_limit)
    images = _extract_image_candidates(markdown, base_url)
    pairs: List[PromptEffectCandidate] = list(gallery_pairs)
    used_pair_keys: set[tuple[str, str]] = {(pair.prompt, pair.image_url) for pair in gallery_pairs}
    for table_pair in table_pairs:
        key = (table_pair.prompt, table_pair.image_url)
        if key in used_pair_keys:
            continue
        used_pair_keys.add(key)
        pairs.append(table_pair)
        if len(pairs) >= limit:
            return pairs[:limit]

    block_pairs = _extract_block_prompt_effect_pairs(markdown, base_url, source_page_url, limit - len(pairs))
    for block_pair in block_pairs:
        key = (block_pair.prompt, block_pair.image_url)
        if key in used_pair_keys:
            continue
        used_pair_keys.add(key)
        pairs.append(block_pair)
        if len(pairs) >= limit:
            return pairs[:limit]

    used_images: set[str] = {pair.image_url for pair in pairs}
    used_prompts: set[str] = {pair.prompt for pair in pairs}

    for prompt in prompts:
        section_start, section_end = _section_bounds(markdown, prompt.start)
        section_text = markdown[section_start:section_end]
        section_has_pair_hint = _contains_any(f"{prompt.heading} {section_text[:600]}", PAIR_SECTION_HINTS)
        best: tuple[int, str, str, ImageCandidate, int, int, int, int, int] | None = None

        for image in images:
            if image.url in used_images:
                continue
            if not (section_start <= image.start <= section_end):
                continue
            distance = min(abs(image.start - prompt.end), abs(prompt.start - image.end))
            if distance > 2200:
                continue

            image_has_pair_hint = _contains_any(f"{image.alt} {image.url} {image.context}", IMAGE_PAIR_HINTS)
            score = 0
            relation = "unclear"
            if section_has_pair_hint and image_has_pair_hint and distance <= 1400:
                score = 86
                relation = "direct_pair"
                structural_score = 52
            elif section_has_pair_hint and distance <= 700:
                score = 74
                relation = "likely_pair"
                structural_score = 42
            elif image_has_pair_hint and distance <= 500:
                score = 70
                relation = "likely_pair"
                structural_score = 35
            else:
                structural_score = 0

            if score < 70:
                continue

            penalty = _image_pair_penalty(image)
            anchor_score, anchor_evidence = _anchor_match_score(image, prompt.text, prompt.heading)
            if anchor_score:
                score += anchor_score
            score -= penalty
            if score < 70:
                continue

            evidence = f"同一小节：{prompt.heading or '未命名小节'}；Prompt 与图片距离 {distance} 字符；图片 alt/path：{image.alt or image.url}"
            if anchor_evidence:
                evidence = f"{evidence}；{anchor_evidence}"
            distance_score = max(0, 20 - min(distance // 120, 20))
            semantic_score = 6 if _contains_any(prompt.text, PROMPT_QUALITY_HINTS) else 2
            candidate = (score, relation, evidence, image, anchor_score, structural_score, distance_score, semantic_score, penalty)
            if best is None or candidate[0] > best[0]:
                best = candidate

        if best and prompt.text not in used_prompts:
            score, relation, evidence, image, anchor_score, structural_score, distance_score, semantic_score, penalty = best
            if (prompt.text, image.url) in used_pair_keys:
                continue
            used_images.add(image.url)
            used_prompts.add(prompt.text)
            used_pair_keys.add((prompt.text, image.url))
            pairs.append(
                PromptEffectCandidate(
                    prompt=prompt.text,
                    image_url=image.url,
                    relation_type=relation,
                    evidence=evidence,
                    confidence=score,
                    source_page_url=source_page_url,
                    source_heading=prompt.heading,
                    line_start=_line_number(markdown, prompt.start),
                    line_end=_line_number(markdown, prompt.end),
                    structural_score=structural_score,
                    distance_score=distance_score,
                    filename_score=max(anchor_score, 4 if image.alt and prompt.heading and image.alt.lower() in prompt.heading.lower() else 0),
                    semantic_score=semantic_score,
                    penalty_score=penalty,
                )
            )
        if len(pairs) >= limit:
            break
    return pairs


def _extract_table_prompt_video_pairs(markdown: str, base_url: str, source_page_url: str, limit: int) -> List[PromptEffectCandidate]:
    pairs: List[PromptEffectCandidate] = []
    lines = (markdown or "").splitlines()
    offset = 0
    line_offsets: List[int] = []
    for line in lines:
        line_offsets.append(offset)
        offset += len(line) + 1

    index = 0
    while index < len(lines) - 2 and len(pairs) < limit:
        headers = _split_table_row(lines[index])
        if not headers or not _is_table_separator(lines[index + 1]):
            index += 1
            continue

        prompt_columns = _table_column_indices(headers, ("prompt", "提示词", "video prompt"))
        video_columns = _table_column_indices(headers, ("video", "result", "output", "clip", "demo", "preview"))
        if not prompt_columns or not video_columns:
            index += 1
            continue

        row_index = index + 2
        while row_index < len(lines):
            cells = _split_table_row(lines[row_index])
            if not cells or len(cells) < max(max(prompt_columns), max(video_columns)) + 1:
                break

            prompt = ""
            for prompt_column in prompt_columns:
                prompt = _clean_prompt_body(cells[prompt_column])
                if _is_probable_prompt(prompt, max_length=6000):
                    break
            if not _is_probable_prompt(prompt, max_length=6000):
                row_index += 1
                continue

            video_candidates: List[VideoCandidate] = []
            for video_column in video_columns:
                video_candidates.extend(_extract_video_candidates(cells[video_column], base_url))
            if not video_candidates:
                row_index += 1
                continue

            video = video_candidates[0]
            title = _current_heading(markdown, line_offsets[index])
            anchor_score, anchor_evidence = _video_anchor_match_score(video, prompt, title)
            pairs.append(
                PromptEffectCandidate(
                    prompt=prompt,
                    image_url=video.url,
                    relation_type="direct_pair",
                    evidence=f"Markdown 表格配对：{title or '未命名表格'}，Prompt 列与视频/结果列位于同一行；视频链接/文件名：{video.label or video.url}" + (f"；{anchor_evidence}" if anchor_evidence else ""),
                    confidence=min(96, max(82, 90 + anchor_score)),
                    source_page_url=source_page_url,
                    source_heading=title,
                    line_start=row_index + 1,
                    line_end=row_index + 1,
                    structural_score=60,
                    distance_score=20,
                    filename_score=6 + anchor_score,
                    semantic_score=6,
                    penalty_score=0,
                )
            )
            row_index += 1

        index = max(row_index, index + 1)

    return pairs


def _extract_block_prompt_video_pairs(markdown: str, base_url: str, source_page_url: str, limit: int) -> List[PromptEffectCandidate]:
    pairs: List[PromptEffectCandidate] = []
    seen: set[tuple[str, str]] = set()
    blocks = split_markdown_content_blocks(markdown, media_mode="video")

    for block in blocks:
        if len(pairs) >= limit:
            break
        prompts = _extract_prompt_candidates_with_positions(block.text, limit=200)
        videos = _extract_video_candidates(block.text, base_url)
        if not prompts or not videos:
            continue

        local_pairs: List[tuple[PromptCandidate, VideoCandidate]] = []
        if len(prompts) == len(videos) and len(prompts) > 1:
            local_pairs = list(zip(prompts, videos))
        else:
            used_video_urls: set[str] = set()
            for prompt in prompts:
                ranked: List[tuple[int, VideoCandidate, int]] = []
                for video in videos:
                    if video.url in used_video_urls:
                        continue
                    distance = min(abs(video.start - prompt.end), abs(prompt.start - video.end))
                    anchor_score, _ = _video_anchor_match_score(video, prompt.text, block.title or prompt.heading)
                    ranked.append((distance - anchor_score * 180, video, anchor_score))
                if not ranked:
                    continue
                _, video, _ = sorted(ranked, key=lambda item: item[0])[0]
                used_video_urls.add(video.url)
                local_pairs.append((prompt, video))

        for prompt, video in local_pairs:
            key = (prompt.text, video.url)
            if key in seen:
                continue
            prompt_count = len(prompts)
            video_count = len(videos)
            distance = min(abs(video.start - prompt.end), abs(prompt.start - video.end))
            distance_score = max(0, 20 - min(distance // 140, 20))
            structural_score = _block_structural_score(block, prompt_count, video_count)
            anchor_score, anchor_evidence = _video_anchor_match_score(video, prompt.text, block.title or prompt.heading)
            semantic_score = 8 if _contains_any(prompt.text, PROMPT_QUALITY_HINTS) else 4
            penalty_score = 8 if prompt_count > 1 and video_count > 1 and prompt_count != video_count else 0
            score = max(0, min(98, structural_score + distance_score + anchor_score + semantic_score - penalty_score))
            if score < 65:
                continue
            relation = "direct_pair" if score >= 85 else "likely_pair"
            evidence = (
                f"{_block_kind_label(block.kind)}：{block.title or prompt.heading or '未命名块'}；"
                f"块内 Prompt 数 {prompt_count}，视频数 {video_count}；"
                f"Prompt 与视频距离 {distance} 字符；视频链接/文件名：{video.label or video.url}"
                + (f"；{anchor_evidence}" if anchor_evidence else "")
            )
            seen.add(key)
            pairs.append(
                PromptEffectCandidate(
                    prompt=prompt.text,
                    image_url=video.url,
                    relation_type=relation,
                    evidence=evidence,
                    confidence=score,
                    source_page_url=source_page_url,
                    source_heading=block.title or prompt.heading,
                    line_start=block.line_start + _line_number(block.text, prompt.start) - 1,
                    line_end=block.line_start + _line_number(block.text, prompt.end) - 1,
                    structural_score=structural_score,
                    distance_score=distance_score,
                    filename_score=anchor_score,
                    semantic_score=semantic_score,
                    penalty_score=penalty_score,
                )
            )
            if len(pairs) >= limit:
                break

    return pairs


def extract_prompt_video_pairs(markdown: str, base_url: str, source_page_url: str, limit: int = 10) -> List[PromptEffectCandidate]:
    table_pairs = _extract_table_prompt_video_pairs(markdown, base_url, source_page_url, limit)
    if len(table_pairs) >= limit:
        return table_pairs[:limit]

    pairs: List[PromptEffectCandidate] = list(table_pairs)
    used_pair_keys: set[tuple[str, str]] = {(pair.prompt, pair.image_url) for pair in table_pairs}

    block_pairs = _extract_block_prompt_video_pairs(markdown, base_url, source_page_url, limit - len(pairs))
    for block_pair in block_pairs:
        key = (block_pair.prompt, block_pair.image_url)
        if key in used_pair_keys:
            continue
        used_pair_keys.add(key)
        pairs.append(block_pair)
        if len(pairs) >= limit:
            return pairs[:limit]

    prompts = _extract_prompt_candidates_with_positions(markdown, limit=max(40, min(limit * 3, 10_000)))
    videos = _extract_video_candidates(markdown, base_url)
    used_videos: set[str] = {pair.image_url for pair in pairs}

    for prompt in prompts:
        section_start, section_end = _section_bounds(markdown, prompt.start)
        section_text = markdown[section_start:section_end]
        if not _contains_any(f"{prompt.heading} {section_text[:1200]}", VIDEO_SECTION_HINTS):
            continue
        best: tuple[int, VideoCandidate, str, int, int, int] | None = None
        for video in videos:
            if video.url in used_videos:
                continue
            if not (section_start <= video.start <= section_end):
                continue
            distance = min(abs(video.start - prompt.end), abs(prompt.start - video.end))
            if distance > 2600:
                continue
            anchor_score, anchor_evidence = _video_anchor_match_score(video, prompt.text, prompt.heading)
            distance_score = max(0, 20 - min(distance // 120, 20))
            structural_score = 46
            semantic_score = 8 if _contains_any(prompt.text, PROMPT_QUALITY_HINTS) else 4
            score = max(0, min(96, structural_score + distance_score + anchor_score + semantic_score))
            if score < 70:
                continue
            evidence = f"同一视频小节：{prompt.heading or '未命名小节'}；Prompt 与视频距离 {distance} 字符；视频链接/文件名：{video.label or video.url}"
            if anchor_evidence:
                evidence = f"{evidence}；{anchor_evidence}"
            candidate = (score, video, evidence, structural_score, distance_score, semantic_score)
            if best is None or candidate[0] > best[0]:
                best = candidate

        if not best:
            continue
        score, video, evidence, structural_score, distance_score, semantic_score = best
        used_videos.add(video.url)
        pairs.append(
            PromptEffectCandidate(
                prompt=prompt.text,
                image_url=video.url,
                relation_type="direct_pair" if score >= 85 else "likely_pair",
                evidence=evidence,
                confidence=score,
                source_page_url=source_page_url,
                source_heading=prompt.heading,
                line_start=_line_number(markdown, prompt.start),
                line_end=_line_number(markdown, prompt.end),
                structural_score=structural_score,
                distance_score=distance_score,
                filename_score=0,
                semantic_score=semantic_score,
                penalty_score=0,
            )
        )
        if len(pairs) >= limit:
            break

    return pairs


def build_cn_explanation(prompt: str, category: str) -> str:
    # 中文解释必须来自翻译标注，扫描阶段不生成泛化占位说明。
    return ""


def infer_scenario(category: str, text: str) -> str:
    lower = text.lower()
    if any(x in lower for x in ("landing", "homepage", "hero section")):
        return "landing_page"
    if "dashboard" in lower:
        return "dashboard"
    if any(x in lower for x in ("saas", "app ui", "mobile app")):
        return "saas_ui"
    if any(x in lower for x in ("product photo", "product image", "packshot")):
        return "product_image"
    if "poster" in lower:
        return "poster"
    editing_hints = (
        "image editing",
        "photo editing",
        "retouch",
        "remove object",
        "object removal",
        "remove background",
        "background replacement",
        "replace background",
        "change background",
        "style transfer",
        "inpaint",
        "outpaint",
    )
    if category == "image_editing_prompt" or any(x in lower for x in editing_hints):
        return "image_editing"
    if any(x in lower for x in ("cinematic", "film", "shot")):
        return "cinematic_video" if category == "video_generation_prompt" else "commercial_visual"
    if "storyboard" in lower:
        return "storyboard"
    if category == "web_ui_prompt":
        return "app_ui"
    if category == "video_generation_prompt":
        return "short_video"
    return "other"


def default_effect_review(has_image: bool, relation: str = "unclear", category: str = "") -> str:
    media_cn = "????" if category == "video_generation_prompt" else "???"
    if not has_image:
        return f"??????{media_cn}??????? Prompt ???????????"
    if relation == "direct_pair":
        return f"{media_cn}? Prompt ??????????????????????????????????/???????????"
    if relation == "likely_pair":
        return f"{media_cn}? Prompt ?????????????????????????????????????????"
    return f"{media_cn}? Prompt ???????????????? Prompt ??????"
