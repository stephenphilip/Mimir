from ...interfaces.repositories import IMemoryRepository

class MemoryStorage:
    def __init__(self, memory_repo: IMemoryRepository):
        self.memory_repo = memory_repo

    def save_memory(self, user_id: int, key: str, value: str) -> None:
        self.memory_repo.save(user_id, key, value)

    def get_memories(self, user_id: int) -> list:
        return self.memory_repo.get_all_by_user(user_id)
