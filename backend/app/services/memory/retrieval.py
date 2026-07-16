from .storage import MemoryStorage

class MemoryRetrieval:
    def __init__(self, storage: MemoryStorage):
        self.storage = storage

    def retrieve_memories(self, user_id: int, query: str = None) -> list:
        # Retrieve all user memories for this user.
        return self.storage.get_memories(user_id)
