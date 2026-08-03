from typing import Dict, Any, List
import json

from ..interfaces.services import IContextBuilder, IMemoryService
from ..core.context import ExecutionContext

from memory.prompt_builder import PromptBuilder, PromptSection
from memory.manager import MemoryManager

class ContextBuilder(IContextBuilder):
    def __init__(self, memory_service: IMemoryService):
        # We know pipeline_factory injects MemoryManager here
        self.memory_manager: MemoryManager = memory_service

    def build_context(self, context: ExecutionContext) -> None:
        """Retrieve memory layers and build system/user prompts using PromptBuilder."""
        
        # 1. Detect attached files and extract text / vision content
        import re
        from pathlib import Path
        from config.paths import get_paths
        from app.db import ManagedFile
        from app.services.vision_service import VisionService

        pattern = r"\[Attached file:\s*(.+?)\s*\(\d+(?:\.\d+)?\s*(?:B|KB|MB|GB),\s*type=(.+?)\)\.\s*File is attached in the UI;\s*use its name if generating related outputs\.\]"
        matches = re.findall(pattern, context.prompt)

        vision_contexts = []
        db = None
        if hasattr(self.memory_manager.setting_repo, "db"):
            db = self.memory_manager.setting_repo.db

        if db and matches:
            for filename, file_type in matches:
                # Find the file in ManagedFile table
                row = db.query(ManagedFile).filter(ManagedFile.file_name == filename).order_by(ManagedFile.created_at.desc()).first()
                if not row:
                    continue
                
                # Check database cache first!
                if hasattr(row, "extracted_text") and row.extracted_text:
                    txt = row.extracted_text
                    if len(txt) > 8000:
                        txt = txt[:8000] + "\n... [Content truncated to prevent model context window overflow] ..."
                    vision_contexts.append(txt)
                    continue

                # Resolve physical disk path
                uploads_dir = get_paths().workspace_dir / ".mimir" / "uploads"
                disk_matches = list(uploads_dir.glob(f"{row.id}_*"))
                disk_path = disk_matches[0] if disk_matches else None
                
                if disk_path and disk_path.is_file():
                    if file_type.lower() in ("pdf", "png", "jpg", "jpeg", "webp") or row.mime_type.startswith("image/"):
                        try:
                            # Run Vision Service analysis (which uses OCR/pypdf)
                            vision_res = VisionService().analyze_file(str(disk_path), mime_type=row.mime_type)
                            if vision_res.get("success") and vision_res.get("context"):
                                txt = vision_res["context"]
                                if len(txt) > 8000:
                                    txt = txt[:8000] + "\n... [Content truncated to prevent model context window overflow] ..."
                                vision_contexts.append(txt)
                                try:
                                    row.extracted_text = vision_res["context"]
                                    db.commit()
                                except Exception:
                                    pass
                        except Exception as e:
                            print(f"Error analyzing attached file {filename}: {e}")
                    else:
                        # For text-like files, read directly
                        try:
                            file_content = disk_path.read_text(encoding="utf-8", errors="replace")
                            text_ctx = f"--- Content of uploaded file: {filename} ---\n{file_content}\n--- End of file: {filename} ---"
                            txt = text_ctx
                            if len(txt) > 8000:
                                txt = txt[:8000] + "\n... [Content truncated to prevent model context window overflow] ..."
                            vision_contexts.append(txt)
                            try:
                                row.extracted_text = text_ctx
                                db.commit()
                            except Exception:
                                pass
                        except Exception as e:
                            print(f"Error reading text of attached file {filename}: {e}")

        if vision_contexts:
            context.execution_metadata["vision_context"] = "\n\n".join(vision_contexts)

        # 1. Fetch memory layers
        user_id = 1 # Hardcoded for local MVP
        conv_id = context.conversation.get("id") if context.conversation else None
        project_id = context.conversation.get("project_id") if context.conversation else None
        
        entity_mem = self.memory_manager.get_entity_memory(user_id)
        episodic_mem = self.memory_manager.get_episodic_memory(user_id)
        semantic_mem = self.memory_manager.get_semantic_memory(user_id, query=context.prompt)
        
        # Populate context objects for downstream use
        context.user = entity_mem.profile
        context.retrieved_memories = [{"key": k, "value": v} for k, v in entity_mem.profile.items() if k != "name"]

        settings = self.memory_manager.get_settings()
        personality = settings.get("personality", "helpful, concise assistant")
        user_name = entity_mem.profile.get("name", "User")
        
        # 2. Build the structured Prompt
        builder = PromptBuilder()
        
        # Core Identity
        core_identity = (
            f"You are a local AI personal assistant. Your name is Mimir.\n"
            f"User name: {user_name}.\n"
            f"Personality: {personality}."
        )
        builder.add_section(PromptSection.CORE_IDENTITY, core_identity)
        
        # Capabilities & Tools (Phase 5: Structured Tool Invocation)
        from tools.registry import ToolRegistry
        from runtime.runtime_coordinator import get_runtime
        
        registry = ToolRegistry(get_runtime().plugin_loader)
        available_tools = registry.list_tools()
        
        active_tools = []
        for cap in context.capabilities:
            for t in available_tools:
                if t.get("capability") == cap and "schema" in t:
                    active_tools.append({
                        "tool": t.get("name"),
                        "description": t.get("description", ""),
                        "parameters": t.get("schema")
                    })
                    
        if active_tools:
            caps = f"Capabilities: You have access to {', '.join(context.capabilities)}.\n\n"
            caps += "You have access to the following structured tools:\n"
            caps += json.dumps(active_tools, indent=2)
            caps += "\n\nTo invoke a tool, output a structured JSON block matching this EXACT format:\n"
            caps += "```json\n{\n  \"tool\": \"<tool_name>\",\n  \"parameters\": { ... }\n}\n```\n"
            caps += "You MUST output the full JSON block in your response. The tool will be executed automatically."
        else:
            caps = f"Capabilities: You have access to {', '.join(context.capabilities)}."
            
        builder.add_section(PromptSection.CAPABILITIES, caps)
        
        # Critical Rules
        rules = (
            "CRITICAL RULES:\n"
            "- Answer the LATEST user message only.\n"
            "- Earlier turns are background context — do NOT reuse old refusals or old topics "
            "when the user changed the subject.\n"
            "- If the latest question is unrelated to previous messages, ignore the old topic completely.\n"
            "- Be direct and helpful. Prefer action (code/files) over declining when tools are available.\n"
            "- STRICT ENTITY PRESERVATION: Identify all character names, subjects, and key nouns "
            "in the user's request (e.g. 'tortoise', 'rabbit'). You MUST preserve these exact names "
            "throughout your response text, stories, and code. Do NOT substitute or blend them with "
            "synonyms or other fables (e.g. do NOT change 'tortoise' to 'hare' or 'turtle', do NOT change "
            "'rabbit' to 'hare').\n"
        )
        workflow = context.execution_metadata.get("workflow") or "chat"

        if workflow == "structured_document":
            rules += (
                "\nIMPORTANT — DOCUMENT WORKFLOW:\n"
                "You generate DOCUMENT CONTENT ONLY as JSON. Do NOT write Python. Do NOT use fpdf.\n"
                "The platform will render PDF/DOCX/Markdown from your JSON.\n"
                "Return ONLY valid JSON with this shape:\n"
                '{"title":"...","summary":"...","sections":[{"heading":"...","body":"...","bullets":["..."]}]}\n'
                "Fill sections with real useful content for the user's request. "
                "No fake download links. No code fences required but allowed."
            )
        elif "python_execution" in context.capabilities or "python" in context.capabilities:
            rules += (
                "\nIMPORTANT PROTOCOL FOR CREATING DOCUMENTS/SPREADSHEETS/FILES:\n"
                "If the user asks you to create a file (such as a PDF, Excel sheet, Word doc, chart, etc.):\n"
                "1. PLAN FIRST: Write a brief, numbered task list of the steps you will take "
                "(e.g., '1. Draft the story text. 2. Write the PDF formatting code. 3. Compile and save the PDF.').\n"
                "2. CREATE CONTENT: Write out the full drafted content (e.g., the complete story, table data, or outline) "
                "directly in your response text so the user can read it first.\n"
                "3. COMPILE CODE: Write the complete, executable Python code block that embeds the entire content "
                "(no placeholders) and saves the file to the current working directory. "
                "Use fpdf2 for PDFs (from fpdf import FPDF), openpyxl/pandas for Excel/CSVs, "
                "python-docx for Word files, and matplotlib for charts.\n"
                "4. CONFIRM SUCCESS: Print a short confirmation message stating the exact filename created."
            )
        elif workflow == "image":
            rules += (
                "\nIMPORTANT — IMAGE WORKFLOW:\n"
                "Describe the image to generate briefly. The platform handles image providers. "
                "Do not invent download URLs."
            )

        builder.add_section(PromptSection.CRITICAL_RULES, rules)

        # Inject vision analysis when an image/PDF was uploaded
        vision_ctx = context.execution_metadata.get("vision_context")
        if vision_ctx:
            builder.add_section(PromptSection.USER_PROFILE, vision_ctx, title="Vision Analysis (uploaded file)")

        # User Profile (Entity Memory)
        builder.add_section(PromptSection.USER_PROFILE, entity_mem.format_for_prompt(), title="Retrieved user memories & profile facts")

        # Working Memory
        if hasattr(context, "working_memory") and context.working_memory:
            builder.add_section(PromptSection.WORKING_MEMORY, context.working_memory.format_for_prompt(), title="Working Memory (Current Task State)")

        # Episodic Memory
        builder.add_section(PromptSection.EPISODIC_MEMORY, episodic_mem.format_for_prompt(), title="Past Session Summaries")

        # Project Context
        if project_id and conv_id:
            project_mem = self.memory_manager.get_project_memory(project_id, conv_id, limit_per_chat=2)
            builder.add_section(PromptSection.SHARED_PROJECT_CONTEXT, project_mem.format_for_prompt())

        # Conversation History
        if conv_id:
            conv_mem = self.memory_manager.get_conversation_memory(conv_id, limit=6)
            conv_mem.apply_budget(max_turns=4, exclude_last_if_matches=context.prompt)
            builder.add_section(PromptSection.CONVERSATION_HISTORY, conv_mem.format_for_prompt())
            context.retrieved_conversation_context = conv_mem.as_dicts()
        else:
            context.retrieved_conversation_context = []
            
        # Latest Prompt
        latest_msg = f"---\nLatest user message (ANSWER THIS):\nUser: {context.prompt}\nAssistant:"
        builder.add_section(PromptSection.LATEST_USER_MESSAGE, latest_msg)

        # 3. Finalize Prompt
        final_prompt = builder.build()
        context.execution_metadata["system_prompt"] = final_prompt
        # For backwards compatibility with Orchestrator, we set user_prompt to empty since we unified it 
        # (Actually, we need to split it for some providers that strictly require a distinct user message,
        # but the prompt builder puts it all in one block. The Orchester expects 'system_prompt' and 'user_prompt'.
        # We will put the LATEST_USER_MESSAGE into user_prompt and the rest into system_prompt to be safe).
        
        # Let's rebuild by keeping LATEST_USER_MESSAGE and CONVERSATION_HISTORY separated to avoid breaking provider chat formatting
        # Actually, let's just do exactly that.
        
        # To avoid breaking existing Orchester flow, we will extract LATEST_USER_MESSAGE out.
        # Wait, the best way is to let PromptBuilder build everything up to EPISODIC_MEMORY as system_prompt
        # and Project, Conversation, Latest into user_prompt.
        
        system_builder = PromptBuilder()
        system_builder.add_section(PromptSection.CORE_IDENTITY, core_identity)
        system_builder.add_section(PromptSection.CAPABILITIES, caps)
        system_builder.add_section(PromptSection.CRITICAL_RULES, rules)
        system_builder.add_section(PromptSection.USER_PROFILE, entity_mem.format_for_prompt(), title="Retrieved user memories & profile facts")
        if hasattr(context, "working_memory") and context.working_memory:
            system_builder.add_section(PromptSection.WORKING_MEMORY, context.working_memory.format_for_prompt(), title="Working Memory (Current Task State)")
        system_builder.add_section(PromptSection.EPISODIC_MEMORY, episodic_mem.format_for_prompt(), title="Past Session Summaries")
        
        context.execution_metadata["system_prompt"] = system_builder.build()
        
        user_builder = PromptBuilder()
        if project_id and conv_id:
            project_mem = self.memory_manager.get_project_memory(project_id, conv_id, limit_per_chat=2)
            user_builder.add_section(PromptSection.SHARED_PROJECT_CONTEXT, project_mem.format_for_prompt())
            
        if conv_id:
            user_builder.add_section(PromptSection.CONVERSATION_HISTORY, conv_mem.format_for_prompt())
            
        user_builder.add_section(PromptSection.LATEST_USER_MESSAGE, latest_msg)
        
        context.execution_metadata["user_prompt"] = user_builder.build()
