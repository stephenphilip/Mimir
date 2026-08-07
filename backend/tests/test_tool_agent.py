from app.core.context import ExecutionContext
from tools.registry import ToolRegistry
from runtime.plugin_loader import PluginLoader
from config.paths import get_paths
from agents.tool_agent import ToolAgent

paths = get_paths()
loader = PluginLoader(paths.extensions_dir)
loader.load_manifests()
registry = ToolRegistry(loader)

class MockArtifact:
    def __init__(self, **kwargs):
        self.id = 1
        self.file_name = kwargs.get("file_name", "")
        self.file_path = kwargs.get("file_path", "")
        self.file_type = kwargs.get("file_type", "")
        self.file_size = kwargs.get("file_size", 0)

class MockRepo:
    def save_execution_history(self, **kwargs):
        pass
    def get_by_key(self, key):
        return None
    def create(self, **kwargs):
        return MockArtifact(**kwargs)

def tool_factory(cap):
    mock_repo = MockRepo()
    return registry.get_executor(cap, mock_repo, mock_repo, str(paths.workspace_dir))

def test_tool_agent_runs_with_capability():
    agent = ToolAgent(registry, MockRepo(), tool_factory)
    ctx = ExecutionContext(prompt="test")
    ctx.capabilities = ["python_execution"]
    ctx.execution_metadata["assistant_response"] = """```json
    {"tool": "python_execution", "parameters": {"code": "print('123')"}}
    ```"""

    chunks = list(agent.run(ctx))
    assert any("Executing tool: python_execution" in str(c) for c in chunks)
    assert ctx.execution_status == "completed"

def test_tool_agent_runs_with_display_name():
    agent = ToolAgent(registry, MockRepo(), tool_factory)
    ctx = ExecutionContext(prompt="test")
    ctx.capabilities = ["python_execution"]
    ctx.execution_metadata["assistant_response"] = """```json
    {"tool": "Python Executor", "parameters": {"code": "print('123')"}}
    ```"""

    chunks = list(agent.run(ctx))
    assert any("Executing tool: Python Executor" in str(c) for c in chunks)
    assert ctx.execution_status == "completed"

def test_tool_agent_fails_when_tool_call_missing_for_python_workflow():
    agent = ToolAgent(registry, MockRepo(), tool_factory)
    ctx = ExecutionContext(prompt="test")
    ctx.capabilities = ["python_execution"]
    ctx.execution_metadata["workflow"] = "python"
    ctx.execution_metadata["assistant_response"] = "This is text without any python code blocks."

    chunks = list(agent.run(ctx))
    assert ctx.execution_status == "failed"
    assert any("The model did not output a valid tool call" in str(c) for c in chunks)

def test_tool_agent_fails_when_artifact_missing():
    agent = ToolAgent(registry, MockRepo(), tool_factory)
    ctx = ExecutionContext(prompt="test")
    ctx.capabilities = ["python_execution"]
    ctx.execution_metadata["preferred_artifact"] = "xlsx"
    ctx.execution_metadata["assistant_response"] = """```json
    {"tool": "Python Executor", "parameters": {"code": "print('123')"}}
    ```"""

    chunks = list(agent.run(ctx))
    assert ctx.execution_status == "failed"
    assert any("failed to save the generated file to disk" in str(c) for c in chunks)
