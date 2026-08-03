"""Unified Artifact Manager — every generated output registers here."""

from __future__ import annotations

import json
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

from config.paths import get_paths

from ..interfaces.creators import IArtifactManager
from ..interfaces.repositories import IArtifactRepository
from .mime import infer_type_from_filename, mime_for_filename
from .types import ArtifactRecord, ValidationResult
from .artifact_validator import ArtifactValidator


class ArtifactManager(IArtifactManager):
    """
    Single registration point for all artifacts.

    Architectural decision: wraps IArtifactRepository rather than replacing it,
    so existing message-linked artifact queries keep working.
    """

    def __init__(self, artifact_repo: IArtifactRepository, validator: Optional[ArtifactValidator] = None):
        self._repo = artifact_repo
        self._paths = get_paths()
        self._validator = validator

    def register_file(
        self,
        file_path: str,
        *,
        message_id: Optional[int] = None,
        workspace_id: Optional[str] = None,
        provider: str = "python_execution",
        artifact_type: Optional[str] = None,
        status: str = "ready",
        thumbnail_path: Optional[str] = None,
        validation: Optional[ValidationResult] = None,
        intelligence: Optional[Dict[str, Any]] = None,
    ) -> ArtifactRecord:
        path = Path(file_path)
        if not path.is_file():
            raise FileNotFoundError(f"Artifact file not found: {file_path}")

        file_type = artifact_type or infer_type_from_filename(path.name)
        if validation is None:
            if self._validator is None:
                raise ValueError("Artifact validation required — validator not configured")
            validation = self._validator.validate(str(path), file_type)
        if not validation.valid:
            raise ValueError("; ".join(validation.errors))

        filename = path.name
        mime_type = validation.mime_type or mime_for_filename(filename)
        file_size = validation.size or path.stat().st_size
        artifact_uuid = str(uuid.uuid4())
        thumb = thumbnail_path or validation.thumbnail_path
        thumb_web: Optional[str] = None
        if thumb:
            try:
                rel_thumb = Path(thumb).resolve().relative_to(self._paths.artifacts_dir.resolve())
                thumb_web = f"/artifacts/{rel_thumb.as_posix()}"
            except ValueError:
                thumb_web = thumb

        try:
            rel = path.resolve().relative_to(self._paths.artifacts_dir.resolve())
            web_path = f"/artifacts/{rel.as_posix()}"
        except ValueError:
            web_path = f"/artifacts/{filename}"

        intel = intelligence or {}
        plan = intel.get("execution_plan")
        row = self._repo.create(
            message_id=message_id,
            file_name=filename,
            file_path=web_path,
            file_type=file_type,
            file_size=file_size,
            artifact_uuid=artifact_uuid,
            mime_type=mime_type,
            provider=provider,
            workspace_id=workspace_id,
            status=status,
            thumbnail_path=thumb_web,
            original_prompt=intel.get("original_prompt"),
            enhanced_prompt=intel.get("enhanced_prompt"),
            execution_plan_json=json.dumps(plan) if plan else None,
            model_name=intel.get("model"),
            intelligence_json=json.dumps(intel) if intel else None,
            version=int(intel.get("version") or 1),
            validation_status=intel.get("validation_status") or "passed",
        )

        return self._to_record(row)

    def attach_intelligence(self, artifact_id: str, intelligence: Dict[str, Any]) -> Optional[ArtifactRecord]:
        if not hasattr(self._repo, "update_intelligence"):
            return None
        row = self._repo.update_intelligence(artifact_id, intelligence)
        return self._to_record(row) if row else None

    def get(self, artifact_id: str) -> Optional[ArtifactRecord]:
        row = self._repo.get_by_uuid(artifact_id)
        if row:
            return self._to_record(row)
        if artifact_id.isdigit():
            row = self._repo.get_by_id(int(artifact_id))
            if row:
                return self._to_record(row)
        return None

    def list_artifacts(
        self,
        *,
        workspace_id: Optional[str] = None,
        artifact_type: Optional[str] = None,
        limit: int = 100,
    ) -> List[ArtifactRecord]:
        rows = self._repo.list_all(
            workspace_id=workspace_id,
            artifact_type=artifact_type,
            limit=limit,
        )
        return [self._to_record(r) for r in rows]

    def count_by_workspace(self, workspace_id: str) -> int:
        return self._repo.count_by_workspace(workspace_id)

    def _to_record(self, row) -> ArtifactRecord:
        created = row.created_at
        if isinstance(created, datetime):
            created_str = created.isoformat()
        else:
            created_str = str(created) if created else ""

        artifact_uuid = getattr(row, "artifact_uuid", None) or str(row.id)
        plan = None
        intel = None
        raw_plan = getattr(row, "execution_plan_json", None)
        raw_intel = getattr(row, "intelligence_json", None)
        try:
            if raw_plan:
                plan = json.loads(raw_plan)
        except Exception:
            plan = None
        try:
            if raw_intel:
                intel = json.loads(raw_intel)
        except Exception:
            intel = None

        return ArtifactRecord(
            artifact_id=artifact_uuid,
            type=row.file_type,
            filename=row.file_name,
            path=row.file_path,
            mime_type=getattr(row, "mime_type", None) or mime_for_filename(row.file_name),
            size=row.file_size or 0,
            created_at=created_str,
            provider=getattr(row, "provider", None) or "unknown",
            workspace_id=getattr(row, "workspace_id", None),
            status=getattr(row, "status", None) or "ready",
            thumbnail=getattr(row, "thumbnail_path", None),
            message_id=row.message_id,
            db_id=row.id,
            original_prompt=getattr(row, "original_prompt", None),
            enhanced_prompt=getattr(row, "enhanced_prompt", None),
            execution_plan=plan,
            model=getattr(row, "model_name", None),
            validation_status=getattr(row, "validation_status", None),
            version=getattr(row, "version", None) or 1,
            intelligence=intel,
        )
