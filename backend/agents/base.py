"""
IAgent — Base interface for all agents in the Agent Runtime.

Design principles:
- Every agent receives a shared ExecutionContext, performs its specialised role,
  enriches the context with its outputs, and returns it.
- Agents are stateless per invocation — they must not store request-specific
  state between calls. Configuration state (models, repos) is injected at
  construction time.
- The `can_run()` pre-condition check allows the Agent Runtime dispatcher
  to skip agents whose preconditions are not met (e.g., a ToolAgent that
  requires python_execution capability skips for general_reasoning requests).
- AgentResult separates what the agent produced (output) from whether it
  should be visible to the user (emit_event) and what SSE events to emit.

Phase 1: Interface defined. No concrete implementations yet.
Phase 4: Orchestrator.process_prompt() is replaced by an AgentRuntime
         that chains these agents in order.

Example future agent (Phase 4):
    class IntentAgent(IAgent):
        @property
        def agent_id(self) -> str:
            return "intent_agent"

        def run(self, context: ExecutionContext) -> AgentResult:
            result = self._model.classify(context.prompt)
            context.intent = result.intent
            context.intent_confidence = result.confidence
            return AgentResult(
                agent_id=self.agent_id,
                output=result,
                status_message=f"Intent: {result.intent} ({result.confidence:.0%})",
            )
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Dict, Optional

from app.core.context import ExecutionContext


@dataclass
class AgentResult:
    """
    Structured output returned by every agent's run() call.

    Attributes:
        agent_id:       The ID of the agent that produced this result.
        output:         The agent's primary output (intent, plan, memory, etc.).
        status_message: Human-readable status string — emitted as an SSE status
                        event if emit_event is True. May be empty.
        emit_event:     Whether the Agent Runtime should emit a status SSE event
                        for this result. Set False for internal/silent steps.
        metadata:       Optional extra data for debugging or inter-agent communication.
        error:          Non-None if the agent encountered a recoverable error.
    """

    agent_id: str
    output: Any = None
    status_message: str = ""
    emit_event: bool = True
    metadata: Dict[str, Any] = field(default_factory=dict)
    error: Optional[str] = None

    @property
    def success(self) -> bool:
        """True if the agent completed without error."""
        return self.error is None


class IAgent(ABC):
    """
    Abstract base class for all agents in the Agent Runtime.

    Agents are the atomic units of intelligence in the system.
    Each agent is responsible for exactly one concern (intent, planning,
    memory, reasoning, tool use, validation, summarization, composition).

    Concrete agents must implement:
        agent_id  — unique string identifier
        run()     — synchronous execution that enriches context

    Concrete agents may override:
        can_run() — pre-condition check (default: always True)
        describe()— metadata about this agent's capabilities
    """

    @property
    @abstractmethod
    def agent_id(self) -> str:
        """
        Unique, stable identifier for this agent.
        Used by the Event Bus and Agent Runtime for routing and logging.
        Convention: lowercase_snake (e.g. "intent_agent", "tool_agent").
        """

    from typing import Generator, Union
    @abstractmethod
    def run(self, context: ExecutionContext) -> Generator[Union[str, AgentResult], None, None]:
        """
        Execute this agent's role on the given context.

        The agent should:
          1. Read relevant fields from context.
          2. Perform its specialised processing.
          3. Write outputs back to context (mutate in place).
          4. Return an AgentResult describing what was produced.

        The agent MUST NOT raise exceptions for recoverable failures —
        return AgentResult(error="...") instead.
        Unrecoverable failures (e.g. DB connection lost) may raise.

        Args:
            context: Shared execution context for the current request.

        Returns:
            AgentResult with the agent's output and status.
        """

    def can_run(self, context: ExecutionContext) -> bool:
        """
        Pre-condition check. Return False to skip this agent.

        The Agent Runtime calls this before run(). If False, run() is
        never called and the agent is silently skipped.

        Override to add capability or context-based conditions.
        Default: always runnable.

        Examples:
            # Only run if python_execution is a required capability
            return "python_execution" in context.capabilities

            # Only run if a model has been selected
            return context.selected_model is not None
        """
        return True

    def describe(self) -> Dict[str, Any]:
        """
        Return metadata about this agent. Used for introspection and logging.
        Override to provide richer information.
        """
        return {
            "agent_id": self.agent_id,
            "class": type(self).__name__,
            "module": type(self).__module__,
        }

    def __repr__(self) -> str:
        return f"{type(self).__name__}(agent_id={self.agent_id!r})"
