import os
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

workspace = tempfile.TemporaryDirectory()
os.environ['SALUS_DB_PATH'] = os.path.join(workspace.name, 'v117.db')
os.environ['SALUS_BACKUP_DIR'] = os.path.join(workspace.name, 'backups')
os.environ['SALUS_SEED_DEMO'] = '1'

from fastapi.testclient import TestClient
import app

client = TestClient(app.app)
director = {'X-Salus-Role': 'Assessment Director', 'X-Salus-User': 'v1.17 tester', 'X-Salus-Tenant': '1'}
admin = {**director, 'X-Salus-Role': 'System Administrator'}

created = client.post('/api/reports/1', headers=director)
assert created.status_code == 200, created.text
report = created.json()
digest = report['snapshot_sha256']
for current, target in [('Draft', 'Reviewed'), ('Reviewed', 'Approved'), ('Approved', 'Released')]:
    advanced = client.post(
        f"/api/reports/versions/{report['id']}/transition",
        headers=director,
        json={'status': target, 'reason': f'Controlled {target.lower()} gate'},
    )
    assert advanced.status_code == 200, advanced.text
    assert advanced.json()['status'] == target

snapshot = client.get(f"/api/reports/versions/{report['id']}/snapshot", headers=director)
assert snapshot.status_code == 200
assert snapshot.headers['etag'] == f'"{digest}"'
assert snapshot.json()['assessment']['id'] == 1

invalid_transition = client.post(
    f"/api/reports/versions/{report['id']}/transition",
    headers=director,
    json={'status': 'Reviewed', 'reason': 'Attempt to rewrite released authority'},
)
assert invalid_transition.status_code == 409

tenant_boundary = client.get(f"/api/reports/versions/{report['id']}/snapshot", headers={**director, 'X-Salus-Tenant': '2'})
assert tenant_boundary.status_code == 404

history = client.get('/api/audit/assessments/1', headers=director)
assert history.status_code == 200
assert any(row['entity_type'] == 'report_version' for row in history.json()['audit'])

backup = client.post('/api/admin/backups', headers=admin)
assert backup.status_code == 200, backup.text
backup_id = backup.json()['id']
assert client.post(f'/api/admin/backups/{backup_id}/verify', headers=admin).json()['ok']
readiness = client.post(f'/api/admin/backups/{backup_id}/dr-validate', headers=admin)
assert readiness.status_code == 200 and readiness.json()['ok']

request = client.post(
    '/api/admin/restore-requests', headers=admin,
    json={'backup_id': backup_id, 'scope': 'Tenant 1 authoritative records', 'reason': 'Recovery control validation'},
)
assert request.status_code == 200, request.text
request_id = request.json()['id']
decision = client.post(
    f'/api/admin/restore-requests/{request_id}/decision', headers=admin,
    json={'decision': 'Authorized', 'reason': 'Scope and integrity independently reviewed'},
)
assert decision.status_code == 200 and decision.json()['status'] == 'Authorized'

blocked = client.post(f'/api/admin/backups/{backup_id}/restore?restore_request_id={request_id}', headers=admin)
assert blocked.status_code == 403  # Real restore remains disabled outside an authorized maintenance window.

print('v1.17 reports, audit, backup, and recovery governance smoke passed')
