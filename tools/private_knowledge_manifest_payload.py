"""Prepare a source/hash-bound bootstrap for one separately authorized job."""
import argparse,base64,hashlib,json,sys,zlib,re
from pathlib import Path

SOURCES={'salcapa_knowledge_consideration':'salcapa_knowledge_consideration.py','salus_manifest_helper':'tools/live_planning_evidence_search.py','salus_private_manifest':'tools/private_knowledge_manifest.py'}

def bundle(root,activation,run,attempt,commit):
    if not(re.fullmatch(r'\d{1,20}',str(run)) and str(attempt)=='1' and re.fullmatch('[a-f0-9]{40}',commit)):raise ValueError('RUN_BINDING')
    if activation['operation']!='private_knowledge_source_manifest' or activation['task_key']!='salus-private-source-reconciliation-20261123' or activation['target_environment']!='dev' or activation['resource_group']!='rg-salcapa-dev':raise ValueError('OPERATION_SCOPE')
    if activation['allowed_attempts']!=1 or activation['max_execution_seconds']!=900 or activation['audit_receipt_insert_limit']!=4 or activation['private_encrypted_file_create_limit']!=1:raise ValueError('EXECUTION_SCOPE')
    if any(activation[k] is not False for k in ['source_content_exported','source_permission_changes','reader_activation','processing_or_retry_resume','operational_implementation','public_artifacts','qualification_or_release_authority','production_deployment_authorized']):raise ValueError('AUTHORITY_SCOPE')
    from cryptography.hazmat.primitives import serialization
    from cryptography.hazmat.primitives.asymmetric import rsa
    public=base64.b64decode(activation['recipient_public_pem_base64'],validate=True);key=serialization.load_pem_public_key(public)
    if not(isinstance(key,rsa.RSAPublicKey) and key.key_size>=3072 and hashlib.sha256(public).hexdigest()==activation['public_key_sha256']):raise ValueError('PUBLIC_RECIPIENT_SCOPE')
    for file,expected in activation['guarded_source_sha256'].items():
        path=(Path(root)/file).resolve()
        if not path.is_relative_to(Path(root).resolve()) or hashlib.sha256(path.read_bytes()).hexdigest()!=expected:raise ValueError('CONTROLLER_SOURCE_BINDING')
    rows=[]
    for name,file in SOURCES.items():
        p=Path(root)/file
        if not p.exists() and (Path(root)/'source-reference'/Path(file).name).exists():p=Path(root)/'source-reference'/Path(file).name
        source=p.read_bytes()
        if hashlib.sha256(source).hexdigest()!=activation['source_sha256'][file]:raise ValueError('SOURCE_BINDING')
        rows.append({'name':name,'source':base64.b64encode(source).decode()})
    binding={'task':activation['task_key'],'run':str(run),'attempt':1,'workflow_commit':commit,'source_bindings':activation['source_sha256'],'public_key_sha256':activation['public_key_sha256']}
    payload={'modules':rows,'activation':activation,'binding':binding}
    encoded=base64.b64encode(zlib.compress(json.dumps(payload,separators=(',',':')).encode(),9)).decode()
    script='''import base64,json,os,sys,types,zlib
payload=json.loads(zlib.decompress(base64.b64decode(PAYLOAD)))
for row in payload['modules']:
 module=types.ModuleType(row['name']);sys.modules[row['name']]=module
 exec(compile(base64.b64decode(row['source']),'<frozen-source>','exec'),module.__dict__)
from database import connect_database
from salcapa_m365_intake import GovernedM365Config,GovernedM365Intake
import salus_manifest_helper as helper
import salus_private_manifest as m
conn=None;intake=None;stage='preflight'
try:
 m.require(os.getenv('SALUS_DB_BACKEND','').lower()=='postgres','BACKEND_SCOPE')
 config=GovernedM365Config.from_environment();a=payload['activation']
 m.require(m.digest((config.drive_id+':'+config.folder_item_id).encode())==a['source_root_sha256'],'SOURCE_ROOT_SCOPE')
 intake=GovernedM365Intake(config);intake.client=m.ReadRetryClient(intake.client)
 destination=m.private_destination(intake,a['destination_sha256'],a['owner_sha256'])
 stage='source_consideration';conn=connect_database()
 public=base64.b64decode(a['recipient_public_pem_base64'],validate=True)
 m.require(m.digest(public)==a['public_key_sha256'],'RECIPIENT_BINDING')
 envelope=m.run_export(conn,intake,helper,public,payload['binding'])
 stage='private_retention'
 result=m.retain_private(intake,destination,envelope,payload['binding'],a['owner_sha256'])
 print('PRIVATE_MANIFEST_RETAINED=1',flush=True)
 print('PRIVATE_MANIFEST_ENCRYPTED_BYTES='+str(result['encrypted_bytes']),flush=True)
 print('PRIVATE_MANIFEST_ENCRYPTED_SHA256='+result['encrypted_sha256'],flush=True)
 print('PRIVATE_MANIFEST_OWNER_ONLY_VERIFIED=1',flush=True)
 print('PRIVATE_MANIFEST_SOURCE_CONTENT_EXPORTED=0',flush=True)
 print('PRIVATE_MANIFEST_PUBLIC_ARTIFACT_CREATED=0',flush=True)
 print('PRIVATE_MANIFEST_COMPLETE=1',flush=True)
except Exception as exc:
 print('PRIVATE_MANIFEST_FAILURE_STAGE='+stage,flush=True)
 print('PRIVATE_MANIFEST_FAILURE_TYPE='+type(exc).__name__,flush=True)
 raise SystemExit(1) from None
finally:
 if conn is not None:conn.close()
 if intake is not None:intake.client.close();intake.credential.close()
'''.replace('PAYLOAD',repr(encoded))
    if len(script.encode())>100000:raise ValueError('BOOTSTRAP_BOUND')
    return base64.b64encode(script.encode()).decode()

def main():
 p=argparse.ArgumentParser();p.add_argument('--root',default='.');p.add_argument('--activation',required=True);p.add_argument('--run',required=True);p.add_argument('--attempt',required=True);p.add_argument('--commit',required=True);a=p.parse_args()
 value=bundle(a.root,json.loads(Path(a.activation).read_text()),a.run,a.attempt,a.commit);print(value)

if __name__=='__main__':main()
