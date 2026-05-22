from __future__ import annotations

import csv
import io
import json
import re
from dataclasses import dataclass, replace
from pathlib import PurePosixPath
from typing import Any, Callable, Dict, Iterable, List, Optional, Sequence, Tuple
from urllib.parse import urljoin, urlparse

from database import utc_now
from services.dedup_service import content_hash
from utils.image_utils import download_image


HEADING_RE = re.compile(r"(?m)^(?P<marks>#{1,6})\s+(?P<title>.+?)\s*$")
FENCED_RE = re.compile(r"```(?P<lang>[a-zA-Z0-9_-]*)\s*\n(?P<body>.*?)```", re.IGNORECASE | re.DOTALL)
IMAGE_RE = re.compile(r"!\[(?P<alt>[^\]]*)\]\((?P<url>[^)\s]+)(?:\s+\"[^\"]*\")?\)", re.IGNORECASE)
HTML_IMAGE_RE = re.compile(r"<img\b(?P<attrs>[^>]*)>", re.IGNORECASE | re.DOTALL)
HTML_ATTR_RE = re.compile(
    r"""(?P<name>[a-zA-Z_:][-a-zA-Z0-9_:.]*)\s*=\s*(?:"(?P<double>[^"]*)"|'(?P<single>[^']*)'|(?P<bare>[^\s>]+))""",
    re.IGNORECASE,
)
TABLE_SEPARATOR_RE = re.compile(r"^\s*\|?\s*:?-{3,}:?\s*(?:\|\s*:?-{3,}:?\s*)+\|?\s*$")
LIST_ITEM_RE = re.compile(r"(?m)^(?P<indent>\s*)(?:[-*+]|\d+[.)])\s+")
DELIMITER_RE = re.compile(r"(?m)^\s*(?:-{3,}|\*{3,}|_{3,})\s*$")

PROMPT_LABEL_RE = re.compile(
    r"(?is)(?:^|\n)\s*(?:[-*]\s*)?(?:\*\*)?"
    r"(?:web\s*ui\s*prompt|ui\s*prompt|component\s*prompt|page\s*prompt|design\s*prompt|prompt|提示词|生成提示词)"
    r"(?:\*\*)?\s*[:：]\s*(?P<prompt>.{24,4000}?)(?=\n\s*\n|#{1,6}\s|!\[|<img\b|```|\n\s*(?:[-*]\s*)?(?:preview|screenshot|result|output|demo|example|说明|截图)\s*[:：]|$)"
)

WEB_UI_HINTS = (
    "web ui",
    "frontend",
    "website",
    "landing",
    "dashboard",
    "component",
    "interface",
    "layout",
    "responsive",
    "design system",
    "shadcn",
    "tailwind",
    "react",
    "next.js",
    "vue",
    "css",
    "html",
    "页面",
    "网页",
    "前端",
    "界面",
    "组件",
    "布局",
    "响应式",
    "设计系统",
)
ACTION_HINTS = ("create", "build", "design", "generate", "make", "craft", "implement", "生成", "创建", "设计", "构建")
DESIGN_RULE_HINTS = ("design rule", "guideline", "principle", "design system", "style guide", "规范", "设计规范", "设计系统", "原则")
LAYOUT_HINTS = ("layout", "grid", "spacing", "responsive", "breakpoint", "布局", "栅格", "间距", "响应式")
INTERACTION_HINTS = ("interaction", "hover", "state", "transition", "animation", "motion", "交互", "悬停", "状态", "动效")
SCREENSHOT_HINTS = ("screenshot", "preview", "demo", "result", "output", "example", "screen", "截图", "预览", "效果", "演示")
BAD_IMAGE_HINTS = ("badge", "logo", "icon", "avatar", "sponsor", "shields", "license", "build", "version", "workflow", "actions")
ASSET_PATH_HINTS = ("prompts/", "components/", "design-system/", "patterns/", "templates/", "examples/", "ui-design/")
EXCLUDED_SOURCE_FILES = {
    "contributing.md",
    "roadmap.md",
    "projectstructure.md",
    "performance_improvements.md",
    "changelog.md",
    "release-notes.md",
}
EXCLUDED_PATH_HINTS = ("/.github/", "/tests/", "/scripts/", "/workflows/")
STRONG_WEB_UI_ASSET_HINTS = (
    "component prompt",
    "page prompt",
    "design prompt",
    "landing page",
    "hero section",
    "navbar",
    "sidebar",
    "pricing card",
    "feature card",
    "dashboard page",
    "data table ui",
    "form ui",
    "settings panel",
    "app shell",
    "design system",
    "design tokens",
    "style guide",
    "visual hierarchy",
    "responsive grid",
    "cta",
    "tailwind classes",
    "shadcn",
)
COMPONENT_LIBRARY_HINTS = (
    "component library",
    "ui component library",
    "ui components",
    "component collection",
    "registry",
    "shadcn registry",
    "design system library",
    "blocks library",
    "customizable components",
    "high-quality components",
    "components for ai applications",
)
COMPONENT_LIBRARY_PATH_HINTS = (
    "components/",
    "registry/",
    "blocks/",
    "src/components/",
    "app/components/",
)
DESIGN_ASSET_HEADING_HINTS = (
    "component spec",
    "component prompt",
    "page prompt",
    "design rule",
    "design guideline",
    "layout guideline",
    "interaction pattern",
    "design system",
    "ui prompt",
)
TECHNICAL_DOC_HINTS = (
    "comfyui",
    "sampler",
    "checkpoint",
    "clip",
    "vae",
    "lora",
    "latent",
    "promptserver",
    "pytest",
    "pr checklist",
    "js syntax",
    "server process",
    "api endpoint",
    "migration check",
    "onconfigure",
    "onnodecreated",
    "widget",
    "state_to_configs_json",
    "conf-builder",
    "dashboard_html",
    "generation_orchestrator",
    "distribution manager",
    "worker thread",
    "cache-busting",
    "restart comfyui",
    "ctrl+f5",
)
TOOLING_UI_HINTS = (
    "visual ui",
    "builder ui",
    "dashboard viewer",
    "add node",
    "canvas",
    "workflow",
    "iframe",
    "browser tab",
    "json output",
    "session_name",
)

