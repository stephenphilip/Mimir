class MemoryInjection:
    def format_memories(self, memories: list) -> str:
        # Format list of memory records into context lines.
        lines = []
        for m in memories:
            lines.append(f"- {getattr(m, 'key', '')}: {getattr(m, 'value', '')}")
        return "\n".join(lines)
