"""Exercise the actual activation guard and five-module bootstrap before Azure access."""
import base64
import copy
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import zlib
import yaml
root=Path('.')
workflow=yaml.load((root/'.github/workflows/salcapa-knowledge-preflight-blockers.yml').read_text(),Loader=yaml.BaseLoader)
assert 'workflow_dispatch' not in workflow['on']
assert workflow['jobs']['authorize_scoped']['environment']=='salcapa-dev-approval'
assert workflow['concurrency']['cancel-in-progress']=='false'
for job in workflow['jobs'].values():
    for step in job.get('steps',[]):
        if 'run' in step:subprocess.run(['bash','-n'],input=step['run'],text=True,check=True)
activation_path='deploy/azure/activations/knowledge-preflight-blockers-20261116.json'
activation=json.loads((root/activation_path).read_text())
assert activation['preserved_receipt_count']==20 and activation['new_search_receipt_count']==activation['query_count']==4
assert activation['expected_parent_batches']==200 and activation['expected_parent_sources']==8430
assert activation['execution_memory']=='1Gi' and activation['maximum_observed_peak_rss_kib']==786432
assert activation['transaction_budget_seconds']==60 and activation['maximum_parent_batch_sources']==50
assert activation['eligibility_diagnostic_schema_authorized'] is True and activation['diagnostic_and_resolution_proposals_authorized'] is True
assert all(activation[k] is False for k in ('method_adoption_authorized','existing_eligibility_policy_changed','review_input_writes_authorized','preflight_execution_authorized','remediation_input_writes_authorized','parent_plan_writes_authorized','baseline_writes_authorized','source_record_or_schema_changes_authorized','automatic_processing_authorized','retry_resume_authorized','hold_release_authorized','source_content_downloads_authorized','protected_member_access','assignment_or_release_authority','production_deployment_authorized'))
guard=next(s['run'] for s in workflow['jobs']['task_search']['steps'] if s.get('name')=='Validate exact task and script')
assert 'az ' not in guard
with tempfile.TemporaryDirectory() as folder:
    fixture=Path(folder);target=fixture/activation_path;target.parent.mkdir(parents=True)
    paths=list(activation['source_sha256'])+list(dict.fromkeys(b['path'] for b in activation['authority_rows']))
    for name in paths:
        (fixture/name).parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(root/name,fixture/name)
    def check(value,attempt='1'):
        target.write_text(json.dumps(value))
        return subprocess.run(['bash','-euo','pipefail','-c',guard],cwd=fixture,env={**os.environ,'GITHUB_RUN_ATTEMPT':attempt},capture_output=True,text=True).returncode
    assert check(activation)==0
    for key in activation:
        changed=copy.deepcopy(activation);changed[key]='invalid-binding-fixture'
        assert check(changed)!=0,key
    assert check(activation,'2')!=0
    for name in activation['source_sha256']:
        path=fixture/name;before=path.read_bytes();path.write_bytes(before+b'\n# altered')
        assert check(activation)!=0,name
        path.write_bytes(before)
    for binding in activation['authority_rows']:
        path=fixture/binding['path'];before=path.read_text();lines=before.splitlines()
        index=next(i for i,line in enumerate(lines) if line.startswith('|') and binding['needle'] in line)
        lines[index]+=' altered authority';path.write_text('\n'.join(lines))
        assert check(activation)!=0,binding['needle']
        path.write_text(before)
    print('Actual pre-Azure guard rejected '+str(len(activation))+' changed activation fields, replay, eight altered sources and five altered governing rows')
bicep=(root/'infra/azure/knowledge-preflight-blockers-job.bicep').read_text()
bootstrap=next(line.strip()[1:-1] for line in bicep.splitlines() if line.strip().startswith("'import base64,zlib,"))
assert len(bootstrap)<4096 and 'replicaRetryLimit: 0' in bicep and 'replicaTimeout: 900' in bicep
names=['salus_postsearch_support','salus_baseline_support','salus_streamed_plan_support','salus_remediation_support','__main__']
def invoke(rows,checksum=None,mutate=None):
    raw=json.dumps(rows,sort_keys=True,separators=(',',':')).encode();encoded=base64.b64encode(zlib.compress(raw,9)).decode()
    if mutate:encoded=mutate(encoded)
    code=bootstrap.replace('${scriptsBase64}',encoded).replace('${payloadSha256}',checksum or hashlib.sha256(raw).hexdigest())
    return subprocess.run([sys.executable,'-c',code],capture_output=True,text=True)
rows=[]
for index,name in enumerate(names):
    source=(('import '+names[index-1]+'\n' if index else '')+('print("SAFE_BOOTSTRAP_OK")\n' if name=='__main__' else 'VALUE=1\n')).encode()
    rows.append({'name':name,'sha256':hashlib.sha256(source).hexdigest(),'source':base64.b64encode(source).decode()})
result=invoke(rows);assert result.returncode==0 and 'SAFE_BOOTSTRAP_OK' in result.stdout,result.stderr
assert invoke(list(reversed(rows))).returncode!=0
assert invoke(rows,checksum='0'*64).returncode!=0
changed=copy.deepcopy(rows);changed[0]['sha256']='0'*64;assert invoke(changed).returncode!=0
changed=copy.deepcopy(rows);changed[0]['source']=base64.b64encode(b'x'*262145).decode();assert invoke(changed).returncode!=0
assert invoke(rows,mutate=lambda value:'!'+value).returncode!=0
print('Actual five-module Bicep bootstrap accepted pinned order and rejected order, digest, source hash, size and encoding drift')
