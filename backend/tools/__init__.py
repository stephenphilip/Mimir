"""
Tools package — Tool Framework.

Phase 1: Package scaffold + ToolRegistry (wraps PluginLoader for tools).
Phase 5: Structured tool invocation framework:
  - JSON schema-based tool call requests
  - Permission-aware tool gating
  - Sandboxed execution environment
  - Tools: Python, Filesystem, Browser, Git, Documents, Spreadsheet, Speech

Architecture (Phase 5 target):
    tools/
        registry.py           ← Tool discovery and dispatch (DONE Phase 1)
        base_tool.py          ← ITool ABC (Phase 5)
        python_tool.py        ← Python execution (rename from extensions/python.py)
        filesystem_tool.py    ← File read/write/list (Phase 5)
        browser_tool.py       ← Web browsing (Phase 5)
        git_tool.py           ← Git operations (Phase 5)
        documents_tool.py     ← PDF/Word generation (Phase 5)
        spreadsheet_tool.py   ← Excel/CSV generation (Phase 5)
        speech_tool.py        ← TTS/STT (Phase 5+)
"""
from .registry import ToolRegistry

__all__ = ["ToolRegistry"]
