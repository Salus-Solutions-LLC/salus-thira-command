"""Audit every saved remediation proposal; propose bounded checks, execute none."""
import copy
import gc
import hashlib
import json
import os
import re
import time
import uuid
from datetime import datetime,timezone
try:
    import salus_remediation_support as rem
except ImportError:
    from tools import live_knowledge_remediation_proposals as rem
planning=rem.planning
baseline=rem.baseline
support=rem.support
require=rem.require
KEY='salus-remediation-review-preflight-proposals-20261116'
ACTOR='System Administrator - task consideration '+KEY+' / '
INPUT_SHA='d68b22cc0eca5655dee804dd3f8e2d511c4cded9d0643d1a2ab2cb829e1a2c85'
STATE='Proposed - Awaiting Bounded Preflight Approval'
TABLES=('m365_knowledge_preflight_proposals','m365_knowledge_remediation_reviews','m365_knowledge_preflight_batches','m365_knowledge_preflight_events')
DDL=('CREATE TABLE IF NOT EXISTS '+TABLES[0]+' (operation_key TEXT PRIMARY KEY,state TEXT NOT NULL,input_manifest_sha256 TEXT NOT NULL,manifest_sha256 TEXT NOT NULL,payload_json TEXT NOT NULL,created_at TEXT NOT NULL)',
     'CREATE TABLE IF NOT EXISTS '+TABLES[1]+' (operation_key TEXT NOT NULL,batch_key TEXT NOT NULL,source_count INTEGER NOT NULL,payload_sha256 TEXT NOT NULL,payload_json TEXT NOT NULL,PRIMARY KEY(operation_key,batch_key))',
     'CREATE TABLE IF NOT EXISTS '+TABLES[2]+' (operation_key TEXT NOT NULL,preflight_key TEXT NOT NULL,source_count INTEGER NOT NULL,payload_sha256 TEXT NOT NULL,payload_json TEXT NOT NULL,PRIMARY KEY(operation_key,preflight_key))',
     'CREATE TABLE IF NOT EXISTS '+TABLES[3]+' (operation_key TEXT PRIMARY KEY,payload_json TEXT NOT NULL,created_at TEXT NOT NULL)')
QUERIES=(('proposal_review','preflight proposal source version remediation review provenance candidate archive integrity'),
         ('bounds_and_checkpoints','bounded budget size limit lease checkpoint due attempt retry paused resource'),
         ('rights_and_contrary','rights permission hold restricted active encryption conflicting unavailable unsafe contrary'),
         ('approval_and_verification','approval authorization qualification review hash audit receipt verification rollback cleanup'))
BOUNDS={'maximum_preflight_batches':2,'maximum_sources_per_preflight':5,'maximum_selected_sources':10,
        'maximum_bytes_per_stream':10485760,'maximum_streams_per_source':2,'maximum_total_bytes':209715200,
        'maximum_seconds_per_preflight':300,'maximum_total_seconds':600,'maximum_automatic_retries':0,
        'maximum_paid_external_api_calls':0,'maximum_persistent_source_content_bytes':0}
GATES=['Approve this exact manifest and selected batch/source/candidate/version IDs; no blanket approval of 200 batches',
       'Source-owner/rightsholder authority and purpose/privacy review, preserving all current holds and pauses',
       'Validate the exact read-only preflight implementation, isolation, byte/time/cost bounds and cleanup',
       'Fresh source/archive identity, etag/size/hash, rights and due/lease/checkpoint verification; stop on drift, active lease or budget excess',
       'Separate exact-version approval to execute bounded preflight; no conversion, extraction, enqueue, retry, hold release or status update',
       'Independent result and cleanup proof, followed by separate remedy/processor qualification and any recovery authorization']
EXCLUDED={'owner_hold_review','authorized_readable_source','safe_derivative_review','all_version_reconciliation','missing_candidate_provenance','unknown_condition_review'}
STAGE='not_started'
COMMIT_ATTEMPTED=COMMIT_ACKNOWLEDGED=0


def phase(value):
    global STAGE
    STAGE=value;gc.collect();print('PREFLIGHT_PHASE='+value,flush=True)
    try:import resource
    except ImportError:return
    peak=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    print('PREFLIGHT_PEAK_RSS_KIB='+str(peak),flush=True);require(peak<786432,'MEMORY_BUDGET')


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


def input_proof(conn,*,expected_input=INPUT_SHA,expected_parent=rem.PARENT_SHA,expected_baseline=planning.MANIFEST,expected_batches=200,expected_sources=8430):
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