COMPONENT_HINTS: Sequence[Tuple[str, Tuple[str, ...]]] = (
    ("hero", ("hero", "首屏", "头图")),
    ("navbar", ("navbar", "navigation", "nav bar", "导航")),
    ("sidebar", ("sidebar", "side nav", "侧边栏")),
    ("pricing", ("pricing", "price", "plans", "定价", "价格")),
    ("card", ("card", "cards", "卡片")),
    ("form", ("form", "input", "表单")),
    ("modal", ("modal", "dialog", "drawer", "弹窗", "抽屉")),
    ("table", ("table", "data table", "表格")),
    ("dashboard", ("dashboard", "analytics", "仪表盘", "数据看板")),
    ("chart", ("chart", "graph", "图表")),
    ("settings", ("settings", "preference", "设置")),
    ("app_shell", ("app shell", "shell layout", "应用框架")),
    ("auth", ("login", "sign in", "auth", "登录", "注册")),
)
PAGE_HINTS: Sequence[Tuple[str, Tuple[str, ...]]] = (
    ("landing_page", ("landing", "homepage", "marketing page", "落地页", "首页")),
    ("dashboard", ("dashboard", "analytics", "数据看板", "仪表盘")),
    ("app_ui", ("app ui", "application", "应用界面")),
    ("saas_ui", ("saas", "b2b", "workspace")),
    ("auth", ("login", "sign in", "sign up", "登录", "注册")),
    ("ecommerce", ("ecommerce", "commerce", "shop", "store", "电商", "商品")),
    ("portfolio", ("portfolio", "作品集")),
    ("admin_panel", ("admin", "cms", "后台", "管理面板")),
)
FRAMEWORK_HINTS: Sequence[Tuple[str, Tuple[str, ...]]] = (
    ("React", ("react", "jsx", "tsx")),
    ("Next.js", ("next.js", "nextjs", "app router")),
    ("Tailwind CSS", ("tailwind", "tailwindcss")),
    ("shadcn/ui", ("shadcn", "radix")),
    ("Framer Motion", ("framer motion", "motion")),
    ("Vue", ("vue", "nuxt")),
    ("Svelte", ("svelte", "sveltekit")),
)


@dataclass(frozen=True)
class WebUiAssetCandidate:
    source_page_url: str
    source_file: str
    source_heading: str
    line_start: int
    line_end: int
    asset_group: str
    asset_type: str
    library_kind: str
    component_type: str
    page_type: str
    framework: str
    prompt_text: str
    design_rules: str
    ui_pattern: str
    screenshot_original_url: str
    tags: List[str]
    evidence: str
    confidence: int
    content_hash: str


@dataclass(frozen=True)
class _Block:
    kind: str
    title: str
    text: str
    start: int
    end: int
    line_start: int
    line_end: int


def _clean_text(text: str) -> str:
    return " ".join((text or "").strip().split())


def _line_number(text: str, pos: int) -> int:
    return (text or "")[: max(0, pos)].count("\n") + 1


def _contains_any(text: str, hints: Iterable[str]) -> bool:
    lower = (text or "").lower()
    return any(hint.lower() in lower for hint in hints)


def _count_hints(text: str, hints: Iterable[str]) -> int:
    lower = (text or "").lower()
    return sum(1 for hint in hints if hint.lower() in lower)


def _is_bad_image(url: str, alt: str = "") -> bool:
    probe = f"{url} {alt}".lower()
    return any(hint in probe for hint in BAD_IMAGE_HINTS)


def _normalized_path(path: str) -> str:
    return (path or "").replace("\\", "/").strip().lower()


def _path_is_excluded(path: str) -> bool:
    clean = _normalized_path(path)
    if not clean:
        return False
    if PurePosixPath(clean).name in EXCLUDED_SOURCE_FILES:
        return True
    return any(hint in clean for hint in EXCLUDED_PATH_HINTS)


def _path_has_asset_context(path: str) -> bool:
    clean = _normalized_path(path)
    if not clean:
        return False
    return any(hint in clean for hint in ASSET_PATH_HINTS)


def _has_strong_web_ui_asset_signal(text: str) -> bool:
    probe = text or ""
    return bool(
        _contains_any(probe, STRONG_WEB_UI_ASSET_HINTS)
        or _infer_from_hints(probe, COMPONENT_HINTS)
        or _infer_from_hints(probe, PAGE_HINTS)
    )


