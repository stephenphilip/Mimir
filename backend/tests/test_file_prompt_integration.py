import os
import sys
import unittest
from pathlib import Path

# Add backend dir to python path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.db import SessionLocal, ensure_db_ready, Workspace, ManagedFile
from app.services.file_manager_service import FileManagerService
from app.services.context_builder import ContextBuilder
from app.core.context import ExecutionContext
from config.paths import get_paths
from fpdf import FPDF

class TestFilePromptIntegration(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        # Ensure database is initialized
        ensure_db_ready()
        cls.db = SessionLocal()
        cls.paths = get_paths()
        
        # Resolve workspace
        cls.workspace = cls.db.query(Workspace).filter(Workspace.is_default == True).first()
        if not cls.workspace:
            import uuid
            cls.workspace = Workspace(id=str(uuid.uuid4()), name="Test Workspace", is_default=True)
            cls.db.add(cls.workspace)
            cls.db.commit()

    @classmethod
    def tearDownClass(cls):
        cls.db.close()

    def test_01_pdf_upload_and_extraction(self):
        print("\n--- Running Test 01: Native PDF Upload and DB Extraction Cache ---")
        ws_id = self.workspace.id
        
        # 1. Create a dummy native PDF using fpdf
        pdf = FPDF()
        pdf.add_page()
        pdf.set_font("Arial", size=12)
        pdf.cell(200, 10, txt="Stephen Philip Kallarackal Resume Content", ln=1, align="C")
        pdf.cell(200, 10, txt="Skills: Python, React, Business Analysis", ln=2, align="C")
        
        test_pdf_path = Path("tests/temp_test_resume.pdf")
        pdf.output(str(test_pdf_path))
        
        # Read binary data
        pdf_data = test_pdf_path.read_bytes()
        
        # 2. Upload using FileManagerService
        from app.repositories.sqlite_repositories import SQLiteFileRepository, SQLiteWorkspaceRepository
        file_repo = SQLiteFileRepository(self.db)
        ws_repo = SQLiteWorkspaceRepository(self.db)
        
        svc = FileManagerService(file_repo, ws_repo)
        
        payload = svc.save_upload(
            workspace_id=ws_id,
            filename="Test_Resume.pdf",
            data=pdf_data,
            mime_type="application/pdf"
        )
        
        self.assertTrue(payload.get("id"))
        file_id = payload["id"]
        
        # 3. Retrieve row from database and check cached text
        row = self.db.query(ManagedFile).filter(ManagedFile.id == file_id).first()
        self.assertIsNotNone(row)
        self.assertIsNotNone(row.extracted_text)
        self.assertIn("Stephen Philip Kallarackal Resume Content", row.extracted_text)
        self.assertIn("Skills: Python, React, Business Analysis", row.extracted_text)
        print("Success: Native PDF parsed and text cached in database successfully.")
        
        # Clean up local temp file
        if test_pdf_path.exists():
            test_pdf_path.unlink()

    def test_02_context_builder_prompt_injection(self):
        print("\n--- Running Test 02: Context Builder Prompt Injection ---")
        # 1. Create a dummy file row manually in the DB with specific content to test cache hit
        import uuid
        file_id = str(uuid.uuid4())
        filename = "Stephen_Test_Attachment.pdf"
        cached_content = "[Vision context]\nOCR/text: This is a cached resume for Stephen Philip Kallarackal, Business Analyst."
        
        row = ManagedFile(
            id=file_id,
            workspace_id=self.workspace.id,
            file_name=filename,
            file_path=f"/api/files/{file_id}/content",
            mime_type="application/pdf",
            file_size=1000,
            extracted_text=cached_content
        )
        self.db.add(row)
        self.db.commit()
        
        # 2. Mock prompt message containing the attachment placeholder
        prompt = f"[Attached file: {filename} (1.0 KB, type=pdf). File is attached in the UI; use its name if generating related outputs.] What is Stephen's role?"
        
        # 3. Setup ExecutionContext
        from app.repositories.sqlite_repositories import SQLiteSettingRepository, SQLiteConversationRepository
        from memory.manager import MemoryManager
        
        setting_repo = SQLiteSettingRepository(self.db)
        conv_repo = SQLiteConversationRepository(self.db)
        
        # We need a conversation row
        from app.db import Conversation
        conv = Conversation(id=str(uuid.uuid4()), title="Test Chat", workspace_id=self.workspace.id)
        self.db.add(conv)
        self.db.commit()
        
        context = ExecutionContext(
            prompt=prompt,
            conversation={"id": conv.id, "project_id": None},
            capabilities=["chat"]
        )
        
        # 4. Invoke ContextBuilder
        from app.repositories.sqlite_repositories import SQLiteMemoryRepository
        mem_repo = SQLiteMemoryRepository(self.db)
        memory_manager = MemoryManager(mem_repo, conv_repo, setting_repo)
        
        builder = ContextBuilder(memory_manager)
        builder.build_context(context)
        
        # 5. Assert vision context is in system prompt
        system_prompt = context.execution_metadata.get("system_prompt", "")
        print(f"DEBUG - Generated System Prompt: {repr(system_prompt)}")
        print(f"DEBUG - Prompt: {repr(context.prompt)}")
        self.assertIsNotNone(system_prompt)
        self.assertIn("VISION ANALYSIS (UPLOADED FILE)", system_prompt)
        self.assertIn("This is a cached resume for Stephen Philip Kallarackal", system_prompt)
        print("Success: ContextBuilder correctly retrieved database cache and injected it into system prompt.")

    def test_03_truncation_limits(self):
        print("\n--- Running Test 03: Text Truncation Safety Limits ---")
        # 1. Create text with 10,000 characters
        large_text = "A" * 10000
        import uuid
        file_id = str(uuid.uuid4())
        filename = "Giant_File.txt"
        
        row = ManagedFile(
            id=file_id,
            workspace_id=self.workspace.id,
            file_name=filename,
            file_path=f"/api/files/{file_id}/content",
            mime_type="text/plain",
            file_size=10000,
            extracted_text=large_text
        )
        self.db.add(row)
        self.db.commit()
        
        # 2. Build context
        prompt = f"[Attached file: {filename} (10.0 KB, type=txt). File is attached in the UI; use its name if generating related outputs.] Summarize this."
        
        from app.repositories.sqlite_repositories import SQLiteSettingRepository, SQLiteConversationRepository, SQLiteMemoryRepository
        from memory.manager import MemoryManager
        
        setting_repo = SQLiteSettingRepository(self.db)
        conv_repo = SQLiteConversationRepository(self.db)
        mem_repo = SQLiteMemoryRepository(self.db)
        memory_manager = MemoryManager(mem_repo, conv_repo, setting_repo)
        
        context = ExecutionContext(
            prompt=prompt,
            conversation=None,
            capabilities=["chat"]
        )
        
        builder = ContextBuilder(memory_manager)
        builder.build_context(context)
        
        # 3. Check compiled prompt
        system_prompt = context.execution_metadata.get("system_prompt", "")
        self.assertIn("Content truncated to prevent model context window overflow", system_prompt)
        # Text should be truncated around 8000 characters
        self.assertTrue(len(system_prompt) < 12000)
        print("Success: Truncation limits successfully applied to prevent context window overflow.")

if __name__ == "__main__":
    unittest.main()
