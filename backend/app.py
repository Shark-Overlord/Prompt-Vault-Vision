from __future__ import annotations

from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from database import PROJECT_ROOT, init_db
from agents.runtime import ensure_agent_runtime
from routes import agent, ai_configs, annotations, assets, auth, dashboard, export, pair_candidates, prompt_pairs, repo_templates, repos, scheduled_tasks, search, tags
from routes import repo_scan_runs
from services.annotation_service import start_annotation_worker, stop_annotation_worker
from services.repo_scan_job_service import start_repo_scan_worker, stop_repo_scan_worker
from services.scheduler_service import start_scheduler, stop_scheduler


init_db()
ensure_agent_runtime()


@asynccontextmanager
async def lifespan(app: FastAPI):
    start_scheduler()
    start_repo_scan_worker()
    start_annotation_worker()
    try:
        yield
    finally:
        await stop_annotation_worker()
        await stop_repo_scan_worker()
        await stop_scheduler()


app = FastAPI(
    title="Visual Prompt Library API",
    description="本地视觉 Prompt 资产管理器后端 API",
    version="0.1.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://127.0.0.1:5173", "http://localhost:5173", "http://127.0.0.1:4173", "http://localhost:4173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

assets_dir = PROJECT_ROOT / "assets"
assets_dir.mkdir(parents=True, exist_ok=True)
app.mount("/assets", StaticFiles(directory=assets_dir), name="assets")

app.include_router(dashboard.router)
app.include_router(auth.router)
app.include_router(ai_configs.router)
app.include_router(agent.router)
app.include_router(annotations.router)
app.include_router(repos.router)
app.include_router(repo_scan_runs.router)
app.include_router(repo_templates.router)
app.include_router(prompt_pairs.router)
app.include_router(pair_candidates.router)
app.include_router(assets.router)
app.include_router(search.router)
app.include_router(scheduled_tasks.router)
app.include_router(export.router)
app.include_router(tags.router)


@app.get("/api/health")
def health():
    return {"status": "ok", "project_root": str(PROJECT_ROOT)}
