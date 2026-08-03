import os
import sys
import subprocess
import time
import shutil
import urllib.request
import tempfile
import json
from pathlib import Path

# ── Ollama helpers ────────────────────────────────────────────────────────────

OLLAMA_API_LATEST = "https://api.github.com/repos/ollama/ollama/releases/latest"

# Direct asset download URLs — GitHub always serves the latest stable here
OLLAMA_DOWNLOAD = {
    "win32":  "https://github.com/ollama/ollama/releases/latest/download/OllamaSetup.exe",
    "darwin": "https://github.com/ollama/ollama/releases/latest/download/Ollama-darwin.zip",
    "linux":  None,  # handled via the official install script
}


def _ollama_version() -> str | None:
    """Return installed Ollama version string, or None if not found."""
    exe = shutil.which("ollama")
    if exe is None:
        # Windows: check the default install location as a fallback
        if sys.platform == "win32":
            local_app = Path(os.environ.get("LOCALAPPDATA", "")) / "Programs" / "Ollama" / "ollama.exe"
            if local_app.exists():
                return "installed"  # version doesn't matter, it exists
        return None
    try:
        result = subprocess.run(
            ["ollama", "--version"],
            capture_output=True,
            text=True,
            timeout=5,
        )
        return result.stdout.strip() or "installed"
    except Exception:
        return None


def _fetch_latest_version() -> str:
    """Fetch the latest stable Ollama version tag from GitHub API."""
    try:
        req = urllib.request.Request(
            OLLAMA_API_LATEST,
            headers={"User-Agent": "Mimir-Platform/1.0"},
        )
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read())
            return data.get("tag_name", "latest")
    except Exception:
        return "latest"


