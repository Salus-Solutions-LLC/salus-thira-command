"""Diagnose saved zero-selection evidence and propose bounded resolution methods only."""
import copy,gc,hashlib,json,os,re,time,uuid
from datetime import datetime,timezone
try:import salus_remediation_support as rem
except ImportError:from tools import live_knowledge_remediation_proposals as rem
planning=rem.planning;baseline=rem.baseline;support=rem.support;require=rem.require
KEY='salus-preflight-blocker-diagnostic-20261116'
ACTOR='System Administrator - task consideration '+KEY+' / '
INPUT_SHA='d68b22cc0eca5655dee804dd3f8e2d511c4cded9d0643d1a2ab2cb829e1a2c85'
REVIEW_SHA='48b56aa85a3098946d9c75042b64c481941a6d8c290e2ed3a42eefeb41ac8638'
OLD_KEY='salus-remediation-review-preflight-proposals-20261116'
OLD_ACTOR='System Administrator - task consideration '+OLD_KEY+' / '
OLD_STATE='Proposed - Awaiting Bounded Preflight Approval'
OLD_TABLES=('m365_knowledge_preflight_proposals','m365_knowledge_remediation_reviews','m365_knowledge_preflight_batches','m365_knowledge_preflight_events')
STATE='Proposed - Awaiting Method and Bounded Preflight Approval'
TABLES=('m365_knowledge_eligibility_diagnostics','m365_knowledge_eligibility_batches','m365_knowledge_resolution_proposals','m365_knowledge_eligibility_events')
DDL=('CREATE TABLE IF NOT EXISTS '+TABLES[0]+' (operation_key TEXT PRIMARY KEY,state TEXT NOT NULL,review_manifest_sha256 TEXT NOT NULL,manifest_sha256 TEXT NOT NULL,payload_json TEXT NOT NULL,created_at TEXT NOT NULL)',
 'CREATE TABLE IF NOT EXISTS '+TABLES[1]+' (operation_key TEXT NOT NULL,batch_key TEXT NOT NULL,source_count INTEGER NOT NULL,payload_sha256 TEXT NOT NULL,payload_json TEXT NOT NULL,PRIMARY KEY(operation_key,batch_key))',
 'CREATE TABLE IF NOT EXISTS '+TABLES[2]+' (operation_key TEXT NOT NULL,proposal_key TEXT NOT NULL,source_count INTEGER NOT NULL,payload_sha256 TEXT NOT NULL,payload_json TEXT NOT NULL,PRIMARY KEY(operation_key,proposal_key))',
 'CREATE TABLE IF NOT EXISTS '+TABLES[3]+' (operation_key TEXT PRIMARY KEY,payload_json TEXT NOT NULL,created_at TEXT NOT NULL)')
QUERIES=(('eligibility_evidence','preflight eligibility blocker source version archive hash sha256 provenance review'),
 ('identity_and_limits','metadata etag current version size resource limit checkpoint lease due retry paused'),
 ('rights_and_contrary','rights permission hold restricted unsafe unknown active encryption conflicting contrary'),
 ('method_and_verification','method approval initial hash historical integrity verification audit receipt rollback cleanup'))
BOUNDS={'maximum_preflight_batches':2,'maximum_sources_per_preflight':5,'maximum_selected_sources':10,'maximum_bytes_per_stream':10485760,
 'maximum_streams_per_source':2,'maximum_total_bytes':209715200,'maximum_seconds_per_preflight':300,'maximum_total_seconds':600,
 'maximum_automatic_retries':0,'maximum_paid_external_api_calls':0,'maximum_persistent_source_content_bytes':0,
 'maximum_metadata_requests_per_source':2,'maximum_metadata_requests_total':20,'maximum_metadata_response_bytes':131072,'maximum_total_metadata_response_bytes':2621440}
EXCLUDED={'owner_hold_review','authorized_readable_source','safe_derivative_review','all_version_reconciliation','missing_candidate_provenance','unknown_condition_review'}
CODES=('category_not_automatic_retry','prior_owner_safety_or_cause_review','missing_current_source','candidate_version_count_not_one','current_version_mismatch',
 'archive_item_metadata_missing','size_outside_bound','version_requires_prior_review','source_sha256_absent','source_sha256_invalid','archive_etag_absent','current_size_or_etag_conflict')
SOFT={'source_sha256_absent','archive_etag_absent'}
GATES=['Review this exact diagnostic/proposal manifest and exact selected source/candidate/version bindings',
 'Source-owner/rightsholder authority, purpose/privacy and preserved pause/hold decisions',
 'Separate competent approval of the proposed method: metadata reconciliation or initial current-pair hash establishment; existing byte eligibility policy remains unchanged',
 'Validated exact implementation, identity/version/archive/lease preflight, resource/cost bounds, no public scanning/content retention, independent result and cleanup',
 'Separate exact-version execution approval; no conversion, extraction, enqueue, status/qualification change, retry resumption or hold release',
 'An initial pair-hash result cannot prove historical authenticity or replace missing historical hash evidence; record uncertainty and separately qualify any remedy']
STAGE='not_started';COMMIT_ATTEMPTED=COMMIT_ACKNOWLEDGED=0


def phase(value):
 global STAGE
 STAGE=value;gc.collect();print('BLOCKER_PHASE='+value,flush=True)
 try:import resource
 except ImportError:return
 peak=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss;print('BLOCKER_PEAK_RSS_KIB='+str(peak),flush=True);require(peak<786432,'MEMORY_BUDGET')


