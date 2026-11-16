"""Validate bounded read-only telemetry and the actual pre-Azure guard/bootstrap."""
import hashlib,json,re,sys
from pathlib import Path

def verify_inventory_log(text):
 values={};deltas=[]
 for line in text.splitlines():
  m=re.search(r' stdout F ([A-Z][A-Z0-9_]+)=(.*)$',line)
  if not m:continue
  key,value=m.groups()
  if key=='OUTSIDE_COHORT_SOURCE':continue
  if key=='INVENTORY_RECON_SOURCE_DELTA':deltas.append(json.loads(value))
  else:
   assert key not in values or key in ('INVENTORY_RECON_PHASE','INVENTORY_RECON_PEAK_RSS_KIB'),key
   values[key]=value
 required={'COMPLETE':1,'FRESH_CONNECTION_VERIFIED':1,'PRESERVED_RECEIPTS':20,'SAVED_TARGET_ROWS':0,'APPROVED_UNRESOLVED_SOURCES':8430,'DATABASE_WRITES':0,'NEW_RECEIPTS':0,'NEW_BASELINE_ADOPTED':0,'PROPOSAL_PREPARATION':0,'SOURCE_CONTENT_DOWNLOADS':0,'PREFLIGHT_EXECUTION':0,'PROCESSING_AUTHORIZED':0,'RETRY_RESUME':0,'HOLD_RELEASE':0,'ALL_REPRESENTED_CONSIDERED':1}
 for key,value in required.items():assert values.get('INVENTORY_RECON_'+key)==str(value),key
 assert 'INVENTORY_RECON_FAILURE_CODE' not in values
 checksum=values['INVENTORY_RECON_INVENTORY_SHA256'];assert re.fullmatch('[a-f0-9]{64}',checksum)
 assert int(values['INVENTORY_RECON_PHYSICAL_FILES'])>=23747
 assert values['INVENTORY_RECON_BASELINE_INVENTORY_SHA256']=='0e556598be30292cc1bbb2e46bb964b2e6e6f5e38f0b3b5e93b48a7cc68bc613'
 assert values['INVENTORY_RECON_HISTORICAL_FAILED_FINAL_RECONSTRUCTED_BY_HASH']==str(int(checksum=='efd10c4ed8793e808d79076f57074afedc549d315985fe6f4dea98f1196e3621'))
 samples=sorted(int(m[1]) for k in values if (m:=re.fullmatch('STABILITY_SAMPLE_([1-4])_COMPLETE',k)))
 assert samples in ([1,2,3],[1,2,3,4])
 for i in samples[-3:]:assert values['STABILITY_SAMPLE_'+str(i)+'_SHA256']==checksum and values['STABILITY_SAMPLE_'+str(i)+'_FILES']==values['INVENTORY_RECON_PHYSICAL_FILES']
 assert values.get('STABILITY_CONSECUTIVE_COMPLETE_INVENTORIES_EQUAL')=='1'
 for key in ('ADDED','REMOVED','CHANGED','ETAG','SIZE','PARENT_OR_AREA','NAME','RELATIVE_PATH','MODIFIED_TIME','CONTENT_TAG','MIME','ATTRIBUTION','TRUSTED_URL','OTHER_METADATA','OTHER_ROW_FIELDS','SERIALIZATION_ONLY'):assert values.get('STABILITY_RECON_FINAL_'+key)=='0'
 for key in ('PROTECTED_CHECKPOINTS_UNCHANGED','PAUSED_MEMBERSHIP_UNCHANGED','HELD_MEMBERSHIP_UNCHANGED'):assert values.get('INVENTORY_RECON_READBACK_'+key)=='1'
 assert len(deltas)==int(values['INVENTORY_RECON_SOURCE_DIFFERENCES'])<=100
 keys={'source_id_sha256','difference','relation','currently_represented','baseline_row_sha256','current_row_sha256','inventory_change_groups','critical_fields_changed'}
 assert len({r['source_id_sha256'] for r in deltas})==len(deltas)
 for row in deltas:
  assert set(row)==keys and re.fullmatch('[a-f0-9]{64}',row['source_id_sha256']) and type(row['currently_represented']) is bool
  assert row['difference'] in ('added','removed','changed','critical_metadata_changed','representation_missing')
  assert row['relation'] in ('approved_unresolved','approved_availability_exception','baseline_governed_hold','baseline_protected_retry','baseline_other','outside_approved_baseline')
  for k in ('baseline_row_sha256','current_row_sha256'):assert row[k] is None or re.fullmatch('[a-f0-9]{64}',row[k])
  assert set(row['inventory_change_groups'])<={'etag','size','parent_or_area','name','relative_path','modified_time','content_tag','mime','attribution','trusted_url','other_metadata','other_row_fields','serialization_only'}
  assert set(row['critical_fields_changed'])<={'source_item_id','source_drive_id','category','current_source','current_inventory_member','availability_exception','exact_complete_text','candidate_versions','candidate_source_provenance','holds','bulk_provenance'}
 raw=json.dumps(deltas,sort_keys=True,separators=(',',':'),ensure_ascii=False).encode();assert len(raw)<=131072 and hashlib.sha256(raw).hexdigest()==values['INVENTORY_RECON_SOURCE_DIFFERENCES_SHA256']
 for kind in ('added','removed','changed'):assert sum(r['difference']==kind for r in deltas)==int(values['INVENTORY_RECON_BASELINE_DIFF_'+kind.upper()])
 assert sum(bool(r['critical_fields_changed']) for r in deltas)==int(values['INVENTORY_RECON_APPROVED_CRITICAL_DRIFT_SOURCES'])
 assert sum(int(values['INVENTORY_RECON_CURRENT_CATEGORY_'+key.upper()]) for key in ('governed_review','retry_paused','automatic_retry','governed_hold','other_or_conflicting','complete_without_text','no_candidate'))==int(values['INVENTORY_RECON_UNRESOLVED_FILES'])
 for label in ('INVENTORY_LINEAGE','REPRESENTATION_AND_COVERAGE','RIGHTS_AND_CONTRARY','STABILITY_AND_CONTROLS'):
  assert 0<=int(values['INVENTORY_RECON_QUERY_'+label+'_MATCHED'])<=int(values['INVENTORY_RECON_REPRESENTED_FILES'])
 for key in ('PRESERVED_RECEIPTS_SHA256','BASELINE_INVENTORY_SHA256','PROTECTED_CHECKPOINT_SHA256','SEARCH_MATRIX_SHA256'):assert re.fullmatch('[a-f0-9]{64}',values['INVENTORY_RECON_'+key])
 return values