def target_empty(conn):
    counts=[]
    for table in TABLES:
        exists=bool(conn.execute('SELECT to_regclass(?)',(table,)).fetchone()[0]) if conn.backend=='postgres' else bool(conn.execute("SELECT name FROM sqlite_master WHERE type='table' AND name=?",(table,)).fetchone())
        counts.append(conn.execute('SELECT COUNT(*) FROM '+table+' WHERE operation_key=?',(KEY,)).fetchone()[0] if exists else 0)
    counts.append(conn.execute('SELECT COUNT(*) FROM '+support.RECEIPT_TABLE+' WHERE actor LIKE ?',(ACTOR+'%',)).fetchone()[0])
    for label,n in zip(('HEADERS','REVIEWS','PREFLIGHTS','EVENTS','TASK_RECEIPTS'),counts):print('PREFLIGHT_PRESTATE_'+label+'='+str(n),flush=True)
    require(not any(counts),'TARGET_NOT_EMPTY')


def semantic_proposal(value):
    value=copy.deepcopy(value)
    for source in value['source_bindings']:
        source.pop('current_bulk_checkpoints',None);source.pop('current_candidate_checkpoints',None)
    return value


def eligibility(proposal,source,current):
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


def review_all(conn,base,parent,header,evidence,core,inventory,*,expected_sources=8430):
    regenerated,scope=rem.build_proposals(conn,base,parent,evidence,core,inventory,expected_sources=expected_sources)
    lookup=rem.indexes(evidence,core);reviews=[];preflights=[];seen=set();histogram={};selected=set()
    for expected,binding in zip(regenerated,header['proposal_hashes']):
        cursor=conn.execute('SELECT * FROM '+rem.TABLES[1]+' WHERE operation_key=? AND batch_key=?',(rem.KEY,binding['batch_key']))
        try:
            row=cursor.fetchone();require(row is not None,'REMEDIATION_BATCH_DRIFT');saved=planning.MEMBER_DECODER.decode(row['payload_json'])
        finally:getattr(cursor,'cursor',cursor).close()
        require(hashlib.sha256(row['payload_json'].encode()).hexdigest()==row['payload_sha256']==binding['sha256'],'REMEDIATION_BATCH_DRIFT')
        require(semantic_proposal(saved)==expected and saved['source_count']==row['source_count'],'REMEDIATION_SOURCE_BINDING_DRIFT')
        audit=[];eligible=[]
        for source in saved['source_bindings']:
            sid=source['source_item_id'];require(sid not in seen,'DUPLICATE_MEMBERSHIP');seen.add(sid)
            current={'candidate_versions':lookup['candidates'].get(sid,[])}
            reason=eligibility(saved,source,current);histogram[reason]=histogram.get(reason,0)+1
            audit.append({'source_item_id':sid,'proposal_source_sha256':support.digest(source),'current_critical_sha256':source['current_critical_sha256'],
                'candidate_versions':source['candidate_versions'],'method_codes':source['method_codes'],'preflight_disposition':reason,
                'review_result':'Metadata consistency and safety-gate audit complete; original content, rights, feasibility and human qualification pending',
                'content_review_completed':False,'human_qualification_completed':False,'remedy_approved':False,'preflight_execution_authorized':False})
            if reason=='conditional_metadata_candidate_not_authorized':
                live=current['candidate_versions'][0]
                eligible.append({'source_item_id':sid,'input_proposal_source_sha256':support.digest(source),'current_critical_sha256':source['current_critical_sha256'],
                    'candidate_versions':source['candidate_versions'],'archive_metadata':{k:live.get(k) for k in ('id','source_sha256','source_archive_item_id','source_archive_etag','source_size')},
                    'source_rights_qualified':False,'archive_bytes_verified':False,'execution_authorized':False})
        chosen=[]
        if eligible and len(preflights)<BOUNDS['maximum_preflight_batches']:
            chosen=sorted(eligible,key=lambda r:r['source_item_id'])[:BOUNDS['maximum_sources_per_preflight']]
            selected.update(r['source_item_id'] for r in chosen)
            preflights.append({'preflight_key':'preflight-'+str(len(preflights)+1).zfill(2),'parent_batch_key':saved['batch_key'],
                'input_proposal_sha256':binding['sha256'],'source_count':len(chosen),'source_bindings':chosen,'state':STATE,'bounds':BOUNDS,
                'objective':'Propose read-only identity/rights and original/archive byte-integrity verification; do not execute preflight now',
                'stop_conditions':['Any identity/version/hash/rights/hold or checkpoint/lease drift','Any missing owner authority or active lease','Any byte/time/cost bound exceeded','Unavailable archive, mismatch, redirection/authorization uncertainty or protected disclosure risk'],
                'approval_steps':GATES,'source_content_downloads_authorized':False,'preflight_execution_authorized':False,
                'processing_authorized':False,'retry_resume_authorized':False,'hold_release_authorized':False})
        chosen_ids={r['source_item_id'] for r in chosen}
        reviews.append({'batch_key':saved['batch_key'],'input_proposal_sha256':binding['sha256'],'category':saved['category'],'source_count':len(audit),
            'review_state':'Metadata Review Complete - Human Qualification Pending','sources':audit,
            'selected_preflight_sources':sorted(chosen_ids),'deferred_sources':sorted(r['source_item_id'] for r in audit if r['source_item_id'] not in chosen_ids),
            'processing_authorized':False,'retry_resume_authorized':False,'hold_release_authorized':False})
    require(len(seen)==expected_sources and len(reviews)==len(header['proposal_hashes']) and len(selected)<=10,'REVIEW_SCOPE_DRIFT')
    del regenerated,lookup
    return reviews,preflights,scope,histogram


