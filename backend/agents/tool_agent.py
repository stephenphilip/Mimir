import json
import re
from typing import Generator, Union, Any, Dict

from agents.base import IAgent, AgentResult
from app.core.context import ExecutionContext
from app.interfaces.repositories import IArtifactRepository

def _sse(payload: dict) -> str:
    return "data: " + json.dumps(payload) + "\n\n"

class ToolAgent(IAgent):
    """
    Agent responsible for executing tools based on context capabilities.
    Phase 5: Parses structured JSON tool calls instead of arbitrary code blocks.
    """
    def __init__(self, tool_registry: Any, artifact_repo: IArtifactRepository, tool_factory: Any):
        self.tool_registry = tool_registry
        self.artifact_repo = artifact_repo
        self.tool_factory = tool_factory

    @property
    def agent_id(self) -> str:
        return "tool_agent"

    def can_run(self, context: ExecutionContext) -> bool:
        return bool(context.capabilities)

    def extract_tool_calls(self, text: str, context: ExecutionContext) -> list[Dict[str, Any]]:
        """Extract JSON tool calls from markdown code blocks, supporting unclosed blocks."""
        calls = []
        
        # 1. Parse JSON blocks (handles both closed and unclosed ```json blocks)
        start_idx = 0
        while True:
            idx = text.find("```json", start_idx)
            if idx == -1:
                break
            start_content = idx + 7
            end_idx = text.find("```", start_content)
            if end_idx == -1:
                content = text[start_content:]
                start_idx = len(text)
            else:
                content = text[start_content:end_idx]
                start_idx = end_idx + 3
            
            content_str = content.strip()
            if content_str:
                # Heal triple quotes (both """ and ''') in JSON key-value pairs
                triple_quote_pattern = r'("[a-zA-Z0-9_-]+")\s*:\s*(?:"""|\'\'\')(.*?)(?:"""|\'\'\')'
                def replace_triple(match):
                    key = match.group(1)
                    content_val = match.group(2)
                    escaped_content = content_val.replace('\\', '\\\\').replace('"', '\\"').replace('\n', '\\n').replace('\r', '')
                    return f'{key}: "{escaped_content}"'
                
                healed_str = re.sub(triple_quote_pattern, replace_triple, content_str, flags=re.DOTALL)
                
                try:
                    data = json.loads(healed_str)
                    if isinstance(data, dict) and "tool" in data and "parameters" in data:
                        calls.append(data)
                except json.JSONDecodeError:
                    pass

        # 2. Fallback for raw python blocks
        if not calls and "python_execution" in context.capabilities:
            # If the model tried to output JSON, do NOT execute raw text as Python
            if "```json" not in text:
                py_pattern = r"```python\s*(.*?)\s*```"
                py_matches = re.findall(py_pattern, text, re.DOTALL)
                for py_match in py_matches:
                    calls.append({
                        "tool": "python_execution",
                        "parameters": {"code": py_match.strip()}
                    })
                
                if not calls and ("import " in text or "print(" in text):
                    if not text.strip().startswith("{"):
                        calls.append({
                            "tool": "python_execution",
                            "parameters": {"code": text.strip()}
                        })

        return calls

    def run(self, context: ExecutionContext) -> Generator[Union[str, AgentResult], None, None]:
        assistant_response = context.execution_metadata.get("assistant_response", "")
        tool_calls = self.extract_tool_calls(assistant_response, context)

        if not tool_calls:
            # Check if the plan required a tool execution that was not met
            workflow = context.execution_metadata.get("workflow")
            if workflow == "structured_document":
                yield _sse({"type": "execution_status", "status": "generating"})
                yield _sse({"type": "status", "status": "Rendering structured document..."})
                
                from app.intelligence.document_workflow import DocumentWorkflow
                from app.creator.factory import build_creator_engine
                creator_engine, _ = build_creator_engine(self.artifact_repo)
                
                doc_workflow = DocumentWorkflow(creator_engine=creator_engine)
                artifact_type = context.execution_metadata.get("preferred_artifact") or "pdf"
                
                try:
                    result = doc_workflow.execute(
                        llm_content=assistant_response,
                        user_prompt=context.prompt,
                        artifact_type=artifact_type,
                        workspace_id=context.execution_metadata.get("workspace_id"),
                        message_id=context.execution_metadata.get("assistant_message_id"),
                        original_prompt=context.prompt,
                        execution_plan=context.execution_metadata.get("workflow_plan"),
                    )
                except Exception as e:
                    result = {"success": False, "stdout": "", "stderr": str(e), "exit_code": 1, "artifacts": []}
                
                final_status = "completed" if result.get("success") else "failed"
                yield _sse({"type": "execution_status", "status": final_status})
                yield _sse({
                    "type": "execution_result",
                    "success": result.get("success", False),
                    "stdout": result.get("stdout", ""),
                    "stderr": result.get("stderr", ""),
                    "exit_code": result.get("exit_code", 0),
                    "artifacts": result.get("artifacts", []),
                    "execution_status": final_status,
                    "workflow": "structured_document",
                })
                
                if not result.get("success", False):
                    context.execution_status = "failed"
                    err_msg = result.get("stderr") or "Document rendering failed"
                    context.errors.append(err_msg)
                    yield _sse({"type": "error", "message": err_msg})
                    yield AgentResult(agent_id=self.agent_id, error=err_msg)
                    return
                
                preferred_artifact = context.execution_metadata.get("preferred_artifact")
                if preferred_artifact and not result.get("artifacts"):
                    err_msg = f"Task failed: The document was rendered but failed to save the generated file to disk. No '{preferred_artifact}' artifact was created."
                    context.errors.append(err_msg)
                    context.execution_status = "failed"
                    yield _sse({"type": "error", "message": err_msg})
                    yield AgentResult(agent_id=self.agent_id, error=err_msg)
                    return

                context.execution_status = "completed"
                yield AgentResult(agent_id=self.agent_id, output=None, emit_event=False)
                return

            if workflow in ("python", "image"):
                err_msg = f"Task failed: The model did not output a valid tool call to perform the requested '{workflow}' task."
                context.errors.append(err_msg)
                context.execution_status = "failed"
                yield _sse({"type": "error", "message": err_msg})
                yield AgentResult(agent_id=self.agent_id, error=err_msg)
                return
            
            context.execution_status = "completed"
            yield AgentResult(agent_id=self.agent_id, output=None, emit_event=False)
            return

        for call in tool_calls:
            tool_name = call["tool"]
            params = call["parameters"]

            yield _sse({"type": "status", "status": f"Executing tool: {tool_name}..."})

            # Resolve tool name (e.g. "Python Executor" or ID "python") to capability string
            capability = tool_name
            if hasattr(self.tool_registry, "list_all_tools"):
                for t in self.tool_registry.list_all_tools():
                    if t.get("name") == tool_name or t.get("id") == tool_name or t.get("capability") == tool_name:
                        capability = t.get("capability")
                        break

            tool_instance = self.tool_factory(capability)
            if not tool_instance:
                err_msg = f"Tool '{tool_name}' not registered or not enabled."
                context.errors.append(err_msg)
                context.execution_status = "failed"
                yield _sse({"type": "error", "message": err_msg})
                yield AgentResult(agent_id=self.agent_id, error=err_msg)
                return

            context.execution_status = "running"
            
            try:
                result = tool_instance.execute(params, context)
            except Exception as e:
                result = {"success": False, "stdout": "", "stderr": str(e), "exit_code": -1, "artifacts": []}
                
            # Log history if it's python_execution for backward compatibility
            if capability == "python_execution":
                code = params.get("code", "")
                self.artifact_repo.save_execution_history(
                    command="python script",
                    code_content=code,
                    stdout=result.get("stdout"),
                    stderr=result.get("stderr"),
                    exit_code=result.get("exit_code")
                )

            yield _sse({
                "type": "execution_result",
                "success": result.get("success", False),
                "stdout": result.get("stdout", ""),
                "stderr": result.get("stderr", ""),
                "exit_code": result.get("exit_code", 0),
                "artifacts": result.get("artifacts", []),
            })

            if not result.get("success", False):
                context.execution_status = "failed"
                err_msg = result.get("stderr") or "Tool execution failed"
                context.errors.append(err_msg)
                yield _sse({"type": "error", "message": err_msg})
                yield AgentResult(agent_id=self.agent_id, error=err_msg)
                return
            
            preferred_artifact = context.execution_metadata.get("preferred_artifact")
            if preferred_artifact and not result.get("artifacts"):
                err_msg = f"Task failed: The script executed but failed to save the generated file to disk. No '{preferred_artifact}' artifact was created."
                context.errors.append(err_msg)
                context.execution_status = "failed"
                yield _sse({"type": "error", "message": err_msg})
                yield AgentResult(agent_id=self.agent_id, error=err_msg)
                return

            context.execution_status = "completed"

        yield AgentResult(
            agent_id=self.agent_id,
            output=tool_calls,
            emit_event=False
        )
