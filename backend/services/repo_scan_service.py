from __future__ import annotations

import fnmatch
import json
from typing import Any, Dict, Optional
from pathlib import PurePosixPath
from urllib.parse import urlparse

import httpx

from database import fetch_one, get_connection, utc_now
from agents.repo_template_graph import generate_template_from_scan, get_active_template, get_template, validate_template_content
from services.auth_service import get_stored_token
from services.candidate_service import save_pair_candidates
from services.dedup_service import infer_category, normalize_github_url
from services.github_search_service import (
    GITHUB_API,
    _get_readme,
    _get_repo_documents,
    _insert_or_update_repo,
    _repo_record,
    _save_pairs_and_images,
    headers,
)
from services.ai_pair_assist_service import assist_record_pair_candidates


class RepoScanError(Exception):
    def __init__(self, status_code: int, detail: str):
        super().__init__(detail)
        self.status_code = status_code
        self.detail = detail


class RepoScanCancelled(Exception):
    pass


def _run_id_from_options(options: Optional[Dict[str, Any]]) -> Optional[int]:
    if not options:
        return None
    value = options.get("_run_id")
    try:
        return int(value) if value else None
    except (TypeError, ValueError):
        return None


def _run_status_done(status: str) -> str:
    if status == "failed":
        return "failed"
    if status == "canceled":
        return "canceled"
    return "succeeded"


def _update_scan_run(run_id: Optional[int], **fields: Any) -> None:
    if not run_id or not fields:
        return
    allowed = {
        "status",
        "progress_percent",
        "current_file",
        "total_files",
        "processed_files",
        "total_images",
        "downloaded_images",
        "error_count",
        "scanned_files",
        "prompt_candidates",
        "pair_candidates",
        "prompt_pairs_added",
        "pair_candidates_added",
        "images_added",
        "summary",
        "error",
        "result_json",
        "started_at",
        "finished_at",
        "updated_at",
        "cancel_requested",
        "template_id",
    }
    payload = {key: value for key, value in fields.items() if key in allowed}
    if not payload:
        return
    payload["updated_at"] = payload.get("updated_at") or utc_now()
    assignments = ", ".join(f"{key} = ?" for key in payload)
    with get_connection() as conn:
        conn.execute(f"UPDATE repo_scan_runs SET {assignments} WHERE id = ?", (*payload.values(), run_id))


def _check_scan_cancel(run_id: Optional[int]) -> None:
    if not run_id:
        return
    row = fetch_one("SELECT cancel_requested, status FROM repo_scan_runs WHERE id = ?", (run_id,))
    if row and (row.get("cancel_requested") or row.get("status") == "cancel_requested"):
        raise RepoScanCancelled("扫描已取消")


def _progress_callback(run_id: Optional[int]):
    counters = {"downloaded_images": 0, "error_count": 0}

    def callback(event: Dict[str, Any]) -> None:
        _check_scan_cancel(run_id)
        update: Dict[str, Any] = {}
        if event.get("downloaded_images_delta"):
            counters["downloaded_images"] += int(event.get("downloaded_images_delta") or 0)
            update["downloaded_images"] = counters["downloaded_images"]
        if event.get("error_count_delta"):
            counters["error_count"] += int(event.get("error_count_delta") or 0)
            update["error_count"] = counters["error_count"]
        for key in ("status", "progress_percent", "current_file", "total_files", "processed_files", "total_images", "prompt_candidates", "pair_candidates", "images_added"):
            if key in event:
                update[key] = event[key]
        total_files = int(update.get("total_files") or event.get("total_files") or 0)
        processed_files = int(update.get("processed_files") or event.get("processed_files") or 0)
        if total_files:
            update["progress_percent"] = max(1, min(95, int(processed_files * 70 / total_files)))
        if update:
            _update_scan_run(run_id, **update)

    return callback


