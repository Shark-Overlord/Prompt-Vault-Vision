from __future__ import annotations

import time
from typing import Any, Dict, List, Optional

import httpx

from database import fetch_all, fetch_one, get_connection, row_to_dict, utc_now


PROVIDER_DEFAULTS: Dict[str, Dict[str, Any]] = {
    "deepseek": {
        "label": "DeepSeek",
        "base_url": "https://api.deepseek.com",
        "model": "deepseek-chat",
        "requires_api_key": True,
    },
    "lm_studio": {
        "label": "LM Studio",
        "base_url": "http://127.0.0.1:1234/v1",
        "model": "local-model",
        "requires_api_key": False,
    },
}


def _normalize_provider(provider: Optional[str]) -> str:
    value = (provider or "deepseek").strip().lower()
    if value not in PROVIDER_DEFAULTS:
        raise ValueError("AI 提供商只能选择 DeepSeek 或 LM Studio")
    return value


def _normalize_base_url(provider: str, base_url: Optional[str]) -> str:
    value = (base_url or PROVIDER_DEFAULTS[provider]["base_url"]).strip().rstrip("/")
    if not value.startswith(("http://", "https://")):
        raise ValueError("base_url 必须以 http:// 或 https:// 开头")
    return value


def _normalize_model(provider: str, model: Optional[str]) -> str:
    value = (model or PROVIDER_DEFAULTS[provider]["model"]).strip()
    if not value:
        raise ValueError("模型名称不能为空")
    return value


