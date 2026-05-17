from __future__ import annotations

import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, Iterator, List, Optional, Sequence, Tuple


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = PROJECT_ROOT / "data"
DB_PATH = DATA_DIR / "visual_prompt_library.db"


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


SCHEMA_SQL = """
PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS repos (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    repo_name TEXT,
    owner TEXT,
    repo_url TEXT,
    canonical_url TEXT UNIQUE,
    stars INTEGER DEFAULT 0,
    forks INTEGER DEFAULT 0,
    license TEXT,
    is_fork INTEGER DEFAULT 0,
    parent_repo TEXT,
    resource_type TEXT,
    category TEXT,
    quality_level TEXT,
    status TEXT,
    summary TEXT,
    local_note_path TEXT,
    content_hash TEXT,
    has_preview_images INTEGER DEFAULT 0,
    has_prompt_effect_pairs INTEGER DEFAULT 0,
    prompt_effect_pair_count INTEGER DEFAULT 0,
    duplicate_of TEXT,
    similar_to TEXT,
    last_checked_at TEXT,
    last_updated_at TEXT,
    created_at TEXT,
    notes TEXT
);

CREATE TABLE IF NOT EXISTS prompt_effect_pairs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    repo_id INTEGER,
    repo_name TEXT,
    repo_url TEXT,
    source_page_url TEXT,
    original_prompt TEXT,
    prompt_cn_explanation TEXT,
    image_original_url TEXT,
    image_local_path TEXT,
    image_hash TEXT,
    task_type TEXT,
    category TEXT,
    scenario TEXT,
    visual_style TEXT,
    quality_level TEXT,
    selection_status TEXT,
    effect_review TEXT,
    reusable_value TEXT,
    license TEXT,
    commercial_risk TEXT,
    pair_relation_type TEXT DEFAULT 'unclear',
    pair_evidence TEXT,
    pair_confidence INTEGER DEFAULT 0,
    generated_by TEXT,
    local_note_path TEXT,
    created_at TEXT,
    updated_at TEXT,
    FOREIGN KEY (repo_id) REFERENCES repos(id)
);

CREATE TABLE IF NOT EXISTS assets (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    repo_id INTEGER,
    image_original_url TEXT,
    image_local_path TEXT,
    thumbnail_local_path TEXT,
    image_hash TEXT UNIQUE,
    source_page_url TEXT,
    asset_type TEXT,
    width INTEGER,
    height INTEGER,
    file_size INTEGER,
    description TEXT,
    commercial_risk TEXT,
    created_at TEXT,
    FOREIGN KEY (repo_id) REFERENCES repos(id)
);

CREATE TABLE IF NOT EXISTS search_state (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    keyword TEXT UNIQUE,
    category TEXT,
    last_success_search_at TEXT,
    safety_overlap_days INTEGER DEFAULT 3,
    last_result_count INTEGER DEFAULT 0,
    status TEXT DEFAULT 'active',
    updated_at TEXT
);

CREATE TABLE IF NOT EXISTS search_logs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    search_date TEXT,
    keyword TEXT,
    search_type TEXT,
    result_count INTEGER,
    new_count INTEGER,
    updated_count INTEGER,
    duplicate_count INTEGER,
    skipped_count INTEGER,
    pending_review_count INTEGER,
    summary TEXT,
    created_at TEXT
);

CREATE TABLE IF NOT EXISTS tags (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT UNIQUE,
    type TEXT,
    created_at TEXT
);

CREATE TABLE IF NOT EXISTS pair_tags (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    pair_id INTEGER,
    tag_id INTEGER,
    FOREIGN KEY (pair_id) REFERENCES prompt_effect_pairs(id),
    FOREIGN KEY (tag_id) REFERENCES tags(id),
    UNIQUE(pair_id, tag_id)
);

CREATE TABLE IF NOT EXISTS ai_configs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    provider TEXT NOT NULL,
    base_url TEXT NOT NULL,
    api_key TEXT,
    model TEXT NOT NULL,
    is_default INTEGER DEFAULT 0,
    enabled INTEGER DEFAULT 1,
    temperature REAL DEFAULT 0.2,
    timeout_seconds INTEGER DEFAULT 60,
    last_test_status TEXT,
    last_test_message TEXT,
    last_test_at TEXT,
    created_at TEXT,
    updated_at TEXT
);

CREATE TABLE IF NOT EXISTS repo_scan_templates (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    repo_id INTEGER NOT NULL,
    template_version INTEGER DEFAULT 1,
    status TEXT DEFAULT 'pending_review',
    content_json TEXT NOT NULL,
    summary_cn TEXT,
    confidence INTEGER DEFAULT 0,
    source_ai_config_id INTEGER,
    created_at TEXT,
    updated_at TEXT,
    approved_at TEXT,
    notes TEXT,
    FOREIGN KEY (repo_id) REFERENCES repos(id),
    FOREIGN KEY (source_ai_config_id) REFERENCES ai_configs(id)
);

CREATE TABLE IF NOT EXISTS repo_scan_runs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    repo_id INTEGER NOT NULL,
    use_ai INTEGER DEFAULT 0,
    template_id INTEGER,
    status TEXT,
    progress_percent INTEGER DEFAULT 0,
    current_file TEXT,
    total_files INTEGER DEFAULT 0,
    processed_files INTEGER DEFAULT 0,
    total_images INTEGER DEFAULT 0,
    downloaded_images INTEGER DEFAULT 0,
    error_count INTEGER DEFAULT 0,
    scanned_files INTEGER DEFAULT 0,
    prompt_candidates INTEGER DEFAULT 0,
    pair_candidates INTEGER DEFAULT 0,
    prompt_pairs_added INTEGER DEFAULT 0,
    pair_candidates_added INTEGER DEFAULT 0,
    images_added INTEGER DEFAULT 0,
    summary TEXT,
    error TEXT,
    options_json TEXT,
    result_json TEXT,
    started_at TEXT,
    finished_at TEXT,
    updated_at TEXT,
    cancel_requested INTEGER DEFAULT 0,
    created_at TEXT,
    FOREIGN KEY (repo_id) REFERENCES repos(id),
    FOREIGN KEY (template_id) REFERENCES repo_scan_templates(id)
);

CREATE TABLE IF NOT EXISTS agent_threads (
    id TEXT PRIMARY KEY,
    title TEXT,
    status TEXT DEFAULT 'active',
    created_at TEXT,
    updated_at TEXT
);

CREATE TABLE IF NOT EXISTS agent_messages (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    thread_id TEXT NOT NULL,
    role TEXT NOT NULL,
    content TEXT NOT NULL,
    sources_json TEXT,
    actions_json TEXT,
    created_at TEXT,
    FOREIGN KEY (thread_id) REFERENCES agent_threads(id)
);

CREATE TABLE IF NOT EXISTS agent_memories (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    memory_type TEXT NOT NULL,
    scope TEXT DEFAULT 'global',
    repo_id INTEGER,
    content TEXT NOT NULL,
    content_json TEXT,
    status TEXT DEFAULT 'pending_review',
    confidence INTEGER DEFAULT 0,
    source TEXT,
    created_at TEXT,
    updated_at TEXT,
    last_used_at TEXT,
    FOREIGN KEY (repo_id) REFERENCES repos(id)
);

CREATE VIRTUAL TABLE IF NOT EXISTS agent_memory_fts
USING fts5(content, memory_id UNINDEXED);

CREATE TABLE IF NOT EXISTS scheduled_tasks (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    task_type TEXT NOT NULL DEFAULT 'github_incremental_search',
    status TEXT NOT NULL DEFAULT 'paused',
    schedule_type TEXT NOT NULL,
    interval_minutes INTEGER,
    daily_time TEXT,
    weekly_day INTEGER,
    weekly_time TEXT,
    timezone TEXT DEFAULT 'Asia/Shanghai',
    categories TEXT,
    keywords TEXT,
    per_keyword_limit INTEGER DEFAULT 5,
    allow_anonymous INTEGER DEFAULT 0,
    next_run_at TEXT,
    last_run_at TEXT,
    last_finished_at TEXT,
    last_status TEXT,
    last_summary TEXT,
    last_error TEXT,
    running INTEGER DEFAULT 0,
    created_at TEXT,
    updated_at TEXT
);

CREATE TABLE IF NOT EXISTS task_runs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    task_id INTEGER,
    task_name TEXT,
    task_type TEXT,
    trigger_type TEXT,
    status TEXT,
    started_at TEXT,
    finished_at TEXT,
    duration_ms INTEGER DEFAULT 0,
    summary TEXT,
    error TEXT,
    result_json TEXT,
    created_at TEXT,
    FOREIGN KEY (task_id) REFERENCES scheduled_tasks(id)
);

CREATE TABLE IF NOT EXISTS prompt_candidates (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    repo_id INTEGER,
    repo_name TEXT,
    repo_url TEXT,
    source_page_url TEXT,
    source_file TEXT,
    source_heading TEXT,
    line_start INTEGER DEFAULT 0,
    line_end INTEGER DEFAULT 0,
    original_prompt TEXT,
    prompt_type TEXT,
    context TEXT,
    content_hash TEXT,
    status TEXT DEFAULT 'candidate',
    created_at TEXT,
    FOREIGN KEY (repo_id) REFERENCES repos(id)
);

CREATE TABLE IF NOT EXISTS image_candidates (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    repo_id INTEGER,
    source_page_url TEXT,
    source_file TEXT,
    source_heading TEXT,
    line_start INTEGER DEFAULT 0,
    image_original_url TEXT,
    image_resolved_url TEXT,
    image_local_path TEXT,
    thumbnail_local_path TEXT,
    image_hash TEXT,
    width INTEGER,
    height INTEGER,
    file_size INTEGER,
    alt_text TEXT,
    caption TEXT,
    context TEXT,
    filename TEXT,
    asset_id INTEGER,
    status TEXT DEFAULT 'candidate',
    created_at TEXT,
    FOREIGN KEY (repo_id) REFERENCES repos(id),
    FOREIGN KEY (asset_id) REFERENCES assets(id)
);

CREATE TABLE IF NOT EXISTS pair_candidates (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    repo_id INTEGER,
    repo_name TEXT,
    repo_url TEXT,
    source_page_url TEXT,
    source_file TEXT,
    source_heading TEXT,
    prompt_candidate_id INTEGER,
    image_candidate_id INTEGER,
    original_prompt TEXT,
    image_original_url TEXT,
    image_local_path TEXT,
    image_hash TEXT,
    match_type TEXT,
    match_score INTEGER DEFAULT 0,
    structural_score INTEGER DEFAULT 0,
    distance_score INTEGER DEFAULT 0,
    filename_score INTEGER DEFAULT 0,
    semantic_score INTEGER DEFAULT 0,
    penalty_score INTEGER DEFAULT 0,
    evidence TEXT,
    review_status TEXT DEFAULT 'pending_review',
    review_reason TEXT,
    selection_status TEXT DEFAULT 'pending_review',
    created_pair_id INTEGER,
    created_at TEXT,
    updated_at TEXT,
    FOREIGN KEY (repo_id) REFERENCES repos(id),
    FOREIGN KEY (prompt_candidate_id) REFERENCES prompt_candidates(id),
    FOREIGN KEY (image_candidate_id) REFERENCES image_candidates(id),
    FOREIGN KEY (created_pair_id) REFERENCES prompt_effect_pairs(id)
);

CREATE TABLE IF NOT EXISTS annotation_runs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    status TEXT DEFAULT 'queued',
    total_items INTEGER DEFAULT 0,
    processed_items INTEGER DEFAULT 0,
    created_suggestions INTEGER DEFAULT 0,
    current_pair_id INTEGER,
    ai_config_id INTEGER,
    options_json TEXT,
    error TEXT,
    created_at TEXT,
    started_at TEXT,
    finished_at TEXT,
    updated_at TEXT,
    cancel_requested INTEGER DEFAULT 0,
    FOREIGN KEY (current_pair_id) REFERENCES prompt_effect_pairs(id),
    FOREIGN KEY (ai_config_id) REFERENCES ai_configs(id)
);

CREATE TABLE IF NOT EXISTS prompt_pair_annotation_suggestions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    run_id INTEGER,
    pair_id INTEGER NOT NULL,
    status TEXT DEFAULT 'pending_review',
    prompt_language TEXT,
    suggested_cn_explanation TEXT,
    suggested_tags_json TEXT,
    image_type_cn TEXT,
    reason_cn TEXT,
    confidence INTEGER DEFAULT 0,
    error TEXT,
    created_at TEXT,
    updated_at TEXT,
    accepted_at TEXT,
    FOREIGN KEY (run_id) REFERENCES annotation_runs(id),
    FOREIGN KEY (pair_id) REFERENCES prompt_effect_pairs(id)
);

CREATE INDEX IF NOT EXISTS idx_repos_category ON repos(category);
CREATE INDEX IF NOT EXISTS idx_repos_status ON repos(status);
CREATE INDEX IF NOT EXISTS idx_pairs_category ON prompt_effect_pairs(category);
CREATE INDEX IF NOT EXISTS idx_pairs_selection ON prompt_effect_pairs(selection_status);
CREATE INDEX IF NOT EXISTS idx_pairs_repo_id ON prompt_effect_pairs(repo_id);
CREATE INDEX IF NOT EXISTS idx_assets_repo_id ON assets(repo_id);
CREATE INDEX IF NOT EXISTS idx_ai_configs_provider ON ai_configs(provider);
CREATE INDEX IF NOT EXISTS idx_ai_configs_default ON ai_configs(is_default, enabled);
CREATE INDEX IF NOT EXISTS idx_repo_scan_templates_repo_id ON repo_scan_templates(repo_id);
CREATE INDEX IF NOT EXISTS idx_repo_scan_templates_status ON repo_scan_templates(status);
CREATE INDEX IF NOT EXISTS idx_repo_scan_runs_repo_id ON repo_scan_runs(repo_id);
CREATE INDEX IF NOT EXISTS idx_agent_messages_thread_id ON agent_messages(thread_id);
CREATE INDEX IF NOT EXISTS idx_agent_memories_status ON agent_memories(status);
CREATE INDEX IF NOT EXISTS idx_agent_memories_type ON agent_memories(memory_type);
CREATE INDEX IF NOT EXISTS idx_scheduled_tasks_status_next ON scheduled_tasks(status, next_run_at);
CREATE INDEX IF NOT EXISTS idx_task_runs_task_id ON task_runs(task_id);
CREATE INDEX IF NOT EXISTS idx_task_runs_created_at ON task_runs(created_at);
CREATE INDEX IF NOT EXISTS idx_prompt_candidates_repo_id ON prompt_candidates(repo_id);
CREATE INDEX IF NOT EXISTS idx_image_candidates_repo_id ON image_candidates(repo_id);
CREATE INDEX IF NOT EXISTS idx_pair_candidates_repo_id ON pair_candidates(repo_id);
CREATE INDEX IF NOT EXISTS idx_pair_candidates_status ON pair_candidates(review_status);
CREATE INDEX IF NOT EXISTS idx_annotation_runs_status ON annotation_runs(status);
CREATE INDEX IF NOT EXISTS idx_annotation_suggestions_pair_id ON prompt_pair_annotation_suggestions(pair_id);
CREATE INDEX IF NOT EXISTS idx_annotation_suggestions_status ON prompt_pair_annotation_suggestions(status);
CREATE UNIQUE INDEX IF NOT EXISTS idx_prompt_candidates_unique
    ON prompt_candidates(repo_id, source_file, line_start, content_hash);
CREATE UNIQUE INDEX IF NOT EXISTS idx_image_candidates_unique
    ON image_candidates(repo_id, source_file, image_resolved_url);
CREATE UNIQUE INDEX IF NOT EXISTS idx_pair_candidates_unique
    ON pair_candidates(repo_id, source_file, original_prompt, image_original_url);
"""


