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
    def save_execution_history(self, **kwargs): pass
    def get_by_key(self, key): return None
    def create(self, **kwargs):
        return MockArtifact(**kwargs)

def tool_factory(cap):
    mock_repo = MockRepo()
    return registry.get_executor(cap, mock_repo, mock_repo, str(paths.workspace_dir))

agent = ToolAgent(registry, MockRepo(), tool_factory)
ctx = ExecutionContext(prompt="test")
ctx.capabilities = ["python_execution"]
ctx.execution_metadata["assistant_response"] = """```json
{"tool": "python_execution", "parameters": {"code": "print('123')"}}
```"""

for chunk in agent.run(ctx):
    print(chunk)
