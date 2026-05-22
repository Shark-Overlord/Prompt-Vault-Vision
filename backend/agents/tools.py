from __future__ import annotations

import re
from typing import Any, Dict, List

from database import fetch_all, fetch_one


STOPWORDS = {
    "prompt",
    "prompts",
    "提示词",
    "帮我",
    "找一下",
    "需要",
    "看看",
    "哪些",
    "对应",
    "相关",
    "本地",
    "库里",
    "里面",
    "资源",
    "寻找",
    "查询",
    "搜索",
    "一个",
}

CATEGORY_HINTS = {
    "web_ui_prompt": ("web ui", "frontend", "前端", "网页", "网站", "落地页", "dashboard", "仪表盘", "组件", "设计系统", "shadcn", "tailwind", "saas"),
    "image_generation_prompt": ("图像生成", "图片生成", "文生图", "text to image", "image generation", "海报", "产品图", "商品图", "摄影", "视觉", "封面", "风格", "卡通", "动漫", "插画", "角色", "头像", "壁纸"),
    "skill_repository": ("skill", "ai skill", "agent skill", "mcp", "mcp server", "mcp tool", "agent tool", "toolkit", "workflow", "cursor rules", "claude skill", "codex skill", "desktop skill", "技能", "工具", "工作流"),
    "video_generation_prompt": ("视频生成", "文生视频", "图生视频", "分镜", "镜头", "cinematic", "storyboard", "kling", "veo", "runway", "seedance", "wan"),
}

STYLE_SYNONYMS = {
    "卡通": ("卡通", "cartoon", "toon", "动漫", "动画", "可爱", "插画", "illustration"),
    "动漫": ("动漫", "anime", "manga", "卡通", "动画", "二次元", "插画"),
    "插画": ("插画", "illustration", "digital illustration", "卡通", "绘本", "手绘"),
    "像素": ("像素", "pixel", "pixel art", "8-bit", "16-bit"),
    "赛博": ("赛博", "cyberpunk", "neon", "futuristic"),
    "电影": ("电影", "cinematic", "film still", "dramatic lighting"),
    "写实": ("写实", "photorealistic", "realistic", "摄影"),
    "3d": ("3d", "three dimensional", "isometric", "clay render"),
}

INTENT_HINTS = {
    "find_prompt": ("找", "搜索", "查询", "推荐", "有没有", "需要", "给我", "寻找"),
    "review_candidates": ("候选", "配对", "证据", "待复查", "人工审核", "人工复查", "匹配"),
    "find_repo": ("仓库", "资源库", "复扫", "扫描", "github", "repo", "repository"),
}

SCENARIO_HINTS = {
    "landing_page": ("落地页", "landing", "首页", "hero"),
    "dashboard": ("dashboard", "仪表盘", "数据看板"),
    "app_ui": ("app ui", "应用界面", "移动端"),
    "saas_ui": ("saas", "后台", "控制台"),
    "product_image": ("产品图", "商品图", "product image", "product photo"),
    "poster": ("海报", "poster"),
    "commercial_visual": ("商业视觉", "广告图", "commercial"),
    "product_video": ("产品视频", "商品视频", "product video"),
    "cinematic_video": ("电影感", "cinematic", "镜头"),
    "storyboard": ("分镜", "storyboard"),
}

PROMPT_ASSET_ROUTES = {
    "image_generation_prompt": "/prompt-assets/image-generation",
    "video_generation_prompt": "/prompt-assets/video-generation",
}

ALLOWED_TOOLS = {"web_ui_prompt_search", "visual_prompt_pair_search", "skill_repo_search", "repo_search", "pair_candidate_search"}


def _like_query(query: str) -> tuple[str, str]:
    clean = " ".join((query or "").strip().split())
    return clean, f"%{clean}%"


def _contains_any(text: str, hints: tuple[str, ...]) -> bool:
    lower = text.lower()
    return any(hint.lower() in lower for hint in hints)


