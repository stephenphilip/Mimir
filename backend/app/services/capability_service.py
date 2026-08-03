from typing import List, Dict, Any

from ..interfaces.services import ICapabilityService
from ..intelligence.capability_registry import get_capability_registry


class CapabilityService(ICapabilityService):
    """
    Capability routing is registry-driven.

    Architectural decision: no hardcoded capability maps — all intent→capability
    resolution goes through CapabilityRegistry (packs can extend it).
    """

    def __init__(self, registry=None):
        self._registry = registry or get_capability_registry()

    def resolve(self, intent: str) -> List[str]:
        return self._registry.resolve_for_intent(intent)

    def get_execution_requirements(self, capabilities: List[str]) -> Dict[str, Any]:
        return self._registry.get_execution_requirements(capabilities)

    def workflow_for_intent(self, intent: str) -> str:
        return self._registry.workflow_for_intent(intent)
