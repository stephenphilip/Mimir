"""Prompt Studio — prompt enhancement + image prompt optimization (Intelligence Layer)."""

from __future__ import annotations

import json
import re
from typing import Any, Dict, List, Optional

import requests

from config.settings import get_settings

from ..creator.execution_types import PromptStudioPlan
from ..intelligence.prompt_analyzer import PromptAnalyzer


class PromptStudioService:
    """
    Analyzes a user prompt and returns improved variants plus execution metadata
    consumed by the Execution Engine. For image intents, also returns negative
    prompt, style, resolution, and aspect ratio suggestions.
    """

    STYLES = [
        ("professional", "Professional"),
        ("creative", "Creative"),
        ("technical", "Technical"),
    ]

    def __init__(self, ollama_url: Optional[str] = None):
        settings = get_settings()
        self._ollama_url = (ollama_url or settings.ollama_url).rstrip("/")
        self._analyzer = PromptAnalyzer()

    def enhance(self, prompt: str, model: Optional[str] = None) -> Dict[str, Any]:
        model = model or "llama3.1:latest"
        analysis = self._analyzer.analyze(prompt)
        is_image = analysis.is_image_gen or analysis.suggested_capability == "image"

        system = (
            "You improve user prompts for an AI orchestration platform. "
            "Return ONLY valid JSON with keys: "
            "professional, creative, technical, execution_intent, expected_output, "
            "expected_artifact, provider_recommendation, capability, enhanced_prompt"
        )
        if is_image:
            system += (
                ", negative_prompt, suggested_style, suggested_resolution, suggested_aspect_ratio. "
                "negative_prompt is quality exclusions. suggested_style e.g. photorealistic, anime, oil painting. "
                "suggested_resolution e.g. 1024x1024. suggested_aspect_ratio e.g. 1:1, 16:9, 9:16. "
                "provider_recommendation is openai, comfyui, or gemini. capability is image_generation."
            )
        else:
            system += (
                ". expected_artifact is a file type like pdf, xlsx, png. "
                "provider_recommendation is document, openai, comfyui, or python_execution. "
                "capability is document_generation, image_generation, or python_execution."
            )
        system += (
            " enhanced_prompt is the best single improved prompt (<= 90 words). "
            "Each variant value must be <= 70 words and preserve user intent."
        )
        user = f"Original prompt:\n{prompt}\n\nReturn JSON only."

        parsed: Optional[Dict[str, Any]] = None
        try:
            resp = requests.post(
                f"{self._ollama_url}/api/generate",
                json={
                    "model": model,
                    "prompt": f"System: {system}\n\nUser: {user}",
                    "stream": False,
                    "options": {"temperature": 0.6, "num_predict": 380 if is_image else 320},
                    "keep_alive": "30s",
                },
                timeout=(5, 45),
            )
            resp.raise_for_status()
            raw = resp.json().get("response", "")
            parsed = self._parse_json(raw)
        except Exception:
            parsed = None

        if not parsed:
            return self._fallback_response(prompt, model, is_image=is_image)

        plan = PromptStudioPlan(
            original=prompt,
            enhanced_prompt=parsed.get("enhanced_prompt") or parsed.get("professional") or prompt,
            execution_intent=parsed.get("execution_intent") or "Answer the user request",
            expected_output=parsed.get("expected_output") or "Structured assistant response",
            expected_artifact=parsed.get("expected_artifact") or self._infer_artifact(prompt),
            provider_recommendation=parsed.get("provider_recommendation") or self._infer_provider(prompt),
            capability=parsed.get("capability") or self._infer_capability(prompt),
            used_model=model,
            negative_prompt=parsed.get("negative_prompt") or (self._default_negative() if is_image else None),
            suggested_style=parsed.get("suggested_style") or ("photorealistic" if is_image else None),
            suggested_resolution=parsed.get("suggested_resolution") or ("1024x1024" if is_image else None),
            suggested_aspect_ratio=parsed.get("suggested_aspect_ratio") or ("1:1" if is_image else None),
        )

        return {
            "original": prompt,
            "used_model": model,
            "execution": plan.to_dict(),
            "image_prompt": {
                "enhanced_prompt": plan.enhanced_prompt,
                "negative_prompt": plan.negative_prompt,
                "suggested_style": plan.suggested_style,
                "suggested_resolution": plan.suggested_resolution,
                "suggested_aspect_ratio": plan.suggested_aspect_ratio,
            } if is_image else None,
            "variants": [
                {"id": "professional", "label": "Professional", "prompt": parsed.get("professional", prompt)},
                {"id": "creative", "label": "Creative", "prompt": parsed.get("creative", prompt)},
                {"id": "technical", "label": "Technical", "prompt": parsed.get("technical", prompt)},
            ],
        }

    def build_plan(self, prompt: str, model: Optional[str] = None) -> PromptStudioPlan:
        data = self.enhance(prompt, model=model)
        ex = data.get("execution") or {}
        return PromptStudioPlan(
            original=prompt,
            enhanced_prompt=ex.get("enhanced_prompt", prompt),
            execution_intent=ex.get("execution_intent", ""),
            expected_output=ex.get("expected_output", ""),
            expected_artifact=ex.get("expected_artifact", ""),
            provider_recommendation=ex.get("provider_recommendation", ""),
            capability=ex.get("capability", ""),
            used_model=data.get("used_model"),
            negative_prompt=ex.get("negative_prompt"),
            suggested_style=ex.get("suggested_style"),
            suggested_resolution=ex.get("suggested_resolution"),
            suggested_aspect_ratio=ex.get("suggested_aspect_ratio"),
        )

    def _parse_json(self, text: str) -> Optional[Dict[str, Any]]:
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            match = re.search(r"\{[\s\S]*\}", text)
            if match:
                try:
                    return json.loads(match.group(0))
                except json.JSONDecodeError:
                    return None
        return None

    def _default_negative(self) -> str:
        return "blurry, low quality, distorted, watermark, text artifacts"

    def _infer_artifact(self, prompt: str) -> str:
        p = prompt.lower()
        if any(w in p for w in ("pdf", "document", "report")):
            return "pdf"
        if any(w in p for w in ("excel", "spreadsheet", "xlsx", "csv")):
            return "xlsx"
        if any(w in p for w in ("image", "picture", "photo", "draw", "illustration")):
            return "png"
        return "txt"

    def _infer_provider(self, prompt: str) -> str:
        artifact = self._infer_artifact(prompt)
        if artifact == "png":
            from config.settings import get_settings
            return get_settings().image_provider or "comfyui"
        if artifact in {"pdf", "docx", "xlsx", "csv", "txt"}:
            return "document"
        return "python_execution"

    def _infer_capability(self, prompt: str) -> str:
        artifact = self._infer_artifact(prompt)
        if artifact == "png":
            return "image_generation"
        if artifact in {"pdf", "docx", "xlsx", "csv", "txt"}:
            return "document_generation"
        return "python_execution"

    def _fallback_variants(self, prompt: str) -> List[Dict[str, str]]:
        return [
            {
                "id": "professional",
                "label": "Professional",
                "prompt": f"Please provide a clear, professional response to the following request:\n\n{prompt}",
            },
            {
                "id": "creative",
                "label": "Creative",
                "prompt": f"Approach this with creative flair and engaging detail:\n\n{prompt}",
            },
            {
                "id": "technical",
                "label": "Technical",
                "prompt": f"Provide a precise, technical answer with structured steps where applicable:\n\n{prompt}",
            },
        ]

    def _fallback_response(self, prompt: str, model: str, *, is_image: bool = False) -> Dict[str, Any]:
        plan = PromptStudioPlan(
            original=prompt,
            enhanced_prompt=prompt if not is_image else f"{prompt}, highly detailed, sharp focus",
            execution_intent="Fulfill the user request",
            expected_output="Assistant response with optional artifact",
            expected_artifact=self._infer_artifact(prompt),
            provider_recommendation=self._infer_provider(prompt),
            capability=self._infer_capability(prompt),
            used_model=model,
            negative_prompt=self._default_negative() if is_image else None,
            suggested_style="photorealistic" if is_image else None,
            suggested_resolution="1024x1024" if is_image else None,
            suggested_aspect_ratio="1:1" if is_image else None,
        )
        return {
            "original": prompt,
            "used_model": model,
            "execution": plan.to_dict(),
            "image_prompt": {
                "enhanced_prompt": plan.enhanced_prompt,
                "negative_prompt": plan.negative_prompt,
                "suggested_style": plan.suggested_style,
                "suggested_resolution": plan.suggested_resolution,
                "suggested_aspect_ratio": plan.suggested_aspect_ratio,
            } if is_image else None,
            "variants": self._fallback_variants(prompt),
        }
