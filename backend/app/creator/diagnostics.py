"""In-memory execution diagnostics for Runtime Dashboard."""

from __future__ import annotations

import threading
import time
import uuid
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


@dataclass
class DiagnosticEntry:
    id: str
    category: str  # execution | validation | filesystem | provider | artifact
    message: str
    level: str = "info"  # info | warning | error
    timestamp: float = field(default_factory=time.time)
    metadata: Dict[str, Any] = field(default_factory=dict)


class ExecutionDiagnostics:
    """Thread-safe ring buffer of diagnostic entries."""

    _MAX = 500

    def __init__(self) -> None:
        self._entries: List[DiagnosticEntry] = []
        self._lock = threading.Lock()

    def log(
        self,
        category: str,
        message: str,
        *,
        level: str = "info",
        metadata: Optional[Dict[str, Any]] = None,
    ) -> DiagnosticEntry:
        entry = DiagnosticEntry(
            id=str(uuid.uuid4()),
            category=category,
            message=message,
            level=level,
            metadata=metadata or {},
        )
        with self._lock:
            self._entries.append(entry)
            if len(self._entries) > self._MAX:
                self._entries = self._entries[-self._MAX :]
        return entry

    def list_recent(self, limit: int = 100, category: Optional[str] = None) -> List[Dict[str, Any]]:
        with self._lock:
            items = list(self._entries)
        if category:
            items = [e for e in items if e.category == category]
        items = items[-limit:]
        return [
            {
                "id": e.id,
                "category": e.category,
                "message": e.message,
                "level": e.level,
                "timestamp": e.timestamp,
                "metadata": e.metadata,
            }
            for e in reversed(items)
        ]


# Process-wide diagnostics singleton
_diagnostics: Optional[ExecutionDiagnostics] = None
_diag_lock = threading.Lock()


def get_execution_diagnostics() -> ExecutionDiagnostics:
    global _diagnostics
    with _diag_lock:
        if _diagnostics is None:
            _diagnostics = ExecutionDiagnostics()
        return _diagnostics
