"""
Memory package — Layered Memory System.

Phase 1: Package scaffold + WorkingMemory (ephemeral in-request scratch space).
         MemoryManager re-exports existing MemoryService (no behavior change).
         ConversationMemory provides a thin typed wrapper for existing context.

Phase 3: Full layered memory architecture:
    - WorkingMemory   — ephemeral, per-request, in-memory (DONE Phase 1)
    - ConversationMemory — recent turns from DB (DONE Phase 1, refactored Phase 3)
    - EpisodicMemory  — session summaries stored in episodic_memory table
    - SemanticMemory  — factual knowledge, embeddings-backed (Phase 6)
    - ProjectMemory   — cross-chat project context (Phase 3)
    - EntityMemory    — named entities from entity_memory table (Phase 6)
    - TimelineMemory  — chronological user history (Phase 6)
    - KnowledgeStore  — embedded document store (Phase 6)

Design: Every memory type implements the same read/write interface
        so the MemoryManager can query all layers uniformly.
"""
from .working import WorkingMemory
from .manager import MemoryManager

__all__ = ["WorkingMemory", "MemoryManager"]
