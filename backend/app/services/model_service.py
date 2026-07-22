import threading
import json
import time
import requests
from typing import List, Dict, Any, Optional

from ..interfaces.services import IModelService, IGPUService
from ..interfaces.repositories import IModelRepository, ISettingRepository, IModelCatalogRepository
from .gpu_service import GPUService

# Process-level hardware cache (nvidia-smi is expensive on every chat)
_HW_CACHE: Optional[Dict[str, Any]] = None
_HW_CACHE_AT: float = 0.0


class ModelService(IModelService):
    def __init__(
        self,
        model_repo: IModelRepository,
        setting_repo: ISettingRepository,
        catalog_repo: Optional[IModelCatalogRepository] = None,
        gpu_service: Optional[IGPUService] = None,
        ollama_url: str = "http://localhost:11434"
    ):
        self.model_repo = model_repo
        self.setting_repo = setting_repo
        self.catalog_repo = catalog_repo
        self.gpu_service = gpu_service or GPUService()
        self.ollama_url = ollama_url
        self._lock = threading.Lock()

    def detect_hardware(self) -> Dict[str, Any]:
        """Detect GPU availability, VRAM, and System RAM (cached briefly)."""
        global _HW_CACHE, _HW_CACHE_AT
        from config.settings import get_settings

        ttl = get_settings().hardware_cache_ttl_s
        now = time.time()
        if _HW_CACHE is not None and (now - _HW_CACHE_AT) < ttl:
            return _HW_CACHE
        _HW_CACHE = self.gpu_service.detect_hardware()
        _HW_CACHE_AT = now
        return _HW_CACHE

    def get_loaded_models(self) -> List[str]:
        """Models currently resident in Ollama RAM/VRAM."""
        try:
            resp = requests.get(f"{self.ollama_url}/api/ps", timeout=3)
            if resp.status_code == 200:
                models = resp.json().get("models", []) or []
                names = []
                for m in models:
                    names.append(m.get("name") or m.get("model"))
                return [n for n in names if n]
        except Exception:
            pass
        return []

    @staticmethod
    def _same_model(a: Optional[str], b: Optional[str]) -> bool:
        if not a or not b:
            return False
        a_l, b_l = a.lower(), b.lower()
        if a_l == b_l:
            return True
        return a_l.split(":")[0] == b_l.split(":")[0]

    def get_installed_models_from_ollama(self) -> List[str]:
        """Fetch list of models available in Ollama."""
        return [m["name"] for m in self._get_ollama_tag_models()]

    def _get_ollama_tag_models(self) -> List[Dict[str, Any]]:
        """Return Ollama /api/tags model objects (name + size when available)."""
        try:
            resp = requests.get(f"{self.ollama_url}/api/tags", timeout=5)
            if resp.status_code == 200:
                return resp.json().get("models", []) or []
        except Exception:
            pass
        return []

    def _format_model_size(self, size_bytes: Any) -> str:
        try:
            bytes_val = float(size_bytes or 0)
            if bytes_val <= 0:
                return "Unknown"
            return f"{round(bytes_val / (1024 ** 3), 2)} GB"
        except (TypeError, ValueError):
            return "Unknown"

    def sync_models_to_db(self) -> None:
        """Synchronize Ollama tags with database (including size from /api/tags)."""
        tag_models = self._get_ollama_tag_models()
        ollama_by_name = {m.get("name"): m for m in tag_models if m.get("name")}
        ollama_names = list(ollama_by_name.keys())

        # Remove models in DB that are no longer in Ollama
        for model in self.model_repo.get_all_installed():
            if model.name not in ollama_names:
                self.model_repo.delete_by_name(model.name)

        # Upsert installed models with accurate sizes from tags
        for model_name, meta in ollama_by_name.items():
            size = self._format_model_size(meta.get("size"))
            self.model_repo.save_installed(
                name=model_name,
                status="installed",
                size=size,
            )

    def unload_other_models(self, active_model: Optional[str] = None) -> None:
        """Unload non-active models. Skips work when only the active model is loaded."""
        try:
            loaded = self.get_loaded_models()
            if not loaded:
                return

            # Fast path: active model already resident and alone — keep warm
            if active_model and all(self._same_model(m, active_model) for m in loaded):
                return

            for name in loaded:
                if active_model and self._same_model(name, active_model):
                    continue
                requests.post(
                    f"{self.ollama_url}/api/generate",
                    json={"model": name, "keep_alive": 0},
                    timeout=5,
                )
        except Exception as e:
            print(f"Error unloading other models: {e}")

    def preload_first_run_models(self) -> None:
        """Check if any models are in database. If empty, trigger auto-downloads based on hardware."""
        self.sync_models_to_db()
        installed = self.model_repo.get_all_installed()
        if not installed:
            hw = self.detect_hardware()
            
            # Select first run defaults dynamically
            if self.catalog_repo:
                try:
                    from .model_selector import ModelSelector
                    from ..core.context import ExecutionContext
                    from datetime import datetime
                    
                    selector = ModelSelector(self.catalog_repo)
                    ctx = ExecutionContext(
                        conversation_id="preload-init",
                        prompt="preload",
                        capabilities=["reasoning"],
                        created_at=datetime.utcnow()
                    )
                    best_reasoning = selector.select_best_model(ctx, [], ["reasoning"], hw)
                    best_coding = selector.select_best_model(ctx, [], ["coding"], hw)
                    defaults = list(set([best_reasoning, best_coding]))
                except Exception as e:
                    print(f"Error resolving dynamic preloads: {e}")
                    defaults = ["llama3.2:1b", "qwen2.5-coder:1.5b"]
            else:
                category = hw["category"]
                if category == "high":
                    defaults = ["qwen2.5-coder:7b", "llama3.2:3b"]
                else:
                    defaults = ["llama3.2:1b", "qwen2.5-coder:1.5b"]
                
            for model in defaults:
                self.trigger_background_download(model)

    def trigger_background_download(self, model_name: str) -> None:
        """Trigger an asynchronous model pull."""
        existing = self.model_repo.get_download(model_name)
        if existing and existing.status in ["downloading", "pending"]:
            return
        
        self.model_repo.save_download(
            model_name=model_name,
            progress=0.0,
            status="pending",
            error=None
        )

        # Start background thread
        thread = threading.Thread(target=self._download_worker, args=(model_name,))
        thread.daemon = True
        thread.start()

    def _download_worker(self, model_name: str) -> None:
        """Worker thread to handle the streaming pull API from Ollama with midway error handling."""
        from ..db import SessionLocal
        from ..repositories.sqlite_repositories import SQLiteModelRepository
        
        db = SessionLocal()
        thread_model_repo = SQLiteModelRepository(db)
        try:
            # Update status to downloading
            thread_model_repo.save_download(
                model_name=model_name,
                progress=0.0,
                status="downloading"
            )

            # Call Ollama Pull API with stream=True
            response = requests.post(
                f"{self.ollama_url}/api/pull",
                json={"name": model_name},
                stream=True,
                timeout=30  # connection timeout
            )
            
            if response.status_code != 200:
                raise Exception(f"Ollama pull returned HTTP {response.status_code}")

            completed_successfully = False
            for line in response.iter_lines():
                if not line:
                    continue
                data = json.loads(line.decode("utf-8"))
                
                # Check status
                status = data.get("status", "")
                if status == "success":
                    completed_successfully = True
                    thread_model_repo.save_download(
                        model_name=model_name,
                        progress=100.0,
                        status="completed"
                    )
                    break
                
                if "error" in data:
                    raise Exception(data["error"])
                
                total = data.get("total", 0)
                completed = data.get("completed", 0)
                if total > 0:
                    prog = round((completed / total) * 100, 1)
                    # Fetch and throttle updates
                    dl = thread_model_repo.get_download(model_name)
                    if dl and abs(dl.progress - prog) >= 1.0:
                        thread_model_repo.save_download(
                            model_name=model_name,
                            progress=prog,
                            status="downloading"
                        )
            
            if not completed_successfully:
                raise Exception("Download stream closed abruptly before completion.")
            
            # Final check to register in InstalledModel
            # Sync inside the thread using the thread's own db session/repo
            self._sync_models_to_repo(thread_model_repo)
            
        except Exception as e:
            thread_model_repo.save_download(
                model_name=model_name,
                progress=0.0,
                status="failed",
                error=str(e)
            )
        finally:
            db.close()

    def _sync_models_to_repo(self, repo: IModelRepository) -> None:
        """Helper to sync using a specific thread-local repository."""
        tag_models = self._get_ollama_tag_models()
        ollama_by_name = {m.get("name"): m for m in tag_models if m.get("name")}
        ollama_names = list(ollama_by_name.keys())

        for model in repo.get_all_installed():
            if model.name not in ollama_names:
                repo.delete_by_name(model.name)

        for model_name, meta in ollama_by_name.items():
            repo.save_installed(
                name=model_name,
                status="installed",
                size=self._format_model_size(meta.get("size")),
            )
