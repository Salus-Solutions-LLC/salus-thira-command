"""Read-only inventory reconciliation; never adopts a baseline or prepares records."""
import gc,hashlib,json,os,re,types
from datetime import datetime,timezone
try:import salus_remediation_support as rem
except ImportError:from tools import live_knowledge_remediation_proposals as rem
planning=rem.planning;baseline=rem.baseline;support=rem.support;require=baseline.require
KEY='salus-outside-cohort-reconciliation-20261116'
INPUT_SHA='d68b22cc0eca5655dee804dd3f8e2d511c4cded9d0643d1a2ab2cb829e1a2c85'
REVIEW_SHA='48b56aa85a3098946d9c75042b64c481941a6d8c290e2ed3a42eefeb41ac8638'
OLD_KEY='salus-remediation-review-preflight-proposals-20261116'
OLD_ACTOR='System Administrator - task consideration '+OLD_KEY+' / '
OLD_STATE='Proposed - Awaiting Bounded Preflight Approval'
OLD_TABLES=('m365_knowledge_preflight_proposals','m365_knowledge_remediation_reviews','m365_knowledge_preflight_batches','m365_knowledge_preflight_events')
FAILED_KEY='salus-preflight-blocker-diagnostic-20261116'
FAILED_TABLES=('m365_knowledge_eligibility_diagnostics','m365_knowledge_eligibility_batches','m365_knowledge_resolution_proposals','m365_knowledge_eligibility_events')
BASELINE_INVENTORY_SHA='0e556598be30292cc1bbb2e46bb964b2e6e6f5e38f0b3b5e93b48a7cc68bc613'
FAILED_FINAL_SHA='efd10c4ed8793e808d79076f57074afedc549d315985fe6f4dea98f1196e3621'
QUERIES=(('inventory_lineage','outside cohort unresolved identity current historical baseline archive version provenance'),('representation_and_coverage','outside recovery scope two added previously available missing coverage receipt verification'),('rights_and_contrary','rights permission hold restricted unsafe conflicting contrary retry paused'),('stability_and_controls','stable inventory independent readback checkpoint lease audit rollback cleanup approval'))
MAX_DELTA=100
STAGE='not_started'
def phase(value):
 global STAGE
 STAGE=value;gc.collect();print('INVENTORY_RECON_PHASE='+value,flush=True)
 try:import resource
 except ImportError:return
 peak=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss;print('INVENTORY_RECON_PEAK_RSS_KIB='+str(peak),flush=True);require(peak<786432,'MEMORY_BUDGET')
class ReadOnlyConnection:
 def __init__(self,inner):self.inner=inner;self.backend=getattr(inner,'backend','sqlite')
 def execute(self,sql,params=()):
  clean=re.sub(r"'(?:''|[^'])*'", "''",sql).strip().rstrip(';').strip();words=set(re.findall('[A-Z_]+',clean.upper()))
  forbidden={'INSERT','UPDATE','DELETE','MERGE','CREATE','ALTER','DROP','TRUNCATE','COPY','CALL','DO','INTO','LOCK','COMMIT','GRANT','REVOKE','VACUUM','ANALYZE','SET','PRAGMA'}
  require(';' not in clean and '--' not in clean and '/*' not in clean and clean.upper().startswith(('SELECT ','WITH ')) and not words.intersection(forbidden),'QUERY_DENIED')
  return self.inner.execute(sql,params)
def begin_read_only(inner):
 if getattr(inner,'backend','sqlite')=='postgres':
  inner.execute('SET TRANSACTION ISOLATION LEVEL REPEATABLE READ READ ONLY');inner.execute("SET LOCAL statement_timeout='120s'")
 else:inner.execute('PRAGMA query_only=ON');inner.execute('BEGIN')
 return ReadOnlyConnection(inner)
