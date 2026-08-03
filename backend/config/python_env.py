"""Resolve the Python interpreter used for chat code execution."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path
from typing import Iterable, List, Optional

from .paths import detect_repo_root

# Packages required for spreadsheet/PDF/chart generation in chat
EXECUTION_PACKAGES = ("fpdf", "pandas", "openpyxl", "matplotlib", "numpy")


def python_candidates(repo_root: Optional[Path] = None) -> List[Path]:
    """Same search order as run_platform.resolve_python."""
    root = repo_root or detect_repo_root()
    backend = root / "backend"
    if sys.platform == "win32":
        rels = [
            backend / ".venv" / "Scripts" / "python.exe",
            root / "venv" / "Scripts" / "python.exe",
            root / ".venv" / "Scripts" / "python.exe",
        ]
    else:
        rels = [
            backend / ".venv" / "bin" / "python",
            root / "venv" / "bin" / "python",
            root / ".venv" / "bin" / "python",
        ]
    return rels


def _can_import(python: Path, module: str) -> bool:
    try:
        result = subprocess.run(
            [str(python), "-c", f"import {module}"],
            capture_output=True,
            timeout=15,
        )
        return result.returncode == 0
    except Exception:
        return False


def resolve_python_executable(
    *,
    repo_root: Optional[Path] = None,
    prefer_with_packages: bool = True,
    required_module: str = "fpdf",
) -> Path:
    """
    Pick the best Python for subprocess execution.

    Prefers an existing venv that can import execution packages (fpdf, etc.).
    Falls back to any existing candidate, then sys.executable.
    """
    import os

    env_override = os.environ.get("MIMIR_VENV_DIR")
    candidates: List[Path] = []
    if env_override:
        venv = Path(env_override).resolve()
        if sys.platform == "win32":
            candidates.append(venv / "Scripts" / "python.exe")
        else:
            candidates.append(venv / "bin" / "python")
    candidates.extend(python_candidates(repo_root))

    existing = [p for p in candidates if p.is_file()]
    if prefer_with_packages:
        for path in existing:
            if _can_import(path, required_module):
                return path

    if existing:
        return existing[0]
    return Path(sys.executable)


def venv_dir_for_python(python: Path) -> Path:
    """Return venv root directory for a venv python executable."""
    if sys.platform == "win32":
        if python.name.lower() == "python.exe" and python.parent.name.lower() == "scripts":
            return python.parent.parent
    else:
        if python.name == "python" and python.parent.name == "bin":
            return python.parent.parent
    return python.parent


def missing_execution_packages(python: Path, packages: Iterable[str] = EXECUTION_PACKAGES) -> List[str]:
    missing: List[str] = []
    for pkg in packages:
        if not _can_import(python, pkg):
            missing.append(pkg)
    return missing


def ensure_execution_packages(python: Path, packages: Iterable[str] = EXECUTION_PACKAGES) -> List[str]:
    """
    pip-install missing execution packages into the given interpreter's environment.
    Returns list of packages that were installed (or attempted).
    """
    installed: List[str] = []
    pip_map = {
        "fpdf": "fpdf2",
        "pandas": "pandas",
        "openpyxl": "openpyxl",
        "matplotlib": "matplotlib",
        "numpy": "numpy",
    }
    for pkg in packages:
        if _can_import(python, pkg):
            continue
        pip_name = pip_map.get(pkg, pkg)
        try:
            subprocess.run(
                [str(python), "-m", "pip", "install", pip_name],
                capture_output=True,
                timeout=180,
                check=True,
            )
            installed.append(pip_name)
        except Exception:
            pass
    return installed
