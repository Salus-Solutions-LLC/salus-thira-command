"""Prepare source-bound human-review proposals; no extraction, queue or hold mutation."""
import gc
import hashlib
import json
import os
import re
import time
import uuid
from datetime import datetime,timezone
try:
    import salus_streamed_plan_support as planning
except ImportError:
    from tools import live_knowledge_streamed_recovery_plan as planning
baseline=planning.baseline
support=baseline.support
require=baseline.require
KEY='salus-recovery-remediation-proposals-20261115'
ACTOR='System Administrator - task consideration '+KEY+' / '
PARENT_SHA='1d1883f3da42c5e3c0aa736f0d7f3d3369193787a3ec27d514287cc639787026'
STATE='Proposed - Awaiting Remediation Approval'
TABLES=('m365_knowledge_remediation_proposals','m365_knowledge_remediation_batches','m365_knowledge_remediation_events')
QUERIES=(('remedy_review','remediation review conversion derivative original archive pdf document image media repair unsupported encryption'),
         ('processor_safety','processor resource capacity retry paused checkpoint lease transcription ocr limit validation'),
         ('rights_and_contrary','rights permission hold restricted unsafe active conflicting version unavailable contrary prohibit'),
         ('approval_and_proof','approval qualified provenance baseline verification hash rollback audit receipt integrity'))
DDL=('CREATE TABLE IF NOT EXISTS '+TABLES[0]+' (operation_key TEXT PRIMARY KEY,state TEXT NOT NULL,parent_manifest_sha256 TEXT NOT NULL,manifest_sha256 TEXT NOT NULL,payload_json TEXT NOT NULL,created_at TEXT NOT NULL)',
     'CREATE TABLE IF NOT EXISTS '+TABLES[1]+' (operation_key TEXT NOT NULL,batch_key TEXT NOT NULL,source_count INTEGER NOT NULL,payload_sha256 TEXT NOT NULL,payload_json TEXT NOT NULL,PRIMARY KEY(operation_key,batch_key))',
     'CREATE TABLE IF NOT EXISTS '+TABLES[2]+' (operation_key TEXT PRIMARY KEY,payload_json TEXT NOT NULL,created_at TEXT NOT NULL)')
STAGE='not_started'
COMMIT_ATTEMPTED=COMMIT_ACKNOWLEDGED=0


def phase(name):
    global STAGE
    STAGE=name;gc.collect()
    print('REMEDIATION_PHASE='+name,flush=True)
    try:import resource
    except ImportError:return
    peak=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    print('REMEDIATION_PEAK_RSS_KIB='+str(peak),flush=True)
    require(peak<786432,'MEMORY_BUDGET')


class Connection(baseline.ProposalConnection):
    def execute(self,sql,params=()):
        write=sql in DDL or bool(re.fullmatch(r'INSERT INTO (?:'+'|'.join((*TABLES,support.RECEIPT_TABLE))+r') VALUES\([?,]+\)',sql))
        if self.writes_enabled and write:
            if sql not in DDL:
                if sql.startswith('INSERT INTO '+support.RECEIPT_TABLE+' '):
                    require(len(params)==10 and params[8] in {ACTOR+label for label,_ in QUERIES},'QUERY_DENIED')
                else:require(params and params[0]==KEY,'QUERY_DENIED')
            if self.deadline is not None:
                remaining=self.deadline-self.clock();require(remaining>0,'TRANSACTION_BUDGET')
                if self.backend=='postgres':self.inner.execute("SET LOCAL statement_timeout='"+str(max(1,min(30000,int(remaining*1000))))+"ms'")
            return self.inner.execute(sql,params)
        enabled=self.writes_enabled;self.writes_enabled=False
        try:return super().execute(sql,params)
        finally:self.writes_enabled=enabled


