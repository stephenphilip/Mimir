# Offline AI Runtime Architecture Specification v1.0

## Project Vision
Build a **modular, privacy-first, fully offline AI Runtime**. Chat is only the first application. The runtime must eventually power multiple applications including Coding, Documents, Voice, Automation and Instagram assistants.

## Guiding Principles
- Offline-first
- Privacy-first
- Modular
- Interface-driven
- Incremental evolution (do not rewrite Mimir)
- Agent-based architecture
- Human-inspired memory
- Backward compatibility during migration

# Target Architecture

```
Frontend
    │
API (FastAPI)
    │
AI Runtime
 ├── Runtime Coordinator
 ├── Scheduler
 ├── Event Bus
 ├── Resource Monitor
 └── Plugin Manager
    │
Agent Runtime
 ├── Intent Agent
 ├── Planner Agent
 ├── Memory Agent
 ├── Reasoning Agent
 ├── Tool Agent
 ├── Validator Agent
 ├── Summarizer Agent
 └── Response Composer
    │
Memory System
Models
Tools
Storage
```

## Keep From Mimir
- FastAPI backend
- React frontend
- SQLite
- Runtime Coordinator
- Plugin loader
- Streaming
- Conversation storage
- Artifact system
- Ollama integration
- Repository pattern
- Interfaces/ABCs

## Replace Gradually
- Regex intent → AI Intent Agent
- Context Builder → Memory Manager
- Linear Orchestrator → Agent Runtime
- Markdown code execution → Tool Framework
- Key-value memory → Layered Memory
- Single-model routing → Multi-model runtime

## Memory Layers
- Working Memory
- Conversation Memory
- Episodic Memory
- Semantic Memory
- Project Memory
- Entity Memory
- Timeline Memory
- Knowledge Store

## Rules
- Never rewrite working code.
- Refactor incrementally.
- Every phase must compile.
- Preserve existing behaviour unless explicitly changed.
- One phase at a time.
