from .execution_engine import ExecutionEngine





class ExecutionService:

    def __init__(self, workspace_dir=None, venv_python=None):

        from config.paths import get_paths

        from ..db import SessionLocal

        from ..repositories.sqlite_repositories import SQLiteArtifactRepository, SQLiteSettingRepository

        from ..extensions.python import PythonExecutor

        from ..creator.factory import build_creator_engine



        paths = get_paths()

        workspace = workspace_dir or str(paths.workspace_dir)

        db = SessionLocal()

        self.artifact_repo = SQLiteArtifactRepository(db)

        self.setting_repo = SQLiteSettingRepository(db)

        creator_engine, _ = build_creator_engine(self.artifact_repo)

        self.engine = ExecutionEngine(self.artifact_repo)

        self.executor = PythonExecutor(

            self.artifact_repo,

            self.setting_repo,

            workspace,

            creator_engine=creator_engine,

        )

        self.engine.register_executor(self.executor)



    def extract_python_code(self, text: str) -> str:

        return self.engine.extract_python_code(text)



    def execute_code(self, code: str, message_id: int, db) -> dict:

        from ..core.context import ExecutionContext

        context = ExecutionContext(prompt="", execution_metadata={"assistant_message_id": message_id})

        return self.executor.execute(code, context)