def _extract_terms(query: str) -> List[str]:
    clean = " ".join((query or "").strip().split())
    if not clean:
        return []
    terms: List[str] = []
    lower = clean.lower()
    known_terms = (
        "web ui",
        "frontend",
        "dashboard",
        "landing",
        "saas",
        "shadcn",
        "tailwind",
        "海报",
        "产品图",
        "商品图",
        "摄影",
        "商业视觉",
        "视频",
        "分镜",
        "镜头",
        "电影感",
        "低商用风险",
        "精选",
        "卡通",
        "动漫",
        "动画",
        "插画",
        "cartoon",
        "anime",
        "illustration",
        "mcp",
        "skill",
        "agent",
        "workflow",
        "工具",
        "技能",
        "工作流",
        "文件整理",
        "网页抓取",
        "桌面自动化",
    )
    for term in known_terms:
        if term.lower() in lower and term not in terms:
            terms.append(term)
    for token in re.split(r"[^a-zA-Z0-9\u4e00-\u9fff]+", clean):
        token = token.strip()
        if not token or token.lower() in STOPWORDS or token in STOPWORDS:
            continue
        if re.fullmatch(r"[\u4e00-\u9fff]{1}", token):
            continue
        if len(token) < 2:
            continue
        if token not in terms:
            terms.append(token)
    expanded: List[str] = []
    for term in terms:
        if term not in expanded:
            expanded.append(term)
        for key, synonyms in STYLE_SYNONYMS.items():
            if key.lower() in term.lower() or term.lower() in [item.lower() for item in synonyms]:
                for synonym in synonyms:
                    if synonym not in expanded:
                        expanded.append(synonym)
    return expanded[:20]


def _infer_intents(query: str) -> List[str]:
    intents = [intent for intent, hints in INTENT_HINTS.items() if _contains_any(query, hints)]
    if not intents:
        intents.append("find_prompt")
    return intents


def _infer_query_focus(query: str, categories: List[str], scenarios: List[str], terms: List[str]) -> str:
    if "skill_repository" in categories:
        return "Skill 仓库能力资产"
    if "web_ui_prompt" in categories:
        return "Web UI 仓库级前端资产"
    if "video_generation_prompt" in categories:
        return "视频生成 Prompt"
    if "image_generation_prompt" in categories:
        if scenarios:
            return f"图像生成 Prompt，场景：{', '.join(scenarios)}"
        style_terms = [term for term in terms if term in {"卡通", "动漫", "动画", "插画", "cartoon", "anime", "illustration"}]
        if style_terms:
            return f"图像生成 Prompt，风格：{', '.join(style_terms[:4])}"
        return "图像生成 Prompt"
    return "本地 Prompt 与仓库资产"


def infer_library_tool_plan(query: str) -> Dict[str, Any]:
    clean = " ".join((query or "").strip().split())
    terms = _extract_terms(clean)
    intents = _infer_intents(clean)
    categories = [category for category, hints in CATEGORY_HINTS.items() if _contains_any(clean, hints)]
    scenarios = [scenario for scenario, hints in SCENARIO_HINTS.items() if _contains_any(clean, hints)]
    wants_repo = _contains_any(clean, ("仓库", "资源库", "复扫", "扫描", "github", "repo", "repository"))
    wants_candidate = _contains_any(clean, ("候选", "配对", "证据", "待复查", "匹配", "人工审核", "人工复查"))

    has_style_term = any(_contains_any(clean, synonyms) for synonyms in STYLE_SYNONYMS.values())
    if has_style_term and "image_generation_prompt" not in categories and "web_ui_prompt" not in categories:
        categories.append("image_generation_prompt")

    if not categories and not wants_repo and not wants_candidate:
        categories = ["image_generation_prompt"]

    wants_web_ui = "web_ui_prompt" in categories
    wants_skill = "skill_repository" in categories
    wants_prompt_assets = any(category in categories for category in ("image_generation_prompt", "video_generation_prompt"))

    tools: List[str] = []
    if wants_web_ui:
        tools.append("web_ui_prompt_search")
    if wants_skill:
        tools.append("skill_repo_search")
    if wants_prompt_assets:
        tools.append("visual_prompt_pair_search")
    if wants_repo:
        tools.append("repo_search")
    if wants_candidate:
        tools.append("pair_candidate_search")
    if not tools:
        tools = ["web_ui_prompt_search", "visual_prompt_pair_search", "skill_repo_search", "repo_search"]

    return {
        "query": clean,
        "intent": intents,
        "focus": _infer_query_focus(clean, categories, scenarios, terms),
        "terms": terms,
        "expanded_keywords": terms,
        "categories": categories,
        "scenarios": scenarios,
        "tools": tools,
        "target_tables": _target_tables_for_tools(tools),
        "planner_mode": "rules",
        "planner_reason": "本地规则规划结果。",
        "wants_repo": wants_repo,
        "wants_candidate": wants_candidate,
        "wants_web_ui": wants_web_ui,
        "wants_skill": wants_skill,
        "wants_prompt_assets": wants_prompt_assets,
    }


