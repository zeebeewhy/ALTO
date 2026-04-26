"""Layered prompt construction for dialogue agents.

Layer order (outer -> inner):
1. Base persona / system identity
2. Global context (topic, summary, key facts, mood)
3. Teaching hints (from pedagogical layer)
4. Recent conversation turns (hot zone)
5. Current user input
"""

from typing import Dict, List, Optional


class PromptBuilder:
    """Constructs LLM prompts with layered conversation context."""

    DIALOGUE_BASE = (
        "You are a friendly, patient language learning partner. "
        "Engage in natural conversation. Do NOT explicitly correct grammar unless "
        "the learner clearly asks for help or makes a serious error that blocks "
        "communication. Focus on keeping the conversation flowing. "
        "If the learner makes a minor error, naturally model the correct form "
        "in your response without pointing it out (implicit recast). "
        "Always respond in English. Keep responses concise (2-4 sentences)."
    )

    TRANSITION_BASE = (
        "You are helping a language learner transition between activities. "
        "Be natural, encouraging, and brief. Do not make the transition feel robotic."
    )

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    @classmethod
    def build_dialogue_messages(
        cls,
        context: Dict,
        user_message: str,
        system_hint: Optional[str] = None,
        is_transition: bool = False,
    ) -> List[Dict]:
        """Build a complete message list for a dialogue LLM call.

        Args:
            context: Output from ConversationContext.to_prompt_context()
            user_message: The current user input
            system_hint: Optional pedagogical hint from MetaOrchestrator
            is_transition: If True, use transition persona instead of chat persona
        """
        messages: List[Dict] = []

        # Layer 1: Base persona
        base = cls.TRANSITION_BASE if is_transition else cls.DIALOGUE_BASE
        system_parts = [base]

        # Layer 2: Global conversation context
        global_ctx = cls._format_global_context(context)
        if global_ctx:
            system_parts.append(global_ctx)

        # Layer 3: Teaching hint (pedagogical layer injects here)
        if system_hint:
            system_parts.append(f"[Teaching Note] {system_hint}")

        messages.append({"role": "system", "content": "\n\n".join(system_parts)})

        # Layer 4: Recent conversation (hot zone)
        for turn in context.get("recent_turns", []):
            role = turn.get("role", "user")
            api_role = "user" if role == "user" else "assistant"
            messages.append({"role": api_role, "content": turn["content"]})

        # Layer 5: Current input
        messages.append({"role": "user", "content": user_message})

        return messages

    # ------------------------------------------------------------------
    # LLM utility prompts (called by DialogueAgent / Engine)
    # ------------------------------------------------------------------

    @classmethod
    def build_summary_prompt(
        cls, previous_summary: str, new_turns: List[Dict]
    ) -> List[Dict]:
        """Prompt for incremental conversation summary generation."""
        turns_text = "\n".join(
            [
                f"{'User' if t['role'] == 'user' else 'Assistant'}: {t['content']}"
                for t in new_turns
            ]
        )

        content = f"""Update the conversation summary based on the new dialogue turns.

Previous summary: {previous_summary or "(None yet — this is the start of the conversation)"}

New dialogue turns:
{turns_text}

Provide a concise updated summary (2-3 sentences max) capturing:
- What the user and assistant have been discussing
- Any key facts about the learner revealed in these turns
- The current topic

Updated summary:"""

        return [
            {
                "role": "system",
                "content": "You are a conversation summarizer. Be concise and factual.",
            },
            {"role": "user", "content": content},
        ]

    @classmethod
    def build_fact_extraction_prompt(cls, turns: List[Dict]) -> List[Dict]:
        """Prompt for extracting key facts about the user from recent turns."""
        turns_text = "\n".join(
            [
                f"{'User' if t['role'] == 'user' else 'Assistant'}: {t['content']}"
                for t in turns
            ]
        )

        content = f"""Analyze the following conversation and extract any NEW facts about the user.
Only extract facts that are personal to the user (preferences, plans, interests, concerns, background).
Do NOT extract general knowledge (e.g., "Paris is in France").

Return a JSON array. Use an empty array [] if no new personal facts are found.
Format: [{{"fact": "...", "category": "plan|preference|personal|concern|interest|background"}}]

Conversation:
{turns_text}

New facts (JSON only):"""

        return [
            {
                "role": "system",
                "content": "You extract personal facts from conversations. Output valid JSON only.",
            },
            {"role": "user", "content": content},
        ]

    @classmethod
    def build_topic_detection_prompt(cls, turns: List[Dict]) -> List[Dict]:
        """Prompt for detecting the current conversation topic."""
        turns_text = "\n".join(
            [
                f"{'User' if t['role'] == 'user' else 'Assistant'}: {t['content']}"
                for t in turns[-6:]
            ]
        )

        content = f"""What is the main topic of this conversation?
Return just the topic name (1-3 words). If unclear, return "general".

{turns_text}

Topic:"""

        return [
            {"role": "system", "content": "You identify conversation topics briefly."},
            {"role": "user", "content": content},
        ]

    @classmethod
    def build_transition_prompt(
        cls,
        from_phase: str,
        to_phase: str,
        target_cxn: Optional[str] = None,
        context_summary: str = "",
    ) -> List[Dict]:
        """Prompt for generating a natural transition utterance."""
        system = cls.TRANSITION_BASE
        if context_summary:
            system += f"\n\n[Context] {context_summary}"

        if target_cxn:
            user = (
                f"Write a brief, natural sentence to transition from free conversation "
                f"to practicing the '{target_cxn}' construction. "
                f"Be encouraging and make it feel organic, not robotic. "
                f"Max 1-2 sentences."
            )
        else:
            user = (
                f"Write a brief, natural sentence to transition from practice "
                f"back to free conversation. "
                f"Acknowledge their progress briefly, then move on. "
                f"Max 1-2 sentences."
            )

        return [
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ]

    @classmethod
    def build_mood_detection_prompt(cls, turns: List[Dict]) -> List[Dict]:
        """Prompt for detecting learner emotional state."""
        turns_text = "\n".join(
            [
                f"{'User' if t['role'] == 'user' else 'Assistant'}: {t['content']}"
                for t in turns[-4:]
            ]
        )

        content = f"""Based on the user's most recent messages, how do they seem to be feeling?
Choose one: engaged, confused, frustrated, bored, excited, neutral, or uncertain.
Return just the single word.

{turns_text}

Mood:"""

        return [
            {"role": "system", "content": "You detect emotional tone briefly."},
            {"role": "user", "content": content},
        ]

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @classmethod
    def _format_global_context(cls, context: Dict) -> str:
        parts = []

        topic = context.get("topic")
        if topic:
            parts.append(f"Current topic: {topic}")

        summary = context.get("summary", "").strip()
        if summary:
            parts.append(f"Summary: {summary}")

        key_facts = context.get("key_facts", [])
        if key_facts:
            # KeyFact objects have .fact attribute
            facts_text = "\n".join(
                [f"- {getattr(kf, 'fact', str(kf))}" for kf in key_facts[-5:]]
            )
            parts.append(f"About the learner:\n{facts_text}")

        mood = context.get("user_mood")
        if mood:
            parts.append(f"Learner seems: {mood}")

        pending = context.get("pending_questions", [])
        if pending:
            parts.append(f"Unanswered questions: {', '.join(pending)}")

        if not parts:
            return ""

        return "[Conversation Context]\n" + "\n\n".join(parts)
