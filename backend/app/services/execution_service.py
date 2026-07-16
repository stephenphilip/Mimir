from .execution_engine import ExecutionEngine
from ..extensions.python import PythonExecutor

class ExecutionService:
    def __init__(self, workspace_dir="C:/Users/StephenPhilipKallara/Mimir", venv_python=None):
        from ..db import SessionLocal
        from ..repositories.sqlite_repositories import SQLiteArtifactRepository, SQLiteSettingRepository
        db = SessionLocal()
        self.artifact_repo = SQLiteArtifactRepository(db)
        self.setting_repo = SQLiteSettingRepository(db)
        self.engine = ExecutionEngine(self.artifact_repo)
        self.executor = PythonExecutor(self.artifact_repo, self.setting_repo, workspace_dir)
        self.engine.register_executor(self.executor)

    def extract_python_code(self, text: str) -> str:
        return self.engine.extract_python_code(text)

    def execute_code(self, code: str, message_id: int, db) -> dict:
        from ..core.context import ExecutionContext
        context = ExecutionContext(prompt="", execution_metadata={"assistant_message_id": message_id})
        return self.executor.execute(code, context)
