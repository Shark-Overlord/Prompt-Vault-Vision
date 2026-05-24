from __future__ import annotations

import asyncio
import hashlib
import hmac
import json
import os
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence
from urllib import error as urllib_error
from urllib import request as urllib_request
from urllib.parse import quote, urlparse

from dotenv import load_dotenv

from database import PROJECT_ROOT, fetch_one, get_connection, paginate, utc_now


load_dotenv()
load_dotenv(Path(__file__).resolve().parents[1] / ".env")


ACTIVE_UPLOAD_STATUSES = {"queued", "running", "cancel_requested"}
_queue: Optional[asyncio.Queue[int]] = None
_worker_task: Optional[asyncio.Task] = None


@dataclass(frozen=True)
class CosSettings:
    host: str
    secret_id: str
    secret_key: str
    region: str
    bucket: str
    key_prefix: str = "visual-prompt-library"


def _settings() -> CosSettings:
    host = (os.getenv("TENCENT_COS_HOST") or "").strip().rstrip("/")
    secret_id = (os.getenv("TENCENT_COS_SECRET_ID") or "").strip()
    secret_key = (os.getenv("TENCENT_COS_SECRET_KEY") or "").strip()
    region = (os.getenv("TENCENT_COS_REGION") or "").strip()
    bucket = (os.getenv("TENCENT_COS_BUCKET") or "").strip()
    key_prefix = (os.getenv("TENCENT_COS_KEY_PREFIX") or "visual-prompt-library").strip().strip("/")
    missing = [
        name
        for name, value in {
            "TENCENT_COS_HOST": host,
            "TENCENT_COS_SECRET_ID": secret_id,
            "TENCENT_COS_SECRET_KEY": secret_key,
            "TENCENT_COS_REGION": region,
            "TENCENT_COS_BUCKET": bucket,
        }.items()
        if not value
    ]
    if missing:
        raise RuntimeError(f"COS 配置缺失：{', '.join(missing)}")
    return CosSettings(host=host, secret_id=secret_id, secret_key=secret_key, region=region, bucket=bucket, key_prefix=key_prefix)


def get_cloud_storage_status() -> Dict[str, Any]:
    try:
        settings = _settings()
    except RuntimeError as exc:
        return {"configured": False, "message": str(exc)}
    return {
        "configured": True,
        "provider": "tencent_cos",
        "host": settings.host,
        "region": settings.region,
        "bucket": settings.bucket,
        "key_prefix": settings.key_prefix,
        "secret_id_set": bool(settings.secret_id),
        "secret_key_set": bool(settings.secret_key),
    }


def _row(run_id: int) -> Optional[Dict[str, Any]]:
    return fetch_one("SELECT * FROM cloud_upload_runs WHERE id = ?", (run_id,))


def _update(run_id: int, **fields: Any) -> None:
    if not fields:
        return
    fields["updated_at"] = fields.get("updated_at") or utc_now()
    assignments = ", ".join(f"{key} = ?" for key in fields)
    with get_connection() as conn:
        conn.execute(f"UPDATE cloud_upload_runs SET {assignments} WHERE id = ?", (*fields.values(), run_id))


def start_cloud_upload_worker() -> None:
    global _queue, _worker_task
    if _worker_task and not _worker_task.done():
        return
    _queue = asyncio.Queue()
    _worker_task = asyncio.create_task(_worker_loop())


async def stop_cloud_upload_worker() -> None:
    global _worker_task
    if not _worker_task:
        return
    _worker_task.cancel()
    try:
        await _worker_task
    except asyncio.CancelledError:
        pass
    _worker_task = None


