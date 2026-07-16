import os
import uuid
from fastapi import FastAPI, Depends, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse, FileResponse
from pydantic import BaseModel
from sqlalchemy.orm import Session

from .db import SessionLocal, init_db
from .repositories.sqlite_repositories import (
    SQLiteConversationRepository,
    SQLiteMemoryRepository,
    SQLiteModelRepository,
    SQLiteArtifactRepository,
    SQLiteSettingRepository
)
from .services.intent_service import IntentService
from .services.capability_service import CapabilityService
from .services.memory.memory_service import MemoryService
from .services.context_builder import ContextBuilder
from .services.model_selector import ModelSelector
from .services.planner import Planner
from .services.execution_engine import ExecutionEngine
from .executors.python_executor import PythonExecutor
from .providers.ollama_provider import OllamaProvider
from .services.model_service import ModelService
from .core.orchestrator import Orchestrator

# Initialize database
init_db()

app = FastAPI(title="AI-Native Personal Assistant Platform")

# CORS middleware config to allow frontend to communicate
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # For local development simplicity
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Dependency to get db session
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

@app.on_event("startup")
def startup_event():
    db = SessionLocal()
    try:
        model_repo = SQLiteModelRepository(db)
        setting_repo = SQLiteSettingRepository(db)
        ms = ModelService(model_repo, setting_repo)
        ms.preload_first_run_models()
    finally:
        db.close()

@app.on_event("shutdown")
def shutdown_event():
    db = SessionLocal()
    try:
        model_repo = SQLiteModelRepository(db)
        setting_repo = SQLiteSettingRepository(db)
        ms = ModelService(model_repo, setting_repo)
        ms.unload_other_models(None)
    finally:
        db.close()

# Ensure artifacts directory is ready
ARTIFACTS_DIR = "C:/Users/StephenPhilipKallara/Mimir/artifacts"
os.makedirs(ARTIFACTS_DIR, exist_ok=True)

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

@app.post("/api/chat")
def chat(req: ChatRequest):
    """SSE endpoint streaming intent, capability checks, model loading, chat content, and script execution logs."""
    db = SessionLocal()
    # Wire up repositories
    conv_repo = SQLiteConversationRepository(db)
    mem_repo = SQLiteMemoryRepository(db)
    model_repo = SQLiteModelRepository(db)
    art_repo = SQLiteArtifactRepository(db)
    setting_repo = SQLiteSettingRepository(db)
    
    # Wire up services
    intent_service = IntentService()
    capability_service = CapabilityService()
    memory_service = MemoryService(mem_repo, conv_repo, setting_repo)
    context_builder = ContextBuilder(memory_service)
    model_selector = ModelSelector()
    provider = OllamaProvider()
    planner = Planner()
    
    # Wire up executor & engine
    python_executor = PythonExecutor(art_repo, setting_repo)
    execution_engine = ExecutionEngine(art_repo)
    execution_engine.register_executor(python_executor)
    
    # Model service
    ms = ModelService(model_repo, setting_repo)
    
    # Instantiate Orchestrator
    orchestrator = Orchestrator(
        intent_service=intent_service,
        capability_service=capability_service,
        context_builder=context_builder,
        model_selector=model_selector,
        provider=provider,
        execution_engine=execution_engine,
        planner=planner,
        model_service=ms,
        conversation_repo=conv_repo,
        model_repo=model_repo
    )
    
    # Ensure conversation exists
    conv = conv_repo.get_by_id(req.conversation_id)
    if not conv:
        conv_repo.create(req.conversation_id, "New Chat", 1)

    return StreamingResponse(
        stream_with_cleanup(orchestrator.process_prompt(req.conversation_id, req.prompt), db),
        media_type="text/event-stream"
    )

@app.get("/api/conversations")
def get_conversations(db: Session = Depends(get_db)):
    conv_repo = SQLiteConversationRepository(db)
    convs = conv_repo.get_all()
    return [{
        "id": c.id,
        "title": c.title,
        "updated_at": c.updated_at
    } for c in convs]

@app.post("/api/conversations")
def create_conversation(db: Session = Depends(get_db)):
    conv_repo = SQLiteConversationRepository(db)
    conv_id = str(uuid.uuid4())
    conv_repo.create(conv_id, "New Chat", 1)
    return {"id": conv_id, "title": "New Chat"}

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
def get_settings(db: Session = Depends(get_db)):
    setting_repo = SQLiteSettingRepository(db)
    return setting_repo.get_all()

@app.post("/api/settings")
def update_settings(settings: SettingsUpdate, db: Session = Depends(get_db)):
    setting_repo = SQLiteSettingRepository(db)
    for key, val in settings.dict().items():
        setting_repo.save(key, val)
    
    # Also sync user name in User table
    mem_repo = SQLiteMemoryRepository(db)
    mem_repo.save_user_name(1, settings.user_name)

    return {"status": "success"}

@app.get("/api/system/status")
def get_system_status(db: Session = Depends(get_db)):
    """Fetch hardware performance specifications, active download states, and active model lists."""
    model_repo = SQLiteModelRepository(db)
    setting_repo = SQLiteSettingRepository(db)
    ms = ModelService(model_repo, setting_repo)
    
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
    file_path = os.path.join(ARTIFACTS_DIR, filename)
    if not os.path.exists(file_path):
        raise HTTPException(status_code=404, detail="File not found")
    return FileResponse(file_path, filename=filename)
