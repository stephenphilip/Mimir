from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional


class IWorkspaceRepository(ABC):
    @abstractmethod
    def get_all(self) -> List[Any]:
        pass

    @abstractmethod
    def get_by_id(self, workspace_id: str) -> Optional[Any]:
        pass

    @abstractmethod
    def get_default(self) -> Optional[Any]:
        pass

    @abstractmethod
    def create(self, workspace_id: str, name: str, model: Optional[str] = None) -> Any:
        pass

    @abstractmethod
    def update(self, workspace_id: str, name: Optional[str] = None, model: Optional[str] = None) -> Optional[Any]:
        pass

    @abstractmethod
    def delete(self, workspace_id: str) -> bool:
        pass


class IFileRepository(ABC):
    @abstractmethod
    def create(
        self,
        file_id: str,
        workspace_id: str,
        file_name: str,
        file_path: str,
        mime_type: str,
        file_size: int,
        source: str = "upload",
        pinned: bool = False,
    ) -> Any:
        pass

    @abstractmethod
    def get_by_id(self, file_id: str) -> Optional[Any]:
        pass

    @abstractmethod
    def list_files(
        self,
        workspace_id: Optional[str] = None,
        category: Optional[str] = None,
        search: Optional[str] = None,
        pinned_only: bool = False,
        limit: int = 200,
    ) -> List[Any]:
        pass

    @abstractmethod
    def update(
        self,
        file_id: str,
        file_name: Optional[str] = None,
        pinned: Optional[bool] = None,
        extracted_text: Optional[str] = None,
    ) -> Optional[Any]:
        pass

    @abstractmethod
    def delete(self, file_id: str) -> bool:
        pass
