from __future__ import annotations

import base64
import os
import re
from datetime import datetime, timedelta, timezone
from typing import Any, Callable, Dict, List, Optional, Tuple

import httpx
from dotenv import load_dotenv

from database import get_connection, utc_now
from services.auth_service import get_stored_token
from services.candidate_service import (
    AUTO_SAVE_TYPES,
    blob_url_for_path,
    extract_candidate_data,
    raw_base_for_path,
    save_pair_candidates,
    should_scan_path,
)
from services.dedup_service import content_hash, get_existing_repo, infer_category, looks_like_forbidden_resource, normalize_github_url
from services.prompt_service import build_cn_explanation, default_effect_review, extract_prompt_candidates, extract_prompt_effect_pairs, extract_prompt_video_pairs, infer_scenario
from services.repo_discovery_filter import evaluate_repo_discovery_candidate
from utils.image_utils import download_image, download_video_preview, extract_markdown_image_urls


load_dotenv()
load_dotenv(os.path.join(os.path.dirname(__file__), "..", ".env"))


GITHUB_API = "https://api.github.com"
REPORT_PATH = os.path.join(os.path.dirname(__file__), "..", "..", "exports", "daily_report.md")
# Negative terms in GitHub repository search can collapse useful results unexpectedly.
# Keep safety filtering in looks_like_forbidden_resource() after fetching candidates.
SEARCH_EXCLUDES = ""
MAX_PER_KEYWORD_LIMIT = 50
DISCOVERY_TRIGGER_MIN_RESULTS = 5
DISCOVERY_CATEGORIES = {
    "web_ui_prompt",
    "image_generation_prompt",
    "skill_repository",
    "video_generation_prompt",
}


def get_github_token() -> Optional[str]:
    return get_stored_token()


def search_start(last_success_search_at: Optional[str], overlap_days: int) -> str:
    if last_success_search_at:
        try:
            dt = datetime.fromisoformat(last_success_search_at.replace("Z", "+00:00"))
        except ValueError:
            dt = datetime.now(timezone.utc) - timedelta(days=overlap_days)
    else:
        dt = datetime.now(timezone.utc) - timedelta(days=30)
    return (dt - timedelta(days=overlap_days)).date().isoformat()


def headers(token: Optional[str]) -> Dict[str, str]:
    base = {
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
        "User-Agent": "visual-prompt-library",
    }
    if token:
        base["Authorization"] = f"Bearer {token}"
    return base


def _build_search_query(keyword: str, qualifier: str, start: str) -> str:
    clean = " ".join(keyword.strip().split())
    phrase = f'"{clean}"' if " " in clean else clean
    return f"{phrase} in:name,description,topics fork:false archived:false {qualifier}:>={start}"


def _build_fallback_search_query(keyword: str, qualifier: str, start: str) -> str:
    clean = " ".join(keyword.strip().split())
    return f"{clean} in:name,description,topics fork:false archived:false {qualifier}:>={start}"


def _build_discovery_search_query(keyword: str) -> str:
    clean = " ".join(keyword.strip().split())
    return f"{clean} in:name,description,topics fork:false archived:false"


def _license_from_item_or_readme(item: Dict[str, Any], readme: str) -> str:
    license_info = item.get("license") or {}
    license_value = (license_info.get("spdx_id") if isinstance(license_info, dict) else None) or "unknown"
    if license_value and license_value.upper() not in {"NOASSERTION", "UNKNOWN"}:
        return license_value

    lower = (readme or "").lower()
    if "cc by 4.0" in lower or "creative commons attribution 4.0" in lower:
        return "CC-BY-4.0"
    if "mit license" in lower:
        return "MIT"
    if "apache license" in lower and "2.0" in lower:
        return "Apache-2.0"
    return license_value or "unknown"


async def _get_readme(client: httpx.AsyncClient, full_name: str) -> str:
    try:
        response = await client.get(f"{GITHUB_API}/repos/{full_name}/readme")
    except httpx.HTTPError:
        return ""
    if response.status_code >= 400:
        return ""
    data = response.json()
    content = data.get("content") or ""
    if data.get("encoding") == "base64":
        try:
            return base64.b64decode(content).decode("utf-8", errors="ignore")
        except Exception:
            return ""
    return content


