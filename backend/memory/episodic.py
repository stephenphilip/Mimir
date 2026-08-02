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
        
        lines = ["## Past Conversation Summaries"]
        for ep in self.episodes:
            # Assuming ep is a db.EpisodicMemory instance or dict-like
            if isinstance(ep, dict):
                summary = ep.get('summary', '')
                topics = ep.get('topics', '')
            else:
                summary = getattr(ep, 'summary', '')
                topics = getattr(ep, 'topics', '')
            
            topics_str = f" (Topics: {topics})" if topics else ""
            lines.append(f"- {summary}{topics_str}")
        return "\n".join(lines)
