"""
Scheduler — Background job execution with lifecycle tracking.

Replaces raw threading.Thread daemon calls scattered across the codebase.
Currently used for:
  - Model download workers (previously in ModelService.trigger_background_download)

Future uses (Phase 4+):
  - Memory summarisation after conversation ends
  - Fact/entity extraction in the background
  - Agent parallel sub-task execution

Design decisions:
- Daemon threads — jobs die when the main process exits. Correct for local assistant.
- Job registry — completed/failed jobs kept in memory for status queries.
  Pruned to MAX_HISTORY_SIZE to avoid unbounded growth.
- Thread-safe — all dict access is guarded by a single lock.
- No priority queues yet — FIFO submit order. Phase 7 can add priority scheduling
  based on hardware resource availability (ResourceMonitor integration).
- No external dependency — stdlib threading only.
"""

from __future__ import annotations

import threading
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, Tuple


# How many terminal (completed/failed/cancelled) jobs to retain in memory
MAX_HISTORY_SIZE = 100


class JobStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


@dataclass
class Job:
    """Represents a single submitted background job."""

    id: str
    name: str
    fn: Callable
    args: Tuple = field(default_factory=tuple)
    kwargs: Dict[str, Any] = field(default_factory=dict)
    status: JobStatus = JobStatus.PENDING
    error: Optional[str] = None
    created_at: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )
    started_at: Optional[str] = None
    ended_at: Optional[str] = None


class Scheduler:
    """
    Lightweight background job scheduler backed by daemon threads.

    Usage:
        scheduler = Scheduler()

        def my_task(model_name: str):
            ...

        job_id = scheduler.submit("download:llama3.2:1b", my_task, "llama3.2:1b")
        status = scheduler.get_status(job_id)
    """

    def __init__(self) -> None:
        self._jobs: Dict[str, Job] = {}
        self._lock = threading.Lock()

    # ── Submission ──────────────────────────────────────────────────

    def submit(self, name: str, fn: Callable, *args: Any, **kwargs: Any) -> str:
        """
        Submit a callable to run in a daemon background thread.

        Args:
            name:   Human-readable job name (e.g. "download:qwen2.5-coder:7b").
            fn:     The callable to invoke.
            *args:  Positional arguments passed to fn.
            **kwargs: Keyword arguments passed to fn.

        Returns:
            Unique job ID string (UUID4).
        """
        job_id = str(uuid.uuid4())
        job = Job(id=job_id, name=name, fn=fn, args=args, kwargs=kwargs)

        with self._lock:
            self._jobs[job_id] = job

        thread = threading.Thread(
            target=self._execute,
            args=(job_id,),
            daemon=True,
            name=f"scheduler-{name}",
        )
        thread.start()
        return job_id

    # ── Status queries ──────────────────────────────────────────────

    def get_status(self, job_id: str) -> Optional[JobStatus]:
        """Return current status of a job, or None if job ID is unknown."""
        with self._lock:
            job = self._jobs.get(job_id)
        return job.status if job else None

    def get_job(self, job_id: str) -> Optional[Job]:
        """Return full Job record, or None if not found."""
        with self._lock:
            return self._jobs.get(job_id)

    def list_running(self) -> List[Dict[str, Any]]:
        """Return summary dicts for all currently running jobs."""
        with self._lock:
            return [
                {
                    "id": j.id,
                    "name": j.name,
                    "status": j.status,
                    "created_at": j.created_at,
                    "started_at": j.started_at,
                }
                for j in self._jobs.values()
                if j.status == JobStatus.RUNNING
            ]

    def list_all(self) -> List[Dict[str, Any]]:
        """Return summary dicts for all tracked jobs (running + history)."""
        with self._lock:
            return [
                {
                    "id": j.id,
                    "name": j.name,
                    "status": j.status,
                    "error": j.error,
                    "created_at": j.created_at,
                    "started_at": j.started_at,
                    "ended_at": j.ended_at,
                }
                for j in self._jobs.values()
            ]

    def is_running(self, name_prefix: str) -> bool:
        """Return True if any running job's name starts with name_prefix."""
        with self._lock:
            return any(
                j.name.startswith(name_prefix) and j.status == JobStatus.RUNNING
                for j in self._jobs.values()
            )

    def has_pending_or_running(self, name_prefix: str) -> bool:
        """Return True if any job matching name_prefix is pending or running."""
        with self._lock:
            return any(
                j.name.startswith(name_prefix)
                and j.status in (JobStatus.PENDING, JobStatus.RUNNING)
                for j in self._jobs.values()
            )

    # ── Internal execution ──────────────────────────────────────────

    def _execute(self, job_id: str) -> None:
        """Thread target — runs the job and updates its status."""
        with self._lock:
            job = self._jobs.get(job_id)

        if job is None:
            return

        job.status = JobStatus.RUNNING
        job.started_at = datetime.now(timezone.utc).isoformat()

        try:
            job.fn(*job.args, **job.kwargs)
            job.status = JobStatus.COMPLETED
        except Exception as exc:
            job.status = JobStatus.FAILED
            job.error = str(exc)
            print(f"[Scheduler] Job '{job.name}' ({job_id[:8]}) failed: {exc}")
        finally:
            job.ended_at = datetime.now(timezone.utc).isoformat()
            self._prune_history()

    def _prune_history(self) -> None:
        """Keep only the most recent MAX_HISTORY_SIZE terminal jobs."""
        with self._lock:
            terminal_statuses = {
                JobStatus.COMPLETED,
                JobStatus.FAILED,
                JobStatus.CANCELLED,
            }
            terminal = [
                j for j in self._jobs.values() if j.status in terminal_statuses
            ]
            # Sort by ended_at ascending so oldest are pruned first
            terminal.sort(key=lambda j: j.ended_at or "")
            for old_job in terminal[:-MAX_HISTORY_SIZE]:
                self._jobs.pop(old_job.id, None)


# ── Process-level singleton ─────────────────────────────────────────────────

_scheduler: Optional[Scheduler] = None
_scheduler_lock = threading.Lock()


def get_scheduler() -> Scheduler:
    """Return (or create) the process-wide Scheduler singleton."""
    global _scheduler
    with _scheduler_lock:
        if _scheduler is None:
            _scheduler = Scheduler()
        return _scheduler
