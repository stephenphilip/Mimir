import sys
import os
from pathlib import Path

# Add backend dir to path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.db import SessionLocal, ensure_db_ready
from config.paths import get_paths
from runtime.runtime_coordinator import get_runtime
from app.pipeline_factory import build_pipeline

def test_chat():
    ensure_db_ready()
    db = SessionLocal()
    paths = get_paths()
    runtime = get_runtime()
    
    print("Building pipeline...")
    orchestrator = build_pipeline(db, paths, runtime)
    
    print("Sending test prompt 'hi'...")
    try:
        generator = orchestrator.process_prompt(
            conversation_id="test-chat-id-123",
            prompt="hi",
            workspace_id="default"
        )
        for chunk in generator:
            print(f"CHUNK: {chunk}")
    except Exception as e:
        import traceback
        traceback.print_exc()
    finally:
        db.close()

if __name__ == "__main__":
    test_chat()
