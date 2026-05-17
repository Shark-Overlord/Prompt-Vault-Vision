from __future__ import annotations

import json
import os
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, Optional

import httpx
from dotenv import load_dotenv

from database import PROJECT_ROOT, utc_now


load_dotenv()
load_dotenv(Path(__file__).resolve().parents[1] / ".env")

AUTH_DIR = PROJECT_ROOT / "backend" / ".auth"
AUTH_FILE = AUTH_DIR / "github_token.json"
DEVICE_SESSIONS_FILE = AUTH_DIR / "github_device_sessions.json"
GITHUB_DEVICE_CODE_URL = "https://github.com/login/device/code"
GITHUB_ACCESS_TOKEN_URL = "https://github.com/login/oauth/access_token"
GITHUB_API = "https://api.github.com"


def _read_json(path: Path) -> Dict[str, Any]:
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return {}


def _write_json(path: Path, payload: Dict[str, Any]) -> None:
    AUTH_DIR.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def _read_auth_file() -> Dict[str, Any]:
    return _read_json(AUTH_FILE)


def _write_auth_file(payload: Dict[str, Any]) -> None:
    _write_json(AUTH_FILE, payload)


def _parse_utc(value: str) -> datetime:
    parsed = datetime.fromisoformat(value)
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _load_device_sessions() -> Dict[str, Dict[str, Any]]:
    now = datetime.now(timezone.utc)
    sessions = _read_json(DEVICE_SESSIONS_FILE)
    valid_sessions: Dict[str, Dict[str, Any]] = {}
    for session_id, session in sessions.items():
        try:
            if _parse_utc(session["expires_at"]) > now:
                valid_sessions[session_id] = session
        except (KeyError, TypeError, ValueError):
            continue
    if valid_sessions != sessions:
        _persist_device_sessions(valid_sessions)
    return valid_sessions


def _persist_device_sessions(sessions: Dict[str, Dict[str, Any]]) -> None:
    _write_json(DEVICE_SESSIONS_FILE, sessions)


_device_sessions: Dict[str, Dict[str, Any]] = _load_device_sessions()


def get_client_id() -> Optional[str]:
    return os.getenv("GITHUB_CLIENT_ID") or _read_auth_file().get("client_id")


def save_client_id(client_id: str) -> Dict[str, Any]:
    clean = client_id.strip()
    if not clean:
        raise ValueError("GitHub Client ID 不能为空")
    data = _read_auth_file()
    data["client_id"] = clean
    data["updated_at"] = utc_now()
    _write_auth_file(data)
    return github_status()


def get_stored_token() -> Optional[str]:
    return os.getenv("GITHUB_TOKEN") or os.getenv("GH_TOKEN") or _read_auth_file().get("access_token")


def clear_github_auth() -> Dict[str, Any]:
    data = _read_auth_file()
    client_id = data.get("client_id")
    if AUTH_FILE.exists():
        AUTH_FILE.unlink()
    if client_id:
        _write_auth_file({"client_id": client_id, "updated_at": utc_now()})
    return github_status()


async def validate_token(token: str) -> Dict[str, Any]:
    async with httpx.AsyncClient(
        timeout=20,
        trust_env=False,
        headers={"Accept": "application/vnd.github+json", "User-Agent": "visual-prompt-library"},
    ) as client:
        response = await client.get(f"{GITHUB_API}/user", headers={"Authorization": f"Bearer {token}"})
        if response.status_code >= 400:
            return {"valid": False, "error": f"GitHub API HTTP {response.status_code}"}
        user = response.json()
        return {
            "valid": True,
            "login": user.get("login"),
            "name": user.get("name"),
            "avatar_url": user.get("avatar_url"),
            "html_url": user.get("html_url"),
        }


def github_status() -> Dict[str, Any]:
    data = _read_auth_file()
    token = get_stored_token()
    return {
        "configured": bool(get_client_id()),
        "connected": bool(token),
        "client_id": get_client_id(),
        "login": data.get("login"),
        "name": data.get("name"),
        "avatar_url": data.get("avatar_url"),
        "html_url": data.get("html_url"),
        "scope": data.get("scope"),
        "token_type": data.get("token_type"),
        "source": "env" if os.getenv("GITHUB_TOKEN") or os.getenv("GH_TOKEN") else ("local" if token else "none"),
        "updated_at": data.get("updated_at"),
    }


