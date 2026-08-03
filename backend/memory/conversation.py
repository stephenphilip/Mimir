"""
ConversationMemory — typed wrapper for conversation message history.

Phase 1: Thin wrapper around the existing IConversationRepository.get_messages()
         call already performed in MemoryService.get_recent_context().
         Provides a named type and explicit interface for the memory layer.

Phase 3: Will be enhanced to:
  - Deduplicate and truncate intelligently
  - Support sliding window with overlap
  - Filter by relevance (semantic similarity) when EmbeddingModel is available
  - Return typed ConversationTurn objects instead of raw dicts

Design: ConversationMemory does NOT own a DB session or repository directly.
        It receives pre-fetched messages and formats them — keeping it
        stateless and testable without a DB.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List, Optional


@dataclass
class ConversationTurn:
    """A single message turn in the conversation history."""

    role: str       # "user" or "assistant"
    content: str
    message_id: Optional[int] = None
    created_at: Optional[str] = None


class ConversationMemory:
    """
    Formats raw conversation messages for prompt injection.

    This is a lightweight value type — it holds a snapshot of the
    conversation window relevant to the current request.

    Phase 1: Simple dict-to-typed-object conversion with truncation.
    Phase 3: Add relevance filtering and semantic chunking.

    Usage:
        messages = conv_repo.get_messages(conv_id, limit=6)
        conv_mem = ConversationMemory.from_messages(messages)
        formatted = conv_mem.format_for_prompt()
    """

    def __init__(self, turns: List[ConversationTurn]) -> None:
        self.turns = turns

    @classmethod
    def from_dicts(cls, messages: List[Dict[str, Any]]) -> "ConversationMemory":
        """
        Create from a list of dicts as returned by IMemoryService.get_recent_context().

        Expected dict shape: {"role": "user"|"assistant", "content": str}
        """
        turns = [
            ConversationTurn(
                role=m.get("role", "user"),
                content=(m.get("content") or "").strip(),
                message_id=m.get("id"),
                created_at=m.get("created_at"),
            )
            for m in messages
            if (m.get("content") or "").strip()
        ]
        return cls(turns)

    @classmethod
    def from_messages(cls, messages: List[Any]) -> "ConversationMemory":
        """
        Create from SQLAlchemy Message ORM objects.

        Compatible with the Message model returned by SQLiteConversationRepository.
        """
        turns = [
            ConversationTurn(
                role=getattr(m, "sender", "user"),
                content=(getattr(m, "content", "") or "").strip(),
                message_id=getattr(m, "id", None),
                created_at=str(getattr(m, "created_at", "")),
            )
            for m in messages
            if (getattr(m, "content", "") or "").strip()
        ]
        return cls(turns)

    def apply_budget(
        self, 
        max_turns: int = 4, 
        exclude_last_if_matches: Optional[str] = None
    ) -> None:
        """
        Filters and truncates the conversation to fit within token/turn limits.
        Removes the last turn if it matches the current prompt (to avoid duplication).
        """
        # Deduplicate latest prompt if requested
        if exclude_last_if_matches is not None:
            current = exclude_last_if_matches.strip()
            if self.turns and self.turns[-1].role == "user":
                last_content = self.turns[-1].content.strip()
                if last_content == current:
                    self.turns = self.turns[:-1]
                    
        # Apply sliding window budget
        if max_turns > 0:
            self.turns = self.turns[-max_turns:]

    def format_for_prompt(
        self,
        max_chars_per_turn: int = 1200,
        include_labels: bool = True,
    ) -> str:
        """
        Format conversation turns into a prompt-ready string.
        """
        if not self.turns:
            return ""
            
        lines = ["Conversation so far (for context only).", "Respond ONLY to the final user message below.\n"]
        for turn in self.turns:
            label = "User" if turn.role == "user" else "Assistant"
            content = turn.content
            if len(content) > max_chars_per_turn:
                content = content[:max_chars_per_turn] + "…"
            if include_labels:
                lines.append(f"{label}: {content}")
            else:
                lines.append(content)
        return "\n".join(lines)

    def as_dicts(self) -> List[Dict[str, Any]]:
        """Return turns as plain dicts (compatible with existing ContextBuilder format)."""
        return [{"role": t.role, "content": t.content} for t in self.turns]

    def __len__(self) -> int:
        return len(self.turns)

    def __repr__(self) -> str:
        return f"ConversationMemory({len(self.turns)} turns)"