def search_matrix(conn, *, family='ALL', source_ids=None):
    # Same tokenization, union, concatenation, lower()/LIKE OR semantics as
    # the deployed consider() service. Return one boolean per source/query;
    # raw classification text, excerpts, names and errors never leave this SQL.
    require(family in ('ALL','C','B','H'), 'QUERY_DENIED')
    if source_ids is not None and not source_ids:return {}
    parameters, flags = [], []
    for index, (_,query) in enumerate(QUERIES):
        terms = list(dict.fromkeys(re.findall(r'[a-z0-9][a-z0-9._-]{1,79}',query.casefold())))[:20]
        clause = ' OR '.join('search_text LIKE ?' for _ in terms)
        parameters.extend('%'+term+'%' for term in terms)
        flags.append('MAX(CASE WHEN '+clause+' THEN 1 ELSE 0 END) m'+str(index))
    materialized = 'MATERIALIZED ' if conn.backend=='postgres' else ''
    pieces = {
      'C':"SELECT c.source_item_id,lower(c.source_name || ' ' || c.source_relative_path || ' ' || c.classification_json) search_text FROM m365_knowledge_candidates c JOIN represented r ON r.source_item_id=c.source_item_id",
      'B':"SELECT b.item_id source_item_id,lower(b.name || ' ' || b.metadata_json || ' ' || b.status || ' ' || b.reason) search_text FROM m365_bulk_items b JOIN represented r ON r.source_item_id=b.item_id WHERE b.kind='file'",
      'H':"SELECT h.source_item_id,lower(h.source_name || ' ' || h.source_relative_path || ' ' || h.source_area || ' ' || h.hold_reason) search_text FROM m365_knowledge_holds h JOIN represented r ON r.source_item_id=h.source_item_id WHERE h.status='Governed Hold'"}
    source_parameters=tuple(sorted(source_ids)) if source_ids is not None else ()
    scoped=' WHERE source_item_id IN ('+','.join('?' for _ in source_parameters)+')' if source_ids is not None else ''
    query = """WITH universe AS (
      SELECT source_item_id FROM m365_knowledge_candidates
      UNION SELECT source_item_id FROM m365_knowledge_holds WHERE status='Governed Hold'
      UNION SELECT item_id FROM m365_bulk_items WHERE kind='file' AND status<>'Removed'
    ), represented AS (SELECT source_item_id FROM universe"""+scoped+'), searchable AS '+materialized+'('+' UNION ALL '.join(pieces[k] for k in ('C','B','H') if family in ('ALL',k))+'), matched AS (SELECT source_item_id,' + ','.join(flags) + ' FROM searchable GROUP BY source_item_id) SELECT r.source_item_id,' + ','.join('COALESCE(m.m'+str(i)+',0) m'+str(i) for i in range(len(QUERIES))) + ' FROM represented r LEFT JOIN matched m ON m.source_item_id=r.source_item_id ORDER BY r.source_item_id'
    result = {}
    for r in conn.execute(query,source_parameters+tuple(parameters)).fetchall():
        source = r['source_item_id']
        require(source not in result, 'DUPLICATE_MEMBERSHIP')
        result[source] = [int(r['m'+str(i)]) for i in range(len(QUERIES))]
    require(len(result)<=100000 and all(set(v)<={0,1} for v in result.values()), 'COVERAGE_INVALID')
    return result


