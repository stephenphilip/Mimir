# Mimir — AI-Native Personal Assistant Platform: Complete Architecture Reference

> **Purpose:** This document provides a thorough architectural reference of the Mimir platform for use as a comparison input source for a similar system. It covers tech stack, module design, data layer, inference pipeline, runtime coordination, plugin system, and frontend architecture.

---

## 1. High-Level Overview

Mimir is a **fully local, privacy-first AI personal assistant** that runs Large Language Models (LLMs) on the user's own hardware using [Ollama](https://ollama.com). It is structured as a **decoupled, two-process application**:

| Layer | Technology | Port |
|---|---|---|
| **Backend API** | Python / FastAPI (Uvicorn) | `:8000` |
| **Frontend UI** | React 19 + TypeScript / Vite | `:5173` |
| **LLM Runtime** | Ollama (local inference server) | `:11434` |
| **Database** | SQLite (via SQLAlchemy ORM) | `backend/data/assistant.db` |

Communication between frontend and backend is via **REST + Server-Sent Events (SSE)** for streaming. The backend never connects to any cloud AI service — all inference is done locally via Ollama.

---

## 2. Repository Structure

```
Mimir/
├── run_platform.py          # One-shot launcher (installs Ollama, starts both servers)
├── backend/
│   ├── app/
│   │   ├── main.py          # FastAPI app, all REST endpoints
│   │   ├── db.py            # SQLAlchemy ORM models + lazy DB init
│   │   ├── core/
│   │   │   ├── orchestrator.py   # Master request pipeline (11-step SSE flow)
│   │   │   └── context.py        # ExecutionContext dataclass
│   │   ├── services/
│   │   │   ├── intent_service.py      # Regex-based intent classifier
│   │   │   ├── capability_service.py  # Intent → capability map
│   │   │   ├── context_builder.py     # Prompt assembly + memory retrieval
│   │   │   ├── model_selector.py      # Multi-criteria model router (MCDM)
│   │   │   ├── model_service.py       # Ollama sync, download, VRAM mgmt
│   │   │   ├── execution_engine.py    # Code extraction + executor dispatch
│   │   │   ├── gpu_service.py         # Hardware detection (nvidia-smi/wmic)
│   │   │   ├── planner.py             # Lightweight plan builder (stub)
│   │   │   └── memory/
│   │   │       ├── memory_service.py  # Facade for all memory subsystems
│   │   │       ├── storage.py         # Key-value memory persistence
│   │   │       ├── retrieval.py       # Memory fetch layer
│   │   │       ├── ranking.py         # Memory prioritisation
│   │   │       └── injection.py       # Memory-to-prompt injector
│   │   ├── providers/
│   │   │   └── ollama_provider.py    # Ollama streaming generate client
│   │   ├── repositories/
│   │   │   └── sqlite_repositories.py # Concrete SQLAlchemy implementations
│   │   ├── interfaces/
│   │   │   ├── services.py       # ABCs for all service contracts
│   │   │   ├── repositories.py   # ABCs for all repository contracts
│   │   │   ├── providers.py      # ABC for inference provider
│   │   │   └── executors.py      # ABC for code executors
│   │   └── extensions/
│   │       ├── python.py         # PythonExecutor (subprocess sandboxing)
│   │       ├── excel.py          # ExcelExecutor stub
│   │       ├── pdf.py            # PDFExecutor stub
│   │       ├── browser.py        # BrowserExecutor stub
│   │       ├── filesystem.py     # FilesystemExecutor stub
│   │       ├── github.py         # GitHubExecutor stub
│   │       └── speech.py         # SpeechExecutor stub
│   ├── config/
│   │   ├── settings.py      # Frozen dataclass + env-var overrides (lru_cache)
│   │   └── paths.py         # Path resolution (repo-relative, env-var overridable)
│   ├── runtime/
│   │   ├── runtime_coordinator.py  # Process-wide singleton runtime
│   │   ├── plugin_loader.py        # Manifest-based lazy plugin loader
│   │   └── resource_monitor.py     # Task/session resource tracking
│   ├── data/                # SQLite database (git-ignored)
│   └── requirements.txt
├── frontend/
│   ├── src/
│   │   ├── App.tsx          # Root component, all state management
│   │   ├── types.ts         # Shared TypeScript types
│   │   ├── api/client.ts    # fetch wrapper (REST + SSE)
│   │   ├── components/      # 18 UI components
│   │   └── utils/           # Artifact helpers, timeline builder, workspace
│   └── package.json
├── extensions/              # (empty) — user-side plugin drop zone
├── artifacts/               # Generated files (PDFs, Excel, charts)
└── docs/
    └── RUNTIME.md
```