def verify_log(text):
 values=verify_inventory_log(text)
 rows=[]
 for line in text.splitlines():
  m=re.search(r' stdout F OUTSIDE_COHORT_SOURCE=(.*)$',line)
  if m:rows.append(json.loads(m[1]))
 assert values.get('OUTSIDE_COHORT_VERIFIED')=='1' and values.get('OUTSIDE_COHORT_COUNT')==str(len(rows)) and 0<=len(rows)<=10
 assert len({r['source_id_sha256'] for r in rows})==len(rows)
 keys={'source_id_sha256','relation','baseline_category','baseline_physical_member','current_physical_member','current_category','availability_exception','exact_complete_text','paused','held','candidate_count','source_version_rights_sha256','current_inventory_row_sha256','candidate_versions_sha256','provenance_sha256','holds_sha256','search_coverage','next_approval','processing_authorized'}
 for row in rows:
  assert set(row)==keys and row['relation'] in ('baseline_previously_available','added_physical_identity','outside_baseline')
  assert row['baseline_category'] in ('legacy_available','outside_baseline') and row['current_category'] in ('governed_hold','governed_review','retry_paused','automatic_retry','complete_without_text','no_candidate','other_or_conflicting')
  for k in ('baseline_physical_member','current_physical_member','availability_exception','exact_complete_text','paused','held','processing_authorized'):assert type(row[k]) is bool
  assert row['processing_authorized'] is False and row['next_approval']=='separate_baseline_scope_and_remediation_approval'
  assert type(row['candidate_count']) is int and row['candidate_count']>=0
  assert len(row['search_coverage'])==4 and all(type(v) is bool for v in row['search_coverage'])
  for k in ('source_id_sha256','source_version_rights_sha256','candidate_versions_sha256','provenance_sha256','holds_sha256'):assert re.fullmatch('[a-f0-9]{64}',row[k])
  assert row['current_inventory_row_sha256'] is None or re.fullmatch('[a-f0-9]{64}',row['current_inventory_row_sha256'])
  assert row['current_physical_member']==(row['current_inventory_row_sha256'] is not None)
  assert (row['relation']=='baseline_previously_available')==(row['baseline_category']=='legacy_available')
  if row['relation']=='added_physical_identity':assert row['current_physical_member'] and not row['baseline_physical_member']
 raw=json.dumps(rows,sort_keys=True,separators=(',',':'),ensure_ascii=False).encode();assert hashlib.sha256(raw).hexdigest()==values['OUTSIDE_COHORT_SHA256']
 expected={'APPROVED_CRITICAL_DRIFT_SOURCES':0,'MISSING_REPRESENTATION':0,'CURRENT_PAUSED_SOURCES':733,'CURRENT_HOLD_SOURCES':93,'PAUSED_MEMBERSHIP_CHANGED':0,'HOLD_MEMBERSHIP_CHANGED':0,'READBACK_OUTSIDE_APPROVED_SOURCES_CHANGED':0,'READBACK_REPRESENTED_ADDED':0,'READBACK_REPRESENTED_REMOVED':0,'PRESERVED_RECEIPTS_SHA256':'21c4bcd816686d4178c32bf224228c13639aa56a8225cf0cd3219af6fab0cd1f','PROTECTED_CHECKPOINT_SHA256':'214f2756ca0bc179bfaed880480113b5cd31cecd9de0e803e03013bcd4872ac7'}
 assert 23747<=int(values['INVENTORY_RECON_PHYSICAL_FILES'])<=23847 and 23757<=int(values['INVENTORY_RECON_REPRESENTED_FILES'])<=23857
 assert int(values['INVENTORY_RECON_UNRESOLVED_FILES'])==8430+len(rows)
 for k,v in expected.items():assert values.get('INVENTORY_RECON_'+k)==str(v),k
 deltas=[json.loads(re.search(r' stdout F INVENTORY_RECON_SOURCE_DELTA=(.*)$',line)[1]) for line in text.splitlines() if re.search(r' stdout F INVENTORY_RECON_SOURCE_DELTA=(.*)$',line)]
 added={r['source_id_sha256'] for r in deltas if r['difference']=='added'}
 assert len(json.dumps({'outside':rows,'differences':deltas},sort_keys=True,separators=(',',':'),ensure_ascii=False).encode())<=131072
 for row in rows:assert (row['relation']=='added_physical_identity')==(row['source_id_sha256'] in added)
 return values


