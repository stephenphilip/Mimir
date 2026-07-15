import os
import subprocess
import shutil
import threading
import json
import psutil
import requests
from sqlalchemy.orm import Session
from ..db import InstalledModel, Download, Setting, SessionLocal

# Map capabilities to standard models
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

class ModelService:
    def __init__(self, ollama_url="http://localhost:11434"):
        self.ollama_url = ollama_url
        self._lock = threading.Lock()

    def detect_hardware(self) -> dict:
        """Detect GPU availability, VRAM, and System RAM."""
        ram_gb = round(psutil.virtual_memory().total / (1024 ** 3), 2)
        gpu_name = "None"
        vram_mb = 0
        has_gpu = False

        # Attempt to run nvidia-smi
        try:
            res = subprocess.run(
                ["nvidia-smi", "--query-gpu=name,memory.total", "--format=csv,noheader,nounits"],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                check=True
            )
            parts = res.stdout.strip().split(",")
            if len(parts) >= 2:
                gpu_name = parts[0].strip()
                vram_mb = int(parts[1].strip())
                has_gpu = True
        except (subprocess.SubprocessError, FileNotFoundError):
            # Fallback check on Windows via wmic
            try:
                res = subprocess.run(
                    ["wmic", "path", "win32_VideoController", "get", "name,AdapterRAM", "/format:csv"],
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    text=True,
                    check=True
                )
                lines = [line.strip() for line in res.stdout.splitlines() if line.strip()]
                # WMIC returns headers, look for GPU that has non-zero adapter RAM
                for line in lines[1:]:
                    parts = line.split(",")
                    if len(parts) >= 3:
                        name = parts[1].strip()
                        ram_val = parts[2].strip()
                        if ram_val.isdigit():
                            ram = int(ram_val) // (1024 * 1024)  # Convert to MB
                            if ram > 512:  # Treat as dedicated GPU
                                gpu_name = name
                                vram_mb = ram
                                has_gpu = True
                                break
            except Exception:
                pass

        # Score category: high if GPU exists or RAM >= 16GB, else low
        category = "high" if (has_gpu and vram_mb >= 4000) or ram_gb >= 16.0 else "low"
        
        return {
            "ram_gb": ram_gb,
            "has_gpu": has_gpu,
            "gpu_name": gpu_name,
            "vram_mb": vram_mb,
            "category": category
        }

    def get_installed_models_from_ollama(self) -> list[str]:
        """Fetch list of models available in Ollama."""
        try:
            resp = requests.get(f"{self.ollama_url}/api/tags", timeout=5)
            if resp.status_code == 200:
                models_data = resp.json().get("models", [])
                return [m["name"] for m in models_data]
        except Exception:
            pass
        return []

    def sync_models_to_db(self, db: Session):
        """Synchronize Ollama tags with SQLite DB."""
        ollama_models = self.get_installed_models_from_ollama()
        
        # Remove models in DB that are no longer in Ollama
        db.query(InstalledModel).filter(~InstalledModel.name.in_(ollama_models)).delete(synchronize_session=False)
        
        # Add missing ones
        for model_name in ollama_models:
            exists = db.query(InstalledModel).filter(InstalledModel.name == model_name).first()
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

                db.add(InstalledModel(
                    name=model_name,
                    status="installed",
                    size=size
                ))
        db.commit()

    def select_best_model(self, capabilities: list[str], db: Session) -> str:
        """Choose the best model based on required capabilities and hardware spec."""
        hw = self.detect_hardware()
        category = hw["category"]
        
        # Map required capabilities to candidate models
        candidates = []
        for cap in capabilities:
            model = CAPABILITY_MODELS[category].get(cap, CAPABILITY_MODELS[category]["reasoning"])
            candidates.append(model)
            
        # Select the most comprehensive candidate (normally the first or the coding one if coding is needed)
        selected_model = candidates[0]
        if "coding" in capabilities or "python_execution" in capabilities:
            selected_model = CAPABILITY_MODELS[category]["coding"]

        self.sync_models_to_db(db)
        return selected_model

    def unload_other_models(self, active_model: str = None):
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

    def preload_first_run_models(self, db: Session):
        """Check if any models are in database. If empty, trigger auto-downloads based on hardware."""
        self.sync_models_to_db(db)
        installed = db.query(InstalledModel).all()
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

    def trigger_background_download(self, model_name: str):
        """Trigger an asynchronous model pull."""
        db = SessionLocal()
        try:
            existing = db.query(Download).filter(Download.model_name == model_name).first()
            if existing and existing.status in ["downloading", "pending"]:
                return
            
            if not existing:
                dl = Download(model_name=model_name, progress=0.0, status="pending")
                db.add(dl)
            else:
                existing.status = "pending"
                existing.progress = 0.0
                existing.error = None
            db.commit()

            # Start background thread
            thread = threading.Thread(target=self._download_worker, args=(model_name,))
            thread.daemon = True
            thread.start()
        finally:
            db.close()

    def _download_worker(self, model_name: str):
        """Worker thread to handle the streaming pull API from Ollama with midway error handling."""
        db = SessionLocal()
        try:
            # Update status to downloading
            dl = db.query(Download).filter(Download.model_name == model_name).first()
            if dl:
                dl.status = "downloading"
                db.commit()

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
                    dl = db.query(Download).filter(Download.model_name == model_name).first()
                    if dl:
                        dl.status = "completed"
                        dl.progress = 100.0
                        db.commit()
                    break
                
                if "error" in data:
                    raise Exception(data["error"])
                
                total = data.get("total", 0)
                completed = data.get("completed", 0)
                if total > 0:
                    prog = round((completed / total) * 100, 1)
                    # Throttle DB updates by checking progress change
                    dl = db.query(Download).filter(Download.model_name == model_name).first()
                    if dl and abs(dl.progress - prog) >= 1.0:
                        dl.progress = prog
                        db.commit()
            
            if not completed_successfully:
                raise Exception("Download stream closed abruptly before completion.")
            
            # Final check to register in InstalledModel
            self.sync_models_to_db(db)
            
        except Exception as e:
            dl = db.query(Download).filter(Download.model_name == model_name).first()
            if dl:
                dl.status = "failed"
                dl.error = str(e)
                db.commit()
        finally:
            db.close()