def baseline_proof(conn,expected=planning.MANIFEST):
    row=conn.execute('SELECT * FROM '+baseline.TABLES[0]+' WHERE operation_key=?',(baseline.KEY,)).fetchone()
    require(row is not None,'BASELINE_MISSING')
    require(hashlib.sha256(row['payload_json'].encode()).hexdigest()==expected,'BASELINE_HEADER_DRIFT')
    header=planning.MEMBER_DECODER.decode(row['payload_json'])
    require(support.digest(header)==row['manifest_sha256']==expected and row['state']==baseline.STATE and row['created_at']==header['created_at'],'BASELINE_HEADER_DRIFT')
    rows=planning.member_projection(conn)
    require(len(rows)==len(header['member_hashes']),'BASELINE_MEMBER_DRIFT')
    for actual,binding in zip(rows,header['member_hashes']):
        require(actual['source_item_id']==binding['source_item_id'] and actual['category']==actual['payload_category'] and actual['member_sha256']==actual['payload_sha256']==binding['sha256'],'BASELINE_MEMBER_DRIFT')
    event=conn.execute('SELECT * FROM '+baseline.TABLES[2]+' WHERE operation_key=?',(baseline.KEY,)).fetchall()
    expected_event={'manifest_sha256':expected,'state':baseline.STATE,'processing_authorized':False,'baseline_accepted':False,'member_count':len(rows)}
    require(len(event)==1 and event[0]['payload_json']==support.canonical(expected_event) and event[0]['created_at']==header['created_at'],'BASELINE_EVENT_DRIFT')
    return header


def parent_proof(conn,*,expected=PARENT_SHA,baseline_sha=planning.MANIFEST,expected_batches=200,expected_sources=8430):
    base=baseline_proof(conn,baseline_sha)
    row=conn.execute('SELECT * FROM '+support.PLAN_TABLES[0]+' WHERE operation_key=?',(support.TASK_KEY,)).fetchone()
    require(row is not None,'PARENT_MISSING')
    require(hashlib.sha256(row['payload_json'].encode()).hexdigest()==expected,'PARENT_HEADER_DRIFT')
    parent=planning.MEMBER_DECODER.decode(row['payload_json'])
    require(row['manifest_sha256']==support.digest(parent)==expected and row['state']==parent['state']=='Prepared - Not Authorized for Processing' and row['created_at']==parent['created_at'],'PARENT_HEADER_DRIFT')
    require(parent['approved_baseline']['manifest_sha256']==baseline_sha and parent['summary']['prepared_sources']==expected_sources and parent['summary']['batch_count']==expected_batches and parent['summary']['processing_authorized'] is False,'PARENT_SCOPE_DRIFT')
    rows=conn.execute('SELECT batch_key,record_count,payload_sha256,'+baseline.sql_hash(conn,'payload_json')+' actual_sha256 FROM '+support.PLAN_TABLES[1]+' WHERE operation_key=? ORDER BY batch_key',(support.TASK_KEY,)).fetchall()
    bindings=parent['batch_hashes']
    require(len(rows)==len(bindings)==expected_batches and len({r['batch_key'] for r in rows})==expected_batches,'PARENT_BATCH_DRIFT')
    for actual,binding in zip(rows,bindings):
        require(actual['batch_key']==binding['batch_key'] and 0<actual['record_count']<=50 and actual['payload_sha256']==actual['actual_sha256']==binding['sha256'],'PARENT_BATCH_DRIFT')
    require(sum(r['record_count'] for r in rows)==expected_sources,'PARENT_SCOPE_DRIFT')
    event=conn.execute('SELECT * FROM '+support.PLAN_TABLES[2]+' WHERE operation_key=?',(support.TASK_KEY,)).fetchall()
    expected_event={'manifest_sha256':expected,'summary':parent['summary'],'processing_authorized':False}
    require(len(event)==1 and event[0]['event_type']=='AvailabilityReconciledAndRecoveryBatchesPrepared' and event[0]['detail_json']==support.canonical(expected_event) and event[0]['created_at']==parent['created_at'],'PARENT_EVENT_DRIFT')
    planning.receipts(conn,base)
    planning.planning_receipts(conn,parent['current_consideration']['receipts'])
    twelve=base['original_receipts']+base['new_receipts']+parent['current_consideration']['receipts']
    require(len(twelve)==len({r['receipt_id'] for r in twelve})==12,'PRESERVED_RECEIPT_DRIFT')
    return base,parent,support.digest(sorted(twelve,key=lambda r:r['actor']))


def target_empty(conn):
    counts=[]
    for table in TABLES:
        present=bool(conn.execute('SELECT to_regclass(?)',(table,)).fetchone()[0]) if conn.backend=='postgres' else bool(conn.execute("SELECT name FROM sqlite_master WHERE type='table' AND name=?",(table,)).fetchone())
        counts.append(conn.execute('SELECT COUNT(*) FROM '+table+' WHERE operation_key=?',(KEY,)).fetchone()[0] if present else 0)
    fresh=conn.execute('SELECT COUNT(*) FROM '+support.RECEIPT_TABLE+' WHERE actor LIKE ?',(ACTOR+'%',)).fetchone()[0]
    for name,value in zip(('HEADERS','BATCHES','EVENTS','TASK_RECEIPTS'),(*counts,fresh)):print('REMEDIATION_PRESTATE_'+name+'='+str(value),flush=True)
    require(not any((*counts,fresh)),'TARGET_NOT_EMPTY')


