import os
import uuid
from fastapi import FastAPI, Depends, HTTPException, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from sqlalchemy.orm import Session
from typing import List, Optional

from .db import SessionLocal, init_db, Conversation, Message, GeneratedArtifact, Setting, User, Download, InstalledModel
from .core.orchestrator import Orchestrator
from .services.model_service import ModelService

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

orchestrator = Orchestrator()
model_service = ModelService()

@app.on_event("startup")
def startup_event():
    db = SessionLocal()
    try:
        model_service.preload_first_run_models(db)
    finally:
        db.close()

@app.on_event("shutdown")
def shutdown_event():
    # Unload all loaded models to free RAM
    model_service.unload_other_models(None)

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

@app.post("/api/chat")
def chat(req: ChatRequest, db: Session = Depends(get_db)):
    """SSE endpoint streaming intent, capability checks, model loading, chat content, and script execution logs."""
    # Ensure conversation exists
    conv = db.query(Conversation).filter(Conversation.id == req.conversation_id).first()
    if not conv:
        conv = Conversation(id=req.conversation_id, title="New Chat", user_id=1)
        db.add(conv)
        db.commit()

    return StreamingResponse(
        orchestrator.process_prompt(db, req.conversation_id, req.prompt),
        media_type="text/event-stream"
    )

@app.get("/api/conversations")
def get_conversations(db: Session = Depends(get_db)):
    convs = db.query(Conversation).order_by(Conversation.updated_at.desc()).all()
    return [{
        "id": c.id,
        "title": c.title,
        "updated_at": c.updated_at
    } for c in convs]

@app.post("/api/conversations")
def create_conversation(db: Session = Depends(get_db)):
    conv_id = str(uuid.uuid4())
    conv = Conversation(id=conv_id, title="New Chat", user_id=1)
    db.add(conv)
    db.commit()
    return {"id": conv_id, "title": "New Chat"}

@app.delete("/api/conversations/{conv_id}")
def delete_conversation(conv_id: str, db: Session = Depends(get_db)):
    conv = db.query(Conversation).filter(Conversation.id == conv_id).first()
    if not conv:
        raise HTTPException(status_code=404, detail="Conversation not found")
    db.delete(conv)
    db.commit()
    return {"status": "success"}

@app.get("/api/conversations/{conv_id}/messages")
def get_messages(conv_id: str, db: Session = Depends(get_db)):
    messages = db.query(Message).filter(Message.conversation_id == conv_id).order_by(Message.created_at.asc()).all()
    
    result = []
    for msg in messages:
        artifacts = db.query(GeneratedArtifact).filter(GeneratedArtifact.message_id == msg.id).all()
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
    settings = db.query(Setting).all()
    return {s.key: s.value for s in settings}

@app.post("/api/settings")
def update_settings(settings: SettingsUpdate, db: Session = Depends(get_db)):
    for key, val in settings.dict().items():
        s = db.query(Setting).filter(Setting.key == key).first()
        if s:
            s.value = val
        else:
            db.add(Setting(key=key, value=val))
    
    # Also sync user name in User table
    user = db.query(User).filter(User.id == 1).first()
    if user:
        user.name = settings.user_name

    db.commit()
    return {"status": "success"}

@app.get("/api/system/status")
def get_system_status(db: Session = Depends(get_db)):
    """Fetch hardware performance specifications, active download states, and active model lists."""
    hw = model_service.detect_hardware()
    
    # Refresh list of models
    model_service.sync_models_to_db(db)
    
    models = db.query(InstalledModel).all()
    downloads = db.query(Download).all()
    
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