class Connection(baseline.ProposalConnection):
 def execute(self,sql,params=()):
  write=sql in DDL or bool(re.fullmatch(r'INSERT INTO (?:'+'|'.join((*TABLES,support.RECEIPT_TABLE))+r') VALUES\([?,]+\)',sql))
  if self.writes_enabled and write:
   if sql not in DDL:
    if sql.startswith('INSERT INTO '+support.RECEIPT_TABLE+' '):require(len(params)==10 and params[8] in {ACTOR+l for l,_ in QUERIES},'QUERY_DENIED')
    else:require(params and params[0]==KEY,'QUERY_DENIED')
   if self.deadline is not None:
    remaining=self.deadline-self.clock();require(remaining>0,'TRANSACTION_BUDGET')
    if self.backend=='postgres':self.inner.execute("SET LOCAL statement_timeout='"+str(max(1,min(30000,int(remaining*1000))))+"ms'")
   return self.inner.execute(sql,params)
  enabled=self.writes_enabled;self.writes_enabled=False
  try:return super().execute(sql,params)
  finally:self.writes_enabled=enabled


def remediation_proof(conn,*,expected_input=INPUT_SHA,expected_parent=rem.PARENT_SHA,expected_baseline=planning.MANIFEST,expected_batches=200,expected_sources=8430):
    base,parent,twelve=rem.parent_proof(conn,expected=expected_parent,baseline_sha=expected_baseline,expected_batches=expected_batches,expected_sources=expected_sources)
    row=conn.execute('SELECT * FROM '+rem.TABLES[0]+' WHERE operation_key=?',(rem.KEY,)).fetchone()
    require(row is not None,'REMEDIATION_MISSING')
    require(hashlib.sha256(row['payload_json'].encode()).hexdigest()==expected_input,'REMEDIATION_HEADER_DRIFT')
    header=planning.MEMBER_DECODER.decode(row['payload_json'])
    require(row['manifest_sha256']==support.digest(header)==expected_input and row['state']==header['state']==rem.STATE and row['created_at']==header['created_at'],'REMEDIATION_HEADER_DRIFT')
    require(header['parent_manifest_sha256']==row['parent_manifest_sha256']==expected_parent and header['approved_baseline_sha256']==expected_baseline and header['preserved_receipts_sha256']==twelve,'REMEDIATION_HEADER_DRIFT')
    require(header['proposal_count']==expected_batches and header['source_count']==expected_sources and header['categories']==parent['summary']['categories'],'REMEDIATION_SCOPE_DRIFT')
    require(header['method_catalog']==rem.METHODS and header['common_approval_gates']==rem.COMMON_GATES and all(header[k] is False for k in ('processing_authorized','retry_resume_authorized','hold_release_authorized','archive_bytes_verified','human_qualification_completed')),'REMEDIATION_AUTHORITY_DRIFT')
    rows=conn.execute('SELECT batch_key,source_count,payload_sha256,'+baseline.sql_hash(conn,'payload_json')+' actual_sha256 FROM '+rem.TABLES[1]+' WHERE operation_key=? ORDER BY batch_key',(rem.KEY,)).fetchall()
    require(len(rows)==len(header['proposal_hashes'])==expected_batches and sum(r['source_count'] for r in rows)==expected_sources,'REMEDIATION_SCOPE_DRIFT')
    require([r['batch_key'] for r in rows]==[r['batch_key'] for r in parent['batch_hashes']],'REMEDIATION_SCOPE_DRIFT')
    for actual,binding in zip(rows,header['proposal_hashes']):require(actual['batch_key']==binding['batch_key'] and 0<actual['source_count']<=50 and actual['payload_sha256']==actual['actual_sha256']==binding['sha256'],'REMEDIATION_BATCH_DRIFT')
    events=conn.execute('SELECT * FROM '+rem.TABLES[2]+' WHERE operation_key=?',(rem.KEY,)).fetchall()
    event={'manifest_sha256':expected_input,'state':rem.STATE,'parent_manifest_sha256':expected_parent,'processing_authorized':False}
    require(len(events)==1 and events[0]['created_at']==header['created_at'] and events[0]['payload_json']==support.canonical(event),'REMEDIATION_EVENT_DRIFT')
    current=[dict(r) for r in conn.execute('SELECT * FROM '+support.RECEIPT_TABLE+' WHERE actor LIKE ? ORDER BY actor',(rem.ACTOR+'%',)).fetchall()]
    require(current==sorted(header['current_consideration']['receipts'],key=lambda r:r['actor']),'PRESERVED_RECEIPT_DRIFT')
    receipts=base['original_receipts']+base['new_receipts']+parent['current_consideration']['receipts']+header['current_consideration']['receipts']
    require(len(receipts)==len({r['receipt_id'] for r in receipts})==16,'PRESERVED_RECEIPT_DRIFT')
    return base,parent,header,support.digest(sorted(receipts,key=lambda r:r['actor']))



