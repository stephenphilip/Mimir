import json
from typing import Generator, List, Any

from agents.base import IAgent, AgentResult
from app.core.context import ExecutionContext
from app.interfaces.repositories import IConversationRepository

def _sse(payload: dict) -> str:
    return "data: " + json.dumps(payload) + "\n\n"

class AgentRuntime:
    """
    Dispatcher that replaces the legacy Orchestrator.
    Routes an ExecutionContext through a pipeline of specialized agents.
    """
    def __init__(
        self,
        agents: List[IAgent],
        runtime_coordinator: Any,
        conversation_repo: IConversationRepository
    ):
        self.agents = agents
        self.runtime_coordinator = runtime_coordinator
        self.conversation_repo = conversation_repo

    def process_prompt(
        self,
        conversation_id: str,
        prompt: str,
        workspace_id: str = None,
        **kwargs
    ) -> Generator[str, None, None]:
        session_id = self.runtime_coordinator.begin_session(conversation_id)
        
        try:
            context = ExecutionContext(prompt=prompt)
            context.execution_status = "running"
            if workspace_id:
                context.execution_metadata["workspace_id"] = workspace_id
            
            # 1. Load or initialize conversation
            conv = self.conversation_repo.get_by_id(conversation_id)
            if conv:
                context.conversation = {
                    "id": conv.id,
                    "title": conv.title,
                    "user_id": conv.user_id,
                    "project_id": conv.project_id
                }
            else:
                context.conversation = {"id": conversation_id, "title": "New Chat", "user_id": 1, "project_id": None}
                
            # 2. Save user message
            user_message = self.conversation_repo.add_message(
                conv_id=conversation_id,
                sender="user",
                content=prompt
            )
            context.user = {"id": user_message.conversation.user_id if user_message.conversation else 1}
            
            # 3. Route through Agents sequentially
            # 3. Route through Agents sequentially
            has_error = False
            for agent in self.agents:
                if context.execution_status == "failed":
                    has_error = True
                    break
                if agent.can_run(context):
                    for chunk in agent.run(context):
                        if isinstance(chunk, str):
                            yield chunk
                        elif isinstance(chunk, AgentResult):
                            if chunk.error:
                                yield _sse({"type": "error", "message": f"Agent {chunk.agent_id} failed: {chunk.error}"})
                                has_error = True
                            elif chunk.emit_event and chunk.status_message:
                                yield _sse({"type": "status", "status": chunk.status_message})
                    if has_error:
                        break
            
            # 4. Update conversation title if needed
            conv = self.conversation_repo.get_by_id(conversation_id)
            if conv and (conv.title in ("New Chat", "New Conversation", "") or len(self.conversation_repo.get_messages(conversation_id)) <= 2):
                new_title = prompt[:30] + "..." if len(prompt) > 30 else prompt
                self.conversation_repo.update_title(conversation_id, new_title)

            if not has_error and context.execution_status != "failed":
                yield _sse({"type": "done", "conversation_id": conversation_id})
            
        except Exception as e:
            yield _sse({
                "type": "error",
                "message": f"Internal Server Error: {str(e)}"
            })
        finally:
            self.runtime_coordinator.end_session(session_id)
