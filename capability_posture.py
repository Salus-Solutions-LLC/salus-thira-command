"""SalCAPA Protected Member capability posture model.

Calculates evidence-based capability posture across Prevention, Protection,
Response, Recovery, and Mitigation.  The model is designed to consume governed
SalTHIRA capability/evidence state plus Planning, Training & Exercise readiness
without changing the existing THIRA risk formula.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal, ROUND_HALF_UP
from enum import Enum
from typing import Iterable, Optional

from pricing_engine import D


class MissionArea(str, Enum):
    PREVENTION = "Prevention"
    PROTECTION = "Protection"
    RESPONSE = "Response"
    RECOVERY = "Recovery"
    MITIGATION = "Mitigation"


class CapabilityBand(str, Enum):
    UNKNOWN = "Unknown"
    CRITICAL = "Critical"
    WEAK = "Weak"
    DEVELOPING = "Developing"
    CAPABLE = "Capable"
    STRONG = "Strong"
    DEMONSTRATED = "Demonstrated"


class EvidenceConfidence(str, Enum):
    LOW = "Low"
    MODERATE = "Moderate"
    HIGH = "High"


@dataclass(frozen=True)
class CapabilityEvidenceState:
    plan_current: bool = False
    required_training_complete: bool = False
    exercise_or_real_event_tested: bool = False
    evaluation_complete: bool = False
    corrective_actions_closed: bool = False
    validation_evidence_current: bool = False
    performance_target_met: bool = False
    evidence_verified: bool = False
    evidence_stale: bool = False

    def evidence_gate_passed(self) -> bool:
        return self.evidence_verified and not self.evidence_stale and self.validation_evidence_current


@dataclass(frozen=True)
class CapabilityMeasure:
    capability_id: int
    name: str
    mission_area: MissionArea
    required_standard: Optional[Decimal] = None
    current_performance: Optional[Decimal] = None
    higher_is_better: bool = True
    gap_severity: Decimal = D("0")
    consequence_weight: Decimal = D("1")
    evidence: CapabilityEvidenceState = field(default_factory=CapabilityEvidenceState)

    def __post_init__(self):
        for name in ("gap_severity", "consequence_weight"):
            object.__setattr__(self, name, D(getattr(self, name)))
        if self.required_standard is not None:
            object.__setattr__(self, "required_standard", D(self.required_standard))
        if self.current_performance is not None:
            object.__setattr__(self, "current_performance", D(self.current_performance))
        if self.gap_severity < 0 or self.gap_severity > 100:
            raise ValueError("gap_severity must be between 0 and 100")
        if self.consequence_weight <= 0:
            raise ValueError("consequence_weight must be greater than zero")

    def measured_performance_score(self) -> Optional[Decimal]:
        if self.required_standard is None or self.current_performance is None:
            return None
        if self.required_standard == 0:
            return D("100") if self.current_performance == 0 else D("0")
        if self.higher_is_better:
            ratio = self.current_performance / self.required_standard
        else:
            if self.current_performance <= 0:
                ratio = D("1")
            else:
                ratio = self.required_standard / self.current_performance
        return max(D("0"), min(D("100"), ratio * D("100"))).quantize(D("0.1"), rounding=ROUND_HALF_UP)

    def demonstrated_score(self) -> Decimal:
        """Return a conservative 0-100 capability score.

        Documentation alone cannot create a high score. Demonstrated performance,
        current verified evidence, completed training/exercise evaluation, and
        closed corrective actions progressively unlock higher score ceilings.
        """
        e = self.evidence
        foundation = D("0")
        foundation += D("15") if e.plan_current else D("0")
        foundation += D("15") if e.required_training_complete else D("0")
        foundation += D("15") if e.exercise_or_real_event_tested else D("0")
        foundation += D("10") if e.evaluation_complete else D("0")
        foundation += D("10") if e.corrective_actions_closed else D("0")
        foundation += D("15") if e.evidence_gate_passed() else D("0")
        foundation += D("20") if e.performance_target_met else D("0")

        measured = self.measured_performance_score()
        if measured is not None:
            # Blend lifecycle readiness with observed performance; measured results
            # are important but cannot bypass missing governance/evidence controls.
            score = foundation * D("0.55") + measured * D("0.45")
        else:
            score = foundation

        # Fail-closed ceilings.
        if not e.plan_current:
            score = min(score, D("35"))
        if not e.required_training_complete:
            score = min(score, D("50"))
        if not e.exercise_or_real_event_tested:
            score = min(score, D("60"))
        if not e.evaluation_complete:
            score = min(score, D("65"))
        if not e.corrective_actions_closed:
            score = min(score, D("70"))
        if not e.evidence_gate_passed():
            score = min(score, D("74"))
        if not e.performance_target_met:
            score = min(score, D("79"))

        # Material gaps reduce current demonstrated capability.
        gap_penalty = self.gap_severity * D("0.30")
        return max(D("0"), score - gap_penalty).quantize(D("0.1"), rounding=ROUND_HALF_UP)

    def confidence(self) -> EvidenceConfidence:
        e = self.evidence
        if e.evidence_gate_passed() and e.exercise_or_real_event_tested and e.evaluation_complete:
            return EvidenceConfidence.HIGH
        if e.evidence_verified and not e.evidence_stale and (e.required_training_complete or e.plan_current):
            return EvidenceConfidence.MODERATE
        return EvidenceConfidence.LOW


@dataclass(frozen=True)
class MissionAreaPosture:
    mission_area: MissionArea
    score: Decimal
    band: CapabilityBand
    confidence: EvidenceConfidence
    capability_count: int
    material_gap_count: int


@dataclass(frozen=True)
class ProtectedMemberPosture:
    overall_score: Decimal
    overall_band: CapabilityBand
    overall_confidence: EvidenceConfidence
    mission_areas: tuple[MissionAreaPosture, ...]
    weakest_area: Optional[MissionArea]
    strongest_area: Optional[MissionArea]
    material_gap_count: int


def capability_band(score: Decimal, has_data: bool = True) -> CapabilityBand:
    if not has_data:
        return CapabilityBand.UNKNOWN
    score = D(score)
    if score < 25:
        return CapabilityBand.CRITICAL
    if score < 40:
        return CapabilityBand.WEAK
    if score < 60:
        return CapabilityBand.DEVELOPING
    if score < 75:
        return CapabilityBand.CAPABLE
    if score < 90:
        return CapabilityBand.STRONG
    return CapabilityBand.DEMONSTRATED


def _confidence_rank(value: EvidenceConfidence) -> int:
    return {EvidenceConfidence.LOW: 1, EvidenceConfidence.MODERATE: 2, EvidenceConfidence.HIGH: 3}[value]


def _rank_confidence(rank: int) -> EvidenceConfidence:
    if rank >= 3:
        return EvidenceConfidence.HIGH
    if rank >= 2:
        return EvidenceConfidence.MODERATE
    return EvidenceConfidence.LOW


def mission_area_posture(area: MissionArea, capabilities: Iterable[CapabilityMeasure]) -> MissionAreaPosture:
    items = [c for c in capabilities if c.mission_area == area]
    if not items:
        return MissionAreaPosture(area, D("0"), CapabilityBand.UNKNOWN, EvidenceConfidence.LOW, 0, 0)
    total_weight = sum((c.consequence_weight for c in items), D("0"))
    weighted = sum((c.demonstrated_score() * c.consequence_weight for c in items), D("0"))
    score = (weighted / total_weight).quantize(D("0.1"), rounding=ROUND_HALF_UP)
    confidence_average = sum((_confidence_rank(c.confidence()) for c in items)) / len(items)
    confidence = _rank_confidence(round(confidence_average))
    material_gaps = sum(1 for c in items if c.gap_severity >= D("40"))
    return MissionAreaPosture(area, score, capability_band(score), confidence, len(items), material_gaps)


def protected_member_posture(capabilities: Iterable[CapabilityMeasure]) -> ProtectedMemberPosture:
    items = tuple(capabilities)
    areas = tuple(mission_area_posture(area, items) for area in MissionArea)
    populated = [a for a in areas if a.capability_count > 0]
    if not populated:
        return ProtectedMemberPosture(D("0"), CapabilityBand.UNKNOWN, EvidenceConfidence.LOW, areas, None, None, 0)

    # Equal mission-area weighting prevents a heavily populated area from hiding a
    # weak but mission-critical area.  Capability consequence weighting occurs
    # inside each mission area.
    overall = (sum((a.score for a in populated), D("0")) / D(len(populated))).quantize(D("0.1"), rounding=ROUND_HALF_UP)
    weakest = min(populated, key=lambda x: x.score).mission_area
    strongest = max(populated, key=lambda x: x.score).mission_area
    confidence = _rank_confidence(round(sum(_confidence_rank(a.confidence) for a in populated) / len(populated)))
    gaps = sum(a.material_gap_count for a in populated)
    return ProtectedMemberPosture(overall, capability_band(overall), confidence, areas, weakest, strongest, gaps)


def readiness_matrix(capabilities: Iterable[CapabilityMeasure]) -> dict[str, dict[str, object]]:
    posture = protected_member_posture(capabilities)
    return {
        area.mission_area.value: {
            "score": str(area.score),
            "band": area.band.value,
            "confidence": area.confidence.value,
            "capabilities": area.capability_count,
            "material_gaps": area.material_gap_count,
        }
        for area in posture.mission_areas
    }
