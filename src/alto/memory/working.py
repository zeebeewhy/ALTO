"""Working Memory: current session temporary state.

Theory: ACT-R working memory (7 +/- 2 chunks capacity) + conversation context.

Note: We maintain TWO turn histories:
- turn_history: ACT-R constrained pedagogical working memory (7+/-2 chunks)
- conversation: dialogue engine context (unbounded, compressible, topic-aware)
"""

import time
from typing import Dict, List, Optional
from collections import deque

from alto.config import get_config
from alto.conversation.context import ConversationContext


class WorkingMemory:
    """Holds transient state for the current session.

    Capacity-limited (default 7 chunks) following ACT-R constraints.
    Old chunks are pushed out when capacity is exceeded.

    Also holds the ConversationContext — the dialogue engine's view of the
    conversation, separate from pedagogical memory.
    """

    def __init__(self, user_id: str = "", storage_path: Optional[str] = None):
        self.current_target: Optional[str] = None
        self.turn_history: List[Dict] = []
        self.pending_errors: List[Dict] = []
        self.last_diagnosis: Optional[Dict] = None
        self.session_start: float = time.time()
        self.interaction_count: int = 0

        # Dialogue engine context (separate from pedagogical working memory)
        self.conversation = ConversationContext(
            user_id=user_id,
            storage_path=storage_path or "./data/memory",
        )

    def push_turn(self, role: str, content: str, meta: Optional[Dict] = None) -> None:
        """Add a conversational turn to working memory."""
        cfg = get_config()
        turn = {
            "role": role,
            "content": content,
            "meta": meta or {},
            "timestamp": time.time(),
        }
        self.turn_history.append(turn)
        self.interaction_count += 1

        # Also push to conversation context (dialogue engine layer)
        self.conversation.add_turn(role, content, meta)

        # Capacity limit: ACT-R 7 +/- 2 chunks (pedagogical working memory only)
        capacity = cfg.memory.working_memory_capacity
        if len(self.turn_history) > capacity + 2:
            self.turn_history = self.turn_history[-(capacity + 2):]

    def get_recent_turns(self, n: int = 5) -> List[Dict]:
        """Get recent n turns for context window."""
        return self.turn_history[-n:]

    def clear_pending_errors(self, cxn_id: Optional[str] = None) -> None:
        """Clear errors for a specific construction or all."""
        if cxn_id:
            self.pending_errors = [
                e for e in self.pending_errors
                if e.get("target_cxn") != cxn_id
            ]
        else:
            self.pending_errors = []

    def to_context_string(self, max_turns: int = 5) -> str:
        """Serialize recent turns into a string for LLM context."""
        turns = self.get_recent_turns(max_turns)
        lines = []
        for t in turns:
            role_label = "User" if t["role"] == "user" else "Assistant"
            lines.append(f"{role_label}: {t['content']}")
        return "\n".join(lines)
