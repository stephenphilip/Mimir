from abc import ABC, abstractmethod
from typing import List, Optional, Any, Dict

class IConversationRepository(ABC):
    @abstractmethod
    def get_by_id(self, conv_id: str) -> Optional[Any]:
        """Fetch conversation by ID."""
        pass

    @abstractmethod
    def create(self, conv_id: str, title: str, user_id: int, project_id: Optional[str] = None) -> Any:
        """Create a new conversation."""
        pass

    @abstractmethod
    def update_project(self, conv_id: str, project_id: Optional[str]) -> None:
        """Associate conversation with a project."""
        pass

    @abstractmethod
    def get_by_project(self, project_id: str) -> List[Any]:
        """Fetch all conversations associated with a project."""
        pass

    @abstractmethod
    def delete(self, conv_id: str) -> bool:
        """Delete a conversation."""
        pass

    @abstractmethod
    def get_all(self) -> List[Any]:
        """Get all conversations."""
        pass

    @abstractmethod
    def update_title(self, conv_id: str, title: str) -> None:
        """Update conversation title."""
        pass

    @abstractmethod
    def get_messages(self, conv_id: str, limit: Optional[int] = None) -> List[Any]:
        """Get messages for a conversation."""
        pass

    @abstractmethod
    def add_message(self, conv_id: str, sender: str, content: str, tokens_count: int = 0) -> Any:
        """Add message to a conversation."""
        pass

class IMemoryRepository(ABC):
    @abstractmethod
    def get_by_key(self, user_id: int, key: str) -> Optional[Any]:
        """Get memory by user and key."""
        pass

    @abstractmethod
    def get_all_by_user(self, user_id: int) -> List[Any]:
        """Get all memory records for a user."""
        pass

    @abstractmethod
    def save(self, user_id: int, key: str, value: str) -> Any:
        """Create or update a memory record."""
        pass

    @abstractmethod
    def get_user_name(self, user_id: int) -> Optional[str]:
        """Get user's name by ID."""
        pass

    @abstractmethod
    def save_user_name(self, user_id: int, name: str) -> None:
        """Save user's name by ID."""
        pass

class IModelRepository(ABC):
    @abstractmethod
    def get_by_name(self, name: str) -> Optional[Any]:
        """Get model configuration by name."""
        pass

    @abstractmethod
    def get_all_installed(self) -> List[Any]:
        """Get all installed models."""
        pass

    @abstractmethod
    def save_installed(self, name: str, status: str, size: str, local_path: Optional[str] = None) -> Any:
        """Save/Update installed model status."""
        pass

    @abstractmethod
    def delete_by_name(self, name: str) -> bool:
        """Delete an installed model entry."""
        pass

    @abstractmethod
    def get_download(self, model_name: str) -> Optional[Any]:
        """Get download details by model name."""
        pass

    @abstractmethod
    def get_all_downloads(self) -> List[Any]:
        """Get all active/completed download tasks."""
        pass

    @abstractmethod
    def save_download(self, model_name: str, progress: float, status: str, error: Optional[str] = None) -> Any:
        """Save/Update download task state."""
        pass

    @abstractmethod
    def refresh(self) -> None:
        """Refresh database state (clear cache)."""
        pass

class IArtifactRepository(ABC):
    @abstractmethod
    def create(
        self,
        message_id: Optional[int],
        file_name: str,
        file_path: str,
        file_type: str,
        file_size: int,
        artifact_uuid: Optional[str] = None,
        mime_type: Optional[str] = None,
        provider: Optional[str] = None,
        workspace_id: Optional[str] = None,
        status: str = "ready",
        thumbnail_path: Optional[str] = None,
        original_prompt: Optional[str] = None,
        enhanced_prompt: Optional[str] = None,
        execution_plan_json: Optional[str] = None,
        model_name: Optional[str] = None,
        intelligence_json: Optional[str] = None,
        version: int = 1,
        validation_status: Optional[str] = None,
    ) -> Any:
        """Record a generated artifact."""
        pass

    @abstractmethod
    def update_intelligence(self, artifact_uuid: str, intelligence: Dict[str, Any]) -> Optional[Any]:
        """Attach or update artifact intelligence metadata."""
        pass

    @abstractmethod
    def get_by_id(self, artifact_id: int) -> Optional[Any]:
        pass

    @abstractmethod
    def get_by_uuid(self, artifact_uuid: str) -> Optional[Any]:
        pass

    @abstractmethod
    def get_by_message_id(self, message_id: int) -> List[Any]:
        """Get all artifacts linked to a message."""
        pass

    @abstractmethod
    def list_all(
        self,
        workspace_id: Optional[str] = None,
        artifact_type: Optional[str] = None,
        limit: int = 100,
    ) -> List[Any]:
        pass

    @abstractmethod
    def count_by_workspace(self, workspace_id: str) -> int:
        pass

    @abstractmethod
    def save_execution_history(
        self,
        command: str,
        code_content: str,
        stdout: Optional[str],
        stderr: Optional[str],
        exit_code: Optional[int]
    ) -> Any:
        """Save an execution log record."""
        pass

class ISettingRepository(ABC):
    @abstractmethod
    def get_all(self) -> Dict[str, str]:
        """Get all system settings as a dictionary."""
        pass

    @abstractmethod
    def get_by_key(self, key: str) -> Optional[str]:
        """Get a setting value by key."""
        pass

    @abstractmethod
    def save(self, key: str, value: str) -> Any:
        """Save or update system setting."""
        pass

class IModelCatalogRepository(ABC):
    @abstractmethod
    def get_by_name(self, name: str) -> Optional[Any]:
        """Fetch model by name."""
        pass

    @abstractmethod
    def get_all_active(self) -> List[Any]:
        """Fetch all active models in catalog."""
        pass

    @abstractmethod
    def save_master_model(
        self,
        name: str,
        base_name: str,
        parameter_size: float,
        file_size_gb: float,
        required_ram_gb: float,
        required_vram_gb: float,
        total_layers: int,
        score_reasoning: float,
        score_coding: float,
        score_math: float,
        score_conversational: float,
        tps_cpu: float,
        tps_gpu: float,
        is_active: int = 1
    ) -> Any:
        """Create or update model specification in catalog."""
        pass

    @abstractmethod
    def delete_by_name(self, name: str) -> bool:
        """Deactivate or remove model from catalog."""
        pass

class IEpisodicRepository(ABC):
    @abstractmethod
    def get_recent_by_user(self, user_id: int, limit: int = 5) -> List[Any]:
        """Fetch recent episodic memories for a user."""
        pass

    @abstractmethod
    def save(self, user_id: int, conversation_id: str, summary: str, topics: Optional[str] = None) -> Any:
        """Create an episodic memory record."""
        pass

class IEntityRepository(ABC):
    @abstractmethod
    def get_by_name(self, user_id: int, entity_name: str) -> Optional[Any]:
        """Fetch an entity by name."""
        pass

    @abstractmethod
    def get_all_by_user(self, user_id: int) -> List[Any]:
        """Fetch all entities for a user."""
        pass

    @abstractmethod
    def save(self, user_id: int, entity_name: str, entity_type: str, description: Optional[str] = None, attributes: Optional[str] = None) -> Any:
        """Create or update an entity memory record."""
        pass

class ISemanticRepository(ABC):
    @abstractmethod
    def search(self, user_id: int, query: str, limit: int = 5) -> List[Any]:
        """Search semantic memories."""
        pass

    @abstractmethod
    def save(self, user_id: int, content: str, source_id: Optional[str] = None) -> Any:
        """Create a semantic memory record."""
        pass
