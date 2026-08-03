"""Project-relative path resolution (Windows / Linux / macOS)."""

from __future__ import annotations

import os
import sys
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path


def detect_repo_root() -> Path:
    """
    Walk upward from this file until we find the repository root
    (directory containing both backend/ and frontend/, or run_platform.py).
    """
    here = Path(__file__).resolve()
    for candidate in [here.parent, *here.parents]:
        if (candidate / "run_platform.py").is_file():
            return candidate
        if (candidate / "backend").is_dir() and (candidate / "frontend").is_dir():
            return candidate
        # When running with cwd=backend, config lives at backend/config/
        if candidate.name == "backend" and (candidate / "app").is_dir():
            return candidate.parent
    # Fallback: backend/ is parent of config/
    return Path(__file__).resolve().parents[2]


@dataclass(frozen=True)
class Paths:
    repo_root: Path
    backend_dir: Path
    data_dir: Path
    database_file: Path
    artifacts_dir: Path
    venv_dir: Path
    extensions_dir: Path
    workspace_dir: Path

    @property
    def database_url(self) -> str:
        # SQLAlchemy requires forward slashes on all platforms
        return "sqlite:///" + self.database_file.resolve().as_posix()

    @property
    def python_executable(self) -> Path:
        if sys.platform == "win32":
            return self.venv_dir / "Scripts" / "python.exe"
        return self.venv_dir / "bin" / "python"

    def ensure_directories(self) -> None:
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.artifacts_dir.mkdir(parents=True, exist_ok=True)


@lru_cache(maxsize=1)
def get_paths() -> Paths:
    """Resolve and cache project paths. Override via MIMIR_* env vars when needed."""
    from .python_env import resolve_python_executable, venv_dir_for_python

    repo_root = Path(os.environ["MIMIR_REPO_ROOT"]).resolve() if os.environ.get("MIMIR_REPO_ROOT") else detect_repo_root()
    backend_dir = repo_root / "backend"

    data_dir = Path(os.environ["MIMIR_DATA_DIR"]).resolve() if os.environ.get("MIMIR_DATA_DIR") else backend_dir / "data"
    artifacts_dir = (
        Path(os.environ["MIMIR_ARTIFACTS_DIR"]).resolve()
        if os.environ.get("MIMIR_ARTIFACTS_DIR")
        else repo_root / "artifacts"
    )

    if os.environ.get("MIMIR_VENV_DIR"):
        venv_dir = Path(os.environ["MIMIR_VENV_DIR"]).resolve()
    else:
        # Prefer a venv that actually has fpdf/pandas for code execution
        resolved_python = resolve_python_executable(repo_root=repo_root)
        venv_dir = venv_dir_for_python(resolved_python)

    extensions_dir = (
        Path(os.environ["MIMIR_EXTENSIONS_DIR"]).resolve()
        if os.environ.get("MIMIR_EXTENSIONS_DIR")
        else repo_root / "extensions"
    )

    return Paths(
        repo_root=repo_root,
        backend_dir=backend_dir,
        data_dir=data_dir,
        database_file=data_dir / "assistant.db",
        artifacts_dir=artifacts_dir,
        venv_dir=venv_dir,
        extensions_dir=extensions_dir,
        workspace_dir=repo_root,
    )