def _transaction_progress_callback(run_id: Optional[int], conn):
    counters = {"downloaded_images": 0, "error_count": 0}

    def callback(event: Dict[str, Any]) -> None:
        if run_id:
            row = conn.execute("SELECT cancel_requested, status FROM repo_scan_runs WHERE id = ?", (run_id,)).fetchone()
            if row and (row["cancel_requested"] or row["status"] == "cancel_requested"):
                raise RepoScanCancelled("扫描已取消")
        update: Dict[str, Any] = {}
        if event.get("downloaded_images_delta"):
            counters["downloaded_images"] += int(event.get("downloaded_images_delta") or 0)
            update["downloaded_images"] = counters["downloaded_images"]
        if event.get("error_count_delta"):
            counters["error_count"] += int(event.get("error_count_delta") or 0)
            update["error_count"] = counters["error_count"]
        for key in ("current_file", "total_files", "processed_files", "total_images", "prompt_candidates", "pair_candidates", "images_added"):
            if key in event:
                update[key] = event[key]
        if not run_id or not update:
            return
        update["updated_at"] = utc_now()
        assignments = ", ".join(f"{key} = ?" for key in update)
        conn.execute(f"UPDATE repo_scan_runs SET {assignments} WHERE id = ?", (*update.values(), run_id))

    return callback


def _full_name_from_repo(repo: Dict[str, Any]) -> Optional[str]:
    owner = (repo.get("owner") or "").strip()
    repo_name = (repo.get("repo_name") or "").strip()
    if owner and repo_name:
        return f"{owner}/{repo_name}"

    normalized = normalize_github_url(repo.get("canonical_url") or repo.get("repo_url") or "")
    if not normalized:
        return None
    path = urlparse(normalized).path.strip("/")
    parts = path.split("/")
    if len(parts) >= 2:
        return f"{parts[0]}/{parts[1]}"
    return None


async def _load_repo_context(repo_id: int) -> tuple[Dict[str, Any], Dict[str, Any], str, list[Dict[str, str]], str]:
    repo = fetch_one("SELECT * FROM repos WHERE id = ?", (repo_id,))
    if not repo:
        raise RepoScanError(404, "资源不存在")

    token = get_stored_token()
    if not token:
        raise RepoScanError(401, "未连接 GitHub。请先完成 GitHub 授权后再扫描仓库。")

    repo_dict = dict(repo)
    full_name = _full_name_from_repo(repo_dict)
    if not full_name:
        raise RepoScanError(400, "仓库地址无法解析为 owner/repo")

    async with httpx.AsyncClient(timeout=30, headers=headers(token), follow_redirects=True, trust_env=False) as client:
        repo_response = await client.get(f"{GITHUB_API}/repos/{full_name}")
        if repo_response.status_code == 404:
            raise RepoScanError(404, "GitHub 仓库不存在或当前 Token 无权访问")
        if repo_response.status_code >= 400:
            raise RepoScanError(repo_response.status_code, f"GitHub API 返回 HTTP {repo_response.status_code}")

        item = repo_response.json()
        readme = await _get_readme(client, full_name)
        documents = await _get_repo_documents(client, item, readme)

    return repo_dict, item, readme, documents, full_name


def _scan_mode(options: Dict[str, Any]) -> str:
    mode = str(options.get("scan_mode") or "").strip()
    if mode in {"generic", "generate_ai_template", "template"}:
        return mode
    if options.get("use_ai") or options.get("generate_template"):
        return "generate_ai_template"
    if options.get("template_id"):
        return "template"
    return "generic"


