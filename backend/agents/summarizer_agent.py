import json
from typing import Optional
from app.interfaces.repositories import IConversationRepository, IEpisodicRepository
from app.providers.ollama_provider import OllamaProvider

class SummarizerAgent:
    """
    Background agent responsible for summarizing past conversations 
    and extracting key topics for Episodic Memory.
    """
    
    def __init__(self, conversation_repo: IConversationRepository, episodic_repo: IEpisodicRepository, provider: OllamaProvider):
        self.conversation_repo = conversation_repo
        self.episodic_repo = episodic_repo
        self.provider = provider
        self.model = "llama3.2:1b" # Default fast model for summarization

    def summarize_conversation(self, conversation_id: str, user_id: int = 1) -> Optional[dict]:
        """Reads a conversation, summarizes it, and saves to EpisodicMemory."""
        messages = self.conversation_repo.get_messages(conversation_id)
        if not messages or len(messages) < 2:
            return None # Skip empty or very short conversations

        # Format conversation for the prompt
        chat_log = ""
        for m in messages:
            chat_log += f"{m.sender.upper()}: {m.content}\n\n"

        prompt = f"""
You are an AI tasked with summarizing a conversation between a USER and an ASSISTANT.
Analyze the following conversation and provide a concise, factual summary (2-3 sentences) of what was discussed, what problems were solved, and any key decisions made.
Then, provide a list of up to 3 high-level topics (e.g. 'python', 'fastapi', 'budgeting') in a comma-separated format.

Return ONLY a JSON object with two keys: "summary" and "topics".
Do NOT include any markdown blocks, explanations, or extra text. Just raw JSON.

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
            
            summary = data.get("summary", "")
            topics_list = data.get("topics", "")
            topics_str = topics_list if isinstance(topics_list, str) else ", ".join(topics_list)

            # Save to repository
            record = self.episodic_repo.save(
                user_id=user_id,
                conversation_id=conversation_id,
                summary=summary,
                topics=topics_str
            )
            return {"summary": summary, "topics": topics_str}
            
        except Exception as e:
            print(f"[SummarizerAgent] Failed to summarize conversation {conversation_id}: {e}")
            return None
