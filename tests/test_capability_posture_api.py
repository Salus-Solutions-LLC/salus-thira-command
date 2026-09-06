import sqlite3

from fastapi import FastAPI
from fastapi.testclient import TestClient

from capability_posture_api import register_routes


def make_conn():
    conn=sqlite3.connect(":memory:", check_same_thread=False)
    conn.row_factory=sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    conn.executescript("""
    CREATE TABLE tenants(id INTEGER PRIMARY KEY AUTOINCREMENT,name TEXT);
    CREATE TABLE assessments(id INTEGER PRIMARY KEY AUTOINCREMENT,tenant_id INTEGER NOT NULL,name TEXT,organization TEXT,
      FOREIGN KEY(tenant_id) REFERENCES tenants(id));
    CREATE TABLE capabilities(id INTEGER PRIMARY KEY AUTOINCREMENT,assessment_id INTEGER NOT NULL,name TEXT,mission_area TEXT,
      required_standard REAL,current_performance REAL,comparator TEXT,
      FOREIGN KEY(assessment_id) REFERENCES assessments(id));
    CREATE TABLE gaps(id INTEGER PRIMARY KEY AUTOINCREMENT,assessment_id INTEGER,capability_id INTEGER,severity TEXT,status TEXT);
    CREATE TABLE evidence(id INTEGER PRIMARY KEY AUTOINCREMENT,assessment_id INTEGER,capability_id INTEGER,evidence_type TEXT,
      verification_status TEXT,lifecycle_status TEXT);
    """)
    tid=conn.execute("INSERT INTO tenants(name) VALUES('Member')").lastrowid
    aid=conn.execute("INSERT INTO assessments(tenant_id,name,organization) VALUES(?,?,?)",(tid,'Assessment','Protected Member')).lastrowid
    cid=conn.execute("INSERT INTO capabilities(assessment_id,name,mission_area,required_standard,current_performance,comparator) VALUES(?,?,?,?,?,?)",(aid,'Incident Command','Response',10,10,'>=')).lastrowid
    conn.execute("INSERT INTO evidence(assessment_id,capability_id,evidence_type,verification_status,lifecycle_status) VALUES(?,?,?,?,?)",(aid,cid,'Exercise Result','Verified','Current'))
    conn.commit()
    return conn,tid,aid


def test_refresh_requires_write_authorization_and_read_returns_gauge():
    conn,tid,aid=make_conn()
    app=FastAPI()
    calls=[]
    def authorize(request, assessment_id, write=False):
        calls.append(write)
        return {'tenant_id':tid,'user_name':'tester'}
    register_routes(app,authorize,connection_factory=lambda: conn)
    client=TestClient(app)
    refresh=client.post(f'/api/capability-posture/{aid}/refresh')
    assert refresh.status_code==200
    assert refresh.json()['refreshed'] is True
    read=client.get(f'/api/capability-posture/{aid}')
    assert read.status_code==200
    assert len(read.json()['mission_areas'])==5
    assert True in calls and False in calls


def test_denied_authorization_never_returns_member_posture():
    conn,tid,aid=make_conn()
    app=FastAPI()
    def deny(request, assessment_id, write=False):
        return {}
    register_routes(app,deny,connection_factory=lambda: conn)
    client=TestClient(app)
    assert client.get(f'/api/capability-posture/{aid}').status_code==403
    assert client.post(f'/api/capability-posture/{aid}/refresh').status_code==403