def _target_tables_for_tools(tools: List[str]) -> List[str]:
    tables: List[str] = []
    if "web_ui_prompt_search" in tools:
        tables.append("web_ui_repo_profiles")
    if "skill_repo_search" in tools:
        tables.append("skill_repo_profiles")
    if "visual_prompt_pair_search" in tools:
        tables.append("prompt_effect_pairs")
    if "repo_search" in tools:
        tables.append("repos")
    if "pair_candidate_search" in tools:
        tables.append("pair_candidates")
    return tables


def _clean_string_list(value: Any, allowed: set[str] | None = None, limit: int = 20) -> List[str]:
    if not isinstance(value, list):
        return []
    result: List[str] = []
    for item in value:
        text = str(item).strip()
        if not text:
            continue
        if allowed is not None and text not in allowed:
            continue
        if text not in result:
            result.append(text)
        if len(result) >= limit:
            break
    return result


def normalize_library_tool_plan(query: str, ai_plan: Dict[str, Any] | None, fallback_plan: Dict[str, Any] | None = None) -> Dict[str, Any]:
    fallback = fallback_plan or infer_library_tool_plan(query)
    ai_plan = ai_plan or {}
    categories = _clean_string_list(ai_plan.get("categories"), set(CATEGORY_HINTS.keys()), limit=4) or list(fallback.get("categories") or [])
    scenarios = _clean_string_list(ai_plan.get("scenarios"), set(SCENARIO_HINTS.keys()), limit=6) or list(fallback.get("scenarios") or [])
    tools = _clean_string_list(ai_plan.get("tools"), ALLOWED_TOOLS, limit=5)

    if not tools:
        tools = []
        if "web_ui_prompt" in categories:
            tools.append("web_ui_prompt_search")
        if "skill_repository" in categories:
            tools.append("skill_repo_search")
        if any(category in categories for category in ("image_generation_prompt", "video_generation_prompt")):
            tools.append("visual_prompt_pair_search")
        if bool(ai_plan.get("wants_repo")) or "find_repo" in _clean_string_list(ai_plan.get("intent"), None, limit=6):
            tools.append("repo_search")
        if bool(ai_plan.get("wants_candidate")) or "review_candidates" in _clean_string_list(ai_plan.get("intent"), None, limit=6):
            tools.append("pair_candidate_search")
    if not tools:
        tools = list(fallback.get("tools") or ["visual_prompt_pair_search"])

    ai_terms = _clean_string_list(ai_plan.get("expanded_keywords") or ai_plan.get("terms"), None, limit=20)
    terms = []
    for term in [*ai_terms, *(fallback.get("expanded_keywords") or fallback.get("terms") or [])]:
        text = str(term).strip()
        if text and text not in terms:
            terms.append(text)
        if len(terms) >= 20:
            break

    intent = _clean_string_list(ai_plan.get("intent"), None, limit=6) or list(fallback.get("intent") or ["find_prompt"])
    focus = str(ai_plan.get("focus") or "").strip() or _infer_query_focus(query, categories, scenarios, terms)
    return {
        "query": " ".join((query or "").strip().split()),
        "intent": intent,
        "focus": focus,
        "terms": terms,
        "expanded_keywords": terms,
        "categories": categories,
        "scenarios": scenarios,
        "tools": tools,
        "target_tables": _target_tables_for_tools(tools),
        "planner_mode": str(ai_plan.get("planner_mode") or "ai").strip() if ai_plan else fallback.get("planner_mode", "rules_fallback"),
        "planner_reason": str(ai_plan.get("reason") or ai_plan.get("planner_reason") or "").strip() if ai_plan else "AI 查询规划不可用，使用规则回退。",
        "wants_repo": "repo_search" in tools,
        "wants_candidate": "pair_candidate_search" in tools,
        "wants_web_ui": "web_ui_prompt_search" in tools,
        "wants_skill": "skill_repo_search" in tools,
        "wants_prompt_assets": "visual_prompt_pair_search" in tools,
    }


