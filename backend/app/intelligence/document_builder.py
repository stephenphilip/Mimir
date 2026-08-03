"""Document Builder — parse LLM output into StructuredDocument."""

from __future__ import annotations

import json
import re
from typing import Any, Dict, Optional

from .document_model import DocumentSection, StructuredDocument


class DocumentBuilder:
    """
    Converts LLM knowledge into a StructuredDocument.

    Prefer JSON from the model; fall back to markdown/plain-text heuristics.
    Never generates files — that is DocumentRenderer's job.
    """

    def build(
        self,
        content: str,
        *,
        title_hint: Optional[str] = None,
        user_prompt: Optional[str] = None,
    ) -> StructuredDocument:
        parsed = self._try_json(content)
        if parsed:
            doc = StructuredDocument.from_dict(parsed)
            if title_hint and (not doc.title or doc.title == "Untitled Document"):
                doc.title = title_hint
            return doc

        return self._from_text(content, title_hint=title_hint, user_prompt=user_prompt)

    def _try_json(self, text: str) -> Optional[Dict[str, Any]]:
        text = (text or "").strip()
        if not text:
            return None
        # Strip markdown fences
        fence = re.search(r"```(?:json)?\s*([\s\S]*?)```", text)
        if fence:
            text = fence.group(1).strip()
        try:
            data = json.loads(text)
            if isinstance(data, dict) and ("title" in data or "sections" in data):
                return data
        except json.JSONDecodeError:
            match = re.search(r"\{[\s\S]*\}", text)
            if match:
                try:
                    data = json.loads(match.group(0))
                    if isinstance(data, dict) and ("title" in data or "sections" in data):
                        return data
                except json.JSONDecodeError:
                    return None
        return None

    def _from_text(
        self,
        content: str,
        *,
        title_hint: Optional[str] = None,
        user_prompt: Optional[str] = None,
    ) -> StructuredDocument:
        lines = [ln.rstrip() for ln in (content or "").splitlines()]
        title = title_hint or "Document"
        # Prefer first markdown H1
        for ln in lines:
            if ln.startswith("# "):
                title = ln[2:].strip() or title
                break
        if title == "Document" and user_prompt:
            title = user_prompt.strip()[:80] or title

        sections: list[DocumentSection] = []
        current: Optional[DocumentSection] = None
        body_buf: list[str] = []
        bullets: list[str] = []

        def flush():
            nonlocal current, body_buf, bullets
            if current is None and (body_buf or bullets):
                current = DocumentSection(heading="Content", body="", bullets=[])
            if current is not None:
                current.body = "\n".join(body_buf).strip()
                current.bullets = list(bullets)
                sections.append(current)
            current = None
            body_buf = []
            bullets = []

        for ln in lines:
            if ln.startswith("#"):
                flush()
                level = len(ln) - len(ln.lstrip("#"))
                heading = ln.lstrip("#").strip() or "Section"
                current = DocumentSection(heading=heading, level=min(level, 3))
            elif re.match(r"^[-*•]\s+", ln):
                bullets.append(re.sub(r"^[-*•]\s+", "", ln).strip())
            elif ln.strip():
                body_buf.append(ln.strip())

        flush()

        if not sections:
            # Strip code blocks that look like python — use as body summary
            cleaned = re.sub(r"```[\s\S]*?```", "", content).strip()
            sections = [
                DocumentSection(
                    heading="Overview",
                    body=cleaned[:4000] or (user_prompt or "Generated document"),
                )
            ]

        return StructuredDocument(title=title, summary="", sections=sections)
