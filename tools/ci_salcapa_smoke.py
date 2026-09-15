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

repository_root = Path(__file__).resolve().parents[1]
navigation_html = (repository_root / 'static' / 'index.html').read_text(encoding='utf-8')
navigation_js = (repository_root / 'static' / 'app.js').read_text(encoding='utf-8')
assert '<div class="nav-primary" aria-label="Start here">' in navigation_html
assert navigation_html.index('data-view="dashboard"') < navigation_html.index('<details class="nav-work-areas">')
assert navigation_html.index('data-view="common_operating_picture"') < navigation_html.index('<details class="nav-work-areas">')
assert '<summary><span>More work areas</span>' in navigation_html
assert navigation_html.index('data-view="reports"') > navigation_html.index('<details class="nav-work-areas">')
assert "closest('details.nav-work-areas')" in navigation_js
assert 'workAreaDisclosure.open=true' in navigation_js
assert 'Prepare a report for authorized review' in navigation_js
assert '<h2>Needs Your Attention</h2>' in navigation_js
assert '<h2>Current Work</h2>' in navigation_js
assert '<summary>Preview and export</summary>' in navigation_js
assert '<summary>Supporting assessment detail</summary>' in navigation_js
assert 'Preview and export do not approve or release a governed report version.' in navigation_js
assert 'Review and route incoming information.' in navigation_js
assert 'Unverified intake remains separate from qualified intelligence.' in navigation_js
assert '<h2>Current Work</h2>' in navigation_js
assert '<summary>Collect a new finding</summary>' in navigation_js
assert '<summary>Closed observation history</summary>' in navigation_js
assert 'Routing does not make a human decision or establish operational authority.' in navigation_js
assert '<h2>Observation triage</h2>' not in navigation_js
assert 'Estimate decisions awaiting your authorized review' in navigation_js
assert '<summary>Available services</summary>' in navigation_js
assert '<summary>People, financials, statements, and field updates</summary>' in navigation_js
assert 'Nothing on this page creates an invoice or operational authority by itself.' in navigation_js
assert 'const attentionEstimateRows=estimateRows.filter' in navigation_js
assert 'SalTHIRA™ · Identify risk and establish priorities' in navigation_js
assert 'Risk assessment workspaces' in navigation_js
assert 'Start a new risk assessment' in navigation_js
assert 'Reassessment records shown only when their lifecycle is due, overdue, or stale' in navigation_js
assert 'Authorized people retain assessment, decision, approval, and operational authority.' in navigation_js
assert 'Open observation records and acknowledgement status' in navigation_js
assert '<summary>Qualified intelligence</summary>' in navigation_js
assert 'Qualified information released for your organization' in navigation_js
assert 'memberClosedObservations.map' in navigation_js
assert 'A submission does not establish a finding, decision, or operational action.' in navigation_js
assert "if(key==='assessments')" in navigation_js

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
authorized = client.post(f'/api/salops/requests/{operation_id}/decision', headers=member, json={
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