def _looks_like_technical_ui_doc(text: str, source_file: str = "") -> bool:
    probe = f"{source_file} {text}"
    technical_hits = _count_hints(probe, TECHNICAL_DOC_HINTS)
    tooling_hits = _count_hints(probe, TOOLING_UI_HINTS)
    strong_hits = _count_hints(probe, STRONG_WEB_UI_ASSET_HINTS)
    component_or_page = bool(_infer_from_hints(probe, COMPONENT_HINTS) or _infer_from_hints(probe, PAGE_HINTS))

    if _path_is_excluded(source_file):
        return True
    if tooling_hits >= 2 and strong_hits == 0 and not component_or_page:
        return True
    if technical_hits >= 3 and strong_hits == 0 and not component_or_page:
        return True
    if technical_hits >= 4 and strong_hits <= 1 and not _path_has_asset_context(source_file):
        return True
    return False


def _looks_like_reference_only(text: str) -> bool:
    clean = _clean_text(text)
    if not clean:
        return True
    if re.fullmatch(r"\[[^\]]+\]\([^)]+\)", clean):
        return True
    if re.fullmatch(r"(?:\./|\.\./|/)?[\w./-]+\.(?:md|mdx|txt|prompt|json|jsonl|csv|ya?ml|png|jpg|jpeg|webp)", clean, re.IGNORECASE):
        return True
    if re.fullmatch(r"https?://\S+", clean, re.IGNORECASE):
        return True
    return False


def _parse_html_attrs(attrs: str) -> Dict[str, str]:
    parsed: Dict[str, str] = {}
    for match in HTML_ATTR_RE.finditer(attrs or ""):
        parsed[match.group("name").lower()] = (match.group("double") or match.group("single") or match.group("bare") or "").strip()
    return parsed


def _extract_images(markdown: str, base_url: str) -> List[Tuple[str, str, int]]:
    images: List[Tuple[str, str, int]] = []
    seen: set[str] = set()
    for match in IMAGE_RE.finditer(markdown or ""):
        raw = match.group("url").strip()
        alt = _clean_text(match.group("alt"))
        url = urljoin(base_url, raw) if base_url else raw
        if raw.startswith("#") or _is_bad_image(url, alt) or url in seen:
            continue
        seen.add(url)
        images.append((url, alt, match.start()))
    for match in HTML_IMAGE_RE.finditer(markdown or ""):
        attrs = _parse_html_attrs(match.group("attrs"))
        raw = (attrs.get("src") or attrs.get("data-src") or "").strip()
        alt = _clean_text(attrs.get("alt") or attrs.get("title") or "")
        url = urljoin(base_url, raw) if base_url else raw
        if not raw or raw.startswith("#") or _is_bad_image(url, alt) or url in seen:
            continue
        seen.add(url)
        images.append((url, alt, match.start()))
    return sorted(images, key=lambda item: item[2])


def _choose_screenshot(block_text: str, base_url: str) -> str:
    images = _extract_images(block_text, base_url)
    if not images:
        return ""
    ranked: List[Tuple[int, str]] = []
    for url, alt, pos in images:
        context = block_text[max(0, pos - 160): pos + 160]
        score = 10 if _contains_any(f"{url} {alt} {context}", SCREENSHOT_HINTS) else 0
        if _contains_any(f"{url} {alt}", COMPONENT_HINTS[0][1]):
            score += 2
        ranked.append((score, url))
    ranked.sort(key=lambda item: item[0], reverse=True)
    return ranked[0][1] if ranked[0][0] > 0 or len(images) == 1 else ""


def _split_table_row(line: str) -> List[str]:
    stripped = (line or "").strip()
    if not stripped.startswith("|") or not stripped.endswith("|"):
        return []
    return [_clean_text(cell) for cell in stripped.strip("|").split("|")]


def _column_indices(headers: Sequence[str], hints: Iterable[str]) -> List[int]:
    return [index for index, header in enumerate(headers) if _contains_any(header, hints)]


def _infer_from_hints(text: str, hints: Sequence[Tuple[str, Tuple[str, ...]]]) -> str:
    for value, tokens in hints:
        if _contains_any(text, tokens):
            return value
    return ""


def _infer_framework(text: str) -> str:
    found = [name for name, hints in FRAMEWORK_HINTS if _contains_any(text, hints)]
    return " + ".join(found[:3])


def _infer_library_kind(text: str) -> str:
    lower = (text or "").lower()
    if "shadcn" in lower or "components.json" in lower or "registry" in lower:
        return "shadcn_registry"
    if "design system" in lower:
        return "design_system_library"
    if "blocks" in lower:
        return "blocks_library"
    return "component_collection"


def _infer_asset_type(text: str, component_type: str, page_type: str) -> str:
    lower = (text or "").lower()
    if "prompt" in lower or "提示词" in lower:
        return "component_prompt" if component_type else "page_prompt" if page_type else "component_prompt"
    if _contains_any(text, INTERACTION_HINTS):
        return "interaction_pattern"
    if _contains_any(text, LAYOUT_HINTS):
        return "layout_pattern"
    if _contains_any(text, DESIGN_RULE_HINTS):
        return "design_rule"
    return "component_prompt" if component_type else "page_prompt" if page_type else "design_rule"