def create_upload_run(options: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    if _queue is None:
        raise RuntimeError("云存储上传队列尚未启动")
    now = utc_now()
    options = options or {}
    with get_connection() as conn:
        cursor = conn.execute(
            """
            INSERT INTO cloud_upload_runs
                (status, current_file, options_json, created_at, updated_at)
            VALUES ('queued', '等待上传队列执行', ?, ?, ?)
            """,
            (json.dumps(options, ensure_ascii=False), now, now),
        )
        run_id = int(cursor.lastrowid)
    _queue.put_nowait(run_id)
    return _row(run_id) or {"id": run_id, "status": "queued"}


async def _worker_loop() -> None:
    assert _queue is not None
    while True:
        run_id = await _queue.get()
        try:
            await _execute_run(run_id)
        finally:
            _queue.task_done()


def _cancel_requested(run_id: int) -> bool:
    row = _row(run_id)
    return bool(row and (row.get("cancel_requested") or row.get("status") == "cancel_requested"))


def cancel_upload_run(run_id: int) -> Dict[str, Any]:
    run = _row(run_id)
    if not run:
        raise ValueError("上传任务不存在")
    if run["status"] == "queued":
        _update(run_id, status="canceled", cancel_requested=1, current_file="已取消", finished_at=utc_now())
    elif run["status"] == "running":
        _update(run_id, status="cancel_requested", cancel_requested=1, current_file="等待当前文件上传结束后取消")
    return _row(run_id) or {}


def _asset_query(options: Dict[str, Any]) -> tuple[str, Sequence[Any]]:
    where = ["image_local_path IS NOT NULL", "image_local_path != ''"]
    params: List[Any] = []
    asset_ids = options.get("asset_ids") or []
    cleaned_ids = [int(item) for item in asset_ids if int(item) > 0]
    if cleaned_ids:
        where.append(f"id IN ({', '.join('?' for _ in cleaned_ids)})")
        params.extend(cleaned_ids)
    if options.get("only_missing", True):
        where.append("(cloud_storage_url IS NULL OR cloud_storage_url = '')")
    asset_type = (options.get("asset_type") or "").strip()
    if asset_type:
        where.append("asset_type = ?")
        params.append(asset_type)
    limit = int(options.get("limit") or 0)
    limit_sql = " LIMIT ?" if limit > 0 else ""
    if limit > 0:
        params.append(limit)
    return f"SELECT * FROM assets WHERE {' AND '.join(where)} ORDER BY id ASC{limit_sql}", tuple(params)


def _local_path(path_value: str) -> Path:
    path = Path(path_value)
    if path.is_absolute():
        return path
    return PROJECT_ROOT / path


def _object_key(settings: CosSettings, local_path: Path) -> str:
    try:
        relative = local_path.resolve().relative_to(PROJECT_ROOT.resolve())
    except ValueError:
        relative = Path(local_path.name)
    normalized = relative.as_posix().lstrip("/")
    return f"{settings.key_prefix}/{normalized}" if settings.key_prefix else normalized


def _public_url(settings: CosSettings, key: str) -> str:
    return f"{settings.host}/{quote(key, safe='/')}"


def _cos_authorization(settings: CosSettings, method: str, key: str) -> tuple[str, str]:
    parsed = urlparse(settings.host)
    host = parsed.netloc
    start = int(time.time()) - 60
    end = start + 3600
    key_time = f"{start};{end}"
    http_uri = f"/{quote(key, safe='/')}"
    http_method = method.lower()
    http_headers = f"host={host}"
    http_parameters = ""
    format_string = f"{http_method}\n{http_uri}\n{http_parameters}\n{http_headers}\n"
    string_to_sign = f"sha1\n{key_time}\n{hashlib.sha1(format_string.encode('utf-8')).hexdigest()}\n"
    sign_key = hmac.new(settings.secret_key.encode("utf-8"), key_time.encode("utf-8"), hashlib.sha1).hexdigest()
    signature = hmac.new(sign_key.encode("utf-8"), string_to_sign.encode("utf-8"), hashlib.sha1).hexdigest()
    authorization = (
        "q-sign-algorithm=sha1"
        f"&q-ak={settings.secret_id}"
        f"&q-sign-time={key_time}"
        f"&q-key-time={key_time}"
        "&q-header-list=host"
        "&q-url-param-list="
        f"&q-signature={signature}"
    )
    return host, authorization


def _upload_file(settings: CosSettings, local_path: Path, key: str) -> str:
    host, authorization = _cos_authorization(settings, "PUT", key)
    url = _public_url(settings, key)
    headers = {
        "Host": host,
        "Authorization": authorization,
        "Content-Type": "application/octet-stream",
        "Content-Length": str(local_path.stat().st_size),
    }
    data = local_path.read_bytes()
    req = urllib_request.Request(url, data=data, headers=headers, method="PUT")
    try:
        with urllib_request.urlopen(req, timeout=120) as response:
            if response.status >= 400:
                body = response.read().decode("utf-8", errors="ignore")
                raise RuntimeError(f"COS HTTP {response.status}: {body[:500]}")
    except urllib_error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="ignore")
        raise RuntimeError(f"COS HTTP {exc.code}: {body[:500]}") from exc
    return _public_url(settings, key)


async def _upload_path(settings: CosSettings, local_path: Path) -> tuple[str, str]:
    key = _object_key(settings, local_path)
    loop = asyncio.get_running_loop()
    url = await loop.run_in_executor(None, _upload_file, settings, local_path, key)
    return key, url