def _filename(path: str) -> str:
    return path.replace("\\", "/").split("/")[-1]


def _natural_path_key(path: str) -> List[Any]:
    return [int(part) if part.isdigit() else part for part in re.split(r"(\d+)", path.lower())]


def _scan_file_priority(path: str) -> Tuple[int, List[Any]]:
    lowered = path.replace("\\", "/").lower()
    suffix = os.path.splitext(lowered)[1]
    if suffix in {".md", ".mdx"}:
        return (0, _natural_path_key(lowered))
    if suffix in {".json", ".jsonl", ".csv", ".yaml", ".yml"}:
        return (1, _natural_path_key(lowered))
    if lowered.startswith(("examples/", "prompts/", "samples/", "docs/")):
        return (2, _natural_path_key(lowered))
    return (3, _natural_path_key(lowered))


async def _get_repo_documents(client: httpx.AsyncClient, item: Dict[str, Any], readme: str, max_documents: Optional[int] = None) -> List[Dict[str, str]]:
    owner = item.get("owner", {}).get("login") or ""
    repo_name = item.get("name") or ""
    full_name = item.get("full_name") or f"{owner}/{repo_name}"
    branch = item.get("default_branch") or "HEAD"
    documents: List[Dict[str, str]] = []
    seen_paths: set[str] = set()

    if readme:
        documents.append(
            {
                "path": "README.md",
                "content": readme,
                "raw_base_url": raw_base_for_path(owner, repo_name, branch, "README.md"),
                "source_page_url": blob_url_for_path(owner, repo_name, branch, "README.md"),
            }
        )
        seen_paths.add("readme.md")

    try:
        tree_response = await client.get(f"{GITHUB_API}/repos/{full_name}/git/trees/{branch}", params={"recursive": "1"})
    except httpx.HTTPError:
        return documents
    if tree_response.status_code >= 400:
        return documents

    file_entries = []
    for entry in tree_response.json().get("tree", []):
        path = entry.get("path") or ""
        if entry.get("type") != "blob" or not should_scan_path(path):
            continue
        if path.lower() in seen_paths:
            continue
        size = int(entry.get("size") or 0)
        if size <= 0 or size > 500_000:
            continue
        file_entries.append(entry)
    file_entries.sort(key=lambda entry: _scan_file_priority(entry.get("path") or ""))

    selected_entries = file_entries
    if max_documents is not None:
        remaining_slots = max(0, int(max_documents) - len(documents))
        selected_entries = file_entries[:remaining_slots]

    for entry in selected_entries:
        path = entry.get("path") or ""
        try:
            blob_response = await client.get(entry.get("url"))
        except httpx.HTTPError:
            continue
        if blob_response.status_code >= 400:
            continue
        blob = blob_response.json()
        if blob.get("encoding") != "base64":
            continue
        try:
            file_content = base64.b64decode(blob.get("content") or "").decode("utf-8", errors="ignore")
        except Exception:
            continue
        if not file_content.strip():
            continue
        documents.append(
            {
                "path": path,
                "content": file_content,
                "raw_base_url": raw_base_for_path(owner, repo_name, branch, path),
                "source_page_url": blob_url_for_path(owner, repo_name, branch, path),
            }
        )
        seen_paths.add(path.lower())
    return documents


