import uuid
from typing import Optional, Generator

from fastapi import FastAPI, Depends, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse, FileResponse, HTMLResponse
from pydantic import BaseModel
from sqlalchemy.orm import Session

from config.paths import get_paths
from config.settings import get_settings
from runtime.runtime_coordinator import get_runtime

from .db import SessionLocal, ensure_db_ready
from .repositories.sqlite_repositories import (
    SQLiteConversationRepository,
    SQLiteModelRepository,
    SQLiteSettingRepository,
    SQLiteModelCatalogRepository,
    SQLiteArtifactRepository,
)
from .services.model_service import ModelService
from .pipeline_factory import build_pipeline

# Architectural decision: do NOT init DB or contact Ollama at import time.
# Config is imported above (cheap); dirs/DB/plugins load in startup_event.

app = FastAPI(title="AI-Native Personal Assistant Platform")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # For local development simplicity
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


def get_db():
    ensure_db_ready()
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


@app.get("/", response_class=HTMLResponse)
def root():
    """
    Backend has no SPA at /. Point operators to the UI and API docs.
    The product UI is served by Vite on :5173.
    """
    return """<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>Mimir API</title>
  <style>
    :root { color-scheme: dark; }
    body {
      margin: 0; min-height: 100vh; display: grid; place-items: center;
      font-family: "Segoe UI", system-ui, sans-serif;
      background: #0f1115; color: #e8eaed;
    }
    main {
      width: min(36rem, 92vw); padding: 2rem;
      border: 1px solid #2a2f3a; border-radius: 12px; background: #161a22;
    }
    h1 { margin: 0 0 0.35rem; font-size: 1.6rem; }
    p { margin: 0 0 1.25rem; color: #9aa3b2; line-height: 1.5; }
    a {
      display: inline-block; margin: 0.35rem 0.5rem 0.35rem 0;
      padding: 0.55rem 0.9rem; border-radius: 8px; text-decoration: none;
      background: #3b82f6; color: white; font-weight: 600;
    }
    a.secondary { background: #2a2f3a; color: #e8eaed; }
    code { color: #93c5fd; }
  </style>
</head>
<body>
  <main>
    <h1>Mimir API</h1>
    <p>
      This is the FastAPI backend. The chat UI is not served from port 8000.
      Start the frontend (<code>npm run dev</code> in <code>frontend/</code>)
      or use <code>python run_platform.py</code> from the repo root.
    </p>
    <a href="http://localhost:5173">Open Mimir UI</a>
    <a class="secondary" href="/docs">API Docs (Swagger)</a>
    <a class="secondary" href="/api/system/status">System Status</a>
  </main>
</body>
</html>"""


@app.on_event("startup")
def startup_event():
    """
    Fast startup path:
    - configuration (already loaded via imports)
    - ensure directories
    - DB schema/seed only when needed for local metadata
    - installed model metadata from SQLite (no Ollama)
    - plugin manifest metadata (JSON / builtins, no code import)
    Never downloads or preloads models.
    """
    settings = get_settings()
    runtime = get_runtime()

    # Schema + seed so we can read local installed_models rows
    ensure_db_ready()

    db = SessionLocal()
    try:
        model_repo = SQLiteModelRepository(db)
        setting_repo = SQLiteSettingRepository(db)
        catalog_repo = SQLiteModelCatalogRepository(db)
        ms = ModelService(
            model_repo,
            setting_repo,
            catalog_repo=catalog_repo,
            ollama_url=settings.ollama_url,
        )
        runtime.bind_model_service(ms)

        # Optional legacy preload — disabled by default (feature flag)
        if settings.enable_startup_model_preload:
            ms.preload_first_run_models()
        if settings.enable_startup_ollama_sync:
            ms.sync_models_to_db()

        runtime.start()
    finally:
        db.close()
        # Drop request-scoped service; rebound per request that needs Ollama
        runtime.bind_model_service(None)


@app.on_event("shutdown")
def shutdown_event():
    """Best-effort idle cleanup. Ollama unload only if a service can be bound."""
    settings = get_settings()
    if not settings.enable_idle_model_unload:
        return

    ensure_db_ready()
    db = SessionLocal()
    try:
        runtime = get_runtime()
        model_repo = SQLiteModelRepository(db)
        setting_repo = SQLiteSettingRepository(db)
        ms = ModelService(model_repo, setting_repo, ollama_url=settings.ollama_url)
        runtime.bind_model_service(ms)
        runtime.unload_other_models(None)
    except Exception:
        pass
    finally:
        db.close()


class ChatRequest(BaseModel):
    conversation_id: str
    prompt: str


class SettingsUpdate(BaseModel):
    user_name: str
    personality: str
    theme: str


def stream_with_cleanup(generator, db: Session):
    try:
        for chunk in generator:
            yield chunk
    finally:
        db.close()


def _build_runtime_for_request(db: Session):
    """
    Bind a request-scoped ModelService to the process-wide RuntimeCoordinator.

    Used by non-chat endpoints (e.g. /api/system/status) that need Ollama
    access but don't require the full inference pipeline.
    For the chat endpoint, use pipeline_factory.build_pipeline() directly.
    """
    settings = get_settings()
    runtime = get_runtime()
    model_repo = SQLiteModelRepository(db)
    setting_repo = SQLiteSettingRepository(db)
    catalog_repo = SQLiteModelCatalogRepository(db)
    ms = ModelService(model_repo, setting_repo, catalog_repo=catalog_repo, ollama_url=settings.ollama_url)
    runtime.bind_model_service(ms)
    return runtime, model_repo, setting_repo, catalog_repo


