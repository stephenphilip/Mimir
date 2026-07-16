class MemoryRanking:
    def rank_memories(self, memories: list, query: str = None) -> list:
        # Sort by created_at descending (most recent first) if created_at attribute is present
        try:
            return sorted(memories, key=lambda m: getattr(m, 'created_at', None) or 0, reverse=True)
        except Exception:
            return memories
