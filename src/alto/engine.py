"""Main Engine: orchestrates all layers into a complete learning loop.

Architecture:
  L4 DialogueAgent ──→ natural conversation (with layered context)
  L3 ConstructionDiagnosis ──→ neuro-symbolic error analysis
  L2 Memory (declarative + procedural + working)
  L1 JSON persistence
  L0 MetaOrchestrator ──→ layer coordination
"""

from typing import Dict, List, Optional

from openai import OpenAI

from alto.config import get_config
from alto.models import ConstructionState, DiagnosisReport, LessonMaterial
from alto.memory.declarative import DeclarativeMemory
from alto.memory.working import WorkingMemory
from alto.memory.procedural import ProceduralMemory
from alto.neuro_symbolic.diagnostic import ConstructionDiagnosis
from alto.agents.dialogue import DialogueAgent
from alto.agents.pedagogical import PedagogicalAgent
from alto.agents.orchestrator import MetaOrchestrator


class Engine:
    """Main orchestrator: wires all layers together."""

    def __init__(
        self,
        user_id: str,
        api_key: str = "",
        base_url: str = "",
        model_name: str = "",
    ):
        cfg = get_config()

        self.user_id = user_id
        self.client = OpenAI(
            api_key=api_key or cfg.llm.api_key,
            base_url=base_url or cfg.llm.base_url,
        )
        self.model = model_name or cfg.llm.model_name

        # L1 + L2: Memory systems
        self.declarative = DeclarativeMemory(user_id)
        self.working = WorkingMemory(
            user_id=user_id,
            storage_path=cfg.memory.storage_path,
        )

        # L3: Neuro-symbolic diagnosis
        self.diagnosis = ConstructionDiagnosis()

        # L4: LLM agents (DialogueAgent now owns conversation context)
        self.dialogue = DialogueAgent(
            self.client,
            self.model,
            conversation_context=self.working.conversation,
        )
        self.pedagogical = PedagogicalAgent(self.client, self.model)

        # L0: Orchestrator
        self.orchestrator = MetaOrchestrator(self.declarative, self.working)

    # ==================== Public API ====================

    def process_chat(self, sentence: str) -> Dict:
        """Process free-chat input: diagnose → update memory → decide → respond.

        This is the main entry point for conversation mode.

        Args:
            sentence: Learner's input sentence

        Returns:
            Dict with keys: mode, reply, should_teach, suggested_target, diagnosis
        """
        # Ensure conversation phase is chat
        self.working.conversation.set_phase("chat")

        # L3: Diagnose
        report = self.diagnosis.diagnose(
            sentence,
            self.working.current_target,
            self.client,
            self.model,
        )
        self.working.last_diagnosis = report.model_dump()

        # L0: Orchestrate
        decision = self.orchestrator.process_chat_input(sentence, report)

        # L4: Generate dialogue response
        if decision["should_teach"] and report.target_cxn and report.error_type != "none":
            # Error detected — generate a natural teaching transition
            reply = self.dialogue.generate_transition(
                from_phase="chat",
                to_phase="teach",
                target_cxn=report.target_cxn,
            )
        else:
            # Normal conversation with layered context
            reply = self.dialogue.chat(
                sentence,
                system_hint=decision.get("system_hint"),
            )

        self.working.push_turn("assistant", reply)

        # Background: refresh conversation context (summary, facts, topic, mood)
        # This is lightweight and does not block the response already sent.
        self.dialogue.update_conversation_context()

        return {
            "mode": "chat",
            "reply": reply,
            "should_teach": decision["should_teach"],
            "suggested_target": decision.get("suggested_target"),
            "diagnosis": report.model_dump(),
        }

    def enter_teaching(self, cxn_id: str) -> Dict:
        """Enter teaching mode for a specific construction.

        Args:
            cxn_id: Target construction ID

        Returns:
            Dict with mode, target_cxn, activation, lesson, transition
        """
        self.working.current_target = cxn_id
        self.working.conversation.set_phase("transition")

        state = self.declarative.get_state(cxn_id)
        if state is None:
            state = ConstructionState(activation=0.1)

        recent_errors = state.error_patterns[-3:] if state else []

        # L4: Generate a natural transition into teaching
        transition_msg = self.dialogue.generate_transition(
            from_phase="chat",
            to_phase="teach",
            target_cxn=cxn_id,
        )

        # L4: Generate lesson material
        lesson = self.pedagogical.generate_lesson(cxn_id, state, recent_errors)

        self.working.push_turn(
            "assistant",
            f"[Teaching: {cxn_id}] {transition_msg}",
            {"lesson": lesson.model_dump(), "transition": transition_msg},
        )

        self.working.conversation.set_phase("teach")

        return {
            "mode": "teach",
            "target_cxn": cxn_id,
            "activation": state.activation,
            "lesson": lesson.model_dump(),
            "transition": transition_msg,
        }

    def evaluate_exercise(self, learner_answer: str) -> Dict:
        """Evaluate a teaching exercise answer.

        Args:
            learner_answer: Learner's submitted answer

        Returns:
            Dict with success, feedback, diagnosis, new_activation, should_continue
        """
        target = self.working.current_target
        if not target:
            return {"error": "No active teaching target"}

        self.working.conversation.set_phase("evaluate")

        # L3: Diagnose the answer against target construction
        report = self.diagnosis.diagnose(
            learner_answer,
            target,
            self.client,
            self.model,
        )

        success = report.error_type == "none"

        # L2: Update memory
        self.declarative.encounter(
            target,
            success=success,
            error_detail=None if success else {
                "sentence": learner_answer,
                "type": report.error_type,
                "missing": report.missing_slots,
                "wrong": report.wrong_slots,
            },
        )

        # L4: Generate feedback
        state = self.declarative.get_state(target)
        feedback_result = self.pedagogical.evaluate_answer(
            learner_answer,
            target,
            target,  # expected_pattern simplified
            report.model_dump(),
        )

        # L0: Check if teaching should continue
        if success:
            self.working.clear_pending_errors(target)

        new_state = self.declarative.get_state(target)

        self.working.conversation.set_phase("teach")

        return {
            "success": success,
            "feedback": feedback_result["feedback"],
            "diagnosis": report.model_dump(),
            "new_activation": new_state.activation if new_state else 0.0,
            "should_continue": not success or (new_state and new_state.activation < 0.85),
        }

    def exit_teaching(self) -> Dict:
        """Exit teaching mode and return to chat with a natural transition."""
        target = self.working.current_target

        self.working.conversation.set_phase("transition")

        transition_msg = self.dialogue.generate_transition(
            from_phase="teach",
            to_phase="chat",
            target_cxn=target,
        )

        self.working.current_target = None
        self.working.push_turn("assistant", transition_msg)
        self.working.conversation.set_phase("chat")

        return {
            "mode": "chat",
            "reply": transition_msg,
        }

    def get_dashboard_data(self) -> Dict:
        """Get data for learner dashboard / memory visualization."""
        stats = self.declarative.get_stats()
        weak = self.declarative.get_weak_constructions(threshold=1.0)

        constructions = []
        for cid, s in weak[:15]:
            constructions.append({
                "id": cid,
                "activation": round(s.activation, 2),
                "stable": s.stable,
                "exposures": s.exposure_count,
                "success_rate": (
                    round(s.success_count / s.exposure_count, 2)
                    if s.exposure_count > 0 else 0
                ),
            })

        # Conversation context for the dashboard
        conv = self.working.conversation
        conv_state = conv.state

        return {
            "user_id": self.user_id,
            "session_duration": int(
                __import__("time").time() - self.working.session_start
            ),
            "interactions": self.working.interaction_count,
            "stats": stats,
            "constructions": constructions,
            "current_target": self.working.current_target,
            "pending_errors": len(self.working.pending_errors),
            # New: conversation context
            "conversation": {
                "phase": conv_state.phase,
                "topic": conv_state.current_topic,
                "summary": conv_state.session_summary,
                "mood": conv_state.user_mood,
                "key_facts": [
                    {"fact": kf.fact, "category": kf.category}
                    for kf in conv_state.key_facts[-5:]
                ],
                "total_turns": conv._turn_counter,
            },
        }
