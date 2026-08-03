"""Shared types for the Creator Engine pipeline."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional


class ArtifactType(str, Enum):
    PDF = "pdf"
    DOCX = "docx"
    XLSX = "xlsx"
    CSV = "csv"
    MARKDOWN = "markdown"
    TXT = "txt"
    IMAGE = "image"
    PPTX = "pptx"
    HTML = "html"


class ArtifactStatus(str, Enum):
    PENDING = "pending"
    GENERATING = "generating"
    READY = "ready"
    FAILED = "failed"


@dataclass
class GenerationRequest:
    """Normalized input for Creator Engine."""

    artifact_type: str
    title: str
    content: str
    workspace_id: Optional[str] = None
    message_id: Optional[int] = None
    provider_hint: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class ArtifactRecord:
    """Standard artifact metadata consumed by the frontend."""

    artifact_id: str
    type: str
    filename: str
    path: str
    mime_type: str
    size: int
    created_at: str
    provider: str
    workspace_id: Optional[str]
    status: str
    thumbnail: Optional[str] = None
    message_id: Optional[int] = None
    db_id: Optional[int] = None
    # Artifact Intelligence
    original_prompt: Optional[str] = None
    enhanced_prompt: Optional[str] = None
    execution_plan: Optional[Dict[str, Any]] = None
    model: Optional[str] = None
    validation_status: Optional[str] = None
    version: int = 1
    intelligence: Optional[Dict[str, Any]] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "artifact_id": self.artifact_id,
            "type": self.type,
            "filename": self.filename,
            "file_name": self.filename,
            "path": self.path,
            "file_path": self.path,
            "mime_type": self.mime_type,
            "file_type": self.type,
            "size": self.size,
            "file_size": self.size,
            "created_at": self.created_at,
            "provider": self.provider,
            "workspace_id": self.workspace_id,
            "status": self.status,
            "thumbnail": self.thumbnail,
            "message_id": self.message_id,
            "id": self.db_id or self.artifact_id,
            "original_prompt": self.original_prompt,
            "enhanced_prompt": self.enhanced_prompt,
            "execution_plan": self.execution_plan,
            "model": self.model,
            "validation_status": self.validation_status,
            "version": self.version,
            "intelligence": self.intelligence,
            "preview": self.path,
        }


@dataclass
class ValidationResult:
    valid: bool
    errors: List[str] = field(default_factory=list)
    mime_type: Optional[str] = None
    thumbnail_path: Optional[str] = None
    size: int = 0


@dataclass
class GenerationResult:
    success: bool
    artifact: Optional[ArtifactRecord] = None
    error: Optional[str] = None
    stdout: str = ""
    stderr: str = ""
    output_path: Optional[str] = None