def _sync_related_records(asset: Dict[str, Any], cloud_url: str, thumbnail_cloud_url: Optional[str], settings: CosSettings, key: str) -> None:
    now = utc_now()
    image_hash = asset.get("image_hash")
    with get_connection() as conn:
        conn.execute(
            """
            UPDATE assets
            SET cloud_storage_url = ?,
                thumbnail_cloud_storage_url = COALESCE(?, thumbnail_cloud_storage_url),
                cloud_storage_provider = 'tencent_cos',
                cloud_storage_bucket = ?,
                cloud_storage_region = ?,
                cloud_storage_key = ?,
                cloud_uploaded_at = ?
            WHERE id = ?
            """,
            (cloud_url, thumbnail_cloud_url, settings.bucket, settings.region, key, now, asset["id"]),
        )
        if image_hash:
            conn.execute("UPDATE prompt_effect_pairs SET cloud_storage_url = ?, updated_at = ? WHERE image_hash = ?", (cloud_url, now, image_hash))
            conn.execute("UPDATE pair_candidates SET cloud_storage_url = ?, updated_at = ? WHERE image_hash = ?", (cloud_url, now, image_hash))
            conn.execute(
                "UPDATE image_candidates SET cloud_storage_url = ?, thumbnail_cloud_storage_url = COALESCE(?, thumbnail_cloud_storage_url) WHERE image_hash = ?",
                (cloud_url, thumbnail_cloud_url, image_hash),
            )
            conn.execute("UPDATE web_ui_prompts SET screenshot_cloud_storage_url = ?, updated_at = ? WHERE screenshot_hash = ?", (cloud_url, now, image_hash))
            conn.execute("UPDATE web_ui_repo_profiles SET screenshot_cloud_storage_url = ?, updated_at = ? WHERE screenshot_hash = ?", (cloud_url, now, image_hash))


async def _execute_run(run_id: int) -> None:
    run = _row(run_id)
    if not run:
        return
    options: Dict[str, Any] = {}
    try:
        options = json.loads(run.get("options_json") or "{}")
    except Exception:
        options = {}
    started = utc_now()
    _update(run_id, status="running", started_at=started, current_file="读取 COS 配置")
    try:
        settings = _settings()
        sql, params = _asset_query(options)
        with get_connection() as conn:
            assets = [dict(row) for row in conn.execute(sql, params).fetchall()]
        total = len(assets)
        _update(run_id, total_assets=total, current_file=f"准备上传 {total} 个资产")
        uploaded = 0
        skipped = 0
        failed = 0
        include_thumbnails = bool(options.get("include_thumbnails", True))
        errors: List[Dict[str, Any]] = []
        for index, asset in enumerate(assets, start=1):
            if _cancel_requested(run_id):
                result = {
                    "uploaded": uploaded,
                    "skipped": skipped,
                    "failed": failed,
                    "errors": errors[:50],
                    "message": "用户已取消，本次任务没有继续处理剩余资源。",
                }
                _update(
                    run_id,
                    status="canceled",
                    processed_assets=index - 1,
                    uploaded_assets=uploaded,
                    skipped_assets=skipped,
                    failed_assets=failed,
                    result_json=json.dumps(result, ensure_ascii=False),
                    error="用户取消",
                    current_file="已取消",
                    finished_at=utc_now(),
                )
                return
            local_path = _local_path(asset["image_local_path"])
            _update(run_id, current_asset_id=asset["id"], current_file=asset["image_local_path"], processed_assets=index - 1)
            if not local_path.exists():
                skipped += 1
                errors.append({"asset_id": asset["id"], "path": asset["image_local_path"], "error": "本地文件不存在"})
                _update(run_id, processed_assets=index, skipped_assets=skipped)
                continue
            try:
                key, cloud_url = await _upload_path(settings, local_path)
                thumbnail_cloud_url = None
                thumb_path_value = asset.get("thumbnail_local_path")
                if include_thumbnails and thumb_path_value:
                    thumb_path = _local_path(thumb_path_value)
                    if thumb_path.exists():
                        _, thumbnail_cloud_url = await _upload_path(settings, thumb_path)
                _sync_related_records(asset, cloud_url, thumbnail_cloud_url, settings, key)
                uploaded += 1
            except Exception as exc:
                failed += 1
                errors.append({"asset_id": asset["id"], "path": asset["image_local_path"], "error": str(exc)[:500]})
            _update(run_id, processed_assets=index, uploaded_assets=uploaded, skipped_assets=skipped, failed_assets=failed)
        result = {"uploaded": uploaded, "skipped": skipped, "failed": failed, "errors": errors[:50]}
        _update(
            run_id,
            status="succeeded" if failed == 0 else "failed",
            result_json=json.dumps(result, ensure_ascii=False),
            error="" if failed == 0 else f"{failed} 个资产上传失败",
            current_file="上传完成",
            finished_at=utc_now(),
        )
    except Exception as exc:
        _update(run_id, status="failed", error=str(exc), current_file="上传失败", finished_at=utc_now())


def get_upload_run(run_id: int) -> Optional[Dict[str, Any]]:
    return _row(run_id)


def list_upload_runs(page: int = 1, page_size: int = 20, status: Optional[str] = None) -> Dict[str, Any]:
    where = ["1 = 1"]
    params: List[Any] = []
    if status and status != "all":
        where.append("status = ?")
        params.append(status)
    clause = " AND ".join(where)
    return paginate(
        f"SELECT * FROM cloud_upload_runs WHERE {clause} ORDER BY id DESC",
        f"SELECT COUNT(*) FROM cloud_upload_runs WHERE {clause}",
        tuple(params),
        page,
        page_size,
    )