@app.post("/api/chat")
def chat(req: ChatRequest):
    """
    SSE endpoint — streams intent classification, model selection, LLM content,
    Python execution results, and download progress events.

    Pipeline is constructed by pipeline_factory.build_pipeline() to keep this
    endpoint thin. Phase 4 will swap build_pipeline() for build_agent_runtime().
    """
    ensure_db_ready()
    db = SessionLocal()
    paths = get_paths()
    runtime = get_runtime()

    # Full pipeline construction delegated to factory
    orchestrator = build_pipeline(db, paths, runtime)

    # Ensure conversation record exists before streaming starts
    from .repositories.sqlite_repositories import SQLiteConversationRepository
    conv_repo = SQLiteConversationRepository(db)
    if not conv_repo.get_by_id(req.conversation_id):
        conv_repo.create(req.conversation_id, "New Chat", 1)

    return StreamingResponse(
        stream_with_cleanup(orchestrator.process_prompt(req.conversation_id, req.prompt), db),
        media_type="text/event-stream",
    )


@app.get("/api/conversations")
def get_conversations(db: Session = Depends(get_db)):
    conv_repo = SQLiteConversationRepository(db)
    convs = conv_repo.get_all()
    return [{
        "id": c.id,
        "title": c.title,
        "updated_at": c.updated_at,
        "project_id": c.project_id
    } for c in convs]


@app.post("/api/conversations")
def create_conversation(project_id: Optional[str] = None, db: Session = Depends(get_db)):
    if not project_id or project_id == "null":
        project_id = None
    conv_repo = SQLiteConversationRepository(db)
    conv_id = str(uuid.uuid4())
    conv_repo.create(conv_id, "New Chat", 1, project_id)
    return {"id": conv_id, "title": "New Chat", "project_id": project_id}


@app.post("/api/conversations/{conv_id}/project")
def update_conversation_project(conv_id: str, project_id: Optional[str] = None, db: Session = Depends(get_db)):
    if not project_id or project_id == "null":
        project_id = None
    conv_repo = SQLiteConversationRepository(db)
    conv_repo.update_project(conv_id, project_id)
    return {"status": "success"}


@app.delete("/api/conversations/{conv_id}")
def delete_conversation(conv_id: str, db: Session = Depends(get_db)):
    conv_repo = SQLiteConversationRepository(db)
    deleted = conv_repo.delete(conv_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Conversation not found")
    return {"status": "success"}


@app.get("/api/conversations/{conv_id}/messages")
def get_messages(conv_id: str, db: Session = Depends(get_db)):
    conv_repo = SQLiteConversationRepository(db)
    art_repo = SQLiteArtifactRepository(db)
    messages = conv_repo.get_messages(conv_id)

    result = []
    for msg in messages:
        artifacts = art_repo.get_by_message_id(msg.id)
        result.append({
            "id": msg.id,
            "sender": msg.sender,
            "content": msg.content,
            "created_at": msg.created_at,
            "artifacts": [{
                "id": a.id,
                "file_name": a.file_name,
                "file_path": a.file_path,
                "file_type": a.file_type,
                "file_size": a.file_size
            } for a in artifacts]
        })
    return result


@app.get("/api/settings")
def get_settings_api(db: Session = Depends(get_db)):
    setting_repo = SQLiteSettingRepository(db)
    return setting_repo.get_all()


@app.post("/api/settings")
def update_settings(settings: SettingsUpdate, db: Session = Depends(get_db)):
    setting_repo = SQLiteSettingRepository(db)
    for key, val in settings.dict().items():
        setting_repo.save(key, val)

    mem_repo = SQLiteMemoryRepository(db)
    mem_repo.save_user_name(1, settings.user_name)

    return {"status": "success"}


@app.get("/api/system/status")
def get_system_status(db: Session = Depends(get_db)):
    """Fetch hardware performance specifications, active download states, and active model lists."""
    runtime, model_repo, _setting_repo, _catalog_repo = _build_runtime_for_request(db)
    ms = runtime.model_service

    hw = ms.detect_hardware()
    ms.sync_models_to_db()

    models = model_repo.get_all_installed()
    downloads = model_repo.get_all_downloads()

    return {
        "hardware": hw,
        "installed_models": [{
            "name": m.name,
            "size": m.size,
            "status": m.status
        } for m in models],
        "downloads": [{
            "model_name": dl.model_name,
            "progress": dl.progress,
            "status": dl.status,
            "error": dl.error
        } for dl in downloads]
    }


@app.get("/artifacts/{filename}")
def get_artifact(filename: str):
    """Serve generated file downloads (Excel sheets, CSVs, charts)."""
    artifacts_dir = get_paths().artifacts_dir
    file_path = artifacts_dir / filename
    # Prevent path traversal
    try:
        file_path.resolve().relative_to(artifacts_dir.resolve())
    except ValueError:
        raise HTTPException(status_code=404, detail="File not found")
    if not file_path.is_file():
        raise HTTPException(status_code=404, detail="File not found")
    return FileResponse(str(file_path), filename=filename)
