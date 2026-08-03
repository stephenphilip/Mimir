# Intelligence Layer

Mimir's orchestration layer: the LLM generates knowledge; the platform executes workflows.

## Architecture

```
User → Prompt Studio → Prompt Analyzer → Intent Engine
  → Capability Registry → Execution Planner → Context Builder
  → Execution Engine / Document Workflow → Providers → Validators
  → Artifact Manager → Workspace
```

## Design principles

1. **Do not replace** RuntimeCoordinator, Creator Engine, Prompt Studio, Workspace, Artifact Manager, or Provider Registry — extend them.
2. **Registry-driven routing** — never hardcode capability checks; use `CapabilityRegistry`.
3. **Lazy providers** — load only when a capability/workflow requires them.
4. **SOLID / composable** — Intelligence modules under `app/intelligence/` are independently testable.

## Modules

| Module | Path | Role |
|--------|------|------|
| Capability Registry | `intelligence/capability_registry.py` | Capabilities + intent bindings; packs register here |
| Prompt Analyzer | `intelligence/prompt_analyzer.py` | Heuristic signals before intent |
| Workflow Planner | `intelligence/workflow_planner.py` | Multi-step execution plans |
| Document Model/Builder/Renderer | `intelligence/document_*.py` | Structured docs → PDF/DOCX/MD/HTML |
| Document Workflow | `intelligence/document_workflow.py` | build → render → validate → register |
| Creator Packs | `intelligence/packs.py` | Marketplace packs → capability registration |

## Document workflow (no LLM PDF code)

`"Create a workout PDF"`:

1. Intent → `document_generation`
2. Capabilities → `reasoning`, `document`, `pdf` (not `python_execution`)
3. Plan → build_structured_document → render → validate → register
4. LLM returns **JSON content only**
5. `DocumentRenderer` produces the PDF
6. Artifact Validator + Artifact Manager register

## Capability Registry

Core capabilities: Chat, Document, Image, Spreadsheet, Presentation, Vision, OCR, Python (+ legacy aliases for compatibility).

```python
from app.intelligence.capability_registry import get_capability_registry
get_capability_registry().resolve_for_intent("document_generation")
```

## Creator Packs

- `GET /api/packs`
- `POST /api/packs/install` `{ "pack_id": "office-pack" }`
- `POST /api/packs/uninstall`

Packs: Office, Creative, Developer, Research. Installing registers pack capabilities with the registry (persisted in `data/installed_packs.json`).

## Artifact Intelligence

Artifacts store: original/enhanced prompt, execution plan, provider, model, validation status, version, intelligence JSON, preview path.

## Vision

Uploads of PNG/JPEG/WEBP/PDF auto-run Vision Service (OCR, caption, objects, scene, layout, tables) when possible. Manual: `POST /api/vision/analyze?file_id=`.

## Image prompts

Prompt Studio returns `image_prompt` for image intents: enhanced prompt, negative prompt, style, resolution, aspect ratio. Providers (OpenAI, ComfyUI, Gemini) consume metadata.

## Diagnostics

`GET /api/runtime/dashboard` includes capabilities, packs, diagnostics (execution/validation/provider/artifact/plans), and telemetry.

## APIs preserved

`/api/chat`, `/api/creator/generate`, `/api/artifacts`, workspaces, files, prompt-studio remain compatible.
