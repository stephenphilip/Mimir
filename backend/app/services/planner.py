from typing import List, Dict, Any
from pydantic import BaseModel

from ..interfaces.services import IPlanner
from ..core.context import ExecutionContext

class ExecutionPlan(BaseModel):
    steps: List[Dict[str, Any]]

class Planner(IPlanner):
    def create_plan(self, context: ExecutionContext) -> ExecutionPlan:
        """Create a minimal one-step plan based on capability requirements."""
        steps = []
        
        # Check requirements
        if "python_execution" in context.capabilities:
            steps.append({
                "step_index": 1,
                "type": "python_execution",
                "description": "Extract and execute Python script to fulfill the spreadsheet or visualization request."
            })
        else:
            steps.append({
                "step_index": 1,
                "type": "text_response",
                "description": "Generate text response directly from the model."
            })
            
        plan = ExecutionPlan(steps=steps)
        context.execution_plan = plan
        return plan
