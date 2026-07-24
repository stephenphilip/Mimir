class EpisodicMemory:
    """
    EpisodicMemory — Summarized sessions of past conversations.
    
    Phase 3: Structural stub.
    Phase 6: Will be populated by an offline summarization agent.
    """
    
    def __init__(self, episodes: list = None):
        self.episodes = episodes or []
        
    def format_for_prompt(self) -> str:
        if not self.episodes:
            return ""
        return "\n".join(self.episodes)