def _infer_asset_group(asset_type: str) -> str:
    return "component_library" if asset_type == "component_library" else "design_spec"


def _tags(
    component_type: str,
    page_type: str,
    framework: str,
    asset_type: str,
    asset_group: str,
    library_kind: str,
) -> List[str]:
    values = [asset_group, asset_type, library_kind, component_type, page_type, *[item.strip() for item in framework.split("+")]]
    clean: List[str] = []
    for value in values:
        if value and value not in clean:
            clean.append(value)
    return clean[:6]


def _readme_overview(readme: str) -> str:
    text = re.sub(r"```.*?```", " ", readme or "", flags=re.DOTALL)
    text = re.sub(r"!\[[^\]]*\]\([^)]+\)", " ", text)
    paragraphs = [re.sub(r"\s+", " ", part).strip() for part in re.split(r"\n\s*\n", text)]
    for paragraph in paragraphs:
        clean = paragraph.strip("#>-* ").strip()
        lower = clean.lower()
        if len(clean) < 48 or len(clean) > 420:
            continue
        if lower.startswith(("npm ", "npx ", "pnpm ", "yarn ", "import ", "export ")):
            continue
        if _contains_any(lower, ("installation", "usage", "getting started", "quickstart")):
            continue
        return clean
    return ""


def _looks_like_component_library_repo(repo_name: str, readme: str, documents: Sequence[Dict[str, str]]) -> bool:
    path_probe = " ".join((doc.get("path") or "").lower() for doc in documents)
    text_probe = f"{repo_name}\n{readme[:8000]}\n{path_probe}"
    if _contains_any(text_probe, TECHNICAL_DOC_HINTS):
        return False
    score = 0
    if _contains_any(text_probe, COMPONENT_LIBRARY_HINTS):
        score += 2
    if _contains_any(text_probe, ("shadcn", "radix", "react", "next.js", "tailwind")):
        score += 1
    if "components.json" in path_probe:
        score += 1
    if any(hint in path_probe for hint in COMPONENT_LIBRARY_PATH_HINTS):
        score += 1
    if _contains_any(text_probe, ("install", "installation", "usage", "import")) and _contains_any(text_probe, ("component", "registry", "library")):
        score += 1
    return score >= 4


def _build_component_library_candidate(
    *,
    repo_name: str,
    repo_url: str,
    readme: str,
    documents: Sequence[Dict[str, str]],
) -> Optional[WebUiAssetCandidate]:
    overview = _readme_overview(readme)
    if not overview:
        overview = f"{repo_name} 是一个面向网站前端的组件库仓库，适合沉淀为本地组件资产参考。"
    probe = f"{repo_name}\n{readme[:8000]}"
    framework = _infer_framework(probe)
    library_kind = _infer_library_kind(probe)
    screenshot = ""
    source_page_url = repo_url
    source_file = "README.md"
    base_url = ""
    for document in documents:
        path = (document.get("path") or "").lower()
        if path == "readme.md":
            source_page_url = document.get("source_page_url") or repo_url
            base_url = document.get("raw_base_url") or ""
            screenshot = _choose_screenshot(document.get("content") or "", base_url)
            break
    if not screenshot and documents:
        first = documents[0]
        screenshot = _choose_screenshot(first.get("content") or "", first.get("raw_base_url") or "")
    content = overview
    component_type = _infer_from_hints(probe, COMPONENT_HINTS)
    page_type = _infer_from_hints(probe, PAGE_HINTS)
    return WebUiAssetCandidate(
        source_page_url=source_page_url,
        source_file=source_file,
        source_heading=repo_name,
        line_start=1,
        line_end=1,
        asset_group="component_library",
        asset_type="component_library",
        library_kind=library_kind,
        component_type=component_type,
        page_type=page_type,
        framework=framework,
        prompt_text=content,
        design_rules="",
        ui_pattern=library_kind,
        screenshot_original_url=screenshot,
        tags=_tags(component_type, page_type, framework, "component_library", "component_library", library_kind),
        evidence="仓库级识别：README、目录结构和技术栈共同表明这是前端组件库，而不是单条 Prompt 或零散规范片段。",
        confidence=90,
        content_hash=content_hash(f"{repo_url}\ncomponent_library\n{overview}"),
    )


def _is_web_ui_text(text: str, heading: str = "", source_file: str = "") -> bool:
    clean = _clean_text(text)
    if not (24 <= len(clean) <= 5000):
        return False
    probe = f"{source_file} {heading} {clean}"
    if _looks_like_technical_ui_doc(probe, source_file):
        return False
    if _has_strong_web_ui_asset_signal(probe):
        return True
    has_framework = bool(_infer_framework(probe))
    has_core_web_ui = _contains_any(probe, WEB_UI_HINTS)
    has_design_intent = _contains_any(
        probe,
        (*ACTION_HINTS, *DESIGN_RULE_HINTS, *LAYOUT_HINTS, *INTERACTION_HINTS, "prompt", "spec", "guideline"),
    )
    return has_core_web_ui and has_framework and has_design_intent and _path_has_asset_context(source_file)


