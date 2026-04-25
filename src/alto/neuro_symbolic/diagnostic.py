"""Neuro-Symbolic Diagnosis Engine.

Symbolic side: spaCy pretrained dependency parsing (self-supervised, no manual annotation).
Neural side: LLM zero-shot semantic role labeling + error classification.
Fusion: DiagnosisReport bridging both worlds.

Theory: Construction Grammar (Slot-filling) + Neuro-Symbolic AI (Torres-Martinez 2025).
"""

import json
import re
from typing import Dict, List, Optional

from alto.config import get_config
from alto.models import DiagnosisReport


class ConstructionDiagnosis:
    """Hybrid diagnosis: spaCy syntax signature + LLM zero-shot semantic analysis."""

    def __init__(self):
        self._nlp = None
        self._spacy_available = False
        self._init_spacy()

    def _init_spacy(self) -> None:
        """Lazy-load spaCy model."""
        try:
            import spacy
            cfg = get_config()
            model_name = cfg.diagnostic.spacy_model
            self._nlp = spacy.load(model_name)
            self._spacy_available = True
        except (ImportError, OSError):
            self._spacy_available = False

    def _extract_syntax_signature(self, sentence: str) -> Dict:
        """Extract syntactic skeleton from sentence using spaCy (self-supervised).

        Returns dict with root, subjects, objects, indirect objects, prepositional objects,
        modifiers, and full token details.
        """
        if not self._spacy_available or self._nlp is None:
            return {"error": "spaCy model not available", "tokens": []}

        doc = self._nlp(sentence)
        sig = {
            "root": None,
            "nsubj": [],
            "dobj": [],
            "pobj": [],
            "iobj": [],
            "amod": [],
            "advmod": [],
            "aux": [],
            "prep": [],
            "tokens": [],
        }

        for token in doc:
            tok_info = {
                "text": token.text,
                "lemma": token.lemma_,
                "pos": token.pos_,
                "dep": token.dep_,
                "head": token.head.text,
                "idx": token.i,
            }
            sig["tokens"].append(tok_info)

            if token.dep_ == "ROOT":
                sig["root"] = {"text": token.text, "lemma": token.lemma_, "pos": token.pos_}
            elif token.dep_ in ("nsubj", "nsubjpass"):
                sig["nsubj"].append(token.text)
            elif token.dep_ == "dobj":
                sig["dobj"].append(token.text)
            elif token.dep_ in ("dative", "iobj"):
                sig["iobj"].append(token.text)
            elif token.dep_ == "pobj" or (token.dep_ == "dobj" and token.head.dep_ == "prep"):
                sig["pobj"].append(token.text)
            elif token.dep_ == "amod":
                sig["amod"].append(token.text)
            elif token.dep_ == "advmod":
                sig["advmod"].append(token.text)
            elif token.dep_ == "aux":
                sig["aux"].append(token.text)
            elif token.dep_ == "prep":
                sig["prep"].append(token.text)

        # Detect common construction patterns from syntax
        sig["detected_patterns"] = self._detect_patterns(sig)
        return sig

    def _detect_patterns(self, sig: Dict) -> List[str]:
        """Heuristic pattern detection from syntax signature."""
        patterns = []
        root = sig.get("root", {})
        root_lemma = (root.get("lemma") or "").lower()
        root_pos = root.get("pos", "")

        # Ditransitive pattern: V + NP + NP
        if sig["dobj"] and sig["iobj"]:
            patterns.append("ditransitive")
        elif sig["dobj"] and sig["pobj"] and root_lemma in ("give", "tell", "show", "send"):
            patterns.append("prepositional_dative")

        # Want-to-V pattern
        if root_lemma == "want" and any(t["dep"] == "xcomp" for t in sig["tokens"]):
            patterns.append("want-to-V")

        # Passive pattern
        if any(t["dep"] == "nsubjpass" for t in sig["tokens"]):
            patterns.append("passive")

        # Modal + V pattern
        if sig["aux"] and root_pos == "VERB":
            patterns.append("modal-verb")

        # TO-infinitive omission candidate
        if root_lemma in ("want", "need", "like", "love", "hate") and not any(
            t["text"].lower() == "to" for t in sig["tokens"]
        ):
            patterns.append("to-infinitive-omission-candidate")

        return patterns

    def diagnose(
        self,
        sentence: str,
        target_cxn: Optional[str] = None,
        llm_client=None,
        model_name: Optional[str] = None,
    ) -> DiagnosisReport:
        """Full neuro-symbolic diagnosis pipeline.

        1. Symbolic layer extracts spaCy dependency signature
        2. Neural layer (LLM zero-shot) analyzes semantic roles and errors
        3. Fusion produces DiagnosisReport

        Args:
            sentence: Learner's input sentence
            target_cxn: Expected construction (if known), e.g. "ditransitive"
            llm_client: OpenAI-compatible client instance
            model_name: LLM model name to use

        Returns:
            DiagnosisReport with slots, errors, ZPD recommendation
        """
        # Step 1: Symbolic extraction
        sig = self._extract_syntax_signature(sentence)

        # Step 2: Neural analysis via LLM
        if llm_client and model_name:
            try:
                neural_result = self._neural_analysis(
                    sentence, sig, target_cxn, llm_client, model_name
                )
            except Exception:
                cfg = get_config()
                if cfg.diagnostic.fallback_enabled:
                    neural_result = self._fallback_diagnosis(sentence, sig)
                else:
                    neural_result = self._empty_result()
        else:
            neural_result = self._fallback_diagnosis(sentence, sig)

        # Step 3: Fusion
        report = DiagnosisReport(
            target_cxn=neural_result.get("target_cxn") or target_cxn,
            filled_slots=neural_result.get("filled_slots", {}),
            missing_slots=neural_result.get("missing_slots", []),
            wrong_slots=neural_result.get("wrong_slots", {}),
            error_type=neural_result.get("error_type", "none"),
            zpd_recommendation=neural_result.get(
                "zpd_recommendation", "demonstration"
            ),
            explanation=neural_result.get("explanation", ""),
            is_systematic=neural_result.get("is_systematic", False),
        )

        # Override with heuristic if LLM failed to detect
        if not report.target_cxn and sig.get("detected_patterns"):
            report.target_cxn = sig["detected_patterns"][0]

        return report

    def _neural_analysis(
        self,
        sentence: str,
        sig: Dict,
        target_cxn: Optional[str],
        llm_client,
        model_name: str,
    ) -> Dict:
        """Call LLM for zero-shot semantic analysis."""
        cfg = get_config()

        prompt = f"""You are an expert in Construction Grammar and language acquisition.
Analyze the following learner sentence and determine if they successfully used a target construction,
or what knowledge gap is exposed.

[SENTENCE]: {sentence}
[spaCy SYNTAX SIGNATURE]: {json.dumps(sig, ensure_ascii=False)}
[TARGET CONSTRUCTION]: {target_cxn or "Not set — infer from the sentence what construction the learner is attempting"}

Output ONLY a JSON object with this exact structure:
{{
  "target_cxn": "construction name, e.g. ditransitive, want-to-V, passive",
  "filled_slots": {{"slot_name": "filler_word"}},
  "missing_slots": ["list of missing slots"],
  "wrong_slots": {{"slot_name": "description of error"}},
  "error_type": "none | omission | commission | misordering | creative",
  "is_systematic": true or false,
  "explanation": "One sentence explaining the error in learner-friendly terms",
  "zpd_recommendation": "demonstration | scaffolded_production | guided_production | refinement"
}}

Error type rules:
- omission: missing necessary element (e.g., missing "to" after "want", missing object)
- commission: extra or wrong element (e.g., wrong tense, wrong preposition)
- misordering: word order error
- creative: interesting attempt close to target but not yet conventional (overgeneralization), worth encouraging
- none: correct usage, or no clear target construction detected

Systematicity: true if this reflects a knowledge gap (recurring pattern), false if it seems like a typo or slip."""

        resp = llm_client.chat.completions.create(
            model=model_name,
            messages=[
                {"role": "system", "content": "You are a language acquisition analysis assistant. Output valid JSON only."},
                {"role": "user", "content": prompt},
            ],
            temperature=cfg.llm.temperature_diagnosis,
            max_tokens=cfg.llm.max_tokens,
        )

        content = resp.choices[0].message.content or ""
        # Extract JSON from possible markdown
        content = content.strip()
        if content.startswith("```json"):
            content = content[7:]
        if content.startswith("```"):
            content = content[3:]
        if content.endswith("```"):
            content = content[:-3]
        content = content.strip()

        return json.loads(content)

    def _fallback_diagnosis(self, sentence: str, sig: Dict) -> Dict:
        """Rule-based heuristic diagnosis when LLM is unavailable."""
        lower = sentence.lower()
        root = (sig.get("root") or {}).get("lemma", "")

        # When spaCy is unavailable, fall back to string heuristics
        if not root:
            if "want" in lower and "to " not in lower:
                return {
                    "target_cxn": "want-to-V",
                    "filled_slots": {"verb": "want"},
                    "missing_slots": ["to-infinitive"],
                    "wrong_slots": {},
                    "error_type": "omission",
                    "is_systematic": True,
                    "explanation": "After 'want', we usually need 'to' before the next verb.",
                    "zpd_recommendation": "scaffolded_production",
                }
            if "want" in lower and "to " in lower:
                return {
                    "target_cxn": "want-to-V",
                    "filled_slots": {"verb": "want", "to": "to"},
                    "missing_slots": [],
                    "wrong_slots": {},
                    "error_type": "none",
                    "is_systematic": False,
                    "explanation": "Correct usage of want-to-V.",
                    "zpd_recommendation": "refinement",
                }
            if any(v in lower for v in ["give", "tell", "show", "send"]):
                return {
                    "target_cxn": "ditransitive",
                    "filled_slots": {},
                    "missing_slots": [],
                    "wrong_slots": {},
                    "error_type": "none",
                    "is_systematic": False,
                    "explanation": "",
                    "zpd_recommendation": "demonstration",
                }
            return self._empty_result()

        # When spaCy IS available, use root + dependency info
            return {
                "target_cxn": "want-to-V",
                "filled_slots": {"verb": "want"},
                "missing_slots": ["to-infinitive"],
                "wrong_slots": {},
                "error_type": "omission",
                "is_systematic": True,
                "explanation": "After 'want', we usually need 'to' before the next verb.",
                "zpd_recommendation": "scaffolded_production",
            }

        # Rule: ditransitive pattern check
        if root in ("give", "tell", "show", "send"):
            has_dobj = bool(sig.get("dobj"))
            has_iobj = bool(sig.get("iobj")) or bool(sig.get("pobj"))
            if has_dobj and not has_iobj:
                return {
                    "target_cxn": "ditransitive",
                    "filled_slots": {"verb": root, "theme": sig["dobj"][0] if sig["dobj"] else ""},
                    "missing_slots": ["recipient"],
                    "wrong_slots": {},
                    "error_type": "omission",
                    "is_systematic": True,
                    "explanation": f"'{root}' usually needs both a thing and a person receiving it.",
                    "zpd_recommendation": "demonstration",
                }

        # Rule: passive without be-verb
        if any(t.get("dep") == "nsubjpass" for t in sig.get("tokens", [])):
            has_be = any(t.get("lemma") in ("be", "was", "were", "is", "are") for t in sig.get("tokens", []))
            if not has_be:
                return {
                    "target_cxn": "passive",
                    "filled_slots": {},
                    "missing_slots": ["be-verb"],
                    "wrong_slots": {},
                    "error_type": "omission",
                    "is_systematic": True,
                    "explanation": "Passive sentences need a form of 'be' before the past participle.",
                    "zpd_recommendation": "scaffolded_production",
                }

        return self._empty_result()

    def _empty_result(self) -> Dict:
        return {
            "target_cxn": None,
            "filled_slots": {},
            "missing_slots": [],
            "wrong_slots": {},
            "error_type": "none",
            "is_systematic": False,
            "explanation": "",
            "zpd_recommendation": "demonstration",
        }
