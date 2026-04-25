"""Main Engine: orchestrates all layers into a complete learning loop.

Architecture:
  L4 DialogueAgent ──→ natural conversation
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
        self.working = WorkingMemory()

        # L3: Neuro-symbolic diagnosis
        self.diagnosis = ConstructionDiagnosis()

        # L4: LLM agents
        self.dialogue = DialogueAgent(self.client, self.model)
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
            # Error detected — suggest teaching transition
            reply = (
                f"I noticed something interesting in your use of 「{report.target_cxn}」. "
                f"{report.explanation} Would you like to practice this pattern?"
            )
        else:
            # Normal conversation
            history = [
                {"role": t["role"], "content": t["content"]}
                for t in self.working.get_recent_turns(6)
            ]
            reply = self.dialogue.chat(
                sentence,
                history,
                system_hint=decision.get("system_hint"),
            )

        self.working.push_turn("assistant", reply)

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
            Dict with mode, target_cxn, activation, lesson
        """
        self.working.current_target = cxn_id

        state = self.declarative.get_state(cxn_id)
        if state is None:
            state = ConstructionState(activation=0.1)

        recent_errors = state.error_patterns[-3:] if state else []

        # L4: Generate lesson material
        lesson = self.pedagogical.generate_lesson(cxn_id, state, recent_errors)

        self.working.push_turn(
            "assistant",
            f"[Teaching mode: {cxn_id}]",
            {"lesson": lesson.model_dump()},
        )

        return {
            "mode": "teach",
            "target_cxn": cxn_id,
            "activation": state.activation,
            "lesson": lesson.model_dump(),
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

        return {
            "success": success,
            "feedback": feedback_result["feedback"],
            "diagnosis": report.model_dump(),
            "new_activation": new_state.activation if new_state else 0.0,
            "should_continue": not success or (new_state and new_state.activation < 0.85),
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
        }
