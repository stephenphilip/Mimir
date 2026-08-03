"""Structured Document Model — LLM produces content; renderers produce files."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


@dataclass
class DocumentSection:
    heading: str
    body: str = ""
    bullets: List[str] = field(default_factory=list)
    level: int = 1

    def to_dict(self) -> Dict[str, Any]:
        return {
            "heading": self.heading,
            "body": self.body,
            "bullets": self.bullets,
            "level": self.level,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "DocumentSection":
        return cls(
            heading=str(data.get("heading") or "Section"),
            body=str(data.get("body") or ""),
            bullets=[str(b) for b in (data.get("bullets") or [])],
            level=int(data.get("level") or 1),
        )


@dataclass
class StructuredDocument:
    """
    Platform-owned document representation.

    The LLM fills title/sections/summary. Renderers emit PDF/DOCX/MD/HTML.
    """

    title: str
    summary: str = ""
    sections: List[DocumentSection] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "title": self.title,
            "summary": self.summary,
            "sections": [s.to_dict() for s in self.sections],
            "metadata": self.metadata,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "StructuredDocument":
        sections = [DocumentSection.from_dict(s) for s in (data.get("sections") or [])]
        return cls(
            title=str(data.get("title") or "Untitled Document"),
            summary=str(data.get("summary") or ""),
            sections=sections,
            metadata=dict(data.get("metadata") or {}),
        )

    def plain_text(self) -> str:
        parts = [self.title, ""]
        if self.summary:
            parts.extend([self.summary, ""])
        for sec in self.sections:
            parts.append(sec.heading)
            if sec.body:
                parts.append(sec.body)
            for b in sec.bullets:
                parts.append(f"- {b}")
            parts.append("")
        return "\n".join(parts).strip()
