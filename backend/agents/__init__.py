"""
Agents package — Agent Runtime.

Phase 1: Package scaffold + IAgent base interface.
         No concrete agents yet.

Phase 4: Each agent (Intent, Planner, Memory, Reasoning, Tool, Validator,
         Summarizer, Response Composer) will be implemented here, replacing
         the corresponding step in the current linear Orchestrator.

Architecture:
    agents/
        base.py           ← IAgent ABC (this phase)
        intent_agent.py   ← Phase 2: replaces IntentService regex classifier
        planner_agent.py  ← Phase 4: replaces Planner stub
        memory_agent.py   ← Phase 3/4: wraps MemoryManager
        reasoning_agent.py← Phase 4: wraps Ollama inference
        tool_agent.py     ← Phase 5: wraps Tool Framework
        validator_agent.py← Phase 4: validates agent outputs
        summarizer_agent.py← Phase 6: summarises conversations
        composer_agent.py ← Phase 4: assembles final response
"""
from .base import IAgent, AgentResult

__all__ = ["IAgent", "AgentResult"]
