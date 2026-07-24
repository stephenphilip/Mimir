import json
from typing import Generator, Union

from agents.base import IAgent, AgentResult
from app.core.context import ExecutionContext
from app.interfaces.agent_interfaces import IContextBuilder

class MemoryAgent(IAgent):
    """
    Agent responsible for collecting history and facts, and building the prompt.
    Phase 4: Wraps the IContextBuilder.
    """
    def __init__(self, context_builder: IContextBuilder):
        self.context_builder = context_builder

    @property
    def agent_id(self) -> str:
        return "memory_agent"

    def run(self, context: ExecutionContext) -> Generator[Union[str, AgentResult], None, None]:
        # Lazily initializes memory and builds context
        self.context_builder.build_context(context)
        
        yield AgentResult(
            agent_id=self.agent_id,
            output=None,
            status_message="Constructed context from memory layers",
            emit_event=False
        )