search_matrix=types.FunctionType(rem.search_matrix.__code__,{**rem.search_matrix.__globals__,'QUERIES':QUERIES},rem.search_matrix.__name__,rem.search_matrix.__defaults__,rem.search_matrix.__closure__)
search_matrix.__kwdefaults__=dict(rem.search_matrix.__kwdefaults__ or {})


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


def saved_targets(conn):
 counts=[]
 for table in FAILED_TABLES:
  exists=bool(conn.execute('SELECT to_regclass(?)',(table,)).fetchone()[0]) if conn.backend=='postgres' else bool(conn.execute("SELECT name FROM sqlite_master WHERE type='table' AND name=?",(table,)).fetchone())
  counts.append(conn.execute('SELECT COUNT(*) FROM '+table+' WHERE operation_key=?',(FAILED_KEY,)).fetchone()[0] if exists else 0)
 for key in (FAILED_KEY,'salus-readonly-inventory-reconciliation-20261116',KEY):counts.append(conn.execute('SELECT COUNT(*) FROM '+support.RECEIPT_TABLE+' WHERE actor LIKE ?',('System Administrator - task consideration '+key+' / %',)).fetchone()[0])
 require(not any(counts),'SAVED_OUTPUT_REQUIRES_RECONCILIATION');return counts

def reconstruct_baseline(conn,header,expected_inventory=BASELINE_INVENTORY_SHA):
 inventory={};authority={};selected={};keys=[r['source_item_id'] for r in header['member_hashes']];bindings={r['source_item_id']:r['sha256'] for r in header['member_hashes']}
 for member in planning.read_member_groups(conn,keys):
  sid=member['source_item_id'];require(support.digest(member)==bindings[sid] and sid not in authority,'BASELINE_MEMBER_DRIFT')
  paused=any(v['extraction_status']=='Retry Paused' or str(v.get('automatic_retry_paused','')).casefold() in ('true','1') for v in member['candidate_versions'])
  authority[sid]={'category':member['category'],'exception':member['availability_exception'],'held':bool(member['holds']),'paused':paused}
  if member['current_inventory_member']:
   row=member['current_source'];require(row and row['item_id']==sid,'BASELINE_INVENTORY_DRIFT');inventory[sid]=row
  else:require(member['current_source'] is None,'BASELINE_INVENTORY_DRIFT')
  if member['category']!='legacy_available' or member['availability_exception'] or member['holds'] or paused:
   value=planning.critical(member);selected[sid]={'category':member['category'],'exception':member['availability_exception'],'held':bool(member['holds']),'paused':paused,'sha256':support.digest(value),'fields':{k:support.digest(v) for k,v in value.items()}}
 require(len(authority)==len(keys) and len(inventory)==header['physical_files'] and support.snapshot_digest(inventory)==header['inventory_sha256']==expected_inventory,'BASELINE_INVENTORY_DRIFT')
 require(sum(v['category']!='legacy_available' for v in authority.values())==header['unresolved_files'],'BASELINE_SCOPE_DRIFT')
 return inventory,authority,selected

def current_member(sid,category,exception,exact,lookup,inventory,drive_id):
 return {'source_item_id':sid,'source_drive_id':drive_id,'category':category,'current_source':inventory.get(sid),'current_inventory_member':sid in inventory,'availability_exception':exception,'exact_complete_text':exact,
  'candidate_versions':[{k:v for k,v in row.items() if k!='checkpoint'} for row in lookup['candidates'].get(sid,[])],
  'candidate_source_provenance':lookup['provenance'].get(sid,[]),'holds':lookup['holds'].get(sid,[]),'bulk_provenance':lookup['bulk'].get(sid,[])}

