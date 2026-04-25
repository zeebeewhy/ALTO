"""Core Pydantic data models: inter-layer communication protocols."""

from typing import Dict, List, Optional, Literal
from pydantic import BaseModel, Field
from datetime import datetime


class SlotBinding(BaseModel):
    """Slot-filling binding: symbolic layer core data structure."""
    slot_name: str
    filler_text: str
    filler_lemma: Optional[str] = None
    confidence: float = Field(default=1.0, ge=0.0, le=1.0)


class ConstructionPattern(BaseModel):
    """A construction pattern extracted from learner input."""
    cxn_id: str  # e.g., "ditransitive", "want-to-V", "passive"
    cxn_type: Literal["lexical", "syntactic", "semantic", "pragmatic"] = "syntactic"
    slots: List[SlotBinding] = Field(default_factory=list)
    missing_slots: List[str] = Field(default_factory=list)
    wrong_slots: Dict[str, str] = Field(default_factory=dict)
    syntax_signature: Optional[Dict] = None
    semantic_frame: Optional[str] = None


class DiagnosisReport(BaseModel):
    """Diagnosis protocol: fusion output of symbolic + neural layers."""
    target_cxn: Optional[str] = None
    filled_slots: Dict[str, str] = Field(default_factory=dict)
    missing_slots: List[str] = Field(default_factory=list)
    wrong_slots: Dict[str, str] = Field(default_factory=dict)
    error_type: Literal["none", "omission", "commission", "misordering", "creative"] = "none"
    zpd_recommendation: Literal[
        "demonstration", "scaffolded_production", "guided_production", "refinement"
    ] = "demonstration"
    explanation: str = ""
    is_systematic: bool = False
    # FCG integration hook
    fcg_applied: bool = False
    fcg_result: Optional[Dict] = None


class ConstructionState(BaseModel):
    """Declarative memory entry for a single construction."""
    activation: float = Field(default=0.0, ge=0.0, le=1.0)
    stable: bool = False
    error_patterns: List[Dict] = Field(default_factory=list)
    last_seen: float = Field(default_factory=lambda: datetime.now().timestamp())
    exposure_count: int = 0
    success_count: int = 0
    systematic_error_count: int = 0


class TeachingStrategy(BaseModel):
    """Output of procedural memory: what to do next."""
    mode: Literal[
        "demonstration", "scaffolded_production", "guided_production", "refinement"
    ] = "demonstration"
    instruction: str = ""
    constraint: str = ""
    allow_free: bool = False


class LessonMaterial(BaseModel):
    """Generated lesson content."""
    title: str = ""
    content: str = ""
    exercise: str = ""
    expected_pattern: str = ""
    hints: List[str] = Field(default_factory=list)


class LearnerProfile(BaseModel):
    """Long-term learner portrait."""
    user_id: str
    native_language: Optional[str] = None
    target_language: str = "en"
    proficiency_level: Literal["A1", "A2", "B1", "B2", "C1", "C2", "unknown"] = "unknown"
    total_sessions: int = 0
    total_interactions: int = 0
    registered_at: float = Field(default_factory=lambda: datetime.now().timestamp())
