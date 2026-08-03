"""Image generation provider interface and adapters."""

from __future__ import annotations

import base64
import json
import time
import uuid
from abc import abstractmethod
from pathlib import Path
from typing import Any, Dict, List, Optional

import requests

from config.paths import get_paths
from config.settings import get_settings

from ...creator.artifact_validator import ArtifactValidator
from ...creator.types import ArtifactRecord, GenerationRequest, GenerationResult, ValidationResult
from ...interfaces.capabilities import ICapabilityProvider
from ...interfaces.creators import ICreatorProvider


class IImageProvider(ICreatorProvider, ICapabilityProvider):
    """Image-specific provider contract."""

    @property
    @abstractmethod
    def provider_id(self) -> str:
        pass

    @abstractmethod
    def is_configured(self) -> bool:
        pass


class _BaseImageAdapter(IImageProvider):
    """Shared image provider skeleton."""

    def __init__(self, validator: Optional[ArtifactValidator] = None):
        self._validator = validator

    def supports(self, artifact_type: str) -> bool:
        return artifact_type.lower() in {"image", "png", "jpg", "jpeg", "webp"}

    @property
    def name(self) -> str:
        return self.provider_id

    def execute(self, request: GenerationRequest) -> GenerationResult:
        return self.generate(request)

    def generate(self, request: GenerationRequest) -> GenerationResult:
        if not self.is_configured():
            return GenerationResult(
                success=False,
                error=f"{self.provider_id} is not configured. Set API keys or URL in settings.",
            )
        return self._generate_image(request)

    @abstractmethod
    def _generate_image(self, request: GenerationRequest) -> GenerationResult:
        pass

    def validate(self, file_path: str, artifact_type: str) -> ValidationResult:
        if self._validator is None:
            return ValidationResult(valid=False, errors=["Image validator not configured"])
        return self._validator.validate(file_path, artifact_type)

    def metadata(self, artifact: ArtifactRecord) -> Dict[str, Any]:
        return {"provider": self.provider_id, "type": "image", "size": artifact.size}


def _save_image_bytes(data: bytes, ext: str = "png") -> Path:
    out_dir = get_paths().artifacts_dir
    out_dir.mkdir(parents=True, exist_ok=True)
    filename = f"image_{uuid.uuid4().hex[:10]}.{ext}"
    path = out_dir / filename
    path.write_bytes(data)
    return path


class OpenAIImageProvider(_BaseImageAdapter):
    provider_id = "openai"

    def __init__(self, api_key: Optional[str] = None, validator: Optional[ArtifactValidator] = None):
        super().__init__(validator=validator)
        self._api_key = api_key

    def is_configured(self) -> bool:
        return bool(self._api_key)

    def _generate_image(self, request: GenerationRequest) -> GenerationResult:
        prompt = request.content or request.title or "A detailed illustration"
        model = request.metadata.get("model", "dall-e-3")
        size = request.metadata.get("size", "1024x1024")
        try:
            resp = requests.post(
                "https://api.openai.com/v1/images/generations",
                headers={
                    "Authorization": f"Bearer {self._api_key}",
                    "Content-Type": "application/json",
                },
                json={
                    "model": model,
                    "prompt": prompt[:4000],
                    "n": 1,
                    "size": size,
                    "response_format": "b64_json",
                },
                timeout=120,
            )
            resp.raise_for_status()
            payload = resp.json()
            b64 = payload["data"][0]["b64_json"]
            path = _save_image_bytes(base64.b64decode(b64), ext="png")
            return GenerationResult(
                success=True,
                stdout=f"OpenAI image saved to {path.name}",
                output_path=str(path),
            )
        except Exception as exc:
            detail = str(exc)
            if hasattr(exc, "response") and getattr(exc, "response", None) is not None:
                try:
                    detail = exc.response.text  # type: ignore[union-attr]
                except Exception:
                    pass
            return GenerationResult(success=False, error=detail, stderr=detail)


