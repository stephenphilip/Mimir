class EntityMemory:
    """
    EntityMemory — Facts linked to specific entities (e.g. User Profile, Characters).
    
    Phase 3: Wraps the existing get_user_profile() logic into a concrete type.
    Phase 6: Will be populated by an entity graph extractor.
    """
    def __init__(self, entities: list = None, profile: dict = None):
        self.entities = entities or []
        self.profile = profile or {}
        
    def format_for_prompt(self) -> str:
        lines = []
        
        if self.profile:
            lines.append("## User Profile")
            for key, value in self.profile.items():
                if key != "name": # "name" is handled in core identity
                    lines.append(f"- {key}: {value}")
        
        if self.entities:
            lines.append("## Known Entities")
            for ent in self.entities:
                if isinstance(ent, dict):
                    name = ent.get('entity_name', '')
                    desc = ent.get('description', '')
                else:
                    name = getattr(ent, 'entity_name', '')
                    desc = getattr(ent, 'description', '')
                
                desc_str = f": {desc}" if desc else ""
                lines.append(f"- {name}{desc_str}")
                
        return "\n".join(lines)
