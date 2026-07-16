from abc import ABC, abstractmethod
from typing import Generator, List, Dict, Any, Optional

class IProvider(ABC):
    @abstractmethod
    def generate_stream(self, model: str, prompt: str, system_prompt: Optional[str] = None) -> Generator[str, None, None]:
        """Stream generation responses chunk by chunk."""
        pass

    @abstractmethod
    def generate(self, model: str, prompt: str, system_prompt: Optional[str] = None) -> str:
        """Run synchronous text generation."""
        pass

    @abstractmethod
    def get_embeddings(self, text: str, model: Optional[str] = None) -> List[float]:
        """Generate high-dimensional vector embeddings for input text."""
        pass

    @abstractmethod
    def generate_vision(
        self,
        model: str,
        prompt: str,
        image_paths: List[str],
        system_prompt: Optional[str] = None
    ) -> Generator[str, None, None]:
        """Stream generation response using image data as contextual input."""
        pass

    @abstractmethod
    def generate_json(
        self,
        model: str,
        prompt: str,
        schema: Dict[str, Any],
        system_prompt: Optional[str] = None
    ) -> Dict[str, Any]:
        """Produce structured response output matching a specific schema format."""
        pass

    @abstractmethod
    def call_tools(
        self,
        model: str,
        messages: List[Dict[str, Any]],
        tools: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """Perform function/tool execution mapping requests."""
        pass

    @abstractmethod
    def get_metadata(self) -> Dict[str, Any]:
        """Fetch general metadata parameters linked to the provider platform."""
        pass