METHODS={
 'owner_hold_review':{'owner':'Source owner/rightsholder and governance reviewer','proposal':'Resolve lawful purpose, access and hold dispositions; retain the existing hold until a separate recorded decision.','acceptance':'Exact source/version, rights, purpose and disposition approval; no hold release from this proposal.'},
 'safe_derivative_review':{'owner':'Qualified source reviewer and validated processor owner','proposal':'Assess a lawful, isolated static or benign derivative from a preserved original; do not execute active content or overwrite the original.','acceptance':'Approved method/version, original and derivative hashes, benign format/content checks and qualified output review.'},
 'authorized_readable_source':{'owner':'Source owner/rightsholder','proposal':'Request an authorized readable or unencrypted successor, or explicit lawful decryption authority; do not bypass access controls.','acceptance':'Rights/authority, source-version lineage, original retention, integrity and qualified readable-output proof.'},
 'integrity_and_repair_review':{'owner':'Source custodian and qualified format reviewer','proposal':'Verify authorized original/archive bytes and integrity, characterize corruption/type mismatch and seek an owner-supplied repaired successor.','acceptance':'Recorded byte/hash comparison, correct type, preserved versions and tested safe output; otherwise retain explicit unavailable status.'},
 'processor_remediation':{'owner':'Processor maintainer and governance reviewer','proposal':'Design processor-specific bounded tests for the recorded resource/capacity/transcription condition, preserving current pause and checkpoints.','acceptance':'Validated processor release, measured limits/cost, representative tests and rollback; separate exact-version execution/resumption approval.'},
 'bounded_retry_preflight':{'owner':'Processor operator and governance approver','proposal':'Prepare same-candidate due/lease/source/archive/hash and rights preflight for a separately authorized small execution; do not enqueue or retry now.','acceptance':'Current candidate/version/rights/archive-byte/checkpoint proof, bounded approved selection, validated processor and independent result verification.'},
 'all_version_reconciliation':{'owner':'Source custodian and governance reviewer','proposal':'Reconcile every retained candidate and current/historical source version; do not silently deduplicate or select a replacement.','acceptance':'Exact ID/version/archive lineage, conflicting evidence disposition and explicit selected-version approval.'},
 'missing_candidate_provenance':{'owner':'Source custodian and governance reviewer','proposal':'Establish current or retained source identity, rights and authorized byte/archive availability before proposing enrollment; retain unavailable evidence if absent.','acceptance':'Source-correlated provenance and owner authority, no fabricated candidate or duplicate source, separate enrollment approval.'},
 'unknown_condition_review':{'owner':'Qualified reviewer and governance approver','proposal':'Characterize the unknown/conflicting failure condition before choosing any processor or remedy.','acceptance':'Documented cause and approved safe method; no automatic remedy or processing inference.'}}
COMMON_GATES=['Qualified review of this exact proposal manifest and selected existing batch IDs',
 'Source-owner/rightsholder authority, purpose, privacy and original/version preservation',
 'Validated remedy/processor version with explicit resource/cost limits and rollback where applicable',
 'Fresh source/archive-byte/hash, candidate/rights and due/lease/checkpoint preflight under separate authority',
 'Separate exact-version authorization for a bounded action; independent result and cleanup proof before any status/qualification change']


def methods_for(record):
    category=record['category'];codes=set(record.get('failure_codes',[]))
    if category=='governed_hold':return ['owner_hold_review']
    if category=='other_or_conflicting':return ['all_version_reconciliation']
    if category=='no_candidate':return ['missing_candidate_provenance']
    chosen=set()
    if record.get('traits',{}).get('multiple_candidate_sources'):chosen.add('all_version_reconciliation')
    if category=='retry_paused':chosen.add('processor_remediation')
    if category=='automatic_retry':chosen.add('bounded_retry_preflight')
    for code in codes:
        if code=='PDF_ENCRYPTED':chosen.add('authorized_readable_source')
        elif code in {'DOCUMENT_ACTIVE_CONTENT','DOCUMENT_ACTIVE_OR_LEGACY_FORMAT','PDF_ACTIVE_CONTENT','FORMAT_NOT_SUPPORTED'}:chosen.add('safe_derivative_review')
        elif any(v in code for v in ('RESOURCE','CAPACITY','TRANSCRIPT','TRANSCRIPTION','PAGE_LIMIT','EXPANSION_LIMIT','SOURCE_LIMIT')):chosen.add('processor_remediation')
        elif code in support.KNOWN_CODES:chosen.add('integrity_and_repair_review')
        else:chosen.add('unknown_condition_review')
    return sorted(chosen or {'unknown_condition_review'})