def _terms_where(fields: List[str], terms: List[str]) -> tuple[str, List[Any]]:
    if not terms:
        return "", []
    clauses = []
    params: List[Any] = []
    for term in terms:
        like = f"%{term}%"
        clauses.append("(" + " OR ".join(f"{field} LIKE ?" for field in fields) + ")")
        params.extend([like] * len(fields))
    return "(" + " OR ".join(clauses) + ")", params


def _source(
    source_type: str,
    source_id: int,
    title: str,
    data: Dict[str, Any],
    tool: str,
    route: str,
    external_url: str | None = None,
    preview_image: str | None = None,
    snippet: str | None = None,
    matched_reason: str | None = None,
) -> Dict[str, Any]:
    return {
        "type": source_type,
        "id": source_id,
        "title": title,
        "tool": tool,
        "route": route,
        "external_url": external_url,
        "preview_image": preview_image,
        "snippet": snippet,
        "matched_reason": matched_reason,
        "data": data,
    }


def search_repos(query: str, limit: int = 6, terms: List[str] | None = None, categories: List[str] | None = None) -> List[Dict[str, Any]]:
    clean, like = _like_query(query)
    terms = terms if terms is not None else _extract_terms(clean)
    where = ["1 = 1"]
    params: List[Any] = []
    term_clause, term_params = _terms_where(["repo_name", "owner", "repo_url", "category", "summary", "notes", "license"], terms)
    if term_clause:
        where.append(term_clause)
        params.extend(term_params)
    elif clean:
        where.append("(repo_name LIKE ? OR owner LIKE ? OR repo_url LIKE ? OR category LIKE ? OR summary LIKE ? OR notes LIKE ?)")
        params.extend([like] * 6)
    if categories:
        where.append(f"category IN ({', '.join('?' for _ in categories)})")
        params.extend(categories)
    params.append(limit)
    return fetch_all(
        f"""
        SELECT id, repo_name, owner, repo_url, category, quality_level, status, summary,
               prompt_effect_pair_count, last_checked_at
        FROM repos
        WHERE {' AND '.join(where)}
        ORDER BY prompt_effect_pair_count DESC, stars DESC, last_checked_at DESC
        LIMIT ?
        """,
        tuple(params),
    )


def search_prompt_pairs(
    query: str,
    limit: int = 6,
    terms: List[str] | None = None,
    categories: List[str] | None = None,
    scenarios: List[str] | None = None,
) -> List[Dict[str, Any]]:
    clean, like = _like_query(query)
    terms = terms if terms is not None else _extract_terms(clean)
    where = ["1 = 1"]
    params: List[Any] = []
    term_clause, term_params = _terms_where(
        ["repo_name", "original_prompt", "prompt_cn_explanation", "effect_review", "reusable_value", "scenario", "category", "visual_style"],
        terms,
    )
    if term_clause:
        where.append(term_clause)
        params.extend(term_params)
    elif clean:
        where.append(
            "(original_prompt LIKE ? OR prompt_cn_explanation LIKE ? OR effect_review LIKE ? OR reusable_value LIKE ? OR scenario LIKE ? OR category LIKE ?)"
        )
        params.extend([like] * 6)
    if categories:
        where.append(f"category IN ({', '.join('?' for _ in categories)})")
        params.extend(categories)
    if scenarios:
        where.append(f"scenario IN ({', '.join('?' for _ in scenarios)})")
        params.extend(scenarios)
    params.append(limit)
    return fetch_all(
        f"""
        SELECT id, repo_id, repo_name, repo_url, source_page_url, original_prompt,
               prompt_cn_explanation, category, scenario, quality_level,
               selection_status, effect_review, reusable_value, commercial_risk,
               image_local_path, image_original_url, pair_evidence, pair_confidence
        FROM prompt_effect_pairs
        WHERE {' AND '.join(where)}
        ORDER BY CASE selection_status WHEN 'featured' THEN 0 WHEN 'normal' THEN 1 ELSE 2 END, updated_at DESC
        LIMIT ?
        """,
        tuple(params),
    )