def source_deltas(before,after,authority,selected,critical_drift,represented):
 physical=(set(after)-set(before))|(set(before)-set(after))|{s for s in before.keys()&after.keys() if before[s]!=after[s]}
 missing=set(after)-set(represented);identities=physical|set(critical_drift)|missing
 require(len(identities)<=MAX_DELTA,'DELTA_REPORT_BOUND')
 rows=[]
 for sid in sorted(identities):
  kind='added' if sid not in before and sid in after else 'removed' if sid in before and sid not in after else 'changed' if sid in physical else 'critical_metadata_changed' if sid in critical_drift else 'representation_missing'
  relation='approved_unresolved' if sid in selected and selected[sid]['category']!='legacy_available' else 'approved_availability_exception' if sid in selected and selected[sid]['exception'] else 'baseline_governed_hold' if sid in selected and selected[sid]['held'] else 'baseline_protected_retry' if sid in selected else 'baseline_other' if sid in authority else 'outside_approved_baseline'
  groups=[k for k,v in support.inventory_diff({sid:before[sid]},{sid:after[sid]}).items() if v and k not in ('added','removed','changed')] if sid in before and sid in after else []
  rows.append({'source_id_sha256':hashlib.sha256(sid.encode()).hexdigest(),'difference':kind,'relation':relation,'currently_represented':sid in represented,'baseline_row_sha256':support.digest(before[sid]) if sid in before else None,'current_row_sha256':support.digest(after[sid]) if sid in after else None,'inventory_change_groups':groups,'critical_fields_changed':critical_drift.get(sid,[])})
 require(len(support.canonical(rows).encode())<=131072,'DELTA_REPORT_BOUND');return rows

def protected_checkpoints(conn,core,protected):
 ids={r['id'] for r in core['candidates'] if r['source_item_id'] in protected};checks=[];bulk=[]
 for row in conn.execute('SELECT candidate_id,attempts,next_attempt,lease_owner,lease_until,last_code FROM m365_bulk_extraction_checks ORDER BY candidate_id'):
  if row['candidate_id'] in ids:checks.append(dict(row))
 for row in conn.execute("SELECT drive_id,pending_id,item_id,status,reason,attempts,next_attempt,lease_owner,lease_until FROM m365_bulk_items WHERE kind='file' ORDER BY drive_id,pending_id,item_id"):
  if row['item_id'] in protected:bulk.append(dict(row))
 return {'sha256':support.digest({'checks':checks,'bulk':bulk}),'extraction_rows':len(checks),'bulk_rows':len(bulk)}

def bind_outside(member,prior,original,coverage,paused,held):
 sid=member['source_item_id'];critical=planning.critical(member)
 relation='baseline_previously_available' if prior else 'outside_baseline'
 if not prior and member['current_inventory_member']:relation='added_physical_identity'
 return {'source_id_sha256':hashlib.sha256(sid.encode()).hexdigest(),'relation':relation,'baseline_category':prior['category'] if prior else 'outside_baseline','baseline_physical_member':sid in original,'current_physical_member':member['current_inventory_member'],'current_category':member['category'],'availability_exception':member['availability_exception'],'exact_complete_text':member['exact_complete_text'],'paused':sid in paused,'held':sid in held,'candidate_count':len(member['candidate_versions']),'source_version_rights_sha256':support.digest(critical),'current_inventory_row_sha256':support.digest(member['current_source']) if member['current_source'] else None,'candidate_versions_sha256':support.digest(critical['candidate_versions']),'provenance_sha256':support.digest({'candidate':critical['candidate_source_provenance'],'bulk':critical['bulk_provenance']}),'holds_sha256':support.digest(critical['holds']),'search_coverage':[bool(v) for v in coverage],'next_approval':'separate_baseline_scope_and_remediation_approval','processing_authorized':False}

