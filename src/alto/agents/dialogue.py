"""L4 Dialogue Agent: natural language interaction via LLM.

Handles free conversation, context maintenance, and natural responses.
Does NOT directly teach — that is PedagogicalAgent's job.
"""

from typing import Dict, List, Optional

from alto.config import get_config


class DialogueAgent:
    """LLM-powered conversational agent for free-form interaction."""

    def __init__(self, llm_client, model_name: Optional[str] = None):
        self.client = llm_client
        self.model = model_name or get_config().llm.model_name

    def chat(
        self,
        user_message: str,
        conversation_history: List[Dict[str, str]],
        system_hint: Optional[str] = None,
    ) -> str:
        """Generate a natural conversational response.

        Args:
            user_message: Current user input
            conversation_history: List of {role, content} dicts
            system_hint: Optional hint about detected construction gaps

        Returns:
            Natural language response string
        """
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

        # Add recent conversation history
        for turn in conversation_history[-6:]:
            messages.append({"role": turn["role"], "content": turn["content"]})

        messages.append({"role": "user", "content": user_message})

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

    def generate_explanation(self, cxn_id: str, error_explanation: str) -> str:
        """Generate a learner-friendly explanation of a construction."""
        cfg = get_config()

        prompt = f"""Explain the "{cxn_id}" construction to an English language learner.
Focus: {error_explanation}

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