---

## 3. Database Layer

### Technology
- **SQLite** via **SQLAlchemy 2.x ORM**
- Single file: `backend/data/assistant.db`
- Lazy initialization: no I/O at import time — DB is created on first HTTP request

### Schema (10 Tables)

| Table | Purpose |
|---|---|
| `users` | Single user record (id=1, name) |
| `conversations` | Chat sessions (UUID PK, title, project_id FK) |
| `messages` | Individual turn records (sender: user/assistant, content, tokens_count) |
| `memory` | Key-value user profile facts (personality traits, preferences) |
| `projects` | Logical grouping for chats (name, path) |
| `installed_models` | Mirror of Ollama's tag list (name, status, size) |
| `model_catalog` | Pre-seeded model specs: RAM/VRAM needs, TPS, benchmark scores |
| `settings` | Key-value app config (user_name, personality, theme, execution_env) |
| `generated_artifacts` | File records for outputs (PDF, Excel, charts, linked to message_id) |
| `downloads` | Live download progress tracker (model_name, progress %, status) |
| `execution_history` | Log of all code runs (code, stdout, stderr, exit_code) |

### Key Design Decisions
- **No migrations library**: Schema is created idempotently via `Base.metadata.create_all()` on startup.
- **Lazy DB proxy**: `SessionLocal` is a proxy callable; the SQLite engine is only created on first call to `ensure_db_ready()`, avoiding I/O at import time.
- **Request-scoped sessions**: Each API request gets its own `Session` instance, yielded by a FastAPI `Depends(get_db)` generator. The `/api/chat` endpoint manages its own session lifecycle because of streaming.
- **Thread-local sessions in workers**: Background model download threads open their own sessions independently from the request thread.

---

## 4. Backend Architecture

### 4.1 FastAPI Application (`main.py`)

The backend is a single **FastAPI** application served by **Uvicorn**. It exposes:

| Endpoint | Method | Purpose |
|---|---|---|
| `GET /` | HTML | Landing page (links to UI + Swagger) |
| `POST /api/chat` | Stream (SSE) | Main chat endpoint — all inference goes through here |
| `GET /api/conversations` | JSON | List all conversations |
| `POST /api/conversations` | JSON | Create a new conversation |
| `DELETE /api/conversations/{id}` | JSON | Delete a conversation |
| `POST /api/conversations/{id}/project` | JSON | Move chat to a project |
| `GET /api/conversations/{id}/messages` | JSON | Get all messages + artifacts |
| `GET /api/settings` | JSON | Get user/app settings |
| `POST /api/settings` | JSON | Update user/app settings |
| `GET /api/system/status` | JSON | Hardware info + installed models + active downloads |
| `GET /artifacts/{filename}` | FileResponse | Serve generated files |

### 4.2 Layered Architecture

```
HTTP Request
    ↓
FastAPI Route (main.py)
    ↓ constructs all dependencies per request
Orchestrator (core/)
    ↓ runs 11-step pipeline
Services (services/)          ←→   Interfaces (interfaces/)
    ↓
Repositories (repositories/)  →   SQLite DB (data/)
    ↓
Providers (providers/)        →   Ollama HTTP API (:11434)
    ↓
Extensions (extensions/)      →   subprocess (PythonExecutor)
    ↑
Runtime (runtime/)            ←   singleton, per-process
```

The entire dependency graph is **hand-wired** in `main.py` per request — no DI framework (like `injector` or `dependency_injector`) is used. All major services implement an Abstract Base Class from `interfaces/`.

