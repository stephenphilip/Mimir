import sys
import os
import pytest
import uuid
from pathlib import Path

# Add backend dir to path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.db import SessionLocal, ensure_db_ready
from config.paths import get_paths
from runtime.runtime_coordinator import get_runtime
from app.pipeline_factory import build_pipeline

@pytest.fixture(scope="module")
def setup_pipeline():
    ensure_db_ready()
    db = SessionLocal()
    paths = get_paths()
    runtime = get_runtime()
    
    # Initialize runtime coordinator and load plugins
    runtime.start()
    
    # Force models sync to ensure Qwen is active
    if runtime.model_service:
        runtime.model_service.sync_models_to_db()
        
    orchestrator = build_pipeline(db, paths, runtime)
    yield orchestrator
    db.close()

def test_arithmetic_simulation(setup_pipeline):
    orchestrator = setup_pipeline
    prompt = "What is 17 * 3? Respond with just the answer number."
    
    print(f"\n[Test 1] Arithmetic prompt: {prompt}")
    generator = orchestrator.process_prompt(
        conversation_id=f"test-arithmetic-sim-{uuid.uuid4().hex}",
        prompt=prompt,
        workspace_id="default"
    )
    
    text_chunks = []
    for chunk in generator:
        if "content" in chunk:
            try:
                import json
                # Chunk is an SSE string like 'data: {"type": "content", "text": "51"}'
                if chunk.startswith("data: "):
                    payload = json.loads(chunk[6:])
                    if payload.get("type") == "content":
                        text_chunks.append(payload.get("text", ""))
            except Exception:
                pass
                
    response_text = "".join(text_chunks).strip()
    print(f"Response text: {response_text}")
    
    # Assert answer is present (llama 3.2 1b or qwen 2.5 coder 1.5b should answer 51)
    assert "51" in response_text

def test_pdf_story_simulation(setup_pipeline):
    orchestrator = setup_pipeline
    prompt = "Write a children's fable about a friendly rabbit and a slow tortoise, and save it as a PDF."
    
    print(f"\n[Test 2] PDF Story prompt: {prompt}")
    generator = orchestrator.process_prompt(
        conversation_id=f"test-pdf-story-sim-{uuid.uuid4().hex}",
        prompt=prompt,
        workspace_id="default"
    )
    
    artifacts = []
    has_error = False
    error_msg = ""
    
    for chunk in generator:
        if "error" in chunk:
            has_error = True
            error_msg = chunk
        if "execution_result" in chunk:
            try:
                import json
                if chunk.startswith("data: "):
                    payload = json.loads(chunk[6:])
                    if payload.get("type") == "execution_result":
                        artifacts.extend(payload.get("artifacts", []))
            except Exception:
                pass
                
    assert not has_error, f"Execution failed with error: {error_msg}"
    
    # Filter for PDF artifacts
    pdf_artifacts = [a for a in artifacts if a.get("file_type") == "pdf" or a.get("file_name", "").endswith(".pdf")]
    print(f"Generated PDF artifacts: {pdf_artifacts}")
    assert len(pdf_artifacts) > 0, "No PDF artifact was generated and registered!"
 
def test_excel_multiples_simulation(setup_pipeline):
    orchestrator = setup_pipeline
    prompt = (
        "Create an Excel spreadsheet containing the first 10 multiples of 17. "
        "You MUST call the tool by outputting a JSON block with the following exact structure:\n"
        "```json\n"
        "{\n"
        '  "tool": "Python Executor",\n'
        '  "parameters": {\n'
        '    "code": "import pandas as pd\\ndf = pd.DataFrame({\\\'Multiples\\\': [i*17 for i in range(1, 11)]})\\ndf.to_excel(\\\'multiples.xlsx\\\', index=False)"\n'
        "  }\n"
        "}\n"
        "```"
    )
    
    print(f"\n[Test 3] Excel Multiples prompt: {prompt}")
    generator = orchestrator.process_prompt(
        conversation_id=f"test-excel-multiples-sim-{uuid.uuid4().hex}",
        prompt=prompt,
        workspace_id="default"
    )
    
    artifacts = []
    has_error = False
    error_msg = ""
    
    for chunk in generator:
        if "error" in chunk:
            has_error = True
            error_msg = chunk
        if "execution_result" in chunk:
            try:
                import json
                if chunk.startswith("data: "):
                    payload = json.loads(chunk[6:])
                    if payload.get("type") == "execution_result":
                        artifacts.extend(payload.get("artifacts", []))
            except Exception:
                pass
                
    assert not has_error, f"Execution failed with error: {error_msg}"
    
    # Filter for Excel artifacts
    xlsx_artifacts = [a for a in artifacts if a.get("file_type") == "xlsx" or a.get("file_name", "").endswith(".xlsx")]
    print(f"Generated Excel artifacts: {xlsx_artifacts}")
    assert len(xlsx_artifacts) > 0, "No Excel artifact was generated and registered!"
