"""SQLAlchemy models and lazy database initialization."""

from __future__ import annotations

from datetime import datetime
from typing import Optional

from sqlalchemy import create_engine, Column, Integer, String, Text, DateTime, ForeignKey, Float
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


class Conversation(Base):
    __tablename__ = "conversations"
    id = Column(String, primary_key=True, index=True)
    title = Column(String, default="New Conversation")
    user_id = Column(Integer, ForeignKey("users.id"))
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


class Setting(Base):
    __tablename__ = "settings"
    id = Column(Integer, primary_key=True, index=True)
    key = Column(String, unique=True, index=True)
    value = Column(String)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class GeneratedArtifact(Base):
    __tablename__ = "generated_artifacts"
    id = Column(Integer, primary_key=True, index=True)
    message_id = Column(Integer, ForeignKey("messages.id"), nullable=True)
    file_name = Column(String)
    file_path = Column(String)
    file_type = Column(String)
    file_size = Column(Integer)
    created_at = Column(DateTime, default=datetime.utcnow)

    message = relationship("Message", back_populates="artifacts")


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


def init_db() -> None:
    """Create schema and seed default user/settings (idempotent)."""
    from config.paths import get_paths
    from config.settings import get_settings

    paths = get_paths()
    settings = get_settings()
    paths.ensure_directories()

    eng = _get_engine()
    Base.metadata.create_all(bind=eng)

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
        db.commit()
    finally:
        db.close()
