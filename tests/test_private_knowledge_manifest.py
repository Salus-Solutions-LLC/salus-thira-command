import base64
import importlib.util
import io
import json
from pathlib import Path
import sqlite3
import sys
import types
import unittest
from unittest.mock import patch
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.exceptions import InvalidTag

ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('private_manifest',ROOT/'tools/private_knowledge_manifest.py');m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)

class Response:
 def __init__(self,status=200,value=None,content=b'',headers=None):self.status_code=status;self.value=value or{};self.content=content;self.headers=headers or{}
 def json(self):return self.value

class PrivateClient:
 def __init__(self,body):self.body=body;self.calls=[];self.shared=False;self.existing=False;self.bad_upload=False;self.bad_read=False;self.write_status=201
 def get(self,url,headers=None,params=None,**kw):
  self.calls.append(('GET',url,headers))
  if url.endswith('/permissions'):
   values=[{'roles':['owner'],'grantedToV2':{'user':{'id':'fixture-owner'}}}]
   if self.shared:values.append({'roles':['read'],'link':{'scope':'anonymous'}})
   return Response(value={'value':values})
  if url.endswith('/root'):return Response(value={'id':'ROOT-0000001','folder':{}})
  if url.endswith('/children'):return Response(value={'value':[{'id':'FOLDER-000001','name':'Salus Restricted Review','folder':{},'parentReference':{'id':'ROOT-0000001'}}]})
  if url.endswith('/content'):return Response(content=self.body+(b'bad'if self.bad_read else b''))
  return Response(200 if self.existing else 404)
 def post(self,url,headers=None,json=None,**kw):
  self.calls.append(('POST',url,json));return Response(value={'uploadUrl':'https://evil.example/upload'if self.bad_upload else'https://salussolutions-my.sharepoint.com/session-fixture'})
 def put(self,url,headers=None,content=None,**kw):
  self.calls.append(('PUT',url,headers));return Response(self.write_status,{'id':'FILE-0000001','name':'Salus_Private_Source_Manifest_20261123_000000.json','size':len(content),'parentReference':{'id':'FOLDER-000001'},'file':{}})

def intake_fixture(body):
 client=PrivateClient(body)
 return types.SimpleNamespace(client=client,config=types.SimpleNamespace(drive_id='DRIVE-000001'),_headers=lambda:{'Authorization':'Bearer fictional-test-only'})