def _load_template_content(template: Optional[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    if not template:
        return None
    try:
        payload = json.loads(template.get("content_json") or "{}")
    except Exception:
        return None
    try:
        return validate_template_content(payload)
    except Exception:
        return payload if isinstance(payload, dict) else None


def _matches_pattern(path: str, pattern: str) -> bool:
    clean_path = path.replace("\\", "/").strip("/")
    clean_pattern = pattern.replace("\\", "/").strip("/")
    if not clean_pattern:
        return False
    if clean_pattern == clean_path:
        return True
    if any(char in clean_pattern for char in "*?[]"):
        return fnmatch.fnmatchcase(clean_path, clean_pattern)
    if "." not in PurePosixPath(clean_pattern).name:
        return clean_path == clean_pattern or clean_path.startswith(f"{clean_pattern.rstrip('/')}/")
    return False


def _select_template_documents(documents: list[Dict[str, str]], template_content: Optional[Dict[str, Any]]) -> tuple[list[Dict[str, str]], int, int]:
    if not template_content:
        return documents, 0, 0
    primary_patterns = [str(item) for item in template_content.get("primary_target_files") or []]
    secondary_patterns = [str(item) for item in template_content.get("secondary_target_files") or []]

    primary: list[Dict[str, str]] = []
    secondary: list[Dict[str, str]] = []
    seen: set[str] = set()
    for document in documents:
        path = document.get("path") or ""
        if any(_matches_pattern(path, pattern) for pattern in primary_patterns):
            primary.append(document)
            seen.add(path.lower())

    for document in documents:
        path = document.get("path") or ""
        if path.lower() in seen:
            continue
        if any(_matches_pattern(path, pattern) for pattern in secondary_patterns):
            secondary.append(document)
            seen.add(path.lower())

    selected = primary + secondary
    return selected, len(primary), len(secondary)


def _record_scan_run(repo_id: int, result: Dict[str, Any], options: Optional[Dict[str, Any]], error: Optional[str] = None) -> None:
    now = utc_now()
    options = options or {}
    run_id = _run_id_from_options(options)
    final_status = _run_status_done(result.get("status") or ("failed" if error else "ok"))
    if run_id:
        _update_scan_run(
            run_id,
            status=final_status,
            progress_percent=100 if final_status == "succeeded" else result.get("progress_percent", 0),
            scanned_files=int(result.get("scanned_files") or 0),
            prompt_candidates=int(result.get("prompt_candidates") or 0),
            pair_candidates=int(result.get("pair_candidates") or 0),
            prompt_pairs_added=int(result.get("prompt_pairs_added") or 0),
            pair_candidates_added=int(result.get("pair_candidates_added") or 0),
            images_added=int(result.get("images_added") or 0),
            summary=result.get("summary"),
            error=error,
            result_json=json.dumps(result, ensure_ascii=False),
            template_id=result.get("template_id") or result.get("generated_template_id"),
            finished_at=now,
            updated_at=now,
        )
        return
    with get_connection() as conn:
        conn.execute(
            """
            INSERT INTO repo_scan_runs
                (repo_id, use_ai, template_id, status, scanned_files, prompt_candidates, pair_candidates,
                 prompt_pairs_added, pair_candidates_added, images_added, summary, error, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                repo_id,
                1 if options.get("use_ai") or options.get("generate_template") else 0,
                result.get("template_id") or result.get("generated_template_id"),
                final_status,
                int(result.get("scanned_files") or 0),
                int(result.get("prompt_candidates") or 0),
                int(result.get("pair_candidates") or 0),
                int(result.get("prompt_pairs_added") or 0),
                int(result.get("pair_candidates_added") or 0),
                int(result.get("images_added") or 0),
                result.get("summary"),
                error,
                now,
            ),
        )


async def generate_repo_template_for_repo(repo_id: int, ai_config_id: Optional[int] = None) -> Dict[str, Any]:
    repo_dict, item, readme, documents, full_name = await _load_repo_context(repo_id)
    if not documents:
        raise RepoScanError(400, "未发现可扫描文件，无法生成仓库扫描模板")
    category = repo_dict.get("category") or infer_category(full_name)
    record = _repo_record(item, "ai_template_generation", category, readme, documents)
    return await generate_template_from_scan(repo_dict, documents, record, ai_config_id=ai_config_id)


async def scan_repo_by_id(repo_id: int, options: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    options = options or {}
    run_id = _run_id_from_options(options)
    progress = _progress_callback(run_id)
    _check_scan_cancel(run_id)
    repo_dict, item, readme, documents, full_name = await _load_repo_context(repo_id)
    mode = _scan_mode(options)
    _update_scan_run(run_id, total_files=len(documents), current_file="GitHub 文件列表读取完成", progress_percent=1)

    if not documents:
        now = utc_now()
        with get_connection() as conn:
            conn.execute(
                """
                UPDATE repos
                SET last_checked_at = ?,
                    notes = COALESCE(notes, '') || char(10) || ?
                WHERE id = ?
                """,
                (now, f"手动扫描：未发现可扫描的 README/docs/examples/prompts 等文件。时间：{now}", repo_id),
            )
        result = {
            "status": "skipped",
            "repo_id": repo_id,
            "repo": full_name,
            "reason": "未发现可扫描文件",
            "scanned_files": 0,
            "prompt_candidates": 0,
            "pair_candidates": 0,
            "prompt_pairs_added": 0,
            "pair_candidates_added": 0,
            "images_added": 0,
        }
        _record_scan_run(repo_id, result, options)
        return result

    category = repo_dict.get("category") or infer_category(full_name)
    selected_template: Optional[Dict[str, Any]] = None
    generated_template: Optional[Dict[str, Any]] = None
    template_content: Optional[Dict[str, Any]] = None
    primary_target_count = 0
    secondary_target_count = 0
    template_fallback = False

    if options.get("template_id"):
        selected_template = get_template(int(options["template_id"]))
        if not selected_template or int(selected_template["repo_id"]) != repo_id:
            raise RepoScanError(400, "扫描模板不存在或不属于当前仓库")
    elif mode in {"generic", "template"}:
        selected_template = get_active_template(repo_id)

    if mode == "generate_ai_template":
        baseline_record = _repo_record(item, "manual_repo_scan", category, readme, documents, progress_callback=progress)
        try:
            _check_scan_cancel(run_id)
            generated_template = await generate_template_from_scan(
                repo_dict,
                documents,
                baseline_record,
                ai_config_id=options.get("ai_config_id"),
            )
        except Exception as exc:
            failed = {
                "status": "failed",
                "repo_id": repo_id,
                "repo": full_name,
                "scanned_files": len(baseline_record.get("_scanned_files") or []),
                "prompt_candidates": len(baseline_record.get("_prompt_candidates") or []),
                "pair_candidates": len(baseline_record.get("_pair_candidates") or []),
                "prompt_pairs_added": 0,
                "pair_candidates_added": 0,
                "images_added": 0,
                "summary": "AI 生成扫描模板失败，未写入正式 Prompt。",
            }
            _record_scan_run(repo_id, failed, options, error=str(exc))
            raise RepoScanError(400, f"AI 生成扫描模板失败：{exc}") from exc

        result = {
            "status": "ok",
            "repo_id": repo_id,
            "repo": full_name,
            "action": "template_generated",
            "scanned_files": len(baseline_record.get("_scanned_files") or []),
            "prompt_candidates": len(baseline_record.get("_prompt_candidates") or []),
            "pair_candidates": len(baseline_record.get("_pair_candidates") or []),
            "prompt_pairs_added": 0,
            "pair_candidates_added": 0,
            "images_added": 0,
            "has_strict_pairs": bool(baseline_record.get("_pair_candidates")),
            "use_ai": True,
            "scan_mode": mode,
            "template_id": generated_template["id"],
            "generated_template_id": generated_template["id"],
            "template_status": generated_template["status"],
            "template_preview": generated_template.get("summary_cn"),
            "primary_target_count": len((_load_template_content(generated_template) or {}).get("primary_target_files") or []),
            "secondary_target_count": len((_load_template_content(generated_template) or {}).get("secondary_target_files") or []),
            "estimated_pair_count": len(baseline_record.get("_pair_candidates") or []),
            "summary": f"AI 已生成待确认扫描模板 #{generated_template['id']}，本次未写入正式 Prompt 效果对。",
        }
        _record_scan_run(repo_id, result, options)
        return result

    if selected_template:
        template_content = _load_template_content(selected_template)

    record: Dict[str, Any]
    if template_content:
        template_documents, primary_target_count, secondary_target_count = _select_template_documents(documents, template_content)
        if template_documents:
            _update_scan_run(run_id, total_files=len(template_documents), current_file="按扫描模板选择文件", progress_percent=5)
            record = _repo_record(item, "template_repo_scan", category, readme, template_documents, template=template_content, progress_callback=progress)
            if not record.get("_pair_candidates"):
                template_fallback = True
                _update_scan_run(run_id, total_files=len(documents), current_file="模板无结果，回退通用扫描", progress_percent=5)
                baseline_record = _repo_record(item, "manual_repo_scan", category, readme, documents, progress_callback=progress)
                record = baseline_record
        else:
            template_fallback = True
            _update_scan_run(run_id, total_files=len(documents), current_file="模板未匹配文件，回退通用扫描", progress_percent=5)
            record = _repo_record(item, "manual_repo_scan", category, readme, documents, progress_callback=progress)
    else:
        record = _repo_record(item, "manual_repo_scan", category, readme, documents, progress_callback=progress)

    if options.get("use_ai") and mode != "generate_ai_template":
        _check_scan_cancel(run_id)
        _update_scan_run(run_id, progress_percent=70, current_file="Qwen 8B 辅助判断低置信复杂内容块")
        record = await assist_record_pair_candidates(record, ai_config_id=options.get("ai_config_id"))

    has_strict_pairs = bool(record.get("_pair_candidates"))
    now = utc_now()

    with get_connection() as conn:
        _check_scan_cancel(run_id)
        action, effective_repo_id = _insert_or_update_repo(conn, record)
        tx_progress = _transaction_progress_callback(run_id, conn)
        tx_progress({"progress_percent": 72, "current_file": "保存候选配对与图片"})
        pair_candidates_added, pair_candidate_images_added = await save_pair_candidates(conn, effective_repo_id, record, progress_callback=tx_progress) if has_strict_pairs else (0, 0)
        tx_progress({"progress_percent": 88, "current_file": "保存正式效果对"})
        prompt_pairs_added, strict_images_added = await _save_pairs_and_images(conn, effective_repo_id, record, progress_callback=tx_progress) if has_strict_pairs else (0, 0)
        pair_count = conn.execute("SELECT COUNT(*) FROM prompt_effect_pairs WHERE repo_id = ?", (effective_repo_id,)).fetchone()[0]
        conn.execute(
            """
            UPDATE repos
            SET has_prompt_effect_pairs = CASE WHEN ? > 0 THEN 1 ELSE 0 END,
                prompt_effect_pair_count = ?,
                last_checked_at = ?,
                notes = COALESCE(notes, '') || char(10) || ?
            WHERE id = ?
            """,
            (
                pair_count,
                pair_count,
                now,
                (
                    f"手动扫描：文件 {len(record.get('_scanned_files') or [])} 个，"
                    f"Prompt 候选 {len(record.get('_prompt_candidates') or [])} 个，"
                    f"配对候选 {len(record.get('_pair_candidates') or [])} 个，"
                    f"新增正式效果对 {prompt_pairs_added} 个。时间：{now}"
                    + (f"；使用扫描模板 #{selected_template['id']}（{selected_template['status']}）" if selected_template else "")
                    + ("；模板扫描无结果，已回退通用规则" if template_fallback else "")
                ),
                effective_repo_id,
            ),
        )

    result = {
        "status": "ok",
        "repo_id": effective_repo_id,
        "repo": full_name,
        "action": action,
        "scanned_files": len(record.get("_scanned_files") or []),
        "prompt_candidates": len(record.get("_prompt_candidates") or []),
        "pair_candidates": len(record.get("_pair_candidates") or []),
        "prompt_pairs_added": prompt_pairs_added,
        "pair_candidates_added": pair_candidates_added,
        "images_added": strict_images_added + pair_candidate_images_added,
        "has_strict_pairs": has_strict_pairs,
        "use_ai": False,
        "scan_mode": "template" if selected_template else mode,
        "template_id": selected_template["id"] if selected_template else None,
        "generated_template_id": generated_template["id"] if generated_template else None,
        "template_status": selected_template["status"] if selected_template else None,
        "template_preview": selected_template.get("summary_cn") if selected_template else None,
        "primary_target_count": primary_target_count,
        "secondary_target_count": secondary_target_count,
        "estimated_pair_count": len(record.get("_pair_candidates") or []),
        "ai_assisted_pairs": int(record.get("_ai_assisted_pairs") or 0),
        "ai_assist_error": record.get("_ai_assist_error"),
        "template_fallback": template_fallback,
        "summary": (
            f"扫描完成：文件 {len(record.get('_scanned_files') or [])} 个，配对候选 {len(record.get('_pair_candidates') or [])} 个。"
            + (f" 已生成待复查模板 #{generated_template['id']}。" if generated_template else "")
            + (f" 使用模板 #{selected_template['id']}。" if selected_template and not generated_template else "")
            + (f" Qwen 8B 辅助判断 {int(record.get('_ai_assisted_pairs') or 0)} 个低置信候选。" if record.get("_ai_assisted_pairs") else "")
            + (f" Qwen 辅助失败：{record.get('_ai_assist_error')}。" if record.get("_ai_assist_error") else "")
            + (" 模板无结果，已回退通用规则。" if template_fallback else "")
        ),
    }
    _record_scan_run(effective_repo_id, result, options)
    return result


async def scan_existing_repos(categories: Optional[list[str]] = None, limit: int = 20) -> Dict[str, Any]:
    where = ["1 = 1"]
    params: list[Any] = []
    if categories:
        placeholders = ", ".join("?" for _ in categories)
        where.append(f"category IN ({placeholders})")
        params.extend(categories)
    params.append(max(1, min(int(limit or 20), 50)))

    with get_connection() as conn:
        rows = conn.execute(
            f"""
            SELECT id, owner, repo_name
            FROM repos
            WHERE {' AND '.join(where)}
            ORDER BY COALESCE(last_checked_at, created_at) ASC, id ASC
            LIMIT ?
            """,
            tuple(params),
        ).fetchall()

    results = []
    failed = []
    totals = {
        "scanned_repos": 0,
        "prompt_pairs_added": 0,
        "pair_candidates_added": 0,
        "images_added": 0,
    }

    for row in rows:
        repo_id = int(row["id"])
        try:
            result = await scan_repo_by_id(repo_id)
        except RepoScanError as exc:
            failed.append({"repo_id": repo_id, "error": exc.detail})
            continue
        except Exception as exc:
            failed.append({"repo_id": repo_id, "error": str(exc)})
            continue
        results.append(result)
        totals["scanned_repos"] += 1
        totals["prompt_pairs_added"] += int(result.get("prompt_pairs_added") or 0)
        totals["pair_candidates_added"] += int(result.get("pair_candidates_added") or 0)
        totals["images_added"] += int(result.get("images_added") or 0)

    return {
        "status": "ok" if not failed else "partial",
        "summary": (
            f"资源库扫描完成：扫描仓库 {totals['scanned_repos']} 个，失败 {len(failed)} 个，"
            f"新增正式效果对 {totals['prompt_pairs_added']} 个，新增配对候选 {totals['pair_candidates_added']} 个。"
        ),
        "results": results,
        "failed": failed,
        **totals,
    }
