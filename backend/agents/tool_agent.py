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
        """Extract JSON tool calls from markdown code blocks."""
        pattern = r"```json\s*(.*?)\s*```"
        matches = re.findall(pattern, text, re.DOTALL)
        calls = []
        for match in matches:
            try:
                data = json.loads(match)
                if "tool" in data and "parameters" in data:
                    calls.append(data)
            except json.JSONDecodeError:
                continue

        # Fallback for models that ignore JSON instruction and output raw python
        if not calls and "python_execution" in context.capabilities:
            py_pattern = r"```python\s*(.*?)\s*```"
            py_matches = re.findall(py_pattern, text, re.DOTALL)
            for py_match in py_matches:
                calls.append({
                    "tool": "python_execution",
                    "parameters": {"code": py_match.strip()}
                })
            
            if not calls and ("import " in text or "print(" in text):
                calls.append({
                    "tool": "python_execution",
                    "parameters": {"code": text.strip()}
                })

        return calls

    def run(self, context: ExecutionContext) -> Generator[Union[str, AgentResult], None, None]:
        assistant_response = context.execution_metadata.get("assistant_response", "")
        tool_calls = self.extract_tool_calls(assistant_response, context)

        if not tool_calls:
            context.execution_status = "completed"
            yield AgentResult(agent_id=self.agent_id, output=None, emit_event=False)
            return

        for call in tool_calls:
            tool_name = call["tool"]
            params = call["parameters"]

            yield _sse({"type": "status", "status": f"Executing tool: {tool_name}..."})

            tool_instance = self.tool_factory(tool_name)
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
            if tool_name == "python_execution":
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
                context.errors.append(result.get("stderr", "Tool execution failed"))
            else:
                context.execution_status = "completed"

        yield AgentResult(
            agent_id=self.agent_id,
            output=tool_calls,
            emit_event=False
        )
