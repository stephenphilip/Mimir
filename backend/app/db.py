"""SQLAlchemy models and lazy database initialization."""

from __future__ import annotations

from datetime import datetime
from typing import Optional

from sqlalchemy import create_engine, Column, Integer, String, Text, DateTime, ForeignKey, Float, Boolean, text
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, relationship, Session

Base = declarative_base()

# Lazily created — no I/O at import time
_engine = None
_SessionLocal = None
_db_initialized = False


class User(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, default="User")
    created_at = Column(DateTime, default=datetime.utcnow)


class Workspace(Base):
    __tablename__ = "workspaces"
    id = Column(String, primary_key=True, index=True)
    name = Column(String, default="Default Workspace")
    model = Column(String, nullable=True)
    settings_json = Column(Text, nullable=True)
    is_default = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class Conversation(Base):
    __tablename__ = "conversations"
    id = Column(String, primary_key=True, index=True)
    title = Column(String, default="New Conversation")
    user_id = Column(Integer, ForeignKey("users.id"))
    project_id = Column(String, nullable=True, index=True)
    workspace_id = Column(String, ForeignKey("workspaces.id"), nullable=True, index=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    messages = relationship("Message", back_populates="conversation", cascade="all, delete-orphan")


class Message(Base):
    __tablename__ = "messages"
    id = Column(Integer, primary_key=True, index=True)
    conversation_id = Column(String, ForeignKey("conversations.id"), index=True)
    sender = Column(String)  # 'user' or 'assistant'
    content = Column(Text)
    tokens_count = Column(Integer, default=0)
    created_at = Column(DateTime, default=datetime.utcnow)

    conversation = relationship("Conversation", back_populates="messages")
    artifacts = relationship("GeneratedArtifact", back_populates="message", cascade="all, delete-orphan")


class Memory(Base):
    __tablename__ = "memory"
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"))
    key = Column(String, index=True)
    value = Column(Text)
    created_at = Column(DateTime, default=datetime.utcnow)


class Project(Base):
    __tablename__ = "projects"
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String)
    path = Column(String)
    created_at = Column(DateTime, default=datetime.utcnow)


class InstalledModel(Base):
    __tablename__ = "installed_models"
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, unique=True, index=True)
    status = Column(String)  # 'downloading', 'installed', 'error'
    size = Column(String)
    local_path = Column(String, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)


class ModelCatalog(Base):
    __tablename__ = "model_catalog"
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, unique=True, index=True)
    base_name = Column(String)
    parameter_size = Column(Float)
    file_size_gb = Column(Float)
    context_limit = Column(Integer, default=8192)
    required_ram_gb = Column(Float)
    required_vram_gb = Column(Float)
    total_layers = Column(Integer, default=32)
    score_reasoning = Column(Float)
    score_coding = Column(Float)
    score_math = Column(Float)
    score_conversational = Column(Float)
    tps_cpu = Column(Float)
    tps_gpu = Column(Float)
    is_active = Column(Integer, default=1)
    release_date = Column(DateTime, default=datetime.utcnow)


