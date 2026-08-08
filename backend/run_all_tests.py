import sys
import subprocess
import os

def run_cmd(args, cwd=None):
    print(f"\n> Running: {' '.join(args)}")
    res = subprocess.run(args, cwd=cwd)
    return res.returncode

def main():
    backend_dir = os.path.abspath(os.path.dirname(__file__))
    venv_python = os.path.join(backend_dir, ".venv", "Scripts", "python.exe")
    if not os.path.exists(venv_python):
        venv_python = "python" # fallback
        
    print("=" * 80)
    print("                      MIMIR INTEGRATED TEST RUNNER                       ")
    print("=" * 80)
    
    # 1. Run unit tests and chat simulations using pytest (ignoring memory regression)
    pytest_args = [
        venv_python, "-m", "pytest",
        "--ignore=tests/test_memory_regression.py",
        "-v"
    ]
    exit_code_unit = run_cmd(pytest_args, cwd=backend_dir)
    
    # 2. Run memory regression tests and print summary
    regression_args = [venv_python, "tests/run_regression.py"]
    exit_code_regression = run_cmd(regression_args, cwd=backend_dir)
    
    print("\n" + "=" * 80)
    print("                            FINAL TEST RESULTS                           ")
    print("=" * 80)
    
    unit_passed = (exit_code_unit == 0)
    reg_passed = (exit_code_regression == 0)
    
    print(f"Unit & Chat Simulation Tests: {'PASSED' if unit_passed else 'FAILED'}")
    print(f"Memory Regression Tests:      {'PASSED' if reg_passed else 'FAILED'}")
    print("=" * 80)
    
    if unit_passed and reg_passed:
        print("\nALL MIMIR TESTS PASSED SUCCESSFULLY!")
        sys.exit(0)
    else:
        print("\nSOME MIMIR TESTS FAILED. PLEASE RESOLVE THE ISSUES.")
        sys.exit(1)

if __name__ == "__main__":
    main()
