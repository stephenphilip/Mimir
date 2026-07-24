"""
PipelineFactory — Request-scoped inference pipeline builder.

Phase 1: Extracted from main.py chat() endpoint. Behavior is 100% identical
         to the inline construction that was previously in chat(). This is a
         pure refactoring — no logic was added or removed.

Phase 4: build_pipeline() will be replaced by build_agent_runtime() which
         constructs an AgentRuntime dispatcher instead of a monolithic Orchestrator.

Why extracted:
  - The inline wiring block in chat() grew to 25+ lines and would have
    continued growing with each new agent or service.
  - A factory function is easier to test in isolation.
  - It provides a single, clearly named place for the Phase 4 cutover.

The factory is intentionally thin — it constructs, wires, and returns.
No business logic lives here.
"""

from __future__ import annotations

from sqlalchemy.orm import Session

from config.paths import Paths
from runtime.runtime_coordinator import RuntimeCoordinator

from .repositories.sqlite_repositories import (
    SQLiteConversationRepository,
    SQLiteMemoryRepository,
    SQLiteArtifactRepository,
    SQLiteSettingRepository,
    SQLiteModelRepository,
    SQLiteModelCatalogRepository,
)
from agents.intent_agent import IntentAgent
from .services.capability_service import CapabilityService
from .services.context_builder import ContextBuilder
from .services.model_selector import ModelSelector
from .services.planner import Planner
from .services.execution_engine import ExecutionEngine
from .providers.ollama_provider import OllamaProvider
from .services.model_service import ModelService
from .core.orchestrator import Orchestrator
from config.settings import get_settings

# Import WorkingMemory for attaching to context
from memory.working import WorkingMemory


def bind_model_service(db: Session, runtime: RuntimeCoordinator) -> None:
    """
    Create a request-scoped ModelService and bind it to the RuntimeCoordinator.

    This must be called before any inference-related operation within a request.
    The binding is cleared (set to None) at request end.

    Separated from build_pipeline() so startup_event and get_system_status
    can reuse it without constructing a full pipeline.
    """
    settings = get_settings()
    model_repo = SQLiteModelRepository(db)
    setting_repo = SQLiteSettingRepository(db)
    catalog_repo = SQLiteModelCatalogRepository(db)
    ms = ModelService(
        model_repo,
        setting_repo,
        catalog_repo=catalog_repo,
        ollama_url=settings.ollama_url,
    )
    runtime.bind_model_service(ms)


def build_pipeline(
    db: Session,
    paths: Paths,
    runtime: RuntimeCoordinator,
) -> "AgentRuntime":
    """
    Build the complete request-scoped inference pipeline.

    Constructs and wires all services for a single /api/chat request.
    The Orchestrator returned by this function is the entry-point for
    processing a user's prompt.

    All services are request-scoped (created fresh per call) except
    RuntimeCoordinator (process-wide singleton) and OllamaProvider
    (stateless HTTP client).

    Phase 1: Returns an Orchestrator (monolithic 11-step pipeline).
    Phase 4: Will be replaced to return an AgentRuntime instance.

    Args:
        db:      Request-scoped SQLAlchemy session.
        paths:   Repository-relative paths (workspace, artifacts, etc.)
        runtime: Process-wide RuntimeCoordinator singleton.

    Returns:
        Configured Orchestrator ready for process_prompt() calls.
    """
    # ── Repositories ────────────────────────────────────────────────
    conv_repo = SQLiteConversationRepository(db)
    mem_repo = SQLiteMemoryRepository(db)
    art_repo = SQLiteArtifactRepository(db)
    model_repo = SQLiteModelRepository(db)
    setting_repo = SQLiteSettingRepository(db)
    catalog_repo = SQLiteModelCatalogRepository(db)

    # ── Model service + runtime binding ─────────────────────────────
    settings = get_settings()
    ms = ModelService(
        model_repo,
        setting_repo,
        catalog_repo=catalog_repo,
        ollama_url=settings.ollama_url,
    )
    runtime.bind_model_service(ms)

    # ── Core services ────────────────────────────────────────────────
    provider = OllamaProvider()
    intent_service = IntentAgent(provider=provider, model_name="llama3.2:1b")
    capability_service = CapabilityService()
    
    from memory.manager import MemoryManager
    memory_manager = MemoryManager(mem_repo, conv_repo, setting_repo)
    
    context_builder = ContextBuilder(memory_manager)
    model_selector = ModelSelector(catalog_repo)
    planner = Planner()

    # ── Executor factory (lazy — plugin code only loaded when needed) ─
    def executor_factory(capability: str):
        return runtime.get_executor(
            capability,
            art_repo,
            setting_repo,
            str(paths.workspace_dir),
        )

    execution_engine = ExecutionEngine(art_repo, executor_factory=executor_factory)

    from agents.planner_agent import PlannerAgent
    from agents.memory_agent import MemoryAgent
    from agents.reasoning_agent import ReasoningAgent
    from agents.tool_agent import ToolAgent
    from ai_runtime.runtime_dispatcher import AgentRuntime

    # ── AgentRuntime assembly ────────────────────────────────────────
    
    intent_agent = intent_service  # It's already IntentAgent
    planner_agent = PlannerAgent(planner)
    memory_agent = MemoryAgent(context_builder)
    reasoning_agent = ReasoningAgent(model_selector, provider, runtime, conv_repo, model_repo)
    from tools.registry import ToolRegistry
    tool_registry = ToolRegistry(runtime.plugin_loader)

    tool_agent = ToolAgent(
        tool_registry=tool_registry,
        artifact_repo=art_repo,
        tool_factory=executor_factory
    )

    agents = [
        intent_agent,
        planner_agent,
        memory_agent,
        reasoning_agent,
        tool_agent
    ]

    agent_runtime = AgentRuntime(
        agents=agents,
        runtime_coordinator=runtime,
        conversation_repo=conv_repo
    )

    return agent_runtime


def make_working_memory() -> WorkingMemory:
    """
    Create a fresh WorkingMemory instance for a new request.

    Convenience function so callers don't need to import from memory.working directly.
    Phase 4: WorkingMemory will be attached to ExecutionContext automatically
             by the AgentRuntime before the first agent runs.
    """
    return WorkingMemory()
