"""Persistent SalCAPA Protected Member capability-posture snapshots.

Append-only persistence for Prevention, Protection, Response, Recovery and
Mitigation posture. Historical snapshots retain the scoring version and the
calculated mission-area values in effect at creation time.
"""
from __future__ import annotations

from dataclasses import asdict
from datetime import datetime, timezone
from decimal import Decimal
from typing import Iterable, Optional

from capability_posture import CapabilityMeasure, MissionArea, protected_member_posture

SCORING_VERSION = "1.0.0"

SCHEMA = """
CREATE TABLE IF NOT EXISTS capability_posture_snapshots(
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    tenant_id INTEGER NOT NULL,
    assessment_id INTEGER NOT NULL,
    protected_member_name TEXT NOT NULL,
    overall_score REAL NOT NULL,
    overall_band TEXT NOT NULL,
    overall_confidence TEXT NOT NULL,
    weakest_area TEXT,
    strongest_area TEXT,
    material_gap_count INTEGER NOT NULL DEFAULT 0,
    scoring_version TEXT NOT NULL,
    created_at TEXT NOT NULL,
    created_by TEXT NOT NULL,
    FOREIGN KEY(tenant_id) REFERENCES tenants(id),
    FOREIGN KEY(assessment_id) REFERENCES assessments(id)
);
CREATE TABLE IF NOT EXISTS capability_posture_area_snapshots(
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    snapshot_id INTEGER NOT NULL,
    mission_area TEXT NOT NULL,
    score REAL NOT NULL,
    band TEXT NOT NULL,
    confidence TEXT NOT NULL,
    capability_count INTEGER NOT NULL DEFAULT 0,
    material_gap_count INTEGER NOT NULL DEFAULT 0,
    FOREIGN KEY(snapshot_id) REFERENCES capability_posture_snapshots(id)
);
CREATE TABLE IF NOT EXISTS capability_posture_measure_snapshots(
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    snapshot_id INTEGER NOT NULL,
    capability_id INTEGER NOT NULL,
    capability_name TEXT NOT NULL,
    mission_area TEXT NOT NULL,
    demonstrated_score REAL NOT NULL,
    confidence TEXT NOT NULL,
    gap_severity REAL NOT NULL DEFAULT 0,
    consequence_weight REAL NOT NULL DEFAULT 1,
    evidence_stale INTEGER NOT NULL DEFAULT 0,
    evidence_verified INTEGER NOT NULL DEFAULT 0,
    performance_target_met INTEGER NOT NULL DEFAULT 0,
    FOREIGN KEY(snapshot_id) REFERENCES capability_posture_snapshots(id),
    FOREIGN KEY(capability_id) REFERENCES capabilities(id)
);
CREATE INDEX IF NOT EXISTS idx_posture_snapshots_assessment_created
    ON capability_posture_snapshots(assessment_id, created_at);
CREATE INDEX IF NOT EXISTS idx_posture_snapshots_tenant
    ON capability_posture_snapshots(tenant_id);
CREATE INDEX IF NOT EXISTS idx_posture_area_snapshot
    ON capability_posture_area_snapshots(snapshot_id);
CREATE INDEX IF NOT EXISTS idx_posture_measure_snapshot
    ON capability_posture_measure_snapshots(snapshot_id);
"""


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def ensure_schema(conn) -> None:
    conn.executescript(SCHEMA)
    conn.commit()


def _assessment_belongs_to_tenant(conn, assessment_id: int, tenant_id: int) -> bool:
    row = conn.execute(
        "SELECT id FROM assessments WHERE id=? AND tenant_id=?",
        (assessment_id, tenant_id),
    ).fetchone()
    return row is not None


def save_posture_snapshot(
    conn,
    *,
    tenant_id: int,
    assessment_id: int,
    protected_member_name: str,
    capabilities: Iterable[CapabilityMeasure],
    created_by: str,
    scoring_version: str = SCORING_VERSION,
    created_at: Optional[str] = None,
) -> int:
    """Persist a complete append-only posture snapshot and return snapshot id."""
    ensure_schema(conn)
    if not _assessment_belongs_to_tenant(conn, assessment_id, tenant_id):
        raise ValueError("assessment does not belong to tenant")
    member = (protected_member_name or "").strip()
    actor = (created_by or "").strip()
    if not member:
        raise ValueError("protected_member_name is required")
    if not actor:
        raise ValueError("created_by is required")

    items = tuple(capabilities)
    posture = protected_member_posture(items)
    timestamp = created_at or now_iso()
    cur = conn.execute(
        """INSERT INTO capability_posture_snapshots(
            tenant_id,assessment_id,protected_member_name,overall_score,
            overall_band,overall_confidence,weakest_area,strongest_area,
            material_gap_count,scoring_version,created_at,created_by
        ) VALUES(?,?,?,?,?,?,?,?,?,?,?,?)""",
        (
            tenant_id,
            assessment_id,
            member,
            float(posture.overall_score),
            posture.overall_band.value,
            posture.overall_confidence.value,
            posture.weakest_area.value if posture.weakest_area else None,
            posture.strongest_area.value if posture.strongest_area else None,
            posture.material_gap_count,
            scoring_version,
            timestamp,
            actor,
        ),
    )
    snapshot_id = cur.lastrowid

    for area in posture.mission_areas:
        conn.execute(
            """INSERT INTO capability_posture_area_snapshots(
                snapshot_id,mission_area,score,band,confidence,
                capability_count,material_gap_count
            ) VALUES(?,?,?,?,?,?,?)""",
            (
                snapshot_id,
                area.mission_area.value,
                float(area.score),
                area.band.value,
                area.confidence.value,
                area.capability_count,
                area.material_gap_count,
            ),
        )

    for capability in items:
        conn.execute(
            """INSERT INTO capability_posture_measure_snapshots(
                snapshot_id,capability_id,capability_name,mission_area,
                demonstrated_score,confidence,gap_severity,consequence_weight,
                evidence_stale,evidence_verified,performance_target_met
            ) VALUES(?,?,?,?,?,?,?,?,?,?,?)""",
            (
                snapshot_id,
                capability.capability_id,
                capability.name,
                capability.mission_area.value,
                float(capability.demonstrated_score()),
                capability.confidence().value,
                float(capability.gap_severity),
                float(capability.consequence_weight),
                1 if capability.evidence.evidence_stale else 0,
                1 if capability.evidence.evidence_verified else 0,
                1 if capability.evidence.performance_target_met else 0,
            ),
        )
    conn.commit()
    return int(snapshot_id)


