import os
import sys
import uuid
import subprocess
from pathlib import Path
from typing import Dict, Any, Optional, Union, List

from ..interfaces.executors import IExecutor
from ..interfaces.repositories import IArtifactRepository, ISettingRepository
from ..core.context import ExecutionContext
from ..creator.diagnostics import get_execution_diagnostics
from ..creator.types import GenerationRequest
from .code_prepare import looks_like_pdf_task, prepare_execution_code


class PythonExecutor(IExecutor):
    def __init__(
        self,
        artifact_repo: IArtifactRepository,
        setting_repo: ISettingRepository,
        workspace_dir: Optional[Union[str, Path]] = None,
        creator_engine=None,
    ):
        from config.paths import get_paths
        from config.settings import get_settings

        paths = get_paths()
        self.artifact_repo = artifact_repo
        self.setting_repo = setting_repo
        self.workspace_dir = str(workspace_dir or paths.workspace_dir)
        self.artifacts_dir = str(paths.artifacts_dir)
        self._creator_engine = creator_engine
        self._exec_timeout_s = get_settings().python_execution_timeout_s
        self._diag = get_execution_diagnostics()
        os.makedirs(self.artifacts_dir, exist_ok=True)

    def can_execute(self, capability: str) -> bool:
        return capability == "python_execution"

    def _resolve_python(self) -> str:
        """Resolve venv python — must have fpdf/pandas for artifact generation."""
        from config.python_env import (
            ensure_execution_packages,
            missing_execution_packages,
            resolve_python_executable,
        )

        python = resolve_python_executable()

        execution_env = self.setting_repo.get_by_key("execution_env")
        if execution_env:
            venv_dir = Path(execution_env)
            if sys.platform == "win32":
                candidate = venv_dir / "Scripts" / "python.exe"
            else:
                candidate = venv_dir / "bin" / "python"
            if candidate.is_file() and not missing_execution_packages(candidate, ["fpdf"]):
                python = candidate

        if not getattr(self, "_deps_checked", False):
            ensure_execution_packages(python)
            self._deps_checked = True  # type: ignore[attr-defined]

        return str(python)

    def _snapshot_artifacts(self) -> Dict[str, float]:
        snap: Dict[str, float] = {}
        for name in os.listdir(self.artifacts_dir):
            if name.startswith("."):
                continue
            fp = os.path.join(self.artifacts_dir, name)
            if os.path.isfile(fp):
                snap[name] = os.path.getmtime(fp)
        return snap

    def _run_subprocess(self, venv_python: str, code: str) -> Dict[str, Any]:
        temp_script_name = f"run_{uuid.uuid4().hex}.py"
        temp_script_path = os.path.join(self.artifacts_dir, temp_script_name)

        prepared = prepare_execution_code(code, self.artifacts_dir)
        with open(temp_script_path, "w", encoding="utf-8") as f:
            f.write(prepared)

        stdout_content = ""
        stderr_content = ""
        exit_code = 0

        try:
            process = subprocess.run(
                [venv_python, temp_script_path],
                cwd=self.artifacts_dir,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                timeout=self._exec_timeout_s,
            )
            stdout_content = process.stdout or ""
            stderr_content = process.stderr or ""
            exit_code = process.returncode
        except subprocess.TimeoutExpired:
            stderr_content = f"Execution timed out (limit: {self._exec_timeout_s} seconds)."
            exit_code = -1
        except Exception as e:
            stderr_content = f"Execution error: {str(e)}"
            exit_code = -2
        finally:
            if os.path.exists(temp_script_path):
                try:
                    os.remove(temp_script_path)
                except Exception:
                    pass

        return {
            "stdout": stdout_content,
            "stderr": stderr_content,
            "exit_code": exit_code,
        }

    def _try_pdf_fallback(
        self,
        context: ExecutionContext,
        user_prompt: str,
    ) -> Optional[Dict[str, Any]]:
        """Use DocumentProvider when LLM Python PDF code fails."""
        if self._creator_engine is None:
            return None

        title = "Mimir Document"
        content = user_prompt or context.prompt or "Generated document"
        if len(content) > 200:
            content = content[:2000]

        req = GenerationRequest(
            artifact_type="pdf",
            title=title,
            content=content,
            workspace_id=context.execution_metadata.get("workspace_id"),
            message_id=context.execution_metadata.get("assistant_message_id"),
            provider="document",
        )
        self._diag.log("execution", "PDF fallback via DocumentProvider")
        result = self._creator_engine.generate(req)
        if not result.success or not result.artifact:
            return None

        artifact_dict = result.artifact.to_dict()
        context.generated_artifacts.append(artifact_dict)
        return {
            "success": True,
            "stdout": result.stdout or "PDF generated via document provider fallback.",
            "stderr": "",
            "exit_code": 0,
            "artifacts": [artifact_dict],
        }

    def execute(self, code: str, context: ExecutionContext) -> Dict[str, Any]:
        if not code.strip():
            return {"success": True, "stdout": "", "stderr": "", "exit_code": 0, "artifacts": []}

        venv_python = self._resolve_python()
        self._diag.log("execution", "Starting Python subprocess", metadata={"python": venv_python})

        files_before = self._snapshot_artifacts()
        user_prompt = context.prompt or ""

        run = self._run_subprocess(venv_python, code)
        stdout_content = run["stdout"]
        stderr_content = run["stderr"]
        exit_code = run["exit_code"]

        self._diag.log(
            "provider",
            f"Python exit code {exit_code}",
            level="error" if exit_code != 0 else "info",
        )

        if exit_code != 0 and looks_like_pdf_task(code, user_prompt):
            fallback = self._try_pdf_fallback(context, user_prompt)
            if fallback:
                return fallback

        files_after = self._snapshot_artifacts()
        changed_files = [
            name
            for name, mtime in files_after.items()
            if name not in files_before or mtime > files_before[name]
        ]

        artifacts_records: List[dict] = []
        validation_errors: List[str] = []
        assistant_message_id = context.execution_metadata.get("assistant_message_id")
        workspace_id = context.execution_metadata.get("workspace_id")

        if exit_code != 0:
            if changed_files:
                validation_errors.append(
                    f"Python exited with code {exit_code}; {len(changed_files)} file(s) were not registered."
                )
                self._diag.log(
                    "filesystem",
                    f"Skipping registration for {len(changed_files)} files due to non-zero exit",
                    level="warning",
                )
            elif looks_like_pdf_task(code, user_prompt):
                fallback = self._try_pdf_fallback(context, user_prompt)
                if fallback:
                    return fallback
        else:
            for file_name in sorted(changed_files):
                file_path = os.path.join(self.artifacts_dir, file_name)
                _, ext = os.path.splitext(file_name)
                file_type = ext.lower().replace(".", "")

                if self._creator_engine is not None:
                    gen = self._creator_engine.register_existing_file(
                        file_path,
                        message_id=assistant_message_id,
                        workspace_id=workspace_id,
                        provider="python_execution",
                        artifact_type=file_type,
                    )
                    if gen.success and gen.artifact:
                        artifact_dict = gen.artifact.to_dict()
                        artifacts_records.append(artifact_dict)
                        context.generated_artifacts.append(artifact_dict)
                        continue
                    err = gen.error or gen.stderr or "Validation failed"
                    validation_errors.append(f"{file_name}: {err}")
                    self._diag.log("validation", f"{file_name}: {err}", level="error")
                    continue

                if not os.path.isfile(file_path) or os.path.getsize(file_path) == 0:
                    validation_errors.append(f"{file_name}: empty or missing")
                    continue

                file_size = os.path.getsize(file_path)
                artifact = self.artifact_repo.create(
                    message_id=assistant_message_id,
                    file_name=file_name,
                    file_path=f"/artifacts/{file_name}",
                    file_type=file_type,
                    file_size=file_size,
                    workspace_id=workspace_id,
                    provider="python_execution",
                )
                artifact_dict = {
                    "id": artifact.id,
                    "artifact_id": getattr(artifact, "artifact_uuid", None) or artifact.id,
                    "file_name": artifact.file_name,
                    "file_path": artifact.file_path,
                    "file_type": artifact.file_type,
                    "file_size": artifact.file_size,
                    "mime_type": getattr(artifact, "mime_type", None),
                    "provider": getattr(artifact, "provider", None),
                    "status": getattr(artifact, "status", "ready"),
                }
                artifacts_records.append(artifact_dict)
                context.generated_artifacts.append(artifact_dict)

        if validation_errors:
            stderr_content = (stderr_content + "\n" + "\n".join(validation_errors)).strip()

        success = exit_code == 0 and not validation_errors

        if not success and exit_code != 0 and looks_like_pdf_task(code, user_prompt):
            fallback = self._try_pdf_fallback(context, user_prompt)
            if fallback:
                return fallback

        return {
            "success": success,
            "stdout": stdout_content,
            "stderr": stderr_content,
            "exit_code": exit_code,
            "artifacts": artifacts_records,
        }