DEFAULT_KEYWORDS: Sequence[Tuple[str, str]] = (
    ("web ui prompt", "web_ui_prompt"),
    ("frontend ui prompt", "web_ui_prompt"),
    ("landing page prompt", "web_ui_prompt"),
    ("dashboard ui prompt", "web_ui_prompt"),
    ("SaaS UI prompt", "web_ui_prompt"),
    ("website design prompt", "web_ui_prompt"),
    ("AI generated UI prompt", "web_ui_prompt"),
    ("shadcn ui prompt", "web_ui_prompt"),
    ("tailwind ui prompt", "web_ui_prompt"),
    ("frontend design prompt", "web_ui_prompt"),
    ("UI design prompt engineering", "web_ui_prompt"),
    ("design system prompt", "web_ui_prompt"),
    ("component generation prompt", "web_ui_prompt"),
    ("image generation prompt", "image_generation_prompt"),
    ("text to image prompt", "image_generation_prompt"),
    ("AI image prompt", "image_generation_prompt"),
    ("GPT Image prompt", "image_generation_prompt"),
    ("GPT Image 2 prompt", "image_generation_prompt"),
    ("product image prompt", "image_generation_prompt"),
    ("poster prompt", "image_generation_prompt"),
    ("commercial poster prompt", "image_generation_prompt"),
    ("visual design prompt", "image_generation_prompt"),
    ("prompt effect examples", "image_generation_prompt"),
    ("product photography prompt", "image_generation_prompt"),
    ("AI image prompt examples", "image_generation_prompt"),
    ("image editing prompt", "image_editing_prompt"),
    ("image to image prompt", "image_editing_prompt"),
    ("AI image editing prompt", "image_editing_prompt"),
    ("background replacement prompt", "image_editing_prompt"),
    ("object removal prompt", "image_editing_prompt"),
    ("image retouch prompt", "image_editing_prompt"),
    ("photo editing prompt", "image_editing_prompt"),
    ("GPT Image editing prompt", "image_editing_prompt"),
    ("image variation prompt", "image_editing_prompt"),
    ("image style transfer prompt", "image_editing_prompt"),
    ("text to video prompt", "video_generation_prompt"),
    ("image to video prompt", "video_generation_prompt"),
    ("AI video prompt", "video_generation_prompt"),
    ("video generation prompt", "video_generation_prompt"),
    ("cinematic prompt", "video_generation_prompt"),
    ("product video prompt", "video_generation_prompt"),
    ("commercial video prompt", "video_generation_prompt"),
    ("short video prompt", "video_generation_prompt"),
    ("storyboard prompt", "video_generation_prompt"),
    ("video ad prompt", "video_generation_prompt"),
    ("Veo prompt", "video_generation_prompt"),
    ("Kling prompt", "video_generation_prompt"),
    ("Runway prompt", "video_generation_prompt"),
    ("Seedance prompt", "video_generation_prompt"),
    ("Wan video prompt", "video_generation_prompt"),
)