def get_snapshot(conn, *, tenant_id: int, snapshot_id: int) -> Optional[dict]:
    ensure_schema(conn)
    row = conn.execute(
        "SELECT * FROM capability_posture_snapshots WHERE id=? AND tenant_id=?",
        (snapshot_id, tenant_id),
    ).fetchone()
    if row is None:
        return None
    result = dict(row)
    areas = conn.execute(
        "SELECT * FROM capability_posture_area_snapshots WHERE snapshot_id=? ORDER BY id",
        (snapshot_id,),
    ).fetchall()
    measures = conn.execute(
        "SELECT * FROM capability_posture_measure_snapshots WHERE snapshot_id=? ORDER BY mission_area, capability_name",
        (snapshot_id,),
    ).fetchall()
    result["mission_areas"] = [dict(x) for x in areas]
    result["capabilities"] = [dict(x) for x in measures]
    return result


def latest_snapshot(conn, *, tenant_id: int, assessment_id: int) -> Optional[dict]:
    ensure_schema(conn)
    row = conn.execute(
        """SELECT id FROM capability_posture_snapshots
           WHERE tenant_id=? AND assessment_id=?
           ORDER BY created_at DESC, id DESC LIMIT 1""",
        (tenant_id, assessment_id),
    ).fetchone()
    return None if row is None else get_snapshot(conn, tenant_id=tenant_id, snapshot_id=row["id"])


def posture_trend(conn, *, tenant_id: int, assessment_id: int, limit: int = 24) -> list[dict]:
    ensure_schema(conn)
    safe_limit = max(1, min(int(limit), 120))
    rows = conn.execute(
        """SELECT id,overall_score,overall_band,overall_confidence,
                  weakest_area,strongest_area,material_gap_count,
                  scoring_version,created_at
           FROM capability_posture_snapshots
           WHERE tenant_id=? AND assessment_id=?
           ORDER BY created_at DESC, id DESC LIMIT ?""",
        (tenant_id, assessment_id, safe_limit),
    ).fetchall()
    return [dict(x) for x in reversed(rows)]


def dashboard_payload(conn, *, tenant_id: int, assessment_id: int) -> dict:
    snapshot = latest_snapshot(conn, tenant_id=tenant_id, assessment_id=assessment_id)
    if snapshot is None:
        return {
            "status": "Unknown",
            "overall": {"score": None, "band": "Unknown", "confidence": "Low"},
            "mission_areas": [
                {"mission_area": area.value, "score": None, "band": "Unknown", "confidence": "Low", "capability_count": 0, "material_gap_count": 0}
                for area in MissionArea
            ],
            "trend": [],
        }
    area_by_name = {x["mission_area"]: x for x in snapshot["mission_areas"]}
    areas = []
    for area in MissionArea:
        raw = area_by_name.get(area.value)
        if raw is None:
            areas.append({"mission_area": area.value, "score": None, "band": "Unknown", "confidence": "Low", "capability_count": 0, "material_gap_count": 0})
        else:
            areas.append({
                "mission_area": area.value,
                "score": raw["score"],
                "band": raw["band"],
                "confidence": raw["confidence"],
                "capability_count": raw["capability_count"],
                "material_gap_count": raw["material_gap_count"],
            })
    return {
        "status": "Current",
        "snapshot_id": snapshot["id"],
        "protected_member_name": snapshot["protected_member_name"],
        "overall": {
            "score": snapshot["overall_score"],
            "band": snapshot["overall_band"],
            "confidence": snapshot["overall_confidence"],
        },
        "weakest_area": snapshot["weakest_area"],
        "strongest_area": snapshot["strongest_area"],
        "material_gap_count": snapshot["material_gap_count"],
        "scoring_version": snapshot["scoring_version"],
        "created_at": snapshot["created_at"],
        "mission_areas": areas,
        "capabilities": snapshot["capabilities"],
        "trend": posture_trend(conn, tenant_id=tenant_id, assessment_id=assessment_id),
    }
