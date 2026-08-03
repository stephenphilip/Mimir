"""Capability Registry — registry-driven capability routing (Intelligence Layer).

Architectural decision: CapabilityService resolves intents through this registry
instead of hardcoded maps. Creator Packs register additional capabilities here.
Providers stay lazy — the registry only stores metadata and factory hooks.
"""

from __future__ import annotations

import threading
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional, Set


@dataclass
class CapabilityDefinition:
    """A platform capability that can be required by intents / packs."""

    id: str
    name: str
    category: str  # chat | document | image | spreadsheet | presentation | vision | ocr | python | pack
    description: str = ""
    packages: List[str] = field(default_factory=list)
    runtime: Optional[str] = None  # python | none
    provider_family: Optional[str] = None  # document | image | vision | None
    lazy_loader: Optional[Callable[[], Any]] = None
    enabled: bool = True
    pack_id: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "name": self.name,
            "category": self.category,
            "description": self.description,
            "packages": self.packages,
            "runtime": self.runtime,
            "provider_family": self.provider_family,
            "enabled": self.enabled,
            "pack_id": self.pack_id,
        }


@dataclass
class IntentBinding:
    """Maps an intent to required capability IDs."""

    intent: str
    capability_ids: List[str]
    preferred_artifact: Optional[str] = None
    workflow: str = "chat"  # chat | structured_document | image | python | vision