PROMPT_PAIR_EXTRA_COLUMNS: Sequence[Tuple[str, str]] = (
    ("pair_relation_type", "TEXT DEFAULT 'unclear'"),
    ("pair_evidence", "TEXT"),
    ("pair_confidence", "INTEGER DEFAULT 0"),
    ("generated_by", "TEXT"),
)


REPO_SCAN_RUN_EXTRA_COLUMNS: Sequence[Tuple[str, str]] = (
    ("progress_percent", "INTEGER DEFAULT 0"),
    ("current_file", "TEXT"),
    ("total_files", "INTEGER DEFAULT 0"),
    ("processed_files", "INTEGER DEFAULT 0"),
    ("total_images", "INTEGER DEFAULT 0"),
    ("downloaded_images", "INTEGER DEFAULT 0"),
    ("error_count", "INTEGER DEFAULT 0"),
    ("options_json", "TEXT"),
    ("result_json", "TEXT"),
    ("started_at", "TEXT"),
    ("finished_at", "TEXT"),
    ("updated_at", "TEXT"),
    ("cancel_requested", "INTEGER DEFAULT 0"),
)


@contextmanager
def get_connection() -> Iterator[sqlite3.Connection]:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


def init_db() -> None:
    with get_connection() as conn:
        conn.executescript(SCHEMA_SQL)
        existing_columns = {row["name"] for row in conn.execute("PRAGMA table_info(prompt_effect_pairs)").fetchall()}
        for name, definition in PROMPT_PAIR_EXTRA_COLUMNS:
            if name not in existing_columns:
                conn.execute(f"ALTER TABLE prompt_effect_pairs ADD COLUMN {name} {definition}")
        run_columns = {row["name"] for row in conn.execute("PRAGMA table_info(repo_scan_runs)").fetchall()}
        for name, definition in REPO_SCAN_RUN_EXTRA_COLUMNS:
            if name not in run_columns:
                conn.execute(f"ALTER TABLE repo_scan_runs ADD COLUMN {name} {definition}")
        stale_now = utc_now()
        conn.execute(
            """
            UPDATE repo_scan_runs
            SET status = 'failed',
                error = COALESCE(error, '后端服务重启，未完成扫描任务已标记失败。'),
                finished_at = COALESCE(finished_at, ?),
                updated_at = ?
            WHERE status IN ('queued', 'running', 'cancel_requested')
            """,
            (stale_now, stale_now),
        )
        now = utc_now()
        for keyword, category in DEFAULT_KEYWORDS:
            conn.execute(
                """
                INSERT OR IGNORE INTO search_state
                    (keyword, category, last_success_search_at, safety_overlap_days, last_result_count, status, updated_at)
                VALUES (?, ?, NULL, 3, 0, 'active', ?)
                """,
                (keyword, category, now),
            )


