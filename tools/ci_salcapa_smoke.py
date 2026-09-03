import os
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
workspace = tempfile.TemporaryDirectory()
os.environ['SALUS_DB_PATH'] = os.path.join(workspace.name, 'salcapa.db')
os.environ['SALUS_BACKUP_DIR'] = os.path.join(workspace.name, 'backups')
os.environ['SALUS_SEED_DEMO'] = '1'

from fastapi.testclient import TestClient
import app

client = TestClient(app.app)
salus = {'X-Salus-Role': 'Assessment Director', 'X-Salus-User': 'Salus Tester', 'X-Salus-Tenant': '1'}
member = {'X-Salus-Role': 'Client Executive', 'X-Salus-User': 'Protected Member', 'X-Salus-Tenant': '1'}

member_workspace = client.get('/api/salcapa/workspace', headers=member).json()
assert member_workspace['platform'] == 'SalCAPA'
assert member_workspace['experience'] == 'Protected Member'
assert member_workspace['component_authority'] == {'SalINTEL': False, 'SalTHIRA': False, 'SalOPS': False}

salus_workspace = client.get('/api/salcapa/workspace', headers=salus).json()
assert salus_workspace['experience'] == 'Salus Personnel'
assert set(('SalINTEL', 'SalTHIRA', 'SalOPS')).issubset(salus_workspace['workspaces'])

forged = client.post('/api/salintel/findings', headers=salus, json={
    'assessment_id': 1, 'title': 'Finding', 'source': 'Source', 'status': 'Qualified'
})
assert forged.status_code == 422

finding = client.post('/api/salintel/findings', headers=salus, json={
    'assessment_id': 1, 'title': 'Regional severe weather',
    'details': 'Travel routes may be disrupted.', 'source': 'Qualified weather monitoring',
    'source_locator': 'source://weather/1',
})
assert finding.status_code == 200, finding.text
finding_id = finding.json()['id']
assert client.get('/api/salintel/findings', headers=member).json() == []

qualified = client.post(f'/api/salintel/findings/{finding_id}/qualify', headers=salus, json={
    'relevance': 'Relevant', 'credibility': 'High', 'validation_status': 'Qualified',
    'operational_significance': 'Executive travel and continuity plans require review.',
})
assert qualified.status_code == 200 and qualified.json()['status'] == 'Qualified'
member_intel = client.get('/api/salintel/findings', headers=member).json()[0]
assert 'source_locator' not in member_intel and 'details' not in member_intel

handoff = client.post(f'/api/salintel/findings/{finding_id}/send-to-salthira', headers=salus)
assert handoff.status_code == 200
assert client.post(f'/api/salintel/findings/{finding_id}/send-to-salthira', headers=salus).status_code == 409

operation = client.post('/api/salops/requests', headers=salus, json={
    'assessment_id': 1, 'title': 'Validate communications roster',
    'description': 'Confirm primary and alternate contacts.', 'priority': 'Priority',
})
assert operation.status_code == 200
operation_id = operation.json()['id']
authorized = client.post(f'/api/salops/requests/{operation_id}/decision', headers=salus, json={
    'decision': 'Authorized', 'reason': 'Required by current risk posture', 'assigned_to': 'Operations Lead',
})
assert authorized.status_code == 200 and authorized.json()['status'] == 'Authorized'
completed = client.post(f'/api/salops/requests/{operation_id}/complete', headers=salus, json={
    'result_summary': 'Roster validated and alternate contacts tested.',
})
assert completed.status_code == 200 and completed.json()['reassessment_trigger_id']

cop = client.get('/api/salcapa/common-operating-picture', headers=member)
assert cop.status_code == 200
assert cop.json()['metrics']['qualified_intelligence'] == 1
assert cop.json()['metrics']['priority_actions'] >= 2

cross_tenant = client.get('/api/salintel/findings', headers={**member, 'X-Salus-Tenant': '2'})
assert cross_tenant.status_code == 200 and cross_tenant.json() == []

print('SalCAPA platform, SalINTEL, SalTHIRA, and SalOPS governed-handoff smoke passed')
