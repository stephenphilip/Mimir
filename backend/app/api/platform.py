"""Platform APIs — Creator Engine, workspaces, files, prompt studio, runtime dashboard."""

from __future__ import annotations

import uuid
from typing import Optional

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, Query
from pydantic import BaseModel
from sqlalchemy.orm import Session

from ..creator.factory import build_creator_engine
from ..creator.types import GenerationRequest
from ..db import SessionLocal, ensure_db_ready
from ..repositories.sqlite_repositories import (
    SQLiteArtifactRepository,
    SQLiteFileRepository,
    SQLiteModelRepository,
    SQLiteSettingRepository,
    SQLiteWorkspaceRepository,
)
from ..services.file_manager_service import FileManagerService
from ..services.prompt_studio_service import PromptStudioService
from ..services.workspace_service import WorkspaceService
from config.paths import get_paths
from runtime.runtime_coordinator import get_runtime

router = APIRouter(prefix="/api", tags=["platform"])


def get_db():
    ensure_db_ready()
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


class CreatorGenerateRequest(BaseModel):
    artifact_type: str
    title: str
    content: str
    workspace_id: Optional[str] = None
    message_id: Optional[int] = None
    provider_hint: Optional[str] = None


class PromptStudioRequest(BaseModel):
    prompt: str
    model: Optional[str] = None


class WorkspaceCreateRequest(BaseModel):
    name: str
    model: Optional[str] = None


class WorkspaceUpdateRequest(BaseModel):
    name: Optional[str] = None
    model: Optional[str] = None


class FileRenameRequest(BaseModel):
    file_name: str


class FilePinRequest(BaseModel):
    pinned: bool


def _artifact_payload(record) -> dict:
    return record.to_dict()


@router.post("/creator/generate")
def creator_generate(body: CreatorGenerateRequest, db: Session = Depends(get_db)):
    art_repo = SQLiteArtifactRepository(db)
    engine, _ = build_creator_engine(art_repo)
    request = GenerationRequest(
        artifact_type=body.artifact_type,
        title=body.title,
        content=body.content,
        workspace_id=body.workspace_id,
        message_id=body.message_id,
        provider_hint=body.provider_hint,
    )
    inner = getattr(engine, "_inner", None)
    if inner is not None and hasattr(inner, "execute"):
        outcome = inner.execute(request)
        if not outcome.success:
            raise HTTPException(status_code=400, detail=outcome.error or "Generation failed")
        return {
            "success": True,
            "execution_status": outcome.status.value,
            "artifact": _artifact_payload(outcome.artifact) if outcome.artifact else None,
            "stdout": outcome.stdout,
        }

    result = engine.generate(request)
    if not result.success:
        raise HTTPException(status_code=400, detail=result.error or "Generation failed")
    return {
        "success": True,
        "execution_status": "completed",
        "artifact": _artifact_payload(result.artifact) if result.artifact else None,
        "stdout": result.stdout,
    }


@router.get("/artifacts")
def list_artifacts(
    workspace_id: Optional[str] = None,
    artifact_type: Optional[str] = None,
    limit: int = 100,
    db: Session = Depends(get_db),
):
    art_repo = SQLiteArtifactRepository(db)
    _, manager = build_creator_engine(art_repo)
    records = manager.list_artifacts(
        workspace_id=workspace_id,
        artifact_type=artifact_type,
        limit=limit,
    )
    return [_artifact_payload(r) for r in records]


@router.get("/workspaces")
def list_workspaces(db: Session = Depends(get_db)):
    svc = WorkspaceService(SQLiteWorkspaceRepository(db))
    return svc.list_workspaces()


@router.post("/workspaces")
def create_workspace(body: WorkspaceCreateRequest, db: Session = Depends(get_db)):
    svc = WorkspaceService(SQLiteWorkspaceRepository(db))
    return svc.create(body.name, model=body.model)


@router.patch("/workspaces/{workspace_id}")
def update_workspace(workspace_id: str, body: WorkspaceUpdateRequest, db: Session = Depends(get_db)):
    svc = WorkspaceService(SQLiteWorkspaceRepository(db))
    updated = svc.update(workspace_id, name=body.name, model=body.model)
    if not updated:
        raise HTTPException(status_code=404, detail="Workspace not found")
    return updated


