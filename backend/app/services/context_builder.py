from typing import Dict, Any, List

from ..interfaces.services import IContextBuilder, IMemoryService
from ..core.context import ExecutionContext


class ContextBuilder(IContextBuilder):
    def __init__(self, memory_service: IMemoryService):
        self.memory_service = memory_service

    def build_context(self, context: ExecutionContext) -> None:
        """Retrieve settings, profile, and recent context history and build system/user prompts."""
        user_id = 1
        profile = self.memory_service.get_user_profile(user_id)
        context.user = profile

        formatted_memories = []
        for key, value in profile.items():
            if key != "name":
                formatted_memories.append(f"{key}: {value}")
        context.retrieved_memories = [{"key": k, "value": v} for k, v in profile.items() if k != "name"]

        settings = self.memory_service.get_settings()
        personality = settings.get("personality", "helpful, concise assistant")
        user_name = profile.get("name", "User")

        system_prompt = (
            f"You are a local AI personal assistant. Your name is Mimir.\n"
            f"User name: {user_name}.\n"
            f"Personality: {personality}.\n"
            f"Capabilities: You have access to {', '.join(context.capabilities)}.\n"
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

        if formatted_memories:
            system_prompt += "\nRetrieved user memories & profile facts:\n"
            system_prompt += "\n".join([f"- {m}" for m in formatted_memories]) + "\n"

        if "python_execution" in context.capabilities:
            system_prompt += (
                "\nIMPORTANT PROTOCOL FOR CREATING DOCUMENTS/SPREADSHEETS/FILES:\n"
                "If the user asks you to create a file (such as a PDF, Excel sheet, Word doc, chart, etc.):\n"
                "1. PLAN FIRST: Write a brief, numbered task list of the steps you will take "
                "(e.g., '1. Draft the story text. 2. Write the PDF formatting code. 3. Compile and save the PDF.').\n"
                "2. CREATE CONTENT: Write out the full drafted content (e.g., the complete story, table data, or outline) "
                "directly in your response text so the user can read it first.\n"
                "3. COMPILE CODE: Write the complete, executable Python code block (wrapped in ```python ... ```) "
                "that embeds the entire content (no placeholders, no truncated text) and saves the file to the current "
                "working directory. Use fpdf2 for PDFs (from fpdf import FPDF), openpyxl/pandas for Excel/CSVs, "
                "python-docx for Word files, and matplotlib for charts.\n"
                "4. CONFIRM SUCCESS: Print a short confirmation message stating the exact filename created.\n"
                "Always generate the full content inside both the message text and the code block. Never use placeholders "
                "like '# add rest of story here' or '[Download PDF]'."
            )

        context.execution_metadata["system_prompt"] = system_prompt

        if context.conversation and "id" in context.conversation:
            conv_id = context.conversation["id"]
            recent_messages = self.memory_service.get_recent_context(conv_id, limit=6)
            # The orchestrator already saved the current user turn — drop it so we don't
            # duplicate the latest prompt (a major cause of stuck/repeated answers).
            current = (context.prompt or "").strip()
            if (
                recent_messages
                and recent_messages[-1].get("role") == "user"
                and (recent_messages[-1].get("content") or "").strip() == current
            ):
                recent_messages = recent_messages[:-1]
            # Keep at most 2 prior turns (4 messages) for focus + speed
            recent_messages = recent_messages[-4:]
            context.retrieved_conversation_context = recent_messages
        else:
            recent_messages = []

        shared_project_context = ""
        project_id = context.conversation.get("project_id") if context.conversation else None
        if project_id and conv_id:
            try:
                shared = self.memory_service.get_shared_project_context(project_id, conv_id, limit_per_chat=2)
                if shared:
                    shared_project_context += "=== SHARED PROJECT KNOWLEDGE (from other chats in this project) ===\n"
                    for chat in shared:
                        shared_project_context += f"Chat: \"{chat['conversation_title']}\"\n"
                        for m in chat["messages"]:
                            role = "User" if m["role"] == "user" else "Assistant"
                            content = (m["content"] or "").strip()
                            if len(content) > 500:
                                content = content[:500] + "..."
                            shared_project_context += f"  {role}: {content}\n"
                    shared_project_context += "===================================================================\n\n"
            except Exception as e:
                print(f"Error fetching shared project context: {e}")

        full_user_prompt = ""
        if shared_project_context:
            full_user_prompt += shared_project_context

        full_user_prompt += (
            "Conversation so far (for context only).\n"
            "Respond ONLY to the final user message below.\n\n"
        )
        for msg in recent_messages:
            role_label = "User" if msg["role"] == "user" else "Assistant"
            content = (msg.get("content") or "").strip()
            if len(content) > 1200:
                content = content[:1200] + "…"
            full_user_prompt += f"{role_label}: {content}\n"

        full_user_prompt += (
            f"\n---\nLatest user message (ANSWER THIS):\nUser: {context.prompt}\nAssistant:"
        )

        context.execution_metadata["user_prompt"] = full_user_prompt
