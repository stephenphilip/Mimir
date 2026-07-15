import os
import re
import uuid
import subprocess
import shutil
from sqlalchemy.orm import Session
from ..db import ExecutionHistory, GeneratedArtifact

class ExecutionService:
    def __init__(self, workspace_dir="C:/Users/StephenPhilipKallara/Mimir", 
                 venv_python="C:/Users/StephenPhilipKallara/Mimir/backend/.venv/Scripts/python.exe"):
        self.workspace_dir = workspace_dir
        self.artifacts_dir = os.path.join(workspace_dir, "artifacts")
        self.venv_python = venv_python
        
        # Ensure directories exist
        os.makedirs(self.artifacts_dir, exist_ok=True)

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

    def execute_code(self, code: str, message_id: int, db: Session) -> dict:
        """Execute python code in a subprocess, detecting any new files generated."""
        if not code.strip():
            return {"success": True, "output": "No code executed.", "artifacts": []}

        # Scan folder before run
        files_before = set(os.listdir(self.artifacts_dir))
        
        # Write temporary script file inside workspace (out of direct artifacts folder)
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
                [self.venv_python, temp_script_path],
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
        for file_name in new_files:
            file_path = os.path.join(self.artifacts_dir, file_name)
            # Standardize file extension check
            _, ext = os.path.splitext(file_name)
            file_type = ext.lower().replace(".", "")
            file_size = os.path.getsize(file_path)

            artifact = GeneratedArtifact(
                message_id=message_id,
                file_name=file_name,
                file_path=f"/artifacts/{file_name}", # Web accessible path
                file_type=file_type,
                file_size=file_size
            )
            db.add(artifact)
            db.commit()
            db.refresh(artifact)
            artifacts_records.append({
                "id": artifact.id,
                "file_name": artifact.file_name,
                "file_path": artifact.file_path,
                "file_type": artifact.file_type,
                "file_size": artifact.file_size
            })

        # Save execution log
        history = ExecutionHistory(
            command=f"python {temp_script_name}",
            code_content=code,
            stdout=stdout_content,
            stderr=stderr_content,
            exit_code=exit_code
        )
        db.add(history)
        db.commit()

        return {
            "success": exit_code == 0,
            "stdout": stdout_content,
            "stderr": stderr_content,
            "exit_code": exit_code,
            "artifacts": artifacts_records
        }
