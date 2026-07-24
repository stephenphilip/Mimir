"""
RuntimeCoordinator re-export — canonical path for AI Runtime layer.

Phase 1: RuntimeCoordinator lives in runtime/runtime_coordinator.py (unchanged).
         This module provides the new canonical import path so callers in
         future phases can import from ai_runtime.coordinator instead of
         navigating through the runtime/ subdirectory directly.

Usage (new canonical path):
    from ai_runtime.coordinator import get_runtime, RuntimeCoordinator

Usage (existing path — still works):
    from runtime.runtime_coordinator import get_runtime, RuntimeCoordinator
"""
from runtime.runtime_coordinator import RuntimeCoordinator, get_runtime

__all__ = ["RuntimeCoordinator", "get_runtime"]
