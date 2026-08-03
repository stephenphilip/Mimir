"""Vision Service — OCR, caption, objects, scene, metadata, layout, tables."""

from __future__ import annotations

import base64
import io
import json
from pathlib import Path
from typing import Any, Dict, List, Optional

import requests

from config.settings import get_settings

from ..creator.diagnostics import get_execution_diagnostics


SUPPORTED_IMAGE_EXT = {".png", ".jpg", ".jpeg", ".webp"}


class VisionService:
    """
    Pipeline: upload → OCR → caption → objects/scene → metadata → layout/tables → context.

    Lazy: optional Tesseract for OCR; Ollama vision for caption/scene when available.
    """

    def __init__(self, ollama_url: Optional[str] = None):
        settings = get_settings()
        self._ollama_url = (ollama_url or settings.ollama_url).rstrip("/")
        self._diag = get_execution_diagnostics()

    def analyze_file(self, file_path: str, mime_type: Optional[str] = None) -> Dict[str, Any]:
        path = Path(file_path)
        if not path.is_file():
            return {"success": False, "error": f"File not found: {file_path}"}

        ext = path.suffix.lower()
        self._diag.log("execution", f"Vision analyze: {path.name}", metadata={"ext": ext})

        if ext not in SUPPORTED_IMAGE_EXT and not (mime_type or "").startswith("image/"):
            if ext == ".pdf":
                return self._analyze_pdf(path)
            return {"success": False, "error": f"Unsupported vision input: {ext}"}

        return self._analyze_image(path)

    def _analyze_image(self, path: Path) -> Dict[str, Any]:
        metadata: Dict[str, Any] = {"filename": path.name, "format": path.suffix.lstrip(".")}
        layout: Dict[str, Any] = {}
        objects: List[str] = []
        scene = ""
        tables: List[Any] = []

        try:
            from PIL import Image

            with Image.open(path) as img:
                metadata.update({
                    "width": img.width,
                    "height": img.height,
                    "mode": img.mode,
                    "format_detail": img.format,
                })
                layout = {
                    "aspect_ratio": round(img.width / img.height, 3) if img.height else None,
                    "orientation": "landscape" if img.width >= img.height else "portrait",
                    "megapixels": round((img.width * img.height) / 1_000_000, 2),
                }
        except Exception as exc:
            metadata["decode_error"] = str(exc)

        ocr_text = self._run_ocr(path)
        caption = self._run_caption(path)
        scene = self._run_scene(path) or caption
        objects = self._infer_objects(caption, ocr_text, scene)
        tables = self._detect_tables_from_ocr(ocr_text)

        context_block = self.build_context_block(
            caption=caption,
            ocr_text=ocr_text,
            metadata=metadata,
            objects=objects,
            scene=scene,
            layout=layout,
            tables=tables,
        )
        result = {
            "success": True,
            "ocr": ocr_text,
            "caption": caption,
            "objects": objects,
            "scene": scene,
            "metadata": metadata,
            "layout": layout,
            "tables": tables,
            "context": context_block,
        }
        self._diag.log("execution", "Vision analysis complete", metadata={"has_ocr": bool(ocr_text)})
        return result

    def _analyze_pdf(self, path: Path) -> Dict[str, Any]:
        text = ""
        try:
            from pypdf import PdfReader  # type: ignore

            reader = PdfReader(str(path))
            chunks = []
            for page in reader.pages[:5]:
                page_text = page.extract_text() or ""
                page_text = page_text.strip()
                
                # Scanned PDF check: if native text is empty/poor and there are embedded images, run OCR
                if len(page_text) < 20 and page.images:
                    ocr_chunks = []
                    try:
                        import pytesseract
                        from PIL import Image
                        import io
                        
                        for img_obj in page.images:
                            try:
                                img_data = img_obj.data
                                pil_img = Image.open(io.BytesIO(img_data))
                                ocr_result = pytesseract.image_to_string(pil_img) or ""
                                if ocr_result.strip():
                                    ocr_chunks.append(ocr_result.strip())
                            except Exception as e:
                                print(f"Error OCR-ing page image: {e}")
                    except ImportError:
                        pass
                    
                    if ocr_chunks:
                        page_text = "\n".join(ocr_chunks)
                
                chunks.append(page_text)
            text = "\n".join(chunks).strip()
        except Exception as exc:
            return {"success": False, "error": f"PDF vision failed: {exc}"}

        tables = self._detect_tables_from_ocr(text)
        metadata = {"filename": path.name, "type": "pdf", "pages_sampled": min(5, 1)}
        context_block = self.build_context_block(
            caption="Scanned/PDF document",
            ocr_text=text,
            metadata=metadata,
            objects=[],
            scene="document",
            layout={},
            tables=tables,
        )
        return {
            "success": True,
            "ocr": text,
            "caption": "Scanned/PDF document",
            "objects": [],
            "scene": "document",
            "metadata": metadata,
            "layout": {},
            "tables": tables,
            "context": context_block,
        }

    def _run_ocr(self, path: Path) -> str:
        try:
            import pytesseract  # type: ignore
            from PIL import Image

            with Image.open(path) as img:
                return (pytesseract.image_to_string(img) or "").strip()
        except ImportError:
            return ""
        except Exception:
            return ""

    def _encode_jpeg_b64(self, path: Path) -> Optional[str]:
        try:
            from PIL import Image

            with Image.open(path) as img:
                if img.mode not in ("RGB",):
                    img = img.convert("RGB")
                buf = io.BytesIO()
                img.save(buf, format="JPEG", quality=85)
                return base64.b64encode(buf.getvalue()).decode("ascii")
        except Exception:
            return None

    def _ollama_vision(self, path: Path, prompt: str, model: str = "llava:latest") -> str:
        b64 = self._encode_jpeg_b64(path)
        if not b64:
            return ""
        try:
            resp = requests.post(
                f"{self._ollama_url}/api/generate",
                json={
                    "model": model,
                    "prompt": prompt,
                    "images": [b64],
                    "stream": False,
                    "options": {"num_predict": 160},
                },
                timeout=(5, 60),
            )
            if resp.status_code != 200:
                return ""
            return (resp.json().get("response") or "").strip()
        except Exception:
            return ""

    def _run_caption(self, path: Path) -> str:
        return self._ollama_vision(
            path,
            "Describe this image in one or two sentences for an AI assistant.",
        )

    def _run_scene(self, path: Path) -> str:
        return self._ollama_vision(
            path,
            "Describe the scene type (e.g. screenshot, photo, diagram, chart, document) "
            "and main visual elements in one short sentence.",
        )

    def _infer_objects(self, caption: str, ocr: str, scene: str) -> List[str]:
        blob = f"{caption} {scene} {ocr[:500]}".lower()
        candidates = [
            "person", "people", "text", "table", "chart", "graph", "logo", "button",
            "screenshot", "document", "icon", "window", "menu", "car", "building",
            "animal", "code", "diagram",
        ]
        return [c for c in candidates if c in blob][:12]

    def _detect_tables_from_ocr(self, ocr_text: str) -> List[Dict[str, Any]]:
        """Heuristic table detection from OCR/PDF text (pipe or tab aligned rows)."""
        if not ocr_text:
            return []
        tables = []
        rows = []
        for line in ocr_text.splitlines():
            if "|" in line and line.count("|") >= 2:
                cells = [c.strip() for c in line.strip("|").split("|")]
                if cells:
                    rows.append(cells)
            elif "\t" in line:
                cells = [c.strip() for c in line.split("\t") if c.strip()]
                if len(cells) >= 2:
                    rows.append(cells)
        if rows:
            tables.append({"rows": rows[:30], "source": "ocr_heuristic"})
        return tables

    def build_context_block(
        self,
        *,
        caption: str,
        ocr_text: str,
        metadata: Dict[str, Any],
        objects: Optional[List[str]] = None,
        scene: str = "",
        layout: Optional[Dict[str, Any]] = None,
        tables: Optional[List[Any]] = None,
    ) -> str:
        parts = ["[Vision context]"]
        if caption:
            parts.append(f"Caption: {caption}")
        if scene:
            parts.append(f"Scene: {scene}")
        if objects:
            parts.append(f"Objects: {', '.join(objects)}")
        if ocr_text:
            parts.append(f"OCR/text: {ocr_text[:2000]}")
        if layout:
            parts.append(f"Layout: {json.dumps(layout, default=str)}")
        if tables:
            parts.append(f"Tables detected: {len(tables)}")
        if metadata:
            parts.append(f"Metadata: {json.dumps(metadata, default=str)}")
        return "\n".join(parts)
