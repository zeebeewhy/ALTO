"""L0 Meta-Orchestrator: coordinates all layers based on learner state.

Implements three core functions:
1. Goal Emergence & Autonomous Planning — detects construction gaps from free conversation
2. Guided Learning with Noise Filtering — separates systematic errors from random noise
3. Memory & Personalization — tracks individual learning trajectories
"""

from typing import Dict, List, Optional, Tuple

from alto.models import DiagnosisReport, ConstructionState
from alto.memory.declarative import DeclarativeMemory
from alto.memory.working import WorkingMemory


class MetaOrchestrator:
    """Central controller: decides when to chat, when to teach, what to teach next."""

    def __init__(
        self,
        declarative: DeclarativeMemory,
        working: WorkingMemory,
    ):
        self.declarative = declarative
        self.working = working

    def process_chat_input(
        self,
        sentence: str,
        diagnosis: DiagnosisReport,
    ) -> Dict:
        """Process a free-chat input: update memory, decide next action.

        Core function #1: Goal Emergence — new constructions enter memory when detected.
        Core function #2: Noise Filtering — only systematic errors trigger teaching.

        Args:
            sentence: Learner's input
            diagnosis: Neuro-symbolic diagnosis result

        Returns:
            Dict with mode (chat/teach), reply, should_teach flag, target_cxn
        """
        target = diagnosis.target_cxn
        has_error = diagnosis.error_type != "none"

        # Update working memory
        self.working.push_turn(
            "user", sentence,
            {"diagnosis": diagnosis.model_dump()}
        )

        # If no construction detected and no error, pure chat
        if not target and not has_error:
            return {
                "mode": "chat",
                "should_teach": False,
                "suggested_target": None,
                "system_hint": None,
            }

        # Update declarative memory
        if target:
            self.declarative.encounter(
                target,
                success=(diagnosis.error_type == "none"),
                error_detail={
                    "sentence": sentence,
                    "type": diagnosis.error_type,
                    "missing": diagnosis.missing_slots,
                    "wrong": diagnosis.wrong_slots,
                    "explanation": diagnosis.explanation,
                } if has_error else None,
            )

        # Noise filtering: only systematic errors enter teaching queue
        if has_error and diagnosis.is_systematic and target:
            self.working.pending_errors.append(diagnosis.model_dump())

        # Decide if teaching mode should be offered
        weak_constructions = self.declarative.get_weak_constructions(threshold=0.4)
        systematic_errors = self.declarative.get_systematic_errors()

        should_teach = (
            len(self.working.pending_errors) > 0
            or len(systematic_errors) > 0
            or (weak_constructions and len(weak_constructions) > 0)
        )

        # Pick the highest priority teaching target
        suggested_target = None
        if systematic_errors:
            suggested_target = systematic_errors[0][0]
        elif self.working.pending_errors:
            suggested_target = self.working.pending_errors[-1].get("target_cxn")
        elif weak_constructions:
            suggested_target = weak_constructions[0][0]

        # Build system hint for dialogue agent
        system_hint = None
        if should_teach and suggested_target:
            state = self.declarative.get_state(suggested_target)
            if state:
                system_hint = (
                    f"Learner has gap in '{suggested_target}' "
                    f"(activation: {state.activation:.0%}, "
                    f"errors: {state.systematic_error_count}). "
                    f"Consider naturally weaving this into conversation."
                )

        return {
            "mode": "chat",
            "should_teach": should_teach,
            "suggested_target": suggested_target,
            "system_hint": system_hint,
        }

    def should_enter_teaching(self, cxn_id: str) -> bool:
        """Determine if learner should enter focused teaching for a construction.

        Checks activation level and error history.
        """
        state = self.declarative.get_state(cxn_id)
        if not state:
            return True  # New construction, definitely teach

        # If activation is very low or has systematic errors, enter teaching
        return state.activation < 0.4 or state.systematic_error_count >= 2

    def get_next_recommendation(self) -> Optional[Tuple[str, ConstructionState]]:
        """Get the next construction to practice (for autonomous planning).

        Priority:
        1. Systematic errors (most urgent)
        2. Weak constructions in ZPD (activation 0.25-0.4)
        3. New constructions not yet encountered
        """
        # 1. Systematic errors
        systematic = self.declarative.get_systematic_errors()
        if systematic:
            return systematic[0]

        # 2. Weak constructions (closest to threshold first)
        weak = self.declarative.get_weak_constructions(threshold=0.4)
        if weak:
            return weak[0]

        return None

    def on_teaching_complete(self, cxn_id: str, success: bool) -> Dict:
        """Handle completion of a teaching session.

        Updates state and decides whether to continue, switch target, or return to chat.
        """
        state = self.declarative.encounter(cxn_id, success=success)

        if success and state.activation >= 0.6:
            # Learner is progressing, clear pending errors for this construction
            self.working.clear_pending_errors(cxn_id)

            # Check if there's another construction needing attention
            next_rec = self.get_next_recommendation()
            if next_rec and next_rec[0] != cxn_id:
                return {
                    "action": "switch_target",
                    "next_cxn": next_rec[0],
                    "message": f"Great progress! Let's also work on '{next_rec[0]}'.",
                }

            return {
                "action": "return_to_chat",
                "message": "Excellent! You are getting comfortable with this pattern. Let's continue chatting!",
            }

        # Not yet mastered — continue practicing
        return {
            "action": "continue_teaching",
            "message": None,  # PedagogicalAgent will handle feedback
        }