class GeminiImageProvider(_BaseImageAdapter):
    provider_id = "gemini"

    def __init__(self, api_key: Optional[str] = None, validator: Optional[ArtifactValidator] = None):
        super().__init__(validator=validator)
        self._api_key = api_key

    def is_configured(self) -> bool:
        return bool(self._api_key)

    def _generate_image(self, request: GenerationRequest) -> GenerationResult:
        prompt = request.content or request.title or "A detailed illustration"
        # Use Prompt Studio image fields if present
        neg = request.metadata.get("negative_prompt") or ""
        if neg:
            prompt = f"{prompt}. Avoid: {neg}"
        model_name = request.metadata.get("model", "gemini-2.0-flash-preview-image-generation")
        try:
            url = (
                f"https://generativelanguage.googleapis.com/v1beta/models/"
                f"{model_name}:generateContent?key={self._api_key}"
            )
            resp = requests.post(
                url,
                json={
                    "contents": [{"parts": [{"text": prompt[:4000]}]}],
                    "generationConfig": {"responseModalities": ["TEXT", "IMAGE"]},
                },
                timeout=120,
            )
            resp.raise_for_status()
            payload = resp.json()
            # Walk candidates for inline image data
            for cand in payload.get("candidates", []):
                for part in cand.get("content", {}).get("parts", []):
                    inline = part.get("inlineData") or part.get("inline_data")
                    if inline and inline.get("data"):
                        ext = "png"
                        mime = inline.get("mimeType") or inline.get("mime_type") or "image/png"
                        if "jpeg" in mime or "jpg" in mime:
                            ext = "jpg"
                        path = _save_image_bytes(base64.b64decode(inline["data"]), ext=ext)
                        return GenerationResult(
                            success=True,
                            stdout=f"Gemini image saved to {path.name}",
                            output_path=str(path),
                        )
            return GenerationResult(
                success=False,
                error="Gemini response contained no image data. Check model support for image generation.",
            )
        except Exception as exc:
            detail = str(exc)
            return GenerationResult(success=False, error=detail, stderr=detail)


class StabilityImageProvider(_BaseImageAdapter):
    provider_id = "stability"

    def __init__(self, api_key: Optional[str] = None, validator: Optional[ArtifactValidator] = None):
        super().__init__(validator=validator)
        self._api_key = api_key

    def is_configured(self) -> bool:
        return bool(self._api_key)

    def _generate_image(self, request: GenerationRequest) -> GenerationResult:
        return GenerationResult(success=False, error="Stability AI image generation not yet wired")