def indexes(evidence,core):
    result={name:{} for name in ('candidates','provenance','holds','bulk')}
    for family,rows,key in (('candidates',evidence['candidates'],'source_item_id'),('provenance',core['candidates'],'source_item_id'),('holds',core['holds'],'source_item_id'),('bulk',core['bulk'],'item_id')):
        for row in rows:result[family].setdefault(row[key],[]).append(row)
    return result


def current_member(original,lookup,signature,inventory):
    source=original['source_item_id'];require(source in signature,'SOURCE_RIGHTS_VERSION_DRIFT');category,exception,exact=signature[source]
    return {'source_item_id':source,'source_drive_id':original['source_drive_id'],'category':category,
        'current_source':inventory.get(source),'current_inventory_member':source in inventory,'availability_exception':exception,'exact_complete_text':exact,
        'candidate_versions':[{k:v for k,v in row.items() if k!='checkpoint'} for row in lookup['candidates'].get(source,[])],
        'candidate_source_provenance':lookup['provenance'].get(source,[]),'holds':lookup['holds'].get(source,[]),'bulk_provenance':lookup['bulk'].get(source,[])}


def build_proposals(conn,base,parent,evidence,core,inventory,*,expected_sources=8430):
    lookup=indexes(evidence,core);signature=baseline.membership_signature(evidence)
    hashes={r['source_item_id']:r['sha256'] for r in base['member_hashes']}
    seen=set();proposals=[];counts={k:0 for k in support.CATEGORIES}
    for binding in parent['batch_hashes']:
        cursor=conn.execute('SELECT * FROM '+support.PLAN_TABLES[1]+' WHERE operation_key=? AND batch_key=?',(support.TASK_KEY,binding['batch_key']))
        try:
            row=cursor.fetchone();require(row is not None,'PARENT_BATCH_DRIFT');batch=planning.MEMBER_DECODER.decode(row['payload_json'])
        finally:getattr(cursor,'cursor',cursor).close()
        require(support.digest(batch)==binding['sha256'] and row['payload_sha256']==binding['sha256'] and row['record_count']==batch['record_count']==len(batch['records']) and batch['processing_authorized'] is False,'PARENT_BATCH_DRIFT')
        ids=sorted(r['source_item_id'] for r in batch['records'])
        require(0<len(ids)<=50 and len(set(ids))==len(ids) and not seen.intersection(ids),'PARENT_SCOPE_DRIFT')
        originals={m['source_item_id']:m for m in planning.read_member_groups(conn,ids)}
        records=[];methods=set()
        for record in batch['records']:
            source=record['source_item_id'];original=originals[source]
            require(support.digest(original)==hashes[source] and source in signature,'BASELINE_MEMBER_DRIFT')
            current=current_member(original,lookup,signature,inventory)
            require(planning.critical(original)==planning.critical(current) and current['category']==record['category']!='legacy_available','SOURCE_RIGHTS_VERSION_DRIFT')
            route=methods_for(record);methods.update(route);counts[record['category']]+=1
            records.append({'source_item_id':source,'parent_record_sha256':support.digest(record),'baseline_member_sha256':hashes[source],
                'current_critical_sha256':support.digest(planning.critical(current)),
                'candidate_versions':[{'candidate_id':r['id'],'source_etag':r['source_etag'],'classification_sha256':r['classification_sha256'],
                    'source_size':r['source_size'],'failure_code':r['failure_code'] if r['failure_code'] in support.KNOWN_CODES else 'UNKNOWN' if r['failure_code'] else 'EMPTY',
                    'method_codes':methods_for({'category':record['category'],'failure_codes':[r['failure_code'] if r['failure_code'] in support.KNOWN_CODES else 'UNKNOWN' if r['failure_code'] else 'EMPTY']}),
                    'source_version_matches_current':bool(inventory.get(source) and inventory[source]['etag']==r['source_etag']),
                    'archive_metadata_recorded':bool(r['source_archive_item_id'])} for r in current['candidate_versions']],
                'current_inventory_member':source in inventory,
                'method_codes':route,'processing_authorized':False,'source_rights_qualified':False,'archive_bytes_verified':False})
        seen.update(ids)
        proposals.append({'batch_key':batch['batch_key'],'parent_batch_sha256':binding['sha256'],'category':batch['category'],
            'source_count':len(records),'state':STATE,'method_codes':sorted(methods),'source_bindings':records,
            'approval_steps':COMMON_GATES,'processing_authorized':False,'retry_resume_authorized':False,'hold_release_authorized':False})
    require(len(seen)==expected_sources and counts==parent['summary']['categories'],'PARENT_SCOPE_DRIFT')
    exceptions=parent['availability_exceptions']
    for original in planning.read_member_groups(conn,sorted(r['source_item_id'] for r in exceptions)):
        require(support.digest(original)==hashes[original['source_item_id']] and planning.critical(original)==planning.critical(current_member(original,lookup,signature,inventory)),'SOURCE_RIGHTS_VERSION_DRIFT')
    return proposals,seen|{r['source_item_id'] for r in exceptions}


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


