"""Procedural Memory: HTN-inspired teaching strategy rules.

Theory: ACT-R procedural memory (production rules) + Vygotsky ZPD + Wood et al. scaffolding.
Rules are hand-crafted but parametric — no manual annotation needed at runtime.
"""

from alto.models import ConstructionState, TeachingStrategy


class ProceduralMemory:
    """Selects teaching strategy based on construction activation level (0..1).

    Four stages mapping to ACT-R skill acquisition:
    - 0.00-0.25: Declarative   (explicit rules, demonstration)
    - 0.25-0.60: Associative   (scaffolded production, limited choices)
    - 0.60-0.85: Procedural    (guided free production, immediate recast)
    - 0.85-1.00: Autonomous    (refinement, variation, fluency)
    """

    @staticmethod
    def select_strategy(state: ConstructionState) -> TeachingStrategy:
        """Select teaching strategy based on activation level.

        Args:
            state: Current construction state including activation

        Returns:
            TeachingStrategy with mode, instruction, constraint, allow_free
        """
        a = state.activation

        if a < 0.25:
            # Stage 1: Declarative — provide comprehensible input + explicit rule
            return TeachingStrategy(
                mode="demonstration",
                instruction=(
                    "Show typical example sentences of the target construction, "
                    "with brief explanation of the form-meaning pairing. "
                    "Do not ask the learner to produce yet."
                ),
                constraint=(
                    "Generate 2 example sentences with Chinese translation. "
                    "Highlight fixed components and slots (___) in the construction. "
                    "Add a one-sentence explanation of what this construction means."
                ),
                allow_free=False,
            )

        elif a < 0.60:
            # Stage 2: Associative — scaffolded production (controlled practice)
            return TeachingStrategy(
                mode="scaffolded_production",
                instruction=(
                    "Provide cloze or reordering exercises. "
                    "Learner fills construction slots from limited choices."
                ),
                constraint=(
                    "Generate 1 cloze exercise with blanks (____) and 1 sentence "
                    "reordering exercise. Provide 3 distractors. "
                    "Keep vocabulary simple. Do not require free production."
                ),
                allow_free=False,
            )

        elif a < 0.85:
            # Stage 3: Procedural — guided free production + immediate recast
            return TeachingStrategy(
                mode="guided_production",
                instruction=(
                    "Ask learner to produce sentences using the target construction. "
                    "If error occurs, use recast (rephrase correctly without direct correction)."
                ),
                constraint=(
                    "Pose a situational question requiring the target construction. "
                    "If learner makes error, respond with a recast — restate their "
                    "intended meaning correctly, then ask them to try again. "
                    "Never give the answer directly."
                ),
                allow_free=True,
            )

        else:
            # Stage 4: Autonomous — refinement, variation, pragmatic nuances
            return TeachingStrategy(
                mode="refinement",
                instruction=(
                    "Introduce construction variants or pragmatic constraints. "
                    "Build fluency and nuanced usage."
                ),
                constraint=(
                    "Ask learner to compare two similar constructions (e.g., ditransitive "
                    "vs prepositional dative). Or ask them to use the construction in "
                    "a formal vs informal context. Encourage creative but correct usage."
                ),
                allow_free=True,
            )

    @staticmethod
    def get_error_response_strategy(error_type: str, is_systematic: bool) -> str:
        """Select error feedback strategy based on error type and systematicity.

        This implements the "noise filtering" function — systematic errors get
        pedagogical treatment; random/creative errors get light feedback.
        """
        if not is_systematic:
            return "light_recast"  # Brief reformulation, no deep dive

        match error_type:
            case "omission":
                return "prompt_filling"  # Hint at what's missing
            case "commission":
                return "contrastive_highlight"  # Show correct vs incorrect form
            case "misordering":
                return "structural_scaffold"  # Provide word order template
            case "creative":
                return "encourage_refine"  # Validate attempt, guide toward standard
            case _:
                return "general_recast"
