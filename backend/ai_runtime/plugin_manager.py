"""
PluginManager — re-exports PluginLoader for backward compatibility.

Phase 1: PluginLoader in runtime/plugin_loader.py is the authoritative implementation.
         This module provides the canonical import path for future phases.
Phase 5: ToolRegistry (in tools/registry.py) will become the primary tool-discovery
         mechanism and PluginManager will coordinate between tool and agent plugins.
"""
from runtime.plugin_loader import PluginLoader, PluginManifest

# Canonical alias for the new architecture
PluginManager = PluginLoader

__all__ = ["PluginManager", "PluginLoader", "PluginManifest"]