@router.delete("/workspaces/{workspace_id}")
def delete_workspace(workspace_id: str, db: Session = Depends(get_db)):
    svc = WorkspaceService(SQLiteWorkspaceRepository(db))
    if not svc.delete(workspace_id):
        raise HTTPException(status_code=400, detail="Cannot delete workspace")
    return {"status": "success"}


@router.post("/prompt-studio/enhance")
def prompt_studio_enhance(body: PromptStudioRequest):
    svc = PromptStudioService()
    return svc.enhance(body.prompt, model=body.model)


@router.get("/files")
def list_files(
    workspace_id: Optional[str] = None,
    category: Optional[str] = None,
    search: Optional[str] = None,
    pinned_only: bool = False,
    db: Session = Depends(get_db),
):
    ws_repo = SQLiteWorkspaceRepository(db)
    file_repo = SQLiteFileRepository(db)
    svc = FileManagerService(file_repo, ws_repo)
    return svc.list_files(
        workspace_id=workspace_id,
        category=category,
        search=search,
        pinned_only=pinned_only,
    )


@router.post("/files/upload")
async def upload_file(
    file: UploadFile = File(...),
    workspace_id: Optional[str] = Query(None),
    db: Session = Depends(get_db),
):
    ws_repo = SQLiteWorkspaceRepository(db)
    file_repo = SQLiteFileRepository(db)
    svc = FileManagerService(file_repo, ws_repo)
    data = await file.read()
    return svc.save_upload(workspace_id, file.filename or "upload.bin", data, file.content_type)


@router.patch("/files/{file_id}")
def rename_file(file_id: str, body: FileRenameRequest, db: Session = Depends(get_db)):
    ws_repo = SQLiteWorkspaceRepository(db)
    file_repo = SQLiteFileRepository(db)
    svc = FileManagerService(file_repo, ws_repo)
    updated = svc.rename(file_id, body.file_name)
    if not updated:
        raise HTTPException(status_code=404, detail="File not found")
    return updated


@router.post("/files/{file_id}/pin")
def pin_file(file_id: str, body: FilePinRequest, db: Session = Depends(get_db)):
    ws_repo = SQLiteWorkspaceRepository(db)
    file_repo = SQLiteFileRepository(db)
    svc = FileManagerService(file_repo, ws_repo)
    updated = svc.pin(file_id, body.pinned)
    if not updated:
        raise HTTPException(status_code=404, detail="File not found")
    return updated


@router.delete("/files/{file_id}")
def delete_file(file_id: str, db: Session = Depends(get_db)):
    ws_repo = SQLiteWorkspaceRepository(db)
    file_repo = SQLiteFileRepository(db)
    svc = FileManagerService(file_repo, ws_repo)
    if not svc.delete(file_id):
        raise HTTPException(status_code=404, detail="File not found")
    return {"status": "success"}


@router.get("/files/{file_id}/content")
def get_file_content(file_id: str, db: Session = Depends(get_db)):
    from fastapi.responses import FileResponse

    ws_repo = SQLiteWorkspaceRepository(db)
    file_repo = SQLiteFileRepository(db)
    svc = FileManagerService(file_repo, ws_repo)
    path = svc.get_disk_path(file_id)
    row = file_repo.get_by_id(file_id)
    if not path or not path.is_file() or not row:
        raise HTTPException(status_code=404, detail="File not found")
    return FileResponse(str(path), filename=row.file_name, media_type=row.mime_type)