def observe(evidence,core,inventory,matrix,drive_id):
    represented=set(evidence['represented']);require(set(inventory)<=represented==set(matrix)==set(core['represented']),'MEMBERSHIP_INVALID')
    require(all(r['source_drive_id']==drive_id for r in (*core['candidates'],*core['holds'])) and all(r['drive_id']==drive_id for r in core['bulk']),'DRIVE_SCOPE_DRIFT')
    signature=baseline.membership_signature(evidence);available={s for s,v in signature.items() if v[0]=='legacy_available'}
    exact={s for s,v in signature.items() if v[2]};strict={r['source_item_id'] for r in evidence['candidates'] if r['extraction_status']=='Complete' and r['strict_text']}
    require(exact==strict and not exact-available,'AVAILABILITY_DRIFT')
    now=datetime.now(timezone.utc).isoformat();receipts=[]
    for i,(label,query) in enumerate(QUERIES):receipts.append({'receipt_id':str(uuid.uuid4()),'query_sha256':hashlib.sha256(query.strip().encode()).hexdigest(),
        'boundary_count':len(inventory),'considered_count':len(represented),'matched_count':sum(v[i] for v in matrix.values()),
        'content_available_count':len(available),'metadata_only_count':len(represented-available),'governed_hold_count':len({r['source_item_id'] for r in core['holds']}),
        'actor':ACTOR+label,'created_at':now})
    return {'created_at':now,'physical_files':len(inventory),'represented_files':len(represented),'legacy_available':len(available),'exact_complete_text':len(exact),
        'unresolved_files':len(represented-available),'queries':[{'label':l,'query':q} for l,q in QUERIES],'receipts':receipts,
        'inventory_sha256':support.snapshot_digest(inventory),'core_sha256':support.digest(core),'search_matrix_sha256':support.digest(matrix),
        'coverage_encoding':{'all_sources_considered_by_all_queries':True,'query_bit_order':[l for l,_ in QUERIES],'zero_mask_means_no_matches':True},
        'per_source_coverage':[[s,sum(1<<i for i,flag in enumerate(matrix[s]) if flag)] for s in sorted(matrix)]}


def current_checkpoints(conn,preflights):
    rem.current_schedules(conn,preflights)


def event_for(header):
    return {'manifest_sha256':support.digest(header),'state':STATE,'input_manifest_sha256':header['input_manifest_sha256'],
        'reviewed_batches':header['reviewed_batches'],'preflight_proposals':header['preflight_proposal_count'],'preflight_execution_authorized':False,'processing_authorized':False}


def validate_scope(reviews,preflights,expected_batches,expected_sources):
    require(len(reviews)==expected_batches and len({r['batch_key'] for r in reviews})==expected_batches,'REVIEW_SCOPE_DRIFT')
    sources={};batches={r['batch_key']:r for r in reviews};selected=set();by_batch={}
    for review in reviews:
        require(review['source_count']==len(review['sources']) and all(review[k] is False for k in ('processing_authorized','retry_resume_authorized','hold_release_authorized')),'REVIEW_SCOPE_DRIFT')
        for source in review['sources']:
            sid=source['source_item_id'];require(sid not in sources,'REVIEW_SCOPE_DRIFT');sources[sid]=(review,source)
    require(len(sources)==expected_sources and len(preflights)<=2 and len({p['preflight_key'] for p in preflights})==len(preflights),'PREFLIGHT_BOUND_DRIFT')
    for proposal in preflights:
        batch=batches.get(proposal['parent_batch_key']);require(batch is not None and batch['category']=='automatic_retry' and proposal['input_proposal_sha256']==batch['input_proposal_sha256'],'PREFLIGHT_SCOPE_DRIFT')
        require(proposal['bounds']==BOUNDS and proposal['approval_steps']==GATES and proposal['state']==STATE and 0<proposal['source_count']==len(proposal['source_bindings'])<=5,'PREFLIGHT_BOUND_DRIFT')
        require(all(proposal[k] is False for k in ('source_content_downloads_authorized','preflight_execution_authorized','processing_authorized','retry_resume_authorized','hold_release_authorized')),'PREFLIGHT_AUTHORITY_DRIFT')
        for source in proposal['source_bindings']:
            sid=source['source_item_id'];require(sid in sources and sid not in selected,'PREFLIGHT_SCOPE_DRIFT');review,audit=sources[sid]
            require(review['batch_key']==batch['batch_key'] and audit['preflight_disposition']=='conditional_metadata_candidate_not_authorized' and audit['proposal_source_sha256']==source['input_proposal_source_sha256'] and audit['candidate_versions']==source['candidate_versions'] and audit['current_critical_sha256']==source['current_critical_sha256'],'PREFLIGHT_SCOPE_DRIFT')
            require(all(source[k] is False for k in ('source_rights_qualified','archive_bytes_verified','execution_authorized')),'PREFLIGHT_AUTHORITY_DRIFT')
            selected.add(sid);by_batch.setdefault(batch['batch_key'],set()).add(sid)
    require(len(selected)<=10,'PREFLIGHT_BOUND_DRIFT')
    for review in reviews:
        expected=by_batch.get(review['batch_key'],set());all_ids={r['source_item_id'] for r in review['sources']}
        require(review['selected_preflight_sources']==sorted(expected) and review['deferred_sources']==sorted(all_ids-expected),'PREFLIGHT_SCOPE_DRIFT')
    return selected