class CapabilityRegistry:
    """
    Process-wide registry of capabilities and intent bindings.

    Never hardcode capability checks in services — always ask the registry.
    """

    def __init__(self) -> None:
        self._capabilities: Dict[str, CapabilityDefinition] = {}
        self._intent_bindings: Dict[str, IntentBinding] = {}
        self._lock = threading.RLock()
        self._bootstrap_defaults()

    def register(self, capability: CapabilityDefinition) -> None:
        with self._lock:
            self._capabilities[capability.id] = capability

    def register_intent(self, binding: IntentBinding) -> None:
        with self._lock:
            self._intent_bindings[binding.intent] = binding

    def get(self, capability_id: str) -> Optional[CapabilityDefinition]:
        with self._lock:
            return self._capabilities.get(capability_id)

    def has(self, capability_id: str) -> bool:
        with self._lock:
            cap = self._capabilities.get(capability_id)
            return bool(cap and cap.enabled)

    def list_capabilities(self, *, enabled_only: bool = True) -> List[CapabilityDefinition]:
        with self._lock:
            caps = list(self._capabilities.values())
        if enabled_only:
            caps = [c for c in caps if c.enabled]
        return sorted(caps, key=lambda c: (c.category, c.id))

    def resolve_for_intent(self, intent: str) -> List[str]:
        with self._lock:
            binding = self._intent_bindings.get(intent)
            if not binding:
                return ["chat"]
            return [
                cid
                for cid in binding.capability_ids
                if self.has(cid) or cid in self._capabilities
            ]

    def get_intent_binding(self, intent: str) -> Optional[IntentBinding]:
        with self._lock:
            return self._intent_bindings.get(intent)

    def workflow_for_intent(self, intent: str) -> str:
        binding = self.get_intent_binding(intent)
        return binding.workflow if binding else "chat"

    def preferred_artifact_for_intent(self, intent: str) -> Optional[str]:
        binding = self.get_intent_binding(intent)
        return binding.preferred_artifact if binding else None

    def get_execution_requirements(self, capability_ids: List[str]) -> Dict[str, Any]:
        packages: Set[str] = set()
        runtime: Optional[str] = None
        for cid in capability_ids:
            cap = self.get(cid)
            if not cap:
                continue
            packages.update(cap.packages)
            if cap.runtime == "python":
                runtime = "python"
        return {"runtime": runtime, "packages": sorted(packages)}

    def register_pack_capabilities(self, pack_id: str, capabilities: List[CapabilityDefinition]) -> None:
        for cap in capabilities:
            cap.pack_id = pack_id
            self.register(cap)

    def disable_pack(self, pack_id: str) -> None:
        with self._lock:
            for cap in self._capabilities.values():
                if cap.pack_id == pack_id:
                    cap.enabled = False

    def enable_pack(self, pack_id: str) -> None:
        with self._lock:
            for cap in self._capabilities.values():
                if cap.pack_id == pack_id:
                    cap.enabled = True

    def load_provider(self, capability_id: str) -> Any:
        """Lazy-load a provider only when the capability is required."""
        cap = self.get(capability_id)
        if not cap or not cap.lazy_loader:
            return None
        return cap.lazy_loader()

    def _bootstrap_defaults(self) -> None:
        defaults = [
            CapabilityDefinition("chat", "Chat", "chat", "Conversational reasoning"),
            CapabilityDefinition("document", "Document", "document", "Structured document generation", provider_family="document"),
            CapabilityDefinition("pdf", "PDF", "document", "PDF rendering", packages=["fpdf"], provider_family="document"),
            CapabilityDefinition("docx", "DOCX", "document", "Word document rendering", packages=["python-docx"], provider_family="document"),
            CapabilityDefinition("markdown", "Markdown", "document", "Markdown rendering", provider_family="document"),
            CapabilityDefinition("html", "HTML", "document", "HTML rendering", provider_family="document"),
            CapabilityDefinition("image", "Image Generation", "image", "Image generation via provider registry", provider_family="image"),
            CapabilityDefinition("spreadsheet", "Spreadsheet", "spreadsheet", "Excel/CSV generation", packages=["pandas", "openpyxl"], runtime="python"),
            CapabilityDefinition("presentation", "Presentation", "presentation", "Presentation generation (future)"),
            CapabilityDefinition("vision", "Vision", "vision", "Image understanding", provider_family="vision"),
            CapabilityDefinition("ocr", "OCR", "ocr", "Optical character recognition"),
            CapabilityDefinition("python", "Python Execution", "python", "Execute Python code", runtime="python"),
            CapabilityDefinition("chart", "Charts", "spreadsheet", "Data visualization", packages=["matplotlib", "seaborn", "pandas"], runtime="python"),
            # Legacy aliases used by existing orchestrator / tests
            CapabilityDefinition("reasoning", "Reasoning", "chat", "General reasoning"),
            CapabilityDefinition("python_execution", "Python Execution (legacy)", "python", "Legacy alias for python", runtime="python"),
            CapabilityDefinition("pdf_generation", "PDF Generation (legacy)", "document", "Legacy alias", packages=["fpdf"], provider_family="document"),
            CapabilityDefinition("excel_generation", "Excel Generation (legacy)", "spreadsheet", "Legacy alias", packages=["pandas", "openpyxl"], runtime="python"),
            CapabilityDefinition("chart_generation", "Chart Generation (legacy)", "spreadsheet", "Legacy alias", packages=["matplotlib", "seaborn", "pandas"], runtime="python"),
            CapabilityDefinition("coding", "Coding", "python", "Code generation support"),
            CapabilityDefinition("translation", "Translation", "chat", "Language translation"),
            CapabilityDefinition("text_processing", "Text Processing", "chat", "Writing and summarization"),
        ]
        for cap in defaults:
            self._capabilities[cap.id] = cap

        bindings = [
            IntentBinding("document_generation", ["reasoning", "document", "pdf"], preferred_artifact="pdf", workflow="structured_document"),
            IntentBinding("spreadsheet_generation", ["reasoning", "python_execution", "excel_generation", "spreadsheet"], preferred_artifact="xlsx", workflow="python"),
            IntentBinding("data_visualization", ["reasoning", "python_execution", "chart_generation", "chart"], preferred_artifact="png", workflow="python"),
            IntentBinding("code_generation", ["reasoning", "coding", "python_execution", "python"], workflow="python"),
            IntentBinding("image_generation", ["reasoning", "image"], preferred_artifact="png", workflow="image"),
            IntentBinding("vision_analysis", ["reasoning", "vision", "ocr"], workflow="vision"),
            IntentBinding("translation", ["reasoning", "translation"], workflow="chat"),
            IntentBinding("writing", ["reasoning", "text_processing"], workflow="chat"),
            IntentBinding("general_reasoning", ["reasoning", "chat"], workflow="chat"),
        ]
        for b in bindings:
            self._intent_bindings[b.intent] = b


_registry: Optional[CapabilityRegistry] = None
_reg_lock = threading.Lock()


def get_capability_registry() -> CapabilityRegistry:
    global _registry
    with _reg_lock:
        if _registry is None:
            _registry = CapabilityRegistry()
        return _registry
