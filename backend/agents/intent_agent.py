import json
import time
from typing import Dict, Any, Optional, Generator, Union

from agents.base import IAgent
from app.interfaces.agent_interfaces import IIntentService
from app.interfaces.providers import IProvider
from app.core.context import ExecutionContext
from app.services.intent_service import LegacyIntentService


class IntentAgent(IAgent, IIntentService):
    """
    Agent responsible for classifying the user's intent.
    Uses an LLM via IProvider to determine intent, with a fallback to LegacyIntentService.
    """

    def __init__(self, provider: IProvider, model_name: str = "llama3.2:1b"):
        self.provider = provider
        self.model_name = model_name
        self.legacy_fallback = LegacyIntentService()

        # Define valid intents based on legacy rules
        self.valid_intents = [
            "document_generation",
            "spreadsheet_generation",
            "data_visualization",
            "code_generation",
            "translation",
            "writing",
            "general_reasoning"
        ]

        self.system_prompt = f"""You are an intent classification agent.
Your task is to classify the user's prompt into exactly ONE of the following intents:
{', '.join(self.valid_intents)}

Return ONLY a valid JSON object with the following schema, and no other text:
{{
  "intent": "<one of the exact intent strings above>",
  "confidence": <float between 0.0 and 1.0>
}}
"""

    @property
    def agent_id(self) -> str:
        return "intent_agent"

    def classify(self, prompt: str) -> Dict[str, Any]:
        """Classify user prompt to detect intention and confidence using LLM."""
        
        # FAST-PATH: Try regex first to save 5-10s LLM latency
        legacy_result = self.legacy_fallback.classify(prompt)
        if legacy_result.get("confidence", 0) >= 0.80:
            return legacy_result
            
        messages = [
            {"role": "system", "content": self.system_prompt},
            {"role": "user", "content": prompt}
        ]
        
        try:
            schema = {
                "type": "object",
                "properties": {
                    "intent": {"type": "string"},
                    "confidence": {"type": "number"}
                },
                "required": ["intent", "confidence"]
            }
            
            result = self.provider.generate_json(
                model=self.model_name,
                prompt=prompt,
                schema=schema,
                system_prompt=self.system_prompt
            )
            
            intent = result.get("intent", "general_reasoning")
            confidence = float(result.get("confidence", 0.5))
            
            if intent not in self.valid_intents:
                intent = "general_reasoning"
                
            return {
                "intent": intent,
                "confidence": round(confidence, 2),
                "normalized_prompt": prompt.strip()
            }
        except Exception as e:
            print(f"[IntentAgent] LLM classification failed: {e}. Falling back to legacy regex.")
            return legacy_result

    def run(self, context: ExecutionContext) -> Generator[Union[str, AgentResult], None, None]:
        """IAgent interface: mutate context with intent."""
        from agents.base import AgentResult
        import json
        
        yield "data: " + json.dumps({"type": "status", "status": "Detecting intent..."}) + "\n\n"
        
        result = self.classify(context.prompt)
        context.intent = result["intent"]
        context.intent_confidence = result["confidence"]
        
        status_msg = f"Detected intent: {context.intent} (confidence {context.intent_confidence})"
        yield "data: " + json.dumps({"type": "status", "status": status_msg}) + "\n\n"
        
        # Capability Mapping (moved from orchestrator)
        yield "data: " + json.dumps({"type": "status", "status": "Mapping capabilities..."}) + "\n\n"
        from app.services.capability_service import CapabilityService
        cap_service = CapabilityService()
        context.capabilities = cap_service.resolve(context.intent)
        
        caps_str = ", ".join(context.capabilities)
        yield "data: " + json.dumps({"type": "status", "status": f"Requirements: {caps_str}"}) + "\n\n"
        
        yield AgentResult(
            agent_id=self.agent_id,
            output=result,
            status_message=status_msg
        )
