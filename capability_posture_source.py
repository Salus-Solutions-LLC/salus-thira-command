"""Build capability-posture measures from governed SalTHIRA source records.

The adapter is deliberately conservative and schema-tolerant. It reads the
existing capability, gap and evidence records and only credits evidence states
that are present and current. Planning/training/exercise persistence can add
stronger evidence without creating a duplicate capability inventory.
"""
from __future__ import annotations

from decimal import Decimal
from typing import Iterable

from capability_posture import (
    CapabilityEvidenceState,
    CapabilityMeasure,
    MissionArea,
)
from database import table_columns

SEVERITY_SCORE = {
    "none": Decimal("0"),
    "informational": Decimal("10"),
    "low": Decimal("25"),
    "moderate": Decimal("50"),
    "medium": Decimal("50"),
    "high": Decimal("75"),
    "critical": Decimal("100"),
    "severe": Decimal("100"),
}


def _mission_area(value: str) -> MissionArea:
    normalized = (value or "").strip().lower()
    aliases = {
        "prevent": MissionArea.PREVENTION,
        "prevention": MissionArea.PREVENTION,
        "protect": MissionArea.PROTECTION,
        "protection": MissionArea.PROTECTION,
        "respond": MissionArea.RESPONSE,
        "response": MissionArea.RESPONSE,
        "recover": MissionArea.RECOVERY,
        "recovery": MissionArea.RECOVERY,
        "mitigate": MissionArea.MITIGATION,
        "mitigation": MissionArea.MITIGATION,
    }
    return aliases.get(normalized, MissionArea.RESPONSE)


def _gap_score(conn, assessment_id: int, capability_id: int) -> Decimal:
    rows = conn.execute(
        "SELECT severity,status FROM gaps WHERE assessment_id=? AND capability_id=?",
        (assessment_id, capability_id),
    ).fetchall()
    scores = []
    for row in rows:
        status = str(row["status"] or "").strip().lower()
        if status in {"closed", "resolved", "validated"}:
            continue
        raw = row["severity"]
        try:
            score = Decimal(str(raw))
        except Exception:
            score = SEVERITY_SCORE.get(str(raw or "").strip().lower(), Decimal("50"))
        scores.append(max(Decimal("0"), min(Decimal("100"), score)))
    return max(scores, default=Decimal("0"))


def _performance_target_met(row) -> bool:
    required = row["required_standard"]
    current = row["current_performance"]
    if required is None or current is None:
        return False
    required = Decimal(str(required)); current = Decimal(str(current))
    comparator = str(row["comparator"] if "comparator" in row.keys() else ">=").strip()
    if comparator in {"<=", "≤"}: return current <= required
    if comparator == "<": return current < required
    if comparator in {"=", "=="}: return current == required
    if comparator == ">": return current > required
    return current >= required


def _current_verified(row, columns: set[str]) -> bool:
    verified = str(row["verification_status"] or "").strip().lower() == "verified" if "verification_status" in columns else False
    current = str(row["lifecycle_status"] or "Current").strip().lower() == "current" if "lifecycle_status" in columns else True
    return verified and current


def _evidence_state(conn, assessment_id: int, capability_id: int, target_met: bool) -> CapabilityEvidenceState:
    columns = table_columns(conn, "evidence")
    if not columns or "capability_id" not in columns:
        return CapabilityEvidenceState(performance_target_met=target_met)
    select = ["evidence_type"]
    for name in ("verification_status", "lifecycle_status"):
        if name in columns: select.append(name)
    rows = conn.execute(
        f"SELECT {','.join(select)} FROM evidence WHERE assessment_id=? AND capability_id=?",
        (assessment_id, capability_id),
    ).fetchall()
    types_current = set()
    any_verified = False
    any_stale = False
    for row in rows:
        etype = str(row["evidence_type"] or "").strip().lower()
        verified = str(row["verification_status"] or "").strip().lower() == "verified" if "verification_status" in columns else False
        stale = str(row["lifecycle_status"] or "Current").strip().lower() == "stale" if "lifecycle_status" in columns else False
        any_verified = any_verified or verified
        any_stale = any_stale or stale
        if verified and not stale:
            types_current.add(etype)
    def has_any(words):
        return any(any(word in etype for word in words) for etype in types_current)
    plan = has_any(("plan", "procedure", "sop", "policy", "annex"))
    training = has_any(("training completion", "training evaluation", "qualification", "certification"))
    exercised = has_any(("exercise result", "functional exercise", "full-scale", "tabletop", "drill", "real event", "incident result"))
    evaluated = has_any(("after action", "exercise evaluation", "training evaluation", "evaluation report", "exercise result"))
    corrective = has_any(("corrective action validation", "improvement validation", "validated improvement"))
    validation_current = bool(types_current)
    return CapabilityEvidenceState(
        plan_current=plan,
        required_training_complete=training,
        exercise_or_real_event_tested=exercised,
        evaluation_complete=evaluated,
        corrective_actions_closed=corrective,
        validation_evidence_current=validation_current,
        performance_target_met=target_met,
        evidence_verified=any_verified,
        evidence_stale=any_stale and not validation_current,
    )


def build_capability_measures(conn, assessment_id: int) -> tuple[CapabilityMeasure, ...]:
    columns = table_columns(conn, "capabilities")
    required = {"id", "assessment_id", "name", "mission_area", "required_standard", "current_performance"}
    if not required.issubset(columns):
        missing = ", ".join(sorted(required - columns))
        raise RuntimeError(f"capability schema missing required columns: {missing}")
    select = ["id", "name", "mission_area", "required_standard", "current_performance"]
    if "comparator" in columns: select.append("comparator")
    rows = conn.execute(
        f"SELECT {','.join(select)} FROM capabilities WHERE assessment_id=? ORDER BY id",
        (assessment_id,),
    ).fetchall()
    measures = []
    for row in rows:
        target_met = _performance_target_met(row)
        comparator = str(row["comparator"] if "comparator" in row.keys() else ">=").strip()
        measures.append(CapabilityMeasure(
            capability_id=int(row["id"]),
            name=str(row["name"]),
            mission_area=_mission_area(str(row["mission_area"])),
            required_standard=row["required_standard"],
            current_performance=row["current_performance"],
            higher_is_better=comparator not in {"<=", "<", "≤"},
            gap_severity=_gap_score(conn, assessment_id, int(row["id"])),
            consequence_weight=Decimal("1"),
            evidence=_evidence_state(conn, assessment_id, int(row["id"]), target_met),
        ))
    return tuple(measures)
