"""File Manager — uploaded and managed workspace files."""

from __future__ import annotations

import shutil
import uuid
from pathlib import Path
from typing import Any, Dict, List, Optional

from config.paths import get_paths

from ..creator.mime import category_for_type, infer_type_from_filename, mime_for_filename
from ..interfaces.workspaces import IFileRepository, IWorkspaceRepository


class FileManagerService:
    def __init__(self, file_repo: IFileRepository, workspace_repo: IWorkspaceRepository):
        self._file_repo = file_repo
        self._workspace_repo = workspace_repo
        self._paths = get_paths()
        self._uploads_dir = self._paths.data_dir / "uploads"
        self._uploads_dir.mkdir(parents=True, exist_ok=True)

    def list_files(
        self,
        workspace_id: Optional[str] = None,
        category: Optional[str] = None,
        search: Optional[str] = None,
        pinned_only: bool = False,
    ) -> List[Dict[str, Any]]:
        ws_id = workspace_id or self._default_workspace_id()
        rows = self._file_repo.list_files(
            workspace_id=ws_id,
            category=category,
            search=search,
            pinned_only=pinned_only,
        )
        return [self._serialize(r) for r in rows]

    def save_upload(
        self,
        workspace_id: Optional[str],
        filename: str,
        data: bytes,
        mime_type: Optional[str] = None,
    ) -> Dict[str, Any]:
        ws_id = workspace_id or self._default_workspace_id()
        if not ws_id:
            raise ValueError("No workspace available")

        file_id = str(uuid.uuid4())
        safe_name = Path(filename).name
        dest = self._uploads_dir / f"{file_id}_{safe_name}"
        dest.write_bytes(data)

        mime = mime_type or mime_for_filename(safe_name)
        row = self._file_repo.create(
            file_id=file_id,
            workspace_id=ws_id,
            file_name=safe_name,
            file_path=f"/api/files/{file_id}/content",
            mime_type=mime,
            file_size=len(data),
            source="upload",
        )
        payload = self._serialize(row, disk_path=str(dest))

        # Vision Intelligence — auto-analyze image/PDF uploads (lazy, best-effort)
        extracted_text = None
        if mime.startswith("image/") or safe_name.lower().endswith((".png", ".jpg", ".jpeg", ".webp", ".pdf")):
            try:
                from .vision_service import VisionService

                vision = VisionService().analyze_file(str(dest), mime_type=mime)
                if vision.get("success"):
                    payload["vision"] = vision
                    extracted_text = vision.get("context") or vision.get("ocr") or ""
            except Exception as exc:
                payload["vision"] = {"success": False, "error": str(exc)}
        else:
            # Text-based file extraction at upload time
            try:
                extracted_text = data.decode("utf-8", errors="replace")
            except Exception:
                pass

        if extracted_text:
            try:
                self._file_repo.update(file_id=file_id, extracted_text=extracted_text)
            except Exception as exc:
                print(f"Error persisting extracted text to database: {exc}")

        return payload

    def get_disk_path(self, file_id: str) -> Optional[Path]:
        row = self._file_repo.get_by_id(file_id)
        if not row:
            return None
        matches = list(self._uploads_dir.glob(f"{file_id}_*"))
        return matches[0] if matches else None

    def rename(self, file_id: str, new_name: str) -> Optional[Dict[str, Any]]:
        row = self._file_repo.update(file_id, file_name=new_name)
        return self._serialize(row) if row else None

    def pin(self, file_id: str, pinned: bool) -> Optional[Dict[str, Any]]:
        row = self._file_repo.update(file_id, pinned=pinned)
        return self._serialize(row) if row else None

    def delete(self, file_id: str) -> bool:
        path = self.get_disk_path(file_id)
        if path and path.is_file():
            try:
                path.unlink()
            except OSError:
                pass
        return self._file_repo.delete(file_id)

    def _default_workspace_id(self) -> Optional[str]:
        ws = self._workspace_repo.get_default()
        return ws.id if ws else None

    def _serialize(self, row, disk_path: Optional[str] = None) -> Dict[str, Any]:
        file_type = infer_type_from_filename(row.file_name)
        return {
            "id": row.id,
            "workspace_id": row.workspace_id,
            "file_name": row.file_name,
            "file_path": row.file_path,
            "mime_type": row.mime_type,
            "file_type": file_type,
            "category": category_for_type(file_type),
            "file_size": row.file_size,
            "source": row.source,
            "pinned": bool(row.pinned),
            "created_at": row.created_at.isoformat() if row.created_at else None,
            "updated_at": row.updated_at.isoformat() if getattr(row, "updated_at", None) else None,
            "disk_path": disk_path,
        }