def _repo_record(
    item: Dict[str, Any],
    keyword: str,
    category: str,
    readme: str,
    documents: Optional[List[Dict[str, str]]] = None,
    template: Optional[Dict[str, Any]] = None,
    progress_callback: Optional[Callable[[Dict[str, Any]], None]] = None,
) -> Dict[str, Any]:
    owner = item.get("owner", {}).get("login") or ""
    repo_name = item.get("name") or ""
    repo_url = item.get("html_url") or f"https://github.com/{owner}/{repo_name}"
    canonical_url = normalize_github_url(repo_url) or repo_url
    now = utc_now()
    raw_base_url = f"https://raw.githubusercontent.com/{owner}/{repo_name}/HEAD/"
    if not documents:
        documents = [{"path": "README.md", "content": readme, "raw_base_url": raw_base_url, "source_page_url": repo_url}]
    extracted = extract_candidate_data(documents, category, template=template, progress_callback=progress_callback)
    preview_images = extracted["preview_images"] or extract_markdown_image_urls(readme, base_url=raw_base_url)
    prompt_candidates = extracted["prompt_candidates"] or extract_prompt_candidates(readme, limit=8)
    pair_candidates = extracted["pair_candidates"] or (
        extract_prompt_video_pairs(readme, base_url=raw_base_url, source_page_url=repo_url, limit=10_000)
        if category == "video_generation_prompt"
        else extract_prompt_effect_pairs(readme, base_url=raw_base_url, source_page_url=repo_url, limit=10_000)
    )
    scanned_files = [document["path"] for document in documents]
    combined_content = "\n".join(document["content"] for document in documents)
    return {
        "repo_name": repo_name,
        "owner": owner,
        "repo_url": repo_url,
        "canonical_url": canonical_url,
        "stars": int(item.get("stargazers_count") or 0),
        "forks": int(item.get("forks_count") or 0),
        "license": _license_from_item_or_readme(item, readme),
        "is_fork": 1 if item.get("fork") else 0,
        "parent_repo": None,
        "resource_type": "github_repo",
        "category": category,
        "quality_level": "pending_review",
        "status": "pending_review",
        "summary": item.get("description") or f"由关键词 {keyword} 检索到的候选视觉 Prompt 资源。",
        "local_note_path": None,
        "content_hash": content_hash(combined_content or readme or item.get("description") or repo_url),
        "has_preview_images": 1 if preview_images else 0,
        "has_prompt_effect_pairs": 1 if pair_candidates else 0,
        "prompt_effect_pair_count": 0,
        "duplicate_of": None,
        "similar_to": None,
        "last_checked_at": now,
        "last_updated_at": item.get("pushed_at"),
        "created_at": now,
        "notes": f"搜索关键词：{keyword}；扫描文件：{len(scanned_files)}；Prompt 候选：{len(prompt_candidates)}；图片候选：{len(preview_images)}；配对候选：{len(pair_candidates)}",
        "_preview_images": preview_images,
        "_prompt_candidates": prompt_candidates,
        "_pair_candidates": pair_candidates,
        "_scanned_files": scanned_files,
    }


