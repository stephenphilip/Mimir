import re
from typing import Dict, Any, List

from ..interfaces.services import IExecutionEngine
from ..interfaces.executors import IExecutor
from ..interfaces.repositories import IArtifactRepository
from ..core.context import ExecutionContext

class ExecutionEngine(IExecutionEngine):
    def __init__(self, artifact_repo: IArtifactRepository):
        self.artifact_repo = artifact_repo
        self.executors: List[IExecutor] = []

    def register_executor(self, executor: IExecutor) -> None:
        self.executors.append(executor)

    def extract_python_code(self, text: str) -> str:
        """Extract Python code blocks from markdown text."""
        pattern = r"```python\s*(.*?)\s*```"
        matches = re.findall(pattern, text, re.DOTALL)
        if matches:
            return "\n\n".join(matches)
        
        # Fallback if model didn't use markdown format but returned plain python
        if "import " in text or "print(" in text:
            return text
        return ""

    def execute(self, context: ExecutionContext) -> Dict[str, Any]:
        """Coordinate execution using registered executors based on capabilities."""
        if "python_execution" not in context.capabilities:
            return {"success": True, "stdout": "No python execution required.", "stderr": "", "exit_code": 0, "artifacts": []}

        assistant_response = context.execution_metadata.get("assistant_response", "")
        code = self.extract_python_code(assistant_response)
        
        if not code:
            context.execution_status = "completed"
            return {"success": True, "stdout": "No code block detected for execution.", "stderr": "", "exit_code": 0, "artifacts": []}

        # Find the python executor
        python_executor = None
        for executor in self.executors:
            if executor.can_execute("python_execution"):
                python_executor = executor
                break

        if not python_executor:
            err_msg = "PythonExecutor not registered in the ExecutionEngine."
            context.errors.append(err_msg)
            context.execution_status = "failed"
            return {"success": False, "stdout": "", "stderr": err_msg, "exit_code": -1, "artifacts": []}

        # Execute
        context.execution_status = "running"
        result = python_executor.execute(code, context)

        # Save to execution log database
        self.artifact_repo.save_execution_history(
            command="python script",
            code_content=code,
            stdout=result.get("stdout"),
            stderr=result.get("stderr"),
            exit_code=result.get("exit_code")
        )

        if result.get("success"):
            context.execution_status = "completed"
        else:
            context.execution_status = "failed"
            context.errors.append(result.get("stderr", "Execution failed"))

        return result
