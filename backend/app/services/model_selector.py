"""Select the best Ollama model using a Multi-Criteria utility router."""

from typing import List, Dict, Any, Optional, Tuple
from datetime import datetime
from ..interfaces.services import IModelSelector
from ..interfaces.repositories import IModelCatalogRepository
from ..core.context import ExecutionContext

# Domain capability weights for Quality rating (Reasoning, Coding, Math, Conversational)
CAPABILITY_WEIGHTS = {
    "reasoning":             [0.7, 0.1, 0.1, 0.1],
    "coding":                [0.1, 0.8, 0.0, 0.1],
    "python_execution":      [0.2, 0.7, 0.0, 0.1],
    "excel_generation":      [0.2, 0.5, 0.2, 0.1],
    "chart_generation":      [0.2, 0.5, 0.2, 0.1],
    "pdf_generation":        [0.3, 0.4, 0.1, 0.2],
    "translation":           [0.4, 0.0, 0.0, 0.6],
    "text_processing":       [0.3, 0.0, 0.0, 0.7],
    "general_reasoning":     [0.6, 0.0, 0.0, 0.4]
}

def _base(name: str) -> str:
    return (name or "").split(":")[0].lower().strip()

class ModelSelector(IModelSelector):
    def __init__(self, catalog_repo: IModelCatalogRepository):
        self.catalog_repo = catalog_repo

    def _get_combined_weights(self, capabilities: List[str]) -> List[float]:
        """Compute the average benchmark weight vector for the requested capabilities."""
        weights = [0.0, 0.0, 0.0, 0.0]
        count = 0
        for cap in capabilities:
            w = CAPABILITY_WEIGHTS.get(cap, CAPABILITY_WEIGHTS["reasoning"])
            for i in range(4):
                weights[i] += w[i]
            count += 1
        if count > 0:
            return [x / count for x in weights]
        return CAPABILITY_WEIGHTS["reasoning"]

    def _calculate_utility(
        self,
        model: Any,
        capabilities: List[str],
        hardware_info: Dict[str, Any],
        is_installed: bool
    ) -> float:
        """Calculate the overall multi-criteria utility score for a catalog model."""
        # 1. Quality score (Weighted benchmarks)
        w = self._get_combined_weights(capabilities)
        quality = (
            w[0] * model.score_reasoning +
            w[1] * model.score_coding +
            w[2] * model.score_math +
            w[3] * model.score_conversational
        )

        # 2. Performance (TPS) score
        system_ram_gb = float(hardware_info.get("ram_gb", 8.0))
        system_vram_gb = float(hardware_info.get("vram_mb", 0.0)) / 1024.0
        has_gpu = bool(hardware_info.get("has_gpu", False))

        tps = model.tps_cpu
        if has_gpu and system_vram_gb > 0:
            overhead = 1.0  # VRAM baseline reservation
            available_vram = max(0.0, system_vram_gb - overhead)
            if model.required_vram_gb <= available_vram:
                tps = model.tps_gpu
            elif model.required_vram_gb > 0:
                offload_fraction = available_vram / model.required_vram_gb
                offload_fraction = min(max(offload_fraction, 0.0), 1.0)
                tps = (offload_fraction * model.tps_gpu) + ((1.0 - offload_fraction) * model.tps_cpu)

        tps_score = min(100.0, tps * 2.0)  # Map TPS (e.g. 50 tps) to a 0-100 score

        # 3. Objective Utility combination (80% Quality, 20% Speed)
        utility = (0.8 * quality) + (0.2 * tps_score)

        # 4. Local Readiness Premium (Bias to prevent heavy cold-start downloads)
        if is_installed:
            utility += 30.0  # Significant premium for ready models

        return utility

    def select_best_model(
        self,
        context: ExecutionContext,
        available_models: List[str],
        capabilities: List[str],
        hardware_info: Dict[str, Any]
    ) -> str:
        """Choose the highest utility model that is currently installed, or fallback to catalog choice."""
        catalog_models = self.catalog_repo.get_all_active()
        if not catalog_models:
            return "llama3.2:1b"  # Hard fallback if DB seeding is completely missing

        system_ram_gb = float(hardware_info.get("ram_gb", 8.0))
        installed_names = [m for m in (available_models or []) if m]

        # Feasibility check & scoring
        feasible_candidates: List[Tuple[float, str, Any]] = []
        for model in catalog_models:
            # Absolute feasibility constraints
            if model.required_ram_gb > system_ram_gb * 1.1:
                continue

            # Determine if installed
            is_installed = False
            matched_name = model.name
            for inst in installed_names:
                if inst == model.name or _base(inst) == _base(model.name):
                    is_installed = True
                    matched_name = inst
                    break

            utility = self._calculate_utility(model, capabilities, hardware_info, is_installed)
            feasible_candidates.append((utility, matched_name, model))

        if not feasible_candidates:
            # Complete system memory deficit: pick the catalog model with smallest required RAM
            smallest = min(catalog_models, key=lambda m: m.required_ram_gb)
            return smallest.name

        # Sort by utility descending
        feasible_candidates.sort(key=lambda x: x[0], reverse=True)
        return feasible_candidates[0][1]

    def ideal_model_for_download(
        self,
        capabilities: List[str],
        hardware_info: Dict[str, Any],
        available_models: Optional[List[str]] = None
    ) -> Optional[str]:
        """Return the ideal model for background download if not already installed (no readiness bias)."""
        catalog_models = self.catalog_repo.get_all_active()
        if not catalog_models:
            return None

        system_ram_gb = float(hardware_info.get("ram_gb", 8.0))
        available = available_models or []

        feasible_candidates: List[Tuple[float, Any]] = []
        for model in catalog_models:
            # Memory check
            if model.required_ram_gb > system_ram_gb * 1.1:
                continue
            
            # Score without readiness premium to find the absolute best fit
            utility = self._calculate_utility(model, capabilities, hardware_info, is_installed=False)
            feasible_candidates.append((utility, model))

        if not feasible_candidates:
            return None

        # Pick the highest scoring target
        feasible_candidates.sort(key=lambda x: x[0], reverse=True)
        ideal_model = feasible_candidates[0][1]

        # Check if already installed
        for name in available:
            if name == ideal_model.name or _base(name) == _base(ideal_model.name):
                return None  # No download needed

        return ideal_model.name