def validate_boundary(summary,pair):
 require(len(summary['outside_unresolved'])==2 and len({r['source_id_sha256'] for r in summary['outside_unresolved']})==2,'OUTSIDE_SCOPE_DRIFT')
 expected={'physical_files':23757,'represented_files':23767,'unresolved_files':8432,'approved_unresolved_sources':8430,'inventory_sha256':'25a11e7d0956a2178d6033a3687e1a1a185873d7e5ade9550a60dae09b40b8ab','source_differences_sha256':'27aba8f05af10eae2f5b50ac6b930be179c9fe552f8c245751aecf35f6a91664','preserved_receipts_sha256':'21c4bcd816686d4178c32bf224228c13639aa56a8225cf0cd3219af6fab0cd1f','critical_drift_sources':0,'missing_representation':0,'current_paused_sources':733,'current_hold_sources':93,'paused_membership_changed':0,'hold_membership_changed':0}
 require(all(summary[k]==v for k,v in expected.items()) and summary['protected_checkpoints']['sha256']=='214f2756ca0bc179bfaed880480113b5cd31cecd9de0e803e03013bcd4872ac7','OUTSIDE_PRIOR_BOUNDARY_DRIFT')
 require(pair['outside_approved_sources_changed']==pair['represented_added']==pair['represented_removed']==0,'OUTSIDE_READBACK_DRIFT')


def capture(conn,inventory,drive_id,*,expected_inventory=BASELINE_INVENTORY_SHA,proof_args=None):
 base,parent,remh,review,twenty=input_proof(conn,**(proof_args or {}));targets=saved_targets(conn)
 original,authority,selected=reconstruct_baseline(conn,base,expected_inventory)
 del parent,remh,review
 core=baseline.core_snapshot(conn);evidence=support.read_evidence(conn);represented=set(evidence['represented']);require(represented==set(core['represented']),'MEMBERSHIP_INVALID')
 require(all(r['source_drive_id']==drive_id for r in (*core['candidates'],*core['holds'])) and all(r['drive_id']==drive_id for r in core['bulk']),'DRIVE_SCOPE_DRIFT')
 lookup=rem.indexes(evidence,core);signature=baseline.membership_signature(evidence);matrix=search_matrix(conn);require(set(matrix)==represented,'COVERAGE_INVALID')
 available={s for s,v in signature.items() if v[0]=='legacy_available'};exact={s for s,v in signature.items() if v[2]};strict={r['source_item_id'] for r in evidence['candidates'] if r['extraction_status']=='Complete' and r['strict_text']};require(exact==strict and not exact-available,'AVAILABILITY_DRIFT')
 outside=[];current={};critical_drift={};counts={k:0 for k in support.CATEGORIES};paused={r['source_item_id'] for r in evidence['candidates'] if r['extraction_status']=='Retry Paused' or str(r.get('automatic_retry_paused','')).casefold() in ('true','1')};held={r['source_item_id'] for r in core['holds']};fields={}
 for sid in sorted(represented|set(selected)):
  category,exception,is_exact=signature.get(sid,('no_candidate',False,False));member=current_member(sid,category,exception,is_exact,lookup,inventory,drive_id);value=planning.critical(member);current[sid]=support.digest(value)
  if sid in represented and category!='legacy_available':
   counts[category]+=1
   if sid not in authority or authority[sid]['category']=='legacy_available':outside.append(bind_outside(member,authority.get(sid),original,matrix[sid],paused,held))
  if category=='retry_paused':paused.add(sid)
  if sid in selected and current[sid]!=selected[sid]['sha256']:
   changed=sorted(k for k,v in value.items() if support.digest(v)!=selected[sid]['fields'][k]);critical_drift[sid]=changed
   for k in changed:fields[k]=fields.get(k,0)+1
 protected={s for s,v in authority.items() if v['paused'] or v['held']};checkpoints=protected_checkpoints(conn,core,protected)
 baseline_paused={s for s,v in authority.items() if v['paused']};baseline_held={s for s,v in authority.items() if v['held']}
 delta=source_deltas(original,inventory,authority,selected,critical_drift,represented)
 summary={'physical_files':len(inventory),'represented_files':len(represented),'unresolved_files':len(represented-available),'legacy_available':len(available),'exact_text':len(exact),'availability_exceptions':len(available-exact),'approved_unresolved_sources':base['unresolved_files'],'approved_availability_exceptions':base['availability_exceptions'],
  'outside_unresolved':outside,'outside_unresolved_sha256':support.digest(outside),'inventory_sha256':support.snapshot_digest(inventory),'baseline_inventory_sha256':support.snapshot_digest(original),'inventory_diff':support.inventory_diff(original,inventory),'source_differences':delta,'source_differences_sha256':support.digest(delta),'critical_drift_sources':len(critical_drift),'critical_field_source_counts_overlapping':fields,
  'current_unresolved_categories':counts,'baseline_paused_sources':len(baseline_paused),'current_paused_sources':len(paused),'baseline_hold_sources':len(baseline_held),'current_hold_sources':len(held),'paused_membership_changed':len(paused^baseline_paused),'hold_membership_changed':len(held^baseline_held),'missing_representation':len(set(inventory)-represented),
  'historical_failed_final_reconstructed_by_exact_hash':support.snapshot_digest(inventory)==FAILED_FINAL_SHA,'historical_failed_final_reconstruction_limit':'Exact failed-final source values were not retained. Current values reconstruct that snapshot only when the complete digest matches; otherwise differences describe current versus approved baseline only.',
  'queries':[{'label':label,'query_sha256':hashlib.sha256(query.encode()).hexdigest(),'considered_count':len(represented),'matched_count':sum(v[i] for v in matrix.values())} for i,(label,query) in enumerate(QUERIES)],'search_matrix_sha256':support.digest(matrix),'all_represented_sources_considered':True,'inventory_not_represented_considered_by_identity_reconciliation':True,
  'preserved_receipt_count':20,'preserved_receipts_sha256':twenty,'saved_target_counts':targets,'protected_checkpoints':checkpoints,
  'baseline_adopted':False,'new_receipts':0,'database_writes':0,'source_content_downloads':0,'proposal_preparation':False,'processing_authorized':False,'retry_resume_authorized':False,'hold_release_authorized':False,'at':datetime.now(timezone.utc).isoformat()}
 require(sum(counts.values())==len(represented-available),'PARTITION_INVALID')
 return {'summary':summary,'current':current,'selected':set(selected),'paused':paused,'held':held,'represented':represented}

