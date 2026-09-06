from decimal import Decimal

from capability_posture import (
    CapabilityBand, CapabilityEvidenceState, CapabilityMeasure, EvidenceConfidence,
    MissionArea, capability_band, mission_area_posture, protected_member_posture,
    readiness_matrix,
)


def capable(cid, name, area, gap=0, weight=1):
    return CapabilityMeasure(
        capability_id=cid,
        name=name,
        mission_area=area,
        required_standard=10,
        current_performance=10,
        higher_is_better=True,
        gap_severity=gap,
        consequence_weight=weight,
        evidence=CapabilityEvidenceState(
            plan_current=True,
            required_training_complete=True,
            exercise_or_real_event_tested=True,
            evaluation_complete=True,
            corrective_actions_closed=True,
            validation_evidence_current=True,
            performance_target_met=True,
            evidence_verified=True,
            evidence_stale=False,
        ),
    )


def test_documentation_alone_cannot_create_high_capability():
    c = CapabilityMeasure(
        1, "Alerting", MissionArea.RESPONSE,
        required_standard=10, current_performance=10,
        evidence=CapabilityEvidenceState(plan_current=True, evidence_verified=True),
    )
    assert c.demonstrated_score() <= Decimal("50")
    assert c.confidence() == EvidenceConfidence.MODERATE


def test_stale_evidence_caps_credit():
    c = CapabilityMeasure(
        2, "Continuity", MissionArea.RECOVERY,
        required_standard=10, current_performance=10,
        evidence=CapabilityEvidenceState(
            plan_current=True, required_training_complete=True,
            exercise_or_real_event_tested=True, evaluation_complete=True,
            corrective_actions_closed=True, validation_evidence_current=True,
            performance_target_met=True, evidence_verified=True, evidence_stale=True,
        ),
    )
    assert c.demonstrated_score() <= Decimal("74")
    assert c.confidence() != EvidenceConfidence.HIGH


def test_material_gap_reduces_demonstrated_score():
    base = capable(1, "Access control", MissionArea.PROTECTION, gap=0)
    gap = capable(2, "Access control", MissionArea.PROTECTION, gap=80)
    assert gap.demonstrated_score() < base.demonstrated_score()


def test_all_five_mission_areas_are_present_in_matrix():
    capabilities = [
        capable(1, "Preventive intel", MissionArea.PREVENTION),
        capable(2, "Physical security", MissionArea.PROTECTION),
        capable(3, "Incident command", MissionArea.RESPONSE),
        capable(4, "Continuity", MissionArea.RECOVERY),
        capable(5, "Flood mitigation", MissionArea.MITIGATION),
    ]
    matrix = readiness_matrix(capabilities)
    assert set(matrix) == {x.value for x in MissionArea}
    assert all(matrix[x.value]["band"] == CapabilityBand.DEMONSTRATED.value for x in MissionArea)


def test_missing_mission_area_is_unknown_not_zero_capability():
    p = protected_member_posture([capable(1, "Incident command", MissionArea.RESPONSE)])
    prevention = [x for x in p.mission_areas if x.mission_area == MissionArea.PREVENTION][0]
    assert prevention.band == CapabilityBand.UNKNOWN


def test_overall_equal_weights_populated_mission_areas():
    response = capable(1, "Response", MissionArea.RESPONSE)
    weak = CapabilityMeasure(
        2, "Recovery", MissionArea.RECOVERY,
        evidence=CapabilityEvidenceState(plan_current=True),
    )
    p = protected_member_posture([response, weak])
    assert p.weakest_area == MissionArea.RECOVERY
    assert p.strongest_area == MissionArea.RESPONSE
    assert p.overall_score < response.demonstrated_score()


def test_consequence_weighting_occurs_inside_mission_area():
    strong = capable(1, "Strong", MissionArea.RESPONSE, weight=1)
    weak = CapabilityMeasure(
        2, "Critical weak function", MissionArea.RESPONSE,
        gap_severity=100, consequence_weight=5,
        evidence=CapabilityEvidenceState(plan_current=True),
    )
    area = mission_area_posture(MissionArea.RESPONSE, [strong, weak])
    assert area.score < Decimal("50")
    assert area.material_gap_count == 1


def test_capability_band_thresholds():
    assert capability_band(10) == CapabilityBand.CRITICAL
    assert capability_band(30) == CapabilityBand.WEAK
    assert capability_band(50) == CapabilityBand.DEVELOPING
    assert capability_band(65) == CapabilityBand.CAPABLE
    assert capability_band(80) == CapabilityBand.STRONG
    assert capability_band(95) == CapabilityBand.DEMONSTRATED
