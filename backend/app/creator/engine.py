"""Creator Engine — backward-compatible facade over ArtifactExecutionEngine."""

from __future__ import annotations

from typing import List, Optional

from ..interfaces.creators import IArtifactManager, ICreatorEngine, ICreatorProvider
from .execution_engine import ArtifactExecutionEngine
from .types import GenerationRequest, GenerationResult


class CreatorEngine(ICreatorEngine):
    """
    Backward-compatible name for ArtifactExecutionEngine.

    Construct via build_creator_engine() — do not instantiate directly.
    """

    def __init__(self, inner: ArtifactExecutionEngine):
        self._inner = inner

    def supported_types(self) -> List[str]:
        return self._inner.supported_types()

    def generate(self, request: GenerationRequest) -> GenerationResult:
        return self._inner.generate(request)

    def register_existing_file(
        self,
        file_path: str,
        *,
        message_id: Optional[int] = None,
        workspace_id: Optional[str] = None,
        provider: str = "python_execution",
        artifact_type: Optional[str] = None,
    ) -> GenerationResult:
        return self._inner.register_existing_file(
            file_path,
            message_id=message_id,
            workspace_id=workspace_id,
            provider=provider,
            artifact_type=artifact_type,
        )