def run_guard_tests():
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
 workflow=yaml.load((root/'.github/workflows/salcapa-knowledge-outside-cohort-drift.yml').read_text(),Loader=yaml.BaseLoader)
 assert 'workflow_dispatch' not in workflow['on']
 assert workflow['jobs']['authorize_scoped']['environment']=='salcapa-dev-approval'
 assert workflow['concurrency']['cancel-in-progress']=='false'
 for job in workflow['jobs'].values():
     for step in job.get('steps',[]):
         if 'run' in step:subprocess.run(['bash','-n'],input=step['run'],text=True,check=True)
 activation_path='deploy/azure/activations/knowledge-outside-cohort-drift-20261116.json'
 activation=json.loads((root/activation_path).read_text())
 assert activation['preserved_receipt_count']==20 and activation['new_search_receipt_count']==0 and activation['query_count']==4
 assert activation['expected_parent_batches']==200 and activation['expected_parent_sources']==8430
 assert activation['execution_memory']=='1Gi' and activation['maximum_observed_peak_rss_kib']==786432
 assert activation['statement_timeout_seconds']==120 and activation['maximum_parent_batch_sources']==50
 assert activation['read_only_reconciliation_authorized'] is True and activation['database_writes_authorized'] is False
 assert all(activation[k] is False for k in ('eligibility_diagnostic_schema_authorized','diagnostic_and_resolution_proposals_authorized','new_search_receipts_authorized','method_adoption_authorized','existing_eligibility_policy_changed','review_input_writes_authorized','preflight_execution_authorized','remediation_input_writes_authorized','parent_plan_writes_authorized','baseline_writes_authorized','source_record_or_schema_changes_authorized','automatic_processing_authorized','retry_resume_authorized','hold_release_authorized','source_content_downloads_authorized','protected_member_access','assignment_or_release_authority','production_deployment_authorized'))
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
     print('Actual pre-Azure guard rejected '+str(len(activation))+' changed activation fields, replay, all altered sources and governing rows')
 bicep=(root/'infra/azure/knowledge-outside-cohort-drift-job.bicep').read_text()
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

if __name__=='__main__':
 if len(sys.argv)==3 and sys.argv[1]=='--verify-log':
  result=verify_log(Path(sys.argv[2]).read_text());print('INVENTORY_RECON_TERMINAL_REPORT_VERIFIED=1')
 else:run_guard_tests()