class ManifestTests(unittest.TestCase):
 @classmethod
 def setUpClass(cls):
  cls.key=rsa.generate_private_key(public_exponent=65537,key_size=3072)
  cls.private=cls.key.private_bytes(serialization.Encoding.PEM,serialization.PrivateFormat.PKCS8,serialization.NoEncryption())
  cls.public=cls.key.public_key().public_bytes(serialization.Encoding.PEM,serialization.PublicFormat.SubjectPublicKeyInfo)
  cls.binding={'task':'fictional-source-reconciliation','run':'000000','attempt':1}
 def sealed(self):return m.seal({'sources':{'fictional-source-01':[['candidate','Sensitive fictional title','hash']]},'source_body_exported':False},self.public,self.binding)
 def test_roundtrip_only_local_private_key(self):
  value=m.open_envelope(self.sealed(),self.private,self.binding);self.assertFalse(value['source_body_exported'])
 def test_no_plaintext_in_transport(self):
  text=self.sealed().decode('ascii');self.assertNotIn('Sensitive fictional',text);self.assertNotIn('fictional-source-01',text);self.assertNotIn('PRIVATE KEY',text)
 def test_changed_task_binding_rejected(self):
  with self.assertRaises(ValueError):m.open_envelope(self.sealed(),self.private,{**self.binding,'run':'other'})
 def test_ciphertext_tampering_rejected(self):
  e=json.loads(self.sealed());cipher=bytearray(base64.b64decode(e['ciphertext']));cipher[0]^=1;e['ciphertext']=base64.b64encode(cipher).decode()
  with self.assertRaises(InvalidTag):m.open_envelope(m.canonical(e),self.private,self.binding)
 def test_small_key_rejected(self):
  key=rsa.generate_private_key(public_exponent=65537,key_size=2048).public_key().public_bytes(serialization.Encoding.PEM,serialization.PublicFormat.SubjectPublicKeyInfo)
  with self.assertRaises(ValueError):m.seal({},key,self.binding)
 def test_resource_bound_rejected(self):
  with patch.object(m,'MAX_PLAINTEXT',2):
   with self.assertRaises(ValueError):m.seal({'large':'value'},self.public,self.binding)
 def test_source_identity_rejects_path_or_query(self):
  for value in ['../source','https://host/x','source\nidentifier','']:
   with self.assertRaises(ValueError):m.safe_identity(value)
 def test_write_guard_denies_source_mutation_ddl_and_extra_receipts(self):
  class Inner:
   def execute(self,*args):return None
  c=m.AuditLimitedConnection(Inner(),'actor',['hash'])
  for sql in ['DELETE FROM m365_bulk_items','UPDATE m365_knowledge_candidates SET status=1','SELECT * FROM users','SELECT 1; DELETE FROM m365_bulk_items','WITH q AS (DELETE FROM m365_bulk_items RETURNING *) SELECT * FROM q']:
   with self.assertRaises(ValueError):c.execute(sql)
  with self.assertRaises(ValueError):c.executescript('DROP TABLE m365_bulk_items')
  statement='INSERT INTO m365_knowledge_consideration_receipts VALUES(?,?,?,?,?,?,?,?,?,?)';params=('receipt','hash',1,1,1,1,0,0,'actor / query','time')
  c.execute(statement,params)
  with self.assertRaises(ValueError):c.execute(statement,params)
 def test_private_destination_exact_binding_and_owner(self):
  i=intake_fixture(b'{}');folder=m.private_destination(i,m.digest(b'DRIVE-000001:FOLDER-000001'),m.digest(b'fixture-owner'));self.assertEqual(folder,'FOLDER-000001');self.assertTrue(all(x[0]=='GET'for x in i.client.calls))
 def test_private_destination_rejects_sharing(self):
  i=intake_fixture(b'{}');i.client.shared=True
  with self.assertRaises(ValueError):m.private_destination(i,m.digest(b'DRIVE-000001:FOLDER-000001'),m.digest(b'fixture-owner'))
  self.assertTrue(all(x[0]=='GET'for x in i.client.calls))
 def test_private_destination_rejects_wrong_binding(self):
  i=intake_fixture(b'{}')
  with self.assertRaises(ValueError):m.private_destination(i,'wrong',m.digest(b'fixture-owner'))
 def test_private_encrypted_file_create_only_and_byte_readback(self):
  e=self.sealed();i=intake_fixture(e);result=m.retain_private(i,'FOLDER-000001',e,self.binding,m.digest(b'fixture-owner'))
  self.assertTrue(result['owner_only_verified']);self.assertFalse(result['public_artifact_created']);self.assertEqual(result['encrypted_sha256'],m.digest(e))
  self.assertEqual([r[0]for r in i.client.calls].count('POST'),1);self.assertEqual([r[0]for r in i.client.calls].count('PUT'),1)
  upload=next(r for r in i.client.calls if r[0]=='PUT');self.assertNotIn('Authorization',upload[2])
  session=next(r for r in i.client.calls if r[0]=='POST');self.assertEqual(session[2]['item']['@microsoft.graph.conflictBehavior'],'fail')
 def test_existing_private_file_is_not_overwritten(self):
  i=intake_fixture(b'{}');i.client.existing=True
  with self.assertRaises(ValueError):m.retain_private(i,'FOLDER-000001',b'{}',self.binding,m.digest(b'fixture-owner'))
  self.assertTrue(all(r[0]=='GET'for r in i.client.calls))
 def test_private_upload_rejects_external_host(self):
  i=intake_fixture(b'{}');i.client.bad_upload=True
  with self.assertRaises(ValueError):m.retain_private(i,'FOLDER-000001',b'{}',self.binding,m.digest(b'fixture-owner'))
  self.assertFalse(any(r[0]=='PUT'for r in i.client.calls))
 def test_private_readback_mismatch_fails_without_retry_or_replacement(self):
  i=intake_fixture(b'{}');i.client.bad_read=True
  with self.assertRaises(ValueError):m.retain_private(i,'FOLDER-000001',b'{}',self.binding,m.digest(b'fixture-owner'))
  self.assertEqual([r[0]for r in i.client.calls].count('PUT'),1)
 def test_private_upload_replacement_response_is_rejected(self):
  i=intake_fixture(b'{}');i.client.write_status=200
  with self.assertRaises(ValueError):m.retain_private(i,'FOLDER-000001',b'{}',self.binding,m.digest(b'fixture-owner'))
  self.assertEqual([r[0]for r in i.client.calls].count('PUT'),1)
 def test_get_retry_respects_retry_after_and_does_not_repeat_writes(self):
  class Inner:
   count=0;writes=0
   def get(self,*a,**kw):
    self.count+=1;return Response(429 if self.count==1 else 200,headers={'Retry-After':'12'})
   def post(self,*a,**kw):self.writes+=1;return Response(503)
   put=post
  waits=[];inner=Inner();client=m.ReadRetryClient(inner,clock=lambda:0,sleep=waits.append)
  self.assertEqual(client.get('fixture').status_code,200);self.assertEqual(waits,[12]);client.post('fixture');self.assertEqual(inner.writes,1)
 def test_get_retry_does_not_retry_before_long_retry_after(self):
  inner=types.SimpleNamespace(get=lambda *a,**kw:Response(429,headers={'Retry-After':'62'}));waits=[];client=m.ReadRetryClient(inner,clock=lambda:0,sleep=waits.append)
  with self.assertRaises(ValueError):client.get('fixture')
  self.assertFalse(waits)
 def test_actual_existing_consideration_pipeline_and_four_audit_inserts(self):
  fastapi=types.ModuleType('fastapi');fastapi.Query=lambda *a,**kw:None
  def source_path(name):
   local=ROOT/'source-reference'/name
   return local if local.exists() else ROOT/name if name=='salcapa_knowledge_consideration.py' else ROOT/'tools'/name
  with patch.dict(sys.modules,{'fastapi':fastapi}):
   spec=importlib.util.spec_from_file_location('salcapa_knowledge_consideration',source_path('salcapa_knowledge_consideration.py'));service=importlib.util.module_from_spec(spec);spec.loader.exec_module(service)
  with patch.dict(sys.modules,{'salcapa_knowledge_consideration':service}):
   spec=importlib.util.spec_from_file_location('fixture_helper',source_path('live_planning_evidence_search.py'));helper=importlib.util.module_from_spec(spec);spec.loader.exec_module(helper)
   c=sqlite3.connect(':memory:');c.row_factory=sqlite3.Row;c.create_function('salus_sha256',1,lambda value:m.digest(str(value).encode()))
   c.executescript('CREATE TABLE m365_knowledge_candidates(id INTEGER PRIMARY KEY,source_item_id,source_name,source_relative_path,source_sha256,source_modified_at,status,classification_json,source_owner,target_folder);CREATE TABLE m365_bulk_items(item_id,name,metadata_json,status,reason,kind,updated_at);CREATE TABLE m365_knowledge_holds(source_item_id,source_name,source_relative_path,source_area,hold_reason,status);')
   for col in ['drive_id','pending_id','attempts','next_attempt','lease_owner','lease_until']:c.execute('ALTER TABLE m365_bulk_items ADD COLUMN '+col)
   c.execute('CREATE TABLE m365_bulk_extraction_checks(candidate_id,attempts,next_attempt,lease_owner,lease_until,last_code)')
   service._create_receipt_table(c)
   c.execute('INSERT INTO m365_knowledge_candidates VALUES(?,?,?,?,?,?,?,?,?,?)',(1,'SOURCE-0001','warning','','b'*64,'2026-01-01','Ingested',json.dumps({'extraction':{'status':'Complete','text':'liaison warning evacuation'}}),'fixture','fixture'))
   for sid,name in [('SOURCE-0001','warning'),('SOURCE-0002','family reunification')]:c.execute('INSERT INTO m365_bulk_items(item_id,name,metadata_json,status,reason,kind,updated_at) VALUES(?,?,?,?,?,?,?)',(sid,name,'{}','Pending','','file','2026-01-01'))
   c.execute('INSERT INTO m365_knowledge_holds VALUES(?,?,?,?,?,?)',('SOURCE-0003','reopening recovery','','enterprise','rights','Governed Hold'));c.commit()
   helper.source_census=lambda _intake:{'SOURCE-0001':('v1','date'),'SOURCE-0002':('v1','date')}
   run=helper.run_search;helper.run_search=lambda *a,**kw:run(*a,minimum_represented=1,**kw)
   binding={**self.binding,'task':'salus-private-source-reconciliation-20261123'}
   envelope=m.run_export(c,object(),helper,self.public,binding)
   payload=m.open_envelope(envelope,self.private,binding)
   self.assertEqual(len(payload['source_rows']),3);self.assertEqual(len(payload['consideration_receipts']),4);self.assertFalse(payload['source_content_exported']);self.assertEqual(payload['physical_files'],2)
   self.assertEqual(c.execute('SELECT count(*) FROM m365_knowledge_consideration_receipts').fetchone()[0],4)
   self.assertNotIn('liaison warning evacuation',json.dumps(payload))
   with self.assertRaises(RuntimeError):m.run_export(c,object(),helper,self.public,binding)
 def test_complete_source_set_no_body_export_and_read_only_queries(self):
  service=types.ModuleType('salcapa_knowledge_consideration');service._terms=lambda q:q.split();service._patterns=lambda ts:(' OR '.join('lower(search_text) LIKE ?'for _ in ts),tuple('%'+t+'%'for t in ts))
  c=sqlite3.connect(':memory:');c.row_factory=sqlite3.Row;c.create_function('salus_sha256',1,lambda value:m.digest(str(value).encode()))
  c.executescript('CREATE TABLE m365_knowledge_candidates(source_item_id,source_name,source_relative_path,source_sha256,source_modified_at,status,classification_json);CREATE TABLE m365_bulk_items(item_id,name,metadata_json,status,reason,kind);CREATE TABLE m365_knowledge_holds(source_item_id,source_name,source_relative_path,source_area,hold_reason,status);')
  c.execute('INSERT INTO m365_knowledge_candidates VALUES(?,?,?,?,?,?,?)',('SOURCE-0001','radio','','a'*64,'2026-01-01','Ingested',json.dumps({'extraction':{'status':'Complete','text':'Body not exported: liaison communications'}})))
  c.execute('INSERT INTO m365_bulk_items VALUES(?,?,?,?,?,?)',('SOURCE-0002','shelter','{"eTag":"v2"}','Pending','content unavailable','file'))
  c.execute('INSERT INTO m365_bulk_items VALUES(?,?,?,?,?,?)',('SOURCE-REMOVED','old','{}','Removed','','file'))
  c.execute('INSERT INTO m365_knowledge_holds VALUES(?,?,?,?,?,?)',('SOURCE-0003','family care','','enterprise','rights','Governed Hold'));c.commit()
  c.execute('ALTER TABLE m365_knowledge_candidates ADD COLUMN source_owner');c.execute('ALTER TABLE m365_knowledge_candidates ADD COLUMN target_folder')
  statements=[];c.set_trace_callback(statements.append);c.execute('PRAGMA query_only=ON')
  with patch.dict(sys.modules,{'salcapa_knowledge_consideration':service}):rows=m.collect_metadata(c,(('a','liaison'),('b','shelter'),('c','family'),('d','none')))
  self.assertEqual(set(rows),{'SOURCE-0001','SOURCE-0002','SOURCE-0003'});self.assertEqual([rows[k][0][-1]for k in sorted(rows)],[1,2,4]);self.assertNotIn('Body not exported',json.dumps(rows));self.assertTrue(all(s.startswith(('SELECT ','WITH ','PRAGMA query_only'))for s in statements));self.assertEqual(rows['SOURCE-0002'][0][-2],'')

if __name__=='__main__':unittest.main()
