import json
from typing import Generator, Union

from agents.base import IAgent, AgentResult
from app.core.context import ExecutionContext
from app.interfaces.agent_interfaces import IPlanner

class PlannerAgent(IAgent):
    """
    Agent responsible for breaking down the request into an execution plan.
    Phase 4: Wraps the existing IPlanner logic.
    """
    def __init__(self, planner: IPlanner):
        self.planner = planner

    @property
    def agent_id(self) -> str:
        return "planner_agent"

    def run(self, context: ExecutionContext) -> Generator[Union[str, AgentResult], None, None]:
        # Legacy planner mutates context directly
        self.planner.create_plan(context)
        
        yield AgentResult(
            agent_id=self.agent_id,
            output=context.execution_plan,
            status_message="Generated execution plan",
            emit_event=False # Silent step for now, like orchestrator did
        )
