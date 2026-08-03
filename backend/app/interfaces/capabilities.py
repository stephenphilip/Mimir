"""Capability contracts — every provider exposes a uniform execution surface."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional

from ..creator.types import ArtifactRecord, GenerationRequest, GenerationResult, ValidationResult


class ICapabilityProvider(ABC):
    """
    Full capability contract for artifact-producing providers.

    Creator/Execution engines dispatch through these methods — never
    provider-specific logic in the engine itself.
    """

    @property
    @abstractmethod
    def name(self) -> str:
        pass

    @abstractmethod
    def supports(self, artifact_type: str) -> bool:
        pass

    @abstractmethod
    def execute(self, request: GenerationRequest) -> GenerationResult:
        """Generate artifact bytes on disk. Does not register."""
        pass

    @abstractmethod
    def validate(self, file_path: str, artifact_type: str) -> ValidationResult:
        """Validate artifact exists and is usable."""
        pass

    @abstractmethod
    def metadata(self, artifact: ArtifactRecord) -> Dict[str, Any]:
        """Return provider-specific metadata for dashboards/history."""
        pass

    def preview(self, artifact: ArtifactRecord) -> Optional[str]:
        """Optional preview URL or inline hint."""
        return artifact.path

    def download(self, artifact: ArtifactRecord) -> str:
        """Return downloadable path/URL."""
        return artifact.path

    def history(self) -> List[Dict[str, Any]]:
        """Optional execution history entries."""
        return []

    # Backward-compatible alias used by existing ICreatorProvider callers
    def generate(self, request: GenerationRequest) -> GenerationResult:
        return self.execute(request)
