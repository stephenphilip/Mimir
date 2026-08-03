"""Workflow Execution Planner — multi-step structured plans (Intelligence Layer).

Converts user requests into execution plans. The LLM generates knowledge;
the platform executes the plan steps.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from .capability_registry import CapabilityRegistry, get_capability_registry
from .prompt_analyzer import PromptAnalysis, PromptAnalyzer


@dataclass
class PlanStep:
    index: int
    type: str
    description: str
    capability: Optional[str] = None
    provider: Optional[str] = None
    artifact_type: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "step_index": self.index,
            "type": self.type,
            "description": self.description,
            "capability": self.capability,
            "provider": self.provider,
            "artifact_type": self.artifact_type,
            "metadata": self.metadata,
        }


@dataclass
class WorkflowPlan:
    intent: str
    workflow: str
    steps: List[PlanStep]
    capabilities: List[str]
    preferred_artifact: Optional[str] = None
    analysis: Optional[Dict[str, Any]] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "intent": self.intent,
            "workflow": self.workflow,
            "steps": [s.to_dict() for s in self.steps],
            "capabilities": self.capabilities,
            "preferred_artifact": self.preferred_artifact,
            "analysis": self.analysis,
        }


class WorkflowPlanner:
    """
    Builds multi-step execution plans from intent + capability registry.

    Example — "Create a workout PDF":
      1. Build structured document (LLM content)
      2. Render PDF
      3. Validate
      4. Register artifact
    """

    def __init__(
        self,
        registry: Optional[CapabilityRegistry] = None,
        analyzer: Optional[PromptAnalyzer] = None,
    ):
        self._registry = registry or get_capability_registry()
        self._analyzer = analyzer or PromptAnalyzer()

    def plan(
        self,
        prompt: str,
        intent: str,
        capabilities: Optional[List[str]] = None,
    ) -> WorkflowPlan:
        analysis = self._analyzer.analyze(prompt)
        caps = capabilities or self._registry.resolve_for_intent(intent)
        workflow = self._registry.workflow_for_intent(intent)
        artifact = self._registry.preferred_artifact_for_intent(intent) or analysis.suggested_artifact

        if workflow == "structured_document":
            steps = self._document_steps(artifact or "pdf")
        elif workflow == "image":
            steps = self._image_steps()
        elif workflow == "python":
            steps = self._python_steps(artifact)
        elif workflow == "vision":
            steps = self._vision_steps()
        else:
            steps = [
                PlanStep(1, "text_response", "Generate text response from the model.", capability="chat"),
            ]

        return WorkflowPlan(
            intent=intent,
            workflow=workflow,
            steps=steps,
            capabilities=caps,
            preferred_artifact=artifact,
            analysis=analysis.to_dict(),
        )

    def _document_steps(self, artifact_type: str) -> List[PlanStep]:
        return [
            PlanStep(1, "build_structured_document", "LLM generates structured document content.", capability="document", artifact_type=artifact_type),
            PlanStep(2, "render_document", f"Render {artifact_type} from structured model.", capability=artifact_type if artifact_type in {"pdf", "docx", "markdown", "html"} else "document", provider="document", artifact_type=artifact_type),
            PlanStep(3, "validate_artifact", "Validate artifact exists and is readable.", capability="document"),
            PlanStep(4, "register_artifact", "Register artifact in Artifact Manager / workspace.", capability="document"),
        ]

    def _image_steps(self) -> List[PlanStep]:
        return [
            PlanStep(1, "optimize_image_prompt", "Prompt Studio enhances image prompt + negative prompt.", capability="image"),
            PlanStep(2, "generate_image", "Dispatch to active image provider (ComfyUI / OpenAI / Gemini).", capability="image", provider="image_registry", artifact_type="png"),
            PlanStep(3, "validate_artifact", "Decode image and generate thumbnail.", capability="image"),
            PlanStep(4, "register_artifact", "Register image artifact.", capability="image"),
        ]

    def _python_steps(self, artifact: Optional[str]) -> List[PlanStep]:
        return [
            PlanStep(1, "generate_python", "LLM generates executable Python for the task.", capability="python_execution"),
            PlanStep(2, "execute_python", "PythonExecutor runs code and captures outputs.", capability="python_execution", provider="python"),
            PlanStep(3, "validate_artifact", "Validate any produced files.", capability="python_execution", artifact_type=artifact),
            PlanStep(4, "register_artifact", "Register validated artifacts.", capability="python_execution"),
        ]

    def _vision_steps(self) -> List[PlanStep]:
        return [
            PlanStep(1, "vision_analyze", "OCR, caption, objects, layout, metadata.", capability="vision"),
            PlanStep(2, "inject_context", "Inject vision context into Context Builder.", capability="vision"),
            PlanStep(3, "text_response", "LLM answers using vision context.", capability="chat"),
        ]
