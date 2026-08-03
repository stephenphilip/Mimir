"""Document generation provider — PDF, DOCX, Markdown, TXT, CSV, XLSX."""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from ...creator.artifact_validator import ArtifactValidator
from ...creator.types import ArtifactRecord, GenerationRequest, GenerationResult, ValidationResult
from ...interfaces.capabilities import ICapabilityProvider
from .generators import (
    generate_csv,
    generate_docx,
    generate_markdown,
    generate_pdf,
    generate_txt,
    generate_xlsx,
    parse_tabular_content,
)


class DocumentProvider(ICapabilityProvider):
    """Generates document artifacts on disk. Registration is handled by Execution Engine."""

    SUPPORTED = {"pdf", "docx", "markdown", "md", "txt", "csv", "xlsx"}

    def __init__(self, validator: Optional[ArtifactValidator] = None):
        self._validator = validator

    @property
    def name(self) -> str:
        return "document"

    def supports(self, artifact_type: str) -> bool:
        return artifact_type.lower() in self.SUPPORTED

    def supported_types(self) -> List[str]:
        return sorted(self.SUPPORTED)

    def execute(self, request: GenerationRequest) -> GenerationResult:
        return self.generate(request)

    def generate(self, request: GenerationRequest) -> GenerationResult:
        artifact_type = request.artifact_type.lower()
        title = request.title or "Mimir Document"
        content = request.content or ""

        try:
            if artifact_type == "pdf":
                path = generate_pdf(title, content)
            elif artifact_type == "docx":
                path = generate_docx(title, content)
            elif artifact_type in {"markdown", "md"}:
                path = generate_markdown(title, content)
            elif artifact_type == "txt":
                path = generate_txt(title, content)
            elif artifact_type == "csv":
                rows = request.metadata.get("rows") or parse_tabular_content(content)
                path = generate_csv(title, rows)
            elif artifact_type == "xlsx":
                rows = request.metadata.get("rows") or parse_tabular_content(content)
                path = generate_xlsx(title, rows)
            else:
                return GenerationResult(success=False, error=f"Unsupported document type: {artifact_type}")

            return GenerationResult(
                success=True,
                stdout=f"Generated {path.name}",
                output_path=str(path),
            )
        except Exception as exc:
            return GenerationResult(success=False, error=str(exc), stderr=str(exc))

    def validate(self, file_path: str, artifact_type: str) -> ValidationResult:
        if self._validator is None:
            return ValidationResult(valid=False, errors=["Document validator not configured"])
        return self._validator.validate(file_path, artifact_type)

    def metadata(self, artifact: ArtifactRecord) -> Dict[str, Any]:
        return {
            "provider": self.name,
            "type": artifact.type,
            "size": artifact.size,
            "filename": artifact.filename,
        }
