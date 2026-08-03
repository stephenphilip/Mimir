"""MIME type and extension helpers for artifacts."""

from __future__ import annotations

from pathlib import Path
from typing import Optional

MIME_BY_EXT = {
    "pdf": "application/pdf",
    "docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    "xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    "csv": "text/csv",
    "md": "text/markdown",
    "markdown": "text/markdown",
    "txt": "text/plain",
    "png": "image/png",
    "jpg": "image/jpeg",
    "jpeg": "image/jpeg",
    "webp": "image/webp",
    "pptx": "application/vnd.openxmlformats-officedocument.presentationml.presentation",
    "html": "text/html",
    "zip": "application/zip",
}

EXT_BY_TYPE = {
    "pdf": "pdf",
    "docx": "docx",
    "xlsx": "xlsx",
    "csv": "csv",
    "markdown": "md",
    "txt": "txt",
    "image": "png",
    "pptx": "pptx",
    "html": "html",
}


def infer_type_from_filename(filename: str) -> str:
    ext = Path(filename).suffix.lower().lstrip(".")
    if ext == "md":
        return "markdown"
    return ext or "bin"


def mime_for_type(artifact_type: str) -> str:
    key = artifact_type.lower()
    if key == "markdown":
        key = "md"
    return MIME_BY_EXT.get(key, "application/octet-stream")


def mime_for_filename(filename: str) -> str:
    return mime_for_type(infer_type_from_filename(filename))


def guess_mime(filename: str) -> str:
    """Alias used by ArtifactValidator."""
    return mime_for_filename(filename)


def category_for_type(artifact_type: str) -> str:
    t = artifact_type.lower()
    if t in {"png", "jpg", "jpeg", "webp", "image"}:
        return "image"
    if t in {"xlsx", "xls", "csv"}:
        return "spreadsheet"
    if t in {"pdf", "docx", "txt", "markdown", "md", "pptx", "html"}:
        return "document"
    return "other"
