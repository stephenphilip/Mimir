"""Interfaces for Creator Engine and generation providers."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import List, Optional

from ..creator.types import ArtifactRecord, GenerationRequest, GenerationResult, ValidationResult


class ICreatorProvider(ABC):
    """Provider adapter for a family of artifact types (document, image, etc.)."""

    @property
    @abstractmethod
    def name(self) -> str:
        pass

    @abstractmethod
    def supports(self, artifact_type: str) -> bool:
        pass

    @abstractmethod
    def generate(self, request: GenerationRequest) -> GenerationResult:
        pass


class IArtifactManager(ABC):
    @abstractmethod
    def register_file(
        self,
        file_path: str,
        *,
        message_id: Optional[int] = None,
        workspace_id: Optional[str] = None,
        provider: str = "python_execution",
        artifact_type: Optional[str] = None,
        status: str = "ready",
        thumbnail_path: Optional[str] = None,
        validation: Optional[ValidationResult] = None,
    ) -> ArtifactRecord:
        pass

    @abstractmethod
    def get(self, artifact_id: str) -> Optional[ArtifactRecord]:
        pass

    @abstractmethod
    def list_artifacts(
        self,
        *,
        workspace_id: Optional[str] = None,
        artifact_type: Optional[str] = None,
        limit: int = 100,
    ) -> List[ArtifactRecord]:
        pass

    @abstractmethod
    def count_by_workspace(self, workspace_id: str) -> int:
        pass


class ICreatorEngine(ABC):
    @abstractmethod
    def generate(self, request: GenerationRequest) -> GenerationResult:
        pass

    @abstractmethod
    def supported_types(self) -> List[str]:
        pass
