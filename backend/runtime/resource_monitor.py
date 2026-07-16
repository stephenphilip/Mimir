"""On-demand resource sampling. Does not poll in the background."""

from __future__ import annotations

import subprocess
import time
from typing import Any, Dict, List, Optional

import psutil


class ResourceMonitor:
    """
    Samples RAM, CPU, GPU VRAM, loaded model, and running tasks when asked.

    Architectural decision: no background thread — sampling is request-driven
    so idle startup stays cheap and RAM stays low.
    """

    def __init__(self) -> None:
        self._loaded_model: Optional[str] = None
        self._running_tasks: List[Dict[str, Any]] = []

    def set_loaded_model(self, model_name: Optional[str]) -> None:
        self._loaded_model = model_name

    def register_task(self, task_id: str, kind: str, detail: str = "") -> None:
        self._running_tasks.append(
            {
                "id": task_id,
                "kind": kind,
                "detail": detail,
                "started_at": time.time(),
            }
        )

    def unregister_task(self, task_id: str) -> None:
        self._running_tasks = [t for t in self._running_tasks if t["id"] != task_id]

    def sample(self) -> Dict[str, Any]:
        """Return a point-in-time snapshot of system and runtime resources."""
        vm = psutil.virtual_memory()
        cpu_percent = psutil.cpu_percent(interval=None)
        gpu = self._sample_gpu()

        return {
            "timestamp": time.time(),
            "ram": {
                "total_gb": round(vm.total / (1024 ** 3), 2),
                "used_gb": round(vm.used / (1024 ** 3), 2),
                "available_gb": round(vm.available / (1024 ** 3), 2),
                "percent": vm.percent,
            },
            "cpu": {
                "percent": cpu_percent,
                "count": psutil.cpu_count() or 0,
            },
            "gpu": gpu,
            "loaded_model": self._loaded_model,
            "running_tasks": list(self._running_tasks),
        }

    def _sample_gpu(self) -> Dict[str, Any]:
        """Best-effort NVIDIA VRAM sample; returns unavailable if nvidia-smi missing."""
        try:
            res = subprocess.run(
                [
                    "nvidia-smi",
                    "--query-gpu=name,memory.total,memory.used,utilization.gpu",
                    "--format=csv,noheader,nounits",
                ],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                check=True,
                timeout=3,
            )
            parts = [p.strip() for p in res.stdout.strip().split(",")]
            if len(parts) >= 4:
                return {
                    "available": True,
                    "name": parts[0],
                    "vram_total_mb": int(float(parts[1])),
                    "vram_used_mb": int(float(parts[2])),
                    "utilization_percent": float(parts[3]),
                }
        except Exception:
            pass

        return {
            "available": False,
            "name": None,
            "vram_total_mb": 0,
            "vram_used_mb": 0,
            "utilization_percent": 0.0,
        }