class ComfyUIImageProvider(_BaseImageAdapter):
    provider_id = "comfyui"

    def __init__(self, base_url: str = "http://127.0.0.1:8188", validator: Optional[ArtifactValidator] = None):
        super().__init__(validator=validator)
        self._base_url = base_url.rstrip("/")
        self._checkpoint_cache: Optional[str] = None

    def is_configured(self) -> bool:
        if not self._base_url:
            return False
        try:
            requests.get(f"{self._base_url}/system_stats", timeout=3)
            return True
        except Exception:
            return False

    def _resolve_checkpoint(self) -> str:
        if self._checkpoint_cache:
            return self._checkpoint_cache
        default = "v1-5-pruned-emaonly.safetensors"
        try:
            resp = requests.get(f"{self._base_url}/object_info/CheckpointLoaderSimple", timeout=10)
            resp.raise_for_status()
            info = resp.json().get("CheckpointLoaderSimple", {})
            choices = info.get("input", {}).get("required", {}).get("ckpt_name", [[]])[0]
            if choices:
                self._checkpoint_cache = choices[0]
                return self._checkpoint_cache
        except Exception:
            pass
        self._checkpoint_cache = default
        return default

    def _default_workflow(self, prompt: str, seed: int, negative: str = "blurry, low quality") -> dict:
        ckpt = self._resolve_checkpoint()
        return {
            "3": {
                "class_type": "KSampler",
                "inputs": {
                    "seed": seed,
                    "steps": 20,
                    "cfg": 7.0,
                    "sampler_name": "euler",
                    "scheduler": "normal",
                    "denoise": 1.0,
                    "model": ["4", 0],
                    "positive": ["6", 0],
                    "negative": ["7", 0],
                    "latent_image": ["5", 0],
                },
            },
            "4": {"class_type": "CheckpointLoaderSimple", "inputs": {"ckpt_name": ckpt}},
            "5": {"class_type": "EmptyLatentImage", "inputs": {"width": 512, "height": 512, "batch_size": 1}},
            "6": {"class_type": "CLIPTextEncode", "inputs": {"text": prompt, "clip": ["4", 1]}},
            "7": {"class_type": "CLIPTextEncode", "inputs": {"text": negative, "clip": ["4", 1]}},
            "8": {"class_type": "VAEDecode", "inputs": {"samples": ["3", 0], "vae": ["4", 2]}},
            "9": {"class_type": "SaveImage", "inputs": {"filename_prefix": "mimir", "images": ["8", 0]}},
        }

    def _generate_image(self, request: GenerationRequest) -> GenerationResult:
        prompt = request.content or request.title or "A scenic landscape"
        seed = int(request.metadata.get("seed", abs(hash(prompt)) % (2**31)))
        negative = request.metadata.get("negative_prompt") or "blurry, low quality"
        workflow = self._default_workflow(prompt, seed, negative=negative)
        try:
            queued = requests.post(
                f"{self._base_url}/prompt",
                json={"prompt": workflow},
                timeout=30,
            )
            queued.raise_for_status()
            prompt_id = queued.json()["prompt_id"]

            for _ in range(120):
                hist = requests.get(f"{self._base_url}/history/{prompt_id}", timeout=15)
                hist.raise_for_status()
                data = hist.json()
                if prompt_id in data:
                    outputs = data[prompt_id].get("outputs", {})
                    for node_out in outputs.values():
                        for img in node_out.get("images", []):
                            view = requests.get(
                                f"{self._base_url}/view",
                                params={
                                    "filename": img["filename"],
                                    "subfolder": img.get("subfolder", ""),
                                    "type": img.get("type", "output"),
                                },
                                timeout=60,
                            )
                            view.raise_for_status()
                            path = _save_image_bytes(view.content, ext=Path(img["filename"]).suffix.lstrip(".") or "png")
                            return GenerationResult(
                                success=True,
                                stdout=f"ComfyUI image saved to {path.name}",
                                output_path=str(path),
                            )
                    break
                time.sleep(1)
            return GenerationResult(success=False, error="ComfyUI did not return an image in time")
        except Exception as exc:
            return GenerationResult(success=False, error=str(exc), stderr=str(exc))


class Automatic1111ImageProvider(_BaseImageAdapter):
    provider_id = "automatic1111"

    def __init__(self, base_url: str = "http://127.0.0.1:7860", validator: Optional[ArtifactValidator] = None):
        super().__init__(validator=validator)
        self._base_url = base_url.rstrip("/")

    def is_configured(self) -> bool:
        return bool(self._base_url)

    def _generate_image(self, request: GenerationRequest) -> GenerationResult:
        return GenerationResult(success=False, error="Automatic1111 image generation not yet wired")


class ImageProviderRegistry:
    """Resolves the active image provider from settings."""

    def __init__(self, setting_repo=None, validator: Optional[ArtifactValidator] = None):
        settings = get_settings()
        self._validator = validator
        self._providers: Dict[str, IImageProvider] = {
            "openai": OpenAIImageProvider(api_key=settings.openai_api_key, validator=validator),
            "gemini": GeminiImageProvider(api_key=settings.gemini_api_key, validator=validator),
            "stability": StabilityImageProvider(api_key=settings.stability_api_key, validator=validator),
            "comfyui": ComfyUIImageProvider(base_url=settings.comfyui_url, validator=validator),
            "automatic1111": Automatic1111ImageProvider(base_url=settings.automatic1111_url, validator=validator),
        }
        self._active = settings.image_provider

    @property
    def active_provider_id(self) -> str:
        return self._active

    def list_providers(self) -> List[Dict[str, object]]:
        return [
            {
                "id": pid,
                "name": p.name,
                "configured": p.is_configured(),
                "active": pid == self._active,
            }
            for pid, p in self._providers.items()
        ]

    def get_active(self) -> IImageProvider:
        return self._providers.get(self._active, self._providers["openai"])

    def as_creator_provider(self) -> ICreatorProvider:
        return self.get_active()
