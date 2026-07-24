"""
Model service interfaces.

Extracted from interfaces/services.py for clarity.
All imports from interfaces/services.py continue to work (it re-exports these).

IModelService — contract for Ollama sync, download management, VRAM lifecycle.
IGPUService   — contract for hardware detection (nvidia-smi/wmic/psutil).

Phase 7: IModelService will be extended to support per-role model binding
         (reasoning model, planning model, intent model, embedding model, etc.)
"""

from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional


class IModelService(ABC):
    @abstractmethod
    def detect_hardware(self) -> Dict[str, Any]:
        """Detect GPU availability, VRAM, and RAM specifications."""

    @abstractmethod
    def get_installed_models_from_ollama(self) -> List[str]:
        """Fetch model names currently present in the Ollama service."""

    @abstractmethod
    def sync_models_to_db(self) -> None:
        """Synchronize active database records with local Ollama service."""

    @abstractmethod
    def unload_other_models(self, active_model: Optional[str] = None) -> None:
        """Unload inactive models from RAM/VRAM to optimize resources."""

    @abstractmethod
    def preload_first_run_models(self) -> None:
        """Ensure initial recommended models are installed on application start."""

    @abstractmethod
    def trigger_background_download(self, model_name: str) -> None:
        """Initiate non-blocking download of a model."""


class IGPUService(ABC):
    @abstractmethod
    def detect_hardware(self) -> Dict[str, Any]:
        """Detect GPU availability, VRAM, and System RAM."""
