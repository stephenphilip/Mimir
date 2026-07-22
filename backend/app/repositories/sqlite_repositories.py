from sqlalchemy.orm import Session
from typing import List, Optional, Dict, Any
from datetime import datetime

from ..interfaces.repositories import (
    IConversationRepository,
    IMemoryRepository,
    IModelRepository,
    IArtifactRepository,
    ISettingRepository,
    IModelCatalogRepository
)
from ..db import Conversation, Message, Memory, InstalledModel, Download, GeneratedArtifact, Setting, User, ExecutionHistory, ModelCatalog

class SQLiteConversationRepository(IConversationRepository):
    def __init__(self, db: Session):
        self.db = db

    def get_by_id(self, conv_id: str) -> Optional[Conversation]:
        return self.db.query(Conversation).filter(Conversation.id == conv_id).first()

    def create(self, conv_id: str, title: str, user_id: int, project_id: Optional[str] = None) -> Conversation:
        conv = Conversation(id=conv_id, title=title, user_id=user_id, project_id=project_id)
        self.db.add(conv)
        self.db.commit()
        self.db.refresh(conv)
        return conv

    def update_project(self, conv_id: str, project_id: Optional[str]) -> None:
        conv = self.get_by_id(conv_id)
        if conv:
            conv.project_id = project_id
            self.db.commit()

    def get_by_project(self, project_id: str) -> List[Conversation]:
        return self.db.query(Conversation).filter(Conversation.project_id == project_id).all()

    def delete(self, conv_id: str) -> bool:
        conv = self.get_by_id(conv_id)
        if conv:
            self.db.delete(conv)
            self.db.commit()
            return True
        return False

    def get_all(self) -> List[Conversation]:
        return self.db.query(Conversation).order_by(Conversation.updated_at.desc()).all()

    def update_title(self, conv_id: str, title: str) -> None:
        conv = self.get_by_id(conv_id)
        if conv:
            conv.title = title
            self.db.commit()

    def get_messages(self, conv_id: str, limit: Optional[int] = None) -> List[Message]:
        query = self.db.query(Message).filter(Message.conversation_id == conv_id).order_by(Message.created_at.asc())
        if limit:
            # Note: to get the last N messages in ascending order, we get the last N sorted by desc, then reverse
            query = self.db.query(Message).filter(Message.conversation_id == conv_id)\
                             .order_by(Message.created_at.desc()).limit(limit)
            messages = query.all()
            messages.reverse()
            return messages
        return query.all()

    def add_message(self, conv_id: str, sender: str, content: str, tokens_count: int = 0) -> Message:
        message = Message(
            conversation_id=conv_id,
            sender=sender,
            content=content,
            tokens_count=tokens_count
        )
        self.db.add(message)
        
        # Also update conversation updated_at
        conv = self.get_by_id(conv_id)
        if conv:
            conv.updated_at = datetime.utcnow()
            
        self.db.commit()
        self.db.refresh(message)
        return message


class SQLiteMemoryRepository(IMemoryRepository):
    def __init__(self, db: Session):
        self.db = db

    def get_by_key(self, user_id: int, key: str) -> Optional[Memory]:
        return self.db.query(Memory).filter(Memory.user_id == user_id, Memory.key == key).first()

    def get_all_by_user(self, user_id: int) -> List[Memory]:
        return self.db.query(Memory).filter(Memory.user_id == user_id).all()

    def save(self, user_id: int, key: str, value: str) -> Memory:
        existing = self.get_by_key(user_id, key)
        if existing:
            existing.value = value
            self.db.commit()
            self.db.refresh(existing)
            return existing
        else:
            mem = Memory(user_id=user_id, key=key, value=value)
            self.db.add(mem)
            self.db.commit()
            self.db.refresh(mem)
            return mem

    def get_user_name(self, user_id: int) -> Optional[str]:
        user = self.db.query(User).filter(User.id == user_id).first()
        return user.name if user else None

    def save_user_name(self, user_id: int, name: str) -> None:
        user = self.db.query(User).filter(User.id == user_id).first()
        if user:
            user.name = name
            self.db.commit()
        else:
            new_user = User(id=user_id, name=name)
            self.db.add(new_user)
            self.db.commit()