def _public_config(row: Optional[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    if not row:
        return None
    data = dict(row)
    api_key = data.pop("api_key", None)
    data["api_key_set"] = bool(api_key)
    data["enabled"] = bool(data.get("enabled"))
    data["is_default"] = bool(data.get("is_default"))
    data["provider_label"] = PROVIDER_DEFAULTS.get(data.get("provider"), {}).get("label", data.get("provider"))
    return data


def list_ai_configs() -> List[Dict[str, Any]]:
    rows = fetch_all("SELECT * FROM ai_configs ORDER BY is_default DESC, updated_at DESC, id DESC")
    return [_public_config(row) or {} for row in rows]


def get_ai_config(config_id: int, include_secret: bool = False) -> Optional[Dict[str, Any]]:
    row = fetch_one("SELECT * FROM ai_configs WHERE id = ?", (config_id,))
    if not row:
        return None
    return row if include_secret else _public_config(row)


def get_default_ai_config(include_secret: bool = False) -> Optional[Dict[str, Any]]:
    row = fetch_one(
        """
        SELECT * FROM ai_configs
        WHERE enabled = 1
        ORDER BY is_default DESC, updated_at DESC, id DESC
        LIMIT 1
        """
    )
    if not row:
        return None
    return row if include_secret else _public_config(row)


def _validated_create_data(payload: Dict[str, Any]) -> Dict[str, Any]:
    provider = _normalize_provider(payload.get("provider"))
    name = (payload.get("name") or PROVIDER_DEFAULTS[provider]["label"]).strip()
    if not name:
        raise ValueError("配置名称不能为空")
    return {
        "name": name,
        "provider": provider,
        "base_url": _normalize_base_url(provider, payload.get("base_url")),
        "api_key": (payload.get("api_key") or "").strip() or None,
        "model": _normalize_model(provider, payload.get("model")),
        "is_default": 1 if payload.get("is_default") else 0,
        "enabled": 1 if payload.get("enabled", True) else 0,
        "temperature": float(payload.get("temperature") if payload.get("temperature") is not None else 0.2),
        "timeout_seconds": int(payload.get("timeout_seconds") or 60),
    }


def create_ai_config(payload: Dict[str, Any]) -> Dict[str, Any]:
    data = _validated_create_data(payload)
    now = utc_now()
    with get_connection() as conn:
        has_existing = conn.execute("SELECT id FROM ai_configs LIMIT 1").fetchone()
        if not has_existing:
            data["is_default"] = 1
        if data["is_default"]:
            conn.execute("UPDATE ai_configs SET is_default = 0")
        cursor = conn.execute(
            """
            INSERT INTO ai_configs
                (name, provider, base_url, api_key, model, is_default, enabled,
                 temperature, timeout_seconds, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                data["name"],
                data["provider"],
                data["base_url"],
                data["api_key"],
                data["model"],
                data["is_default"],
                data["enabled"],
                data["temperature"],
                data["timeout_seconds"],
                now,
                now,
            ),
        )
        config_id = int(cursor.lastrowid)
    config = get_ai_config(config_id)
    if not config:
        raise ValueError("AI 配置创建失败")
    return config


def update_ai_config(config_id: int, payload: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    existing = get_ai_config(config_id, include_secret=True)
    if not existing:
        return None

    merged = dict(existing)
    for key, value in payload.items():
        if value is not None and key not in {"api_key", "clear_api_key"}:
            merged[key] = value

    provider = _normalize_provider(merged.get("provider"))
    name = (merged.get("name") or PROVIDER_DEFAULTS[provider]["label"]).strip()
    if not name:
        raise ValueError("配置名称不能为空")

    if payload.get("clear_api_key"):
        api_key = None
    elif payload.get("api_key") is not None:
        api_key = (payload.get("api_key") or "").strip() or None
    else:
        api_key = existing.get("api_key")

    data = {
        "name": name,
        "provider": provider,
        "base_url": _normalize_base_url(provider, merged.get("base_url")),
        "api_key": api_key,
        "model": _normalize_model(provider, merged.get("model")),
        "is_default": 1 if merged.get("is_default") else 0,
        "enabled": 1 if merged.get("enabled") else 0,
        "temperature": float(merged.get("temperature") if merged.get("temperature") is not None else 0.2),
        "timeout_seconds": int(merged.get("timeout_seconds") or 60),
    }
    now = utc_now()
    with get_connection() as conn:
        if data["is_default"]:
            conn.execute("UPDATE ai_configs SET is_default = 0 WHERE id != ?", (config_id,))
        conn.execute(
            """
            UPDATE ai_configs
            SET name = ?, provider = ?, base_url = ?, api_key = ?, model = ?,
                is_default = ?, enabled = ?, temperature = ?, timeout_seconds = ?,
                updated_at = ?
            WHERE id = ?
            """,
            (
                data["name"],
                data["provider"],
                data["base_url"],
                data["api_key"],
                data["model"],
                data["is_default"],
                data["enabled"],
                data["temperature"],
                data["timeout_seconds"],
                now,
                config_id,
            ),
        )
    return get_ai_config(config_id)


def delete_ai_config(config_id: int) -> bool:
    with get_connection() as conn:
        row = conn.execute("SELECT id FROM ai_configs WHERE id = ?", (config_id,)).fetchone()
        if not row:
            return False
        conn.execute("DELETE FROM ai_configs WHERE id = ?", (config_id,))
    return True


def _chat_completions_url(base_url: str) -> str:
    cleaned = base_url.strip().rstrip("/")
    if cleaned.endswith("/chat/completions"):
        return cleaned
    return f"{cleaned}/chat/completions"


def _models_url(base_url: str) -> str:
    cleaned = base_url.strip().rstrip("/")
    if cleaned.endswith("/chat/completions"):
        cleaned = cleaned[: -len("/chat/completions")]
    return f"{cleaned}/models"


def _headers(api_key: Optional[str]) -> Dict[str, str]:
    result = {"Content-Type": "application/json"}
    if api_key:
        result["Authorization"] = f"Bearer {api_key}"
    return result


async def chat_completion(
    messages: List[Dict[str, str]],
    ai_config_id: Optional[int] = None,
    temperature: Optional[float] = None,
    max_tokens: int = 1200,
) -> Dict[str, Any]:
    config = get_ai_config(ai_config_id, include_secret=True) if ai_config_id else get_default_ai_config(include_secret=True)
    if not config:
        raise ValueError("还没有可用的 AI 配置")
    provider = config["provider"]
    if PROVIDER_DEFAULTS[provider]["requires_api_key"] and not config.get("api_key"):
        raise ValueError("当前 AI 配置缺少 API Key")

    body = {
        "model": config["model"],
        "messages": messages,
        "temperature": float(temperature if temperature is not None else config.get("temperature") or 0.2),
        "max_tokens": max_tokens,
        "stream": False,
    }
    async with httpx.AsyncClient(timeout=int(config.get("timeout_seconds") or 60), trust_env=False) as client:
        response = await client.post(
            _chat_completions_url(config["base_url"]),
            headers=_headers(config.get("api_key")),
            json=body,
        )
    if response.status_code >= 400:
        raise ValueError(f"AI 调用失败：HTTP {response.status_code}: {_response_error_message(response)}")
    payload = response.json()
    try:
        content = payload["choices"][0]["message"]["content"]
    except Exception as exc:
        raise ValueError("AI 响应缺少 message.content") from exc
    return {"content": content, "config": _public_config(config), "raw": payload}


def _response_error_message(response: httpx.Response) -> str:
    try:
        payload = response.json()
    except ValueError:
        return response.text[:800] or f"HTTP {response.status_code}"
    if isinstance(payload, dict):
        error = payload.get("error")
        if isinstance(error, dict):
            return str(error.get("message") or error)
        if error:
            return str(error)
        if payload.get("message"):
            return str(payload["message"])
    return str(payload)[:800]


def _save_test_result(config_id: int, status: str, message: str, tested_at: str) -> None:
    with get_connection() as conn:
        conn.execute(
            """
            UPDATE ai_configs
            SET last_test_status = ?, last_test_message = ?, last_test_at = ?, updated_at = ?
            WHERE id = ?
            """,
            (status, message[:1000], tested_at, tested_at, config_id),
        )


async def test_ai_config(config_id: int) -> Optional[Dict[str, Any]]:
    config = get_ai_config(config_id, include_secret=True)
    if not config:
        return None

    provider = config["provider"]
    if PROVIDER_DEFAULTS[provider]["requires_api_key"] and not config.get("api_key"):
        tested_at = utc_now()
        message = "DeepSeek 配置缺少 API Key，无法测试连接。"
        _save_test_result(config_id, "failed", message, tested_at)
        return {
            "status": "failed",
            "message": message,
            "tested_at": tested_at,
            "latency_ms": 0,
            "config": get_ai_config(config_id),
        }

    started = time.perf_counter()
    tested_at = utc_now()
    body = {
        "model": config["model"],
        "messages": [
            {"role": "system", "content": "你是视觉 Prompt 资产库的连接测试助手。"},
            {"role": "user", "content": "请只回复 OK。"},
        ],
        "temperature": 0,
        "max_tokens": 12,
        "stream": False,
    }

    try:
        async with httpx.AsyncClient(timeout=int(config.get("timeout_seconds") or 60), trust_env=False) as client:
            response = await client.post(
                _chat_completions_url(config["base_url"]),
                headers=_headers(config.get("api_key")),
                json=body,
            )
    except httpx.HTTPError as exc:
        message = f"连接失败：{exc}"
        _save_test_result(config_id, "failed", message, tested_at)
        return {
            "status": "failed",
            "message": message,
            "tested_at": tested_at,
            "latency_ms": int((time.perf_counter() - started) * 1000),
            "config": get_ai_config(config_id),
        }

    latency_ms = int((time.perf_counter() - started) * 1000)
    if response.status_code >= 400:
        message = f"HTTP {response.status_code}: {_response_error_message(response)}"
        _save_test_result(config_id, "failed", message, tested_at)
        return {
            "status": "failed",
            "message": message,
            "tested_at": tested_at,
            "latency_ms": latency_ms,
            "config": get_ai_config(config_id),
        }

    try:
        payload = response.json()
        content = payload["choices"][0]["message"]["content"]
    except Exception:
        content = ""
    message = f"连接成功，模型返回：{content.strip() or 'OK'}"
    _save_test_result(config_id, "success", message, tested_at)
    return {
        "status": "success",
        "message": message,
        "tested_at": tested_at,
        "latency_ms": latency_ms,
        "config": get_ai_config(config_id),
    }


async def list_ai_models(config_id: int) -> Optional[Dict[str, Any]]:
    config = get_ai_config(config_id, include_secret=True)
    if not config:
        return None
    started = time.perf_counter()
    try:
        async with httpx.AsyncClient(timeout=int(config.get("timeout_seconds") or 60), trust_env=False) as client:
            response = await client.get(_models_url(config["base_url"]), headers=_headers(config.get("api_key")))
    except httpx.HTTPError as exc:
        return {"status": "failed", "message": f"模型列表读取失败：{exc}", "models": [], "latency_ms": int((time.perf_counter() - started) * 1000)}
    latency_ms = int((time.perf_counter() - started) * 1000)
    if response.status_code >= 400:
        return {"status": "failed", "message": f"HTTP {response.status_code}: {_response_error_message(response)}", "models": [], "latency_ms": latency_ms}
    try:
        payload = response.json()
    except ValueError:
        return {"status": "failed", "message": "模型列表响应不是 JSON。", "models": [], "latency_ms": latency_ms}
    models = []
    for item in payload.get("data", []) if isinstance(payload, dict) else []:
        if isinstance(item, dict) and item.get("id"):
            models.append(str(item["id"]))
    return {"status": "success", "message": f"读取到 {len(models)} 个模型。", "models": models, "latency_ms": latency_ms}
