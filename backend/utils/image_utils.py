from __future__ import annotations

import hashlib
import re
import asyncio
import urllib.request
from pathlib import Path
from typing import Dict, Iterable, List, Optional
from urllib.parse import urljoin, urlparse

from PIL import Image

from database import PROJECT_ROOT


IMAGE_PATTERN = re.compile(r"!\[[^\]]*\]\((?P<url>[^)\s]+)(?:\s+\"[^\"]*\")?\)", re.IGNORECASE)
BADGE_HINTS = ("badge", "shields.io", "license.svg", "stars.svg", "forks.svg", "workflow", "actions")


def extract_markdown_image_urls(markdown: str, base_url: str = "") -> List[str]:
    urls: List[str] = []
    for match in IMAGE_PATTERN.finditer(markdown or ""):
        url = match.group("url").strip()
        if any(hint in url.lower() for hint in BADGE_HINTS):
            continue
        if url.startswith("#"):
            continue
        urls.append(urljoin(base_url, url) if base_url else url)
    return urls


def stable_filename(url: str, suffix: str = ".jpg") -> str:
    parsed = urlparse(url)
    ext = Path(parsed.path).suffix.lower()
    if ext not in {".jpg", ".jpeg", ".png", ".webp", ".gif"}:
        ext = suffix
    digest = hashlib.sha256(url.encode("utf-8")).hexdigest()[:20]
    return f"{digest}{ext}"


def compute_average_hash(path: Path) -> str:
    with Image.open(path) as img:
        img = img.convert("L").resize((8, 8))
        pixels = list(img.getdata())
    avg = sum(pixels) / len(pixels)
    bits = "".join("1" if pixel >= avg else "0" for pixel in pixels)
    return f"{int(bits, 2):016x}"


def image_metadata(path: Path) -> Dict[str, int]:
    with Image.open(path) as img:
        width, height = img.size
    return {
        "width": int(width),
        "height": int(height),
        "file_size": int(path.stat().st_size),
    }


def create_thumbnail(source: Path, target: Path, size: tuple[int, int] = (720, 720)) -> None:
    target.parent.mkdir(parents=True, exist_ok=True)
    with Image.open(source) as img:
        img.thumbnail(size)
        if img.mode not in ("RGB", "RGBA"):
            img = img.convert("RGB")
        img.save(target)


def _download_image_bytes(url: str, timeout: int = 30) -> tuple[str, bytes]:
    request = urllib.request.Request(
        url,
        headers={
            "User-Agent": "Mozilla/5.0 (Visual Prompt Library)",
            "Accept": "image/avif,image/webp,image/apng,image/svg+xml,image/*,*/*;q=0.8",
        },
    )
    with urllib.request.urlopen(request, timeout=timeout) as response:
        content_type = response.headers.get("content-type", "")
        data = response.read(20 * 1024 * 1024 + 1)
    return content_type, data


async def download_image(url: str, image_dir: Optional[Path] = None, thumb_dir: Optional[Path] = None) -> Optional[Dict[str, str | int]]:
    image_dir = image_dir or PROJECT_ROOT / "assets" / "images"
    thumb_dir = thumb_dir or PROJECT_ROOT / "assets" / "thumbnails"
    image_dir.mkdir(parents=True, exist_ok=True)
    thumb_dir.mkdir(parents=True, exist_ok=True)
    filename = stable_filename(url)
    local_path = image_dir / filename
    thumb_path = thumb_dir / filename
    try:
        loop = asyncio.get_running_loop()
        content_type, content = await loop.run_in_executor(None, _download_image_bytes, url)
        if "image" not in content_type.lower() or len(content) > 20 * 1024 * 1024:
            return None
        local_path.write_bytes(content)
    except Exception:
        return None
    try:
        metadata = image_metadata(local_path)
        if metadata["width"] < 240 or metadata["height"] < 160:
            local_path.unlink(missing_ok=True)
            return None
        image_hash = compute_average_hash(local_path)
        create_thumbnail(local_path, thumb_path)
    except Exception:
        local_path.unlink(missing_ok=True)
        return None
    return {
        "image_local_path": str(local_path.relative_to(PROJECT_ROOT)).replace("\\", "/"),
        "thumbnail_local_path": str(thumb_path.relative_to(PROJECT_ROOT)).replace("\\", "/"),
        "image_hash": image_hash,
        **metadata,
    }
