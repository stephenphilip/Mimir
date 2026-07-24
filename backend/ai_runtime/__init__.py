"""
AI Runtime — Top-level package.

The AI Runtime is the central process-wide infrastructure layer.
It owns the EventBus, Scheduler, ResourceMonitor, and PluginManager.
The RuntimeCoordinator (in runtime/) is the singleton entry-point that
composes all of these together.

Phase 1: Package scaffold + EventBus + Scheduler created.
         No orchestration logic has been moved here yet.
Phase 4+: Agent Runtime dispatcher will live here.
"""
from .event_bus import EventBus, Event
from .scheduler import Scheduler, Job, JobStatus

__all__ = [
    "EventBus",
    "Event",
    "Scheduler",
    "Job",
    "JobStatus",
]
