import sqlite3
from decimal import Decimal

from capability_posture import (
    CapabilityEvidenceState, CapabilityMeasure, MissionArea,
)
from capability_posture_store import (
    dashboard_payload, ensure_schema, get_snapshot, latest_snapshot,
    posture_trend, save_posture_snapshot,
)


def conn_with_core_schema():
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    conn.executescript("""
        CREATE TABLE tenants(id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT);
        CREATE TABLE assessments(id INTEGER PRIMARY KEY AUTOINCREMENT, tenant_id INTEGER NOT NULL, name TEXT,
            FOREIGN KEY(tenant_id) REFERENCES tenants(id));
        CREATE TABLE capabilities(id INTEGER PRIMARY KEY AUTOINCREMENT, assessment_id INTEGER NOT NULL, name TEXT,
            FOREIGN KEY(assessment_id) REFERENCES assessments(id));
    """)
    tid = conn.execute("INSERT INTO tenants(name) VALUES('Protected Member A')").lastrowid
    aid = conn.execute("INSERT INTO assessments(tenant_id,name) VALUES(?,?)", (tid, "Enterprise THIRA")).lastrowid
    return conn, tid, aid


def demonstrated(capability_id, name, area, gap=0):
    return CapabilityMeasure(
        capability_id=capability_id,
        name=name,
        mission_area=area,
        required_standard=10,
        current_performance=10,
        gap_severity=gap,
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


def test_snapshot_is_tenant_scoped_and_contains_five_areas():
    conn, tid, aid = conn_with_core_schema()
    cid = conn.execute("INSERT INTO capabilities(assessment_id,name) VALUES(?,?)", (aid, "Incident Command")).lastrowid
    snapshot_id = save_posture_snapshot(
        conn,
        tenant_id=tid,
        assessment_id=aid,
        protected_member_name="Protected Member A",
        capabilities=[demonstrated(cid, "Incident Command", MissionArea.RESPONSE)],
        created_by="test-user",
        created_at="2026-09-06T18:00:00+00:00",
    )
    saved = get_snapshot(conn, tenant_id=tid, snapshot_id=snapshot_id)
    assert saved is not None
    assert len(saved["mission_areas"]) == 5
    assert get_snapshot(conn, tenant_id=999, snapshot_id=snapshot_id) is None


def test_cross_tenant_assessment_save_is_rejected():
    conn, tid, aid = conn_with_core_schema()
    other_tid = conn.execute("INSERT INTO tenants(name) VALUES('Other')").lastrowid
    cid = conn.execute("INSERT INTO capabilities(assessment_id,name) VALUES(?,?)", (aid, "Recovery")).lastrowid
    try:
        save_posture_snapshot(
            conn,
            tenant_id=other_tid,
            assessment_id=aid,
            protected_member_name="Other",
            capabilities=[demonstrated(cid, "Recovery", MissionArea.RECOVERY)],
            created_by="test-user",
        )
        assert False, "expected tenant isolation failure"
    except ValueError as exc:
        assert "tenant" in str(exc)


def test_snapshots_are_append_only_and_trend_preserves_history():
    conn, tid, aid = conn_with_core_schema()
    cid = conn.execute("INSERT INTO capabilities(assessment_id,name) VALUES(?,?)", (aid, "Continuity")).lastrowid
    first = CapabilityMeasure(
        cid, "Continuity", MissionArea.RECOVERY,
        evidence=CapabilityEvidenceState(plan_current=True),
    )
    save_posture_snapshot(
        conn, tenant_id=tid, assessment_id=aid,
        protected_member_name="Protected Member A", capabilities=[first],
        created_by="test-user", created_at="2026-09-01T00:00:00+00:00",
    )
    save_posture_snapshot(
        conn, tenant_id=tid, assessment_id=aid,
        protected_member_name="Protected Member A",
        capabilities=[demonstrated(cid, "Continuity", MissionArea.RECOVERY)],
        created_by="test-user", created_at="2026-09-06T00:00:00+00:00",
    )
    trend = posture_trend(conn, tenant_id=tid, assessment_id=aid)
    assert len(trend) == 2
    assert trend[0]["overall_score"] < trend[1]["overall_score"]
    latest = latest_snapshot(conn, tenant_id=tid, assessment_id=aid)
    assert latest["created_at"] == "2026-09-06T00:00:00+00:00"


def test_dashboard_payload_is_gauge_ready():
    conn, tid, aid = conn_with_core_schema()
    areas = list(MissionArea)
    capabilities = []
    for idx, area in enumerate(areas, start=1):
        cid = conn.execute("INSERT INTO capabilities(assessment_id,name) VALUES(?,?)", (aid, area.value)).lastrowid
        capabilities.append(demonstrated(cid, area.value, area))
    save_posture_snapshot(
        conn, tenant_id=tid, assessment_id=aid,
        protected_member_name="Protected Member A", capabilities=capabilities,
        created_by="test-user",
    )
    payload = dashboard_payload(conn, tenant_id=tid, assessment_id=aid)
    assert payload["status"] == "Current"
    assert payload["overall"]["band"] == "Demonstrated"
    assert len(payload["mission_areas"]) == 5
    assert {x["mission_area"] for x in payload["mission_areas"]} == {x.value for x in MissionArea}


def test_empty_dashboard_is_unknown_not_false_zero():
    conn, tid, aid = conn_with_core_schema()
    payload = dashboard_payload(conn, tenant_id=tid, assessment_id=aid)
    assert payload["status"] == "Unknown"
    assert payload["overall"]["score"] is None
    assert all(x["band"] == "Unknown" for x in payload["mission_areas"])
