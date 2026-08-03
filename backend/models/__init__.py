"""
Models package — Model Management layer.

Phase 1: Empty scaffold. No logic moved here yet.

Phase 7: Multi-model runtime:
    - Reasoning Model (primary chat/QA)
    - Planning Model (task decomposition)
    - Intent Model (fast, lightweight classifier)
    - Embedding Model (semantic memory, RAG)
    - Vision Model (image understanding)
    - Speech Model (TTS/STT)

Each model role will have:
    - A dedicated selector with role-specific scoring weights
    - Independent VRAM allocation tracking
    - Role-aware keep_alive strategy

Current model logic lives in:
    - app/services/model_selector.py   ← MCDM utility scoring
    - app/services/model_service.py    ← Ollama sync + download
    - app/db.py ModelCatalog           ← Benchmark seeding
"""
# Phase 1: No exports yet. Package scaffold only.
