"""Factory for Creator / Execution Engine stack (lazy, per-request)."""

from __future__ import annotations

from typing import Tuple

from config.paths import get_paths

from ..creator import ArtifactManager, CreatorEngine
from ..creator.artifact_validator import ArtifactValidator
from ..creator.execution_engine import ArtifactExecutionEngine
from ..interfaces.creators import IArtifactManager, ICreatorEngine
from ..interfaces.repositories import IArtifactRepository
from ..providers.documents.document_provider import DocumentProvider
from ..providers.images.registry import ImageProviderRegistry


def build_creator_engine(artifact_repo: IArtifactRepository) -> Tuple[ICreatorEngine, IArtifactManager]:
    paths = get_paths()
    validator = ArtifactValidator(paths.artifacts_dir)
    artifact_manager = ArtifactManager(artifact_repo, validator=validator)
    document_provider = DocumentProvider(validator=validator)
    image_registry = ImageProviderRegistry(validator=validator)
    inner = ArtifactExecutionEngine(
        artifact_manager=artifact_manager,
        validator=validator,
        document_provider=document_provider,
        image_provider=image_registry.as_creator_provider(),
    )
    engine = CreatorEngine(inner)
    return engine, artifact_manager