def current_schedules(conn,proposals):
    sources={r['source_item_id'] for p in proposals for r in p['source_bindings']}
    bulk={};checks={}
    for row in conn.execute("SELECT drive_id,pending_id,item_id,parent_id,etag,size,status,reason,attempts,next_attempt,updated_at,lease_owner,lease_until FROM m365_bulk_items WHERE kind='file' AND status<>'Removed' ORDER BY drive_id,pending_id,item_id"):
        if row['item_id'] in sources:bulk.setdefault(row['item_id'],[]).append(dict(row))
    for row in conn.execute('SELECT candidate_id,attempts,next_attempt,lease_owner,lease_until,checked_at,last_code FROM m365_bulk_extraction_checks ORDER BY candidate_id'):checks[row['candidate_id']]=dict(row)
    require(len(checks)<=150000,'RESOURCE_BOUND')
    for p in proposals:
        for record in p['source_bindings']:
            record['current_bulk_checkpoints']=bulk.get(record['source_item_id'],[])
            record['current_candidate_checkpoints']=[{'candidate_id':v['candidate_id'],'checkpoint':checks.get(v['candidate_id'])} for v in record['candidate_versions']]


def verify_output(conn,header,proposals):
    row=conn.execute('SELECT * FROM '+TABLES[0]+' WHERE operation_key=?',(KEY,)).fetchone()
    require(row is not None and row['state']==STATE and row['parent_manifest_sha256']==header['parent_manifest_sha256'] and row['manifest_sha256']==support.digest(header) and row['payload_json']==support.canonical(header) and row['created_at']==header['created_at'],'OUTPUT_HEADER_DRIFT')
    rows=conn.execute('SELECT * FROM '+TABLES[1]+' WHERE operation_key=? ORDER BY batch_key',(KEY,)).fetchall();require(len(rows)==len(proposals),'OUTPUT_BATCH_DRIFT')
    for row,p in zip(rows,proposals):require(row['batch_key']==p['batch_key'] and row['source_count']==p['source_count'] and row['payload_sha256']==support.digest(p) and row['payload_json']==support.canonical(p),'OUTPUT_BATCH_DRIFT')
    event=conn.execute('SELECT * FROM '+TABLES[2]+' WHERE operation_key=?',(KEY,)).fetchall()
    require(len(event)==1 and event[0]['created_at']==header['created_at'] and event[0]['payload_json']==support.canonical({'manifest_sha256':support.digest(header),'state':STATE,'parent_manifest_sha256':header['parent_manifest_sha256'],'processing_authorized':False}),'OUTPUT_EVENT_DRIFT')
    fresh=[dict(r) for r in conn.execute('SELECT * FROM '+support.RECEIPT_TABLE+' WHERE actor LIKE ? ORDER BY actor',(ACTOR+'%',)).fetchall()]
    require(fresh==sorted(header['current_consideration']['receipts'],key=lambda r:r['actor']),'TASK_RECEIPT_DRIFT')
    return support.digest(header)