@router.get("/runtime/dashboard")
def runtime_dashboard(db: Session = Depends(get_db)):
    from config.settings import get_settings
    from ..creator.diagnostics import get_execution_diagnostics

    settings = get_settings()
    diagnostics = get_execution_diagnostics()
    runtime = get_runtime()
    model_repo = SQLiteModelRepository(db)
    art_repo = SQLiteArtifactRepository(db)
    ws_repo = SQLiteWorkspaceRepository(db)

    ms = runtime.model_service
    if ms is None:
        setting_repo = SQLiteSettingRepository(db)
        from ..services.model_service import ModelService

        ms = ModelService(model_repo, setting_repo, ollama_url=settings.ollama_url)
        runtime.bind_model_service(ms)

    hw = ms.detect_hardware()
    ms.sync_models_to_db()
    resources = runtime.sample_resources()
    plugins = runtime.list_plugin_manifests()
    default_ws = ws_repo.get_default()

    models = model_repo.get_all_installed()
    downloads = model_repo.get_all_downloads()
    artifact_count = art_repo.list_all(limit=10000)
    _, manager = build_creator_engine(art_repo)

    return {
        "system_status": "online",
        "current_model": resources.get("loaded_model"),
        "workspace": {
            "id": default_ws.id if default_ws else None,
            "name": default_ws.name if default_ws else None,
        },
        "resources": resources,
        "hardware": hw,
        "plugins": plugins,
        "installed_models": [
            {"name": m.name, "size": m.size, "status": m.status}
            for m in models
        ],
        "downloads": [
            {
                "model_name": dl.model_name,
                "progress": dl.progress,
                "status": dl.status,
                "error": dl.error,
            }
            for dl in downloads
        ],
        "artifacts_generated": len(artifact_count),
        "supported_creator_types": build_creator_engine(art_repo)[0].supported_types(),
        "image_providers": __import__(
            "app.providers.images.registry", fromlist=["ImageProviderRegistry"]
        ).ImageProviderRegistry().list_providers(),
        "capabilities": __import__(
            "app.intelligence.capability_registry", fromlist=["get_capability_registry"]
        ).get_capability_registry().list_capabilities(),
        "packs": __import__(
            "app.intelligence.packs", fromlist=["get_pack_registry"]
        ).get_pack_registry().list_packs(),
        "diagnostics": {
            "execution": diagnostics.list_recent(limit=50, category="execution"),
            "validation": diagnostics.list_recent(limit=50, category="validation"),
            "filesystem": diagnostics.list_recent(limit=50, category="filesystem"),
            "provider": diagnostics.list_recent(limit=50, category="provider"),
            "artifact": diagnostics.list_recent(limit=50, category="artifact"),
            "plans": [
                e for e in diagnostics.list_recent(limit=50, category="execution")
                if "Plan:" in (e.get("message") or "")
            ],
        },
        "telemetry": {
            "resources": resources,
            "hardware": hw,
            "loaded_model": resources.get("loaded_model"),
        },
    }


@router.get("/capabilities")
def list_capabilities():
    from ..intelligence.capability_registry import get_capability_registry

    return [c.to_dict() for c in get_capability_registry().list_capabilities()]


@router.get("/packs")
def list_packs():
    from ..intelligence.packs import get_pack_registry

    return get_pack_registry().list_packs()


class PackInstallRequest(BaseModel):
    pack_id: str


@router.post("/packs/install")
def install_pack(body: PackInstallRequest):
    from ..intelligence.packs import get_pack_registry

    try:
        return {"success": True, "pack": get_pack_registry().install(body.pack_id)}
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc))


@router.post("/packs/uninstall")
def uninstall_pack(body: PackInstallRequest):
    from ..intelligence.packs import get_pack_registry

    try:
        return {"success": True, "pack": get_pack_registry().uninstall(body.pack_id)}
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc))


@router.post("/vision/analyze")
def vision_analyze(file_id: str = Query(...), db: Session = Depends(get_db)):
    from ..services.vision_service import VisionService

    ws_repo = SQLiteWorkspaceRepository(db)
    file_repo = SQLiteFileRepository(db)
    svc = FileManagerService(file_repo, ws_repo)
    path = svc.get_disk_path(file_id)
    row = file_repo.get_by_id(file_id)
    if not path or not path.is_file() or not row:
        raise HTTPException(status_code=404, detail="File not found")
    result = VisionService().analyze_file(str(path), mime_type=row.mime_type)
    if not result.get("success"):
        raise HTTPException(status_code=400, detail=result.get("error", "Vision analysis failed"))
    return result
