from typing import Dict, List, Optional
from dataclasses import dataclass
from enum import Enum

class PromptSection(Enum):
    """
    Strictly defines the allowed sections and their exact rendering order 
    in the final prompt.
    """
    CORE_IDENTITY = 1
    CAPABILITIES = 2
    CRITICAL_RULES = 3
    USER_PROFILE = 4
    WORKING_MEMORY = 5
    EPISODIC_MEMORY = 6
    SHARED_PROJECT_CONTEXT = 7
    CONVERSATION_HISTORY = 8
    LATEST_USER_MESSAGE = 9

@dataclass
class SectionData:
    title: Optional[str]
    content: str
    order: PromptSection

class PromptBuilder:
    """
    Builds structured prompts by enforcing strict ordering of sections.
    It does not contain domain logic, only rendering and ordering logic.
    """
    
    def __init__(self):
        self._sections: Dict[PromptSection, SectionData] = {}
        
    def add_section(self, section: PromptSection, content: str, title: Optional[str] = None) -> None:
        """
        Add or update a section in the prompt.
        Empty content is ignored.
        """
        if not content.strip():
            return
            
        self._sections[section] = SectionData(title=title, content=content.strip(), order=section)
        
    def build(self) -> str:
        """
        Renders the final prompt by sorting the added sections based on PromptSection enum order.
        """
        rendered_parts = []
        
        # Sort by the enum value to guarantee strict ordering
        sorted_sections = sorted(self._sections.values(), key=lambda s: s.order.value)
        
        for idx, sec in enumerate(sorted_sections):
            if sec.title:
                rendered_parts.append(f"=== {sec.title.upper()} ===")
            
            rendered_parts.append(sec.content)
            
            # Add spacing between sections, but not at the very end
            if idx < len(sorted_sections) - 1:
                rendered_parts.append("")
                
        return "\n".join(rendered_parts)
