"""Working Memory: current session temporary state.

Theory: ACT-R working memory (7 +/- 2 chunks capacity) + conversation context.
"""

import time
from typing import Dict, List, Optional
from collections import deque

from alto.config import get_config


class WorkingMemory:
    """Holds transient state for the current session.

    Capacity-limited (default 7 chunks) following ACT-R constraints.
    Old chunks are pushed out when capacity is exceeded.
    """

    def __init__(self):
        self.current_target: Optional[str] = None
        self.turn_history: List[Dict] = []
        self.pending_errors: List[Dict] = []
        self.last_diagnosis: Optional[Dict] = None
        self.session_start: float = time.time()
        self.interaction_count: int = 0

    def push_turn(self, role: str, content: str, meta: Optional[Dict] = None) -> None:
        """Add a conversational turn to working memory."""
        cfg = get_config()
        self.turn_history.append({
            "role": role,
            "content": content,
            "meta": meta or {},
            "timestamp": time.time(),
        })
        self.interaction_count += 1

        # Capacity limit: ACT-R 7 +/- 2 chunks
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