def _repo_discovery_record(item: Dict[str, Any], keyword: str, category: str, readme: str, evaluation: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    owner = item.get("owner", {}).get("login") or ""
    repo_name = item.get("name") or ""
    repo_url = item.get("html_url") or f"https://github.com/{owner}/{repo_name}"
    canonical_url = normalize_github_url(repo_url) or repo_url
    now = utc_now()
    raw_base_url = f"https://raw.githubusercontent.com/{owner}/{repo_name}/HEAD/"
    preview_images = extract_markdown_image_urls(readme, base_url=raw_base_url)
    description = item.get("description") or ""
    evaluation = evaluation or evaluate_repo_discovery_candidate(item, keyword, category, readme)
    breakdown = evaluation.get("breakdown") or {}
    reason_lines = "；".join((evaluation.get("reasons") or [])[:6])
    return {
        "repo_name": repo_name,
        "owner": owner,
        "repo_url": repo_url,
        "canonical_url": canonical_url,
        "stars": int(item.get("stargazers_count") or 0),
        "forks": int(item.get("forks_count") or 0),
        "license": _license_from_item_or_readme(item, readme),
        "is_fork": 1 if item.get("fork") else 0,
        "parent_repo": None,
        "resource_type": "github_repo",
        "category": category,
        "quality_level": evaluation.get("quality_level") or "pending_review",
        "status": evaluation.get("status") or "discovery_review",
        "summary": description or f"由关键词 {keyword} 发现的候选视觉 Prompt 仓库，待进入资源库扫描。",
        "local_note_path": None,
        "content_hash": content_hash(readme or description or repo_url),
        "has_preview_images": 1 if preview_images else 0,
        "has_prompt_effect_pairs": 0,
        "prompt_effect_pair_count": 0,
        "duplicate_of": None,
        "similar_to": None,
        "last_checked_at": now,
        "last_updated_at": item.get("pushed_at"),
        "created_at": now,
        "notes": (
            f"GitHub 仓库发现：关键词 {keyword}；分类 {category}；"
            f"README 长度 {len(readme or '')}；候选预览图 {len(preview_images)}。"
            f"发现分数 {evaluation.get('score', 0)}/100；结论：{evaluation.get('reason', '')}。"
            f"分项：Prompt 密度 {breakdown.get('prompt_density', 0)}，目标相关性 {breakdown.get('target_relevance', 0)}，"
            f"证据质量 {breakdown.get('evidence_quality', 0)}，复用价值 {breakdown.get('reusable_value', 0)}，仓库健康度 {breakdown.get('repo_health', 0)}。"
            f"主要证据：{reason_lines}。"
            "此阶段只写入资源库，不扫描仓库内部 Prompt/图片；请在资源库页面执行扫描。"
        ),
        "_preview_images": preview_images,
        "_prompt_candidates": [],
        "_pair_candidates": [],
        "_scanned_files": ["README.md"] if readme else [],
    }


def _insert_or_update_repo(conn, record: Dict[str, Any]) -> Tuple[str, int]:
    existing = get_existing_repo(record["canonical_url"])
    fields = [
        "repo_name",
        "owner",
        "repo_url",
        "canonical_url",
        "stars",
        "forks",
        "license",
        "is_fork",
        "parent_repo",
        "resource_type",
        "category",
        "quality_level",
        "status",
        "summary",
        "local_note_path",
        "content_hash",
        "has_preview_images",
        "has_prompt_effect_pairs",
        "prompt_effect_pair_count",
        "duplicate_of",
        "similar_to",
        "last_checked_at",
        "last_updated_at",
        "created_at",
        "notes",
    ]
    if existing:
        changed = existing.get("content_hash") != record["content_hash"]
        conn.execute(
            """
            UPDATE repos
            SET stars = ?,
                forks = ?,
                license = ?,
                last_checked_at = ?,
                last_updated_at = ?,
                has_preview_images = ?,
                content_hash = ?,
                notes = CASE WHEN ? THEN COALESCE(notes, '') || char(10) || ? ELSE notes END
            WHERE canonical_url = ?
            """,
            (
                record["stars"],
                record["forks"],
                record["license"],
                record["last_checked_at"],
                record["last_updated_at"],
                record["has_preview_images"],
                record["content_hash"],
                1 if changed else 0,
                f"内容在 {record['last_checked_at']} 发生变化，已追加更新记录。",
                record["canonical_url"],
            ),
        )
        return "updated", int(existing["id"])

    cursor = conn.execute(
        f"INSERT INTO repos ({', '.join(fields)}) VALUES ({', '.join('?' for _ in fields)})",
        tuple(record[field] for field in fields),
    )
    return "new", int(cursor.lastrowid)


async def _save_pairs_and_images(conn, repo_id: int, record: Dict[str, Any], progress_callback: Optional[Callable[[Dict[str, Any]], None]] = None) -> Tuple[int, int]:
    candidates = record.get("_pair_candidates") or []
    saved = 0
    images_added = 0
    category = record["category"]

    for candidate in candidates:
        if candidate.relation_type not in AUTO_SAVE_TYPES or candidate.confidence < 85:
            continue
        if progress_callback:
            progress_callback({"current_file": candidate.source_file, "phase": "download_effect_image"})
        asset_existing = conn.execute("SELECT * FROM assets WHERE image_original_url = ?", (candidate.image_url,)).fetchone()
        asset = None
        if not asset_existing:
            asset = await download_image(candidate.image_url)
            if not asset and category == "video_generation_prompt":
                asset = await download_video_preview(candidate.image_url)
            if not asset:
                if progress_callback:
                    progress_callback({"error_count_delta": 1})
                continue
            asset_existing = conn.execute("SELECT * FROM assets WHERE image_hash = ?", (asset["image_hash"],)).fetchone()

        if asset_existing:
            image_local_path = asset_existing["image_local_path"]
            thumbnail_local_path = asset_existing["thumbnail_local_path"]
            image_hash = asset_existing["image_hash"]
        else:
            if not asset:
                continue
            image_local_path = asset["image_local_path"]
            thumbnail_local_path = asset["thumbnail_local_path"]
            image_hash = asset["image_hash"]
            conn.execute(
                """
                INSERT OR IGNORE INTO assets
                    (repo_id, image_original_url, image_local_path, thumbnail_local_path, image_hash, source_page_url,
                     asset_type, width, height, file_size, description, commercial_risk, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    repo_id,
                    candidate.image_url,
                    image_local_path,
                    thumbnail_local_path,
                    asset["image_hash"],
                    candidate.source_page_url,
                    "effect_image",
                    asset["width"],
                    asset["height"],
                    asset["file_size"],
                    f"通过严格邻近上下文识别的 Prompt 效果图候选；关系：{candidate.relation_type}",
                    "unknown",
                    utc_now(),
                ),
            )
            images_added += 1
            if progress_callback:
                progress_callback({"downloaded_images_delta": 1, "images_added": images_added})

        duplicate_pair = conn.execute(
            """
            SELECT id FROM prompt_effect_pairs
            WHERE repo_id = ? AND image_hash = ? AND original_prompt = ?
            """,
            (repo_id, image_hash, candidate.prompt),
        ).fetchone()
        if duplicate_pair:
            continue

        now = utc_now()
        review = f"{default_effect_review(True, candidate.relation_type, category)}\n证据：{candidate.evidence}"
        conn.execute(
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
                repo_id,
                record["repo_name"],
                record["repo_url"],
                candidate.source_page_url,
                candidate.prompt,
                build_cn_explanation(candidate.prompt, category),
                candidate.image_url,
                image_local_path,
                image_hash,
                category,
                category,
                infer_scenario(category, candidate.prompt),
                "待人工整理",
                "pending_review",
                "pending_review",
                review,
                "存在 Prompt 与效果图的上下文证据，但仍需人工复核后再进入精选库。",
                record["license"],
                "unknown",
                candidate.relation_type,
                candidate.evidence,
                candidate.confidence,
                "github_incremental_search_strict_v2",
                None,
                now,
                now,
            ),
        )
        saved += 1

    pair_count = conn.execute("SELECT COUNT(*) FROM prompt_effect_pairs WHERE repo_id = ?", (repo_id,)).fetchone()[0]
    conn.execute(
        """
        UPDATE repos
        SET has_prompt_effect_pairs = CASE WHEN ? > 0 THEN 1 ELSE 0 END,
            prompt_effect_pair_count = ?
        WHERE id = ?
        """,
        (pair_count, pair_count, repo_id),
    )
    return saved, images_added


async def _save_candidate_images(conn, repo_id: int, record: Dict[str, Any], limit: int = 8) -> int:
    urls = record.get("_preview_images") or []
    saved = 0
    for image_url in urls[:limit]:
        asset = await download_image(image_url)
        if not asset:
            continue
        asset_existing = conn.execute("SELECT id FROM assets WHERE image_hash = ?", (asset["image_hash"],)).fetchone()
        if asset_existing:
            continue
        conn.execute(
            """
            INSERT OR IGNORE INTO assets
                (repo_id, image_original_url, image_local_path, thumbnail_local_path, image_hash, source_page_url,
                 asset_type, width, height, file_size, description, commercial_risk, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                repo_id,
                image_url,
                asset["image_local_path"],
                asset["thumbnail_local_path"],
                asset["image_hash"],
                record["repo_url"],
                "candidate_image",
                asset["width"],
                asset["height"],
                asset["file_size"],
                "README 中解析到的候选效果图，尚未通过 Prompt + 效果图严格配对证据校验。",
                "unknown",
                utc_now(),
            ),
        )
        saved += 1
    return saved


async def run_incremental_search(categories: Optional[List[str]], keywords: Optional[List[str]], per_keyword_limit: int, allow_anonymous: bool = False) -> Dict[str, Any]:
    token = get_github_token()
    if not token and not allow_anonymous:
        now = utc_now()
        report = {
            "status": "needs_token",
            "summary": "未连接 GitHub，也未检测到 GITHUB_TOKEN/GH_TOKEN。请先在 UI 中完成 GitHub 授权；本次没有执行搜索，也没有推进 search_state。",
            "new": [],
            "updated": [],
            "duplicates": [],
            "skipped": [],
            "pending_review": [],
            "discovery_review": [],
        }
        write_daily_report(report)
        with get_connection() as conn:
            conn.execute(
                """
                INSERT INTO search_logs
                    (search_date, keyword, search_type, result_count, new_count, updated_count, duplicate_count,
                     skipped_count, pending_review_count, summary, created_at)
                VALUES (?, ?, ?, 0, 0, 0, 0, 0, 0, ?, ?)
                """,
                (now[:10], "all", "incremental_github", report["summary"], now),
            )
        return report

    per_keyword_limit = min(max(per_keyword_limit, 1), MAX_PER_KEYWORD_LIMIT)
    with get_connection() as conn:
        states = conn.execute("SELECT * FROM search_state WHERE status = 'active'").fetchall()
        state_rows = [dict(row) for row in states]

    if not categories and not keywords:
        categories = sorted(DISCOVERY_CATEGORIES)
    if categories:
        category_set = {category for category in categories if category in DISCOVERY_CATEGORIES}
        state_rows = [row for row in state_rows if row["category"] in category_set]
    if keywords:
        keyword_set = {keyword.lower() for keyword in keywords}
        existing_keyword_set = {row["keyword"].lower() for row in state_rows}
        state_rows = [row for row in state_rows if row["keyword"].lower() in keyword_set]
        for keyword in keywords:
            if keyword.lower() not in existing_keyword_set:
                state_rows.append(
                    {
                        "keyword": keyword,
                        "category": categories[0] if categories and len(categories) == 1 else infer_category(keyword),
                        "last_success_search_at": None,
                        "safety_overlap_days": 3,
                        "last_result_count": 0,
                    }
                )
    report: Dict[str, Any] = {
        "status": "ok",
        "summary": "",
        "new": [],
        "updated": [],
        "duplicates": [],
        "skipped": [],
        "pending_review": [],
        "discovery_review": [],
        "prompt_pairs_added": 0,
        "images_added": 0,
        "candidate_images_added": 0,
        "pair_candidates_added": 0,
        "discovery_results": 0,
        "github_total_count": 0,
    }
    now = utc_now()
    async with httpx.AsyncClient(timeout=30, headers=headers(token), follow_redirects=True, trust_env=False) as client:
        for state in state_rows:
            keyword = state["keyword"]
            category = state["category"] or infer_category(keyword)
            start = search_start(state.get("last_success_search_at"), int(state.get("safety_overlap_days") or 3))
            # 定时/手动 GitHub 搜索只发现仓库。Prompt、图片和配对证据只能由资源库扫描流程产生。
            query_types = [
                ("created", "created", _build_search_query(keyword, "created", start)),
                ("pushed", "pushed", _build_search_query(keyword, "pushed", start)),
                ("discovery", "discovery", _build_discovery_search_query(keyword)),
            ]
            keyword_ok = True
            counts = {"result": 0, "github_total": 0, "discovery": 0, "new": 0, "updated": 0, "duplicate": 0, "skipped": 0, "pending": 0}
            seen_repo_keys: set[str] = set()

            for search_type, qualifier, query in query_types:
                sort_key = "stars" if search_type == "discovery" else "updated"
                try:
                    response = await client.get(
                        f"{GITHUB_API}/search/repositories",
                        params={"q": query, "sort": sort_key, "order": "desc", "per_page": per_keyword_limit},
                    )
                except httpx.HTTPError as exc:
                    keyword_ok = False
                    report["skipped"].append({"repo": keyword, "reason": f"GitHub 网络请求失败：{exc}"})
                    counts["skipped"] += 1
                    continue

                if response.status_code == 422 and qualifier in {"created", "pushed"}:
                    fallback_query = _build_fallback_search_query(keyword, qualifier, start)
                    try:
                        response = await client.get(
                            f"{GITHUB_API}/search/repositories",
                            params={"q": fallback_query, "sort": sort_key, "order": "desc", "per_page": per_keyword_limit},
                        )
                    except httpx.HTTPError as exc:
                        keyword_ok = False
                        report["skipped"].append({"repo": keyword, "reason": f"GitHub 回退搜索网络请求失败：{exc}"})
                        counts["skipped"] += 1
                        continue

                if response.status_code >= 400:
                    if qualifier != "discovery":
                        keyword_ok = False
                    report["skipped"].append({"repo": keyword, "reason": f"GitHub API 返回 HTTP {response.status_code}"})
                    counts["skipped"] += 1
                    continue

                data = response.json()
                items = data.get("items", [])
                counts["github_total"] += int(data.get("total_count") or 0)
                if search_type == "discovery":
                    counts["discovery"] += len(items)
                    report["discovery_results"] += len(items)
                if not items and qualifier in {"created", "pushed"}:
                    fallback_query = _build_fallback_search_query(keyword, qualifier, start)
                    try:
                        fallback_response = await client.get(
                            f"{GITHUB_API}/search/repositories",
                            params={"q": fallback_query, "sort": sort_key, "order": "desc", "per_page": per_keyword_limit},
                        )
                    except httpx.HTTPError as exc:
                        keyword_ok = False
                        report["skipped"].append({"repo": keyword, "reason": f"GitHub 空结果回退搜索失败：{exc}"})
                        counts["skipped"] += 1
                        continue
                    if fallback_response.status_code < 400:
                        fallback_data = fallback_response.json()
                        items = fallback_data.get("items", [])
                        counts["github_total"] += int(fallback_data.get("total_count") or 0)
                counts["result"] += len(items)
                for item in items:
                    name = item.get("full_name") or item.get("name") or ""
                    canonical_key = normalize_github_url(item.get("html_url") or "") or name.lower()
                    if canonical_key in seen_repo_keys:
                        report["duplicates"].append({"repo": name, "reason": f"同一关键词在 {search_type} 搜索中重复命中，已复用首次结果"})
                        counts["duplicate"] += 1
                        continue
                    seen_repo_keys.add(canonical_key)
                    if looks_like_forbidden_resource(name, item.get("description") or ""):
                        report["skipped"].append({"repo": name, "reason": "命中禁止整理关键词"})
                        counts["skipped"] += 1
                        continue
                    if item.get("fork"):
                        report["skipped"].append({"repo": name, "reason": "Fork 仓库，默认跳过独立保存"})
                        counts["skipped"] += 1
                        continue

                    readme = await _get_readme(client, name)
                    if looks_like_forbidden_resource(name, f"{item.get('description') or ''} {readme[:12000]}"):
                        report["skipped"].append({"repo": name, "reason": "README 命中禁止整理关键词"})
                        counts["skipped"] += 1
                        continue

                    evaluation = evaluate_repo_discovery_candidate(item, keyword, category, readme)
                    if evaluation.get("decision") == "skip":
                        report["skipped"].append(
                            {
                                "repo": name,
                                "reason": f"{evaluation.get('reason', '发现评分未通过')}；分数 {evaluation.get('score', 0)}/100",
                            }
                        )
                        counts["skipped"] += 1
                        continue

                    record = _repo_discovery_record(item, keyword, category, readme, evaluation=evaluation)

                    with get_connection() as conn:
                        action, repo_id = _insert_or_update_repo(conn, record)

                    if action == "new":
                        report["new"].append(record["canonical_url"])
                        counts["new"] += 1
                    else:
                        report["updated"].append(record["canonical_url"])
                        counts["updated"] += 1
                    if record["status"] == "discovery_review":
                        report["discovery_review"].append(record["canonical_url"])
                        report["pending_review"].append(record["canonical_url"])
                        counts["pending"] += 1
                    elif record["status"] == "pending_review":
                        report["pending_review"].append(record["canonical_url"])
                        counts["pending"] += 1

            report["github_total_count"] += counts["github_total"]
            with get_connection() as conn:
                conn.execute(
                    """
                    INSERT INTO search_logs
                        (search_date, keyword, search_type, result_count, new_count, updated_count, duplicate_count,
                         skipped_count, pending_review_count, summary, created_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        now[:10],
                        keyword,
                        "incremental_github",
                        counts["result"],
                        counts["new"],
                        counts["updated"],
                        counts["duplicate"],
                        counts["skipped"],
                        counts["pending"],
                        f"搜索窗口起点：{start}；状态：{'成功' if keyword_ok else '部分失败'}；已按发现评分过滤仓库；仅发现 GitHub 仓库并写入资源库，仓库内容扫描在资源库页面执行。",
                        now,
                    ),
                )
                if keyword_ok:
                    conn.execute(
                        """
                        INSERT INTO search_state
                            (keyword, category, last_success_search_at, safety_overlap_days, last_result_count, status, updated_at)
                        VALUES (?, ?, ?, ?, ?, 'active', ?)
                        ON CONFLICT(keyword) DO UPDATE SET
                            category = excluded.category,
                            last_success_search_at = excluded.last_success_search_at,
                            last_result_count = excluded.last_result_count,
                            updated_at = excluded.updated_at
                        """,
                        (keyword, category, now, int(state.get("safety_overlap_days") or 3), counts["result"], now),
                    )

    report["summary"] = (
        f"仓库发现完成：新增仓库 {len(report['new'])}，更新仓库 {len(report['updated'])}，跳过 {len(report['skipped'])}，"
        f"重复 {len(report['duplicates'])}，待观察 {len(report['discovery_review'])}，待复查 {len(report['pending_review'])}；"
        f"GitHub total_count 合计 {report.get('github_total_count', 0)}，发现补扫返回 {report.get('discovery_results', 0)}；"
        "本阶段不会写入 Prompt 库或图片候选；请在资源库页面扫描仓库内容。"
    )
    write_daily_report(report)
    return report


def write_daily_report(report: Dict[str, Any]) -> None:
    path = os.path.abspath(REPORT_PATH)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    lines = [
        "# 每日视觉 Prompt 资源检索报告",
        "",
        f"- 生成时间：{utc_now()}",
        f"- 本次摘要：{report.get('summary') or report.get('status')}",
        f"- 新增资源：{len(report.get('new', []))}",
        f"- 更新资源：{len(report.get('updated', []))}",
        f"- 跳过资源：{len(report.get('skipped', []))}",
        f"- 重复资源：{len(report.get('duplicates', []))}",
        f"- 待观察仓库：{len(report.get('discovery_review', []))}",
        "- 相似资源：0",
        "- 新增 Prompt 效果对：0（仓库发现阶段不扫描仓库内容）",
        "- 新增配对候选：0（仓库发现阶段不扫描仓库内容）",
        "- 新增图片：0（仓库发现阶段不下载图片）",
        "- 新增候选图：0（仓库发现阶段不下载图片）",
        f"- 待人工复查：{len(report.get('pending_review', []))}",
        "",
        "## 新增资源",
        "",
        *[f"- {item}" for item in report.get("new", [])],
        "",
        "## 更新资源",
        "",
        *[f"- {item}" for item in report.get("updated", [])],
        "",
        "## 待观察仓库",
        "",
        *[f"- {item}" for item in report.get("discovery_review", [])],
        "",
        "## 跳过资源",
        "",
        *[f"- {item.get('repo', item)}：{item.get('reason', '')}" if isinstance(item, dict) else f"- {item}" for item in report.get("skipped", [])],
        "",
        "## 待复查资源",
        "",
        *[f"- {item}" for item in report.get("pending_review", [])],
        "",
        "## 今日最有价值发现",
        "",
        "本报告只统计 GitHub 仓库发现结果。Prompt、图片、配对候选与效果对只能通过资源库页面的仓库扫描流程产生。",
        "",
    ]
    with open(path, "w", encoding="utf-8") as fp:
        fp.write("\n".join(lines))