def verify_output(conn,header,reviews,preflights):
    validate_scope(reviews,preflights,header['reviewed_batches'],header['reviewed_sources'])
    row=conn.execute('SELECT * FROM '+TABLES[0]+' WHERE operation_key=?',(KEY,)).fetchone()
    require(row is not None and row['payload_json']==support.canonical(header) and row['manifest_sha256']==support.digest(header) and row['state']==STATE and row['input_manifest_sha256']==header['input_manifest_sha256'] and row['created_at']==header['created_at'],'OUTPUT_HEADER_DRIFT')
    for table,key,values in ((TABLES[1],'batch_key',reviews),(TABLES[2],'preflight_key',preflights)):
        rows=conn.execute('SELECT * FROM '+table+' WHERE operation_key=? ORDER BY '+key,(KEY,)).fetchall();require(len(rows)==len(values),'OUTPUT_BATCH_DRIFT')
        for actual,expected in zip(rows,values):require(actual[key]==expected[key] and actual['source_count']==expected['source_count'] and actual['payload_sha256']==support.digest(expected) and actual['payload_json']==support.canonical(expected),'OUTPUT_BATCH_DRIFT')
    events=conn.execute('SELECT * FROM '+TABLES[3]+' WHERE operation_key=?',(KEY,)).fetchall()
    require(len(events)==1 and events[0]['payload_json']==support.canonical(event_for(header)) and events[0]['created_at']==header['created_at'],'OUTPUT_EVENT_DRIFT')
    receipts=[dict(r) for r in conn.execute('SELECT * FROM '+support.RECEIPT_TABLE+' WHERE actor LIKE ? ORDER BY actor',(ACTOR+'%',)).fetchall()]
    require(receipts==sorted(header['current_consideration']['receipts'],key=lambda r:r['actor']),'TASK_RECEIPT_DRIFT')
    return support.digest(header)


