from typing import List, Dict, Any

class ProjectMemory:
    """
    ProjectMemory — shared context across conversations within the same project.
    
    Phase 3: Extracts the shared project context logic out of ContextBuilder.
    Phase 6: Will be enhanced with summarized cross-project semantic extraction.
    """

    def __init__(self, shared_chats: List[Dict[str, Any]]):
        self.shared_chats = shared_chats

    def format_for_prompt(self, max_chars_per_turn: int = 500) -> str:
        """
        Format shared project conversations into a prompt-ready string.
        """
        if not self.shared_chats:
            return ""

        lines = ["=== SHARED PROJECT KNOWLEDGE (from other chats in this project) ==="]
        
        for chat in self.shared_chats:
            title = chat.get("conversation_title", "Untitled Chat")
            lines.append(f'Chat: "{title}"')
            for m in chat.get("messages", []):
                role = "User" if m.get("role") == "user" else "Assistant"
                content = (m.get("content") or "").strip()
                if len(content) > max_chars_per_turn:
                    content = content[:max_chars_per_turn] + "..."
                lines.append(f"  {role}: {content}")
                
        lines.append("===================================================================")
        return "\n".join(lines)
