from typing import Any, List, Dict, Optional
from pydantic import BaseModel, Field

class ExecutionContext(BaseModel):
    user: Optional[Dict[str, Any]] = None
    conversation: Optional[Dict[str, Any]] = None
    prompt: str
    attachments: List[Any] = Field(default_factory=list)
    intent: Optional[str] = None
    intent_confidence: Optional[float] = None
    capabilities: List[str] = Field(default_factory=list)
    retrieved_memories: List[Dict[str, Any]] = Field(default_factory=list)
    retrieved_conversation_context: List[Dict[str, Any]] = Field(default_factory=list)
    retrieved_files: List[Dict[str, Any]] = Field(default_factory=list)
    selected_model: Optional[str] = None
    selected_provider: Optional[str] = None
    execution_plan: Optional[Any] = None
    generated_artifacts: List[Dict[str, Any]] = Field(default_factory=list)
    execution_metadata: Dict[str, Any] = Field(default_factory=dict)
    errors: List[str] = Field(default_factory=list)
    timing_metrics: Dict[str, float] = Field(default_factory=dict)
    execution_status: str = "pending"
