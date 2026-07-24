"""
ExecutionContext — Shared request-scoped data container.

This is the single object that flows through the entire pipeline (and later,
through every agent in the Agent Runtime). Each step reads from it and writes
its outputs back to it.

Phase 1 additions:
  - working_memory: Ephemeral scratch space for intermediate agent results.
                    Created fresh per request, never persisted to DB.
                    Agents can store/retrieve transient intermediate outputs here.
"""

from typing import Any, List, Dict, Optional
from pydantic import BaseModel, Field


class ExecutionContext(BaseModel):
    # ── Request identification ───────────────────────────────────────
    user: Optional[Dict[str, Any]] = None
    conversation: Optional[Dict[str, Any]] = None
    prompt: str
    attachments: List[Any] = Field(default_factory=list)

    # ── Intent + capability resolution ──────────────────────────────
    intent: Optional[str] = None
    intent_confidence: Optional[float] = None
    capabilities: List[str] = Field(default_factory=list)

    # ── Memory retrieval results ─────────────────────────────────────
    retrieved_memories: List[Dict[str, Any]] = Field(default_factory=list)
    retrieved_conversation_context: List[Dict[str, Any]] = Field(default_factory=list)
    retrieved_files: List[Dict[str, Any]] = Field(default_factory=list)

    # ── Model selection ──────────────────────────────────────────────
    selected_model: Optional[str] = None
    selected_provider: Optional[str] = None

    # ── Execution planning ───────────────────────────────────────────
    execution_plan: Optional[Any] = None

    # ── Outputs ──────────────────────────────────────────────────────
    generated_artifacts: List[Dict[str, Any]] = Field(default_factory=list)
    execution_metadata: Dict[str, Any] = Field(default_factory=dict)
    errors: List[str] = Field(default_factory=list)
    timing_metrics: Dict[str, float] = Field(default_factory=dict)
    execution_status: str = "pending"

    # ── Phase 1: Working Memory ──────────────────────────────────────
    # Ephemeral scratch space for intermediate agent results.
    # Type: Optional[WorkingMemory] — kept as Any here to avoid circular
    # imports between context.py and memory/working.py.
    # Set by pipeline_factory.py at request start.
    working_memory: Optional[Any] = Field(default=None, exclude=True)

    class Config:
        # Allow WorkingMemory (non-pydantic) to be stored
        arbitrary_types_allowed = True