def input_proof(conn,*,expected_review=REVIEW_SHA,**kwargs):
 base,parent,remh,sixteen=remediation_proof(conn,**kwargs)
 row=conn.execute('SELECT * FROM '+OLD_TABLES[0]+' WHERE operation_key=?',(OLD_KEY,)).fetchone();require(row is not None,'REVIEW_MISSING')
 require(hashlib.sha256(row['payload_json'].encode()).hexdigest()==expected_review,'REVIEW_HEADER_DRIFT');header=planning.MEMBER_DECODER.decode(row['payload_json'])
 require(row['manifest_sha256']==support.digest(header)==expected_review and row['state']==header['state']==OLD_STATE and row['created_at']==header['created_at'],'REVIEW_HEADER_DRIFT')
 require(row['input_manifest_sha256']==header['input_manifest_sha256']==support.digest(remh) and header['preserved_receipts_sha256']==sixteen and header['preserved_receipt_count']==16,'REVIEW_HEADER_DRIFT')
 require(header['parent_manifest_sha256']==support.digest(parent) and header['approved_baseline_sha256']==support.digest(base),'REVIEW_HEADER_DRIFT')
 require(header['reviewed_batches']==len(remh['proposal_hashes']) and header['reviewed_sources']==remh['source_count'] and header['selected_sources']==header['preflight_proposal_count']==0 and header['preflight_hashes']==[],'REVIEW_SCOPE_DRIFT')
 require(all(header[k] is False for k in ('preflight_execution_authorized','source_content_downloads_authorized','processing_authorized','retry_resume_authorized','hold_release_authorized','human_qualification_completed','archive_bytes_verified')),'REVIEW_AUTHORITY_DRIFT')
 rows=conn.execute('SELECT batch_key,source_count,payload_sha256,'+baseline.sql_hash(conn,'payload_json')+' actual_sha256 FROM '+OLD_TABLES[1]+' WHERE operation_key=? ORDER BY batch_key',(OLD_KEY,)).fetchall()
 require(len(rows)==len(header['review_hashes'])==header['reviewed_batches'] and sum(r['source_count'] for r in rows)==header['reviewed_sources'],'REVIEW_SCOPE_DRIFT')
 for actual,binding,prior in zip(rows,header['review_hashes'],remh['proposal_hashes']):require(actual['batch_key']==binding['batch_key']==prior['batch_key'] and actual['payload_sha256']==actual['actual_sha256']==binding['sha256'] and 0<actual['source_count']<=50,'REVIEW_BATCH_DRIFT')
 require(conn.execute('SELECT COUNT(*) FROM '+OLD_TABLES[2]+' WHERE operation_key=?',(OLD_KEY,)).fetchone()[0]==0,'REVIEW_SCOPE_DRIFT')
 event={'manifest_sha256':expected_review,'state':OLD_STATE,'input_manifest_sha256':support.digest(remh),'reviewed_batches':header['reviewed_batches'],'preflight_proposals':0,'preflight_execution_authorized':False,'processing_authorized':False}
 events=conn.execute('SELECT * FROM '+OLD_TABLES[3]+' WHERE operation_key=?',(OLD_KEY,)).fetchall();require(len(events)==1 and events[0]['payload_json']==support.canonical(event) and events[0]['created_at']==header['created_at'],'REVIEW_EVENT_DRIFT')
 fresh=[dict(r) for r in conn.execute('SELECT * FROM '+support.RECEIPT_TABLE+' WHERE actor LIKE ? ORDER BY actor',(OLD_ACTOR+'%',)).fetchall()]
 require(fresh==sorted(header['current_consideration']['receipts'],key=lambda r:r['actor']),'PRESERVED_RECEIPT_DRIFT')
 allrows=base['original_receipts']+base['new_receipts']+parent['current_consideration']['receipts']+remh['current_consideration']['receipts']+fresh
 require(len(allrows)==len({r['receipt_id'] for r in allrows})==20,'PRESERVED_RECEIPT_DRIFT')
 return base,parent,remh,header,support.digest(sorted(allrows,key=lambda r:r['actor']))


def target_empty(conn):
    counts=[]
    for table in TABLES:
        exists=bool(conn.execute('SELECT to_regclass(?)',(table,)).fetchone()[0]) if conn.backend=='postgres' else bool(conn.execute("SELECT name FROM sqlite_master WHERE type='table' AND name=?",(table,)).fetchone())
        counts.append(conn.execute('SELECT COUNT(*) FROM '+table+' WHERE operation_key=?',(KEY,)).fetchone()[0] if exists else 0)
    counts.append(conn.execute('SELECT COUNT(*) FROM '+support.RECEIPT_TABLE+' WHERE actor LIKE ?',(ACTOR+'%',)).fetchone()[0])
    for label,n in zip(('HEADERS','REVIEWS','PREFLIGHTS','EVENTS','TASK_RECEIPTS'),counts):print('BLOCKER_PRESTATE_'+label+'='+str(n),flush=True)
    require(not any(counts),'TARGET_NOT_EMPTY')



def legacy_reason(proposal,source,current):
    if proposal['category']!='automatic_retry':return 'paused_held_or_review_category'
    versions=source['candidate_versions'];methods=set(source['method_codes'])
    if methods&EXCLUDED or 'bounded_retry_preflight' not in methods:return 'prior_owner_safety_or_cause_review_required'
    if not source['current_inventory_member'] or len(versions)!=1:return 'missing_current_or_multiple_versions'
    version=versions[0]
    if not version['source_version_matches_current'] or not version['archive_metadata_recorded']:return 'current_version_or_archive_metadata_missing'
    if not isinstance(version['source_size'],int) or isinstance(version['source_size'],bool) or not 0<version['source_size']<=BOUNDS['maximum_bytes_per_stream']:return 'size_outside_bound'
    if set(version['method_codes'])&EXCLUDED:return 'version_requires_prior_review'
    live=current['candidate_versions'][0]
    if not live.get('source_sha256') or not live.get('source_archive_etag'):return 'integrity_metadata_incomplete'
    return 'conditional_metadata_candidate_not_authorized'



def source_blockers(proposal,source,current,inventory):
 codes=set();versions=source['candidate_versions'];live=current['candidate_versions']
 if proposal['category']!='automatic_retry':codes.add('category_not_automatic_retry')
 if set(source['method_codes'])&EXCLUDED or 'bounded_retry_preflight' not in source['method_codes']:codes.add('prior_owner_safety_or_cause_review')
 if not source['current_inventory_member']:codes.add('missing_current_source')
 if len(versions)!=1 or len(live)!=1:codes.add('candidate_version_count_not_one')
 by_id={r['id']:r for r in live}
 for version in versions:
  metadata=by_id.get(version['candidate_id']);require(metadata is not None,'SOURCE_RIGHTS_VERSION_DRIFT')
  if not version['source_version_matches_current']:codes.add('current_version_mismatch')
  if not version['archive_metadata_recorded'] or not metadata.get('source_archive_item_id'):codes.add('archive_item_metadata_missing')
  size=version['source_size']
  if not isinstance(size,int) or isinstance(size,bool) or not 0<size<=BOUNDS['maximum_bytes_per_stream']:codes.add('size_outside_bound')
  if set(version['method_codes'])&EXCLUDED:codes.add('version_requires_prior_review')
  value=metadata.get('source_sha256')
  if not value:codes.add('source_sha256_absent')
  elif not re.fullmatch('[a-fA-F0-9]{64}',value):codes.add('source_sha256_invalid')
  if not metadata.get('source_archive_etag'):codes.add('archive_etag_absent')
  item=inventory.get(source['source_item_id'])
  if item and (item['etag']!=version['source_etag'] or item['size']!=size):codes.add('current_size_or_etag_conflict')
 require(codes<=set(CODES),'BLOCKER_CODE_DRIFT');return sorted(codes)


