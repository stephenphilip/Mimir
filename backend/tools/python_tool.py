import os
import sys
import uuid
import subprocess
from pathlib import Path
from typing import Dict, Any, Optional, Union

from .base_tool import ITool
from app.interfaces.repositories import IArtifactRepository, ISettingRepository
from app.core.context import ExecutionContext

class PythonTool(ITool):
    """
    Python execution tool implementing ITool (Phase 5).
    Replaces the old PythonExecutor.
    """
    
    def __init__(
        self,
        artifact_repo: IArtifactRepository,
        setting_repo: ISettingRepository,
        workspace_dir: Optional[Union[str, Path]] = None,
    ):
        from config.paths import get_paths
        from config.settings import get_settings

        paths = get_paths()
        self.artifact_repo = artifact_repo
        self.setting_repo = setting_repo
        self.workspace_dir = str(workspace_dir or paths.workspace_dir)
        self.artifacts_dir = str(paths.artifacts_dir)
        self._exec_timeout_s = get_settings().python_execution_timeout_s
        os.makedirs(self.artifacts_dir, exist_ok=True)

    @classmethod
    def name(cls) -> str:
        return "python_execution"

    @classmethod
    def description(cls) -> str:
        return "Execute arbitrary python code. Use this for data processing, math, fetching APIs, or any logic that can be expressed in Python."

    @classmethod
    def get_schema(cls) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "code": {
                    "type": "string", 
                    "description": "The complete Python script to execute. Must be valid Python code."
                }
            },
            "required": ["code"]
        }

    def _resolve_python(self) -> str:
        """Resolve venv python from settings or project-relative config."""
        from config.paths import get_paths

        execution_env = self.setting_repo.get_by_key("execution_env")
        venv_dir = Path(execution_env) if execution_env else get_paths().venv_dir
        if sys.platform == "win32":
            candidate = venv_dir / "Scripts" / "python.exe"
        else:
            candidate = venv_dir / "bin" / "python"
        return str(candidate) if candidate.exists() else sys.executable

    def execute(self, params: Dict[str, Any], context: ExecutionContext) -> Dict[str, Any]:
        code = params.get("code", "")
        if not code.strip():
            return {"success": True, "stdout": "", "stderr": "No code provided", "exit_code": 0, "artifacts": []}

        venv_python = self._resolve_python()

        # Scan folder before run
        files_before = set(os.listdir(self.artifacts_dir))
        
        # Write temporary script file inside workspace
        temp_script_name = f"run_{uuid.uuid4().hex}.py"
        temp_script_path = os.path.join(self.workspace_dir, temp_script_name)
        
        with open(temp_script_path, "w", encoding="utf-8") as f:
            f.write(code)

        stdout_content = ""
        stderr_content = ""
        exit_code = 0

        # Execute
        try:
            process = subprocess.run(
                [venv_python, temp_script_path],
                cwd=self.artifacts_dir, # Run in artifacts dir so files save there directly
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                timeout=self._exec_timeout_s,
            )
            stdout_content = process.stdout
            stderr_content = process.stderr
            exit_code = process.returncode
        except subprocess.TimeoutExpired:
            stderr_content = f"Execution timed out (limit: {self._exec_timeout_s} seconds)."
            exit_code = -1
        except Exception as e:
            stderr_content = f"Execution error: {str(e)}"
            exit_code = -2
        finally:
            # Cleanup temp script
            if os.path.exists(temp_script_path):
                try:
                    os.remove(temp_script_path)
                except Exception:
                    pass

        # Scan folder after run to detect newly created files
        files_after = set(os.listdir(self.artifacts_dir))
        new_files = files_after - files_before
        
        artifacts_records = []
        assistant_message_id = context.execution_metadata.get("assistant_message_id")
        
        for file_name in new_files:
            file_path = os.path.join(self.artifacts_dir, file_name)
            _, ext = os.path.splitext(file_name)
            file_type = ext.lower().replace(".", "")
            file_size = os.path.getsize(file_path)

            # Create artifact using repository
            artifact = self.artifact_repo.create(
                message_id=assistant_message_id,
                file_name=file_name,
                file_path=f"/artifacts/{file_name}", # Web accessible path
                file_type=file_type,
                file_size=file_size
            )
            
            artifact_dict = {
                "id": artifact.id,
                "file_name": artifact.file_name,
                "file_path": artifact.file_path,
                "file_type": artifact.file_type,
                "file_size": artifact.file_size
            }
            artifacts_records.append(artifact_dict)
            context.generated_artifacts.append(artifact_dict)

        result = {
            "success": exit_code == 0,
            "stdout": stdout_content,
            "stderr": stderr_content,
            "exit_code": exit_code,
            "artifacts": artifacts_records
        }
        
        return result
