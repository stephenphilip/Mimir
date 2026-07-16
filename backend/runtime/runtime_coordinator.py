"""
RuntimeCoordinator — single runtime entry point for Mimir.

Delegates model work to ModelService. Does not contain inference logic.
Does not replace ModelService or the Orchestrator.
"""

from __future__ import annotations

import threading
import time
import uuid
from contextlib import contextmanager
from typing import Any, Dict, Generator, List, Optional

from config.paths import Paths, get_paths
from config.settings import Settings, get_settings

from .plugin_loader import PluginLoader
from .resource_monitor import ResourceMonitor


class RuntimeCoordinator:
    """
    Wraps ModelService and owns session/resource/plugin lazy-loading state.

    Flow: Orchestrator → RuntimeCoordinator → ModelService → Ollama
    """

    def __init__(
        self,
        model_service: Any = None,
        paths: Optional[Paths] = None,
        settings: Optional[Settings] = None,
    ) -> None:
        self.paths = paths or get_paths()
        self.settings = settings or get_settings()
        self.model_service = model_service

        self.monitor = ResourceMonitor()
        self.plugin_loader = PluginLoader(extensions_dir=self.paths.extensions_dir)

        self._sessions: Dict[str, Dict[str, Any]] = {}
        self._inference_sema = threading.Semaphore(self.settings.max_concurrent_inferences)
        self._lock = threading.Lock()
        self._active_model: Optional[str] = None
        self._last_inference_at: float = 0.0
        self._started = False
        self._manifests_loaded = False

    # ── Startup (fast path — no Ollama, no downloads) ───────────────

    def start(self) -> Dict[str, Any]:
        """
        Lightweight startup: config already loaded; ensure dirs; load
        local model metadata + plugin manifests. Never contacts Ollama.
        """
        self.paths.ensure_directories()

        if not self._manifests_loaded:
            self.plugin_loader.load_manifests()
            self._manifests_loaded = True

        # Local DB metadata only (no sync). Caller ensures DB is ready.
        installed: List[Dict[str, Any]] = []
        if self.model_service is not None:
            try:
                rows = self.model_service.model_repo.get_all_installed()
                installed = [
                    {"name": m.name, "size": m.size, "status": m.status}
                    for m in rows
                ]
            except Exception:
                installed = []

        self._started = True
        return {
            "paths": {
                "repo_root": str(self.paths.repo_root),
                "data_dir": str(self.paths.data_dir),
                "artifacts_dir": str(self.paths.artifacts_dir),
            },
            "installed_models": installed,
            "plugins": self.plugin_loader.list_manifests(),
        }

    def bind_model_service(self, model_service: Any) -> None:
        """Attach a request-scoped ModelService (repos need a live DB session)."""
        self.model_service = model_service

    # ── Session lifecycle ───────────────────────────────────────────

    def begin_session(self, conversation_id: str) -> str:
        session_id = str(uuid.uuid4())
        with self._lock:
            self._sessions[session_id] = {
                "conversation_id": conversation_id,
                "started_at": time.time(),
                "active_model": None,
            }
        self.monitor.register_task(session_id, "session", conversation_id)
        return session_id

    def end_session(self, session_id: str) -> None:
        with self._lock:
            self._sessions.pop(session_id, None)
        self.monitor.unregister_task(session_id)

    # ── Model lifecycle (delegates to ModelService) ─────────────────

    def sync_models_to_db(self) -> None:
        """Lazy: called when inference / status needs fresh Ollama tags."""
        self._require_model_service().sync_models_to_db()

    def detect_hardware(self) -> Dict[str, Any]:
        return self._require_model_service().detect_hardware()

    def trigger_background_download(self, model_name: str) -> None:
        self._require_model_service().trigger_background_download(model_name)

    def prepare_model(self, active_model: str) -> None:
        """
        Prepare VRAM for inference: unload others, track active model.
        Called only when inference is about to begin (lazy load).
        """
        ms = self._require_model_service()
        ms.unload_other_models(active_model)
        with self._lock:
            self._active_model = active_model
            self._last_inference_at = time.time()
        self.monitor.set_loaded_model(active_model)

    def unload_other_models(self, active_model: Optional[str] = None) -> None:
        """Compatibility wrapper used by orchestrator / shutdown."""
        self._require_model_service().unload_other_models(active_model)
        with self._lock:
            self._active_model = active_model
        self.monitor.set_loaded_model(active_model)

    def idle_cleanup(self) -> None:
        """Unload models if idle longer than configured delay."""
        if not self.settings.enable_idle_model_unload:
            return
        with self._lock:
            if not self._active_model:
                return
            idle_for = time.time() - self._last_inference_at
            if idle_for < self.settings.idle_unload_delay_s:
                return
            model = self._active_model
        if self.model_service is not None:
            self.model_service.unload_other_models(None)
            with self._lock:
                self._active_model = None
            self.monitor.set_loaded_model(None)
            _ = model  # retained for future logging hooks

    # ── Inference scheduling (no inference logic here) ──────────────

    @contextmanager
    def schedule_inference(self, model_name: str) -> Generator[str, None, None]:
        """
        Acquire a concurrency slot for inference. Caller runs the provider.
        Future GPU scheduling hooks can extend this without changing callers.
        """
        task_id = f"infer-{uuid.uuid4().hex[:8]}"
        self._inference_sema.acquire()
        self.monitor.register_task(task_id, "inference", model_name)
        try:
            with self._lock:
                self._last_inference_at = time.time()
            yield task_id
        finally:
            self.monitor.unregister_task(task_id)
            self._inference_sema.release()
            with self._lock:
                self._last_inference_at = time.time()

    # ── Plugins (lazy import) ───────────────────────────────────────

    def get_executor(self, capability: str, *args, **kwargs) -> Any:
        if not self._manifests_loaded:
            self.plugin_loader.load_manifests()
            self._manifests_loaded = True
        return self.plugin_loader.get_executor(capability, *args, **kwargs)

    def list_plugin_manifests(self) -> List[Dict[str, Any]]:
        if not self._manifests_loaded:
            self.plugin_loader.load_manifests()
            self._manifests_loaded = True
        return self.plugin_loader.list_manifests()

    # ── Resource monitoring API ─────────────────────────────────────

    def sample_resources(self) -> Dict[str, Any]:
        """On-demand sample — never polls continuously."""
        return self.monitor.sample()

    # ── Internals ───────────────────────────────────────────────────

    def _require_model_service(self) -> Any:
        if self.model_service is None:
            raise RuntimeError("RuntimeCoordinator has no ModelService bound")
        return self.model_service


# Process-wide coordinator (bound to request-scoped ModelService as needed)
_runtime: Optional[RuntimeCoordinator] = None
_runtime_lock = threading.Lock()


def get_runtime() -> RuntimeCoordinator:
    global _runtime
    with _runtime_lock:
        if _runtime is None:
            _runtime = RuntimeCoordinator()
        return _runtime
