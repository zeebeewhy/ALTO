"""ConversationContext: dialogue state, history, summary, and key facts.

Separated from WorkingMemory because:
- WorkingMemory = ACT-R cognitive chunks (7+/-2, ephemeral, pedagogical)
- ConversationContext = dialogue engine state (persistent across turns,
  compressible, topic-aware, social)
"""

import json
import time
from pathlib import Path
from typing import Dict, List, Optional

from pydantic import BaseModel, Field


class KeyFact(BaseModel):
    """A fact about the learner extracted from conversation."""

    fact: str
    category: str = ""  # e.g., "plan", "preference", "personal", "concern", "interest"
    source_turn: int = 0
    timestamp: float = Field(default_factory=time.time)


class ConversationState(BaseModel):
    """Serializable dialogue state."""

    phase: str = "chat"  # chat, diagnose, teach, evaluate, transition
    current_topic: Optional[str] = None
    topics_history: List[str] = Field(default_factory=list)
    user_mood: Optional[str] = None
    pending_questions: List[str] = Field(default_factory=list)
    session_summary: str = ""
    summary_turn_count: int = 0
    key_facts: List[KeyFact] = Field(default_factory=list)


class ConversationContext:
    """Manages dialogue state, full history, summary, and key facts.

    Design decisions:
    - LLM calls (summary generation, fact extraction) are TRIGGERED by
      the caller (DialogueAgent/Engine), not executed automatically inside
      add_turn().  This keeps the class pure and testable.
    - Full history is kept in memory for summary generation, but NEVER
      sent to the LLM directly. Only recent_turns + summary go into prompts.
    """

    def __init__(self, user_id: str = "", storage_path: Optional[str] = None):
        self.user_id = user_id
        self.state = ConversationState()
        self._turn_history: List[Dict] = []
        self._turn_counter: int = 0

        # Optional persistence (mirrors DeclarativeMemory pattern)
        self._storage_path: Optional[Path] = None
        if storage_path:
            base = Path(storage_path)
            base.mkdir(parents=True, exist_ok=True)
            self._storage_path = base / f"{user_id}_conversation.json"
            self._load()

    # ---------- Turn management ----------

    def add_turn(self, role: str, content: str, meta: Optional[Dict] = None) -> None:
        """Record a conversational turn."""
        self._turn_counter += 1
        self._turn_history.append(
            {
                "role": role,
                "content": content,
                "meta": meta or {},
                "turn_idx": self._turn_counter,
                "timestamp": time.time(),
            }
        )

    def get_recent_turns(self, n: int = 6) -> List[Dict]:
        """Get the most recent n turns for the hot zone."""
        return self._turn_history[-n:]

    def get_turns_since_summary(self) -> List[Dict]:
        """Get turns added since the last summary update."""
        start_idx = self.state.summary_turn_count
        return [t for t in self._turn_history if t["turn_idx"] > start_idx]

    # ---------- State mutations ----------

    def update_summary(self, new_summary: str) -> None:
        """Set a new session summary and reset the delta counter."""
        self.state.session_summary = new_summary
        self.state.summary_turn_count = self._turn_counter

    def add_key_fact(self, fact: str, category: str = "") -> None:
        """Append a new key fact, deduplicating by exact string match."""
        # Simple dedup
        existing = {kf.fact.lower().strip() for kf in self.state.key_facts}
        if fact.lower().strip() in existing:
            return
        self.state.key_facts.append(
            KeyFact(
                fact=fact,
                category=category,
                source_turn=self._turn_counter,
            )
        )
        # Keep last 20 facts
        self.state.key_facts = self.state.key_facts[-20:]

    def set_topic(self, topic: str) -> None:
        """Update current topic, archiving previous if changed."""
        prev = self.state.current_topic
        if prev and prev != topic:
            if prev not in self.state.topics_history:
                self.state.topics_history.append(prev)
        self.state.current_topic = topic

    def set_phase(self, phase: str) -> None:
        """Update dialogue phase (chat/diagnose/teach/evaluate/transition)."""
        self.state.phase = phase

    def set_mood(self, mood: Optional[str]) -> None:
        self.state.user_mood = mood

    def add_pending_question(self, question: str) -> None:
        if question not in self.state.pending_questions:
            self.state.pending_questions.append(question)

    def resolve_pending_question(self, question: str) -> None:
        self.state.pending_questions = [
            q for q in self.state.pending_questions if q != question
        ]

    # ---------- Introspection ----------

    def needs_summary_update(self, threshold_turns: int = 8) -> bool:
        """Check if enough new turns have accumulated to warrant re-summarizing."""
        return (self._turn_counter - self.state.summary_turn_count) >= threshold_turns

    def to_prompt_context(self, max_recent: int = 6) -> Dict:
        """Package context for PromptBuilder."""
        return {
            "phase": self.state.phase,
            "topic": self.state.current_topic,
            "summary": self.state.session_summary,
            "key_facts": self.state.key_facts,
            "recent_turns": self.get_recent_turns(max_recent),
            "pending_questions": self.state.pending_questions,
            "user_mood": self.state.user_mood,
            "total_turns": self._turn_counter,
        }

    # ---------- Persistence ----------

    def save(self) -> None:
        if self._storage_path is None:
            return
        with open(self._storage_path, "w", encoding="utf-8") as f:
            json.dump(
                {
                    "state": self.state.model_dump(),
                    "turn_count": self._turn_counter,
                },
                f,
                indent=2,
                ensure_ascii=False,
            )

    def _load(self) -> None:
        if self._storage_path is None or not self._storage_path.exists():
            return
        try:
            with open(self._storage_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            self.state = ConversationState(**data.get("state", {}))
            self._turn_counter = data.get("turn_count", 0)
        except (json.JSONDecodeError, TypeError):
            pass

    def to_dict(self) -> Dict:
        return {
            "state": self.state.model_dump(),
            "turn_count": self._turn_counter,
        }

    @classmethod
    def from_dict(cls, data: Dict, user_id: str = "") -> "ConversationContext":
        ctx = cls(user_id=user_id)
        ctx.state = ConversationState(**data.get("state", {}))
        ctx._turn_counter = data.get("turn_count", 0)
        return ctx