def prepare(inner,context,*,expected_parent=PARENT_SHA,expected_baseline=planning.MANIFEST,expected_batches=200,expected_sources=8430,fail_after_batches=False,clock=time.monotonic):
    global COMMIT_ATTEMPTED,COMMIT_ACKNOWLEDGED
    COMMIT_ATTEMPTED=COMMIT_ACKNOWLEDGED=0;started=clock();conn=Connection(inner);conn.clock=clock;conn.deadline=started+60
    try:
        phase('locked_parent_and_receipt_verification')
        if conn.backend=='postgres':
            inner.execute("SET LOCAL lock_timeout='2s'");inner.execute("SET LOCAL statement_timeout='30s'")
            require(inner.execute('SELECT pg_try_advisory_xact_lock(674160041245)').fetchone()[0],'PLANNING_BUSY')
            inner.execute('LOCK TABLE '+','.join((*support.SOURCE_TABLES,support.RECEIPT_TABLE,*baseline.TABLES,*support.PLAN_TABLES))+' IN SHARE MODE NOWAIT')
        else:inner.execute('BEGIN IMMEDIATE')
        base,parent,twelve_sha=parent_proof(conn,expected=expected_parent,baseline_sha=expected_baseline,expected_batches=expected_batches,expected_sources=expected_sources);target_empty(conn)
        current=baseline.core_snapshot(conn);before=context.pop('preview_core')
        require(current['represented']==before['represented'],'SOURCE_IDENTITY_VERSION_DRIFT')
        delta=baseline.core_delta(before,current);del before;baseline.emit_delta(delta,'REMEDIATION_DRIFT')
        for family,allowed in (('candidates',{'classification_sha256','status','decision','reviewed_at','reviewed_by','review_rationale','target_folder'}),('holds',{'reviewed_at'}),('bulk',{'status','reason','metadata_sha256'})):
            require(delta[family]['added']==delta[family]['removed']==0 and set(delta[family]['fields'])<=allowed,'SOURCE_IDENTITY_VERSION_DRIFT')
        for change in delta['candidates']['rows']:
            if change['source_item_id'] in context['scope']:require(set(change['fields'])<={'reviewed_at'},'SOURCE_RIGHTS_VERSION_DRIFT')
        sources={r['source_item_id'] for r in delta['candidates']['rows']};require(len(sources)<=100,'REFRESH_SCOPE_EXCEEDED')
        evidence={'represented':current['represented'],'holds':current['holds'],'candidates':sorted([r for r in context['evidence']['candidates'] if r['source_item_id'] not in sources]+baseline.candidate_subset(conn,sources),key=lambda r:r['id'])}
        families=context.pop('families');context['evidence']=None
        if sources:families['C'].update(search_matrix(conn,family='C',source_ids=sources))
        for family in ('B','H'):families[family]=search_matrix(conn,family=family)
        observation=observe(evidence,current,context['inventory'],baseline.combine_families(families),context['drive_id'])
        proposed_sources={r['source_item_id'] for p in context['proposals'] for r in p['source_bindings']}
        signature=baseline.membership_signature(evidence)
        observation['unresolved_outside_parent_batches']=sorted(s for s,v in signature.items() if v[0]!='legacy_available' and s not in proposed_sources)
        observation['unresolved_outside_parent_batches_count']=len(observation['unresolved_outside_parent_batches'])
        observation['outside_parent_disposition']='Considered in current corpus; no proposal or processing authority outside the existing parent batches'
        del families,evidence,signature
        proposals=context['proposals'];current_schedules(conn,proposals)
        require(len(proposals)==expected_batches and len({p['batch_key'] for p in proposals})==expected_batches and len(proposed_sources)==expected_sources and sum(p['source_count'] for p in proposals)==expected_sources,'PARENT_SCOPE_DRIFT')
        require([{'batch_key':p['batch_key'],'sha256':p['parent_batch_sha256']} for p in proposals]==parent['batch_hashes'],'PARENT_BATCH_DRIFT')
        now=observation['created_at']
        header={'operation_key':KEY,'state':STATE,'created_at':now,'parent_operation_key':support.TASK_KEY,'parent_manifest_sha256':expected_parent,
            'approved_baseline_sha256':expected_baseline,'preserved_receipt_count':12,'preserved_receipts_sha256':twelve_sha,
            'proposal_count':len(proposals),'source_count':expected_sources,'categories':parent['summary']['categories'],'method_catalog':METHODS,
            'common_approval_gates':COMMON_GATES,'excluded_availability_exceptions':len(parent['availability_exceptions']),
            'review_challenges':['Challenge unsafe conversion/active content, wrong source/version, missing rights, false completion, resource/cost overrun and disclosure risk before approval'],
            'reassessment_triggers':['Source identity/version/rights or hold disposition changes','Processor, resource/cost limits or rollback evidence changes','New failure, conflicting evidence, invalid/empty output or checkpoint/lease changes'],
            'uncertainty':'Metadata-derived proposed remedies; source bytes, archive integrity, rights, feasibility and output quality still need authorized verification',
            'current_consideration':observation,'proposal_hashes':[{'batch_key':p['batch_key'],'sha256':support.digest(p)} for p in proposals],
            'paused_retries_preserved':True,'governed_holds_preserved':True,'processing_authorized':False,'retry_resume_authorized':False,'hold_release_authorized':False,
            'source_record_writes':0,'parent_plan_writes':0,'baseline_writes':0,'archive_bytes_verified':False,'human_qualification_completed':False,
            'request':{'thread_id':'01a1dccc-3c40-7c60-b6eb-f9836bd1332e','turn_id':'01a1e283-bd83-7942-b622-87d82cbb9d85','user_message_id':'01a1e283-be6e-7f11-b0c9-6748219d2596'},
            'execution_run_id':os.getenv('SALUS_POSTSEARCH_RUN_ID','fixture'),'script_sha256':os.getenv('SALUS_POSTSEARCH_SCRIPT_SHA256','fixture'),
            'chat_export_backfill_complete':False,'repository_source_copy_in_library':False}
        require(len(support.canonical(header).encode())+sum(len(support.canonical(p).encode()) for p in proposals)<=24*1024*1024,'OUTPUT_RESOURCE_BOUND')
        phase('atomic_proposals_and_four_receipts');conn.writes_enabled=True
        for sql in DDL:conn.execute(sql)
        for p in proposals:conn.execute('INSERT INTO '+TABLES[1]+' VALUES(?,?,?,?,?)',(KEY,p['batch_key'],p['source_count'],support.digest(p),support.canonical(p)))
        if fail_after_batches:raise ValueError('INJECTED_ROLLBACK')
        for receipt in observation['receipts']:conn.execute('INSERT INTO '+support.RECEIPT_TABLE+' VALUES('+','.join('?' for _ in receipt)+')',tuple(receipt.values()))
        checksum=support.digest(header)
        conn.execute('INSERT INTO '+TABLES[0]+' VALUES(?,?,?,?,?,?)',(KEY,STATE,expected_parent,checksum,support.canonical(header),now))
        conn.execute('INSERT INTO '+TABLES[2]+' VALUES(?,?,?)',(KEY,support.canonical({'manifest_sha256':checksum,'state':STATE,'parent_manifest_sha256':expected_parent,'processing_authorized':False}),now))
        verify_output(conn,header,proposals)
        require(parent_proof(conn,expected=expected_parent,baseline_sha=expected_baseline,expected_batches=expected_batches,expected_sources=expected_sources)[2]==twelve_sha,'PRESERVED_RECEIPT_DRIFT')
        require(clock()-started<60,'TRANSACTION_BUDGET');COMMIT_ATTEMPTED=1;inner.commit();COMMIT_ACKNOWLEDGED=1
        print('REMEDIATION_COMMIT_WINDOW_MS='+str(int((clock()-started)*1000)),flush=True)
        return header,proposals,current
    except Exception:inner.rollback();raise
    finally:conn.writes_enabled=False;conn.deadline=None