def proposed_method(codes,first):
 if not codes and first=='conditional_metadata_candidate_not_authorized':return 'existing_policy_preflight'
 if not codes or set(codes)-SOFT:return None
 if 'archive_etag_absent' in codes:return 'metadata_identity_reconciliation'
 if codes==['source_sha256_absent']:return 'initial_current_pair_hash_establishment'
 return None


def diagnose_all(conn,base,parent,remh,review,evidence,core,inventory,*,expected_sources=8430):
 regenerated,scope=rem.build_proposals(conn,base,parent,evidence,core,inventory,expected_sources=expected_sources)
 lookup=rem.indexes(evidence,core);diagnostics=[];proposals=[];seen=set();first_counts={};all_counts={c:0 for c in CODES};auto_counts={c:0 for c in CODES};strict=0;selected_counts={}
 for fresh,binding,input_binding in zip(regenerated,review['review_hashes'],remh['proposal_hashes']):
  r=conn.execute('SELECT * FROM '+OLD_TABLES[1]+' WHERE operation_key=? AND batch_key=?',(OLD_KEY,binding['batch_key'])).fetchone();saved=planning.MEMBER_DECODER.decode(r['payload_json'])
  require(hashlib.sha256(r['payload_json'].encode()).hexdigest()==r['payload_sha256']==binding['sha256'],'REVIEW_BATCH_DRIFT')
  r=conn.execute('SELECT * FROM '+rem.TABLES[1]+' WHERE operation_key=? AND batch_key=?',(rem.KEY,input_binding['batch_key'])).fetchone();original=planning.MEMBER_DECODER.decode(r['payload_json'])
  require(hashlib.sha256(r['payload_json'].encode()).hexdigest()==r['payload_sha256']==input_binding['sha256'],'REMEDIATION_BATCH_DRIFT')
  semantic=copy.deepcopy(original)
  for row in semantic['source_bindings']:row.pop('current_bulk_checkpoints',None);row.pop('current_candidate_checkpoints',None)
  require(semantic==fresh and saved['input_proposal_sha256']==input_binding['sha256'] and saved['source_count']==len(saved['sources'])==original['source_count'] and saved['category']==original['category'],'REVIEW_SOURCE_BINDING_DRIFT')
  originals={r['source_item_id']:r for r in original['source_bindings']};records=[];eligible=[]
  for audit in saved['sources']:
   sid=audit['source_item_id'];require(sid in originals and sid not in seen,'REVIEW_SCOPE_DRIFT');seen.add(sid);source=originals[sid]
   require(audit['proposal_source_sha256']==support.digest(source) and audit['current_critical_sha256']==source['current_critical_sha256'] and audit['candidate_versions']==source['candidate_versions'] and audit['method_codes']==source['method_codes'],'REVIEW_SOURCE_BINDING_DRIFT')
   live={'candidate_versions':lookup['candidates'].get(sid,[])};first=legacy_reason(original,source,live)
   require(first==audit['preflight_disposition'],'LEGACY_ELIGIBILITY_DRIFT')
   codes=source_blockers(original,source,live,inventory);first_counts[first]=first_counts.get(first,0)+1;strict+=first=='conditional_metadata_candidate_not_authorized'
   for code in codes:
    all_counts[code]+=1
    if original['category']=='automatic_retry':auto_counts[code]+=1
   kind=proposed_method(codes,first)
   row={'source_item_id':sid,'category':original['category'],'input_audit_sha256':support.digest(audit),'input_remediation_source_sha256':support.digest(source),
    'current_critical_sha256':source['current_critical_sha256'],'candidate_versions':source['candidate_versions'],'method_codes':source['method_codes'],
    'legacy_first_blocker':first,'all_applicable_blockers':codes,'strict_existing_policy_eligible':first=='conditional_metadata_candidate_not_authorized',
    'proposed_resolution_method':kind,'execution_prerequisites_pending':['source-owner rights','exact method/implementation approval','fresh identity/lease/budget proof','separate execution approval'],
    'human_qualification_completed':False,'historical_integrity_proven':False,'execution_authorized':False}
   records.append(row)
   if kind:
    eligible.append({'source_item_id':sid,'diagnostic_source_sha256':support.digest(row),'candidate_versions':source['candidate_versions'],
     'current_critical_sha256':source['current_critical_sha256'],'resolution_method':kind,'blockers':codes,'strict_existing_policy_eligible':row['strict_existing_policy_eligible'],
     'candidate_metadata':[{k:r.get(k) for k in ('id','source_sha256','source_archive_item_id','source_archive_etag','source_size','source_etag')} for r in live['candidate_versions']],
     'method_approval_required':True,'method_approved':False,'source_rights_qualified':False,'historical_integrity_proven':False,'execution_authorized':False})
  chosen=[]
  if eligible and len(proposals)<2:
   chosen=sorted(eligible,key=lambda r:r['source_item_id'])[:5]
   for row in chosen:selected_counts[row['resolution_method']]=selected_counts.get(row['resolution_method'],0)+1
   proposals.append({'proposal_key':'resolution-'+str(len(proposals)+1).zfill(2),'parent_batch_key':saved['batch_key'],'input_review_sha256':binding['sha256'],'source_count':len(chosen),'source_bindings':chosen,
    'state':STATE,'bounds':BOUNDS,'approval_steps':GATES,'existing_eligibility_policy_changed':False,'method_approved':False,'preflight_execution_authorized':False,
    'source_content_downloads_authorized':False,'processing_authorized':False,'retry_resume_authorized':False,'hold_release_authorized':False,
    'method_limits':{'metadata_identity_reconciliation':'Propose current source/archive metadata checks only; no bytes. A newly observed etag does not prove historical lineage.',
     'initial_current_pair_hash_establishment':'Propose separately approved bounded current-original/archive hash measurements. No historical SHA256 exists: pair equality cannot prove historical authenticity. Do not claim eligibility under the existing recorded-hash rule.',
     'existing_policy_preflight':'Requires its own rights, exact implementation and execution approvals; no processing.'},
    'stop_conditions':['Any source/version/rights/hold/lease or budget drift','Absent competent method or source-owner approval','Unexpected archive identity, size, metadata or authorization/redirect condition','Hash mismatch or unavailable bytes; never bypass safety/access controls'],
    'graph_sha256_metadata_supported':False,'sha1_or_quickxor_substituted_for_sha256':False})
  chosen_ids={r['source_item_id'] for r in chosen}
  diagnostics.append({'batch_key':saved['batch_key'],'input_review_sha256':binding['sha256'],'category':saved['category'],'source_count':len(records),'sources':records,
   'proposed_sources':sorted(chosen_ids),'deferred_sources':sorted(r['source_item_id'] for r in records if r['source_item_id'] not in chosen_ids),'processing_authorized':False})
 require(len(seen)==expected_sources and len(diagnostics)==review['reviewed_batches'] and first_counts==review['review_dispositions'] and strict==review['selected_sources']==0,'REVIEW_SCOPE_DRIFT')
 summary={'first_blocker_counts_exclusive':first_counts,'all_blocker_source_counts_overlapping':all_counts,'automatic_retry_blocker_source_counts_overlapping':auto_counts,
  'strict_existing_policy_eligible_sources':strict,'proposed_source_method_counts':selected_counts,'counts_are_source_correlated':True,'overlapping_gate_counts_must_not_be_summed':True}
 return diagnostics,proposals,scope,summary


