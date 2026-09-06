"""Recommended next-readiness actions for SalCAPA capability posture.

Recommendations are decision support only. They identify the next missing
readiness control but do not authorize scope, spending, training or operations.
"""
from __future__ import annotations

from capability_posture import CapabilityMeasure


def next_readiness_action(capability: CapabilityMeasure) -> str:
    e = capability.evidence
    if not e.plan_current:
        return "Planning / Procedure Development"
    if not e.required_training_complete:
        return "Role / Skills Training"
    if not e.exercise_or_real_event_tested:
        return "Exercise / Real-Event Validation"
    if not e.evaluation_complete:
        return "Evaluation / After-Action Review"
    if not e.corrective_actions_closed:
        return "Corrective Action / Improvement Validation"
    if e.evidence_stale or not e.validation_evidence_current or not e.evidence_verified:
        return "Evidence Review / Refresh"
    if not e.performance_target_met:
        return "Performance Improvement / Retest"
    return "Maintain / Sustain Capability"


def action_priority(capability: CapabilityMeasure) -> tuple:
    """Sort lower capability and higher material gaps first."""
    return (capability.demonstrated_score(), -capability.gap_severity, capability.name.lower())
