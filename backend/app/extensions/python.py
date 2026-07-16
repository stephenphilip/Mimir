import os
import re
import uuid
import subprocess
from typing import Dict, Any

from ..interfaces.executors import IExecutor
from ..interfaces.repositories import IArtifactRepository, ISettingRepository
from ..core.context import ExecutionContext

class PythonExecutor(IExecutor):
    def __init__(self, artifact_repo: IArtifactRepository, setting_repo: ISettingRepository, workspace_dir: str = "C:/Users/StephenPhilipKallara/Mimir"):
        self.artifact_repo = artifact_repo
        self.setting_repo = setting_repo
        self.workspace_dir = workspace_dir
        self.artifacts_dir = os.path.join(workspace_dir, "artifacts")
        os.makedirs(self.artifacts_dir, exist_ok=True)

    def can_execute(self, capability: str) -> bool:
        return capability == "python_execution"

    def execute(self, code: str, context: ExecutionContext) -> Dict[str, Any]:
        if not code.strip():
            return {"success": True, "stdout": "", "stderr": "", "exit_code": 0, "artifacts": []}

        # Resolve python executable from settings
        execution_env = self.setting_repo.get_by_key("execution_env")
        if execution_env:
            venv_python = os.path.join(execution_env, "Scripts", "python.exe") if os.name == 'nt' else os.path.join(execution_env, "bin", "python")
        else:
            # Fallback
            venv_python = "python"

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
                timeout=120  # Limit to 2 minutes
            )
            stdout_content = process.stdout
            stderr_content = process.stderr
            exit_code = process.returncode
        except subprocess.TimeoutExpired:
            stderr_content = "Execution timed out (limit: 120 seconds)."
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
