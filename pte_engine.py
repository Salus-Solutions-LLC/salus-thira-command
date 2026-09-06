"""SalCAPA Planning, Training & Exercise (P/T/E) domain.

Provides a governed lifecycle linking SalTHIRA capability gaps to plans,
training, exercises, evaluation, corrective actions and reassessment.  The
module integrates commercially with pricing_engine without changing governed
THIRA risk calculations.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal
from enum import Enum
from typing import Iterable, Optional

from pricing_engine import (
    D,
    LaborEstimate,
    QuoteInputs,
    QuoteRecommendation,
    RevenueClass,
    recommend_quote,
)


class PTEKind(str, Enum):
    PLANNING = "Planning"
    TRAINING = "Training"
    EXERCISE = "Exercise"


class PlanType(str, Enum):
    STRATEGIC = "Strategic Plan"
    EMERGENCY_OPERATIONS = "Emergency Operations Plan"
    CONTINUITY = "Continuity Plan"
    CRISIS_COMMUNICATIONS = "Crisis Communications Plan"
    SECURITY = "Security Plan"
    PROTECTIVE = "Protective Operations Plan"
    INCIDENT_ACTION = "Incident Action / Response Plan"
    RECOVERY = "Recovery Plan"
    ANNEX = "Plan Annex / Functional Annex"
    SOP = "SOP / Procedure"
    OTHER = "Other Plan"


class TrainingType(str, Enum):
    AWARENESS = "Awareness / Orientation"
    ROLE_BASED = "Role-Based Training"
    SKILLS = "Skills / Task Training"
    LEADERSHIP = "Leadership / Decision Training"
    TRAIN_THE_TRAINER = "Train-the-Trainer"
    REFRESHER = "Refresher / Sustainment"
    REMEDIAL = "Remedial / Corrective Training"
    OTHER = "Other Training"


class ExerciseType(str, Enum):
    SEMINAR = "Seminar"
    WORKSHOP = "Workshop"
    TABLETOP = "Tabletop Exercise"
    GAME = "Game"
    DRILL = "Drill"
    FUNCTIONAL = "Functional Exercise"
    FULL_SCALE = "Full-Scale Exercise"


class PTEStatus(str, Enum):
    PROPOSED = "Proposed"
    AUTHORIZED = "Authorized"
    DESIGN = "Design / Development"
    READY = "Ready"
    CONDUCTED = "Conducted"
    EVALUATING = "Evaluating"
    CORRECTIVE_ACTION = "Corrective Action"
    CLOSED = "Closed"
    CANCELLED = "Cancelled"


class CorrectiveActionStatus(str, Enum):
    OPEN = "Open"
    IN_PROGRESS = "In Progress"
    PENDING_VALIDATION = "Pending Validation"
    VALIDATED = "Validated"
    CLOSED = "Closed"
    ACCEPTED_RISK = "Accepted Risk"


class EvidenceType(str, Enum):
    PLAN = "Approved Plan / Procedure"
    TRAINING_COMPLETION = "Training Completion"
    TRAINING_EVALUATION = "Training Evaluation"
    EXERCISE_RESULT = "Exercise Result"
    AFTER_ACTION_REPORT = "After Action Report"
    IMPROVEMENT_PLAN = "Improvement Plan"
    CORRECTIVE_ACTION_VALIDATION = "Corrective Action Validation"


@dataclass(frozen=True)
class CapabilityLink:
    assessment_id: int
    capability_id: int
    gap_id: Optional[int] = None
    improvement_id: Optional[int] = None
    threat_id: Optional[int] = None
    scenario_id: Optional[int] = None


@dataclass(frozen=True)
class PTEObjective:
    statement: str
    capability_id: Optional[int] = None
    performance_metric: Optional[str] = None
    target: Optional[str] = None


@dataclass(frozen=True)
class PTEWorkPackage:
    kind: PTEKind
    title: str
    status: PTEStatus = PTEStatus.PROPOSED
    plan_type: Optional[PlanType] = None
    training_type: Optional[TrainingType] = None
    exercise_type: Optional[ExerciseType] = None
    capability_links: tuple[CapabilityLink, ...] = field(default_factory=tuple)
    objectives: tuple[PTEObjective, ...] = field(default_factory=tuple)
    authorized_hours: Decimal = D("0")
    authorized_budget: Decimal = D("0")

    def __post_init__(self):
        object.__setattr__(self, "authorized_hours", D(self.authorized_hours))
        object.__setattr__(self, "authorized_budget", D(self.authorized_budget))
        if not self.title.strip():
            raise ValueError("title is required")
        if self.kind == PTEKind.PLANNING and self.plan_type is None:
            raise ValueError("plan_type is required for planning work")
        if self.kind == PTEKind.TRAINING and self.training_type is None:
            raise ValueError("training_type is required for training work")
        if self.kind == PTEKind.EXERCISE and self.exercise_type is None:
            raise ValueError("exercise_type is required for exercise work")
        if self.authorized_hours < 0 or self.authorized_budget < 0:
            raise ValueError("authorization values cannot be negative")


@dataclass(frozen=True)
class ExerciseObservation:
    objective: str
    observed_result: str
    rating: str
    capability_id: Optional[int] = None
    evidence_reference: Optional[str] = None


@dataclass(frozen=True)
class CorrectiveAction:
    title: str
    description: str
    capability_id: Optional[int] = None
    gap_id: Optional[int] = None
    improvement_id: Optional[int] = None
    owner: Optional[str] = None
    due_date: Optional[str] = None
    status: CorrectiveActionStatus = CorrectiveActionStatus.OPEN
    requires_retest: bool = True


@dataclass(frozen=True)
class ReadinessCycle:
    plan_current: bool
    required_training_complete: bool
    exercise_completed: bool
    evaluation_complete: bool
    corrective_actions_closed: bool
    validation_evidence_current: bool

    def completion_score(self) -> Decimal:
        values = (
            self.plan_current,
            self.required_training_complete,
            self.exercise_completed,
            self.evaluation_complete,
            self.corrective_actions_closed,
            self.validation_evidence_current,
        )
        return (D(sum(1 for value in values if value)) / D(len(values)) * D("100")).quantize(D("0.1"))

    def ready_for_capability_credit(self) -> bool:
        return all((
            self.plan_current,
            self.required_training_complete,
            self.exercise_completed,
            self.evaluation_complete,
            self.corrective_actions_closed,
            self.validation_evidence_current,
        ))


DEFAULT_PTE_MINIMUMS = {
    (PTEKind.PLANNING, PlanType.SOP): D("3500"),
    (PTEKind.PLANNING, PlanType.ANNEX): D("5000"),
    (PTEKind.PLANNING, PlanType.EMERGENCY_OPERATIONS): D("12500"),
    (PTEKind.PLANNING, PlanType.CONTINUITY): D("12500"),
    (PTEKind.PLANNING, PlanType.CRISIS_COMMUNICATIONS): D("10000"),
    (PTEKind.PLANNING, PlanType.SECURITY): D("12500"),
    (PTEKind.TRAINING, TrainingType.AWARENESS): D("2500"),
    (PTEKind.TRAINING, TrainingType.ROLE_BASED): D("5000"),
    (PTEKind.TRAINING, TrainingType.SKILLS): D("7500"),
    (PTEKind.TRAINING, TrainingType.LEADERSHIP): D("7500"),
    (PTEKind.TRAINING, TrainingType.TRAIN_THE_TRAINER): D("7500"),
    (PTEKind.EXERCISE, ExerciseType.SEMINAR): D("3500"),
    (PTEKind.EXERCISE, ExerciseType.WORKSHOP): D("5000"),
    (PTEKind.EXERCISE, ExerciseType.TABLETOP): D("7500"),
    (PTEKind.EXERCISE, ExerciseType.DRILL): D("7500"),
    (PTEKind.EXERCISE, ExerciseType.FUNCTIONAL): D("15000"),
    (PTEKind.EXERCISE, ExerciseType.FULL_SCALE): D("30000"),
}


def minimum_pte_price(work: PTEWorkPackage) -> Decimal:
    discriminator = work.plan_type or work.training_type or work.exercise_type
    return DEFAULT_PTE_MINIMUMS.get((work.kind, discriminator), D("5000"))


def recommend_pte_quote(
    work: PTEWorkPackage,
    labor: Iterable[LaborEstimate],
    direct_costs=D("0"),
    pass_through_costs=D("0"),
    complexity_allowance=D("0"),
    contingency=D("0"),
    premium_multiplier=D("1"),
) -> QuoteRecommendation:
    base = recommend_quote(
        QuoteInputs(
            labor=tuple(labor),
            direct_costs=direct_costs,
            pass_through_costs=pass_through_costs,
            complexity_allowance=complexity_allowance,
            contingency=contingency,
            premium_multiplier=premium_multiplier,
        ),
        RevenueClass.SPECIAL_PROJECT,
    )
    minimum = minimum_pte_price(work)
    if base.target_price >= minimum:
        return base
    # Preserve engine-computed economics but enforce a service minimum on target/premium.
    return QuoteRecommendation(
        labor_value=base.labor_value,
        internal_labor_cost=base.internal_labor_cost,
        base_commercial_value=base.base_commercial_value,
        internal_expected_cost=base.internal_expected_cost,
        floor_price=min(base.floor_price, minimum),
        target_price=minimum,
        premium_price=max(base.premium_price, minimum * D("1.20")),
        expected_margin_at_target=(
            (minimum - base.internal_expected_cost) / minimum
            if minimum > 0 else D("0")
        ).quantize(D("0.0001")),
    )


def corrective_actions_required(observations: Iterable[ExerciseObservation]) -> bool:
    adverse = {"Needs Improvement", "Unsatisfactory", "Failed", "Not Demonstrated", "Partial"}
    return any(obs.rating in adverse for obs in observations)


def can_close_pte_cycle(
    status: PTEStatus,
    corrective_actions: Iterable[CorrectiveAction],
    evaluation_complete: bool,
) -> bool:
    if status not in {PTEStatus.EVALUATING, PTEStatus.CORRECTIVE_ACTION, PTEStatus.CONDUCTED}:
        return False
    if not evaluation_complete:
        return False
    blocking = {
        CorrectiveActionStatus.OPEN,
        CorrectiveActionStatus.IN_PROGRESS,
        CorrectiveActionStatus.PENDING_VALIDATION,
    }
    return not any(action.status in blocking for action in corrective_actions)


def next_readiness_action(cycle: ReadinessCycle) -> Optional[PTEKind]:
    if not cycle.plan_current:
        return PTEKind.PLANNING
    if not cycle.required_training_complete:
        return PTEKind.TRAINING
    if not cycle.exercise_completed or not cycle.evaluation_complete:
        return PTEKind.EXERCISE
    if not cycle.corrective_actions_closed or not cycle.validation_evidence_current:
        return PTEKind.EXERCISE
    return None
