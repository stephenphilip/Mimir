"""
WorkingMemory — Ephemeral in-request scratch space.

WorkingMemory is the AI Runtime's equivalent of a CPU's register file:
fast, temporary, and scoped to a single request. It holds intermediate
agent outputs that need to be passed between pipeline steps without
polluting the structured ExecutionContext fields or writing to the DB.

Lifecycle:
    - Created fresh for each Orchestrator.process_prompt() call.
    - Attached to ExecutionContext.working_memory at request start.
    - Garbage collected when the request ends (no DB persistence).

Persistence:
    - WorkingMemory itself is NEVER written to DB.
    - The WorkingMemoryLog DB table (db.py) is an OPTIONAL debug trace
      for development use only — not written by default.

Common keys (convention — not enforced):
    "raw_intent_result"   — raw output from IntentAgent (Phase 2+)
    "raw_plan"            — raw plan before validation (Phase 4+)
    "tool_call_requests"  — structured tool invocation requests (Phase 5+)
    "entity_mentions"     — entities detected in the current turn (Phase 6+)
    "summarizer_input"    — content fed to SummarizerAgent (Phase 6+)

Phase 1: Core implementation complete.
"""

from __future__ import annotations

from typing import Any, Dict, Iterator, List, Optional, Tuple


class WorkingMemory:
    """
    Key-value scratch space for intermediate agent results.

    Thread-safety: NOT thread-safe by design — WorkingMemory is
    per-request and per-agent (one goroutine/thread owns it at a time).
    If agents are ever parallelised (Phase 4+), callers must ensure
    appropriate synchronisation before sharing a WorkingMemory instance.

    Usage:
        wm = WorkingMemory()
        wm.set("intent", {"intent": "code_generation", "confidence": 0.87})
        intent = wm.get("intent")
        wm.set("prior_context", ["msg1", "msg2"], layer="conversation")
        print(wm.all())
    """

    def __init__(self) -> None:
        # Primary key-value store
        self._store: Dict[str, Any] = {}
        # Optional layer namespace for categorised storage
        self._layers: Dict[str, Dict[str, Any]] = {}

    # ── Primary key-value API ───────────────────────────────────────

    def set(self, key: str, value: Any, layer: Optional[str] = None) -> None:
        """
        Store a value.

        Args:
            key:   String key identifying the value.
            value: Any Python object. Not serialised.
            layer: Optional namespace (e.g. "intent", "memory", "plan").
                   Layer values are also accessible via get() without layer.
        """
        self._store[key] = value
        if layer is not None:
            self._layers.setdefault(layer, {})[key] = value

    def get(self, key: str, default: Any = None) -> Any:
        """Return value for key, or default if not found."""
        return self._store.get(key, default)

    def has(self, key: str) -> bool:
        """Return True if key exists."""
        return key in self._store

    def delete(self, key: str) -> None:
        """Remove a key. Safe to call even if key doesn't exist."""
        self._store.pop(key, None)
        for layer_store in self._layers.values():
            layer_store.pop(key, None)

    # ── Layer API ───────────────────────────────────────────────────

    def layer(self, name: str) -> Dict[str, Any]:
        """Return all key-value pairs in a named layer."""
        return dict(self._layers.get(name, {}))

    def layer_keys(self) -> List[str]:
        """Return all registered layer names."""
        return list(self._layers.keys())

    # ── Bulk operations ─────────────────────────────────────────────

    def update(self, data: Dict[str, Any], layer: Optional[str] = None) -> None:
        """Set multiple keys at once."""
        for k, v in data.items():
            self.set(k, v, layer=layer)

    def all(self) -> Dict[str, Any]:
        """Return a shallow copy of the entire store."""
        return dict(self._store)

    def clear(self) -> None:
        """Erase all stored data."""
        self._store.clear()
        self._layers.clear()

    # ── Iteration ───────────────────────────────────────────────────

    def items(self) -> Iterator[Tuple[str, Any]]:
        """Iterate over (key, value) pairs."""
        return iter(self._store.items())

    def keys(self) -> List[str]:
        """Return all stored keys."""
        return list(self._store.keys())

    def __len__(self) -> int:
        return len(self._store)

    def __contains__(self, key: str) -> bool:
        return key in self._store

    def __repr__(self) -> str:
        return f"WorkingMemory({len(self._store)} keys: {list(self._store.keys())})"