def verify_pair(first,second):
 a,b=first['summary'],second['summary'];require(a['outside_unresolved']==b['outside_unresolved'],'OUTSIDE_SOURCE_DRIFT');require(a['preserved_receipts_sha256']==b['preserved_receipts_sha256'] and a['saved_target_counts']==b['saved_target_counts'],'PRESERVED_RECEIPT_OR_TARGET_DRIFT')
 require(a['protected_checkpoints']==b['protected_checkpoints'] and first['paused']==second['paused'] and first['held']==second['held'],'PROTECTED_PAUSE_HOLD_DRIFT')
 require(first['selected']==second['selected'],'APPROVED_SOURCE_MEMBERSHIP_DRIFT')
 changed={s for s in first['current'].keys()|second['current'].keys() if first['current'].get(s)!=second['current'].get(s)}
 require(not changed&first['selected'],'INDEPENDENT_APPROVED_SOURCE_DRIFT');require(len(changed)<=MAX_DELTA,'DATABASE_DRIFT_BOUND')
 return {'outside_approved_sources_changed':len(changed),'outside_approved_changed_source_hashes_sha256':support.digest(sorted(hashlib.sha256(s.encode()).hexdigest() for s in changed)),'represented_added':len(second['represented']-first['represented']),'represented_removed':len(first['represented']-second['represented']),'protected_checkpoints_unchanged':1,'paused_membership_unchanged':1,'held_membership_unchanged':1}

def verify_final_inventory(inventory,final):
 support.emit_diff(inventory,final,'RECON_FINAL');require(final==inventory,'FINAL_INVENTORY_DRIFT')

