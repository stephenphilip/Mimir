from typing import List, Dict, Any

from ..interfaces.services import IModelSelector
from ..core.context import ExecutionContext

CAPABILITY_MODELS = {
    "high": {
        "reasoning": "qwen2.5-coder:7b",
        "coding": "qwen2.5-coder:7b",
        "text_processing": "qwen2.5-coder:7b",
        "translation": "qwen2.5-coder:7b"
    },
    "low": {
        "reasoning": "llama3.2:1b",
        "coding": "qwen2.5-coder:1.5b",
        "text_processing": "llama3.2:1b",
        "translation": "llama3.2:1b"
    }
}

class ModelSelector(IModelSelector):
    def select_best_model(
        self,
        context: ExecutionContext,
        available_models: List[str],
        capabilities: List[str],
        hardware_info: Dict[str, Any]
    ) -> str:
        """Choose the best model based on capabilities and hardware category."""
        category = hardware_info.get("category", "low")
        
        # Map required capabilities to candidate models
        candidates = []
        for cap in capabilities:
            # Map capability to specific models (defaulting to reasoning model)
            model = CAPABILITY_MODELS[category].get(cap, CAPABILITY_MODELS[category]["reasoning"])
            candidates.append(model)
            
        if not candidates:
            # Fallback
            return CAPABILITY_MODELS[category]["reasoning"]

        # Select the most comprehensive candidate (normally the first or the coding one if coding is needed)
        selected_model = candidates[0]
        if "coding" in capabilities or "python_execution" in capabilities:
            selected_model = CAPABILITY_MODELS[category]["coding"]

        return selected_model
