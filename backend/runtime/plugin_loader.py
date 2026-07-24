"""
Lightweight plugin manifest loader.

Reads plugin.json metadata without importing plugin code.
Code is imported only on first use (lazy loading).
"""

from __future__ import annotations

import importlib
import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional


@dataclass
class PluginManifest:
    id: str
    name: str
    version: str = "0.0.0"
    capability: str = ""
    entry: str = "main"
    source: str = "builtin"
    path: Optional[str] = None
    enabled: bool = True


# Built-in capability → import path (code NOT imported until first use)
_BUILTIN_MANIFESTS: List[Dict[str, Any]] = [
    {
        "id": "python",
        "name": "Python Executor",
        "version": "1.0.0",
        "capability": "python_execution",
        "entry": "tools.python_tool:PythonTool",
        "source": "builtin",
        "enabled": True,
    },
    {
        "id": "excel",
        "name": "Excel (stub)",
        "version": "0.0.0",
        "capability": "excel_generation",
        "entry": "app.extensions.excel:ExcelExecutor",
        "source": "builtin",
        "enabled": False,
    },
    {
        "id": "filesystem",
        "name": "Filesystem (stub)",
        "version": "0.0.0",
        "capability": "filesystem",
        "entry": "app.extensions.filesystem:FilesystemExecutor",
        "source": "builtin",
        "enabled": False,
    },
]


@dataclass
class PluginLoader:
    """Manifest metadata at startup; import on first execute."""

    extensions_dir: Path
    manifests: List[PluginManifest] = field(default_factory=list)
    _instances: Dict[str, Any] = field(default_factory=dict)

    def load_manifests(self) -> List[PluginManifest]:
        """Load JSON/builtin manifests only — no plugin code imports."""
        found: List[PluginManifest] = []

        for raw in _BUILTIN_MANIFESTS:
            found.append(PluginManifest(**raw))

        if self.extensions_dir.is_dir():
            for plugin_json in sorted(self.extensions_dir.glob("*/plugin.json")):
                try:
                    data = json.loads(plugin_json.read_text(encoding="utf-8"))
                    found.append(
                        PluginManifest(
                            id=data.get("id", plugin_json.parent.name),
                            name=data.get("name", plugin_json.parent.name),
                            version=data.get("version", "0.0.0"),
                            capability=data.get("capability", ""),
                            entry=data.get("entry", "main"),
                            source="extension",
                            path=str(plugin_json.parent),
                            enabled=bool(data.get("enabled", True)),
                        )
                    )
                except Exception:
                    continue

        self.manifests = found
        return found

    def list_manifests(self) -> List[Dict[str, Any]]:
        return [
            {
                "id": m.id,
                "name": m.name,
                "version": m.version,
                "capability": m.capability,
                "source": m.source,
                "enabled": m.enabled,
                "loaded": m.id in self._instances,
            }
            for m in self.manifests
        ]

    def get_executor(self, capability: str, *factory_args, **factory_kwargs) -> Any:
        """
        Return an executor for capability, importing its module on first use.
        """
        manifest = next(
            (m for m in self.manifests if m.capability == capability and m.enabled),
            None,
        )
        if not manifest:
            return None

        if manifest.id in self._instances:
            return self._instances[manifest.id]

        instance = self._import_and_construct(manifest, *factory_args, **factory_kwargs)
        if instance is not None:
            self._instances[manifest.id] = instance
        return instance

    def get_class(self, capability: str) -> Optional[Any]:
        """
        Return the executor class for capability, importing its module on first use,
        but without instantiating it.
        """
        manifest = next(
            (m for m in self.manifests if m.capability == capability and m.enabled),
            None,
        )
        if not manifest:
            return None
        
        entry = manifest.entry
        if ":" not in entry:
            return None
        module_path, attr = entry.split(":", 1)
        module = importlib.import_module(module_path)
        return getattr(module, attr)

    def _import_and_construct(self, manifest: PluginManifest, *args, **kwargs) -> Any:
        entry = manifest.entry
        if ":" not in entry:
            return None
        module_path, attr = entry.split(":", 1)
        module = importlib.import_module(module_path)
        cls = getattr(module, attr)
        return cls(*args, **kwargs)
