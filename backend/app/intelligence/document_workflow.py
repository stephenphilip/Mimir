"""Document Workflow — build → render → validate → register (no LLM PDF code)."""

from __future__ import annotations

from typing import Any, Dict, Optional

from ..creator.diagnostics import get_execution_diagnostics
from ..creator.types import GenerationRequest
from .document_builder import DocumentBuilder
from .document_renderer import DocumentRenderer


class DocumentWorkflow:
    """
    Executes the structured_document workflow plan.

    LLM provides knowledge (text/JSON). Platform owns rendering and registration.
    """

    def __init__(self, creator_engine=None):
        self._builder = DocumentBuilder()
        self._renderer = DocumentRenderer()
        self._creator_engine = creator_engine
        self._diag = get_execution_diagnostics()

    def execute(
        self,
        *,
        llm_content: str,
        user_prompt: str,
        artifact_type: str = "pdf",
        workspace_id: Optional[str] = None,
        message_id: Optional[int] = None,
        title_hint: Optional[str] = None,
        original_prompt: Optional[str] = None,
        enhanced_prompt: Optional[str] = None,
        execution_plan: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        self._diag.log("execution", "DocumentWorkflow: building structured document")
        doc = self._builder.build(
            llm_content,
            title_hint=title_hint or self._title_from_prompt(user_prompt),
            user_prompt=user_prompt,
        )

        fmt = (artifact_type or "pdf").lower()
        if fmt == "md":
            fmt = "markdown"

        self._diag.log("execution", f"DocumentWorkflow: rendering {fmt}", metadata={"title": doc.title})
        try:
            path = self._renderer.render(doc, format=fmt)
        except Exception as exc:
            self._diag.log("execution", f"Render failed: {exc}", level="error")
            return {
                "success": False,
                "stdout": "",
                "stderr": str(exc),
                "exit_code": 1,
                "artifacts": [],
                "structured_document": doc.to_dict(),
            }

        intelligence = {
            "original_prompt": original_prompt or user_prompt,
            "enhanced_prompt": enhanced_prompt,
            "execution_plan": execution_plan,
            "structured_document": doc.to_dict(),
            "provider": "document_renderer",
            "model": None,
            "validation_status": "pending",
        }

        if self._creator_engine is None:
            return {
                "success": True,
                "stdout": f"Rendered {path.name}",
                "stderr": "",
                "exit_code": 0,
                "artifacts": [],
                "output_path": str(path),
                "structured_document": doc.to_dict(),
            }

        req = GenerationRequest(
            artifact_type=fmt,
            title=doc.title,
            content=doc.plain_text(),
            workspace_id=workspace_id,
            message_id=message_id,
            provider_hint="document",
            metadata={
                "output_path": str(path),
                "intelligence": intelligence,
                "skip_provider_generate": True,
            },
        )

        # Register existing rendered file through validation gate
        result = self._creator_engine.register_existing_file(
            str(path),
            message_id=message_id,
            workspace_id=workspace_id,
            provider="document_renderer",
            artifact_type=fmt,
        )

        if result.success and result.artifact:
            # Attach intelligence metadata if engine supports it
            if hasattr(self._creator_engine, "_inner"):
                inner = self._creator_engine._inner
                if hasattr(inner, "_artifact_manager") and hasattr(
                    inner._artifact_manager, "attach_intelligence"
                ):
                    inner._artifact_manager.attach_intelligence(
                        result.artifact.artifact_id, intelligence
                    )
            intelligence["validation_status"] = "passed"
            self._diag.log("artifact", f"Document registered: {result.artifact.filename}")
            return {
                "success": True,
                "stdout": f"Generated {result.artifact.filename}",
                "stderr": "",
                "exit_code": 0,
                "artifacts": [result.artifact.to_dict()],
                "structured_document": doc.to_dict(),
                "execution_status": "completed",
            }

        err = result.error or "Registration failed"
        self._diag.log("artifact", err, level="error")
        return {
            "success": False,
            "stdout": "",
            "stderr": err,
            "exit_code": 1,
            "artifacts": [],
            "structured_document": doc.to_dict(),
        }

    def _title_from_prompt(self, prompt: str) -> str:
        p = (prompt or "").strip()
        # "Create a workout PDF" → "Workout"
        for prefix in ("create a ", "generate a ", "make a ", "build a ", "write a "):
            if p.lower().startswith(prefix):
                p = p[len(prefix) :]
                break
        for suffix in (" pdf", " document", " report", " docx", " markdown"):
            if p.lower().endswith(suffix):
                p = p[: -len(suffix)]
                break
        return (p.strip() or "Document")[:80]