def bind_task_projection(function):
 # Reuse pinned code with isolated task configuration, never mutate its module.
 import types
 result=types.FunctionType(function.__code__,{**function.__globals__,'QUERIES':QUERIES,'ACTOR':ACTOR},function.__name__,function.__defaults__,function.__closure__)
 result.__kwdefaults__=dict(function.__kwdefaults__ or {})
 return result
search_matrix=bind_task_projection(rem.search_matrix)
observe=bind_task_projection(rem.observe)



def validate_scope(diagnostics,proposals,batches,sources):
 require(len(diagnostics)==batches and len({d['batch_key'] for d in diagnostics})==batches,'DIAGNOSTIC_SCOPE_DRIFT');by_source={};by_batch={d['batch_key']:d for d in diagnostics};selected=set();selection={}
 for d in diagnostics:
  require(d['source_count']==len(d['sources']) and d['processing_authorized'] is False,'DIAGNOSTIC_SCOPE_DRIFT')
  for s in d['sources']:require(s['source_item_id'] not in by_source,'DIAGNOSTIC_SCOPE_DRIFT');by_source[s['source_item_id']]=(d,s)
 require(len(by_source)==sources and len(proposals)<=2 and len({p['proposal_key'] for p in proposals})==len(proposals),'PROPOSAL_BOUND_DRIFT')
 for p in proposals:
  d=by_batch.get(p['parent_batch_key']);require(d and d['category']=='automatic_retry' and p['input_review_sha256']==d['input_review_sha256'],'PROPOSAL_SCOPE_DRIFT')
  require(p['state']==STATE and p['bounds']==BOUNDS and p['approval_steps']==GATES and 0<p['source_count']==len(p['source_bindings'])<=5,'PROPOSAL_BOUND_DRIFT')
  require(all(p[k] is False for k in ('existing_eligibility_policy_changed','method_approved','preflight_execution_authorized','source_content_downloads_authorized','processing_authorized','retry_resume_authorized','hold_release_authorized')),'PROPOSAL_AUTHORITY_DRIFT')
  for s in p['source_bindings']:
   sid=s['source_item_id'];require(sid in by_source and sid not in selected,'PROPOSAL_SCOPE_DRIFT');batch,diag=by_source[sid]
   require(batch['batch_key']==p['parent_batch_key'] and s['diagnostic_source_sha256']==support.digest(diag) and s['candidate_versions']==diag['candidate_versions'] and s['current_critical_sha256']==diag['current_critical_sha256'] and s['resolution_method']==diag['proposed_resolution_method']==proposed_method(diag['all_applicable_blockers'],diag['legacy_first_blocker']),'PROPOSAL_SCOPE_DRIFT')
   require(s['method_approval_required'] is True and all(s[k] is False for k in ('method_approved','source_rights_qualified','historical_integrity_proven','execution_authorized')),'PROPOSAL_AUTHORITY_DRIFT')
   selected.add(sid);selection.setdefault(p['parent_batch_key'],set()).add(sid)
 require(len(selected)<=10,'PROPOSAL_BOUND_DRIFT')
 for d in diagnostics:
  expected=selection.get(d['batch_key'],set());all_ids={r['source_item_id'] for r in d['sources']};require(d['proposed_sources']==sorted(expected) and d['deferred_sources']==sorted(all_ids-expected),'PROPOSAL_SCOPE_DRIFT')
 return selected


def summarize(diagnostics,proposals):
 first={};all_counts={c:0 for c in CODES};auto={c:0 for c in CODES};strict=0;methods={}
 for d in diagnostics:
  for s in d['sources']:
   require(s['category']==d['category'] and set(s['all_applicable_blockers'])<=set(CODES),'DIAGNOSTIC_SCOPE_DRIFT')
   reason=s['legacy_first_blocker'];first[reason]=first.get(reason,0)+1;strict+=s['strict_existing_policy_eligible']
   require(s['strict_existing_policy_eligible']==(reason=='conditional_metadata_candidate_not_authorized'),'LEGACY_ELIGIBILITY_DRIFT')
   for code in s['all_applicable_blockers']:
    all_counts[code]+=1
    if d['category']=='automatic_retry':auto[code]+=1
 for p in proposals:
  for s in p['source_bindings']:methods[s['resolution_method']]=methods.get(s['resolution_method'],0)+1
 return {'first_blocker_counts_exclusive':first,'all_blocker_source_counts_overlapping':all_counts,'automatic_retry_blocker_source_counts_overlapping':auto,'strict_existing_policy_eligible_sources':strict,'proposed_source_method_counts':methods,'counts_are_source_correlated':True,'overlapping_gate_counts_must_not_be_summed':True}


