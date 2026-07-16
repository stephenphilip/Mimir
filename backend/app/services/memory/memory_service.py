from typing import List, Dict, Any, Optional

from ...interfaces.services import IMemoryService
from ...interfaces.repositories import IMemoryRepository, IConversationRepository, ISettingRepository
from .storage import MemoryStorage
from .retrieval import MemoryRetrieval
from .ranking import MemoryRanking
from .injection import MemoryInjection

class MemoryService(IMemoryService):
    def __init__(
        self,
        memory_repo: IMemoryRepository,
        conversation_repo: IConversationRepository,
        setting_repo: ISettingRepository
    ):
        self.memory_repo = memory_repo
        self.conversation_repo = conversation_repo
        self.setting_repo = setting_repo
        
        self.storage = MemoryStorage(self.memory_repo)
        self.retrieval = MemoryRetrieval(self.storage)
        self.ranking = MemoryRanking()
        self.injection = MemoryInjection()

    def get_user_profile(self, user_id: int = 1) -> Dict[str, Any]:
        """Fetch user profile information."""
        memories = self.retrieval.retrieve_memories(user_id)
        ranked = self.ranking.rank_memories(memories)
        
        # Build profile dict
        profile = {m.key: m.value for m in ranked}
        
        # Get user's name
        name = self.memory_repo.get_user_name(user_id)
        if name:
            profile["name"] = name
        else:
            profile["name"] = "User"
            
        return profile

    def update_user_profile(self, key: str, value: str, user_id: int = 1) -> None:
        """Update or insert a profile key-value."""
        if key == "name":
            self.memory_repo.save_user_name(user_id, value)
        else:
            self.storage.save_memory(user_id, key, value)

    def get_settings(self) -> Dict[str, str]:
        """Fetch system settings."""
        return self.setting_repo.get_all()

    def set_setting(self, key: str, value: str) -> None:
        """Update a system setting."""
        self.setting_repo.save(key, value)

    def get_recent_context(self, conversation_id: str, limit: int = 10) -> List[Dict[str, Any]]:
        """Fetch conversation messages formatted as prompt context."""
        messages = self.conversation_repo.get_messages(conversation_id, limit=limit)
        return [{"role": m.sender, "content": m.content} for m in messages]
