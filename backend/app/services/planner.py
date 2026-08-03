from typing import List, Dict, Any, Optional

from pydantic import BaseModel

from ..interfaces.services import IPlanner
from ..core.context import ExecutionContext
from ..intelligence.workflow_planner import WorkflowPlanner
from ..creator.diagnostics import get_execution_diagnostics


class ExecutionPlan(BaseModel):
    """Backward-compatible plan shape stored on ExecutionContext."""

    steps: List[Dict[str, Any]]
    workflow: Optional[str] = None
    intent: Optional[str] = None
    preferred_artifact: Optional[str] = None


class Planner(IPlanner):
    """
    Chat-path planner — delegates to Intelligence Layer WorkflowPlanner.

    Produces multi-step structured plans instead of immediately assuming Python.
    """

    def __init__(self, workflow_planner: Optional[WorkflowPlanner] = None):
        self._workflow = workflow_planner or WorkflowPlanner()
        self._diag = get_execution_diagnostics()

    def create_plan(self, context: ExecutionContext) -> ExecutionPlan:
        intent = context.intent or "general_reasoning"
        prompt = context.prompt or ""
        workflow_plan = self._workflow.plan(prompt, intent, context.capabilities)

        steps = [s.to_dict() for s in workflow_plan.steps]
        plan = ExecutionPlan(
            steps=steps,
            workflow=workflow_plan.workflow,
            intent=workflow_plan.intent,
            preferred_artifact=workflow_plan.preferred_artifact,
        )
        context.execution_plan = plan
        context.execution_metadata["workflow"] = workflow_plan.workflow
        context.execution_metadata["preferred_artifact"] = workflow_plan.preferred_artifact
        context.execution_metadata["workflow_plan"] = workflow_plan.to_dict()

        self._diag.log(
            "execution",
            f"Plan: {workflow_plan.workflow} ({len(steps)} steps)",
            metadata={"intent": intent, "steps": [s["type"] for s in steps]},
        )
        return plan
