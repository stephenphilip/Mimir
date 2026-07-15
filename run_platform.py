import os
import sys
import subprocess
import time
import signal

def main():
    print("==============================================================")
    print("             AI-Native Personal Assistant Platform            ")
    print("==============================================================")
    
    root_dir = os.path.dirname(os.path.abspath(__file__))
    backend_dir = os.path.join(root_dir, "backend")
    frontend_dir = os.path.join(root_dir, "frontend")
    
    python_exe = os.path.join(backend_dir, ".venv", "Scripts", "python.exe")
    
    if not os.path.exists(python_exe):
        print(f"Error: Virtual environment not found at {python_exe}")
        print("Please check that your backend setup was successful.")
        sys.exit(1)
        
    print("\n[1/2] Starting FastAPI Backend on http://localhost:8000 ...")
    backend_proc = subprocess.Popen(
        [python_exe, "-m", "uvicorn", "app.main:app", "--reload", "--host", "127.0.0.1", "--port", "8000"],
        cwd=backend_dir,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        bufsize=1
    )
    
    # Wait a moment for backend to bind port
    time.sleep(2)
    
    print("[2/2] Starting Vite Frontend on http://localhost:5173 ...")
    # On Windows, we use shell=True for npm commands
    frontend_proc = subprocess.Popen(
        ["npm", "run", "dev"],
        cwd=frontend_dir,
        shell=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        bufsize=1
    )
    
    print("\n--------------------------------------------------------------")
    print("✨ Platform is running successfully!")
    print("👉 Access the Personal Assistant Dashboard: http://localhost:5173")
    print("👉 Access the API endpoints & Swagger docs: http://localhost:8000/docs")
    print("Press Ctrl+C to terminate both servers.")
    print("--------------------------------------------------------------\n")
    
    # Simple threads or loops to print logs
    # We will set both proc outputs to non-blocking and poll them
    try:
        # Set pipes to non-blocking
        if sys.platform != 'win32':
            import fcntl
            for pipe in [backend_proc.stdout, frontend_proc.stdout]:
                fd = pipe.fileno()
                fl = fcntl.fcntl(fd, fcntl.F_GETFL)
                fcntl.fcntl(fd, fcntl.F_SETFL, fl | os.O_NONBLOCK)
                
        while True:
            # Check backend output
            if backend_proc.poll() is not None:
                print("Backend terminated unexpectedly.")
                break
            if frontend_proc.poll() is not None:
                print("Frontend terminated unexpectedly.")
                break
                
            # Read line from backend (non-blocking simulation on windows)
            # Since select/fcntl is hard on Windows without thread, we just sleep slightly and check
            # For simplicity, we just keep running until Ctrl+C.
            time.sleep(0.5)
            
    except KeyboardInterrupt:
        print("\nStopping services...")
    finally:
        # Terminate processes
        backend_proc.terminate()
        # On Windows, taskkill might be needed to kill npm's child node process
        if sys.platform == 'win32':
            subprocess.run(["taskkill", "/F", "/T", "/PID", str(frontend_proc.pid)], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        else:
            frontend_proc.terminate()
            
        print("Servers stopped. Thank you for using Mimir!")

if __name__ == "__main__":
    main()