def event_for(header):return {'manifest_sha256':support.digest(header),'state':STATE,'review_manifest_sha256':header['review_manifest_sha256'],'diagnosed_batches':header['diagnosed_batches'],'proposal_count':header['proposal_count'],'method_approved':False,'execution_authorized':False}


def verify_output(conn,header,diagnostics,proposals):
 validate_scope(diagnostics,proposals,header['diagnosed_batches'],header['diagnosed_sources'])
 require(header['summary']==summarize(diagnostics,proposals),'DIAGNOSTIC_SUMMARY_DRIFT')
 row=conn.execute('SELECT * FROM '+TABLES[0]+' WHERE operation_key=?',(KEY,)).fetchone();require(row and row['payload_json']==support.canonical(header) and row['manifest_sha256']==support.digest(header) and row['state']==STATE and row['review_manifest_sha256']==header['review_manifest_sha256'] and row['created_at']==header['created_at'],'OUTPUT_HEADER_DRIFT')
 for table,key,values in ((TABLES[1],'batch_key',diagnostics),(TABLES[2],'proposal_key',proposals)):
  rows=conn.execute('SELECT * FROM '+table+' WHERE operation_key=? ORDER BY '+key,(KEY,)).fetchall();require(len(rows)==len(values),'OUTPUT_BATCH_DRIFT')
  for actual,value in zip(rows,values):require(actual[key]==value[key] and actual['source_count']==value['source_count'] and actual['payload_sha256']==support.digest(value) and actual['payload_json']==support.canonical(value),'OUTPUT_BATCH_DRIFT')
 events=conn.execute('SELECT * FROM '+TABLES[3]+' WHERE operation_key=?',(KEY,)).fetchall();require(len(events)==1 and events[0]['payload_json']==support.canonical(event_for(header)) and events[0]['created_at']==header['created_at'],'OUTPUT_EVENT_DRIFT')
 receipts=[dict(r) for r in conn.execute('SELECT * FROM '+support.RECEIPT_TABLE+' WHERE actor LIKE ? ORDER BY actor',(ACTOR+'%',)).fetchall()];require(receipts==sorted(header['current_consideration']['receipts'],key=lambda r:r['actor']),'TASK_RECEIPT_DRIFT');return support.digest(header)


