"""
Memory service interfaces.

Extracted from interfaces/services.py for clarity.
All imports from interfaces/services.py continue to work (it re-exports these).

IMemoryService defines the contract that MemoryService (Phase 1) and
MemoryManager (Phase 3) must implement. Keeping this in a dedicated file
makes it easy to reference when building the Phase 3 layered memory system.
"""

from abc import ABC, abstractmethod
from typing import Any, Dict, List


class IMemoryService(ABC):
    @abstractmethod
    def get_user_profile(self, user_id: int = 1) -> Dict[str, Any]:
        """Fetch user profile information."""

    @abstractmethod
    def update_user_profile(self, key: str, value: str, user_id: int = 1) -> None:
        """Update or insert a profile key-value."""

    @abstractmethod
    def get_settings(self) -> Dict[str, str]:
        """Fetch system settings."""

    @abstractmethod
    def set_setting(self, key: str, value: str) -> None:
        """Update a system setting."""

    @abstractmethod
    def get_recent_context(self, conversation_id: str, limit: int = 10) -> List[Dict[str, Any]]:
        """Fetch conversation messages formatted as prompt context."""

    @abstractmethod
    def get_shared_project_context(
        self,
        project_id: str,
        current_conv_id: str,
        limit_per_chat: int = 2,
    ) -> List[Dict[str, Any]]:
        """Fetch recent message pairs from other chats in the same project."""
