from typing import List, Dict, Any, Optional

from app.interfaces.services import IMemoryService
from app.interfaces.repositories import IMemoryRepository, IConversationRepository, ISettingRepository, IEpisodicRepository, IEntityRepository

from memory.conversation import ConversationMemory, ConversationTurn
from memory.project import ProjectMemory
from memory.entity import EntityMemory
from memory.episodic import EpisodicMemory
from memory.semantic import SemanticMemory

class MemoryManager(IMemoryService):
    """
    MemoryManager — Orchestrates the layered memory system.
    
    Replaces the legacy MemoryService.
    """

    def __init__(
        self,
        memory_repo: IMemoryRepository,
        conversation_repo: IConversationRepository,
        setting_repo: ISettingRepository,
        episodic_repo: Optional['IEpisodicRepository'] = None,
        entity_repo: Optional['IEntityRepository'] = None,
    ):
        self.memory_repo = memory_repo
        self.conversation_repo = conversation_repo
        self.setting_repo = setting_repo
        self.episodic_repo = episodic_repo
        self.entity_repo = entity_repo

    def get_user_profile(self, user_id: int = 1) -> Dict[str, Any]:
        """Fetch user profile information."""
        memories = self.memory_repo.get_all_by_user(user_id)
        
        profile = {m.key: m.value for m in memories}

        name = self.memory_repo.get_user_name(user_id)
        if name:
            profile["name"] = name
        else:
            profile["name"] = "User"

        return profile
        
    def get_entity_memory(self, user_id: int = 1) -> EntityMemory:
        """Returns the user profile and extracted entities as a typed EntityMemory layer."""
        profile = self.get_user_profile(user_id)
        entities = []
        if self.entity_repo:
            entities = self.entity_repo.get_all_by_user(user_id)
        return EntityMemory(entities=entities, profile=profile)

    def update_user_profile(self, key: str, value: str, user_id: int = 1) -> None:
        """Update or insert a profile key-value."""
        if key == "name":
            self.memory_repo.save_user_name(user_id, value)
        else:
            self.memory_repo.save(user_id, key, value)

    def get_settings(self) -> Dict[str, str]:
        """Fetch system settings."""
        return self.setting_repo.get_all()

    def set_setting(self, key: str, value: str) -> None:
        """Update a system setting."""
        self.setting_repo.save(key, value)

    def get_recent_context(self, conversation_id: str, limit: int = 10) -> List[Dict[str, Any]]:
        """Fetch conversation messages formatted as prompt context (Legacy support)."""
        messages = self.conversation_repo.get_messages(conversation_id, limit=limit)
        return [{"role": m.sender, "content": m.content} for m in messages]
        
    def get_conversation_memory(self, conversation_id: str, limit: int = 10) -> ConversationMemory:
        """Returns recent messages as a typed ConversationMemory layer."""
        messages = self.conversation_repo.get_messages(conversation_id, limit=limit)
        return ConversationMemory.from_messages(messages)

    def get_shared_project_context(self, project_id: str, current_conv_id: str, limit_per_chat: int = 2) -> List[Dict[str, Any]]:
        """Legacy shared project context."""
        other_convs = self.conversation_repo.get_by_project(project_id)
        shared = []
        for conv in other_convs:
            if conv.id == current_conv_id:
                continue
            
            messages = self.conversation_repo.get_messages(conv.id, limit=limit_per_chat)
            if messages:
                chat_context = []
                for m in messages:
                    chat_context.append({"role": m.sender, "content": m.content})
                shared.append({
                    "conversation_title": conv.title,
                    "messages": chat_context
                })
        return shared
        
    def get_project_memory(self, project_id: str, current_conv_id: str, limit_per_chat: int = 2) -> ProjectMemory:
        """Returns shared project context as a typed ProjectMemory layer."""
        shared = self.get_shared_project_context(project_id, current_conv_id, limit_per_chat)
        return ProjectMemory(shared)
        
    def get_episodic_memory(self, user_id: int = 1, limit: int = 5) -> EpisodicMemory:
        """Returns episodic memory from recent conversations."""
        episodes = []
        if self.episodic_repo:
            episodes = self.episodic_repo.get_recent_by_user(user_id, limit=limit)
        return EpisodicMemory(episodes)
        
    def get_semantic_memory(self, user_id: int = 1, query: str = "") -> SemanticMemory:
        """Returns semantic memory (Phase 6 keyword stub)."""
        # A full RAG implementation would use ISemanticRepository
        return SemanticMemory([])

    def compact_conversation(self, conversation_id: str) -> None:
        """
        Compacts the conversation history by deleting older neutral messages,
        while ensuring that pinned messages are preserved.
        """
        messages = self.conversation_repo.get_messages(conversation_id)
        if len(messages) <= 10:
            return
            
        # Keep the latest 10 messages and any pinned messages. Delete the rest.
        latest_ids = {m.id for m in messages[-10:]}
        for msg in messages[:-10]:
            is_pinned = getattr(msg, "is_pinned", 0)
            if not is_pinned and msg.id not in latest_ids:
                self.conversation_repo.db.delete(msg)
                
        self.conversation_repo.db.commit()

# Export MemoryManager
__all__ = ["MemoryManager"]