class Setting(Base):
    __tablename__ = "settings"
    id = Column(Integer, primary_key=True, index=True)
    key = Column(String, unique=True, index=True)
    value = Column(String)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class GeneratedArtifact(Base):
    __tablename__ = "generated_artifacts"
    id = Column(Integer, primary_key=True, index=True)
    artifact_uuid = Column(String, unique=True, index=True, nullable=True)
    message_id = Column(Integer, ForeignKey("messages.id"), nullable=True)
    workspace_id = Column(String, ForeignKey("workspaces.id"), nullable=True, index=True)
    file_name = Column(String)
    file_path = Column(String)
    file_type = Column(String)
    file_size = Column(Integer)
    mime_type = Column(String, nullable=True)
    provider = Column(String, nullable=True)
    status = Column(String, default="ready")
    thumbnail_path = Column(String, nullable=True)
    # Artifact Intelligence
    original_prompt = Column(Text, nullable=True)
    enhanced_prompt = Column(Text, nullable=True)
    execution_plan_json = Column(Text, nullable=True)
    model_name = Column(String, nullable=True)
    intelligence_json = Column(Text, nullable=True)
    version = Column(Integer, default=1)
    validation_status = Column(String, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    message = relationship("Message", back_populates="artifacts")


class ManagedFile(Base):
    __tablename__ = "managed_files"
    id = Column(String, primary_key=True, index=True)
    workspace_id = Column(String, ForeignKey("workspaces.id"), index=True)
    file_name = Column(String)
    file_path = Column(String)
    mime_type = Column(String)
    file_size = Column(Integer, default=0)
    source = Column(String, default="upload")  # upload | generated
    pinned = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class Download(Base):
    __tablename__ = "downloads"
    id = Column(Integer, primary_key=True, index=True)
    model_name = Column(String, unique=True, index=True)
    progress = Column(Float, default=0.0)  # 0.0 to 100.0
    status = Column(String)  # 'pending', 'downloading', 'completed', 'failed'
    error = Column(String, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)


class ExecutionHistory(Base):
    __tablename__ = "execution_history"
    id = Column(Integer, primary_key=True, index=True)
    command = Column(String)
    code_content = Column(Text)
    stdout = Column(Text, nullable=True)
    stderr = Column(Text, nullable=True)
    exit_code = Column(Integer, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)


# ── Phase 1: New memory layer tables (additive — existing tables unchanged) ──

class WorkingMemoryLog(Base):
    """
    Optional debug trace of WorkingMemory contents.

    WorkingMemory itself is ephemeral (per-request, never persisted).
    This table is ONLY written when debug tracing is explicitly enabled.
    In normal production use, this table remains empty.

    Phase 1: Table created on startup, never written.
    Phase 4+: Optional debug mode can write agent intermediate states here.
    """
    __tablename__ = "working_memory_log"
    id = Column(Integer, primary_key=True, index=True)
    conversation_id = Column(String, ForeignKey("conversations.id"), index=True, nullable=True)
    session_id = Column(String, index=True, nullable=True)   # RuntimeCoordinator session
    key = Column(String)
    value = Column(Text)
    created_at = Column(DateTime, default=datetime.utcnow)


class EpisodicMemory(Base):
    """
    Episodic memories: AI-generated summaries of past conversation sessions.

    Populated by SummarizerAgent (Phase 6) after a conversation ends.
    Used by MemoryAgent (Phase 4) to inject relevant past session context
    into new conversations without replaying full message history.

    Example: "On 2026-07-20, the user worked on a Python FastAPI project
    and asked for help with JWT authentication."

    Phase 1: Table created on startup, never written.
    Phase 6: SummarizerAgent writes summaries here after conversations end.
    """
    __tablename__ = "episodic_memory"
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), index=True)
    conversation_id = Column(String, ForeignKey("conversations.id"), nullable=True, index=True)
    summary = Column(Text)                          # AI-generated session summary
    topics = Column(Text, nullable=True)            # JSON array: ["fastapi", "jwt", "python"]
    sentiment = Column(String, nullable=True)       # "positive" | "neutral" | "negative"
    importance_score = Column(Float, nullable=True) # 0.0–1.0, set by SummarizerAgent
    created_at = Column(DateTime, default=datetime.utcnow)


class EntityMemory(Base):
    """
    Named entity memory: tracks people, places, projects, and concepts
    the user has mentioned across conversations.

    Examples:
      - entity_name="Mimir Next", entity_type="project"
      - entity_name="Stephen", entity_type="person"
      - entity_name="FastAPI", entity_type="technology"

    Populated by entity extraction in Phase 6.
    Used by MemoryAgent (Phase 4) to inject entity-specific context
    (e.g., "You have discussed the Mimir Next project in 3 previous chats").

    Phase 1: Table created on startup, never written.
    Phase 6: EntityExtractor writes records here during post-conversation processing.
    """
    __tablename__ = "entity_memory"
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), index=True)
    entity_name = Column(String, index=True)
    entity_type = Column(String)           # "person" | "place" | "project" | "technology" | "concept"
    description = Column(Text, nullable=True)
    attributes = Column(Text, nullable=True)  # JSON: {"language": "Python", "framework": "FastAPI"}
    mention_count = Column(Integer, default=1)
    first_seen_at = Column(DateTime, default=datetime.utcnow)
    last_seen_at = Column(DateTime, default=datetime.utcnow)



