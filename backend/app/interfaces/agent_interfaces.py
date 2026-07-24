"""
Agent-oriented service interfaces.

Extracted from interfaces/services.py for clarity.
All imports from interfaces/services.py continue to work (it re-exports these).

These ABCs define the contract for:
  - Intent classification (Phase 1: regex, Phase 2: AI agent)
  - Capability resolution (Phase 1: static map, Phase 4: dynamic)
  - Context building (Phase 1: string assembly, Phase 3: PromptBuilder)
  - Model selection (Phase 1: MCDM scoring, Phase 7: role-aware)
  - Planning (Phase 1: stub, Phase 4: multi-step agent)
  - Execution (Phase 1: regex+subprocess, Phase 5: Tool Framework)
"""

from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional

from ..core.context import ExecutionContext


class IIntentService(ABC):
    @abstractmethod
    def classify(self, prompt: str) -> Dict[str, Any]:
        """Classify user prompt to detect intention and confidence."""


class ICapabilityService(ABC):
    @abstractmethod
    def resolve(self, intent: str) -> List[str]:
        """Resolve capability requirements for a given intent."""

    @abstractmethod
    def get_execution_requirements(self, capabilities: List[str]) -> Dict[str, Any]:
        """Determine system and package requirements for a set of capabilities."""


class IContextBuilder(ABC):
    @abstractmethod
    def build_context(self, context: ExecutionContext) -> None:
        """Enrich context with memories, history and format final prompts."""


class IModelSelector(ABC):
    @abstractmethod
    def select_best_model(
        self,
        context: ExecutionContext,
        available_models: List[str],
        capabilities: List[str],
        hardware_info: Dict[str, Any],
    ) -> str:
        """Evaluate criteria to select the most appropriate model."""


class IPlanner(ABC):
    @abstractmethod
    def create_plan(self, context: ExecutionContext) -> Any:
        """Construct a minimal execution plan for the request."""


class IExecutionEngine(ABC):
    @abstractmethod
    def register_executor(self, executor: Any) -> None:
        """Register capability handlers/executors."""

    @abstractmethod
    def execute(self, context: ExecutionContext) -> Dict[str, Any]:
        """Coordinate plan or script execution using executors."""