class SQLiteModelRepository(IModelRepository):
    def __init__(self, db: Session):
        self.db = db

    def get_by_name(self, name: str) -> Optional[InstalledModel]:
        return self.db.query(InstalledModel).filter(InstalledModel.name == name).first()

    def get_all_installed(self) -> List[InstalledModel]:
        return self.db.query(InstalledModel).all()

    def save_installed(self, name: str, status: str, size: str, local_path: Optional[str] = None) -> InstalledModel:
        existing = self.get_by_name(name)
        if existing:
            existing.status = status
            existing.size = size
            if local_path:
                existing.local_path = local_path
            self.db.commit()
            self.db.refresh(existing)
            return existing
        else:
            model = InstalledModel(name=name, status=status, size=size, local_path=local_path)
            self.db.add(model)
            self.db.commit()
            self.db.refresh(model)
            return model

    def delete_by_name(self, name: str) -> bool:
        model = self.get_by_name(name)
        if model:
            self.db.delete(model)
            self.db.commit()
            return True
        return False

    def get_download(self, model_name: str) -> Optional[Download]:
        return self.db.query(Download).filter(Download.model_name == model_name).first()

    def get_all_downloads(self) -> List[Download]:
        return self.db.query(Download).all()

    def save_download(self, model_name: str, progress: float, status: str, error: Optional[str] = None) -> Download:
        existing = self.get_download(model_name)
        if existing:
            existing.progress = progress
            existing.status = status
            existing.error = error
            self.db.commit()
            self.db.refresh(existing)
            return existing
        else:
            dl = Download(model_name=model_name, progress=progress, status=status, error=error)
            self.db.add(dl)
            self.db.commit()
            self.db.refresh(dl)
            return dl

    def refresh(self) -> None:
        self.db.expire_all()


class SQLiteArtifactRepository(IArtifactRepository):
    def __init__(self, db: Session):
        self.db = db

    def create(self, message_id: Optional[int], file_name: str, file_path: str, file_type: str, file_size: int) -> GeneratedArtifact:
        art = GeneratedArtifact(
            message_id=message_id,
            file_name=file_name,
            file_path=file_path,
            file_type=file_type,
            file_size=file_size
        )
        self.db.add(art)
        self.db.commit()
        self.db.refresh(art)
        return art

    def get_by_message_id(self, message_id: int) -> List[GeneratedArtifact]:
        return self.db.query(GeneratedArtifact).filter(GeneratedArtifact.message_id == message_id).all()

    def save_execution_history(
        self,
        command: str,
        code_content: str,
        stdout: Optional[str],
        stderr: Optional[str],
        exit_code: Optional[int]
    ) -> ExecutionHistory:
        history = ExecutionHistory(
            command=command,
            code_content=code_content,
            stdout=stdout,
            stderr=stderr,
            exit_code=exit_code
        )
        self.db.add(history)
        self.db.commit()
        self.db.refresh(history)
        return history


class SQLiteSettingRepository(ISettingRepository):
    def __init__(self, db: Session):
        self.db = db

    def get_all(self) -> Dict[str, str]:
        settings = self.db.query(Setting).all()
        return {s.key: s.value for s in settings}

    def get_by_key(self, key: str) -> Optional[str]:
        setting = self.db.query(Setting).filter(Setting.key == key).first()
        return setting.value if setting else None

    def save(self, key: str, value: str) -> Setting:
        setting = self.db.query(Setting).filter(Setting.key == key).first()
        if setting:
            setting.value = value
            self.db.commit()
            self.db.refresh(setting)
            return setting
        else:
            s = Setting(key=key, value=value)
            self.db.add(s)
            self.db.commit()
            self.db.refresh(s)
            return s


class SQLiteModelCatalogRepository(IModelCatalogRepository):
    def __init__(self, db: Session):
        self.db = db

    def get_by_name(self, name: str) -> Optional[ModelCatalog]:
        return self.db.query(ModelCatalog).filter(ModelCatalog.name == name).first()

    def get_all_active(self) -> List[ModelCatalog]:
        return self.db.query(ModelCatalog).filter(ModelCatalog.is_active == 1).all()

    def save_master_model(
        self,
        name: str,
        base_name: str,
        parameter_size: float,
        file_size_gb: float,
        required_ram_gb: float,
        required_vram_gb: float,
        total_layers: int,
        score_reasoning: float,
        score_coding: float,
        score_math: float,
        score_conversational: float,
        tps_cpu: float,
        tps_gpu: float,
        is_active: int = 1
    ) -> ModelCatalog:
        existing = self.get_by_name(name)
        if existing:
            existing.base_name = base_name
            existing.parameter_size = parameter_size
            existing.file_size_gb = file_size_gb
            existing.required_ram_gb = required_ram_gb
            existing.required_vram_gb = required_vram_gb
            existing.total_layers = total_layers
            existing.score_reasoning = score_reasoning
            existing.score_coding = score_coding
            existing.score_math = score_math
            existing.score_conversational = score_conversational
            existing.tps_cpu = tps_cpu
            existing.tps_gpu = tps_gpu
            existing.is_active = is_active
            self.db.commit()
            self.db.refresh(existing)
            return existing
        else:
            model = ModelCatalog(
                name=name,
                base_name=base_name,
                parameter_size=parameter_size,
                file_size_gb=file_size_gb,
                required_ram_gb=required_ram_gb,
                required_vram_gb=required_vram_gb,
                total_layers=total_layers,
                score_reasoning=score_reasoning,
                score_coding=score_coding,
                score_math=score_math,
                score_conversational=score_conversational,
                tps_cpu=tps_cpu,
                tps_gpu=tps_gpu,
                is_active=is_active
            )
            self.db.add(model)
            self.db.commit()
            self.db.refresh(model)
            return model

    def delete_by_name(self, name: str) -> bool:
        model = self.get_by_name(name)
        if model:
            model.is_active = 0
            self.db.commit()
            return True
        return False

