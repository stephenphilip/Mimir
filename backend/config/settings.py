"""Runtime constants, timeouts, and feature flags."""

from __future__ import annotations

import os
from dataclasses import dataclass
from functools import lru_cache


@dataclass(frozen=True)
class Settings:
    # Network
    ollama_url: str
    ollama_request_timeout_s: float
    ollama_pull_connect_timeout_s: float

    # Inference / download heuristics (used by orchestrator)
    tokens_per_sec_gpu: float
    tokens_per_sec_cpu: float
    expected_response_tokens: float
    download_speed_gbps: float
    bypass_threshold_ratio: float
    download_poll_interval_s: float

    # Execution
    python_execution_timeout_s: int

    # Runtime / scheduler
    idle_unload_delay_s: float
    max_concurrent_inferences: int
    hardware_cache_ttl_s: float

    # Feature flags
    enable_startup_model_preload: bool
    enable_startup_ollama_sync: bool
    enable_idle_model_unload: bool

    # Defaults for seeded settings
    default_user_name: str
    default_personality: str
    default_theme: str


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    def _bool(name: str, default: bool) -> bool:
        raw = os.environ.get(name)
        if raw is None:
            return default
        return raw.strip().lower() in {"1", "true", "yes", "on"}

    def _float(name: str, default: float) -> float:
        raw = os.environ.get(name)
        return float(raw) if raw is not None else default

    def _int(name: str, default: int) -> int:
        raw = os.environ.get(name)
        return int(raw) if raw is not None else default

    return Settings(
        ollama_url=os.environ.get("MIMIR_OLLAMA_URL", "http://localhost:11434"),
        ollama_request_timeout_s=_float("MIMIR_OLLAMA_TIMEOUT_S", 5.0),
        ollama_pull_connect_timeout_s=_float("MIMIR_OLLAMA_PULL_TIMEOUT_S", 30.0),
        tokens_per_sec_gpu=_float("MIMIR_TOKENS_PER_SEC_GPU", 40.0),
        tokens_per_sec_cpu=_float("MIMIR_TOKENS_PER_SEC_CPU", 8.0),
        expected_response_tokens=_float("MIMIR_EXPECTED_RESPONSE_TOKENS", 400.0),
        download_speed_gbps=_float("MIMIR_DOWNLOAD_SPEED_GBPS", 0.005),
        bypass_threshold_ratio=_float("MIMIR_BYPASS_THRESHOLD_RATIO", 0.5),
        download_poll_interval_s=_float("MIMIR_DOWNLOAD_POLL_INTERVAL_S", 1.0),
        python_execution_timeout_s=_int("MIMIR_PYTHON_EXEC_TIMEOUT_S", 120),
        idle_unload_delay_s=_float("MIMIR_IDLE_UNLOAD_DELAY_S", 300.0),
        max_concurrent_inferences=_int("MIMIR_MAX_CONCURRENT_INFERENCES", 1),
        hardware_cache_ttl_s=_float("MIMIR_HARDWARE_CACHE_TTL_S", 30.0),
        # Startup must stay fast — preload/sync off by default
        enable_startup_model_preload=_bool("MIMIR_STARTUP_MODEL_PRELOAD", False),
        enable_startup_ollama_sync=_bool("MIMIR_STARTUP_OLLAMA_SYNC", False),
        enable_idle_model_unload=_bool("MIMIR_IDLE_MODEL_UNLOAD", True),
        default_user_name=os.environ.get("MIMIR_DEFAULT_USER_NAME", "User"),
        default_personality=os.environ.get(
            "MIMIR_DEFAULT_PERSONALITY",
            "helpful, concise, expert data analyst and assistant",
        ),
        default_theme=os.environ.get("MIMIR_DEFAULT_THEME", "dark"),
    )
