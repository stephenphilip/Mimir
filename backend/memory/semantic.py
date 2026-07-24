class SemanticMemory:
    """
    SemanticMemory — Global facts and knowledge retrieved by vector search.
    
    Phase 3: Structural stub.
    Phase 6: Will be populated by an RAG/Embedding retrieval system.
    """
    def __init__(self, facts: list = None):
        self.facts = facts or []
        
    def format_for_prompt(self) -> str:
        if not self.facts:
            return ""
        return "\n".join([f"- {fact}" for fact in self.facts])
