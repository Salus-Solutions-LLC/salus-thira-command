#!/usr/bin/env python3
import importlib.util
import os
import sys
import tempfile
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TMP = tempfile.TemporaryDirectory()
os.environ['SALUS_DB_BACKEND'] = 'sqlite'
os.environ['SALUS_DB_PATH'] = str(Path(TMP.name) / 'v110-smoke.db')
os.environ['SALUS_AUTH_MODE'] = 'prototype'

sys.path.insert(0, str(ROOT))
from starlette.testclient import TestClient
import app
from portable_backup import collect_tenant_records


def main():
    spec = importlib.util.spec_from_file_location('ci_v19', ROOT / 'tools' / 'ci_v19_smoke.py')
    previous = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(previous)
    actual = app.APP_VERSION
    try:
        app.APP_VERSION = '1.9.0'
        previous.main()
    finally:
        app.APP_VERSION = actual

    client = TestClient(app.app)
    h = {'X-Salus-Role': 'Assessment Director', 'X-Salus-User': 'V110 CI', 'X-Salus-Tenant': '1'}
    future = (datetime.now(timezone.utc).date() + timedelta(days=365)).isoformat()
    payload = {
        'name': 'Member Client Continuity Assessment',
        'organization': 'Member Client Alpha',
        'assessment_type': 'Enterprise',
        'purpose': 'Establish a governed operational risk baseline.',
        'mission': 'Protect people and sustain essential operations.',
        'scope': 'Primary operating location and essential dependencies.',
        'exclusions': 'Supplier sites outside the Member Client boundary.',
        'classification': 'Restricted',
        'reassessment_date': future,
    }

    created = client.post('/api/assessments', headers=h, json=payload)
    assert created.status_code == 200, created.text
    assessment = created.json()
    assert assessment['name'] == payload['name']
    assert assessment['organization'] == payload['organization']
    assert assessment['status'] == 'Draft'
    assert assessment['reassessment_lifecycle_status'] == 'Current'
    assert assessment['version'] == 1
    assert assessment['tenant_id'] == 1
    assert assessment['reassessment_date'] == future
    assert assessment['last_reassessment_review_at'] == ''
    assessment_id = assessment['id']

    listed = client.get('/api/assessments', headers=h)
    assert listed.status_code == 200, listed.text
    assert assessment_id in [row['id'] for row in listed.json()]

    protected = {
        'tenant_id': 2,
        'status': 'Scope Approved',
        'reassessment_lifecycle_status': 'Reassessment Overdue',
        'reassessment_overdue_reason': 'forged',
        'last_reassessment_review_by': 'forged reviewer',
        'version': 99,
        'created_at': '2000-01-01T00:00:00Z',
    }
    for key, value in protected.items():
        forged = client.post('/api/assessments', headers=h, json={**payload, key: value})
        assert forged.status_code == 422, (key, forged.text)
    assert client.post('/api/assessments', headers=h, json={**payload, 'name': '   '}).status_code == 422
    assert client.post('/api/assessments', headers=h, json={**payload, 'reassessment_date': 'not-a-date'}).status_code == 422
    assert client.put(f'/api/assessments/{assessment_id}', headers=h, json={'status': 'Scope Approved'}).status_code == 409
    assert client.put(f'/api/assessments/{assessment_id}', headers=h, json={'reassessment_date': '2099-01-01'}).status_code == 409

    conn = app.db()
    audit = conn.execute("SELECT * FROM audit_log WHERE entity_type='assessment' AND entity_id=? ORDER BY id DESC LIMIT 1", (assessment_id,)).fetchone()
    versions = conn.execute("SELECT * FROM entity_versions WHERE entity_type='assessments' AND entity_id=? ORDER BY id", (assessment_id,)).fetchall()
    package = collect_tenant_records(conn, 1)
    conn.close()
    assert audit and audit['action'] == 'CREATE' and audit['user_name'] == 'V110 CI'
    assert len(versions) == 1 and versions[0]['version_no'] == 1
    assert any(row['id'] == assessment_id for row in package['assessments'])
    assert any(row['entity_id'] == assessment_id and row['entity_type'] == 'assessments' for row in package['entity_versions'])

    h2 = {**h, 'X-Salus-Tenant': '2', 'X-Salus-User': 'Tenant Two User'}
    assert client.get('/api/assessments', headers=h2).json() == []
    second = client.post('/api/assessments', headers=h2, json={**payload, 'name': 'Tenant Two Assessment'})
    assert second.status_code == 200, second.text
    assert second.json()['tenant_id'] == 2
    assert assessment_id in [row['id'] for row in client.get('/api/assessments', headers=h).json()]
    assert client.get('/health/ready').json()['version'] == '1.10.0'
    print('V1_10_OPERATIONAL_ASSESSMENT_WORKSPACE_PASS', app.DB_BACKEND)


if __name__ == '__main__':
    main()