def _is_prompt_like(text: str, heading: str = "", source_file: str = "") -> bool:
    probe = f"{source_file} {heading} {text}"
    return _is_web_ui_text(text, heading, source_file) and (
        _contains_any(text, ACTION_HINTS)
        or _contains_any(probe, ("prompt", "提示词", "instruction", "spec"))
        or _has_strong_web_ui_asset_signal(probe)
    )


def _split_markdown_blocks(markdown: str) -> List[_Block]:
    text = markdown or ""
    blocks: List[_Block] = []

    def add(kind: str, title: str, start: int, end: int) -> None:
        start = max(0, start)
        end = min(len(text), max(start, end))
        block_text = text[start:end].strip()
        if len(block_text) < 24:
            return
        blocks.append(_Block(kind, _clean_text(title), text[start:end], start, end, _line_number(text, start), _line_number(text, end)))

    headings = list(HEADING_RE.finditer(text))
    for index, heading in enumerate(headings):
        level = len(heading.group("marks"))
        end = len(text)
        for next_heading in headings[index + 1:]:
            if len(next_heading.group("marks")) <= level:
                end = next_heading.start()
                break
        add("heading", heading.group("title"), heading.start(), end)

    delimiters = list(DELIMITER_RE.finditer(text))
    if delimiters:
        starts = [0, *[match.end() for match in delimiters]]
        ends = [*[match.start() for match in delimiters], len(text)]
        for start, end in zip(starts, ends):
            add("delimiter", "", start, end)

    items = list(LIST_ITEM_RE.finditer(text))
    for index, item in enumerate(items):
        end = items[index + 1].start() if index + 1 < len(items) else len(text)
        add("list_item", "", item.start(), end)

    if not headings:
        add("root", "", 0, len(text))
    return sorted(blocks, key=lambda block: (block.start, block.end - block.start))


def _candidate_from_text(
    *,
    prompt_text: str,
    block_text: str,
    source_page_url: str,
    source_file: str,
    source_heading: str,
    line_start: int,
    line_end: int,
    base_url: str,
    evidence_prefix: str,
) -> Optional[WebUiAssetCandidate]:
    prompt = _clean_text(prompt_text)
    if _looks_like_reference_only(prompt):
        return None
    if not _is_web_ui_text(prompt, source_heading, source_file):
        return None
    probe = f"{source_file} {source_heading} {prompt} {block_text[:600]}"
    if _looks_like_technical_ui_doc(probe, source_file):
        return None
    component_type = _infer_from_hints(probe, COMPONENT_HINTS)
    page_type = _infer_from_hints(probe, PAGE_HINTS)
    framework = _infer_framework(probe)
    is_prompt_source = "Prompt 标签" in evidence_prefix or "Prompt 代码块" in evidence_prefix or "Prompt/规范列" in evidence_prefix
    asset_type = ("component_prompt" if component_type else "page_prompt" if page_type else "component_prompt") if is_prompt_source else _infer_asset_type(probe, component_type, page_type)
    asset_group = _infer_asset_group(asset_type)
    screenshot = _choose_screenshot(block_text, base_url)
    design_rules = prompt if asset_type in {"design_rule", "layout_pattern", "interaction_pattern"} else ""
    ui_pattern = component_type or page_type or asset_type
    confidence = 86 if "prompt" in probe.lower() or "提示词" in probe else 78
    if screenshot:
        confidence += 4
    if framework:
        confidence += 3
    hash_value = content_hash(f"{source_file}\n{asset_type}\n{source_heading}\n{prompt}")
    return WebUiAssetCandidate(
        source_page_url=source_page_url,
        source_file=source_file,
        source_heading=source_heading,
        line_start=line_start,
        line_end=line_end,
        asset_group=asset_group,
        asset_type=asset_type,
        library_kind="",
        component_type=component_type,
        page_type=page_type,
        framework=framework,
        prompt_text=prompt,
        design_rules=design_rules,
        ui_pattern=ui_pattern,
        screenshot_original_url=screenshot,
        tags=_tags(component_type, page_type, framework, asset_type, asset_group, ""),
        evidence=f"{evidence_prefix}；识别到 Web UI 线索，资产类型为 {asset_type}，组件/页面线索为 {component_type or page_type or '未明确'}。",
        confidence=min(confidence, 95),
        content_hash=hash_value,
    )