def emit(summary,pair):
 scalars={'PHYSICAL_FILES':summary['physical_files'],'REPRESENTED_FILES':summary['represented_files'],'UNRESOLVED_FILES':summary['unresolved_files'],'APPROVED_UNRESOLVED_SOURCES':summary['approved_unresolved_sources'],'AVAILABILITY_EXCEPTIONS':summary['availability_exceptions'],'INVENTORY_SHA256':summary['inventory_sha256'],'BASELINE_INVENTORY_SHA256':summary['baseline_inventory_sha256'],'SOURCE_DIFFERENCES':len(summary['source_differences']),'SOURCE_DIFFERENCES_SHA256':summary['source_differences_sha256'],'APPROVED_CRITICAL_DRIFT_SOURCES':summary['critical_drift_sources'],'MISSING_REPRESENTATION':summary['missing_representation'],'HISTORICAL_FAILED_FINAL_RECONSTRUCTED_BY_HASH':int(summary['historical_failed_final_reconstructed_by_exact_hash']),'PRESERVED_RECEIPTS':20,'PRESERVED_RECEIPTS_SHA256':summary['preserved_receipts_sha256'],'SAVED_TARGET_ROWS':sum(summary['saved_target_counts']),'BASELINE_PAUSED_SOURCES':summary['baseline_paused_sources'],'CURRENT_PAUSED_SOURCES':summary['current_paused_sources'],'BASELINE_HOLD_SOURCES':summary['baseline_hold_sources'],'CURRENT_HOLD_SOURCES':summary['current_hold_sources'],'PAUSED_MEMBERSHIP_CHANGED':summary['paused_membership_changed'],'HOLD_MEMBERSHIP_CHANGED':summary['hold_membership_changed'],'PROTECTED_CHECKPOINT_SHA256':summary['protected_checkpoints']['sha256'],'SEARCH_MATRIX_SHA256':summary['search_matrix_sha256'],'ALL_REPRESENTED_CONSIDERED':1,'DATABASE_WRITES':0,'NEW_RECEIPTS':0,'NEW_BASELINE_ADOPTED':0,'PROPOSAL_PREPARATION':0,'SOURCE_CONTENT_DOWNLOADS':0,'PREFLIGHT_EXECUTION':0,'PROCESSING_AUTHORIZED':0,'RETRY_RESUME':0,'HOLD_RELEASE':0,'FRESH_CONNECTION_VERIFIED':1,'COMPLETE':1}
 for k,v in scalars.items():print('INVENTORY_RECON_'+k+'='+str(v),flush=True)
 for prefix,values in (('BASELINE_DIFF',summary['inventory_diff']),('CURRENT_CATEGORY',summary['current_unresolved_categories']),('CRITICAL_FIELD',summary['critical_field_source_counts_overlapping']),('READBACK',pair)):
  for k,v in sorted(values.items()):print('INVENTORY_RECON_'+prefix+'_'+k.upper()+'='+str(v),flush=True)
 for row in summary['outside_unresolved']:print('OUTSIDE_COHORT_SOURCE='+support.canonical(row),flush=True)
 print('OUTSIDE_COHORT_COUNT='+str(len(summary['outside_unresolved'])),flush=True)
 print('OUTSIDE_COHORT_SHA256='+summary['outside_unresolved_sha256'],flush=True)
 print('OUTSIDE_COHORT_VERIFIED=1',flush=True)
 for row in summary['source_differences']:print('INVENTORY_RECON_SOURCE_DELTA='+support.canonical(row),flush=True)
 for query in summary['queries']:print('INVENTORY_RECON_QUERY_'+query['label'].upper()+'_MATCHED='+str(query['matched_count']),flush=True)