### 4.3 Interface-First Design

Every cross-layer boundary is expressed as an **ABC**:

- `IIntentService` → classify prompt → intent + confidence
- `ICapabilityService` → intent → list of capability strings
- `IMemoryService` → user profile, recent context, project context
- `IContextBuilder` → enriches `ExecutionContext` with system/user prompts
- `IModelSelector` → selects best available model given hardware + task
- `IPlanner` → builds a high-level plan (stub)
- `IExecutionEngine` → dispatches code to executors, returns results
- `IProvider` → streaming inference against LLM
- `IGPUService` → hardware detection
- `IModelService` → Ollama sync + lifecycle
- `IConversationRepository`, `IMemoryRepository`, `IModelRepository`, `IArtifactRepository`, `ISettingRepository`, `IModelCatalogRepository`

---

## 5. Inference Pipeline (The Orchestrator)

The `Orchestrator.process_prompt()` method is a **11-step streaming generator** that emits JSON SSE events at each stage. Every event has a `type` field.

### SSE Event Types

| `type` | Payload | Meaning |
|---|---|---|
| `status` | `{status: string}` | Pipeline progress update |
| `content` | `{text: string}` | LLM response token chunk |
| `download_progress` | `{model, progress}` | Model pull progress % |
| `execution_result` | `{success, stdout, stderr, exit_code, artifacts}` | Python code output |
| `error` | `{message}` | Fatal error |
| `done` | `{conversation_id}` | Stream complete |

### Pipeline Steps

```
Step 1: Initialize ExecutionContext
Step 2: Save user message to DB
Step 3: Intent Engine → classify intent + confidence (regex-based)
Step 4: Capability Engine → map intent to capabilities list
Step 5: Planner → create lightweight execution plan
Step 6: Context Builder → fetch memory, recent messages, project context → build system_prompt + user_prompt
Step 7: Model Selection → MCDM utility scoring → pick best installed model
         → if ideal model missing, trigger background download
Step 8: Runtime preparation → unload other models from VRAM
Step 9: Inference scheduling → semaphore-gated concurrency slot
         → stream OllamaProvider.generate_stream() → yield content chunks
Step 10: Save assistant message to DB
Step 11: (Conditional) Python execution → extract code block → run in subprocess → collect artifacts
         → auto-rename conversation title from first message
→ yield done event
```

---

## 6. Intent & Capability Classification

### Intent Engine (`intent_service.py`)
**Method**: Regex keyword scoring (no NLP model, zero latency).

- Rules are dictionaries of `intent_name → [regex_patterns]`
- Each pattern hit increments an intent score
- Winning intent = highest score, falls back to `"general_reasoning"`
- Confidence formula: `min(0.95, 0.5 + (max_score / total_score) * 0.45)`
- A boost rule fires when `pdf/document/report` + `generate/create/make` co-occur

**Supported Intents:**
- `document_generation` (PDF, report)
- `spreadsheet_generation` (Excel, CSV, table)
- `data_visualization` (chart, plot, graph)
- `code_generation` (code, Python, script, etc.)
- `translation`
- `writing` (email, essay, summary)
- `general_reasoning` (default/fallback)

### Capability Engine (`capability_service.py`)
**Method**: Static lookup table (intent → capability list).

| Intent | Resolved Capabilities |
|---|---|
| `document_generation` | `reasoning, python_execution, pdf_generation` |
| `spreadsheet_generation` | `reasoning, python_execution, excel_generation` |
| `data_visualization` | `reasoning, python_execution, chart_generation` |
| `code_generation` | `reasoning, coding, python_execution` |
| `translation` | `reasoning, translation` |
| `writing` | `reasoning, text_processing` |
| `general_reasoning` | `reasoning` |

The capability list drives: (a) model selection weights, (b) system prompt augmentation, (c) execution pipeline activation.

---

## 7. Model Selection (MCDM Router)

**File:** `model_selector.py`  
**Algorithm:** Multi-Criteria Decision Making (MCDM) utility scoring.

### Scoring Formula

```
utility = (0.6 × quality_score) + (0.4 × tps_score)
         + 30.0 if model is already installed  ← Local Readiness Premium
```

