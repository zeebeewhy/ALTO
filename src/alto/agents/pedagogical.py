"""L4 Pedagogical Agent: HTN-constrained teaching material generation.

Generates exercises, examples, and lesson content constrained by the current
teaching strategy (demonstration → scaffolded → guided → refinement).
"""

import json
from typing import Dict, List, Optional

from alto.config import get_config
from alto.models import ConstructionState, LessonMaterial, TeachingStrategy
from alto.memory.procedural import ProceduralMemory


class PedagogicalAgent:
    """Generates teaching materials under HTN strategy constraints."""

    def __init__(self, llm_client, model_name: Optional[str] = None):
        self.client = llm_client
        self.model = model_name or get_config().llm.model_name

    def generate_lesson(
        self,
        cxn_id: str,
        state: ConstructionState,
        recent_errors: Optional[List[Dict]] = None,
    ) -> LessonMaterial:
        """Generate lesson material constrained by the learner's current stage.

        Args:
            cxn_id: Target construction ID
            state: Current construction state (activation, errors, etc.)
            recent_errors: Recent error patterns for context

        Returns:
            LessonMaterial with title, content, exercise, hints
        """
        cfg = get_config()
        strategy = ProceduralMemory.select_strategy(state)
        error_context = self._format_errors(recent_errors)

        prompt = f"""You are a Construction Grammar language teacher AI.
Generate teaching material following the strategy below exactly.

TARGET CONSTRUCTION: {cxn_id}
LEARNER MASTERY: {state.activation:.0%}
STRATEGY MODE: {strategy.mode}

STRATEGY INSTRUCTION: {strategy.instruction}
GENERATION CONSTRAINT: {strategy.constraint}

RECENT ERRORS: {error_context}

Output valid JSON only:
{{
  "title": "Lesson title (5-10 words)",
  "content": "Teaching text to display to the learner (include Chinese translations for examples)",
  "exercise": "The actual exercise text with blanks (____) if applicable",
  "expected_pattern": "The construction pattern being practiced, e.g. [NP] told [NP] [NP]",
  "hints": ["Hint 1", "Hint 2"]
}}"""

        try:
            resp = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": "You are a professional language teacher using Construction Grammar methods."},
                    {"role": "user", "content": prompt},
                ],
                temperature=cfg.llm.temperature_pedagogy,
                max_tokens=cfg.llm.max_tokens,
            )
            content = resp.choices[0].message.content or ""

            # Extract JSON
            content = content.strip()
            if content.startswith("```json"):
                content = content[7:]
            if content.startswith("```"):
                content = content[3:]
            if content.endswith("```"):
                content = content[:-3]
            content = content.strip()

            data = json.loads(content)
            return LessonMaterial(
                title=data.get("title", f"Practice: {cxn_id}"),
                content=data.get("content", ""),
                exercise=data.get("exercise", "Please make a sentence using the target construction."),
                expected_pattern=data.get("expected_pattern", cxn_id),
                hints=data.get("hints", []),
            )

        except Exception:
            # Degrade to template
            return self._template_lesson(cxn_id, state, strategy)

    def evaluate_answer(
        self,
        learner_answer: str,
        target_cxn: str,
        expected_pattern: str,
        diagnosis_report: Dict,
    ) -> Dict:
        """Generate feedback for a learner's exercise answer.

        Args:
            learner_answer: The learner's submitted answer
            target_cxn: Target construction ID
            expected_pattern: Expected construction pattern
            diagnosis_report: Output from ConstructionDiagnosis

        Returns:
            Dict with feedback text, correct/incorrect, next action hint
        """
        cfg = get_config()
        is_correct = diagnosis_report.get("error_type") == "none"

        if is_correct:
            prompt = f"""The learner correctly used '{target_cxn}' in: "{learner_answer}"
Give brief, encouraging feedback (1-2 sentences). Then suggest a slight variation
to keep them challenged."""
        else:
            explanation = diagnosis_report.get("explanation", "")
            missing = diagnosis_report.get("missing_slots", [])
            wrong = diagnosis_report.get("wrong_slots", {})

            prompt = f"""The learner made an error with '{target_cxn}' in: "{learner_answer}"
Error: {explanation}
Missing: {missing}
Wrong: {wrong}

Give a recast — restate their intended meaning correctly without saying "you are wrong".
Then ask them to try again. Keep it encouraging and brief (2-3 sentences)."""

        try:
            resp = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": "You are an encouraging language teacher who uses recasts rather than direct correction."},
                    {"role": "user", "content": prompt},
                ],
                temperature=cfg.llm.temperature_pedagogy,
                max_tokens=512,
            )
            feedback = resp.choices[0].message.content or "Good try! Let's continue."
        except Exception:
            feedback = "Good try! Let's practice more." if not is_correct else "Well done!"

        return {
            "correct": is_correct,
            "feedback": feedback,
            "should_continue": not is_correct,
        }

    def _format_errors(self, errors: Optional[List[Dict]]) -> str:
        if not errors:
            return "None"
        lines = []
        for e in errors[-3:]:
            lines.append(f"- {e.get('type', '?')}: {e.get('sentence', '?')}")
        return "\n".join(lines)

    def _template_lesson(
        self, cxn_id: str, state: ConstructionState, strategy: TeachingStrategy
    ) -> LessonMaterial:
        """Fallback template when LLM generation fails."""
        templates = {
            "demonstration": LessonMaterial(
                title=f"Learn: {cxn_id}",
                content=f"Let's look at how '{cxn_id}' works.\n\nExample 1: I want ___ (to eat) an apple.\n我想吃一个苹果。\n\nExample 2: She wants ___ (to go) home.\n她想回家。\n\nPattern: want + to + verb",
                exercise="Read the examples aloud. Notice where 'to' goes.",
                expected_pattern="want-to-V",
                hints=["'want' is always followed by 'to'"],
            ),
            "scaffolded_production": LessonMaterial(
                title=f"Practice: {cxn_id}",
                content="Fill in the blank with the correct form.",
                exercise="I want ____ (go) to the park.",
                expected_pattern="want-to-V",
                hints=["Add 'to' before the verb"],
            ),
            "guided_production": LessonMaterial(
                title=f"Use: {cxn_id}",
                content="Answer the question using the target construction.",
                exercise="What do you want to do this weekend?\n(Use: I want to ___)",
                expected_pattern="want-to-V",
                hints=["Start with 'I want to'"],
            ),
            "refinement": LessonMaterial(
                title=f"Master: {cxn_id}",
                content="Compare these two similar patterns.",
                exercise="What's the difference?\nA) I want to eat.\nB) I want eating.",
                expected_pattern="want-to-V",
                hints=["Which one sounds more natural?"],
            ),
        }
        return templates.get(strategy.mode, templates["demonstration"])
