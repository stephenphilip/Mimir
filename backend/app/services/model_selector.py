"""Select the best Ollama model for a request — prefer what's already installed."""

from typing import List, Dict, Any, Optional, Tuple

from ..interfaces.services import IModelSelector
from ..core.context import ExecutionContext

# Ideal targets by hardware tier (used for background pulls when missing)
IDEAL_MODELS = {
    "high": {
        "reasoning": "llama3.2:3b",
        "coding": "qwen2.5-coder:7b",
        "text_processing": "llama3.2:3b",
        "translation": "llama3.2:3b",
    },
    "low": {
        "reasoning": "llama3.2:1b",
        "coding": "qwen2.5-coder:1.5b",
        "text_processing": "llama3.2:1b",
        "translation": "llama3.2:1b",
    },
}


def _base(name: str) -> str:
    return (name or "").split(":")[0].lower().strip()


def _score_model(name: str, needs_coding: bool) -> int:
    """Higher is better for the current task among installed models."""
    n = name.lower()
    b = _base(name)
    score = 0

    # Prefer mid-size local models over tiny ones for quality
    if any(x in n for x in ("70b", "65b", "34b")):
        score += 10
    elif any(x in n for x in ("13b", "14b", "8b", "7b")):
        score += 40
    elif any(x in n for x in ("3b", "4b")):
        score += 35
    elif any(x in n for x in ("1.5b", "1b", "0.5b")):
        score += 15
    else:
        score += 28  # unknown size (e.g. llama3.1:latest)

    if needs_coding:
        if "coder" in n or "code" in n:
            score += 50
        if "qwen" in b:
            score += 20
        if "llama" in b:
            score += 18
        if "mistral" in b or "mixtral" in b:
            score += 12
        if "phi" in b:
            score += 8
    else:
        if "llama" in b:
            score += 25
        if "mistral" in b:
            score += 20
        if "qwen" in b and "coder" not in n:
            score += 18
        if "gemma" in b:
            score += 15

    # Slight preference for :latest / untagged everyday installs
    if n.endswith(":latest") or ":" not in n:
        score += 3

    return score


class ModelSelector(IModelSelector):
    def select_best_model(
        self,
        context: ExecutionContext,
        available_models: List[str],
        capabilities: List[str],
        hardware_info: Dict[str, Any],
    ) -> str:
        """
        Choose a model that can answer NOW.

        Architectural decision: prefer an installed model for instant replies.
        Ideal models (Qwen coder, etc.) are returned only when present, or as
        the download target when nothing suitable is installed.
        """
        category = hardware_info.get("category", "low")
        if category not in IDEAL_MODELS:
            category = "low"

        needs_coding = any(
            c in capabilities
            for c in (
                "coding",
                "python_execution",
                "excel_generation",
                "chart_generation",
                "pdf_generation",
            )
        )
        ideal_key = "coding" if needs_coding else "reasoning"
        ideal = IDEAL_MODELS[category][ideal_key]

        installed = [m for m in (available_models or []) if m]
        if not installed:
            return ideal

        # Exact / base-name match for the ideal model
        for name in installed:
            if name == ideal or _base(name) == _base(ideal):
                return name

        # Best installed model for this task (fixes hallucination from wrong picks
        # and avoids blocking on multi‑GB pulls when llama/mistral already exist)
        ranked: List[Tuple[int, str]] = [
            (_score_model(name, needs_coding), name) for name in installed
        ]
        ranked.sort(key=lambda x: x[0], reverse=True)
        return ranked[0][1]

    def ideal_model_for_download(
        self,
        capabilities: List[str],
        hardware_info: Dict[str, Any],
        available_models: Optional[List[str]] = None,
    ) -> Optional[str]:
        """Return ideal model name if it is not already installed (for background pull)."""
        category = hardware_info.get("category", "low")
        if category not in IDEAL_MODELS:
            category = "low"
        needs_coding = any(
            c in capabilities
            for c in (
                "coding",
                "python_execution",
                "excel_generation",
                "chart_generation",
                "pdf_generation",
            )
        )
        ideal = IDEAL_MODELS[category]["coding" if needs_coding else "reasoning"]
        available = available_models or []
        for name in available:
            if name == ideal or _base(name) == _base(ideal):
                return None
        return ideal
