"""Declarative Memory: stores construction mastery states (activation 0..1).

Theory: ACT-R declarative memory (Anderson et al.) + Usage-Based frequency effects (Bybee 2006).
Each construction has an activation value representing the learner's mastery level.
"""

import json
import time
import os
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from alto.config import get_config
from alto.models import ConstructionState


class DeclarativeMemory:
    """Stores learner's construction knowledge as activation-weighted entries."""

    def __init__(self, user_id: str, storage_path: Optional[str] = None):
        self.user_id = user_id
        cfg = get_config()
        path = storage_path or cfg.memory.storage_path
        self._base = Path(path)
        self._base.mkdir(parents=True, exist_ok=True)
        self._path = self._base / f"{user_id}_declarative.json"
        self._constructions: Dict[str, ConstructionState] = {}
        self._load()

    def _load(self) -> None:
        if self._path.exists():
            try:
                with open(self._path, "r", encoding="utf-8") as f:
                    raw = json.load(f)
                for k, v in raw.items():
                    self._constructions[k] = ConstructionState(**v)
            except (json.JSONDecodeError, TypeError):
                self._constructions = {}

    def save(self) -> None:
        with open(self._path, "w", encoding="utf-8") as f:
            json.dump(
                {k: v.model_dump() for k, v in self._constructions.items()},
                f,
                indent=2,
                ensure_ascii=False,
            )

    def encounter(
        self,
        cxn_id: str,
        success: bool,
        error_detail: Optional[Dict] = None,
    ) -> ConstructionState:
        """Register one exposure to a construction. Update activation via ACT-R inspired curve.

        Args:
            cxn_id: Construction identifier, e.g. "ditransitive", "want-to-V"
            success: Whether the learner used the construction correctly
            error_detail: Optional dict with keys: sentence, type, missing, wrong, explanation

        Returns:
            Updated ConstructionState
        """
        cfg = get_config()
        now = time.time()

        if cxn_id not in self._constructions:
            # Emergence: new construction enters declarative memory at low activation
            self._constructions[cxn_id] = ConstructionState(activation=0.05)

        state = self._constructions[cxn_id]
        state.exposure_count += 1
        state.last_seen = now

        if success:
            state.success_count += 1
            # Exponential smoothing toward 1.0 (proceduralization progress)
            state.activation = min(
                1.0,
                state.activation * cfg.memory.activation_decay + cfg.memory.activation_boost,
            )
            if state.activation > cfg.memory.stabilization_threshold and state.exposure_count > 5:
                state.stable = True
        else:
            # Failure: decay activation, but keep a floor (avoid total forgetting)
            state.activation = max(
                0.0,
                state.activation * cfg.memory.activation_decay - 0.05,
            )
            state.stable = False
            if error_detail:
                state.error_patterns.append(error_detail)
                state.error_patterns = state.error_patterns[-10:]  # Keep last 10

            # Track systematic errors
            if error_detail and error_detail.get("type") != "creative":
                state.systematic_error_count += 1
            else:
                state.systematic_error_count = max(0, state.systematic_error_count - 1)

        self.save()
        return state

    def get_state(self, cxn_id: str) -> Optional[ConstructionState]:
        return self._constructions.get(cxn_id)

    def get_weak_constructions(
        self, threshold: float = 0.4
    ) -> List[Tuple[str, ConstructionState]]:
        """Get constructions needing pedagogical intervention (ZPD boundary).

        Returns items sorted by activation descending (closest to threshold first).
        These are in the Zone of Proximal Development — not mastered, not too hard.
        """
        items = [
            (cid, s) for cid, s in self._constructions.items() if s.activation < threshold
        ]
        items.sort(key=lambda x: x[1].activation, reverse=True)
        return items

    def get_systematic_errors(self) -> List[Tuple[str, ConstructionState]]:
        """Get constructions with repeated errors (candidates for focused teaching)."""
        cfg = get_config()
        threshold = cfg.diagnostic.systematic_error_threshold
        items = [
            (cid, s)
            for cid, s in self._constructions.items()
            if s.systematic_error_count >= threshold
        ]
        items.sort(key=lambda x: x[1].systematic_error_count, reverse=True)
        return items

    def get_all_constructions(self) -> Dict[str, ConstructionState]:
        return dict(self._constructions)

    def get_stats(self) -> Dict:
        """Return aggregate statistics for dashboard display."""
        if not self._constructions:
            return {"total": 0, "mastered": 0, "learning": 0, "weak": 0, "avg_activation": 0.0}

        states = list(self._constructions.values())
        return {
            "total": len(states),
            "mastered": sum(1 for s in states if s.stable),
            "learning": sum(1 for s in states if 0.25 <= s.activation < 0.85),
            "weak": sum(1 for s in states if s.activation < 0.25),
            "avg_activation": sum(s.activation for s in states) / len(states),
        }