def main():
    from database import connect_database
    from salcapa_m365_intake import GovernedM365Config,GovernedM365Intake
    inner=intake=None
    try:
        require(os.getenv('SALUS_DB_BACKEND','').lower()=='postgres','BACKEND_REQUIRED')
        require(bool(re.fullmatch('[1-9][0-9]{5,19}',os.getenv('SALUS_POSTSEARCH_RUN_ID',''))) and bool(re.fullmatch('[0-9a-f]{64}',os.getenv('SALUS_POSTSEARCH_SCRIPT_SHA256',''))),'EXECUTION_BINDING')
        phase('parent_baseline_and_twelve_receipts');inner=connect_database();conn=baseline.begin_read_only(inner)
        parent_proof(conn);target_empty(conn);inner.close();inner=None
        config=GovernedM365Config.from_environment();intake=GovernedM365Intake(config)
        phase('stable_physical_inventory');inventory=support.establish_stable_inventory(intake);require(len(inventory)>=23747,'BOUNDARY_BELOW_MINIMUM')
        phase('full_corpus_consideration_and_streamed_proposals');inner=connect_database();conn=baseline.begin_read_only(inner)
        base,parent,_=parent_proof(conn);support.verify_membership(conn,inventory)
        core=baseline.core_snapshot(conn);evidence=support.read_evidence(conn);families={f:search_matrix(conn,family=f) for f in ('C','B','H')}
        proposals,scope=build_proposals(conn,base,parent,evidence,core,inventory)
        observe(evidence,core,inventory,baseline.combine_families(families),config.drive_id)
        inner.close();inner=None;del base,parent
        require(support.acquire_inventory(intake)==inventory,'SOURCE_INVENTORY_CHANGED')
        context={'preview_core':core,'evidence':evidence,'families':families,'inventory':inventory,'drive_id':config.drive_id,'proposals':proposals,'scope':scope}
        del core,evidence,families
        inner=connect_database();header,proposals,committed_core=prepare(inner,context);inner.close();inner=None
        phase('independent_durable_readback');inner=connect_database();conn=baseline.begin_read_only(inner)
        require(parent_proof(conn)[2]==header['preserved_receipts_sha256'],'PRESERVED_RECEIPT_DRIFT');checksum=verify_output(conn,header,proposals)
        after=baseline.core_snapshot(conn);delta=baseline.core_delta(committed_core,after);baseline.emit_delta(delta,'REMEDIATION_POSTCOMMIT_DRIFT')
        require(after['represented']==committed_core['represented'],'INDEPENDENT_SOURCE_DRIFT')
        for family,allowed in (('candidates',{'reviewed_at'}),('holds',{'reviewed_at'}),('bulk',{'status','reason','metadata_sha256'})):
            require(delta[family]['added']==delta[family]['removed']==0 and set(delta[family]['fields'])<=allowed,'INDEPENDENT_SOURCE_DRIFT')
        for key,value in {'MANIFEST_SHA256':checksum,'PARENT_MANIFEST_SHA256':PARENT_SHA,'PROPOSALS':200,'SOURCES':8430,'PRESERVED_RECEIPTS':12,'NEW_RECEIPTS':4,
            'SOURCE_RECORD_WRITES':0,'PARENT_PLAN_WRITES':0,'BASELINE_WRITES':0,'PROCESSING_AUTHORIZED':0,'FRESH_CONNECTION_VERIFIED':1,'PROPOSALS_COMPLETE':1}.items():print('REMEDIATION_'+key+'='+str(value),flush=True)
        for receipt,(label,_) in zip(header['current_consideration']['receipts'],QUERIES):
            print('REMEDIATION_RECEIPT_'+label.upper()+'_ID='+receipt['receipt_id'],flush=True)
            print('REMEDIATION_RECEIPT_'+label.upper()+'_MATCHED='+str(receipt['matched_count']),flush=True)
    except Exception as exc:
        allowed={'MEMORY_BUDGET','QUERY_DENIED','TRANSACTION_BUDGET','BASELINE_MISSING','BASELINE_HEADER_DRIFT','BASELINE_MEMBER_DRIFT','BASELINE_EVENT_DRIFT',
            'PARENT_MISSING','PARENT_HEADER_DRIFT','PARENT_SCOPE_DRIFT','PARENT_BATCH_DRIFT','PARENT_EVENT_DRIFT','PRESERVED_RECEIPT_DRIFT','TARGET_NOT_EMPTY',
            'SOURCE_RIGHTS_VERSION_DRIFT','MEMBERSHIP_INVALID','DRIVE_SCOPE_DRIFT','AVAILABILITY_DRIFT','RESOURCE_BOUND','OUTPUT_HEADER_DRIFT','OUTPUT_BATCH_DRIFT',
            'OUTPUT_EVENT_DRIFT','TASK_RECEIPT_DRIFT','PLANNING_BUSY','SOURCE_IDENTITY_VERSION_DRIFT','REFRESH_SCOPE_EXCEEDED','OUTPUT_RESOURCE_BOUND',
            'BACKEND_REQUIRED','EXECUTION_BINDING','BOUNDARY_BELOW_MINIMUM','SOURCE_INVENTORY_CHANGED','INDEPENDENT_SOURCE_DRIFT','COVERAGE_INVALID','DUPLICATE_MEMBERSHIP'}
        code=exc.code if isinstance(exc,support.CensusFailure) else str(exc) if str(exc) in allowed else 'UNEXPECTED_FAILURE'
        print('REMEDIATION_FAILURE_CODE='+code,flush=True);print('REMEDIATION_FAILURE_STAGE='+STAGE,flush=True)
        print('REMEDIATION_COMMIT_ATTEMPTED='+str(COMMIT_ATTEMPTED),flush=True);print('REMEDIATION_COMMIT_ACKNOWLEDGED='+str(COMMIT_ACKNOWLEDGED),flush=True)
        raise SystemExit(1) from None
    finally:
        if inner is not None:inner.close()
        if intake is not None:intake.client.close();intake.credential.close()


if __name__=='__main__':main()
