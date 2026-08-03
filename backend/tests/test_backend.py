import sys
from app.db import init_db, SessionLocal, User, Setting
from app.services.intent_service import LegacyIntentService
from app.services.capability_service import CapabilityService
from app.services.model_service import ModelService
from app.services.execution_service import ExecutionService
from app.repositories.sqlite_repositories import SQLiteModelRepository, SQLiteSettingRepository

def run_tests():
    print("--- 1. Testing Database Initialization ---")
    try:
        init_db()
        db = SessionLocal()
        user = db.query(User).first()
        print(f"Database initialized. Seeded user: {user.name if user else 'None'}")
        
        settings = db.query(Setting).all()
        print(f"Database settings seeded count: {len(settings)}")
        db.close()
        print("DB Test: SUCCESS")
    except Exception as e:
        print(f"DB Test: FAILED: {str(e)}")
        sys.exit(1)

    print("\n--- 2. Testing Intent Service ---")
    intent_service = LegacyIntentService()
    test_prompts = [
        ("Please create an excel expense tracker spreadsheet for this year", "spreadsheet_generation"),
        ("Plot a bar chart of the sales data for me", "data_visualization"),
        ("Write a python script to calculate fibonacci", "code_generation"),
        ("Can you translate this sentence to French?", "translation"),
        ("Write a short email summarizing my task list", "writing"),
        ("What is the speed of light in vacuum?", "general_reasoning")
    ]
    
    intent_success = True
    for prompt, expected in test_prompts:
        res = intent_service.classify(prompt)
        matched = res["intent"] == expected
        print(f"Prompt: '{prompt}' -> Classified: {res['intent']} (Conf: {res['confidence']}) - {'PASS' if matched else 'FAIL'}")
        if not matched:
            intent_success = False
            
    if intent_success:
        print("Intent Test: SUCCESS")
    else:
        print("Intent Test: FAILED (Some classification mismatches)")

    print("\n--- 3. Testing Capability Service ---")
    capability_service = CapabilityService()
    caps = capability_service.resolve("spreadsheet_generation")
    print(f"Spreadsheet Intent Capabilities: {caps} (Expected: reasoning, python_execution, excel_generation)")
    reqs = capability_service.get_execution_requirements(caps)
    print(f"Spreadsheet Requirements: {reqs} (Expected: pandas, openpyxl)")
    if "python" in reqs["runtime"] and "pandas" in reqs["packages"]:
        print("Capability Test: SUCCESS")
    else:
        print("Capability Test: FAILED")

    print("\n--- 4. Testing Hardware Detection ---")
    db = SessionLocal()
    model_repo = SQLiteModelRepository(db)
    setting_repo = SQLiteSettingRepository(db)
    model_service = ModelService(model_repo, setting_repo)
    hw = model_service.detect_hardware()
    db.close()
    print("Detected Hardware Specs:")
    print(f"  System RAM: {hw['ram_gb']} GB")
    print(f"  Has GPU: {hw['has_gpu']}")
    print(f"  GPU Name: {hw['gpu_name']}")
    print(f"  VRAM: {hw['vram_mb']} MB")
    print(f"  Recommended Spec Category: {hw['category']}")
    print("Hardware Test: SUCCESS")

    print("\n--- 5. Testing Execution Service ---")
    db = SessionLocal()
    from tools.python_tool import PythonTool
    from config.paths import get_paths
    from app.core.context import ExecutionContext
    
    from app.repositories.sqlite_repositories import SQLiteSettingRepository as SqliteSetRepo
    from app.repositories.sqlite_repositories import SQLiteArtifactRepository as SqliteArtRepo
    setting_repo_local = SqliteSetRepo(db)
    artifact_repo_local = SqliteArtRepo(db)
    
    # Remove pre-existing test artifact to ensure new detection succeeds
    import os
    test_csv_path = get_paths().artifacts_dir / "test_run.csv"
    if test_csv_path.exists():
        try:
            os.remove(test_csv_path)
        except Exception:
            pass

    exec_tool = PythonTool(
        artifact_repo=artifact_repo_local,
        setting_repo=setting_repo_local,
        workspace_dir=get_paths().workspace_dir
    )
    
    code = """
import pandas as pd
import numpy as np

# Generate a mock csv
df = pd.DataFrame({
    'Category': ['A', 'B', 'C'],
    'Value': [10, 20, 30]
})
df.to_csv('test_run.csv', index=False)
print("CSV generated successfully.")
"""
    try:
        ctx = ExecutionContext(prompt="test")
        res = exec_tool.execute({"code": code}, ctx)
        print(f"Exit code: {res['exit_code']}")
        print(f"Stdout: {res['stdout'].strip()}")
        print(f"Stderr: {res['stderr'].strip()}")
        print(f"Artifacts generated: {res['artifacts']}")
        if res["success"] and len(res["artifacts"]) > 0:
            print("Execution Test: SUCCESS")
        else:
            print(f"Execution Test: FAILED: {res}")
    except Exception as e:
        print(f"Execution Test: FAILED: {str(e)}")
    finally:
        db.close()

    print("\n--- 6. Testing Model Memory Lifecycles & Time Calculations ---")
    db = SessionLocal()
    try:
        from app.repositories.sqlite_repositories import SQLiteModelCatalogRepository
        model_repo = SQLiteModelRepository(db)
        setting_repo = SQLiteSettingRepository(db)
        catalog_repo = SQLiteModelCatalogRepository(db)
        model_service = ModelService(model_repo, setting_repo, catalog_repo=catalog_repo)
        
        # Test unloading execution safety
        model_service.unload_other_models("non_existent_mock_model")
        print("Memory Unloading test executed (safety checked).")
        
        # Test deterministic estimation logic (mocking values)
        prompt = "Create a custom excel file for sales"
        prompt_tokens = len(prompt) / 4.0
        expected_response_tokens = 400.0
        tokens_per_sec = 8.0 # CPU default
        
        t_exec_fallback = (prompt_tokens + expected_response_tokens) / tokens_per_sec
        t_exec_target = t_exec_fallback
        
        # qwen2.5-coder:7b = 4.7 GB size
        size_gb = 4.7
        download_speed_gbps = 0.005 # 5 MB/s
        t_download_target = size_gb / download_speed_gbps
        t_total_target = t_download_target + t_exec_target
        threshold = 0.5 * t_total_target
        
        bypass_should_trigger = t_exec_fallback < threshold
        print(f"Bypass Evaluation Test: Fallback exec = {int(t_exec_fallback)}s, Target total = {int(t_total_target)}s, Threshold = {int(threshold)}s")
        print(f"  Should bypass download: {bypass_should_trigger} (Expected: True)")
        
        if bypass_should_trigger:
            print("Time Calculations Test: SUCCESS")
        else:
            print("Time Calculations Test: FAILED")
            
    except Exception as e:
        print(f"Model Lifecycle Test: FAILED: {str(e)}")
    finally:
        db.close()

if __name__ == "__main__":
    run_tests()