def prepare(inner,context,*,expected_input=INPUT_SHA,expected_parent=rem.PARENT_SHA,expected_baseline=planning.MANIFEST,expected_batches=200,expected_sources=8430,fail_after_reviews=False,clock=time.monotonic):
    global COMMIT_ATTEMPTED,COMMIT_ACKNOWLEDGED
    COMMIT_ATTEMPTED=COMMIT_ACKNOWLEDGED=0;started=clock();conn=Connection(inner);conn.clock=clock;conn.deadline=started+60
    proof_args=dict(expected_input=expected_input,expected_parent=expected_parent,expected_baseline=expected_baseline,expected_batches=expected_batches,expected_sources=expected_sources)
    try:
        phase('locked_sixteen_receipts_and_review_verification')
        if conn.backend=='postgres':
            inner.execute("SET LOCAL lock_timeout='2s'");inner.execute("SET LOCAL statement_timeout='30s'")
            require(inner.execute('SELECT pg_try_advisory_xact_lock(674160041245)').fetchone()[0],'PLANNING_BUSY')
            inner.execute('LOCK TABLE '+','.join((*support.SOURCE_TABLES,support.RECEIPT_TABLE,*baseline.TABLES,*support.PLAN_TABLES,*rem.TABLES))+' IN SHARE MODE NOWAIT')
        else:inner.execute('BEGIN IMMEDIATE')
        base,parent,source,sixteen=input_proof(conn,**proof_args);del base,parent,source;target_empty(conn)
        current=baseline.core_snapshot(conn);before=context.pop('preview_core');delta=baseline.core_delta(before,current);del before
        require(current['represented']==context['evidence']['represented'],'SOURCE_OR_SEARCH_INPUT_DRIFT')
        for family,allowed in (('candidates',{'classification_sha256','status','decision','reviewed_at','reviewed_by','review_rationale','target_folder'}),('holds',{'reviewed_at'}),('bulk',{'status','reason','metadata_sha256'})):
            require(delta[family]['added']==delta[family]['removed']==0 and set(delta[family]['fields'])<=allowed,'SOURCE_OR_SEARCH_INPUT_DRIFT')
        for change in delta['candidates']['rows']:
            if change['source_item_id'] in context['scope']:require(set(change['fields'])<={'reviewed_at'},'SOURCE_RIGHTS_VERSION_DRIFT')
        changed={r['source_item_id'] for r in delta['candidates']['rows']};require(len(changed)<=100,'REFRESH_SCOPE_EXCEEDED')
        baseline.emit_delta(delta,'PREFLIGHT_DRIFT')
        families=context.pop('families');old=context.pop('evidence')
        evidence={'represented':current['represented'],'holds':current['holds'],'candidates':sorted([r for r in old['candidates'] if r['source_item_id'] not in changed]+baseline.candidate_subset(conn,changed),key=lambda r:r['id'])};del old
        if changed:families['C'].update(search_matrix(conn,family='C',source_ids=changed))
        for family in ('B','H'):families[family]=search_matrix(conn,family=family)
        observation=observe(evidence,current,context['inventory'],baseline.combine_families(families),context['drive_id'])
        reviewed={r['source_item_id'] for batch in context['reviews'] for r in batch['sources']}
        signature=baseline.membership_signature(evidence)
        observation['unresolved_outside_review_scope']=sorted(s for s,v in signature.items() if v[0]!='legacy_available' and s not in reviewed)
        observation['unresolved_outside_review_scope_count']=len(observation['unresolved_outside_review_scope'])
        observation['outside_scope_disposition']='Considered in current corpus; no review or preflight proposal authority outside the immutable input batches'
        del evidence,families,signature,reviewed
        reviews=context['reviews'];preflights=context['preflights'];current_checkpoints(conn,preflights)
        selected=validate_scope(reviews,preflights,expected_batches,expected_sources)
        header={'operation_key':KEY,'state':STATE,'created_at':observation['created_at'],'input_operation_key':rem.KEY,'input_manifest_sha256':expected_input,
            'parent_manifest_sha256':expected_parent,'approved_baseline_sha256':expected_baseline,'preserved_receipt_count':16,'preserved_receipts_sha256':sixteen,
            'reviewed_batches':len(reviews),'reviewed_sources':expected_sources,'preflight_proposal_count':len(preflights),'selected_sources':len(selected),
            'deferred_source_count':expected_sources-len(selected),'selection_policy':'First two sorted automatic-retry parent batches with qualifying single current archived-version metadata; first five sorted sources each; no implied rights or execution authority',
            'review_dispositions':context['histogram'],'no_eligible_preflight_sources':not preflights,'bounds':BOUNDS,'approval_steps':GATES,
            'review_hashes':[{'batch_key':r['batch_key'],'sha256':support.digest(r)} for r in reviews],
            'preflight_hashes':[{'preflight_key':p['preflight_key'],'sha256':support.digest(p)} for p in preflights],
            'current_consideration':observation,'paused_retries_preserved':True,'governed_holds_preserved':True,
            'preflight_execution_authorized':False,'source_content_downloads_authorized':False,'processing_authorized':False,'retry_resume_authorized':False,'hold_release_authorized':False,
            'source_record_writes':0,'remediation_input_writes':0,'parent_plan_writes':0,'baseline_writes':0,'human_qualification_completed':False,'archive_bytes_verified':False,
            'execution_run_id':os.getenv('SALUS_POSTSEARCH_RUN_ID','fixture'),'script_sha256':os.getenv('SALUS_POSTSEARCH_SCRIPT_SHA256','fixture'),
            'request':{'thread_id':'01a1dccc-3c40-7c60-b6eb-f9836bd1332e','text':'Review the 200 remediation proposals through the governed process and prepare bounded preflight proposals for approval. Preserve all 16 receipts, paused retries and holds, verify results and cleanup, and update the handoff with next steps.'},
            'limits':'Metadata/source-version/safety-gate review only; no source-byte inspection, rights qualification, expert feasibility judgment or universal content/capture/Compass-proof completion',
            'chat_export_backfill_complete':False,'repository_source_copy_in_library':False}
        require(len(support.canonical(header).encode())+sum(len(support.canonical(r).encode()) for r in reviews+preflights)<=24*1024*1024,'OUTPUT_RESOURCE_BOUND')
        phase('atomic_reviews_and_preflight_proposals');conn.writes_enabled=True
        for sql in DDL:conn.execute(sql)
        for table,key,values in ((TABLES[1],'batch_key',reviews),(TABLES[2],'preflight_key',preflights)):
            for value in values:conn.execute('INSERT INTO '+table+' VALUES(?,?,?,?,?)',(KEY,value[key],value['source_count'],support.digest(value),support.canonical(value)))
        if fail_after_reviews:raise ValueError('INJECTED_ROLLBACK')
        for receipt in observation['receipts']:conn.execute('INSERT INTO '+support.RECEIPT_TABLE+' VALUES('+','.join('?' for _ in receipt)+')',tuple(receipt.values()))
        checksum=support.digest(header)
        conn.execute('INSERT INTO '+TABLES[0]+' VALUES(?,?,?,?,?,?)',(KEY,STATE,expected_input,checksum,support.canonical(header),header['created_at']))
        conn.execute('INSERT INTO '+TABLES[3]+' VALUES(?,?,?)',(KEY,support.canonical(event_for(header)),header['created_at']))
        verify_output(conn,header,reviews,preflights)
        require(input_proof(conn,**proof_args)[3]==sixteen,'PRESERVED_RECEIPT_DRIFT')
        require(clock()-started<60,'TRANSACTION_BUDGET');COMMIT_ATTEMPTED=1;inner.commit();COMMIT_ACKNOWLEDGED=1
        print('PREFLIGHT_COMMIT_WINDOW_MS='+str(int((clock()-started)*1000)),flush=True)
        return header,reviews,preflights,current
    except Exception:inner.rollback();raise
    finally:conn.writes_enabled=False;conn.deadline=None


