"""Prompt Analyzer — light pre-routing analysis before Intent Engine."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


@dataclass
class PromptAnalysis:
    original: str
    normalized: str
    signals: List[str] = field(default_factory=list)
    suggested_artifact: Optional[str] = None
    suggested_capability: Optional[str] = None
    is_generation: bool = False
    is_vision: bool = False
    is_image_gen: bool = False

    def to_dict(self) -> Dict[str, Any]:
        return {
            "original": self.original,
            "normalized": self.normalized,
            "signals": self.signals,
            "suggested_artifact": self.suggested_artifact,
            "suggested_capability": self.suggested_capability,
            "is_generation": self.is_generation,
            "is_vision": self.is_vision,
            "is_image_gen": self.is_image_gen,
        }


class PromptAnalyzer:
    """Heuristic analyzer — feeds Intent Engine and Execution Planner."""

    _GEN = re.compile(r"\b(create|generate|make|build|write|produce|render)\b", re.I)
    _PDF = re.compile(r"\b(pdf|document|report|workout|plan)\b", re.I)
    _XLSX = re.compile(r"\b(excel|spreadsheet|xlsx|csv|table)\b", re.I)
    _IMG = re.compile(r"\b(image|picture|photo|illustration|draw|generate an? image)\b", re.I)
    _VISION = re.compile(r"\b(ocr|read this|what.?s in|describe (this|the) (image|screenshot|photo)|scan)\b", re.I)
    _CODE = re.compile(r"\b(python|script|code|function|program)\b", re.I)
    _CHART = re.compile(r"\b(chart|plot|graph|visualize)\b", re.I)

    def analyze(self, prompt: str) -> PromptAnalysis:
        text = (prompt or "").strip()
        norm = text.lower()
        signals: List[str] = []
        artifact: Optional[str] = None
        capability: Optional[str] = None
        is_gen = bool(self._GEN.search(norm))
        is_vision = bool(self._VISION.search(norm))
        is_image = bool(self._IMG.search(norm)) and is_gen

        if self._PDF.search(norm) and is_gen:
            signals.append("document")
            artifact = "pdf"
            capability = "document"
        elif self._XLSX.search(norm) and is_gen:
            signals.append("spreadsheet")
            artifact = "xlsx"
            capability = "spreadsheet"
        elif self._CHART.search(norm):
            signals.append("chart")
            artifact = "png"
            capability = "chart"
        elif is_image:
            signals.append("image")
            artifact = "png"
            capability = "image"
        elif self._CODE.search(norm):
            signals.append("python")
            capability = "python"
        elif is_vision:
            signals.append("vision")
            capability = "vision"

        if is_gen:
            signals.append("generation")

        return PromptAnalysis(
            original=text,
            normalized=norm,
            signals=signals,
            suggested_artifact=artifact,
            suggested_capability=capability,
            is_generation=is_gen,
            is_vision=is_vision,
            is_image_gen=is_image,
        )