**Quality Score** = weighted dot product of `[reasoning, coding, math, conversational]` benchmark scores × capability-specific weight vector.

**TPS Score** = tokens/sec estimate (CPU or GPU based on VRAM availability), normalized to 0–100. GPU TPS is used when VRAM capacity ≥ required VRAM; otherwise linearly interpolated.

**Capability Weight Vectors** (per dimension: Reasoning, Coding, Math, Conversational):

| Capability | Reasoning | Coding | Math | Conversational |
|---|---|---|---|---|
| `general_reasoning` | 0.6 | 0.0 | 0.0 | 0.4 |
| `coding` | 0.1 | 0.8 | 0.0 | 0.1 |
| `python_execution` | 0.2 | 0.7 | 0.0 | 0.1 |
| `translation` | 0.4 | 0.0 | 0.0 | 0.6 |
| `pdf_generation` | 0.3 | 0.4 | 0.1 | 0.2 |

**Feasibility gate**: Models requiring > 1.1× available RAM are excluded entirely.

**Ideal model for background pull**: A second pass over the catalog without the readiness premium finds the absolute best fit — if different from the active model, it is pulled in the background.

### Seeded Model Catalog

| Model | Params | RAM Req | VRAM Req | Reasoning | Coding | Math | Conversational |
|---|---|---|---|---|---|---|---|
| `llama3.2:1b` | 1.3B | 4 GB | 2 GB | 55 | 35 | 40 | 60 |
| `llama3.2:3b` | 3.2B | 6 GB | 3.2 GB | 65 | 50 | 55 | 70 |
| `qwen2.5-coder:1.5b` | 1.5B | 4 GB | 2.2 GB | 60 | 68 | 62 | 65 |
| `qwen2.5-coder:7b` | 7.2B | 16 GB | 8 GB | 80 | 85 | 82 | 80 |
| `gemma2:2b` | 2.6B | 6 GB | 3 GB | 63 | 45 | 52 | 68 |
| `mistral:7b` | 7.2B | 16 GB | 8 GB | 72 | 55 | 68 | 75 |

---

## 8. Context Builder & Memory System

### Context Builder (`context_builder.py`)
Assembles the full prompt pair `(system_prompt, user_prompt)` sent to Ollama.

**System Prompt contains:**
- Identity: "You are Mimir, a local AI personal assistant."
- User name + personality (from settings)
- Active capabilities list
- Critical behavioural rules (focus on latest message, entity preservation)
- Retrieved user memory facts (key: value pairs)
- (Conditional) File creation protocol: step-by-step instructions for generating PDF/Excel/charts with specific libraries

**User Prompt contains:**
- Shared project context (from other chats in the same project, truncated to 500 chars each)
- Conversation history (last 4 messages = 2 prior turns), truncated to 1200 chars each
- Current user message with role labels

### Memory System (`services/memory/`)
Structured as a **lazy-initialised facade** with four sub-modules:

| Module | Role |
|---|---|
| `MemoryStorage` | Persist/read key-value memory via `IMemoryRepository` |
| `MemoryRetrieval` | Fetch all memories for a user |
| `MemoryRanking` | Sort/prioritize memories (stub, returns as-is) |
| `MemoryInjection` | Format memories for prompt injection |

Memory is stored as flat key-value pairs in the `memory` table, keyed by `user_id`. Values include personality traits, preferences, user profile facts.

**Project Context**: For conversations belonging to a project, recent messages from _other_ conversations in the same project are injected as `SHARED PROJECT KNOWLEDGE` — enabling cross-chat continuity within a project.

---

## 9. Runtime Coordinator

**File:** `runtime/runtime_coordinator.py`  
**Pattern:** Process-wide singleton (`get_runtime()` returns a cached instance via threading lock).

