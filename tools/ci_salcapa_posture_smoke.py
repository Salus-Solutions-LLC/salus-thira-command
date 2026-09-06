#!/usr/bin/env python3
"""Release-gate smoke for SalCAPA pricing, P/T/E and capability posture domains."""
import os
import sqlite3
import tempfile

from capability_posture import CapabilityBand, MissionArea
from capability_posture_source import build_capability_measures
from capability_posture_store import dashboard_payload, save_posture_snapshot
from pricing_engine import CostProfile, DEFAULT_MEMBERSHIP_PLANS
from pte_engine import PTEKind, PTEStatus, ReadinessCycle, next_readiness_action


def main():
    loaded=CostProfile(130000,40000,15000,35000,1300)
    assert str(loaded.productive_hour_cost)=='169.23'
    assert str(DEFAULT_MEMBERSHIP_PLANS['Protected Member'].monthly_price)=='6000'

    cycle=ReadinessCycle(False,False,False,False,False,False)
    assert next_readiness_action(cycle)==PTEKind.PLANNING

    fd,path=tempfile.mkstemp(suffix='.db'); os.close(fd)
    try:
        conn=sqlite3.connect(path); conn.row_factory=sqlite3.Row; conn.execute('PRAGMA foreign_keys = ON')
        conn.executescript('''
        CREATE TABLE tenants(id INTEGER PRIMARY KEY AUTOINCREMENT,name TEXT);
        CREATE TABLE assessments(id INTEGER PRIMARY KEY AUTOINCREMENT,tenant_id INTEGER NOT NULL,name TEXT,organization TEXT,
          FOREIGN KEY(tenant_id) REFERENCES tenants(id));
        CREATE TABLE capabilities(id INTEGER PRIMARY KEY AUTOINCREMENT,assessment_id INTEGER NOT NULL,name TEXT,mission_area TEXT,
          required_standard REAL,current_performance REAL,comparator TEXT,
          FOREIGN KEY(assessment_id) REFERENCES assessments(id));
        CREATE TABLE gaps(id INTEGER PRIMARY KEY AUTOINCREMENT,assessment_id INTEGER,capability_id INTEGER,severity TEXT,status TEXT);
        CREATE TABLE evidence(id INTEGER PRIMARY KEY AUTOINCREMENT,assessment_id INTEGER,capability_id INTEGER,evidence_type TEXT,
          verification_status TEXT,lifecycle_status TEXT);
        ''')
        tid=conn.execute("INSERT INTO tenants(name) VALUES('CI Member')").lastrowid
        aid=conn.execute("INSERT INTO assessments(tenant_id,name,organization) VALUES(?,?,?)",(tid,'CI Assessment','CI Protected Member')).lastrowid
        evidence_by_area={
            'Prevention':['Approved Plan / Procedure','Training Completion','Exercise Result','After Action Report','Corrective Action Validation'],
            'Protection':['Approved Plan / Procedure','Training Completion','Exercise Result','After Action Report','Corrective Action Validation'],
            'Response':['Approved Plan / Procedure','Training Completion','Exercise Result','After Action Report','Corrective Action Validation'],
            'Recovery':['Approved Plan / Procedure','Training Completion','Exercise Result','After Action Report','Corrective Action Validation'],
            'Mitigation':['Approved Plan / Procedure','Training Completion','Exercise Result','After Action Report','Corrective Action Validation'],
        }
        for area in MissionArea:
            cid=conn.execute("INSERT INTO capabilities(assessment_id,name,mission_area,required_standard,current_performance,comparator) VALUES(?,?,?,?,?,?)",(aid,area.value,area.value,10,10,'>=')).lastrowid
            for etype in evidence_by_area[area.value]:
                conn.execute("INSERT INTO evidence(assessment_id,capability_id,evidence_type,verification_status,lifecycle_status) VALUES(?,?,?,?,?)",(aid,cid,etype,'Verified','Current'))
        conn.commit()
        measures=build_capability_measures(conn,aid)
        assert len(measures)==5
        sid=save_posture_snapshot(conn,tenant_id=tid,assessment_id=aid,protected_member_name='CI Protected Member',capabilities=measures,created_by='ci')
        assert sid>0
        payload=dashboard_payload(conn,tenant_id=tid,assessment_id=aid)
        assert len(payload['mission_areas'])==5
        assert payload['overall']['band']==CapabilityBand.DEMONSTRATED.value
        conn.close()
    finally:
        if os.path.exists(path): os.remove(path)
    print('SALCAPA_PRICING_PTE_POSTURE_PASS')


if __name__=='__main__':
    main()