def _download_with_progress(url: str, dest: Path) -> None:
    """Download a file with a simple progress indicator."""
    def _progress(count, block_size, total):
        if total > 0:
            pct = min(int(count * block_size * 100 / total), 100)
            bar = "█" * (pct // 5) + "░" * (20 - pct // 5)
            print(f"\r  [{bar}] {pct}%", end="", flush=True)

    urllib.request.urlretrieve(url, str(dest), reporthook=_progress)
    print()  # newline after progress bar


def _install_ollama_windows(tmp_dir: Path) -> bool:
    """Download and silently run the Ollama Windows installer."""
    installer = tmp_dir / "OllamaSetup.exe"
    print(f"  Downloading OllamaSetup.exe ...")
    _download_with_progress(OLLAMA_DOWNLOAD["win32"], installer)

    print("  Running installer (this may take ~30 seconds) ...")
    result = subprocess.run(
        [str(installer), "/VERYSILENT", "/NORESTART", "/SUPPRESSMSGBOXES"],
        timeout=120,
    )
    if result.returncode != 0:
        print(f"  Error: Installer exited with code {result.returncode}.")
        return False

    # Refresh PATH so the new ollama.exe is findable in this process
    local_app = Path(os.environ.get("LOCALAPPDATA", "")) / "Programs" / "Ollama"
    os.environ["PATH"] = str(local_app) + os.pathsep + os.environ.get("PATH", "")
    return True


def _install_ollama_macos(tmp_dir: Path) -> bool:
    """Download the Ollama macOS zip and place the binary in /usr/local/bin."""
    zip_path = tmp_dir / "Ollama-darwin.zip"
    print("  Downloading Ollama for macOS ...")
    _download_with_progress(OLLAMA_DOWNLOAD["darwin"], zip_path)

    print("  Extracting ...")
    subprocess.run(["unzip", "-q", str(zip_path), "-d", str(tmp_dir)], check=True)

    # The zip contains Ollama.app; extract the CLI binary from it
    binary = tmp_dir / "Ollama.app" / "Contents" / "Resources" / "ollama"
    if not binary.exists():
        print("  Error: Could not find ollama binary inside zip.")
        return False

    dest = Path("/usr/local/bin/ollama")
    try:
        shutil.copy2(str(binary), str(dest))
        dest.chmod(0o755)
    except PermissionError:
        print("  Retrying with sudo ...")
        subprocess.run(["sudo", "cp", str(binary), str(dest)], check=True)
        subprocess.run(["sudo", "chmod", "755", str(dest)], check=True)
    return True


def _install_ollama_linux() -> bool:
    """Use the official Ollama install script (curl | sh)."""
    print("  Running official Ollama install script ...")
    result = subprocess.run(
        "curl -fsSL https://ollama.com/install.sh | sh",
        shell=True,
        timeout=300,
    )
    return result.returncode == 0


def _wait_for_ollama(timeout_s: int = 30) -> bool:
    """Poll localhost:11434 until Ollama responds or timeout expires."""
    url = os.environ.get("MIMIR_OLLAMA_URL", "http://localhost:11434")
    deadline = time.time() + timeout_s
    print(f"  Waiting for Ollama to start at {url} ...", end="", flush=True)
    while time.time() < deadline:
        try:
            urllib.request.urlopen(f"{url}/api/tags", timeout=2)
            print(" ready.")
            return True
        except Exception:
            print(".", end="", flush=True)
            time.sleep(1)
    print(" timed out.")
    return False


def _start_ollama_service() -> None:
    """Start the Ollama background server if it isn't already running."""
    try:
        urllib.request.urlopen("http://localhost:11434/api/tags", timeout=2)
        return  # already running
    except Exception:
        pass

    print("  Starting Ollama server ...")
    if sys.platform == "win32":
        # Ollama on Windows self-daemonises when invoked without a subcommand
        subprocess.Popen(
            ["ollama", "serve"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            creationflags=subprocess.CREATE_NO_WINDOW,
        )
    else:
        subprocess.Popen(
            ["ollama", "serve"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            start_new_session=True,
        )


def ensure_ollama() -> None:
    """
    Check if Ollama is installed and reachable.
    If not installed, download and install the latest stable version.
    If installed but not running, start the server.
    Exits the process on unrecoverable failure.
    """
    version = _ollama_version()

    if version:
        print(f"[Ollama] Found: {version}")
    else:
        latest_tag = _fetch_latest_version()
        print(f"[Ollama] Not found. Installing {latest_tag} ...")

        with tempfile.TemporaryDirectory() as tmp:
            tmp_dir = Path(tmp)
            if sys.platform == "win32":
                ok = _install_ollama_windows(tmp_dir)
            elif sys.platform == "darwin":
                ok = _install_ollama_macos(tmp_dir)
            else:
                ok = _install_ollama_linux()

        if not ok:
            print("\nError: Ollama installation failed.")
            print("Please install it manually from: https://ollama.com/download")
            sys.exit(1)

        print("[Ollama] Installation complete.")

    # Ensure the server process is running, then wait for it to be ready
    _start_ollama_service()
    if not _wait_for_ollama(timeout_s=30):
        print("\nError: Ollama installed but server did not respond within 30 seconds.")
        print("Try running 'ollama serve' manually in another terminal.")
        sys.exit(1)


def resolve_python(root_dir: Path, backend_dir: Path) -> Path:
    """Prefer backend/.venv, then repo-root venv (Windows/Linux/macOS)."""
    candidates = []
    if sys.platform == "win32":
        candidates = [
            backend_dir / ".venv" / "Scripts" / "python.exe",
            root_dir / "venv" / "Scripts" / "python.exe",
            root_dir / ".venv" / "Scripts" / "python.exe",
        ]
    else:
        candidates = [
            backend_dir / ".venv" / "bin" / "python",
            root_dir / "venv" / "bin" / "python",
            root_dir / ".venv" / "bin" / "python",
        ]

    for path in candidates:
        if path.exists():
            return path
    return candidates[0]


def ensure_frontend_deps(frontend_dir: Path) -> None:
    """Install npm packages if node_modules/vite is missing."""
    vite_bin = frontend_dir / "node_modules" / "vite" / "bin" / "vite.js"
    node_modules = frontend_dir / "node_modules"
    if node_modules.is_dir() and vite_bin.is_file():
        return

    print("Frontend dependencies missing. Running npm install ...")
    result = subprocess.run(
        ["npm", "install"],
        cwd=str(frontend_dir),
        shell=(sys.platform == "win32"),
    )
    if result.returncode != 0:
        print("Error: npm install failed. Fix the npm errors above, then retry.")
        sys.exit(1)

    if not vite_bin.is_file():
        print("Error: vite still not found after npm install.")
        print(f"Expected: {vite_bin}")
        sys.exit(1)


def _load_mimir_env(root_dir: Path) -> None:
    """Load mimir.env into process environment (simple KEY=VALUE format)."""
    for name in ("mimir.env", ".env"):
        env_file = root_dir / name
        if not env_file.is_file():
            continue
        for line in env_file.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, _, value = line.partition("=")
            key, value = key.strip(), value.strip().strip('"').strip("'")
            if key and key not in os.environ:
                os.environ[key] = value
        print(f"[Env] Loaded {env_file.name}")
        break


def drain_output(proc: subprocess.Popen, label: str) -> None:
    if proc.stdout is None:
        return
    try:
        out = proc.stdout.read()
        if out:
            print(f"----- {label} output -----")
            print(out if isinstance(out, str) else out.decode("utf-8", errors="replace"))
    except Exception:
        pass


def main():
    print("==============================================================")
    print("             AI-Native Personal Assistant Platform            ")
    print("==============================================================")

    root_dir = Path(__file__).resolve().parent
    _load_mimir_env(root_dir)
    backend_dir = root_dir / "backend"
    frontend_dir = root_dir / "frontend"

    # ── Step 0: Ensure Ollama is installed and running ────────────────
    print("\n[0/2] Checking Ollama ...")
    ensure_ollama()

    python_exe = resolve_python(root_dir, backend_dir)

    if not python_exe.exists():
        print(f"Error: Virtual environment not found at {python_exe}")
        print("Create one, e.g.: python -m venv venv && venv\\Scripts\\activate")
        print("Then: pip install -r backend\\requirements.txt")
        sys.exit(1)

    ensure_frontend_deps(frontend_dir)

    print("\n[1/2] Starting FastAPI Backend on http://localhost:8000 ...")
    backend_proc = subprocess.Popen(
        [str(python_exe), "-m", "uvicorn", "app.main:app", "--reload", "--host", "127.0.0.1", "--port", "8000"],
        cwd=str(backend_dir),
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        bufsize=1,
    )

    time.sleep(2)

    print("[2/2] Starting Vite Frontend on http://localhost:5173 ...")
    frontend_proc = subprocess.Popen(
        ["npm", "run", "dev", "--", "--host", "127.0.0.1", "--port", "5173"],
        cwd=str(frontend_dir),
        shell=(sys.platform == "win32"),
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        bufsize=1,
    )

    # Give Vite a moment; surface early failures instead of a fake success banner
    time.sleep(2)
    if frontend_proc.poll() is not None:
        print("Error: Frontend failed to start.")
        drain_output(frontend_proc, "Frontend")
        backend_proc.terminate()
        print("\nTip: from frontend/, run: npm install && npm run dev")
        sys.exit(1)

    if backend_proc.poll() is not None:
        print("Error: Backend failed to start.")
        drain_output(backend_proc, "Backend")
        frontend_proc.terminate()
        sys.exit(1)

    print("\n--------------------------------------------------------------")
    print("Platform is running.")
    print("UI:   http://localhost:5173")
    print("API:  http://localhost:8000/docs")
    print("Press Ctrl+C to stop both servers.")
    print("--------------------------------------------------------------\n")

    try:
        while True:
            if backend_proc.poll() is not None:
                print("Backend terminated unexpectedly.")
                drain_output(backend_proc, "Backend")
                break
            if frontend_proc.poll() is not None:
                print("Frontend terminated unexpectedly.")
                drain_output(frontend_proc, "Frontend")
                break
            time.sleep(0.5)
    except KeyboardInterrupt:
        print("\nStopping services...")
    finally:
        backend_proc.terminate()
        if sys.platform == "win32":
            subprocess.run(
                ["taskkill", "/F", "/T", "/PID", str(frontend_proc.pid)],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
        else:
            frontend_proc.terminate()
        print("Servers stopped. Thank you for using Mimir!")


if __name__ == "__main__":
    main()
