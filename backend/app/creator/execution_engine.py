"""Artifact Execution Engine — full generate → validate → register lifecycle."""

from __future__ import annotations

from typing import Callable, List, Optional

from ..interfaces.creators import IArtifactManager, ICreatorEngine, ICreatorProvider
from .artifact_validator import ArtifactValidator
from .diagnostics import get_execution_diagnostics
from .execution_planner import ExecutionPlanner
from .execution_types import ExecutionOutcome, ExecutionPlan, ExecutionStatus, PromptStudioPlan
from .types import GenerationRequest, GenerationResult, ValidationResult


StatusCallback = Callable[[ExecutionStatus, Optional[str]], None]


class ArtifactExecutionEngine(ICreatorEngine):
    """
    Reliable execution platform for artifact generation.

    Lifecycle: Queued → Planning → Generating → Validating → Registering → Completed/Failed
    """

    MAX_RETRIES = 1

    def __init__(
        self,
        artifact_manager: IArtifactManager,
        validator: ArtifactValidator,
        document_provider: ICreatorProvider,
        image_provider: Optional[ICreatorProvider] = None,
        extra_providers: Optional[List[ICreatorProvider]] = None,
        planner: Optional[ExecutionPlanner] = None,
    ):
        self._artifact_manager = artifact_manager
        self._validator = validator
        self._planner = planner or ExecutionPlanner()
        self._diag = get_execution_diagnostics()
        self._providers: List[ICreatorProvider] = [document_provider]
        if image_provider:
            self._providers.append(image_provider)
        if extra_providers:
            self._providers.extend(extra_providers)

    def supported_types(self) -> List[str]:
        types: List[str] = []
        for provider in self._providers:
            if hasattr(provider, "supported_types"):
                types.extend(provider.supported_types())  # type: ignore[attr-defined]
            elif hasattr(provider, "SUPPORTED"):
                types.extend(provider.SUPPORTED)  # type: ignore[attr-defined]
            else:
                types.append("image")
        return sorted(set(types))

    def _emit(self, cb: Optional[StatusCallback], status: ExecutionStatus, detail: Optional[str] = None) -> None:
        self._diag.log("execution", f"Status: {status.value}" + (f" — {detail}" if detail else ""))
        if cb:
            cb(status, detail)

    def execute(
        self,
        request: GenerationRequest,
        *,
        studio_plan: Optional[PromptStudioPlan] = None,
        on_status: Optional[StatusCallback] = None,
    ) -> ExecutionOutcome:
        self._emit(on_status, ExecutionStatus.QUEUED)
        self._emit(on_status, ExecutionStatus.PLANNING)

        plan = self._planner.plan(request, self._providers, studio_plan=studio_plan)
        provider = self._resolve_provider(request, plan)
        if not provider:
            err = f"No provider for artifact type: {request.artifact_type}"
            self._diag.log("execution", err, level="error")
            return ExecutionOutcome(success=False, status=ExecutionStatus.FAILED, error=err)

        self._emit(on_status, ExecutionStatus.GENERATING, provider.name)
        self._diag.log("provider", f"Dispatching to {provider.name}", metadata={"type": request.artifact_type})

        last_error: Optional[str] = None
        for attempt in range(self.MAX_RETRIES + 1):
            result = self._run_provider(provider, request)
            if not result.success:
                last_error = result.error or "Provider generation failed"
                self._diag.log("provider", last_error, level="error", metadata={"attempt": attempt})
                continue

            file_path = result.output_path or request.metadata.get("output_path")
            if not file_path:
                last_error = "Provider succeeded but no output path was returned"
                continue

            self._emit(on_status, ExecutionStatus.VALIDATING)
            validation = self._validate(provider, file_path, request.artifact_type)
            if not validation.valid:
                last_error = "; ".join(validation.errors)
                self._diag.log("validation", last_error, level="error")
                continue

            self._emit(on_status, ExecutionStatus.REGISTERING)
            try:
                artifact = self._artifact_manager.register_file(
                    file_path,
                    message_id=request.message_id,
                    workspace_id=request.workspace_id,
                    provider=provider.name,
                    artifact_type=request.artifact_type,
                    validation=validation,
                )
            except Exception as exc:
                last_error = str(exc)
                self._diag.log("artifact", last_error, level="error")
                continue

            self._emit(on_status, ExecutionStatus.COMPLETED)
            self._diag.log("artifact", f"Registered {artifact.filename}", metadata={"id": artifact.artifact_id})
            return ExecutionOutcome(
                success=True,
                status=ExecutionStatus.COMPLETED,
                artifact=artifact,
                stdout=result.stdout,
                stderr=result.stderr,
                output_path=file_path,
                provider=provider.name,
            )

        return ExecutionOutcome(
            success=False,
            status=ExecutionStatus.FAILED,
            error=last_error or "Execution failed",
            stderr=last_error or "",
            provider=plan.provider_name,
        )

    def generate(self, request: GenerationRequest) -> GenerationResult:
        return self.execute(request).to_generation_result()

    def register_existing_file(
        self,
        file_path: str,
        *,
        message_id: Optional[int] = None,
        workspace_id: Optional[str] = None,
        provider: str = "python_execution",
        artifact_type: Optional[str] = None,
        on_status: Optional[StatusCallback] = None,
    ) -> GenerationResult:
        """Validate and register a file already on disk (e.g. from PythonExecutor)."""
        from pathlib import Path

        inferred = artifact_type or Path(file_path).suffix.lstrip(".")
        self._emit(on_status, ExecutionStatus.VALIDATING, file_path)
        validation = self._validator.validate(file_path, inferred)
        if not validation.valid:
            err = "; ".join(validation.errors)
            self._diag.log("validation", err, level="error")
            return GenerationResult(success=False, error=err, stderr=err)

        self._emit(on_status, ExecutionStatus.REGISTERING)
        try:
            artifact = self._artifact_manager.register_file(
                file_path,
                message_id=message_id,
                workspace_id=workspace_id,
                provider=provider,
                artifact_type=inferred,
                validation=validation,
            )
            self._emit(on_status, ExecutionStatus.COMPLETED)
            return GenerationResult(success=True, artifact=artifact)
        except Exception as exc:
            self._diag.log("artifact", str(exc), level="error")
            return GenerationResult(success=False, error=str(exc), stderr=str(exc))

    def _resolve_provider(
        self,
        request: GenerationRequest,
        plan: ExecutionPlan,
    ) -> Optional[ICreatorProvider]:
        hint = (request.provider_hint or plan.provider_name or "").lower()
        if hint and hint != "unknown":
            for p in self._providers:
                pid = getattr(p, "provider_id", None) or p.name
                if pid == hint or p.name == hint:
                    if p.supports(request.artifact_type):
                        return p
        for p in self._providers:
            if p.supports(request.artifact_type):
                return p
        return None

    def _run_provider(self, provider: ICreatorProvider, request: GenerationRequest) -> GenerationResult:
        if hasattr(provider, "execute"):
            return provider.execute(request)  # type: ignore[attr-defined]
        return provider.generate(request)

    def _validate(
        self,
        provider: ICreatorProvider,
        file_path: str,
        artifact_type: str,
    ) -> ValidationResult:
        if hasattr(provider, "validate"):
            return provider.validate(file_path, artifact_type)  # type: ignore[attr-defined]
        return self._validator.validate(file_path, artifact_type)