def _get_engine():
    global _engine, _SessionLocal
    if _engine is None:
        from config.paths import get_paths

        paths = get_paths()
        paths.ensure_directories()
        _engine = create_engine(
            paths.database_url,
            connect_args={"check_same_thread": False},
        )
        _SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=_engine)
    return _engine


class _SessionLocalProxy:
    """Callable that creates sessions after ensuring the engine exists."""

    def __call__(self) -> Session:
        ensure_db_ready()
        assert _SessionLocal is not None
        return _SessionLocal()


# Backward-compatible name used across the codebase
SessionLocal = _SessionLocalProxy()


# Expose engine as a property-like lazy attribute for rare direct access
def get_engine():
    return _get_engine()


# Compatibility: some code may reference `engine`
class _EngineProxy:
    def __getattr__(self, name):
        return getattr(_get_engine(), name)


engine = _EngineProxy()


def ensure_db_ready() -> None:
    """Create tables and seed defaults on first use only."""
    global _db_initialized
    _get_engine()
    if _db_initialized:
        return
    init_db()
    _db_initialized = True


def _migrate_schema(eng) -> None:
    """Add columns/tables for existing SQLite databases without Alembic."""
    with eng.connect() as conn:
        def _columns(table: str) -> set:
            rows = conn.execute(text(f"PRAGMA table_info({table})")).fetchall()
            return {r[1] for r in rows}

        artifact_cols = {
            "artifact_uuid": "VARCHAR",
            "workspace_id": "VARCHAR",
            "mime_type": "VARCHAR",
            "provider": "VARCHAR",
            "status": "VARCHAR DEFAULT 'ready'",
            "thumbnail_path": "VARCHAR",
            "original_prompt": "TEXT",
            "enhanced_prompt": "TEXT",
            "execution_plan_json": "TEXT",
            "model_name": "VARCHAR",
            "intelligence_json": "TEXT",
            "version": "INTEGER DEFAULT 1",
            "validation_status": "VARCHAR",
        }
        if "generated_artifacts" in eng.dialect.get_table_names(conn):
            existing = _columns("generated_artifacts")
            for col, col_type in artifact_cols.items():
                if col not in existing:
                    conn.execute(text(f"ALTER TABLE generated_artifacts ADD COLUMN {col} {col_type}"))

        conv_cols = {"workspace_id": "VARCHAR"}
        if "conversations" in eng.dialect.get_table_names(conn):
            existing = _columns("conversations")
            for col, col_type in conv_cols.items():
                if col not in existing:
                    conn.execute(text(f"ALTER TABLE conversations ADD COLUMN {col} {col_type}"))
        conn.commit()


