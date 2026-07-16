import os
import sys
import subprocess
import time
from pathlib import Path


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
    backend_dir = root_dir / "backend"
    frontend_dir = root_dir / "frontend"

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