def prepare(inner,context,*,expected_review=REVIEW_SHA,expected_input=INPUT_SHA,expected_parent=rem.PARENT_SHA,expected_baseline=planning.MANIFEST,expected_batches=200,expected_sources=8430,fail_after_diagnostics=False,clock=time.monotonic):
 global COMMIT_ATTEMPTED,COMMIT_ACKNOWLEDGED
 COMMIT_ATTEMPTED=COMMIT_ACKNOWLEDGED=0;started=clock();conn=Connection(inner);conn.clock=clock;conn.deadline=started+60
 args=dict(expected_review=expected_review,expected_input=expected_input,expected_parent=expected_parent,expected_baseline=expected_baseline,expected_batches=expected_batches,expected_sources=expected_sources)
 try:
  phase('locked_input_and_twenty_receipts')
  if conn.backend=='postgres':
   inner.execute('SET TRANSACTION ISOLATION LEVEL READ COMMITTED');inner.execute("SET LOCAL lock_timeout='2s'");inner.execute("SET LOCAL statement_timeout='30s'")
   require(inner.execute('SELECT pg_try_advisory_xact_lock(674160041245)').fetchone()[0],'PLANNING_BUSY');inner.execute('LOCK TABLE '+','.join((*support.SOURCE_TABLES,support.RECEIPT_TABLE,*baseline.TABLES,*support.PLAN_TABLES,*rem.TABLES,*OLD_TABLES))+' IN SHARE MODE NOWAIT')
  else:inner.execute('BEGIN IMMEDIATE')
  base,parent,remh,review,twenty=input_proof(conn,**args);del base,parent,remh,review;target_empty(conn)
  current=baseline.core_snapshot(conn);before=context.pop('preview_core');delta=baseline.core_delta(before,current);del before;require(current['represented']==context['evidence']['represented'],'SOURCE_OR_SEARCH_INPUT_DRIFT');baseline.emit_delta(delta,'BLOCKER_DRIFT')
  for family,allowed in (('candidates',{'classification_sha256','status','decision','reviewed_at','reviewed_by','review_rationale','target_folder'}),('holds',{'reviewed_at'}),('bulk',{'status','reason','metadata_sha256'})):
   require(delta[family]['added']==delta[family]['removed']==0 and set(delta[family]['fields'])<=allowed,'SOURCE_OR_SEARCH_INPUT_DRIFT')
  for change in delta['candidates']['rows']:
   if change['source_item_id'] in context['scope']:require(set(change['fields'])<={'reviewed_at'},'SOURCE_RIGHTS_VERSION_DRIFT')
  changed={r['source_item_id'] for r in delta['candidates']['rows']};require(len(changed)<=100,'REFRESH_SCOPE_EXCEEDED');old=context.pop('evidence');families=context.pop('families')
  evidence={'represented':current['represented'],'holds':current['holds'],'candidates':sorted([r for r in old['candidates'] if r['source_item_id'] not in changed]+baseline.candidate_subset(conn,changed),key=lambda r:r['id'])};del old
  if changed:families['C'].update(search_matrix(conn,family='C',source_ids=changed))
  for family in ('B','H'):families[family]=search_matrix(conn,family=family)
  observation=observe(evidence,current,context['inventory'],baseline.combine_families(families),context['drive_id']);signature=baseline.membership_signature(evidence);diagnostics=context['diagnostics'];proposals=context['proposals']
  diagnosed={r['source_item_id'] for d in diagnostics for r in d['sources']};observation['unresolved_outside_diagnostic_scope']=sorted(s for s,v in signature.items() if v[0]!='legacy_available' and s not in diagnosed);observation['outside_scope_disposition']='Considered only; no diagnostic/proposal scope or processing authority';del evidence,families,signature,diagnosed
  rem.current_schedules(conn,proposals);selected=validate_scope(diagnostics,proposals,expected_batches,expected_sources);require(context['summary']==summarize(diagnostics,proposals),'DIAGNOSTIC_SUMMARY_DRIFT')
  header={'operation_key':KEY,'state':STATE,'created_at':observation['created_at'],'review_manifest_sha256':expected_review,'remediation_manifest_sha256':expected_input,'parent_manifest_sha256':expected_parent,'approved_baseline_sha256':expected_baseline,
   'preserved_receipt_count':20,'preserved_receipts_sha256':twenty,'diagnosed_batches':len(diagnostics),'diagnosed_sources':expected_sources,'proposal_count':len(proposals),'proposed_sources':len(selected),'deferred_sources':expected_sources-len(selected),
   'summary':context['summary'],'blocker_codebook':CODES,'bounds':BOUNDS,'approval_steps':GATES,'current_consideration':observation,
   'diagnostic_hashes':[{'batch_key':d['batch_key'],'sha256':support.digest(d)} for d in diagnostics],'proposal_hashes':[{'proposal_key':p['proposal_key'],'sha256':support.digest(p)} for p in proposals],
   'existing_eligibility_policy_changed':False,'method_approved':False,'preflight_execution_authorized':False,'source_content_downloads_authorized':False,'processing_authorized':False,'retry_resume_authorized':False,'hold_release_authorized':False,'human_qualification_completed':False,'historical_integrity_proven':False,
   'source_record_writes':0,'review_input_writes':0,'remediation_input_writes':0,'parent_plan_writes':0,'baseline_writes':0,'paused_retries_preserved':True,'governed_holds_preserved':True,
   'execution_run_id':os.getenv('SALUS_POSTSEARCH_RUN_ID','fixture'),'script_sha256':os.getenv('SALUS_POSTSEARCH_SCRIPT_SHA256','fixture'),
   'source_references':['https://learn.microsoft.com/en-us/graph/api/resources/hashes?view=graph-rest-1.0','https://www.postgresql.org/docs/16/sql-lock.html'],
   'request':'Diagnose preflight eligibility blockers; preserve twenty receipts, paused retries and holds; prepare bounded proposals for approval, verify and update handoff',
   'limits':'Current metadata diagnosis/proposals only. Proposed initial hashes need separate method/rights/implementation/execution approval and cannot establish missing historical authenticity. No byte access or policy change now.',
   'chat_export_backfill_complete':False,'repository_source_copy_in_library':False}
  require(len(support.canonical(header).encode())+sum(len(support.canonical(v).encode()) for v in diagnostics+proposals)<=24*1024*1024,'OUTPUT_RESOURCE_BOUND');phase('atomic_diagnostics_proposals_and_receipts');conn.writes_enabled=True
  for sql in DDL:conn.execute(sql)
  for table,key,values in ((TABLES[1],'batch_key',diagnostics),(TABLES[2],'proposal_key',proposals)):
   for value in values:conn.execute('INSERT INTO '+table+' VALUES(?,?,?,?,?)',(KEY,value[key],value['source_count'],support.digest(value),support.canonical(value)))
  if fail_after_diagnostics:raise ValueError('INJECTED_ROLLBACK')
  for receipt in observation['receipts']:conn.execute('INSERT INTO '+support.RECEIPT_TABLE+' VALUES('+','.join('?' for _ in receipt)+')',tuple(receipt.values()))
  checksum=support.digest(header);conn.execute('INSERT INTO '+TABLES[0]+' VALUES(?,?,?,?,?,?)',(KEY,STATE,expected_review,checksum,support.canonical(header),header['created_at']));conn.execute('INSERT INTO '+TABLES[3]+' VALUES(?,?,?)',(KEY,support.canonical(event_for(header)),header['created_at']))
  verify_output(conn,header,diagnostics,proposals);require(input_proof(conn,**args)[4]==twenty,'PRESERVED_RECEIPT_DRIFT');require(clock()-started<60,'TRANSACTION_BUDGET');COMMIT_ATTEMPTED=1;inner.commit();COMMIT_ACKNOWLEDGED=1;print('BLOCKER_COMMIT_WINDOW_MS='+str(int((clock()-started)*1000)),flush=True)
  return header,diagnostics,proposals,current
 except Exception:inner.rollback();raise
 finally:conn.writes_enabled=False;conn.deadline=None