def _extract_markdown_table_assets(document: Dict[str, str]) -> List[WebUiAssetCandidate]:
    path = document["path"]
    content = document["content"]
    base_url = document.get("raw_base_url") or ""
    source_page_url = document.get("source_page_url") or ""
    lines = content.splitlines()
    assets: List[WebUiAssetCandidate] = []
    index = 0
    while index < len(lines) - 2:
        headers = _split_table_row(lines[index])
        if not headers or not TABLE_SEPARATOR_RE.match(lines[index + 1]):
            index += 1
            continue
        prompt_cols = _column_indices(headers, ("prompt", "提示词", "instruction", "description", "spec", "规范"))
        if not prompt_cols:
            index += 1
            continue
        name_cols = _column_indices(headers, ("component", "name", "title", "page", "组件", "名称", "页面"))
        screenshot_cols = _column_indices(headers, ("screenshot", "preview", "demo", "result", "image", "截图", "预览", "效果"))
        row_index = index + 2
        while row_index < len(lines):
            cells = _split_table_row(lines[row_index])
            if not cells or len(cells) < len(headers):
                break
            prompt = next((_clean_text(cells[col]) for col in prompt_cols if col < len(cells) and _is_web_ui_text(cells[col], " ".join(headers), path)), "")
            if prompt:
                title = next((_clean_text(cells[col]) for col in name_cols if col < len(cells) and cells[col].strip()), "")
                screenshot_text = " ".join(cells[col] for col in screenshot_cols if col < len(cells))
                row_text = " ".join(cells)
                candidate = _candidate_from_text(
                    prompt_text=prompt,
                    block_text=f"{row_text}\n{screenshot_text}",
                    source_page_url=source_page_url,
                    source_file=path,
                    source_heading=title or "Markdown 表格",
                    line_start=row_index + 1,
                    line_end=row_index + 1,
                    base_url=base_url,
                    evidence_prefix=f"Markdown 表格第 {row_index + 1} 行包含 Web UI Prompt/规范列",
                )
                if candidate:
                    if screenshot_text:
                        screenshot = _choose_screenshot(screenshot_text, base_url)
                        if screenshot:
                            candidate = replace(candidate, screenshot_original_url=screenshot)
                    assets.append(candidate)
            row_index += 1
        index = max(row_index, index + 1)
    return assets


def _extract_markdown_block_assets(document: Dict[str, str]) -> List[WebUiAssetCandidate]:
    path = document["path"]
    content = document["content"]
    base_url = document.get("raw_base_url") or ""
    source_page_url = document.get("source_page_url") or ""
    assets: List[WebUiAssetCandidate] = []
    if _path_is_excluded(path):
        return assets
    for block in _split_markdown_blocks(content):
        block_probe = f"{path} {block.title} {block.text[:1400]}"
        if not _contains_any(block_probe, WEB_UI_HINTS) and not _has_strong_web_ui_asset_signal(block_probe):
            continue
        for match in PROMPT_LABEL_RE.finditer(block.text):
            prompt = _clean_text(match.group("prompt"))
            candidate = _candidate_from_text(
                prompt_text=prompt,
                block_text=block.text,
                source_page_url=source_page_url,
                source_file=path,
                source_heading=block.title,
                line_start=block.line_start + _line_number(block.text, match.start("prompt")) - 1,
                line_end=block.line_start + _line_number(block.text, match.end("prompt")) - 1,
                base_url=base_url,
                evidence_prefix=f"Markdown {block.kind} 块中存在 Prompt 标签",
            )
            if candidate:
                assets.append(candidate)
        for match in FENCED_RE.finditer(block.text):
            lang = (match.group("lang") or "").lower()
            body = _clean_text(match.group("body"))
            if lang not in {"", "prompt", "text", "txt", "md", "markdown"} and not _contains_any(f"{block.title} {block.text[max(0, match.start() - 160):match.start()]}", ("prompt", "提示词")):
                continue
            if not _is_prompt_like(body, block.title, path):
                continue
            candidate = _candidate_from_text(
                prompt_text=body,
                block_text=block.text,
                source_page_url=source_page_url,
                source_file=path,
                source_heading=block.title,
                line_start=block.line_start + _line_number(block.text, match.start("body")) - 1,
                line_end=block.line_start + _line_number(block.text, match.end("body")) - 1,
                base_url=base_url,
                evidence_prefix=f"Markdown {block.kind} 块中存在 Web UI Prompt 代码块",
            )
            if candidate:
                assets.append(candidate)
        allow_rule_block = _path_has_asset_context(path) or _contains_any(block.title, DESIGN_ASSET_HEADING_HINTS)
        if (
            allow_rule_block
            and not any(asset.source_file == path and asset.line_start >= block.line_start and asset.line_end <= block.line_end for asset in assets)
            and not any(TABLE_SEPARATOR_RE.match(line) for line in block.text.splitlines())
        ):
            clean_block = _clean_text(re.sub(r"```.*?```", "", block.text, flags=re.DOTALL))
            if (
                _contains_any(f"{block.title} {clean_block}", (*DESIGN_RULE_HINTS, *LAYOUT_HINTS, *INTERACTION_HINTS))
                and 60 <= len(clean_block) <= 1800
                and (_contains_any(block.title, DESIGN_ASSET_HEADING_HINTS) or _has_strong_web_ui_asset_signal(f"{block.title} {clean_block}"))
                and not _looks_like_technical_ui_doc(f"{block.title} {clean_block}", path)
            ):
                candidate = _candidate_from_text(
                    prompt_text=clean_block,
                    block_text=block.text,
                    source_page_url=source_page_url,
                    source_file=path,
                    source_heading=block.title,
                    line_start=block.line_start,
                    line_end=block.line_end,
                    base_url=base_url,
                    evidence_prefix=f"Markdown {block.kind} 块包含 Web UI 设计规范/布局/交互说明",
                )
                if candidate:
                    assets.append(candidate)
    return assets


def _structured_objects(value: Any) -> Iterable[Dict[str, Any]]:
    if isinstance(value, dict):
        yield value
        for nested in value.values():
            yield from _structured_objects(nested)
    elif isinstance(value, list):
        for item in value:
            yield from _structured_objects(item)