### Responsibilities
- **Session lifecycle**: `begin_session()` / `end_session()` track active conversations
- **Model lifecycle delegation**: delegates to `ModelService` for sync, download, unload
- **Inference concurrency**: `threading.Semaphore(max_concurrent_inferences)` gates parallel generation (default: 1)
- **Context manager** `schedule_inference()`: acquires semaphore slot, registers task in monitor, releases on exit
- **Plugin loading**: delegates to `PluginLoader` (lazy, manifest-first)
- **Resource monitoring**: tracks loaded model, last inference time for idle unloading
- **Idle cleanup**: unloads model from Ollama if idle > `idle_unload_delay_s` (default: 300s)

### Request Binding Pattern
`ModelService` requires a live SQLAlchemy `Session` (because repositories are session-scoped). The runtime does not own a permanent session. Instead, `_build_runtime_for_request(db)` binds a fresh `ModelService` to the runtime at the start of each request and unbinds it at the end.

---

## 10. Model Service & Ollama Integration

**File:** `services/model_service.py`

| Method | Mechanism |
|---|---|
| `detect_hardware()` | Runs `nvidia-smi` (NVIDIA GPU) or `wmic` (Windows fallback) via subprocess; uses `psutil` for RAM; result cached for `hardware_cache_ttl_s` (30s) |
| `sync_models_to_db()` | Calls `GET /api/tags` on Ollama; upserts `InstalledModel` rows, deletes stale ones |
| `get_loaded_models()` | Calls `GET /api/ps` on Ollama to find models currently in VRAM |
| `unload_other_models()` | Calls `POST /api/generate` with `keep_alive: 0` for all non-active loaded models |
| `trigger_background_download()` | Starts a daemon thread that calls `POST /api/pull` (streaming) and updates download progress in DB |

### Ollama Provider (`providers/ollama_provider.py`)
Calls `POST /api/generate` with:
- `stream: true` for SSE chunks
- `keep_alive: "30m"` — keeps model warm between turns (significant latency win on CPU)
- `num_predict: 3072` — max output tokens cap
- `temperature: 0.35` — low temperature for focused, factual responses
- Connection timeout: 10s, read timeout: unlimited (allows long CPU generations)

---

## 11. Code Execution Subsystem

### Execution Engine (`services/execution_engine.py`)
- Extracts Python code blocks from LLM markdown output using regex: ` ```python ... ``` `
- Dispatches to a registered executor via `IExecutor.can_execute(capability)`
- Lazy factory: executors are loaded from plugins on first use (not at startup)

### Python Executor (`extensions/python.py`)
- Writes extracted code to a temp `.py` file in the workspace directory
- Runs it as a **subprocess** using the venv Python at `backend/.venv`
- `cwd` is set to the artifacts directory so outputs land there automatically
- Timeout: 120s (configurable via `MIMIR_PYTHON_EXEC_TIMEOUT_S`)
- Pre/post scans the artifacts directory to detect new files created by the script
- New files are registered as `GeneratedArtifact` records in the DB
- Returns: `{success, stdout, stderr, exit_code, artifacts[]}`

**Libraries pre-installed in the execution venv:**
- `fpdf2` — PDF generation
- `openpyxl`, `pandas` — Excel/CSV
- `matplotlib`, `seaborn`, `numpy` — Charts/visualization
- `python-docx` — Word documents

### Plugin System (`runtime/plugin_loader.py`)
Manifest-based lazy loader:
- At startup: reads `plugin.json` manifests (metadata only, no code import)
- On first use: imports the module and constructs the class
- Built-in plugins: Python Executor (enabled), Excel stub, Filesystem stub
- External plugins: drop a directory with `plugin.json` into `/extensions/`
- Manifest format: `{id, name, version, capability, entry: "module.path:ClassName"}`

---

## 12. Hardware Detection

**File:** `services/gpu_service.py`

Detection order:
1. `nvidia-smi --query-gpu=name,memory.total --format=csv,noheader,nounits` (NVIDIA GPUs)
2. `wmic path win32_VideoController get name,AdapterRAM` (Windows fallback, any GPU > 512 MB VRAM)
3. `psutil.virtual_memory().total` for system RAM

**Hardware category**: `"high"` if GPU present with ≥ 4 GB VRAM or RAM ≥ 16 GB, else `"low"`.  
Category determines first-run default model selection.

---

## 13. Configuration System

