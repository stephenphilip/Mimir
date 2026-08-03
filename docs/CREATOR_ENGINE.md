# Execution Engine (formerly Creator Engine)

Mimir's reliable artifact pipeline. Generation succeeds only after validation and registration.

## Architecture

```
User Prompt
    ↓
Intent Detection
    ↓
Prompt Studio (optional — execution metadata)
    ↓
Capability Router
    ↓
Execution Planner
    ↓
ArtifactExecutionEngine
    ↓
Provider.execute()
    ↓
ArtifactValidator.validate()
    ↓
ArtifactManager.register_file()
    ↓
Workspace / Frontend
```

## Execution lifecycle

| Status | Meaning |
|--------|---------|
| `queued` | Request accepted |
| `planning` | Provider/capability selection |
| `generating` | Provider writing file to disk |
| `validating` | MIME, readability, thumbnail checks |
| `registering` | SQLite + workspace registration |
| `completed` | Artifact exists and is downloadable |
| `failed` | No artifact registered; error returned |

**Reliability rule:** success requires file exists, validation passes, registration succeeds. Invalid files never become artifact cards.

## Key modules

| Module | Path | Role |
|--------|------|------|
| ArtifactExecutionEngine | `app/creator/execution_engine.py` | Full lifecycle orchestration |
| CreatorEngine | `app/creator/engine.py` | Backward-compatible facade |
| ArtifactValidator | `app/creator/artifact_validator.py` | Mandatory pre-registration gate |
| ExecutionPlanner | `app/creator/execution_planner.py` | Maps requests → provider plans |
| ExecutionDiagnostics | `app/creator/diagnostics.py` | Runtime dashboard log ring buffer |
| ICapabilityProvider | `app/interfaces/capabilities.py` | execute/validate/register/metadata contract |
| DocumentProvider | `app/providers/documents/` | PDF, DOCX, MD, TXT, CSV, XLSX |
| ImageProviderRegistry | `app/providers/images/registry.py` | OpenAI (cloud) + ComfyUI (local) |
| VisionService | `app/services/vision_service.py` | OCR, caption, metadata for uploads |
| PromptStudioService | `app/services/prompt_studio_service.py` | v3 execution metadata |

## Capability contract

Every provider implements `ICapabilityProvider`:

- `execute()` — write artifact to disk
- `validate()` — type-specific checks (delegates to ArtifactValidator)
- `metadata()` — provider-specific fields for dashboards
- `preview()` / `download()` / `history()` — optional helpers

The engine never contains provider-specific logic.

## Validation rules

| Type | Checks |
|------|--------|
| PDF | Exists, non-empty, `%PDF` header, readable pages |
| Image | Decodable, thumbnail generated |
| DOCX | Opens via python-docx |
| XLSX | Workbook readable via openpyxl |
| CSV/MD/TXT | Valid UTF-8 |

## API endpoints

- `POST /api/creator/generate` — returns `execution_status` + artifact (only when validated)
- `GET /api/artifacts` — list registered artifacts
- `POST /api/prompt-studio/enhance` — variants + `execution` metadata block
- `POST /api/vision/analyze?file_id=` — OCR/caption for uploads
- `GET /api/runtime/dashboard` — includes `diagnostics` (execution, validation, filesystem, provider, artifact)

Existing `/api/chat` and `/artifacts/{filename}` are unchanged. PythonExecutor uses the same validation path via `register_existing_file()`.

## Image providers

Configure via environment:

- `MIMIR_IMAGE_PROVIDER` — `openai` or `comfyui` (recommended pair)
- `OPENAI_API_KEY` — DALL·E 3 via Images API
- `MIMIR_COMFYUI_URL` — local ComfyUI (`http://127.0.0.1:8188`)

## Extensibility

1. Implement `ICapabilityProvider`
2. Register in `build_creator_engine()` factory
3. Add MIME mapping in `creator/mime.py`

No changes to RuntimeCoordinator or chat handlers required.
