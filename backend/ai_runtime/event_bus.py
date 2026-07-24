"""
EventBus — Synchronous, in-process publish/subscribe system.

Design decisions:
- Synchronous (not async) — avoids complexity with FastAPI's event loop.
  Handlers must be fast; long-running work should be submitted to the Scheduler.
- In-process only — no external broker (Redis/Kafka). This is a local AI runtime.
- Thread-safe — handlers are snapshotted before dispatch; the lock is released
  before calling handlers so subscribers can safely call publish() themselves.
- Failure-isolated — a crashing handler never kills the bus or other handlers.

Phase 1: Wired into RuntimeCoordinator but not yet used by the Orchestrator.
Phase 4: Orchestrator replaced by Agent Runtime which routes through EventBus.

Standard event types (add more as agents are introduced):
    "session.started"        — conversation session opened
    "session.ended"          — conversation session closed
    "intent.classified"      — IntentAgent produced a classification
    "capabilities.resolved"  — CapabilityService resolved required capabilities
    "model.selected"         — ModelSelector chose a model
    "model.download.started" — background model pull initiated
    "model.download.progress"— background model pull progress update
    "model.download.done"    — model pull complete
    "inference.started"      — LLM generation started
    "inference.done"         — LLM generation complete
    "tool.started"           — Tool/executor invocation started
    "tool.done"              — Tool/executor invocation complete
    "memory.retrieved"       — Memory layer returned context
    "artifact.created"       — A file artifact was generated
"""

from __future__ import annotations

import threading
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Callable, Dict, List, Optional


@dataclass
class Event:
    """
    Immutable event envelope.

    Attributes:
        type:      Dot-separated event type string (e.g. "intent.classified").
        payload:   Event-specific data — any serialisable value.
        source:    Identifier of the component that published the event.
        session_id: Optional conversation session correlation ID.
        timestamp: UTC ISO-8601 string set at publish time.
    """

    type: str
    payload: Any = None
    source: str = ""
    session_id: Optional[str] = None
    timestamp: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )


class EventBus:
    """
    Thread-safe synchronous pub/sub event bus.

    Usage:
        bus = EventBus()

        def on_model_selected(event: Event):
            print(f"Model chosen: {event.payload}")

        bus.subscribe("model.selected", on_model_selected)
        bus.publish(Event(type="model.selected", payload="qwen2.5-coder:1.5b"))
        bus.unsubscribe("model.selected", on_model_selected)
    """

    def __init__(self) -> None:
        # event_type → list of handler callables
        self._handlers: Dict[str, List[Callable[[Event], None]]] = {}
        self._lock = threading.Lock()

    # ── Subscription management ─────────────────────────────────────

    def subscribe(self, event_type: str, handler: Callable[[Event], None]) -> None:
        """Register a handler for an event type. Idempotent for the same handler."""
        with self._lock:
            handlers = self._handlers.setdefault(event_type, [])
            if handler not in handlers:
                handlers.append(handler)

    def unsubscribe(self, event_type: str, handler: Callable[[Event], None]) -> None:
        """Remove a previously registered handler. Safe if handler not registered."""
        with self._lock:
            handlers = self._handlers.get(event_type, [])
            self._handlers[event_type] = [h for h in handlers if h is not handler]

    def subscribe_once(self, event_type: str, handler: Callable[[Event], None]) -> None:
        """Register a handler that auto-unsubscribes after first invocation."""
        def _wrapper(event: Event) -> None:
            self.unsubscribe(event_type, _wrapper)
            handler(event)

        self.subscribe(event_type, _wrapper)

    # ── Publishing ──────────────────────────────────────────────────

    def publish(self, event: Event) -> int:
        """
        Dispatch event to all registered handlers synchronously.

        Returns the number of handlers notified.
        Handlers are snapshotted before dispatch — subscribing inside a
        handler does NOT affect the current dispatch cycle.
        """
        with self._lock:
            handlers = list(self._handlers.get(event.type, []))

        notified = 0
        for handler in handlers:
            try:
                handler(event)
                notified += 1
            except Exception as exc:
                # A crashing handler must never kill the bus or sibling handlers.
                print(
                    f"[EventBus] Handler error for '{event.type}' "
                    f"in {getattr(handler, '__qualname__', repr(handler))}: {exc}"
                )
        return notified

    # ── Introspection ───────────────────────────────────────────────

    def subscriber_count(self, event_type: str) -> int:
        """Return number of handlers registered for an event type."""
        with self._lock:
            return len(self._handlers.get(event_type, []))

    def registered_types(self) -> List[str]:
        """Return all event types that have at least one subscriber."""
        with self._lock:
            return [k for k, v in self._handlers.items() if v]

    def clear(self) -> None:
        """Remove all subscriptions. Useful in tests."""
        with self._lock:
            self._handlers.clear()