def search_pair_candidates(query: str, limit: int = 6, terms: List[str] | None = None) -> List[Dict[str, Any]]:
    clean, like = _like_query(query)
    terms = terms if terms is not None else _extract_terms(clean)
    where = ["1 = 1"]
    params: List[Any] = []
    term_clause, term_params = _terms_where(["original_prompt", "evidence", "source_file", "repo_name", "match_type", "review_status"], terms)
    if term_clause:
        where.append(term_clause)
        params.extend(term_params)
    elif clean:
        where.append("(original_prompt LIKE ? OR evidence LIKE ? OR source_file LIKE ? OR repo_name LIKE ?)")
        params.extend([like] * 4)
    params.append(limit)
    return fetch_all(
        f"""
        SELECT id, repo_id, repo_name, repo_url, source_page_url, source_file,
               original_prompt, image_original_url, match_type, match_score,
               evidence, review_status, selection_status
        FROM pair_candidates
        WHERE {' AND '.join(where)}
        ORDER BY match_score DESC, updated_at DESC
        LIMIT ?
        """,
        tuple(params),
    )


def search_web_ui_prompts(query: str, limit: int = 6, terms: List[str] | None = None) -> List[Dict[str, Any]]:
    clean, like = _like_query(query)
    terms = terms if terms is not None else _extract_terms(clean)
    where = ["1 = 1"]
    params: List[Any] = []
    term_clause, term_params = _terms_where(
        [
            "repo_name",
            "repo_url",
            "profile_type",
            "library_kind",
            "ui_stack",
            "supported_frontend_types_json",
            "component_focus_json",
            "style_keywords_json",
            "reuse_mode",
            "summary_cn",
            "ai_summary_cn",
            "evidence",
            "ai_reason_cn",
            "notes",
        ],
        terms,
    )
    if term_clause:
        where.append(term_clause)
        params.extend(term_params)
    elif clean:
        where.append(
            "(repo_name LIKE ? OR profile_type LIKE ? OR library_kind LIKE ? OR ui_stack LIKE ? OR supported_frontend_types_json LIKE ? OR component_focus_json LIKE ? OR style_keywords_json LIKE ? OR summary_cn LIKE ? OR ai_summary_cn LIKE ?)"
        )
        params.extend([like] * 9)
    params.append(limit)
    return fetch_all(
        f"""
        SELECT id, repo_id, repo_name, repo_url, profile_type, library_kind, ui_stack,
               supported_frontend_types_json, component_focus_json, style_keywords_json,
               reuse_mode, summary_cn, ai_summary_cn, evidence, ai_reason_cn,
               screenshot_local_path, screenshot_original_url, quality_level, selection_status, commercial_risk
        FROM web_ui_repo_profiles
        WHERE {' AND '.join(where)}
        ORDER BY CASE selection_status WHEN 'featured' THEN 0 WHEN 'normal' THEN 1 ELSE 2 END, updated_at DESC
        LIMIT ?
        """,
        tuple(params),
    )


def search_skill_repo_profiles(query: str, limit: int = 6, terms: List[str] | None = None) -> List[Dict[str, Any]]:
    clean, like = _like_query(query)
    terms = terms if terms is not None else _extract_terms(clean)
    where = ["1 = 1"]
    params: List[Any] = []
    term_clause, term_params = _terms_where(
        [
            "repo_name",
            "repo_url",
            "skill_type",
            "target_platform",
            "runtime_stack",
            "capabilities_json",
            "input_types_json",
            "output_types_json",
            "use_cases_json",
            "tools_json",
            "install_method",
            "configuration_notes",
            "reuse_mode",
            "summary_cn",
            "ai_summary_cn",
            "evidence",
            "ai_reason_cn",
            "tags_json",
            "notes",
        ],
        terms,
    )
    if term_clause:
        where.append(term_clause)
        params.extend(term_params)
    elif clean:
        where.append(
            "(repo_name LIKE ? OR skill_type LIKE ? OR target_platform LIKE ? OR runtime_stack LIKE ? OR capabilities_json LIKE ? OR use_cases_json LIKE ? OR tools_json LIKE ? OR summary_cn LIKE ? OR ai_summary_cn LIKE ?)"
        )
        params.extend([like] * 9)
    params.append(limit)
    return fetch_all(
        f"""
        SELECT id, repo_id, repo_name, repo_url, skill_type, target_platform, runtime_stack,
               capabilities_json, input_types_json, output_types_json, use_cases_json, tools_json,
               install_method, configuration_notes, reuse_mode, summary_cn, ai_summary_cn,
               evidence, ai_reason_cn, tags_json, quality_level, selection_status, commercial_risk, confidence
        FROM skill_repo_profiles
        WHERE {' AND '.join(where)}
        ORDER BY CASE selection_status WHEN 'featured' THEN 0 WHEN 'normal' THEN 1 ELSE 2 END, updated_at DESC
        LIMIT ?
        """,
        tuple(params),
    )


