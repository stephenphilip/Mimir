import os
import subprocess
import threading
import json
import psutil
import requests
from typing import List, Dict, Any, Optional

from ..interfaces.services import IModelService, IGPUService
from ..interfaces.repositories import IModelRepository, ISettingRepository
from .gpu_service import GPUService

class ModelService(IModelService):
    def __init__(self, model_repo: IModelRepository, setting_repo: ISettingRepository, gpu_service: Optional[IGPUService] = None, ollama_url: str = "http://localhost:11434"):
        self.model_repo = model_repo
        self.setting_repo = setting_repo
        self.gpu_service = gpu_service or GPUService()
        self.ollama_url = ollama_url
        self._lock = threading.Lock()

    def detect_hardware(self) -> Dict[str, Any]:
        """Detect GPU availability, VRAM, and System RAM."""
        return self.gpu_service.detect_hardware()

    def get_installed_models_from_ollama(self) -> List[str]:
        """Fetch list of models available in Ollama."""
        try:
            resp = requests.get(f"{self.ollama_url}/api/tags", timeout=5)
            if resp.status_code == 200:
                models_data = resp.json().get("models", [])
                return [m["name"] for m in models_data]
        except Exception:
            pass
        return []

    def sync_models_to_db(self) -> None:
        """Synchronize Ollama tags with database."""
        ollama_models = self.get_installed_models_from_ollama()
        
        # Remove models in DB that are no longer in Ollama
        for model in self.model_repo.get_all_installed():
            if model.name not in ollama_models:
                self.model_repo.delete_by_name(model.name)
        
        # Add missing ones
        for model_name in ollama_models:
            exists = self.model_repo.get_by_name(model_name)
            if not exists:
                # Get size info
                try:
                    resp = requests.post(f"{self.ollama_url}/api/show", json={"name": model_name}, timeout=3)
                    size = "Unknown"
                    if resp.status_code == 200:
                        details = resp.json().get("details", {})
                        size = f"{round(resp.json().get('size', 0) / (1024**3), 2)} GB"
                except Exception:
                    size = "Unknown"

                self.model_repo.save_installed(
                    name=model_name,
                    status="installed",
                    size=size
                )

    def unload_other_models(self, active_model: Optional[str] = None) -> None:
        """Query Ollama and unload all loaded models except active_model to free VRAM/RAM."""
        try:
            resp = requests.get(f"{self.ollama_url}/api/ps", timeout=5)
            if resp.status_code == 200:
                models = resp.json().get("models", [])
                for m in models:
                    name = m.get("name")
                    model = m.get("model")
                    
                    to_unload = None
                    if name and name != active_model and name != f"{active_model}:latest":
                        to_unload = name
                    elif model and model != active_model and model != f"{active_model}:latest":
                        to_unload = model
                        
                    if to_unload:
                        requests.post(
                            f"{self.ollama_url}/api/generate",
                            json={"model": to_unload, "keep_alive": 0},
                            timeout=5
                        )
        except Exception as e:
            print(f"Error unloading other models: {e}")

    def preload_first_run_models(self) -> None:
        """Check if any models are in database. If empty, trigger auto-downloads based on hardware."""
        self.sync_models_to_db()
        installed = self.model_repo.get_all_installed()
        if not installed:
            hw = self.detect_hardware()
            category = hw["category"]
            
            # Select first run defaults: a general reasoning and a code model
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
        ollama_models = self.get_installed_models_from_ollama()
        for model in repo.get_all_installed():
            if model.name not in ollama_models:
                repo.delete_by_name(model.name)
        
        for model_name in ollama_models:
            exists = repo.get_by_name(model_name)
            if not exists:
                try:
                    resp = requests.post(f"{self.ollama_url}/api/show", json={"name": model_name}, timeout=3)
                    size = "Unknown"
                    if resp.status_code == 200:
                        size = f"{round(resp.json().get('size', 0) / (1024**3), 2)} GB"
                except Exception:
                    size = "Unknown"

                repo.save_installed(name=model_name, status="installed", size=size)
