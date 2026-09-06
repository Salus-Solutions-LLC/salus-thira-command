from decimal import Decimal

from pricing_engine import DEFAULT_LABOR_CATEGORIES, LaborEstimate
from pte_engine import (
    CorrectiveAction, CorrectiveActionStatus, ExerciseObservation, ExerciseType,
    PTEKind, PTEStatus, PTEWorkPackage, PlanType, ReadinessCycle, TrainingType,
    can_close_pte_cycle, corrective_actions_required, minimum_pte_price,
    next_readiness_action, recommend_pte_quote,
)


def test_each_pte_kind_requires_its_specific_type():
    try:
        PTEWorkPackage(PTEKind.PLANNING, "Plan")
        assert False
    except ValueError:
        pass
    try:
        PTEWorkPackage(PTEKind.TRAINING, "Training")
        assert False
    except ValueError:
        pass
    try:
        PTEWorkPackage(PTEKind.EXERCISE, "Exercise")
        assert False
    except ValueError:
        pass


def test_pte_minimum_pricing():
    ttx = PTEWorkPackage(PTEKind.EXERCISE, "Executive TTX", exercise_type=ExerciseType.TABLETOP)
    fse = PTEWorkPackage(PTEKind.EXERCISE, "Full Scale", exercise_type=ExerciseType.FULL_SCALE)
    eop = PTEWorkPackage(PTEKind.PLANNING, "EOP", plan_type=PlanType.EMERGENCY_OPERATIONS)
    assert minimum_pte_price(ttx) == Decimal("7500")
    assert minimum_pte_price(fse) == Decimal("30000")
    assert minimum_pte_price(eop) == Decimal("12500")


def test_pte_quote_enforces_service_minimum_and_margin_logic():
    work = PTEWorkPackage(PTEKind.TRAINING, "Role Training", training_type=TrainingType.ROLE_BASED)
    labor = (LaborEstimate(DEFAULT_LABOR_CATEGORIES["Senior Consultant"], 4, 150),)
    q = recommend_pte_quote(work, labor)
    assert q.target_price >= Decimal("5000")
    assert q.premium_price >= q.target_price


def test_adverse_exercise_observation_requires_corrective_action():
    observations = (
        ExerciseObservation("Notify leadership", "Late", "Needs Improvement"),
        ExerciseObservation("Accountability", "Complete", "Satisfactory"),
    )
    assert corrective_actions_required(observations)


def test_cycle_cannot_close_with_open_corrective_action():
    action = CorrectiveAction("Fix notification", "Revise process", status=CorrectiveActionStatus.OPEN)
    assert not can_close_pte_cycle(PTEStatus.CORRECTIVE_ACTION, (action,), True)
    closed = CorrectiveAction("Fix notification", "Revise process", status=CorrectiveActionStatus.VALIDATED)
    assert can_close_pte_cycle(PTEStatus.CORRECTIVE_ACTION, (closed,), True)


def test_readiness_requires_plan_training_exercise_evaluation_and_validation():
    incomplete = ReadinessCycle(True, True, True, True, False, False)
    complete = ReadinessCycle(True, True, True, True, True, True)
    assert incomplete.completion_score() == Decimal("66.7")
    assert not incomplete.ready_for_capability_credit()
    assert complete.completion_score() == Decimal("100.0")
    assert complete.ready_for_capability_credit()


def test_next_readiness_action_follows_plan_train_exercise_cycle():
    assert next_readiness_action(ReadinessCycle(False, False, False, False, False, False)) == PTEKind.PLANNING
    assert next_readiness_action(ReadinessCycle(True, False, False, False, False, False)) == PTEKind.TRAINING
    assert next_readiness_action(ReadinessCycle(True, True, False, False, False, False)) == PTEKind.EXERCISE
    assert next_readiness_action(ReadinessCycle(True, True, True, True, True, True)) is None