def row_to_dict(row: Optional[sqlite3.Row]) -> Optional[Dict[str, Any]]:
    if row is None:
        return None
    return {key: row[key] for key in row.keys()}


def rows_to_dicts(rows: Iterable[sqlite3.Row]) -> List[Dict[str, Any]]:
    return [row_to_dict(row) or {} for row in rows]


def fetch_one(sql: str, params: Sequence[Any] = ()) -> Optional[Dict[str, Any]]:
    with get_connection() as conn:
        row = conn.execute(sql, params).fetchone()
        return row_to_dict(row)


def fetch_all(sql: str, params: Sequence[Any] = ()) -> List[Dict[str, Any]]:
    with get_connection() as conn:
        rows = conn.execute(sql, params).fetchall()
        return rows_to_dicts(rows)


def execute(sql: str, params: Sequence[Any] = ()) -> int:
    with get_connection() as conn:
        cursor = conn.execute(sql, params)
        return int(cursor.lastrowid or 0)


def execute_many(sql: str, rows: Iterable[Sequence[Any]]) -> None:
    with get_connection() as conn:
        conn.executemany(sql, rows)


def paginate(base_sql: str, count_sql: str, params: Sequence[Any], page: int, page_size: int) -> Dict[str, Any]:
    page = max(page, 1)
    page_size = min(max(page_size, 1), 100)
    offset = (page - 1) * page_size
    with get_connection() as conn:
        total = conn.execute(count_sql, params).fetchone()[0]
        items = conn.execute(f"{base_sql} LIMIT ? OFFSET ?", (*params, page_size, offset)).fetchall()
    return {
        "items": rows_to_dicts(items),
        "page": page,
        "page_size": page_size,
        "total": int(total),
    }