**Two-layer configuration:**

### Layer 1: Static/Infrastructure (`config/paths.py`)
- File paths: repo root, data dir, artifacts dir, venv dir, extensions dir
- All overridable via `MIMIR_*` environment variables
- Cached via `@lru_cache(maxsize=1)` — computed once per process

### Layer 2: Runtime/Behavioural (`config/settings.py`)
- Frozen dataclass — immutable after creation
- All values read from environment variables with hardcoded defaults
- Cached via `@lru_cache(maxsize=1)`

**Key settings and defaults:**

| Setting | Env Var | Default |
|---|---|---|
| Ollama URL | `MIMIR_OLLAMA_URL` | `http://127.0.0.1:11434` |
| Python exec timeout | `MIMIR_PYTHON_EXEC_TIMEOUT_S` | 120s |
| Max concurrent inferences | `MIMIR_MAX_CONCURRENT_INFERENCES` | 1 |
| Hardware cache TTL | `MIMIR_HARDWARE_CACHE_TTL_S` | 30s |
| Idle unload delay | `MIMIR_IDLE_UNLOAD_DELAY_S` | 300s |
| Enable startup model preload | `MIMIR_STARTUP_MODEL_PRELOAD` | false |
| Enable startup Ollama sync | `MIMIR_STARTUP_OLLAMA_SYNC` | false |
| Enable idle model unload | `MIMIR_IDLE_MODEL_UNLOAD` | true |

---

## 14. Frontend Architecture

### Technology Stack

| Component | Library |
|---|---|
| Framework | React 19 (functional components + hooks) |
| Build tool | Vite 8 |
| Language | TypeScript 6 |
| Styling | Vanilla CSS (`index.css` — 36KB, full design system) |
| Icons | Lucide React |
| Markdown rendering | `react-markdown` + `remark-gfm` + `rehype-highlight` |
| Code highlighting | `highlight.js` |
| Linting | `oxlint` |

### State Management

**No external state library** (no Redux, no Zustand). All state lives in the root `App.tsx` as `useState` hooks:

| State | Type | Purpose |
|---|---|---|
| `conversations` | `Conversation[]` | Sidebar list |
| `activeConvId` | `string` | Currently viewed chat |
| `messages` | `Message[]` | Current chat history |
| `isGenerating` | `boolean` | Stream lock |
| `pipeline` | `string[]` | Accumulated status SSE events |
| `streamText` | `string` | Accumulating LLM token chunks |
| `streamExecution` | `ExecutionResult\|null` | Python execution result |
| `liveDownloads` | `Record<string,number>` | Real-time download % overlays |
| `systemStatus` | `SystemStatus\|null` | Hardware + models info (polled every 5s) |
| `workspace` | `WorkspaceState` | Pinned/archived/project state (localStorage) |

### Client-Side Persistence (localStorage)

`WorkspaceState` is persisted to `localStorage` under the key `mimir_workspace`:
```typescript
{
  pinned: string[],          // Pinned chat IDs
  archived: string[],        // Archived chat IDs
  titleOverrides: Record<string, string>,  // Client-side title renames
  projects: {id, name}[],   // Project definitions
  projectByChat: Record<string, string>,   // Chat → project mapping
}
```

This is intentionally client-local — projects exist in localStorage plus the `project_id` FK in the conversations table (synced via API calls).

### Frontend Components (18 total)

| Component | Role |
|---|---|
| `App.tsx` | Root, all state, SSE stream parser |
| `Sidebar` | Navigation, conversation list, project tree, search |
| `ChatWindow` | Scrollable message list (forwards ref for scroll control) |
| `ChatBubble` | Individual message render (user/assistant, markdown) |
| `MarkdownContent` | `react-markdown` with code highlighting |
| `PromptInput` | Multi-line textarea with file attachment and send controls |
| `FileUploader` | Drag-and-drop file picker with text preview extraction |
| `ArtifactCard` | Download card for generated files (PDF, Excel, etc.) |
| `ExecutionTimeline` | Step-by-step pipeline status display |
| `StatusBar` | Bottom bar: model name, hardware info, connection status |
| `DownloadTray` | Floating overlay showing active model download progress |
| `SettingsPanel` | User name, personality, theme form |
| `Greeting` | Welcome screen with quick-action prompt chips |
| `ChatContextMenu` | Right-click context menu for chat list items |
| `ChatOutline` | Conversation outline/header |
| `MessageActions` | Per-message actions (copy, retry) |
| `ModelsView` | Installed model list (coming soon tab) |
| `CursorGlow` | Ambient cursor glow visual effect |

