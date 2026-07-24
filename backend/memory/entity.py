class EntityMemory:
    """
    EntityMemory — Facts linked to specific entities (e.g. User Profile, Characters).
    
    Phase 3: Wraps the existing get_user_profile() logic into a concrete type.
    Phase 6: Will be populated by an entity graph extractor.
    """
    def __init__(self, entities: dict = None):
        self.entities = entities or {}
        
    def format_for_prompt(self) -> str:
        if not self.entities:
            return ""
        
        lines = []
        for key, value in self.entities.items():
            if key != "name": # "name" is handled in core identity
                lines.append(f"- {key}: {value}")
                
        return "\n".join(lines)
