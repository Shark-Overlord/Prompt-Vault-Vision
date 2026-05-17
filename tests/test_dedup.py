import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend"))

from services.dedup_service import looks_like_forbidden_resource, normalize_github_url


def test_normalize_github_url_variants():
    assert normalize_github_url("https://github.com/foo/bar.git?x=1#readme") == "https://github.com/foo/bar"
    assert normalize_github_url("git@github.com:foo/bar.git") == "https://github.com/foo/bar"


def test_forbidden_filter_checks_readme_style_text():
    assert looks_like_forbidden_resource("safe-name", "This README contains a not safe for work disclaimer.")
    assert looks_like_forbidden_resource("safe-name", "NSFW examples are included.")
