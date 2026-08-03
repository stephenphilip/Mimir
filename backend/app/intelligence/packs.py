"""Creator Packs — marketplace packs that register capabilities."""

from __future__ import annotations

import json
import threading
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

from config.paths import get_paths

from .capability_registry import CapabilityDefinition, CapabilityRegistry, get_capability_registry


@dataclass
class CreatorPack:
    id: str
    name: str
    developer: str
    version: str
    description: str
    category: str
    capabilities: List[str] = field(default_factory=list)
    featured: bool = False
    rating: float = 4.5
    installs: int = 0
    installed: bool = False
    has_update: bool = False

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "name": self.name,
            "developer": self.developer,
            "version": self.version,
            "description": self.description,
            "category": self.category,
            "capabilities": self.capabilities,
            "featured": self.featured,
            "rating": self.rating,
            "installs": self.installs,
            "installed": self.installed,
            "hasUpdate": self.has_update,
        }


# Pack definitions — installing registers these capability IDs
_PACK_CAPABILITY_DEFS: Dict[str, List[CapabilityDefinition]] = {
    "office-pack": [
        CapabilityDefinition(
            "office_templates",
            "Office Templates",
            "document",
            "Branded PDF/DOCX templates",
            provider_family="document",
            pack_id="office-pack",
        ),
        CapabilityDefinition(
            "presentation_basic",
            "Basic Presentations",
            "presentation",
            "Simple presentation outlines",
            pack_id="office-pack",
        ),
    ],
    "creative-pack": [
        CapabilityDefinition(
            "creative_styles",
            "Creative Styles",
            "image",
            "Style presets for image generation",
            provider_family="image",
            pack_id="creative-pack",
        ),
        CapabilityDefinition(
            "negative_prompt_library",
            "Negative Prompt Library",
            "image",
            "Curated negative prompts",
            provider_family="image",
            pack_id="creative-pack",
        ),
    ],
    "developer-pack": [
        CapabilityDefinition(
            "code_templates",
            "Code Templates",
            "python",
            "Scaffolding helpers for scripts",
            runtime="python",
            pack_id="developer-pack",
        ),
    ],
    "research-pack": [
        CapabilityDefinition(
            "research_citations",
            "Research Citations",
            "document",
            "Citation-aware document sections",
            provider_family="document",
            pack_id="research-pack",
        ),
        CapabilityDefinition(
            "vision_tables",
            "Vision Table Detection",
            "vision",
            "Enhanced table detection in scans",
            provider_family="vision",
            pack_id="research-pack",
        ),
    ],
}


class PackRegistry:
    """Catalog + install state for Creator Packs."""

    def __init__(self, capability_registry: Optional[CapabilityRegistry] = None):
        self._caps = capability_registry or get_capability_registry()
        self._lock = threading.Lock()
        self._catalog = self._default_catalog()
        self._state_path = get_paths().data_dir / "installed_packs.json"
        self._load_state()

    def _default_catalog(self) -> Dict[str, CreatorPack]:
        packs = [
            CreatorPack(
                id="office-pack",
                name="Office Pack",
                developer="Mimir Labs",
                version="1.0.0",
                description="Documents, DOCX templates, and presentation outlines.",
                category="Documents",
                capabilities=["office_templates", "presentation_basic", "document", "pdf", "docx"],
                featured=True,
                rating=4.8,
                installs=1240,
            ),
            CreatorPack(
                id="creative-pack",
                name="Creative Pack",
                developer="Pixel Studio",
                version="0.9.0",
                description="Image styles, negative prompts, and creative workflows.",
                category="Images",
                capabilities=["creative_styles", "negative_prompt_library", "image"],
                featured=True,
                rating=4.9,
                installs=2100,
                has_update=True,
            ),
            CreatorPack(
                id="developer-pack",
                name="Developer Pack",
                developer="DataForge",
                version="2.0.1",
                description="Python scaffolding and spreadsheet analyst helpers.",
                category="Developer",
                capabilities=["code_templates", "python", "spreadsheet"],
                featured=True,
                rating=4.6,
                installs=890,
            ),
            CreatorPack(
                id="research-pack",
                name="Research Pack",
                developer="Recall AI",
                version="1.0.0",
                description="Citations, OCR table detection, and research documents.",
                category="Research",
                capabilities=["research_citations", "vision_tables", "vision", "ocr"],
                rating=4.5,
                installs=670,
            ),
        ]
        return {p.id: p for p in packs}

    def list_packs(self) -> List[Dict[str, Any]]:
        with self._lock:
            return [p.to_dict() for p in self._catalog.values()]

    def install(self, pack_id: str) -> Dict[str, Any]:
        with self._lock:
            pack = self._catalog.get(pack_id)
            if not pack:
                raise KeyError(f"Unknown pack: {pack_id}")
            defs = _PACK_CAPABILITY_DEFS.get(pack_id, [])
            self._caps.register_pack_capabilities(pack_id, defs)
            self._caps.enable_pack(pack_id)
            pack.installed = True
            pack.installs += 1
            self._save_state()
            return pack.to_dict()

    def uninstall(self, pack_id: str) -> Dict[str, Any]:
        with self._lock:
            pack = self._catalog.get(pack_id)
            if not pack:
                raise KeyError(f"Unknown pack: {pack_id}")
            self._caps.disable_pack(pack_id)
            pack.installed = False
            self._save_state()
            return pack.to_dict()

    def _load_state(self) -> None:
        if not self._state_path.is_file():
            return
        try:
            data = json.loads(self._state_path.read_text(encoding="utf-8"))
            for pid in data.get("installed", []):
                if pid in self._catalog:
                    self._catalog[pid].installed = True
                    defs = _PACK_CAPABILITY_DEFS.get(pid, [])
                    self._caps.register_pack_capabilities(pid, defs)
                    self._caps.enable_pack(pid)
        except Exception:
            pass

    def _save_state(self) -> None:
        self._state_path.parent.mkdir(parents=True, exist_ok=True)
        installed = [p.id for p in self._catalog.values() if p.installed]
        self._state_path.write_text(json.dumps({"installed": installed}, indent=2), encoding="utf-8")


_packs: Optional[PackRegistry] = None
_packs_lock = threading.Lock()


def get_pack_registry() -> PackRegistry:
    global _packs
    with _packs_lock:
        if _packs is None:
            _packs = PackRegistry()
        return _packs
