import sqlite3
from decimal import Decimal

from capability_posture import MissionArea
from capability_posture_source import build_capability_measures


def db():
    conn=sqlite3.connect(":memory:")
    conn.row_factory=sqlite3.Row
    conn.executescript("""
    CREATE TABLE capabilities(
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      assessment_id INTEGER NOT NULL,
      name TEXT NOT NULL,
      mission_area TEXT NOT NULL,
      required_standard REAL,
      current_performance REAL,
      comparator TEXT
    );
    CREATE TABLE gaps(
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      assessment_id INTEGER NOT NULL,
      capability_id INTEGER NOT NULL,
      severity TEXT,
      status TEXT
    );
    CREATE TABLE evidence(
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      assessment_id INTEGER NOT NULL,
      capability_id INTEGER,
      evidence_type TEXT,
      verification_status TEXT,
      lifecycle_status TEXT
    );
    """)
    return conn


def test_source_adapter_uses_existing_mission_area_and_performance_direction():
    conn=db()
    cid=conn.execute("INSERT INTO capabilities(assessment_id,name,mission_area,required_standard,current_performance,comparator) VALUES(1,'Mobilization','Response',10,8,'<=')").lastrowid
    conn.execute("INSERT INTO evidence(assessment_id,capability_id,evidence_type,verification_status,lifecycle_status) VALUES(1,?,'Exercise Result','Verified','Current')",(cid,))
    measures=build_capability_measures(conn,1)
    assert len(measures)==1
    m=measures[0]
    assert m.mission_area==MissionArea.RESPONSE
    assert m.higher_is_better is False
    assert m.evidence.performance_target_met is True
    assert m.evidence.exercise_or_real_event_tested is True
    assert m.evidence.evidence_verified is True


def test_open_material_gap_reduces_measure():
    conn=db()
    cid=conn.execute("INSERT INTO capabilities(assessment_id,name,mission_area,required_standard,current_performance,comparator) VALUES(1,'Continuity','Recovery',100,100,'>=')").lastrowid
    conn.execute("INSERT INTO gaps(assessment_id,capability_id,severity,status) VALUES(1,?,'Critical','Open')",(cid,))
    measure=build_capability_measures(conn,1)[0]
    assert measure.gap_severity==Decimal('100')
    assert measure.demonstrated_score() < Decimal('50')


def test_closed_gap_does_not_penalize_current_posture():
    conn=db()
    cid=conn.execute("INSERT INTO capabilities(assessment_id,name,mission_area,required_standard,current_performance,comparator) VALUES(1,'Protection','Protection',1,1,'=')").lastrowid
    conn.execute("INSERT INTO gaps(assessment_id,capability_id,severity,status) VALUES(1,?,'Critical','Closed')",(cid,))
    measure=build_capability_measures(conn,1)[0]
    assert measure.gap_severity==Decimal('0')


def test_stale_only_evidence_fails_current_evidence_gate():
    conn=db()
    cid=conn.execute("INSERT INTO capabilities(assessment_id,name,mission_area,required_standard,current_performance,comparator) VALUES(1,'Warning','Prevention',10,10,'>=')").lastrowid
    conn.execute("INSERT INTO evidence(assessment_id,capability_id,evidence_type,verification_status,lifecycle_status) VALUES(1,?,'Exercise Result','Verified','Stale')",(cid,))
    measure=build_capability_measures(conn,1)[0]
    assert measure.evidence.evidence_stale is True
    assert measure.evidence.validation_evidence_current is False
    assert measure.evidence.evidence_gate_passed() is False