async def start_device_flow(client_id: Optional[str], scope: str) -> Dict[str, Any]:
    if client_id:
        save_client_id(client_id)
    resolved_client_id = get_client_id()
    if not resolved_client_id:
        raise ValueError("请先配置 GitHub OAuth App Client ID")

    async with httpx.AsyncClient(timeout=20, trust_env=False, headers={"Accept": "application/json", "User-Agent": "visual-prompt-library"}) as client:
        response = await client.post(
            GITHUB_DEVICE_CODE_URL,
            data={"client_id": resolved_client_id, "scope": scope},
        )
    if response.status_code >= 400:
        raise ValueError(f"GitHub 设备授权启动失败：HTTP {response.status_code}")

    payload = response.json()
    if "error" in payload:
        raise ValueError(payload.get("error_description") or payload["error"])
    if not payload.get("device_code"):
        raise ValueError("GitHub 未返回 device_code，请检查 OAuth App 是否启用了 Device Flow")

    session_id = uuid.uuid4().hex
    expires_in = int(payload.get("expires_in") or 900)
    expires_at = datetime.now(timezone.utc) + timedelta(seconds=expires_in)
    _device_sessions[session_id] = {
        "client_id": resolved_client_id,
        "device_code": payload["device_code"],
        "interval": int(payload.get("interval") or 5),
        "expires_at": expires_at.isoformat(),
    }
    _persist_device_sessions(_device_sessions)
    return {
        "session_id": session_id,
        "user_code": payload.get("user_code"),
        "verification_uri": payload.get("verification_uri"),
        "verification_uri_complete": payload.get("verification_uri_complete"),
        "expires_in": expires_in,
        "interval": int(payload.get("interval") or 5),
    }


async def poll_device_flow(session_id: str) -> Dict[str, Any]:
    session = _device_sessions.get(session_id)
    if not session:
        return {"status": "expired", "message": "授权会话不存在或已过期，请重新连接 GitHub。"}

    try:
        expires_at = _parse_utc(session["expires_at"])
    except (KeyError, TypeError, ValueError):
        _device_sessions.pop(session_id, None)
        _persist_device_sessions(_device_sessions)
        return {"status": "expired", "message": "授权会话状态异常，请重新连接 GitHub。"}

    if datetime.now(timezone.utc) >= expires_at:
        _device_sessions.pop(session_id, None)
        _persist_device_sessions(_device_sessions)
        return {"status": "expired", "message": "GitHub 授权码已过期，请重新开始。"}

    async with httpx.AsyncClient(timeout=20, trust_env=False, headers={"Accept": "application/json", "User-Agent": "visual-prompt-library"}) as client:
        response = await client.post(
            GITHUB_ACCESS_TOKEN_URL,
            data={
                "client_id": session["client_id"],
                "device_code": session["device_code"],
                "grant_type": "urn:ietf:params:oauth:grant-type:device_code",
            },
        )
    if response.status_code >= 400:
        return {"status": "error", "message": f"GitHub token 请求失败：HTTP {response.status_code}"}

    payload = response.json()
    if payload.get("error") == "authorization_pending":
        return {"status": "pending", "message": "等待你在 GitHub 页面完成授权。", "interval": session["interval"]}
    if payload.get("error") == "slow_down":
        session["interval"] = int(session["interval"]) + 5
        _persist_device_sessions(_device_sessions)
        return {"status": "pending", "message": "GitHub 要求降低轮询频率，已自动放慢。", "interval": session["interval"]}
    if payload.get("error"):
        _device_sessions.pop(session_id, None)
        _persist_device_sessions(_device_sessions)
        return {"status": "error", "message": payload.get("error_description") or payload["error"]}

    token = payload.get("access_token")
    if not token:
        return {"status": "error", "message": "GitHub 未返回 access_token。"}

    user = await validate_token(token)
    if not user.get("valid"):
        return {"status": "error", "message": user.get("error") or "GitHub token 校验失败。"}

    data = _read_auth_file()
    data.update(
        {
            "client_id": session["client_id"],
            "access_token": token,
            "token_type": payload.get("token_type"),
            "scope": payload.get("scope"),
            "updated_at": utc_now(),
            **{key: value for key, value in user.items() if key != "valid"},
        }
    )
    _write_auth_file(data)
    _device_sessions.pop(session_id, None)
    _persist_device_sessions(_device_sessions)
    return {"status": "connected", "auth": github_status(), "message": "GitHub 已连接。"}
