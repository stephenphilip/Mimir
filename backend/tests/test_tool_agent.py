from app.core.context import ExecutionContext
from tools.registry import ToolRegistry
from runtime.plugin_loader import PluginLoader
from config.paths import get_paths
from agents.tool_agent import ToolAgent

paths = get_paths()
loader = PluginLoader(paths.extensions_dir)
loader.load_manifests()
registry = ToolRegistry(loader)

class MockRepo:
    def save_execution_history(self, **kwargs): pass

def tool_factory(cap):
    return registry.get_executor(cap, MockRepo(), None, str(paths.workspace_dir))

agent = ToolAgent(registry, MockRepo(), tool_factory)
ctx = ExecutionContext(prompt="test")
ctx.capabilities = ["python_execution"]
ctx.execution_metadata["assistant_response"] = """```json
{"tool": "python_execution", "parameters": {"code": "print('123')"}}
```"""

for chunk in agent.run(ctx):
    print(chunk)
