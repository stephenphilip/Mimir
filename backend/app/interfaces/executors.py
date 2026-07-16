from abc import ABC, abstractmethod
from typing import Dict, Any
from ..core.context import ExecutionContext

class IExecutor(ABC):
    @abstractmethod
    def can_execute(self, capability: str) -> bool:
        """Evaluate if this executor supports running actions for the specified capability."""
        pass

    @abstractmethod
    def execute(self, code: str, context: ExecutionContext) -> Dict[str, Any]:
        """Perform action/execution logic and return details of outcomes."""
        pass
