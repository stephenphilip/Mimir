import subprocess
import psutil
from typing import Dict, Any
from ..interfaces.services import IGPUService

class GPUService(IGPUService):
    def detect_hardware(self) -> Dict[str, Any]:
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
