#!/usr/bin/env python3
import importlib.util
import os
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TMP = tempfile.TemporaryDirectory()
os.environ['SALUS_DB_BACKEND'] = 'sqlite'
os.environ['SALUS_DB_PATH'] = str(Path(TMP.name) / 'v111-smoke.db')
os.environ['SALUS_AUTH_MODE'] = 'prototype'

sys.path.insert(0, str(ROOT))
from starlette.testclient import TestClient
import app
from portable_backup import collect_tenant_records


def main():
    spec = importlib.util.spec_from_file_location('ci_v110', ROOT / 'tools' / 'ci_v110_smoke.py')
    previous = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(previous)
    actual = app.APP_VERSION
    try:
        app.APP_VERSION = '1.10.0'
        previous.main()
    finally:
        app.APP_VERSION = actual

    client = TestClient(app.app)
    h = {'X-Salus-Role': 'Assessment Director', 'X-Salus-User': 'V111 CI', 'X-Salus-Tenant': '1'}
    assessment = client.post('/api/assessments', headers=h, json={
        'name': 'V111 Threat and Scenario Assessment',
        'organization': 'Member Client Alpha',
        'purpose': 'Govern scenario-based operational analysis.',
    })
    assert assessment.status_code == 200, assessment.text
    assessment_id = assessment.json()['id']

    threat_payload = {
        'assessment_id': assessment_id,
        'name': 'Extended utility interruption',
        'category': 'Utility',
        'subcategory': 'Electric service',
        'description': 'Regional electric service is unavailable beyond onsite generation endurance.',
        'likelihood': 3,
        'vulnerability': 4,
        'consequence': 5,
        'confidence': 'High',
        'trend': 'Increasing',
        'inclusion_status': 'Included - Scenario Required',
        'basis': 'Member Client operating history and current dependency review.',
    }
    threat_response = client.post('/api/threats', headers=h, json=threat_payload)
    assert threat_response.status_code == 200, threat_response.text
    threat = threat_response.json()
    assert threat['status'] == 'Active'
    assert threat['assessment_id'] == assessment_id
    threat_id = threat['id']

    for key, value in {'status': 'Closed', 'tenant_id': 2, 'version': 99, 'created_at': '2000-01-01T00:00:00Z'}.items():
        forged = client.post('/api/threats', headers=h, json={**threat_payload, key: value})
        assert forged.status_code == 422, (key, forged.text)
    assert client.post('/api/threats', headers=h, json={**threat_payload, 'likelihood': 6}).status_code == 422
    assert client.post('/api/threats', headers=h, json={**threat_payload, 'name': '   '}).status_code == 422

    scenario_payload = {
        'assessment_id': assessment_id,
        'threat_id': threat_id,
        'title': 'Seven-day grid outage during extreme heat',
        'narrative': 'A regional outage isolates the facility while temperature and demand remain elevated.',
        'initiating_event': 'Transmission failure during peak demand',
        'location': 'Primary operating location',
        'duration': 'Seven days',
        'operating_conditions': 'Extreme heat, constrained fuel delivery, and degraded communications.',
        'dependencies': 'Electricity, fuel, telecommunications, water, and critical suppliers.',
        'decision_points': 'Relocate operations, prioritize generator loads, and request mutual aid.',
        'assumptions': 'Backup generation starts and fuel is initially available.',
        'uncertainties': 'Restoration sequence and resupply access.',
        'life_safety': 5,
        'mission': 5,
        'operations': 5,
        'financial': 4,
        'legal_regulatory': 3,
        'reputation': 4,
        'recovery': 5,
        'evidence_confidence': 'High',
    }
    scenario_response = client.post('/api/scenarios', headers=h, json=scenario_payload)
    assert scenario_response.status_code == 200, scenario_response.text
    scenario = scenario_response.json()
    assert scenario['assessment_id'] == assessment_id and scenario['threat_id'] == threat_id
    assert scenario['title'] == scenario_payload['title']
    scenario_id = scenario['id']

    for key, value in {'professional_override': 'Critical', 'override_reason': 'forged', 'version': 8, 'created_at': '2000-01-01T00:00:00Z'}.items():
        forged = client.post('/api/scenarios', headers=h, json={**scenario_payload, key: value})
        assert forged.status_code == 422, (key, forged.text)
    assert client.post('/api/scenarios', headers=h, json={**scenario_payload, 'life_safety': 0}).status_code == 422
    assert client.post('/api/scenarios', headers=h, json={**scenario_payload, 'narrative': '   '}).status_code == 422

    tenant_two = {**h, 'X-Salus-Tenant': '2', 'X-Salus-User': 'Tenant Two User'}
    cross_tenant = client.post('/api/scenarios', headers=tenant_two, json=scenario_payload)
    assert cross_tenant.status_code in (403, 404), cross_tenant.text

    other_assessment = client.post('/api/assessments', headers=h, json={'name': 'Other Assessment', 'organization': 'Member Client Alpha'}).json()['id']
    cross_assessment = client.post('/api/scenarios', headers=h, json={**scenario_payload, 'assessment_id': other_assessment})
    assert cross_assessment.status_code == 422, cross_assessment.text

    listed_threats = client.get(f'/api/threats?assessment_id={assessment_id}', headers=h).json()
    listed_scenarios = client.get(f'/api/scenarios?assessment_id={assessment_id}', headers=h).json()
    assert [row['id'] for row in listed_threats] == [threat_id]
    assert [row['id'] for row in listed_scenarios] == [scenario_id]

    conn = app.db()
    audit_rows = conn.execute("SELECT entity_type,entity_id,action FROM audit_log WHERE entity_id IN (?,?) ORDER BY id", (threat_id, scenario_id)).fetchall()
    versions = conn.execute("SELECT entity_type,entity_id,version_no FROM entity_versions WHERE entity_id IN (?,?) ORDER BY id", (threat_id, scenario_id)).fetchall()
    package = collect_tenant_records(conn, 1)
    conn.close()
    assert any(row['entity_type'] == 'threat' and row['entity_id'] == threat_id and row['action'] == 'CREATE' for row in audit_rows)
    assert any(row['entity_type'] == 'scenario' and row['entity_id'] == scenario_id and row['action'] == 'CREATE' for row in audit_rows)
    assert any(row['entity_type'] == 'threats' and row['entity_id'] == threat_id and row['version_no'] == 1 for row in versions)
    assert any(row['entity_type'] == 'scenarios' and row['entity_id'] == scenario_id and row['version_no'] == 1 for row in versions)
    assert any(row['id'] == threat_id for row in package['threats'])
    assert any(row['id'] == scenario_id for row in package['scenarios'])
    assert client.get('/health/ready').json()['version'] == '1.11.0'
    print('V1_11_OPERATIONAL_THREAT_SCENARIO_WORKSPACE_PASS', app.DB_BACKEND)


if __name__ == '__main__':
    main()
