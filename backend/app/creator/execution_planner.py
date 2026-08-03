"""Execution Planner — maps requests to provider + capability plans."""

from __future__ import annotations

from typing import List, Optional

from ..interfaces.capabilities import ICapabilityProvider
from ..interfaces.creators import ICreatorProvider
from .execution_types import ExecutionPlan, PromptStudioPlan
from .types import GenerationRequest


class ExecutionPlanner:
    """Builds execution plans from generation requests and Prompt Studio metadata."""

    def plan(
        self,
        request: GenerationRequest,
        providers: List[ICreatorProvider],
        *,
        studio_plan: Optional[PromptStudioPlan] = None,
    ) -> ExecutionPlan:
        artifact_type = request.artifact_type.lower()
        provider_hint = (request.provider_hint or "").lower()

        if studio_plan and studio_plan.provider_recommendation:
            provider_hint = provider_hint or studio_plan.provider_recommendation.lower()

        provider = self._resolve_provider(providers, artifact_type, provider_hint)
        provider_name = provider.name if provider else "unknown"
        capability = studio_plan.capability if studio_plan else self._capability_for_type(artifact_type)

        metadata = dict(request.metadata)
        if studio_plan:
            metadata.update(studio_plan.to_dict())

        return ExecutionPlan(
            artifact_type=artifact_type,
            provider_name=provider_name,
            capability=capability,
            workspace_id=request.workspace_id,
            message_id=request.message_id,
            metadata=metadata,
        )

    def _resolve_provider(
        self,
        providers: List[ICreatorProvider],
        artifact_type: str,
        hint: str,
    ) -> Optional[ICreatorProvider]:
        if hint:
            for p in providers:
                pid = getattr(p, "provider_id", None) or p.name
                if pid == hint or p.name == hint:
                    if p.supports(artifact_type):
                        return p
        for p in providers:
            if p.supports(artifact_type):
                return p
        return None

    def _capability_for_type(self, artifact_type: str) -> str:
        if artifact_type in {"png", "jpg", "jpeg", "webp", "gif", "image"}:
            return "image_generation"
        if artifact_type in {"pdf", "docx", "markdown", "md", "txt", "csv", "xlsx"}:
            return "document_generation"
        return "artifact_generation"