### SSE Stream Parsing (in `App.tsx`)

The frontend reads `ReadableStream` from the `/api/chat` response, decodes chunks, splits on `\n\n`, and parses `data: {...}` JSON lines. Each event type is handled:
- `status` → accumulated into `pipeline[]` → drives `ExecutionTimeline`
- `content` → appended to `streamText` → drives live `liveMessage` display
- `download_progress` → updates `liveDownloads` map
- `execution_result` → sets `streamExecution`
- `done` → commits assembled `Message` to `messages[]`, triggers DB reconciliation fetch

---

## 15. Platform Launcher (`run_platform.py`)

Single Python script to bootstrap the entire platform:

1. **Check/Install Ollama**: Detects via `shutil.which("ollama")`; if missing, downloads platform-specific installer (Windows `.exe`, macOS `.zip`, Linux `curl | sh`)
2. **Start Ollama daemon**: If not already running on `:11434`
3. **Resolve Python**: Finds `.venv` in `backend/` or repo root
4. **Install frontend deps**: Runs `npm install` if `node_modules/vite` is missing
5. **Launch backend**: `uvicorn app.main:app --reload --host 127.0.0.1 --port 8000`
6. **Launch frontend**: `npm run dev -- --host 127.0.0.1 --port 5173`
7. **Monitor**: Polls both processes; on Ctrl+C, terminates both cleanly

---

## 16. Concurrency & Threading Model

| Concern | Mechanism |
|---|---|
| HTTP server concurrency | Uvicorn async workers (FastAPI) |
| Inference concurrency cap | `threading.Semaphore(max_concurrent=1)` in RuntimeCoordinator |
| Model download | Daemon `threading.Thread` per download, owns its own DB session |
| Hardware cache | Module-level globals `_HW_CACHE` / `_HW_CACHE_AT` (TTL-based, unguarded — acceptable for read-heavy cache) |
| Session state | `threading.Lock` in RuntimeCoordinator for `_sessions`, `_active_model`, `_last_inference_at` |
| DB sessions | Per-request `Session` from `SessionLocal()`, closed in `finally` block; thread-local for download workers |

---

## 17. Key Architectural Decisions & Design Patterns

| Decision | Rationale |
|---|---|
| **All-local inference (Ollama)** | Privacy, no API keys, no cloud dependency, offline-first |
| **SQLite over PostgreSQL** | Zero-configuration, single-user, local assistant use case |
| **Lazy DB init** | Fast startup — DB only created on first request, not at import |
| **Interface-first (ABCs)** | Enables testing with mocks; decouples layers; allows swapping providers |
| **Request-scoped dependency wiring** | Avoids shared mutable state; each request wires its own service graph |
| **Regex intent engine (no LLM for routing)** | Zero latency for intent detection; keeps model inference focused on content |
| **MCDM model router** | Objective, hardware-aware model selection without user configuration |
| **Local readiness premium (+30)** | Prevents unnecessary cold-start downloads when a good model is already installed |
| **Background model download** | User gets a response immediately using current best model; ideal model pulled in parallel |
| **SSE for streaming** | Native browser API; real-time pipeline status visible to user; no WebSocket complexity |
| **Subprocess code execution** | Isolation from backend process; real pip packages; simple artifact detection via filesystem diff |
| **Manifest-first plugin loading** | Startup stays fast — plugin code never imported until capability is first needed |
| **Client-side workspace (localStorage)** | Pinning, archiving, renaming, projects — purely UI concerns, no server round-trips |

---

## 18. Dependencies Summary

### Backend (Python)

