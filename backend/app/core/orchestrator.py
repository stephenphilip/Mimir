import json
import time
from typing import Generator, Any, Optional, Dict

from .context import ExecutionContext
from ..interfaces.services import (
    IIntentService,
    ICapabilityService,
    IContextBuilder,
    IModelSelector,
    IExecutionEngine,
    IPlanner,
)
from ..interfaces.providers import IProvider
from ..interfaces.repositories import IConversationRepository, IModelRepository


def _sse(payload: Dict[str, Any]) -> str:
    """Format a Server-Sent Event data line."""
    return "data: " + json.dumps(payload) + "\n\n"


class Orchestrator:
    def __init__(
        self,
        intent_service: IIntentService,
        capability_service: ICapabilityService,
        context_builder: IContextBuilder,
        model_selector: IModelSelector,
        provider: IProvider,
        execution_engine: IExecutionEngine,
        planner: IPlanner,
        runtime: Any,
        conversation_repo: IConversationRepository,
        model_repo: IModelRepository,
        # Backward-compatible alias: older callers may still pass model_service
        model_service: Optional[Any] = None,
        creator_engine: Optional[Any] = None,
    ):
        self.intent_service = intent_service
        self.capability_service = capability_service
        self.context_builder = context_builder
        self.model_selector = model_selector
        self.provider = provider
        self.execution_engine = execution_engine
        self.planner = planner
        self.conversation_repo = conversation_repo
        self.model_repo = model_repo
        self.creator_engine = creator_engine

        if runtime is not None:
            self.runtime = runtime
        elif model_service is not None:
            from runtime.runtime_coordinator import RuntimeCoordinator
            self.runtime = RuntimeCoordinator(model_service=model_service)
        else:
            raise TypeError("Orchestrator requires runtime (or model_service for compatibility)")

    def process_prompt(
        self,
        conversation_id: str,
        prompt: str,
        workspace_id: Optional[str] = None,
    ) -> Generator[str, None, None]:
        """Stream orchestration steps as JSON event strings."""
        from config.settings import get_settings

        settings = get_settings()
        session_id = self.runtime.begin_session(conversation_id)

        try:
            # 1. Initialize ExecutionContext
            context = ExecutionContext(prompt=prompt)
            context.execution_status = "running"
            if workspace_id:
                context.execution_metadata["workspace_id"] = workspace_id

            # Load conversation
            conv = self.conversation_repo.get_by_id(conversation_id)
            if conv:
                context.conversation = {"id": conv.id, "title": conv.title, "user_id": conv.user_id}
            else:
                context.conversation = {"id": conversation_id, "title": "New Chat", "user_id": 1}

            # 2. Save user message
            user_message = self.conversation_repo.add_message(
                conv_id=conversation_id,
                sender="user",
                content=prompt
            )
            context.user = {"id": user_message.conversation.user_id if user_message.conversation else 1}

            # 3. Intent Engine
            yield _sse({"type": "status", "status": "Detecting intent..."})
            intent_res = self.intent_service.classify(prompt)
            context.intent = intent_res["intent"]
            context.intent_confidence = intent_res["confidence"]
            yield _sse({
                "type": "status",
                "status": "Detected intent: {} (confidence {})".format(
                    context.intent, context.intent_confidence
                ),
            })

            # 4. Capability Engine
            yield _sse({"type": "status", "status": "Mapping capabilities..."})
            context.capabilities = self.capability_service.resolve(context.intent)
            yield _sse({
                "type": "status",
                "status": "Requirements: {}".format(", ".join(context.capabilities)),
            })

            # 5. Planner
            plan = self.planner.create_plan(context)
            yield _sse({
                "type": "execution_plan",
                "plan": {
                    "workflow": getattr(plan, "workflow", None),
                    "intent": getattr(plan, "intent", None),
                    "preferred_artifact": getattr(plan, "preferred_artifact", None),
                    "steps": plan.steps if hasattr(plan, "steps") else [],
                },
            })
            yield _sse({
                "type": "status",
                "status": "Plan: {} ({} steps)".format(
                    getattr(plan, "workflow", "chat"),
                    len(plan.steps) if hasattr(plan, "steps") else 0,
                ),
            })

            # 6. Context Builder (memory initializes lazily on first use here)
            self.context_builder.build_context(context)

            # 7. Model Selection — prefer installed models for instant answers
            yield _sse({"type": "status", "status": "Selecting best available model..."})
            self.runtime.sync_models_to_db()

            installed_models = self.model_repo.get_all_installed()
            available_model_names = [m.name for m in installed_models if m.status == "installed"]
            hw = self.runtime.detect_hardware()

            active_model = self.model_selector.select_best_model(
                context, available_model_names, context.capabilities, hw
            )
            context.selected_model = active_model
            context.selected_provider = "ollama"

            # Ideal model for this task — pull in background if missing (never block chat)
            ideal_for_pull = None
            if hasattr(self.model_selector, "ideal_model_for_download"):
                ideal_for_pull = self.model_selector.ideal_model_for_download(
                    context.capabilities, hw, available_model_names
                )

            if available_model_names:
                yield _sse({
                    "type": "status",
                    "status": "Selected model: {} (ready now)".format(active_model),
                })
                if ideal_for_pull and ideal_for_pull != active_model:
                    yield _sse({
                        "type": "status",
                        "status": "Queuing recommended model for later: {}".format(ideal_for_pull),
                    })
                    self.runtime.trigger_background_download(ideal_for_pull)
                    yield _sse({
                        "type": "download_progress",
                        "model": ideal_for_pull,
                        "progress": 0,
                    })
            else:
                # Nothing installed — must pull before we can answer
                yield _sse({
                    "type": "status",
                    "status": "No local models found. Downloading {}...".format(active_model),
                })
                self.runtime.trigger_background_download(active_model)
                while True:
                    self.model_repo.refresh()
                    inst = self.model_repo.get_by_name(active_model)
                    if inst and inst.status == "installed":
                        break
                    # Also accept base-name matches after pull completes
                    ready = [
                        m.name for m in self.model_repo.get_all_installed()
                        if m.status == "installed"
                    ]
                    if ready:
                        active_model = self.model_selector.select_best_model(
                            context, ready, context.capabilities, hw
                        )
                        context.selected_model = active_model
                        break

                    dl = self.model_repo.get_download(active_model)
                    if dl:
                        if dl.status == "downloading":
                            yield _sse({
                                "type": "download_progress",
                                "model": active_model,
                                "progress": dl.progress,
                            })
                        elif dl.status == "failed":
                            yield _sse({
                                "type": "error",
                                "message": "Failed to download model {}: {}".format(
                                    active_model, dl.error
                                ),
                            })
                            return
                        elif dl.status == "completed":
                            break
                    else:
                        self.runtime.trigger_background_download(active_model)
                    time.sleep(settings.download_poll_interval_s)

            # 8. Prepare runtime (skip cold unload when model already warm)
            yield _sse({
                "type": "status",
                "status": "Preparing runtime for {}...".format(active_model),
            })
            self.runtime.prepare_model(active_model)

            # 9. Stream Inference (scheduled slot; provider still owns generation)
            yield _sse({
                "type": "status",
                "status": "Generating response using {}...".format(active_model),
            })

            system_prompt = context.execution_metadata.get("system_prompt", "")
            user_prompt = context.execution_metadata.get("user_prompt", "")

            assistant_content = ""
            with self.runtime.schedule_inference(active_model):
                for chunk in self.provider.generate_stream(active_model, user_prompt, system_prompt):
                    assistant_content += chunk
                    yield _sse({"type": "content", "text": chunk})

            context.execution_metadata["assistant_response"] = assistant_content

            # 10. Save assistant message
            assistant_message = self.conversation_repo.add_message(
                conv_id=conversation_id,
                sender="assistant",
                content=assistant_content
            )
            context.execution_metadata["assistant_message_id"] = assistant_message.id

            # 11. Tool Execution Pipeline
            workflow = context.execution_metadata.get("workflow") or "chat"

            if workflow == "structured_document":
                yield _sse({"type": "execution_status", "status": "generating"})
                yield _sse({"type": "status", "status": "Rendering structured document..."})
                from ..intelligence.document_workflow import DocumentWorkflow

                doc_workflow = DocumentWorkflow(creator_engine=self.creator_engine)
                artifact_type = context.execution_metadata.get("preferred_artifact") or "pdf"
                exec_result = doc_workflow.execute(
                    llm_content=assistant_content,
                    user_prompt=prompt,
                    artifact_type=artifact_type,
                    workspace_id=context.execution_metadata.get("workspace_id"),
                    message_id=assistant_message.id,
                    original_prompt=prompt,
                    execution_plan=context.execution_metadata.get("workflow_plan"),
                )
                final_status = "completed" if exec_result.get("success") else "failed"
                yield _sse({"type": "execution_status", "status": final_status})
                yield _sse({
                    "type": "execution_result",
                    "success": exec_result["success"],
                    "stdout": exec_result.get("stdout", ""),
                    "stderr": exec_result.get("stderr", ""),
                    "exit_code": exec_result.get("exit_code", 0),
                    "artifacts": exec_result.get("artifacts", []),
                    "execution_status": final_status,
                    "workflow": "structured_document",
                })
            elif "python_execution" in context.capabilities or "python" in context.capabilities:
                yield _sse({"type": "execution_status", "status": "generating"})
                yield _sse({"type": "status", "status": "Executing generated python code..."})

                exec_result = self.execution_engine.execute(context)
                final_status = "completed" if exec_result.get("success") else "failed"
                yield _sse({"type": "execution_status", "status": final_status})
                yield _sse({
                    "type": "execution_result",
                    "success": exec_result["success"],
                    "stdout": exec_result["stdout"],
                    "stderr": exec_result["stderr"],
                    "exit_code": exec_result["exit_code"],
                    "artifacts": exec_result["artifacts"],
                    "execution_status": final_status,
                })

            new_title = prompt[:30] + "..." if len(prompt) > 30 else prompt
            self.conversation_repo.update_title(conversation_id, new_title)

            yield _sse({"type": "done", "conversation_id": conversation_id})
        except Exception as e:
            yield _sse({
                "type": "error",
                "message": "Internal Server Error: {}".format(str(e)),
            })
        finally:
            self.runtime.end_session(session_id)