def main():
 from database import connect_database
 from salcapa_m365_intake import GovernedM365Config,GovernedM365Intake
 inner=intake=None
 try:
  require(os.getenv('SALUS_DB_BACKEND','').lower()=='postgres','BACKEND_REQUIRED');require(bool(re.fullmatch('[1-9][0-9]{5,19}',os.getenv('SALUS_POSTSEARCH_RUN_ID',''))) and bool(re.fullmatch('[0-9a-f]{64}',os.getenv('SALUS_POSTSEARCH_SCRIPT_SHA256',''))),'EXECUTION_BINDING')
  phase('initial_twenty_receipts_and_empty_outputs');inner=connect_database();conn=begin_read_only(inner);input_proof(conn);saved_targets(conn);inner.close();inner=None
  config=GovernedM365Config.from_environment();intake=GovernedM365Intake(config);phase('bounded_stable_inventory');inventory=support.establish_stable_inventory(intake,max_observations=3);require(len(inventory)>=23747,'BOUNDARY_BELOW_MINIMUM')
  phase('first_read_only_reconciliation');inner=connect_database();first=capture(begin_read_only(inner),inventory,config.drive_id);inner.close();inner=None;phase('final_complete_inventory');final=support.acquire_inventory(intake);verify_final_inventory(inventory,final);del final
  phase('independent_read_only_verification');inner=connect_database();second=capture(begin_read_only(inner),inventory,config.drive_id);pair=verify_pair(first,second);validate_boundary(second['summary'],pair);phase('verified_read_only_result');emit(second['summary'],pair)
 except Exception as exc:
  allowed={'OUTSIDE_SCOPE_DRIFT','OUTSIDE_SOURCE_DRIFT','OUTSIDE_PRIOR_BOUNDARY_DRIFT','OUTSIDE_READBACK_DRIFT','QUERY_DENIED','MEMORY_BUDGET','SAVED_OUTPUT_REQUIRES_RECONCILIATION','BASELINE_INVENTORY_DRIFT','BASELINE_MEMBER_DRIFT','BASELINE_SCOPE_DRIFT','DELTA_REPORT_BOUND','MEMBERSHIP_INVALID','DRIVE_SCOPE_DRIFT','COVERAGE_INVALID','AVAILABILITY_DRIFT','PARTITION_INVALID','PRESERVED_RECEIPT_OR_TARGET_DRIFT','PROTECTED_PAUSE_HOLD_DRIFT','APPROVED_SOURCE_MEMBERSHIP_DRIFT','INDEPENDENT_APPROVED_SOURCE_DRIFT','DATABASE_DRIFT_BOUND','BACKEND_REQUIRED','EXECUTION_BINDING','BOUNDARY_BELOW_MINIMUM','FINAL_INVENTORY_DRIFT','PRESERVED_RECEIPT_DRIFT','REVIEW_HEADER_DRIFT','REVIEW_SCOPE_DRIFT','REVIEW_AUTHORITY_DRIFT','REVIEW_BATCH_DRIFT','REVIEW_EVENT_DRIFT','REMEDIATION_HEADER_DRIFT','REMEDIATION_BATCH_DRIFT','BASELINE_HEADER_DRIFT','PARENT_HEADER_DRIFT','PARENT_BATCH_DRIFT'}
  code=exc.code if isinstance(exc,support.CensusFailure) else str(exc) if str(exc) in allowed else 'INPUT_PROOF_OR_READ_FAILURE';print('INVENTORY_RECON_FAILURE_CODE='+code,flush=True);print('INVENTORY_RECON_FAILURE_STAGE='+STAGE,flush=True);state=getattr(exc,'sqlstate','');print('INVENTORY_RECON_FAILURE_SQLSTATE='+(state if isinstance(state,str) and re.fullmatch('[A-Z0-9]{5}',state) else 'UNAVAILABLE'),flush=True);print('INVENTORY_RECON_DATABASE_WRITES=0',flush=True);raise SystemExit(1) from None
 finally:
  if inner is not None:inner.close()
  if intake is not None:intake.client.close();intake.credential.close()

if __name__=='__main__':main()
