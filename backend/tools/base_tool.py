from abc import ABC, abstractmethod
from typing import Dict, Any

from app.core.context import ExecutionContext

class ITool(ABC):
    """
    Base interface for all tools in the Tool Framework (Phase 5).
    Replaces the legacy IExecutor.
    """

    @classmethod
    @abstractmethod
    def name(cls) -> str:
        """The unique name/identifier of the tool (e.g., 'python_execution')."""
        pass

    @classmethod
    @abstractmethod
    def description(cls) -> str:
        """A brief description of what the tool does, injected into the system prompt."""
        pass

    @classmethod
    @abstractmethod
    def get_schema(cls) -> Dict[str, Any]:
        """
        Returns a JSON schema defining the tool's required and optional parameters.
        Example:
            return {
                "type": "object",
                "properties": {
                    "code": {"type": "string", "description": "The python code to execute"}
                },
                "required": ["code"]
            }
        """
        pass

    @abstractmethod
    def execute(self, params: Dict[str, Any], context: ExecutionContext) -> Dict[str, Any]:
        """
        Execute the tool with the given parameters and context.
        Returns a dictionary with at least 'success' (bool) and output details.
        """
        pass