| Package | Version | Role |
|---|---|---|
| `fastapi` | ≥0.100 | REST API framework |
| `uvicorn` | ≥0.22 | ASGI server |
| `sqlalchemy` | ≥2.0 | ORM + SQLite driver |
| `pydantic` | ≥2.0 | Request/response model validation |
| `requests` | ≥2.31 | HTTP client for Ollama API calls |
| `psutil` | ≥5.9 | System RAM detection |
| `pandas` | ≥2.0 | Data processing (execution env) |
| `openpyxl` | ≥3.1 | Excel file generation |
| `matplotlib` | ≥3.7 | Chart generation |
| `seaborn` | ≥0.12 | Statistical visualizations |
| `numpy` | ≥1.24 | Numerical operations |
| `fpdf2` | ≥2.7 | PDF generation |
| `python-docx` | ≥0.8 | Word document generation |

### Frontend (Node.js/npm)

| Package | Version | Role |
|---|---|---|
| `react` | ^19.2 | UI framework |
| `react-dom` | ^19.2 | DOM renderer |
| `vite` | ^8.1 | Build tool + dev server |
| `typescript` | ~6.0 | Type system |
| `lucide-react` | ^1.24 | Icon library |
| `react-markdown` | ^10.1 | Markdown rendering |
| `remark-gfm` | ^4.0 | GitHub Flavored Markdown |
| `rehype-highlight` | ^7.0 | Code syntax highlighting |
| `highlight.js` | ^11.11 | Syntax highlighter |

### External Runtime Dependency

| Dependency | Version | Role |
|---|---|---|
| **Ollama** | Latest stable | Local LLM inference server; auto-installed by `run_platform.py` |

---

## 19. What Is NOT Implemented (Future / Stubs)

- **Vector embeddings / RAG** — `IProvider.get_embeddings()` raises `NotImplementedError`
- **Vision / multimodal** — `generate_vision()` raises `NotImplementedError`
- **Structured JSON output / tool calling** — provider stubs, not yet wired
- **Excel, PDF, Filesystem, Browser, GitHub, Speech executors** — stub files exist but all disabled in plugin manifest
- **Memory ranking** — `MemoryRanking.rank_memories()` returns memories unmodified
- **Planner** — `Planner.create_plan()` is a near-stub (no complex multi-step planning)
- **Plugin Marketplace UI** — renders "Coming Soon" in frontend
- **Models view** — navigation tab exists, marked coming soon
- **Authentication / multi-user** — single user (id=1) hardcoded

---

## 20. Data Flow: End-to-End Example

> User types: _"Create an Excel expense tracker with 10 rows"_

```
1. Frontend: POST /api/chat { conversation_id, prompt }
   ↓ (SSE stream opens)
2. Orchestrator.process_prompt() starts
3. IntentService.classify() → intent="spreadsheet_generation" (confidence=0.87)
4. CapabilityService.resolve() → ["reasoning","python_execution","excel_generation"]
5. ContextBuilder.build_context():
   - system_prompt built with file-creation protocol (openpyxl instructions)
   - user_prompt: last 4 messages + current request
6. model_selector.select_best_model() → e.g., "qwen2.5-coder:1.5b" (installed, best coding score)
7. runtime.prepare_model() → unloads other models from VRAM
8. runtime.schedule_inference() → acquires semaphore
9. OllamaProvider.generate_stream():
   - Sends system_prompt + user_prompt to Ollama /api/generate
   - Streams tokens → yields "content" SSE events to frontend
   - Frontend displays markdown as it streams in
10. Full response saved to messages table
11. ExecutionEngine.execute():
    - Regex extracts ```python ... ``` block from response
    - PythonExecutor runs it via subprocess (cwd = artifacts/)
    - New file "expense_tracker.xlsx" detected in artifacts/
    - GeneratedArtifact record created in DB
    - "execution_result" SSE event sent to frontend with artifact info
12. "done" SSE event → frontend commits message + triggers DB reconciliation fetch
13. Frontend shows ArtifactCard with download link → /artifacts/expense_tracker.xlsx
```

---

*Document generated: 2026-07-24 | Source: stephenphilip/Mimir repository*
