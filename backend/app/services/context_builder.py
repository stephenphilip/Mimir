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
        )

        if formatted_memories:
            system_prompt += "\nRetrieved user memories & profile facts:\n"
            system_prompt += "\n".join([f"- {m}" for m in formatted_memories]) + "\n"

        if "python_execution" in context.capabilities:
            system_prompt += (
                "\nIMPORTANT: To solve spreadsheet, csv, charts, pdf, document, workout plan, or math tasks, "
                "you MUST write executable Python code inside a ```python ... ``` code block. "
                "For PDFs use the fpdf library (from fpdf import FPDF). "
                "For Excel use pandas/openpyxl. For charts use matplotlib. "
                "All files MUST be saved to the current working directory with real filenames "
                "(e.g. leg_day_workout.pdf, expense_tracker.xlsx). "
                "Do NOT refuse to generate PDFs or documents — create them with code. "
                "Print a short success message listing the exact filenames created. "
                "NEVER write fake placeholders such as [Download PDF] — the UI shows download cards automatically. "
                "Keep commentary brief; prioritize correct working code."
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

        full_user_prompt = (
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