def get_repo_brief(repo_id: int) -> Dict[str, Any] | None:
    return fetch_one("SELECT * FROM repos WHERE id = ?", (repo_id,))


def build_sources(query: str, plan: Dict[str, Any] | None = None) -> List[Dict[str, Any]]:
    plan = plan or infer_library_tool_plan(query)
    terms = plan["terms"]
    categories = plan["categories"]
    visual_categories = [category for category in categories if category in {"image_generation_prompt", "video_generation_prompt"}]
    sources: List[Dict[str, Any]] = []
    if "web_ui_prompt_search" in plan["tools"]:
        for row in search_web_ui_prompts(query, terms=terms, limit=8):
            title = row.get("repo_name") or "Web UI 仓库"
            sources.append(
                _source(
                    "web_ui_prompt",
                    row["id"],
                    title,
                    row,
                    "Web UI 仓库画像工具",
                    "/prompt-assets/web-ui",
                    row.get("repo_url"),
                    row.get("screenshot_local_path") or row.get("screenshot_original_url"),
                    row.get("ai_summary_cn") or row.get("summary_cn") or row.get("evidence"),
                    "根据你的描述匹配 Web UI 仓库级资产。",
                )
            )

    if "skill_repo_search" in plan["tools"]:
        for row in search_skill_repo_profiles(query, terms=terms, limit=8):
            title = row.get("repo_name") or "Skill 仓库"
            sources.append(
                _source(
                    "skill_repo",
                    row["id"],
                    title,
                    row,
                    "Skill 仓库画像工具",
                    "/prompt-assets/skills",
                    row.get("repo_url"),
                    None,
                    row.get("ai_summary_cn") or row.get("summary_cn") or row.get("evidence"),
                    "根据能力、平台、工具名和使用场景匹配 Skill 仓库资产。",
                )
            )

    if "visual_prompt_pair_search" in plan["tools"]:
        for row in search_prompt_pairs(query, terms=terms, categories=visual_categories or None, scenarios=plan["scenarios"] or None, limit=10):
            route = PROMPT_ASSET_ROUTES.get(row.get("category"), "/prompt-assets/image-generation")
            title = f"{row.get('scenario') or row.get('category') or 'Prompt'} · {row.get('repo_name')}"
            sources.append(
                _source(
                    "prompt_pair",
                    row["id"],
                    title,
                    row,
                    "视觉 Prompt 工具",
                    route,
                    row.get("repo_url"),
                    row.get("image_local_path") or row.get("image_original_url"),
                    row.get("prompt_cn_explanation") or row.get("original_prompt"),
                    "根据分类、场景和关键词匹配 Prompt 效果对。",
                )
            )

    if "repo_search" in plan["tools"]:
        repo_categories = categories or None
        for row in search_repos(query, terms=terms, categories=repo_categories, limit=8):
            sources.append(
                _source(
                    "repo",
                    row["id"],
                    row["repo_name"],
                    row,
                    "资源仓库工具",
                    "/repos",
                    row.get("repo_url"),
                    None,
                    row.get("summary"),
                    "根据仓库名、分类、摘要和备注匹配资源库。",
                )
            )

    if "pair_candidate_search" in plan["tools"]:
        for row in search_pair_candidates(query, terms=terms, limit=8):
            sources.append(
                _source(
                    "pair_candidate",
                    row["id"],
                    f"候选配对 · {row.get('repo_name')}",
                    row,
                    "候选配对工具",
                    "/pair-candidates",
                    row.get("repo_url"),
                    row.get("image_original_url"),
                    row.get("evidence") or row.get("original_prompt"),
                    "根据证据链、匹配分数和候选状态匹配待复查项。",
                )
            )

    deduped: List[Dict[str, Any]] = []
    seen: set[tuple[str, int]] = set()
    for source in sources:
        key = (source["type"], int(source["id"]))
        if key in seen:
            continue
        seen.add(key)
        deduped.append(source)
    return deduped[:16]
