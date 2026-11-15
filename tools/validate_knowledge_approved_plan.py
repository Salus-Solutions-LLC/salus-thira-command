"""Exercise the actual pre-Azure guard and Bicep bootstrap with harmless local fixtures."""
import base64
import copy
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile
import zlib
import yaml
root=Path('.')
workflow=yaml.load((root/'.github/workflows/salcapa-knowledge-approved-recovery-plan.yml').read_text(),Loader=yaml.BaseLoader)
assert 'workflow_dispatch' not in workflow['on']
assert workflow['jobs']['authorize_scoped']['environment']=='salcapa-dev-approval'
for job in workflow['jobs'].values():
    for step in job.get('steps',[]):
        if 'run' in step:subprocess.run(['bash','-n'],input=step['run'],text=True,check=True)
activation_path='deploy/azure/activations/knowledge-approved-recovery-plan-20261115.json'
activation=json.loads((root/activation_path).read_text())
assert activation['preserved_receipt_count']==8 and activation['new_search_receipt_count']==4
assert activation['expected_unresolved_sources']==8430 and activation['maximum_batch_size']==50
assert activation['recovery_ledger_changes_authorized'] is True and activation['recovery_schema_authorized'] is True
assert all(activation[key] is False for key in ('baseline_proposal_records_authorized','baseline_proposal_schema_authorized','source_record_or_schema_changes_authorized','automatic_processing_authorized','new_baseline_adoption_authorized','production_deployment_authorized','protected_member_access'))
guard=next(s['run'] for s in workflow['jobs']['task_search']['steps'] if s.get('name')=='Validate exact task and script')
assert 'az ' not in guard
paths=('tools/live_knowledge_approved_recovery_plan.py','tools/live_knowledge_postsearch_resume.py','tools/live_knowledge_baseline_proposal.py','tools/knowledge_recovery_plan_payload.py',*activation['authority_row_sha256'])
with tempfile.TemporaryDirectory() as folder:
    fixture=Path(folder)
    target=fixture/activation_path;target.parent.mkdir(parents=True)
    for name in paths:
        (fixture/name).parent.mkdir(parents=True,exist_ok=True)
        shutil.copyfile(root/name,fixture/name)
    def check(value,attempt='1'):
        target.write_text(json.dumps(value))
        return subprocess.run(['bash','-euo','pipefail','-c',guard],cwd=fixture,env={**os.environ,'GITHUB_RUN_ATTEMPT':attempt},capture_output=True,text=True).returncode
    assert check(activation)==0
    for key in activation:
        changed=copy.deepcopy(activation);changed[key]='invalid-binding-fixture'
        assert check(changed)!=0,key
    assert check(activation,'2')!=0
    for name in paths:
        path=fixture/name;before=path.read_bytes()
        if name in activation['authority_row_sha256']:
            text=before.decode();needle='| SAL-D137 |' if name.startswith('SALUS_') else activation['approved_baseline_sha256']
            lines=text.splitlines();index=next(i for i,line in enumerate(lines) if line.startswith('|') and needle in line)
            lines[index]+=' altered authority';path.write_text('\n'.join(lines))
        else:path.write_bytes(before+b'\n# altered')
        assert check(activation)!=0,name
        path.write_bytes(before)
    print('Actual pre-Azure guard rejected '+str(len(activation))+' activation-field changes, replay, four source changes and both governing-row changes')
bicep=(root/'infra/azure/knowledge-approved-recovery-plan-job.bicep').read_text()
bootstrap=next(line.strip()[1:-1] for line in bicep.splitlines() if line.strip().startswith("'import base64,zlib,"))
assert len(bootstrap)<4096 and 'replicaRetryLimit: 0' in bicep and "replicaTimeout: 900" in bicep
def invoke(rows,mutate=None,checksum=None):
    raw=json.dumps(rows,sort_keys=True,separators=(',',':')).encode()
    encoded=base64.b64encode(zlib.compress(raw,9)).decode()
    if mutate:encoded=mutate(encoded)
    code=bootstrap.replace('${scriptsBase64}',encoded).replace('${payloadSha256}',checksum or hashlib.sha256(raw).hexdigest())
    return subprocess.run([sys.executable,'-c',code],capture_output=True,text=True)
rows=[]
for name in ('salus_postsearch_support','salus_baseline_support','__main__'):
    source=(('import salus_postsearch_support\n' if name=='salus_baseline_support' else '')+('import salus_baseline_support\nprint("SAFE_BOOTSTRAP_OK")\n' if name=='__main__' else 'VALUE=1\n')).encode()
    rows.append({'name':name,'sha256':hashlib.sha256(source).hexdigest(),'source':base64.b64encode(source).decode()})
result=invoke(rows);assert result.returncode==0 and 'SAFE_BOOTSTRAP_OK' in result.stdout,result.stderr
assert invoke(list(reversed(rows))).returncode!=0
assert invoke(rows,checksum='0'*64).returncode!=0
changed=copy.deepcopy(rows);changed[0]['sha256']='0'*64
assert invoke(changed).returncode!=0
changed=copy.deepcopy(rows);changed[0]['source']=base64.b64encode(b'x'*262145).decode()
assert invoke(changed).returncode!=0
assert invoke(rows,mutate=lambda value:'!'+value).returncode!=0
print('Actual Bicep bootstrap accepted three pinned modules and rejected order, digest, source-hash, size and encoding drift')
