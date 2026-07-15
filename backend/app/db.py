from datetime import datetime
from sqlalchemy import create_engine, Column, Integer, String, Text, DateTime, ForeignKey, Float
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, relationship

DATABASE_URL = "sqlite:///C:/Users/StephenPhilipKallara/Mimir/assistant.db"

engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

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

def init_db():
    Base.metadata.create_all(bind=engine)
    # Seed default user and settings
    db = SessionLocal()
    try:
        if not db.query(User).first():
            user = User(id=1, name="Stephen")
            db.add(user)
        # Add default settings
        defaults = {
            "user_name": "Stephen",
            "personality": "helpful, concise, expert data analyst and assistant",
            "theme": "dark",
            "execution_env": "C:/Users/StephenPhilipKallara/Mimir/backend/.venv"
        }
        for k, v in defaults.items():
            if not db.query(Setting).filter(Setting.key == k).first():
                db.add(Setting(key=k, value=v))
        db.commit()
    finally:
        db.close()
