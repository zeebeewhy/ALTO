"""L4 Dialogue Agent: natural language interaction via LLM.

Handles free conversation, context maintenance, and natural responses.
Does NOT directly teach — that is PedagogicalAgent's job.

Key improvement: uses layered conversation context (summary + key facts + topic)
instead of raw turn history, enabling fluent multi-turn dialogue.
"""

import json
from typing import Dict, List, Optional

from alto.config import get_config
from alto.conversation.context import ConversationContext
from alto.conversation.prompt_builder import PromptBuilder


class DialogueAgent:
    """LLM-powered conversational agent for free-form interaction."""

    def __init__(
        self,
        llm_client,
        model_name: Optional[str] = None,
        conversation_context: Optional[ConversationContext] = None,
    ):
        self.client = llm_client
        self.model = model_name or get_config().llm.model_name
        self.conversation = conversation_context

    def chat(
        self,
        user_message: str,
        system_hint: Optional[str] = None,
        is_transition: bool = False,
    ) -> str:
        """Generate a natural conversational response using layered context.

        Args:
            user_message: Current user input
            system_hint: Optional hint about detected construction gaps
            is_transition: If True, generates a transition utterance

        Returns:
            Natural language response string
        """
        cfg = get_config()

        # Build layered prompt with conversation context
        if self.conversation is not None:
            context = self.conversation.to_prompt_context()
            messages = PromptBuilder.build_dialogue_messages(
                context=context,
                user_message=user_message,
                system_hint=system_hint,
                is_transition=is_transition,
            )
        else:
            # Fallback to old behavior if no conversation context
            messages = self._legacy_build_messages(user_message, system_hint)

        try:
            resp = self.client.chat.completions.create(
                model=self.model,
                messages=messages,
                temperature=cfg.llm.temperature_chat,
                max_tokens=cfg.llm.max_tokens,
            )
            return resp.choices[0].message.content or "..."
        except Exception as e:
            return f"(Dialogue generation failed: {e})"

    def generate_transition(
        self,
        from_phase: str,
        to_phase: str,
        target_cxn: Optional[str] = None,
    ) -> str:
        """Generate a natural transition utterance between phases."""
        cfg = get_config()

        summary = ""
        if self.conversation:
            summary = self.conversation.state.session_summary

        messages = PromptBuilder.build_transition_prompt(
            from_phase=from_phase,
            to_phase=to_phase,
            target_cxn=target_cxn,
            context_summary=summary,
        )

        try:
            resp = self.client.chat.completions.create(
                model=self.model,
                messages=messages,
                temperature=cfg.llm.temperature_chat,
                max_tokens=256,
            )
            return resp.choices[0].message.content or "Let's continue!"
        except Exception:
            if target_cxn:
                return f"Hey, I noticed you might want to practice '{target_cxn}'. Want to give it a try?"
            return "Great work! Let's keep chatting."

    def update_conversation_context(self) -> None:
        """Trigger background context updates: summary, facts, topic, mood.

        This should be called after the main response is already sent to the user,
        so latency is not critical. All calls are lightweight (small prompts).
        """
        if self.conversation is None:
            return

        cfg = get_config()

        # 1. Update summary if enough turns have accumulated
        if self.conversation.needs_summary_update(threshold_turns=8):
            self._refresh_summary()

        # 2. Extract key facts periodically
        if self.conversation._turn_counter % 5 == 0:
            self._extract_key_facts()

        # 3. Update topic periodically
        if self.conversation._turn_counter % 4 == 0:
            self._detect_topic()

        # 4. Update mood periodically
        if self.conversation._turn_counter % 3 == 0:
            self._detect_mood()

        # Persist
        self.conversation.save()

    # ------------------------------------------------------------------
    # Internal: context refresh helpers
    # ------------------------------------------------------------------

    def _refresh_summary(self) -> None:
        """Incrementally update the session summary."""
        cfg = get_config()
        new_turns = self.conversation.get_turns_since_summary()
        if not new_turns:
            return

        previous = self.conversation.state.session_summary
        messages = PromptBuilder.build_summary_prompt(previous, new_turns)

        try:
            resp = self.client.chat.completions.create(
                model=self.model,
                messages=messages,
                temperature=0.3,
                max_tokens=256,
            )
            new_summary = resp.choices[0].message.content or previous
            self.conversation.update_summary(new_summary.strip())
        except Exception:
            pass  # Keep previous summary on failure

    def _extract_key_facts(self) -> None:
        """Extract new key facts from recent conversation."""
        cfg = get_config()
        turns = self.conversation.get_recent_turns(8)
        messages = PromptBuilder.build_fact_extraction_prompt(turns)

        try:
            resp = self.client.chat.completions.create(
                model=self.model,
                messages=messages,
                temperature=0.2,
                max_tokens=512,
            )
            content = resp.choices[0].message.content or "[]"
            content = content.strip()
            if content.startswith("```json"):
                content = content[7:]
            if content.startswith("```"):
                content = content[3:]
            if content.endswith("```"):
                content = content[:-3]
            content = content.strip()

            facts = json.loads(content)
            for f in facts:
                if isinstance(f, dict) and "fact" in f:
                    self.conversation.add_key_fact(
                        fact=f["fact"],
                        category=f.get("category", ""),
                    )
        except Exception:
            pass  # Silent fail — facts are best-effort

    def _detect_topic(self) -> None:
        """Detect current conversation topic."""
        turns = self.conversation.get_recent_turns(6)
        messages = PromptBuilder.build_topic_detection_prompt(turns)

        try:
            resp = self.client.chat.completions.create(
                model=self.model,
                messages=messages,
                temperature=0.2,
                max_tokens=32,
            )
            topic = resp.choices[0].message.content or "general"
            topic = topic.strip().lower()
            self.conversation.set_topic(topic)
        except Exception:
            pass

    def _detect_mood(self) -> None:
        """Detect learner emotional state from recent messages."""
        turns = self.conversation.get_recent_turns(4)
        messages = PromptBuilder.build_mood_detection_prompt(turns)

        try:
            resp = self.client.chat.completions.create(
                model=self.model,
                messages=messages,
                temperature=0.2,
                max_tokens=16,
            )
            mood = resp.choices[0].message.content or "neutral"
            mood = mood.strip().lower()
            self.conversation.set_mood(mood)
        except Exception:
            pass

    def generate_explanation(self, cxn_id: str, error_explanation: str) -> str:
        """Generate a learner-friendly explanation of a construction."""
        cfg = get_config()

        # Inject conversation context for personalization
        context_snippet = ""
        if self.conversation and self.conversation.state.current_topic:
            context_snippet = (
                f"The learner is currently talking about {self.conversation.state.current_topic}. "
                f"Try to connect examples to this topic when possible.\n\n"
            )

        prompt = f"""Explain the "{cxn_id}" construction to an English language learner.
{context_snippet}Focus: {error_explanation}

Requirements:
- Use simple vocabulary
- Give 2 clear example sentences
- Highlight the pattern with ___ for variable parts
- Add Chinese translation for examples
- Keep under 100 words"""

        try:
            resp = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": "You are a clear, encouraging language teacher."},
                    {"role": "user", "content": prompt},
                ],
                temperature=cfg.llm.temperature_pedagogy,
                max_tokens=cfg.llm.max_tokens,
            )
            return resp.choices[0].message.content or ""
        except Exception:
            return f"[{cxn_id}] is a common English pattern. Let's practice it!"

    # ------------------------------------------------------------------
    # Fallback: legacy prompt building (when no conversation context)
    # ------------------------------------------------------------------

    def _legacy_build_messages(
        self, user_message: str, system_hint: Optional[str] = None
    ) -> List[Dict]:
        cfg = get_config()
        system_msg = (
            "You are a friendly, patient language learning partner. "
            "Engage in natural conversation. Do NOT explicitly correct grammar unless "
            "the learner clearly asks for help or makes a serious error that blocks "
            "communication. Focus on keeping the conversation flowing. "
            "If the learner makes a minor error, naturally model the correct form "
            "in your response without pointing it out (implicit recast). "
            "Always respond in English. Keep responses concise (2-4 sentences)."
        )
        if system_hint:
            system_msg += f"\n\n[Teacher note: {system_hint}]"

        messages = [{"role": "system", "content": system_msg}]
        messages.append({"role": "user", "content": user_message})
        return messages