def main():
    from database import connect_database
    from salcapa_m365_intake import GovernedM365Config,GovernedM365Intake
    inner=intake=None
    try:
        require(os.getenv('SALUS_DB_BACKEND','').lower()=='postgres','BACKEND_REQUIRED')
        require(bool(re.fullmatch('[1-9][0-9]{5,19}',os.getenv('SALUS_POSTSEARCH_RUN_ID',''))) and bool(re.fullmatch('[0-9a-f]{64}',os.getenv('SALUS_POSTSEARCH_SCRIPT_SHA256',''))),'EXECUTION_BINDING')
        phase('immutable_input_and_sixteen_receipts');inner=connect_database();conn=baseline.begin_read_only(inner);input_proof(conn);target_empty(conn);inner.close();inner=None
        config=GovernedM365Config.from_environment();intake=GovernedM365Intake(config)
        phase('stable_physical_inventory');inventory=support.establish_stable_inventory(intake);require(len(inventory)>=23747,'BOUNDARY_BELOW_MINIMUM')
        phase('full_corpus_consideration_and_all_proposal_review');inner=connect_database();conn=baseline.begin_read_only(inner)
        base,parent,source,_=input_proof(conn);support.verify_membership(conn,inventory)
        core=baseline.core_snapshot(conn);evidence=support.read_evidence(conn);families={f:search_matrix(conn,family=f) for f in ('C','B','H')}
        reviews,preflights,scope,histogram=review_all(conn,base,parent,source,evidence,core,inventory)
        observe(evidence,core,inventory,baseline.combine_families(families),config.drive_id)
        inner.close();inner=None;del base,parent,source
        require(support.acquire_inventory(intake)==inventory,'SOURCE_INVENTORY_CHANGED')
        context={'preview_core':core,'evidence':evidence,'families':families,'inventory':inventory,'drive_id':config.drive_id,'reviews':reviews,'preflights':preflights,'scope':scope,'histogram':histogram}
        del core,evidence,families
        inner=connect_database();header,reviews,preflights,committed=prepare(inner,context);inner.close();inner=None
        phase('independent_durable_readback');inner=connect_database();conn=baseline.begin_read_only(inner)
        require(input_proof(conn)[3]==header['preserved_receipts_sha256'],'PRESERVED_RECEIPT_DRIFT');checksum=verify_output(conn,header,reviews,preflights)
        after=baseline.core_snapshot(conn);delta=baseline.core_delta(committed,after);baseline.emit_delta(delta,'PREFLIGHT_POSTCOMMIT_DRIFT')
        require(after['represented']==committed['represented'],'INDEPENDENT_SOURCE_DRIFT')
        for family,allowed in (('candidates',{'reviewed_at'}),('holds',{'reviewed_at'}),('bulk',{'status','reason','metadata_sha256'})):
            require(delta[family]['added']==delta[family]['removed']==0 and set(delta[family]['fields'])<=allowed,'INDEPENDENT_SOURCE_DRIFT')
        values={'MANIFEST_SHA256':checksum,'INPUT_MANIFEST_SHA256':INPUT_SHA,'REVIEWED_BATCHES':200,'REVIEWED_SOURCES':8430,'PREFLIGHT_PROPOSALS':len(preflights),
            'SELECTED_SOURCES':header['selected_sources'],'PRESERVED_RECEIPTS':16,'NEW_RECEIPTS':4,'SOURCE_RECORD_WRITES':0,'REMEDIATION_INPUT_WRITES':0,
            'PARENT_PLAN_WRITES':0,'BASELINE_WRITES':0,'PREFLIGHT_EXECUTION_AUTHORIZED':0,'PROCESSING_AUTHORIZED':0,'FRESH_CONNECTION_VERIFIED':1,'PROPOSALS_COMPLETE':1}
        for k,v in values.items():print('PREFLIGHT_'+k+'='+str(v),flush=True)
        for receipt,(label,_) in zip(header['current_consideration']['receipts'],QUERIES):
            print('PREFLIGHT_RECEIPT_'+label.upper()+'_ID='+receipt['receipt_id'],flush=True);print('PREFLIGHT_RECEIPT_'+label.upper()+'_MATCHED='+str(receipt['matched_count']),flush=True)
    except Exception as exc:
        allowed={'MEMORY_BUDGET','QUERY_DENIED','TRANSACTION_BUDGET','PLANNING_BUSY','TARGET_NOT_EMPTY','PRESERVED_RECEIPT_DRIFT','SOURCE_OR_SEARCH_INPUT_DRIFT','REVIEW_SCOPE_DRIFT','PREFLIGHT_BOUND_DRIFT','PREFLIGHT_SCOPE_DRIFT','PREFLIGHT_AUTHORITY_DRIFT','REFRESH_SCOPE_EXCEEDED','OUTPUT_RESOURCE_BOUND',
            'REMEDIATION_MISSING','REMEDIATION_HEADER_DRIFT','REMEDIATION_SCOPE_DRIFT','REMEDIATION_AUTHORITY_DRIFT','REMEDIATION_BATCH_DRIFT','REMEDIATION_EVENT_DRIFT','REMEDIATION_SOURCE_BINDING_DRIFT',
            'PARENT_MISSING','PARENT_HEADER_DRIFT','PARENT_SCOPE_DRIFT','PARENT_BATCH_DRIFT','PARENT_EVENT_DRIFT','BASELINE_MISSING','BASELINE_HEADER_DRIFT','BASELINE_MEMBER_DRIFT','BASELINE_EVENT_DRIFT',
            'SOURCE_RIGHTS_VERSION_DRIFT','SOURCE_INVENTORY_CHANGED','BOUNDARY_BELOW_MINIMUM','INDEPENDENT_SOURCE_DRIFT','OUTPUT_HEADER_DRIFT','OUTPUT_BATCH_DRIFT','OUTPUT_EVENT_DRIFT','TASK_RECEIPT_DRIFT','EXECUTION_BINDING','BACKEND_REQUIRED','MEMBERSHIP_INVALID','DRIVE_SCOPE_DRIFT','AVAILABILITY_DRIFT','RESOURCE_BOUND','DUPLICATE_MEMBERSHIP'}
        code=exc.code if isinstance(exc,support.CensusFailure) else str(exc) if str(exc) in allowed else 'UNEXPECTED_FAILURE'
        print('PREFLIGHT_FAILURE_CODE='+code,flush=True);print('PREFLIGHT_FAILURE_STAGE='+STAGE,flush=True)
        print('PREFLIGHT_COMMIT_ATTEMPTED='+str(COMMIT_ATTEMPTED),flush=True);print('PREFLIGHT_COMMIT_ACKNOWLEDGED='+str(COMMIT_ACKNOWLEDGED),flush=True)
        raise SystemExit(1) from None
    finally:
        if inner is not None:inner.close()
        if intake is not None:intake.client.close();intake.credential.close()


if __name__=='__main__':main()
