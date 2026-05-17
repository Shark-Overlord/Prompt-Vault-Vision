from __future__ import annotations

import hashlib
import re
from typing import Optional
from urllib.parse import urlparse

from database import fetch_one


GITHUB_RE = re.compile(r"github\.com[:/](?P<owner>[^/\s#?]+)/(?P<repo>[^/\s#?]+)", re.IGNORECASE)


def normalize_github_url(url: str) -> Optional[str]:
    if not url:
        return None
    cleaned = url.strip()
    if cleaned.startswith("git@github.com:"):
        cleaned = cleaned.replace("git@github.com:", "https://github.com/", 1)
    parsed = urlparse(cleaned)
    probe = cleaned if not parsed.netloc else f"{parsed.netloc}{parsed.path}"
    match = GITHUB_RE.search(probe)
    if not match:
        return None
    owner = match.group("owner").strip()
    repo = match.group("repo").strip().rstrip("/")
    if repo.endswith(".git"):
        repo = repo[:-4]
    if not owner or not repo:
        return None
    return f"https://github.com/{owner}/{repo}"


def content_hash(text: str) -> str:
    normalized = " ".join((text or "").lower().split())
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()


def get_existing_repo(canonical_url: str):
    return fetch_one("SELECT * FROM repos WHERE canonical_url = ?", (canonical_url,))


def looks_like_forbidden_resource(name: str, description: str = "") -> bool:
    text = f"{name} {description}".lower()
    forbidden = (
        "midjourney",
        "not safe for work",
        "porn",
        "nsfw",
        "adult",
        "erotic",
        "sexual",
        "nude",
        "nudity",
        "gore",
        "bloody",
        "graphic violence",
        "malware",
        "crack",
        "phishing",
        "exploit",
        "payload",
        "破解",
        "色情",
        "成人",
        "血腥",
    )
    return any(token in text for token in forbidden)


def infer_category(keyword: str, fallback: str = "image_generation_prompt") -> str:
    text = keyword.lower()
    if any(x in text for x in ("web", "ui", "frontend", "landing", "dashboard", "saas", "shadcn", "tailwind", "component")):
        return "web_ui_prompt"
    if any(x in text for x in ("edit", "retouch", "background", "object removal", "variation", "style transfer")):
        return "image_editing_prompt"
    if any(x in text for x in ("video", "cinematic", "storyboard", "veo", "kling", "runway", "seedance", "wan")):
        return "video_generation_prompt"
    return fallback