def _value_for_keys(obj: Dict[str, Any], keys: Sequence[str]) -> str:
    lowered = {str(key).lower(): key for key in obj}
    for key in keys:
        actual = lowered.get(key)
        if actual is not None and obj.get(actual) is not None:
            return str(obj[actual]).strip()
    return ""


def _extract_structured_assets(document: Dict[str, str]) -> List[WebUiAssetCandidate]:
    path = document["path"]
    content = document["content"]
    base_url = document.get("raw_base_url") or ""
    source_page_url = document.get("source_page_url") or ""
    if _path_is_excluded(path):
        return []
    suffix = PurePosixPath(path).suffix.lower()
    rows: List[Dict[str, Any]] = []
    if suffix in {".json", ".jsonl"}:
        try:
            parsed = [json.loads(line) for line in content.splitlines() if line.strip()] if suffix == ".jsonl" else json.loads(content)
            rows = list(_structured_objects(parsed))
        except Exception:
            rows = []
    elif suffix == ".csv":
        try:
            rows = [dict(row) for row in csv.DictReader(io.StringIO(content))]
        except Exception:
            rows = []
    elif suffix in {".yaml", ".yml"}:
        simple: Dict[str, str] = {}
        for line in content.splitlines():
            if ":" not in line or line.startswith((" ", "\t")):
                continue
            key, value = line.split(":", 1)
            simple[key.strip()] = value.strip().strip("'\"")
        rows = [simple] if simple else []
    assets: List[WebUiAssetCandidate] = []
    for index, row in enumerate(rows, start=1):
        prompt = _value_for_keys(row, ("web_ui_prompt", "ui_prompt", "component_prompt", "page_prompt", "prompt", "instruction", "description", "spec", "design_rule"))
        if not prompt or not _is_web_ui_text(prompt, path, path):
            continue
        title = _value_for_keys(row, ("component", "component_type", "name", "title", "page", "page_type"))
        image = _value_for_keys(row, ("screenshot", "preview", "demo", "result", "image", "image_url"))
        block_text = " ".join(str(value) for value in row.values() if value is not None)
        if _looks_like_technical_ui_doc(f"{title} {block_text}", path):
            continue
        candidate = _candidate_from_text(
            prompt_text=prompt,
            block_text=block_text,
            source_page_url=source_page_url,
            source_file=path,
            source_heading=title or PurePosixPath(path).stem,
            line_start=index,
            line_end=index,
            base_url=base_url,
            evidence_prefix=f"结构化文件 {path} 的同一对象/行包含 Web UI Prompt 或规范字段",
        )
        if candidate and image and not _is_bad_image(image):
            candidate = replace(candidate, screenshot_original_url=urljoin(base_url, image) if base_url else image)
        if candidate:
            assets.append(candidate)
    return assets


def extract_web_ui_assets(
    documents: Sequence[Dict[str, str]],
    repo_name: str = "",
    repo_url: str = "",
    readme: str = "",
    progress_callback: Optional[Callable[[Dict[str, Any]], None]] = None,
) -> Dict[str, Any]:
    assets: List[WebUiAssetCandidate] = []
    seen: set[str] = set()
    seen_prompt_keys: set[tuple[str, str, str]] = set()
    sorted_docs = sorted(documents, key=lambda doc: (0 if PurePosixPath(doc.get("path") or "").suffix.lower() in {".md", ".mdx"} else 1, doc.get("path") or ""))
    repo_is_component_library = _looks_like_component_library_repo(repo_name, readme, documents)
    if repo_is_component_library:
        library_candidate = _build_component_library_candidate(
            repo_name=repo_name,
            repo_url=repo_url,
            readme=readme,
            documents=sorted_docs,
        )
        if library_candidate:
            assets.append(library_candidate)
        if progress_callback:
            progress_callback(
                {
                    "total_files": len(sorted_docs),
                    "processed_files": len(sorted_docs),
                    "current_file": "README.md",
                    "prompt_candidates": len(assets),
                    "pair_candidates": 0,
                }
            )
        return {
            "web_ui_assets": assets,
            "prompt_candidates": [asset.prompt_text for asset in assets],
            "preview_images": list(dict.fromkeys(asset.screenshot_original_url for asset in assets if asset.screenshot_original_url)),
            "scanned_files": [document.get("path") or "" for document in sorted_docs],
        }
    for index, document in enumerate(sorted_docs, start=1):
        path = document.get("path") or ""
        suffix = PurePosixPath(path).suffix.lower()
        if suffix in {".md", ".mdx", ".txt", ".prompt"}:
            found = [*_extract_markdown_table_assets(document), *_extract_markdown_block_assets(document)]
        elif suffix in {".json", ".jsonl", ".csv", ".yaml", ".yml"}:
            found = _extract_structured_assets(document)
        else:
            found = []
        for candidate in found:
            prompt_key = (candidate.source_file, candidate.prompt_text, "")
            if prompt_key in seen_prompt_keys:
                continue
            if candidate.content_hash in seen:
                continue
            seen.add(candidate.content_hash)
            seen_prompt_keys.add(prompt_key)
            assets.append(candidate)
        if progress_callback:
            progress_callback(
                {
                    "total_files": len(sorted_docs),
                    "processed_files": index,
                    "current_file": path,
                    "prompt_candidates": len(assets),
                    "pair_candidates": 0,
                }
            )
    return {
        "web_ui_assets": assets,
        "prompt_candidates": [asset.prompt_text for asset in assets],
        "preview_images": list(dict.fromkeys(asset.screenshot_original_url for asset in assets if asset.screenshot_original_url)),
        "scanned_files": [document.get("path") or "" for document in sorted_docs],
    }


