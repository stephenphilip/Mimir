import json
from typing import Optional
from app.interfaces.repositories import IConversationRepository, IEntityRepository
from app.providers.ollama_provider import OllamaProvider

class EntityExtractorAgent:
    """
    Background agent responsible for extracting entities (people, projects, concepts)
    from past conversations and writing them to EntityMemory.
    """
    
    def __init__(self, conversation_repo: IConversationRepository, entity_repo: IEntityRepository, provider: OllamaProvider):
        self.conversation_repo = conversation_repo
        self.entity_repo = entity_repo
        self.provider = provider
        self.model = "llama3.2:1b" # Default fast model for extraction

    def extract_entities(self, conversation_id: str, user_id: int = 1) -> Optional[list]:
        """Reads a conversation, extracts entities, and saves them to EntityMemory."""
        messages = self.conversation_repo.get_messages(conversation_id)
        if not messages or len(messages) < 2:
            return None # Skip empty or very short conversations

        # Format conversation for the prompt
        chat_log = ""
        for m in messages:
            chat_log += f"{m.sender.upper()}: {m.content}\n\n"

        prompt = f"""
You are an AI data extractor. Read the following conversation and identify key entities. 
An entity is a person, a place, a software project, or a major technical concept that the USER is working on or has strong preferences about.
Do not extract common conversational words.

Return ONLY a JSON list of objects. Each object must have:
- "entity_name": The specific name (e.g., "Mimir", "Alice")
- "entity_type": One of ["person", "project", "technology", "concept"]
- "description": A short sentence describing what this entity is or the user's relationship to it.
- "attributes": An optional JSON string of key-value pairs (e.g. '{{"role": "engineer"}}'). If none, use an empty string.

Do NOT include any markdown blocks, explanations, or extra text. Just raw JSON list.

CONVERSATION:
{chat_log}
"""
        try:
            result_str = self.provider.generate(model=self.model, prompt=prompt, system_prompt="You are a data extraction system. Output strictly valid JSON.")
            
            # Clean up the output if model wrapped it in markdown
            result_str = result_str.strip()
            if result_str.startswith("```json"):
                result_str = result_str[7:]
            if result_str.startswith("```"):
                result_str = result_str[3:]
            if result_str.endswith("```"):
                result_str = result_str[:-3]
                
            data = json.loads(result_str.strip())
            if not isinstance(data, list):
                if isinstance(data, dict) and "entities" in data:
                    data = data["entities"]
                else:
                    return None
            
            extracted = []
            for item in data:
                name = item.get("entity_name")
                etype = item.get("entity_type", "concept")
                desc = item.get("description", "")
                attrs = item.get("attributes", "")
                
                if name:
                    record = self.entity_repo.save(
                        user_id=user_id,
                        entity_name=name,
                        entity_type=etype,
                        description=desc,
                        attributes=attrs
                    )
                    extracted.append(name)
                    
            return extracted
            
        except Exception as e:
            print(f"[EntityExtractorAgent] Failed to extract entities from conversation {conversation_id}: {e}")
            return None
