from abc import ABC, abstractmethod
from typing import List, Dict, Any, Optional
from ..core.context import ExecutionContext

class IIntentService(ABC):
    @abstractmethod
    def classify(self, prompt: str) -> Dict[str, Any]:
        """Classify user prompt to detect intention and confidence."""
        pass

class ICapabilityService(ABC):
    @abstractmethod
    def resolve(self, intent: str) -> List[str]:
        """Resolve capability requirements for a given intent."""
        pass

    @abstractmethod
    def get_execution_requirements(self, capabilities: List[str]) -> Dict[str, Any]:
        """Determine system and package requirements for a set of capabilities."""
        pass

class IMemoryService(ABC):
    @abstractmethod
    def get_user_profile(self, user_id: int = 1) -> Dict[str, Any]:
        """Fetch user profile information."""
        pass

    @abstractmethod
    def update_user_profile(self, key: str, value: str, user_id: int = 1) -> None:
        """Update or insert a profile key-value."""
        pass

    @abstractmethod
    def get_settings(self) -> Dict[str, str]:
        """Fetch system settings."""
        pass

    @abstractmethod
    def set_setting(self, key: str, value: str) -> None:
        """Update a system setting."""
        pass

    @abstractmethod
    def get_recent_context(self, conversation_id: str, limit: int = 10) -> List[Dict[str, Any]]:
        """Fetch conversation messages formatted as prompt context."""
        pass

class IContextBuilder(ABC):
    @abstractmethod
    def build_context(self, context: ExecutionContext) -> None:
        """Enrich context with memories, history and format final prompts."""
        pass

class IModelSelector(ABC):
    @abstractmethod
    def select_best_model(
        self,
        context: ExecutionContext,
        available_models: List[str],
        capabilities: List[str],
        hardware_info: Dict[str, Any]
    ) -> str:
        """Evaluate criteria to select the most appropriate model."""
        pass

class IPlanner(ABC):
    @abstractmethod
    def create_plan(self, context: ExecutionContext) -> Any:
        """Construct a minimal execution plan for the request."""
        pass

class IExecutionEngine(ABC):
    @abstractmethod
    def register_executor(self, executor: Any) -> None:
        """Register capability handlers/executors."""
        pass

    @abstractmethod
    def execute(self, context: ExecutionContext) -> Dict[str, Any]:
        """Coordinate plan or script execution using executors."""
        pass

class IModelService(ABC):
    @abstractmethod
    def detect_hardware(self) -> Dict[str, Any]:
        """Detect GPU availability, VRAM, and RAM specifications."""
        pass

    @abstractmethod
    def get_installed_models_from_ollama(self) -> List[str]:
        """Fetch model names currently present in the Ollama service."""
        pass

    @abstractmethod
    def sync_models_to_db(self) -> None:
        """Synchronize active database records with local Ollama service."""
        pass

    @abstractmethod
    def unload_other_models(self, active_model: Optional[str] = None) -> None:
        """Unload inactive models from RAM/VRAM to optimize resources."""
        pass

    @abstractmethod
    def preload_first_run_models(self) -> None:
        """Ensure initial recommended models are installed on application start."""
        pass

    @abstractmethod
    def trigger_background_download(self, model_name: str) -> None:
        """Initiate non-blocking download of a model."""
        pass

class IGPUService(ABC):
    @abstractmethod
    def detect_hardware(self) -> Dict[str, Any]:
        """Detect GPU availability, VRAM, and System RAM."""
        pass