async def save_web_ui_assets(
    conn,
    repo_id: int,
    record: Dict[str, Any],
    progress_callback: Optional[Callable[[Dict[str, Any]], None]] = None,
) -> Dict[str, int]:
    now = utc_now()
    added = 0
    updated = 0
    skipped = 0
    screenshots_added = 0
    assets: Sequence[WebUiAssetCandidate] = record.get("_web_ui_assets") or []

    for candidate in assets:
        screenshot_local_path = ""
        screenshot_hash = ""
        if candidate.screenshot_original_url:
            if progress_callback:
                progress_callback({"current_file": candidate.source_file, "phase": "download_web_ui_screenshot"})
            downloaded = await download_image(candidate.screenshot_original_url)
            if downloaded:
                asset_row = conn.execute("SELECT * FROM assets WHERE image_hash = ?", (downloaded["image_hash"],)).fetchone()
                if asset_row:
                    screenshot_local_path = asset_row["image_local_path"]
                    screenshot_hash = asset_row["image_hash"]
                else:
                    conn.execute(
                        """
                        INSERT OR IGNORE INTO assets
                            (repo_id, image_original_url, image_local_path, thumbnail_local_path, image_hash, source_page_url,
                             asset_type, width, height, file_size, description, commercial_risk, created_at)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                        """,
                        (
                            repo_id,
                            candidate.screenshot_original_url,
                            downloaded["image_local_path"],
                            downloaded["thumbnail_local_path"],
                            downloaded["image_hash"],
                            candidate.source_page_url,
                            "web_ui_screenshot",
                            downloaded["width"],
                            downloaded["height"],
                            downloaded["file_size"],
                            f"Web UI 资产截图：{candidate.asset_type} / {candidate.source_heading}",
                            "unknown",
                            now,
                        ),
                    )
                    screenshot_local_path = downloaded["image_local_path"]
                    screenshot_hash = downloaded["image_hash"]
                    screenshots_added += 1
                    if progress_callback:
                        progress_callback({"downloaded_images_delta": 1, "images_added": screenshots_added})
            elif progress_callback:
                progress_callback({"error_count_delta": 1})

        existing = conn.execute(
            """
            SELECT * FROM web_ui_prompts
            WHERE repo_id = ? AND source_file = ? AND content_hash = ?
            """,
            (repo_id, candidate.source_file, candidate.content_hash),
        ).fetchone()
        tags_json = json.dumps(candidate.tags, ensure_ascii=False)
        if existing:
            updates: Dict[str, Any] = {}
            for field, value in {
                "source_page_url": candidate.source_page_url,
                "source_heading": candidate.source_heading,
                "asset_group": candidate.asset_group,
                "library_kind": candidate.library_kind,
                "screenshot_original_url": candidate.screenshot_original_url,
                "screenshot_local_path": screenshot_local_path,
                "screenshot_hash": screenshot_hash,
                "evidence": candidate.evidence,
                "framework": candidate.framework,
                "component_type": candidate.component_type,
                "page_type": candidate.page_type,
                "tags_json": tags_json,
            }.items():
                if value and not existing[field]:
                    updates[field] = value
            if updates:
                updates["updated_at"] = now
                assignments = ", ".join(f"{key} = ?" for key in updates)
                conn.execute(f"UPDATE web_ui_prompts SET {assignments} WHERE id = ?", (*updates.values(), existing["id"]))
                updated += 1
            else:
                skipped += 1
            continue

        conn.execute(
            """
            INSERT INTO web_ui_prompts
                (repo_id, repo_name, repo_url, source_page_url, source_file, source_heading, line_start, line_end,
                 asset_group, asset_type, library_kind, component_type, page_type, framework, prompt_text, prompt_cn_translation, design_rules,
                 ui_pattern, screenshot_original_url, screenshot_local_path, screenshot_hash, tags_json, quality_level,
                 selection_status, reuse_value, evidence, confidence, content_hash, license, commercial_risk,
                 generated_by, created_at, updated_at, notes)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
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
                candidate.asset_group,
                candidate.asset_type,
                candidate.library_kind,
                candidate.component_type,
                candidate.page_type,
                candidate.framework,
                candidate.prompt_text,
                None,
                candidate.design_rules,
                candidate.ui_pattern,
                candidate.screenshot_original_url,
                screenshot_local_path,
                screenshot_hash,
                tags_json,
                "pending_review",
                "pending_review",
                "可作为 Web UI 组件、页面或设计规范资产复用，需人工分级后进入精选库。",
                candidate.evidence,
                candidate.confidence,
                candidate.content_hash,
                record.get("license") or "unknown",
                "unknown",
                "web_ui_rule_scan_v1",
                now,
                now,
                "",
            ),
        )
        added += 1

    return {
        "web_ui_prompts_found": len(assets),
        "web_ui_prompts_added": added,
        "web_ui_prompts_updated": updated,
        "web_ui_prompts_skipped": skipped,
        "web_ui_screenshots_added": screenshots_added,
    }
