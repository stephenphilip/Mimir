# Mimir Runtime Foundation

This document explains the runtime layer introduced to keep Mimir lightweight, fast to start, and easy to evolve — without rewriting working chat/inference code.

## Why RuntimeCoordinator exists

Previously, lifecycle concerns were scattered:

- Startup called `ModelService.preload_first_run_models()` (Ollama + downloads)
- The orchestrator talked directly to `ModelService` for unload/sync/download
- There was no single place for sessions, idle cleanup, or resource snapshots

`RuntimeCoordinator` (`backend/runtime/runtime_coordinator.py`) is the **only** runtime entry point. It:

- Wraps `ModelService` (does **not** replace it)
- Tracks conversation sessions
- Schedules inference slots (concurrency gate — no generation logic)
- Owns the resource monitor and plugin manifest loader
- Prepares models only when inference begins

```
UI → API → Orchestrator → RuntimeCoordinator → ModelService → Ollama
```

Inference text generation still lives in `OllamaProvider`. Planning/intent still live in the orchestrator.

## How lazy loading works

| Concern | When it loads |
|--------|----------------|
| Configuration | Import of `config` (cheap, cached) |
| Database schema/seed | First `SessionLocal()` / `ensure_db_ready()` |
| Model weights (Ollama) | First chat that needs a model (`prepare_model` / generate) |
| Ollama tag sync | First inference path or `/api/system/status` — **not** startup |
| Plugins / executors | First capability execution via `PluginLoader.get_executor` |
| Memory subsystems | First `MemoryService` profile/context call during a conversation |

Nothing is preloaded at process start unless a feature flag explicitly re-enables legacy behavior (`MIMIR_STARTUP_MODEL_PRELOAD`).

## Startup lifecycle

Target: **under two seconds**, no model load, no Ollama traffic by default.

1. Import `app.main` — load config modules only; **no** `init_db()`, **no** artifacts mkdir side effects beyond path helpers.
2. Uvicorn starts FastAPI.
3. `startup_event`:
   - Ensure project-relative directories (`backend/data/`, `artifacts/`)
   - `ensure_db_ready()` — local SQLite only
   - Read **installed model metadata from SQLite** (no `/api/tags`)
   - Load **plugin manifest metadata** (builtins + `extensions/*/plugin.json`) without importing plugin code
   - Call `RuntimeCoordinator.start()`
4. Ready to serve.

Feature flags (see `backend/config/settings.py`):

- `MIMIR_STARTUP_MODEL_PRELOAD=false` (default)
- `MIMIR_STARTUP_OLLAMA_SYNC=false` (default)

## Model lifecycle

1. **Select** — orchestrator picks a target via `ModelSelector` (unchanged).
2. **Sync / download** — `RuntimeCoordinator.sync_models_to_db` / `trigger_background_download` delegate to `ModelService` when a chat needs it.
3. **Prepare** — `RuntimeCoordinator.prepare_model(active)` unloads other Ollama residents and records the active model on the resource monitor.
4. **Infer** — `schedule_inference` acquires a concurrency slot; `OllamaProvider.generate_stream` runs inside that slot.
5. **Idle cleanup** — `idle_cleanup()` / shutdown may unload when `MIMIR_IDLE_MODEL_UNLOAD` is enabled.

## Resource monitoring

`backend/runtime/resource_monitor.py` samples **on demand** only:

- RAM (psutil)
- CPU percent
- GPU VRAM (nvidia-smi when available)
- Loaded model name (as tracked by the coordinator)
- Running tasks (sessions / inference slots)

Python API:

```python
from runtime.runtime_coordinator import get_runtime

snapshot = get_runtime().sample_resources()
```

No background polling thread. REST shapes for existing endpoints are unchanged; the monitor is available for future UI/HUD use.

## Directory structure

```
Mimir/
├── artifacts/                 # Generated files (project-relative)
├── extensions/                # Future external plugins (plugin.json + main.py)
├── docs/RUNTIME.md            # This file
├── backend/
│   ├── config/                # Paths, timeouts, feature flags
│   │   ├── paths.py
│   │   └── settings.py
│   ├── data/                  # SQLite database (assistant.db)
│   ├── runtime/               # Runtime foundation
│   │   ├── runtime_coordinator.py
│   │   ├── resource_monitor.py
│   │   └── plugin_loader.py
│   └── app/                   # Existing FastAPI app (preserved)
└── frontend/                  # Unchanged in this sprint
```

### Portable paths

Resolved via `config.paths.get_paths()`:

| Resource | Default location |
|----------|------------------|
| Database | `backend/data/assistant.db` |
| Artifacts | `artifacts/` |
| Venv | `backend/.venv` |
| Extensions | `extensions/` |

Overrides: `MIMIR_REPO_ROOT`, `MIMIR_DATA_DIR`, `MIMIR_ARTIFACTS_DIR`, `MIMIR_VENV_DIR`, `MIMIR_EXTENSIONS_DIR`.

No Windows usernames are hardcoded.

## Compatibility

- REST paths and SSE event types are unchanged.
- `ModelService` and the orchestrator pipeline steps are preserved.
- `preload_first_run_models` remains on `ModelService` for optional/manual use; it is not called at startup by default.
