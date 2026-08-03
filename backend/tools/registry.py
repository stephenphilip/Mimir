"""
ToolRegistry — Tool discovery and dispatch for the Tool Framework.

Phase 1: Wraps the existing PluginLoader to provide a tool-oriented view
         of available executors. Behavior is identical to the existing
         runtime.plugin_loader.PluginLoader — this is a façade, not a
         replacement.

Phase 5: ToolRegistry will be extended with:
  - Structured tool call schema (JSON schema per tool)
  - Permission gating (user-configurable allow/deny per tool)
  - Tool capability metadata (what inputs/outputs each tool expects)
  - Direct invocation without ExecutionEngine middleware

Design: ToolRegistry is separate from PluginManager (which handles
        generic plugins) because tools have a different lifecycle:
        - Tools are always capability-scoped (one tool = one capability)
        - Tools must declare their schema for structured invocation (Phase 5)
        - Tools are user-facing (users can enable/disable them in settings)
        - Plugins may include non-tool extensions (e.g. UI themes, model adapters)
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional


class ToolRegistry:
    """
    Discovers and dispatches tool executors.

    Phase 1: Delegates entirely to PluginLoader for backward compatibility.
             Adds a tool-oriented API on top.

    Usage:
        registry = ToolRegistry(plugin_loader)
        executor = registry.get_executor("python_execution", art_repo, setting_repo, workspace)
        tools = registry.list_tools()
    """

    def __init__(self, plugin_loader: Any) -> None:
        """
        Args:
            plugin_loader: A PluginLoader instance (from runtime.plugin_loader).
        """
        self._plugin_loader = plugin_loader

    # ── Discovery ───────────────────────────────────────────────────

    def list_tools(self) -> List[Dict[str, Any]]:
        """
        Return metadata for all registered tools.

        Returns dicts with keys: id, name, version, capability, source, enabled, loaded, schema, description.
        """
        manifests = self._plugin_loader.list_manifests()
        tools = []
        for m in manifests:
            if m.get("enabled", False):
                cap = m.get("capability")
                tool_data = dict(m)
                try:
                    tool_cls = self._plugin_loader.get_class(cap)
                    if tool_cls and hasattr(tool_cls, "get_schema"):
                        tool_data["schema"] = tool_cls.get_schema()
                        tool_data["description"] = tool_cls.description()
                except Exception:
                    pass
                tools.append(tool_data)
        return tools

    def list_all_tools(self) -> List[Dict[str, Any]]:
        """Return all tools including disabled ones (for admin/settings view)."""
        return self._plugin_loader.list_manifests()

    def is_available(self, capability: str) -> bool:
        """Return True if an enabled tool exists for the given capability."""
        return any(
            t.get("capability") == capability
            for t in self.list_tools()
        )

    def available_capabilities(self) -> List[str]:
        """Return list of capability strings that have an enabled tool."""
        return [
            t["capability"]
            for t in self.list_tools()
            if t.get("capability")
        ]

    # ── Dispatch ────────────────────────────────────────────────────

    def get_executor(self, capability: str, *factory_args: Any, **factory_kwargs: Any) -> Optional[Any]:
        """
        Return an executor instance for the given capability.

        Delegates to PluginLoader which handles lazy import + caching.
        Returns None if no enabled tool exists for the capability.

        Args:
            capability:    e.g. "python_execution", "filesystem", "browser"
            *factory_args: Passed to the executor constructor (repo, workspace, etc.)
        """
        return self._plugin_loader.get_executor(capability, *factory_args, **factory_kwargs)

    # ── Introspection ────────────────────────────────────────────────

    def __repr__(self) -> str:
        available = self.available_capabilities()
        return f"ToolRegistry({len(available)} tools: {available})"
