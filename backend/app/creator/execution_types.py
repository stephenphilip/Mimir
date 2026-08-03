"""Execution lifecycle types for the Execution Engine."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional

from .types import ArtifactRecord, GenerationRequest, GenerationResult, ValidationResult

__all__ = [
    "ExecutionStatus",
    "ExecutionPlan",
    "ExecutionOutcome",
    "PromptStudioPlan",
    "ValidationResult",
]


class ExecutionStatus(str, Enum):
    QUEUED = "queued"
    PLANNING = "planning"
    GENERATING = "generating"
    VALIDATING = "validating"
    REGISTERING = "registering"
    COMPLETED = "completed"
    FAILED = "failed"


@dataclass
class ExecutionPlan:
    artifact_type: str
    provider_name: str
    capability: str
    workspace_id: Optional[str] = None
    message_id: Optional[int] = None
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class ExecutionOutcome:
    """Result of a full execution lifecycle (generate → validate → register)."""

    success: bool
    status: ExecutionStatus
    artifact: Optional[ArtifactRecord] = None
    error: Optional[str] = None
    stdout: str = ""
    stderr: str = ""
    output_path: Optional[str] = None
    provider: Optional[str] = None
    diagnostics: Dict[str, Any] = field(default_factory=dict)

    def to_generation_result(self) -> GenerationResult:
        """Backward-compatible view for existing API callers."""
        return GenerationResult(
            success=self.success,
            artifact=self.artifact,
            error=self.error,
            stdout=self.stdout,
            stderr=self.stderr,
            output_path=self.output_path,
        )


@dataclass
class PromptStudioPlan:
    """Prompt Studio 3 — metadata consumed by Execution Engine."""

    original: str
    enhanced_prompt: str
    execution_intent: str
    expected_output: str
    expected_artifact: str
    provider_recommendation: str
    capability: str
    used_model: Optional[str] = None
    # Image prompt optimization
    negative_prompt: Optional[str] = None
    suggested_style: Optional[str] = None
    suggested_resolution: Optional[str] = None
    suggested_aspect_ratio: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "original": self.original,
            "enhanced_prompt": self.enhanced_prompt,
            "execution_intent": self.execution_intent,
            "expected_output": self.expected_output,
            "expected_artifact": self.expected_artifact,
            "provider_recommendation": self.provider_recommendation,
            "capability": self.capability,
            "used_model": self.used_model,
            "negative_prompt": self.negative_prompt,
            "suggested_style": self.suggested_style,
            "suggested_resolution": self.suggested_resolution,
            "suggested_aspect_ratio": self.suggested_aspect_ratio,
        }
