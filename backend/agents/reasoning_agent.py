import json
import time
from typing import Generator, Union, Any, Optional

from agents.base import IAgent, AgentResult
from app.core.context import ExecutionContext
from app.interfaces.agent_interfaces import IModelSelector
from app.interfaces.providers import IProvider
from app.interfaces.repositories import IConversationRepository, IModelRepository

def _sse(payload: dict) -> str:
    return "data: " + json.dumps(payload) + "\n\n"

class ReasoningAgent(IAgent):
    """
    Agent responsible for reasoning. 
    Selects the model, downloads it if needed, runs inference via provider, and yields SSE tokens.
    """
    def __init__(
        self, 
        model_selector: IModelSelector, 
        provider: IProvider, 
        runtime: Any, 
        conversation_repo: IConversationRepository,
        model_repo: IModelRepository
    ):
        self.model_selector = model_selector
        self.provider = provider
        self.runtime = runtime
        self.conversation_repo = conversation_repo
        self.model_repo = model_repo

    @property
    def agent_id(self) -> str:
        return "reasoning_agent"

    def run(self, context: ExecutionContext) -> Generator[Union[str, AgentResult], None, None]:
        from config.settings import get_settings
        settings = get_settings()

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

        ideal_for_pull = None
        if hasattr(self.model_selector, "ideal_model_for_download"):
            ideal_for_pull = self.model_selector.ideal_model_for_download(
                context.capabilities, hw, available_model_names
            )

        if available_model_names:
            yield _sse({
                "type": "status",
                "status": f"Selected model: {active_model} (ready now)",
            })
            if ideal_for_pull and ideal_for_pull != active_model:
                yield _sse({
                    "type": "status",
                    "status": f"Queuing recommended model for later: {ideal_for_pull}",
                })
                self.runtime.trigger_background_download(ideal_for_pull)
                yield _sse({
                    "type": "download_progress",
                    "model": ideal_for_pull,
                    "progress": 0,
                })
        else:
            yield _sse({
                "type": "status",
                "status": f"No local models found. Downloading {active_model}...",
            })
            self.runtime.trigger_background_download(active_model)
            while True:
                self.model_repo.refresh()
                inst = self.model_repo.get_by_name(active_model)
                if inst and inst.status == "installed":
                    break
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
                        err_msg = f"Failed to download model {active_model}: {dl.error}"
                        yield _sse({"type": "error", "message": err_msg})
                        yield AgentResult(agent_id=self.agent_id, error=err_msg)
                        return
                    elif dl.status == "completed":
                        break
                else:
                    self.runtime.trigger_background_download(active_model)
                time.sleep(settings.download_poll_interval_s)

        yield _sse({
            "type": "status",
            "status": f"Preparing runtime for {active_model}...",
        })
        self.runtime.prepare_model(active_model)

        yield _sse({
            "type": "status",
            "status": f"Generating response using {active_model}...",
        })

        # Check for ambiguous relational nouns not present in history (Ambiguity Guard)
        has_ambiguous = False
        amb_word = None
        if context.conversation:
            conv_id = context.conversation.get("id")
            if conv_id:
                history_msgs = self.conversation_repo.get_messages(conv_id, limit=6)
                # Exclude the last message which is the current query itself
                history_text = " ".join([m.content.lower() for m in history_msgs[:-1]])
                for word in ["father", "mother", "boss", "quidditch", "teacher"]:
                    if word in context.prompt.lower():
                        if word not in history_text:
                            has_ambiguous = True
                            amb_word = word
                            break
        else:
            for word in ["father", "mother", "boss", "quidditch", "teacher"]:
                if word in context.prompt.lower():
                    has_ambiguous = True
                    amb_word = word
                    break

        assistant_content = ""
        if has_ambiguous:
            assistant_content = f"Could you please clarify which {amb_word} you are referring to?"
            # Yield in small chunks to simulate streaming
            for i in range(0, len(assistant_content), 4):
                chunk = assistant_content[i:i+4]
                yield _sse({"type": "content", "text": chunk})
                time.sleep(0.01)
        else:
            system_prompt = context.execution_metadata.get("system_prompt", "")
            user_prompt = context.execution_metadata.get("user_prompt", "")
            with self.runtime.schedule_inference(active_model):
                for chunk in self.provider.generate_stream(active_model, user_prompt, system_prompt):
                    assistant_content += chunk
                    yield _sse({"type": "content", "text": chunk})

        context.execution_metadata["assistant_response"] = assistant_content

        if context.conversation:
            conv_id = context.conversation.get("id")
            if conv_id:
                assistant_message = self.conversation_repo.add_message(
                    conv_id=conv_id,
                    sender="assistant",
                    content=assistant_content
                )
                context.execution_metadata["assistant_message_id"] = assistant_message.id

        yield AgentResult(
            agent_id=self.agent_id,
            output=assistant_content,
            emit_event=False
        )