def main():
 from database import connect_database
 from salcapa_m365_intake import GovernedM365Config,GovernedM365Intake
 inner=intake=None
 try:
  require(os.getenv('SALUS_DB_BACKEND','').lower()=='postgres','BACKEND_REQUIRED');require(bool(re.fullmatch('[1-9][0-9]{5,19}',os.getenv('SALUS_POSTSEARCH_RUN_ID',''))) and bool(re.fullmatch('[0-9a-f]{64}',os.getenv('SALUS_POSTSEARCH_SCRIPT_SHA256',''))),'EXECUTION_BINDING')
  phase('review_and_twenty_receipts');inner=connect_database();conn=baseline.begin_read_only(inner);input_proof(conn);target_empty(conn);inner.close();inner=None
  config=GovernedM365Config.from_environment();intake=GovernedM365Intake(config);phase('stable_inventory');inventory=support.establish_stable_inventory(intake);require(len(inventory)>=23747,'BOUNDARY_BELOW_MINIMUM')
  phase('source_correlated_blocker_diagnosis');inner=connect_database();conn=baseline.begin_read_only(inner);base,parent,remh,review,_=input_proof(conn);support.verify_membership(conn,inventory)
  core=baseline.core_snapshot(conn);evidence=support.read_evidence(conn);families={f:search_matrix(conn,family=f) for f in ('C','B','H')};diagnostics,proposals,scope,summary=diagnose_all(conn,base,parent,remh,review,evidence,core,inventory);observe(evidence,core,inventory,baseline.combine_families(families),config.drive_id)
  inner.close();inner=None;del base,parent,remh,review;require(support.acquire_inventory(intake)==inventory,'SOURCE_INVENTORY_CHANGED')
  context={'preview_core':core,'evidence':evidence,'families':families,'inventory':inventory,'drive_id':config.drive_id,'diagnostics':diagnostics,'proposals':proposals,'scope':scope,'summary':summary};del core,evidence,families
  inner=connect_database();header,diagnostics,proposals,committed=prepare(inner,context);inner.close();inner=None;phase('independent_durable_readback');inner=connect_database();conn=baseline.begin_read_only(inner)
  require(input_proof(conn)[4]==header['preserved_receipts_sha256'],'PRESERVED_RECEIPT_DRIFT');checksum=verify_output(conn,header,diagnostics,proposals);after=baseline.core_snapshot(conn);delta=baseline.core_delta(committed,after);baseline.emit_delta(delta,'BLOCKER_POSTCOMMIT_DRIFT');require(after['represented']==committed['represented'],'INDEPENDENT_SOURCE_DRIFT')
  for family,allowed in (('candidates',{'reviewed_at'}),('holds',{'reviewed_at'}),('bulk',{'status','reason','metadata_sha256'})):require(delta[family]['added']==delta[family]['removed']==0 and set(delta[family]['fields'])<=allowed,'INDEPENDENT_SOURCE_DRIFT')
  for k,v in {'MANIFEST_SHA256':checksum,'REVIEW_MANIFEST_SHA256':REVIEW_SHA,'DIAGNOSED_BATCHES':200,'DIAGNOSED_SOURCES':8430,'PROPOSALS':len(proposals),'PROPOSED_SOURCES':header['proposed_sources'],'STRICT_ELIGIBLE_SOURCES':header['summary']['strict_existing_policy_eligible_sources'],'PRESERVED_RECEIPTS':20,'NEW_RECEIPTS':4,'SOURCE_RECORD_WRITES':0,'REVIEW_INPUT_WRITES':0,'REMEDIATION_INPUT_WRITES':0,'PARENT_PLAN_WRITES':0,'BASELINE_WRITES':0,'METHOD_APPROVED':0,'PREFLIGHT_EXECUTION_AUTHORIZED':0,'PROCESSING_AUTHORIZED':0,'FRESH_CONNECTION_VERIFIED':1,'DIAGNOSTIC_COMPLETE':1}.items():print('BLOCKER_'+k+'='+str(v),flush=True)
  for group in ('first_blocker_counts_exclusive','all_blocker_source_counts_overlapping','automatic_retry_blocker_source_counts_overlapping','proposed_source_method_counts'):
   for label,value in sorted(header['summary'][group].items()):print('BLOCKER_'+group.upper()+'_'+label.upper()+'='+str(value),flush=True)
  for receipt,(label,_) in zip(header['current_consideration']['receipts'],QUERIES):print('BLOCKER_RECEIPT_'+label.upper()+'_ID='+receipt['receipt_id'],flush=True);print('BLOCKER_RECEIPT_'+label.upper()+'_MATCHED='+str(receipt['matched_count']),flush=True)
 except Exception as exc:
  allowed={'MEMORY_BUDGET','QUERY_DENIED','TRANSACTION_BUDGET','PLANNING_BUSY','TARGET_NOT_EMPTY','PRESERVED_RECEIPT_DRIFT','REVIEW_MISSING','REVIEW_HEADER_DRIFT','REVIEW_SCOPE_DRIFT','REVIEW_AUTHORITY_DRIFT','REVIEW_BATCH_DRIFT','REVIEW_EVENT_DRIFT','REVIEW_SOURCE_BINDING_DRIFT','LEGACY_ELIGIBILITY_DRIFT','SOURCE_RIGHTS_VERSION_DRIFT','SOURCE_OR_SEARCH_INPUT_DRIFT','REFRESH_SCOPE_EXCEEDED','DIAGNOSTIC_SCOPE_DRIFT','DIAGNOSTIC_SUMMARY_DRIFT','PROPOSAL_BOUND_DRIFT','PROPOSAL_SCOPE_DRIFT','PROPOSAL_AUTHORITY_DRIFT','OUTPUT_RESOURCE_BOUND','OUTPUT_HEADER_DRIFT','OUTPUT_BATCH_DRIFT','OUTPUT_EVENT_DRIFT','TASK_RECEIPT_DRIFT','INDEPENDENT_SOURCE_DRIFT','SOURCE_INVENTORY_CHANGED','BOUNDARY_BELOW_MINIMUM','BACKEND_REQUIRED','EXECUTION_BINDING','REMEDIATION_MISSING','REMEDIATION_HEADER_DRIFT','REMEDIATION_SCOPE_DRIFT','REMEDIATION_AUTHORITY_DRIFT','REMEDIATION_BATCH_DRIFT','REMEDIATION_EVENT_DRIFT','BLOCKER_CODE_DRIFT','MEMBERSHIP_INVALID','DRIVE_SCOPE_DRIFT','AVAILABILITY_DRIFT','BASELINE_HEADER_DRIFT','BASELINE_MEMBER_DRIFT','BASELINE_EVENT_DRIFT','PARENT_HEADER_DRIFT','PARENT_BATCH_DRIFT','PARENT_EVENT_DRIFT','RESOURCE_BOUND'}
  code=exc.code if isinstance(exc,support.CensusFailure) else str(exc) if str(exc) in allowed else 'UNEXPECTED_FAILURE';print('BLOCKER_FAILURE_CODE='+code,flush=True);print('BLOCKER_FAILURE_STAGE='+STAGE,flush=True);print('BLOCKER_COMMIT_ATTEMPTED='+str(COMMIT_ATTEMPTED),flush=True);print('BLOCKER_COMMIT_ACKNOWLEDGED='+str(COMMIT_ACKNOWLEDGED),flush=True);raise SystemExit(1) from None
 finally:
  if inner is not None:inner.close()
  if intake is not None:intake.client.close();intake.credential.close()


if __name__=='__main__':main()
