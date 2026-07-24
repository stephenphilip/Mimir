"""
Backward-compatible re-export hub for all service interfaces.

This file previously contained all ABCs directly.
They are now split into domain-specific files for clarity:
  - agent_interfaces.py  : IIntentService, ICapabilityService, IContextBuilder,
                           IModelSelector, IPlanner, IExecutionEngine
  - memory_interfaces.py : IMemoryService
  - model_interfaces.py  : IModelService, IGPUService

All existing imports from this module continue to work unchanged:
    from app.interfaces.services import IIntentService   # still valid
    from app.interfaces.agent_interfaces import IIntentService  # new path
"""

# Re-export everything from split files for full backward compatibility
from .agent_interfaces import (  # noqa: F401
    IIntentService,
    ICapabilityService,
    IContextBuilder,
    IModelSelector,
    IPlanner,
    IExecutionEngine,
)
from .memory_interfaces import IMemoryService  # noqa: F401
from .model_interfaces import IModelService, IGPUService  # noqa: F401

__all__ = [
    "IIntentService",
    "ICapabilityService",
    "IContextBuilder",
    "IModelSelector",
    "IPlanner",
    "IExecutionEngine",
    "IMemoryService",
    "IModelService",
    "IGPUService",
]
