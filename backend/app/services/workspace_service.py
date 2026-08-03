"""Workspace management service."""

from __future__ import annotations

import uuid
from typing import Any, Dict, List, Optional

from ..interfaces.workspaces import IWorkspaceRepository


class WorkspaceService:
    def __init__(self, workspace_repo: IWorkspaceRepository):
        self._repo = workspace_repo

    def list_workspaces(self) -> List[Dict[str, Any]]:
        return [self._serialize(w) for w in self._repo.get_all()]

    def get_default_id(self) -> Optional[str]:
        ws = self._repo.get_default()
        return ws.id if ws else None

    def create(self, name: str, model: Optional[str] = None) -> Dict[str, Any]:
        ws_id = str(uuid.uuid4())
        ws = self._repo.create(ws_id, name, model=model)
        return self._serialize(ws)

    def update(self, workspace_id: str, name: Optional[str] = None, model: Optional[str] = None) -> Optional[Dict[str, Any]]:
        ws = self._repo.update(workspace_id, name=name, model=model)
        return self._serialize(ws) if ws else None

    def delete(self, workspace_id: str) -> bool:
        return self._repo.delete(workspace_id)

    def _serialize(self, ws) -> Dict[str, Any]:
        return {
            "id": ws.id,
            "name": ws.name,
            "model": ws.model,
            "is_default": bool(getattr(ws, "is_default", False)),
            "created_at": ws.created_at.isoformat() if ws.created_at else None,
            "updated_at": ws.updated_at.isoformat() if getattr(ws, "updated_at", None) else None,
        }