def init_db() -> None:
    """Create schema and seed default user/settings (idempotent)."""
    import uuid

    from config.paths import get_paths
    from config.settings import get_settings

    paths = get_paths()
    settings = get_settings()
    paths.ensure_directories()

    eng = _get_engine()
    Base.metadata.create_all(bind=eng)
    _migrate_schema(eng)

    assert _SessionLocal is not None
    db = _SessionLocal()
    try:
        if not db.query(User).first():
            user = User(id=1, name=settings.default_user_name)
            db.add(user)

        defaults = {
            "user_name": settings.default_user_name,
            "personality": settings.default_personality,
            "theme": settings.default_theme,
            "execution_env": str(paths.venv_dir),
        }
        for k, v in defaults.items():
            if not db.query(Setting).filter(Setting.key == k).first():
                db.add(Setting(key=k, value=v))

        # Keep execution_env aligned with the venv that has fpdf/pandas
        from config.python_env import resolve_python_executable, venv_dir_for_python

        resolved = venv_dir_for_python(resolve_python_executable())
        env_row = db.query(Setting).filter(Setting.key == "execution_env").first()
        if env_row and env_row.value != str(resolved):
            env_row.value = str(resolved)

        if not db.query(Workspace).first():
            default_ws = Workspace(
                id=str(uuid.uuid4()),
                name="Default Workspace",
                is_default=True,
            )
            db.add(default_ws)

        # Seed Model Catalog
        if not db.query(ModelCatalog).first():
            catalog_seeds = [
                ModelCatalog(
                    name="llama3.2:1b",
                    base_name="llama3.2",
                    parameter_size=1.3,
                    file_size_gb=1.3,
                    context_limit=8192,
                    required_ram_gb=4.0,
                    required_vram_gb=2.0,
                    total_layers=28,
                    score_reasoning=65.0,
                    score_coding=35.0,
                    score_math=40.0,
                    score_conversational=85.0,
                    tps_cpu=12.0,
                    tps_gpu=50.0,
                    is_active=1
                ),
                ModelCatalog(
                    name="llama3.2:3b",
                    base_name="llama3.2",
                    parameter_size=3.2,
                    file_size_gb=2.0,
                    context_limit=8192,
                    required_ram_gb=6.0,
                    required_vram_gb=3.2,
                    total_layers=28,
                    score_reasoning=65.0,
                    score_coding=50.0,
                    score_math=55.0,
                    score_conversational=70.0,
                    tps_cpu=8.5,
                    tps_gpu=38.0,
                    is_active=1
                ),
                ModelCatalog(
                    name="qwen2.5-coder:1.5b",
                    base_name="qwen2.5-coder",
                    parameter_size=1.5,
                    file_size_gb=1.6,
                    context_limit=32768,
                    required_ram_gb=4.0,
                    required_vram_gb=2.2,
                    total_layers=28,
                    score_reasoning=60.0,
                    score_coding=68.0,
                    score_math=62.0,
                    score_conversational=65.0,
                    tps_cpu=10.0,
                    tps_gpu=42.0,
                    is_active=1
                ),
                ModelCatalog(
                    name="qwen2.5-coder:7b",
                    base_name="qwen2.5-coder",
                    parameter_size=7.2,
                    file_size_gb=4.7,
                    context_limit=32768,
                    required_ram_gb=16.0,
                    required_vram_gb=8.0,
                    total_layers=28,
                    score_reasoning=80.0,
                    score_coding=85.0,
                    score_math=82.0,
                    score_conversational=80.0,
                    tps_cpu=4.0,
                    tps_gpu=25.0,
                    is_active=1
                ),
                ModelCatalog(
                    name="gemma2:2b",
                    base_name="gemma2",
                    parameter_size=2.6,
                    file_size_gb=1.6,
                    context_limit=8192,
                    required_ram_gb=6.0,
                    required_vram_gb=3.0,
                    total_layers=26,
                    score_reasoning=63.0,
                    score_coding=45.0,
                    score_math=52.0,
                    score_conversational=68.0,
                    tps_cpu=8.0,
                    tps_gpu=35.0,
                    is_active=1
                ),
                ModelCatalog(
                    name="mistral:7b",
                    base_name="mistral",
                    parameter_size=7.2,
                    file_size_gb=4.1,
                    context_limit=32768,
                    required_ram_gb=16.0,
                    required_vram_gb=8.0,
                    total_layers=32,
                    score_reasoning=72.0,
                    score_coding=55.0,
                    score_math=68.0,
                    score_conversational=75.0,
                    tps_cpu=3.5,
                    tps_gpu=22.0,
                    is_active=1
                )
            ]
            db.bulk_save_objects(catalog_seeds)

        db.commit()
    finally:
        db.close()
