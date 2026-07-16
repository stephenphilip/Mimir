from typing import Dict, Any, List

from ..interfaces.services import IContextBuilder, IMemoryService
from ..core.context import ExecutionContext

class ContextBuilder(IContextBuilder):
    def __init__(self, memory_service: IMemoryService):
        self.memory_service = memory_service

    def build_context(self, context: ExecutionContext) -> None:
        """Retrieve settings, profile, and recent context history and build system/user prompts."""
        # 1. Retrieve User Profile & Memories
        user_id = 1  # Default MVP user ID
        profile = self.memory_service.get_user_profile(user_id)
        context.user = profile
        
        # Format memories from profile
        formatted_memories = []
        for key, value in profile.items():
            if key != "name":
                formatted_memories.append(f"{key}: {value}")
        context.retrieved_memories = [{"key": k, "value": v} for k, v in profile.items() if k != "name"]

        # 2. Retrieve Settings & Personality
        settings = self.memory_service.get_settings()
        personality = settings.get("personality", "helpful, concise assistant")
        user_name = profile.get("name", "User")
        
        # 3. Build System Prompt
        system_prompt = (
            f"You are a local AI personal assistant. Your name is Mimir.\n"
            f"User name: {user_name}.\n"
            f"Personality: {personality}.\n"
            f"Capabilities: You have access to {', '.join(context.capabilities)}.\n"
        )
        
        # Inject memory context if available
        if formatted_memories:
            system_prompt += "\nRetrieved user memories & profile facts:\n"
            system_prompt += "\n".join([f"- {m}" for m in formatted_memories]) + "\n"

        if "python_execution" in context.capabilities:
            system_prompt += (
                "\nIMPORTANT: To solve spreadsheet, csv, charts, or math tasks, you MUST write executable Python code inside a "
                "```python ... ``` code block. Use libraries like pandas, openpyxl, and matplotlib. "
                "All files generated MUST be saved directly to the current working directory. "
                "Provide brief, clean Python scripts that perform the entire task, then print a short success message. "
                "Do not explain the code too much; focus on writing correct python code that generates the files requested."
            )
            
        context.execution_metadata["system_prompt"] = system_prompt

        # 4. Retrieve recent conversation history context
        if context.conversation and "id" in context.conversation:
            conv_id = context.conversation["id"]
            recent_messages = self.memory_service.get_recent_context(conv_id, limit=6)
            context.retrieved_conversation_context = recent_messages
        else:
            recent_messages = []

        # 5. Build final User Prompt (combining history + current prompt)
        full_user_prompt = ""
        for msg in recent_messages:
            role_label = "User" if msg["role"] == "user" else "Assistant"
            full_user_prompt += f"{role_label}: {msg['content']}\n"
        full_user_prompt += f"User: {context.prompt}\nAssistant:"
        
        context.execution_metadata["user_prompt"] = full_user_prompt
