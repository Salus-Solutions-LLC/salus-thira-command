"""Append-only planning from SAL-D137; never starts processing or changes source state."""
import hashlib
import json
import os
import re
import time
import uuid
import sys
import gc
from datetime import datetime,timezone
try:
    import salus_baseline_support as baseline
except ImportError:
    from tools import live_knowledge_baseline_proposal as baseline
support = baseline.support
require = baseline.require
PHASE_KEY = 'salus-streamed-baseline-recovery-plan-20261115'
ACTOR = 'System Administrator - task consideration salus-approved-baseline-recovery-plan-20261115 / '
MANIFEST = '9a662aa94726890dfc7e4845620161ab372d81c2cc27ba8f45d84ee694840821'
AUTHORITY_COMMIT = '0f0d9fa46904e78a36027c4f45a801a7de0f47c8'
STAGE = 'not_started'
COMMIT_ATTEMPTED = COMMIT_ACKNOWLEDGED = 0


def phase(name):
    global STAGE
    STAGE=name
    gc.collect()
    print('RECOVERY_PHASE='+name,flush=True)
    try:
        import resource
    except ImportError:
        return
    peak=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    print('RECOVERY_PEAK_RSS_KIB='+str(peak),flush=True)
    require(peak<786432,'MEMORY_BUDGET')


class PlanConnection(baseline.ProposalConnection):
    """Source SELECT only; exact planning DDL and bound append-only statements."""
    def execute(self, sql, params=()):
        # Capture the three existing, reviewed CREATE statements without executing them.
        class Capture:
            def execute(self, statement): ddl.append(statement)
        ddl = []
        support.create_plan_tables(Capture())
        write = sql in ddl or bool(re.fullmatch(
            r'INSERT INTO (?:' + '|'.join((*support.PLAN_TABLES, support.RECEIPT_TABLE)) + r') VALUES\([?,]+\)', sql))
        if self.writes_enabled and write:
            if self.deadline is not None:
                remaining = self.deadline - self.clock()
                require(remaining > 0, 'TRANSACTION_BUDGET')
                if self.backend == 'postgres':
                    self.inner.execute("SET LOCAL statement_timeout='" + str(max(1,min(30000,int(remaining*1000)))) + "ms'")
            return self.inner.execute(sql, params)
        enabled = self.writes_enabled
        self.writes_enabled = False
        try:
            return super().execute(sql, params)
        finally:
            self.writes_enabled = enabled


def receipts(conn, header):
    support.preserved_receipts(conn)
    rows = [dict(r) for r in conn.execute('SELECT * FROM '+support.RECEIPT_TABLE+' WHERE actor LIKE ? ORDER BY actor', (baseline.ACTOR+'%',)).fetchall()]
    require(rows == sorted(header['new_receipts'], key=lambda r:r['actor']), 'PRESERVED_RECEIPT_DRIFT')
    require(len(rows)==4, 'PRESERVED_RECEIPT_DRIFT')
    return support.digest(sorted(header['original_receipts']+rows,key=lambda r:r['actor']))


def member_projection(conn):
    category="payload_json::jsonb->>'category'" if conn.backend=='postgres' else "json_extract(payload_json,'$.category')"
    exception="(payload_json::jsonb->>'availability_exception')='true'" if conn.backend=='postgres' else "json_extract(payload_json,'$.availability_exception')=1"
    return [dict(r) for r in conn.execute('SELECT source_item_id,category,member_sha256,'+baseline.sql_hash(conn,'payload_json')+
        ' payload_sha256,'+category+' payload_category,'+exception+' availability_exception FROM '+baseline.TABLES[1]+
        ' WHERE operation_key=? ORDER BY source_item_id',(baseline.KEY,)).fetchall()]


def verify_baseline(conn, header, members, expected_manifest=MANIFEST, *, projection=None):
    require(support.digest(header)==expected_manifest,'APPROVED_MANIFEST_DRIFT')
    rows=conn.execute('SELECT * FROM '+baseline.TABLES[0]+' WHERE operation_key=?',(baseline.KEY,)).fetchall()
    require(len(rows)==1 and rows[0]['manifest_sha256']==expected_manifest and rows[0]['state']==baseline.STATE
            and rows[0]['created_at']==header['created_at'] and rows[0]['payload_json']==support.canonical(header),'BASELINE_HEADER_DRIFT')
    rows=member_projection(conn) if projection is None else projection
    require(len(rows)==len(header['member_hashes']),'BASELINE_MEMBER_DRIFT')
    for row,binding in zip(rows,header['member_hashes']):
        require(row['source_item_id']==binding['source_item_id'] and row['category']==row['payload_category']
                and row['member_sha256']==row['payload_sha256']==binding['sha256'],'BASELINE_MEMBER_DRIFT')
    selected={r['source_item_id'] for r in rows if r['category']!='legacy_available' or r['availability_exception']}
    by_id={b['source_item_id']:b['sha256'] for b in header['member_hashes']}
    require(len(members)==len(selected) and {m['source_item_id'] for m in members}==selected,'BASELINE_MEMBER_DRIFT')
    require(all(support.digest(m)==by_id[m['source_item_id']] for m in members),'BASELINE_MEMBER_DRIFT')
    event=conn.execute('SELECT * FROM '+baseline.TABLES[2]+' WHERE operation_key=?',(baseline.KEY,)).fetchall()
    expected_event={'manifest_sha256':expected_manifest,'state':baseline.STATE,'processing_authorized':False,
                    'baseline_accepted':False,'member_count':len(header['member_hashes'])}
    require(len(event)==1 and event[0]['created_at']==header['created_at'] and event[0]['payload_json']==support.canonical(expected_event),'BASELINE_EVENT_DRIFT')
    return receipts(conn,header)


MEMBER_PAGE_SIZE=100
MEMBER_DECODER=json.JSONDecoder(object_pairs_hook=lambda pairs:{sys.intern(key):value for key,value in pairs})


def read_member_groups(conn, selected):
    for offset in range(0,len(selected),MEMBER_PAGE_SIZE):
        keys=selected[offset:offset+MEMBER_PAGE_SIZE]
        cursor=conn.execute('SELECT source_item_id,payload_json FROM '+baseline.TABLES[1]+
            ' WHERE operation_key=? AND source_item_id IN ('+','.join('?' for _ in keys)+') ORDER BY source_item_id',(baseline.KEY,*keys))
        observed=[]
        try:
            for row in cursor:
                observed.append(row['source_item_id'])
                yield MEMBER_DECODER.decode(row['payload_json'])
        finally:
            getattr(cursor,'cursor',cursor).close()
        require(observed==keys,'BASELINE_MEMBER_DRIFT')


def read_baseline(conn, expected_manifest=MANIFEST):
    row=conn.execute('SELECT payload_json FROM '+baseline.TABLES[0]+' WHERE operation_key=?',(baseline.KEY,)).fetchone()
    require(row is not None,'BASELINE_MISSING')
    header=MEMBER_DECODER.decode(row['payload_json'])
    require(support.digest(header)==expected_manifest,'APPROVED_MANIFEST_DRIFT')
    projection=member_projection(conn)
    selected=[r['source_item_id'] for r in projection if r['category']!='legacy_available' or r['availability_exception']]
    # Limit each client/server result buffer and intern only repeated JSON field names.
    # Hash-bound payload values and canonical bytes are never changed.
    members=list(read_member_groups(conn,selected))
    verify_baseline(conn,header,members,expected_manifest,projection=projection)
    print('RECOVERY_BASELINE_MEMBER_HASHES_VERIFIED='+str(len(header['member_hashes'])),flush=True)
    print('RECOVERY_SELECTED_BASELINE_PAYLOADS='+str(len(members)),flush=True)
    print('RECOVERY_PRESERVED_RECEIPTS_VERIFIED=8',flush=True)
    return header,members


def critical(member):
    """Approval identity, source version, classification/rights and disposition remain fixed.

    A review timestamp alone and bulk scheduling/search metadata carry no approval authority.
    They may refresh, but are retained in current evidence and never written by this task.
    """
    result={k:member[k] for k in ('source_item_id','source_drive_id','category','current_source',
                                 'current_inventory_member','availability_exception','exact_complete_text')}
    for family in ('candidate_versions','candidate_source_provenance','holds'):
        result[family]=[{k:v for k,v in row.items() if k!='reviewed_at'} for row in member[family]]
    result['bulk_provenance']=[{k:v for k,v in row.items() if k not in ('status','reason','metadata_sha256')} for row in member['bulk_provenance']]
    return result


def approved_scope(approved, current):
    selected={m['source_item_id']:m for m in approved if m['category']!='legacy_available' or m['availability_exception']}
    now={m['source_item_id']:m for m in current if m['category']!='legacy_available' or m['availability_exception']}
    require(set(selected)==set(now), 'APPROVED_SOURCE_MEMBERSHIP_DRIFT')
    require(all(critical(m)==critical(now[s]) for s,m in selected.items()), 'APPROVED_SOURCE_RIGHTS_VERSION_DRIFT')
    return set(selected)


def scoped_evidence(conn, sources, candidate_rows=None):
    ordered=sorted(sources)
    candidates=[]
    if candidate_rows is None:
        for offset in range(0,len(ordered),100):
            candidates.extend(baseline.candidate_subset(conn,set(ordered[offset:offset+100])))
    else:candidates=[r for r in candidate_rows if r['source_item_id'] in sources]
    candidates.sort(key=lambda r:r['id'])
    bulk=[dict(r) for r in conn.execute("SELECT drive_id,pending_id,item_id,parent_id,etag,size,status,reason,attempts,next_attempt,updated_at,lease_owner,lease_until FROM m365_bulk_items WHERE kind='file' AND status<>'Removed' ORDER BY drive_id,pending_id,item_id").fetchall() if r['item_id'] in sources]
    holds=[dict(r) for r in conn.execute("SELECT source_drive_id,source_item_id,source_parent_id,source_etag,source_size,source_modified_at,source_area,status,hold_reason,research_disposition,teaching_disposition,citation_disposition,reviewed_by,reviewed_at,review_rationale FROM m365_knowledge_holds WHERE status='Governed Hold' ORDER BY source_drive_id,source_item_id").fetchall() if r['source_item_id'] in sources]
    candidate_ids={r['id'] for r in candidates}
    checks=[dict(r) for r in conn.execute('SELECT candidate_id,attempts,next_attempt,lease_owner,lease_until,checked_at,last_code FROM m365_bulk_extraction_checks ORDER BY candidate_id').fetchall() if r['candidate_id'] in candidate_ids]
    require(all(len(rows)<=150000 for rows in (candidates,bulk,holds,checks)), 'RESOURCE_BOUND')
    return {'represented':ordered,'candidates':candidates,'bulk':bulk,'holds':holds,'checks':checks}


def planning_receipts(conn, expected=None):
    rows=[dict(r) for r in conn.execute('SELECT * FROM '+support.RECEIPT_TABLE+' WHERE actor LIKE ? ORDER BY actor',(ACTOR+'%',)).fetchall()]
    require(rows==sorted(expected or [],key=lambda r:r['actor']), 'TASK_RECEIPT_DRIFT')
    if expected is None:print('RECOVERY_PRESTATE_CURRENT_RECEIPTS=0',flush=True)


def current_view(evidence,inventory,matrix,core,drive_id,*,expected=baseline.EXPECTED,expected_exceptions=5):
    represented=set(evidence['represented'])
    require(set(inventory)<=represented and represented==set(matrix)==set(core['represented']),'MEMBERSHIP_INVALID')
    require(all(r['source_drive_id']==drive_id for r in (*core['candidates'],*core['holds'])) and all(r['drive_id']==drive_id for r in core['bulk']),'DRIVE_SCOPE_DRIFT')
    signature=baseline.membership_signature(evidence)
    counts={key:sum(v[0]==key for v in signature.values()) for key in support.CATEGORIES}
    require(counts==expected,'UNRESOLVED_SCOPE_DRIFT')
    available={s for s,v in signature.items() if v[0]=='legacy_available'}
    exact={s for s,v in signature.items() if v[2]}
    strict={r['source_item_id'] for r in evidence['candidates'] if r['extraction_status']=='Complete' and r['strict_text']}
    exceptions={s for s,v in signature.items() if v[1]}
    require(exact==strict and not exact-available and len(exceptions)==expected_exceptions,'AVAILABILITY_DRIFT')
    selected=represented-available|exceptions
    indexes={name:{} for name in ('versions','provenance','holds','bulk')}
    for family,rows,key in (('versions',evidence['candidates'],'source_item_id'),('provenance',core['candidates'],'source_item_id'),('holds',core['holds'],'source_item_id'),('bulk',core['bulk'],'item_id')):
        for row in rows:
            if row[key] in selected:indexes[family].setdefault(row[key],[]).append(row)
    members=[]
    for s in sorted(selected):
        members.append({'source_item_id':s,'source_drive_id':drive_id,'category':signature[s][0],
            'current_source':inventory.get(s),'current_inventory_member':s in inventory,'availability_exception':signature[s][1],
            'exact_complete_text':signature[s][2],
            'candidate_versions':[{k:v for k,v in r.items() if k!='checkpoint'} for r in indexes['versions'].get(s,[])],
            'candidate_source_provenance':indexes['provenance'].get(s,[]),'holds':indexes['holds'].get(s,[]),'bulk_provenance':indexes['bulk'].get(s,[])})
    created=datetime.now(timezone.utc).isoformat()
    receipts=[]
    for i,(label,query) in enumerate(baseline.QUERIES):
        receipts.append({'receipt_id':str(uuid.uuid4()),'query_sha256':hashlib.sha256(query.strip().encode()).hexdigest(),
            'boundary_count':len(inventory),'considered_count':len(represented),'matched_count':sum(v[i] for v in matrix.values()),
            'content_available_count':len(available),'metadata_only_count':len(represented-available),
            'governed_hold_count':len({r['source_item_id'] for r in core['holds']}),'actor':ACTOR+label,'created_at':created})
    header={'created_at':created,'physical_files':len(inventory),'represented_files':len(represented),
        'unresolved_files':len(represented-available),'categories':counts,'legacy_available':len(available),
        'exact_complete_text':len(exact),'availability_exceptions':len(exceptions),
        'represented_not_in_current_inventory':len(represented-set(inventory)),
        'inventory_sha256':support.snapshot_digest(inventory),'core_sha256':support.digest(core),
        'search_matrix_sha256':support.digest(matrix),'new_receipts':receipts,
        'queries':[{'label':label,'query':query} for label,query in baseline.QUERIES],
        'historical_membership_reconstructed':False,'source_record_writes':0,'processing_authorized':False}
    for key,value in {'REPRESENTED':len(represented),'UNRESOLVED':len(represented-available),'SELECTED_MEMBERS':len(members)}.items():print('RECOVERY_CURRENT_'+key+'='+str(value),flush=True)
    return header,members


def refresh_current(conn,delta,current,context):
    baseline.emit_delta(delta)
    mutable={'candidates':{'classification_sha256','status','decision','reviewed_at','reviewed_by','review_rationale','target_folder'},
             'holds':{'hold_reason','research_disposition','teaching_disposition','citation_disposition','reviewed_by','reviewed_at','review_rationale'},
             'bulk':{'status','reason','metadata_sha256'}}
    for table in mutable:
        require(delta[table]['added']==delta[table]['removed']==0 and set(delta[table]['fields'])<=mutable[table],'SOURCE_IDENTITY_VERSION_DRIFT')
    sources={r['source_item_id'] for r in delta['candidates']['rows']}
    require(len(sources)<=100,'REFRESH_SCOPE_EXCEEDED')
    prior_signature=baseline.membership_signature(context['evidence'])
    evidence={'holds':current['holds'],'represented':current['represented']}
    rows=baseline.candidate_subset(conn,sources)
    evidence['candidates']=sorted([r for r in context['evidence']['candidates'] if r['source_item_id'] not in sources]+rows,key=lambda r:r['id'])
    families={k:dict(v) for k,v in context['families'].items()}
    if sources:families['C'].update(baseline.search_matrix(conn,family='C',source_ids=sources))
    for family in ('B','H'):families[family]=baseline.search_matrix(conn,family=family)
    matrix=baseline.combine_families(families)
    if context.get('_transfer_owned'):
        context['evidence']=None
        context['families']=None
    header,members=current_view(evidence,context['inventory'],matrix,current,context['drive_id'],
        expected=context.get('expected',baseline.EXPECTED),expected_exceptions=context.get('expected_exceptions',5))
    require(prior_signature==baseline.membership_signature(evidence),'SOURCE_COHORT_MEMBERSHIP_DRIFT')
    header['locked_refresh']={'candidate_sources_refreshed':len(sources),'maximum_candidate_sources':100,'delta':delta,
        'unchanged_candidate_search_flags_reused':True,'bulk_and_hold_flags_refreshed':True}
    header['coverage_encoding']={'all_sources_considered_by_all_queries':True,'query_bit_order':[label for label,_ in baseline.QUERIES],'zero_mask_means_no_matches':True}
    header['per_source_coverage']=[[s,sum((1<<i) for i,flag in enumerate(matrix[s]) if flag)] for s in sorted(matrix)]
    return header,members,evidence


def prepare(inner, approved_header, approved_members, preview_core, context, *, expected_manifest=MANIFEST, fail_after_batches=False, clock=time.monotonic):
    global COMMIT_ATTEMPTED,COMMIT_ACKNOWLEDGED
    COMMIT_ATTEMPTED=COMMIT_ACKNOWLEDGED=0
    conn=PlanConnection(inner);started=clock();conn.clock=clock;conn.deadline=started+60
    try:
        phase('locked_revalidation')
        if conn.backend=='postgres':
            inner.execute("SET LOCAL lock_timeout='2s'")
            inner.execute("SET LOCAL statement_timeout='30s'")
            require(inner.execute('SELECT pg_try_advisory_xact_lock(674160041245)').fetchone()[0], 'PLANNING_BUSY')
            inner.execute('LOCK TABLE '+','.join((*support.SOURCE_TABLES,support.RECEIPT_TABLE,*baseline.TABLES))+' IN SHARE MODE NOWAIT')
        else:inner.execute('BEGIN IMMEDIATE')
        receipt_sha=verify_baseline(conn,approved_header,approved_members,expected_manifest)
        support.target_empty(conn);planning_receipts(conn)
        current_core=baseline.core_snapshot(conn)
        if preview_core is None:preview_core=context.pop('preview_core')
        require(preview_core['represented']==current_core['represented'],'SOURCE_IDENTITY_VERSION_DRIFT')
        delta=baseline.core_delta(preview_core,current_core)
        del preview_core
        current_header,current_members,current_evidence=refresh_current(conn,delta,current_core,context)
        sources=approved_scope(approved_members,current_members)
        phase("locked_scope_projection")
        evidence=scoped_evidence(conn,sources,current_evidence["candidates"])
        del current_evidence
        phase("locked_scoped_evidence_ready")
        inventory=context['inventory']
        plan=support.make_plan(evidence,{s:v for s,v in inventory.items() if s in sources},clock=int(time.time()),
            expected_cohorts=context.get('expected',baseline.EXPECTED),expected_discrepancies=context.get('expected_exceptions',5))
        fresh=current_header['new_receipts']
        for row,(label,_) in zip(fresh,baseline.QUERIES):row['actor']=ACTOR+label
        plan['approved_baseline']={'operation_key':baseline.KEY,'manifest_sha256':expected_manifest,
            'authority_decision':'SAL-D137','authority_commit':AUTHORITY_COMMIT,'baseline_payload_rewritten':False,
            'source_scope_sha256':support.digest(sorted(sources)), 'preserved_receipts_sha256':receipt_sha,
            'preserved_receipt_ids':[r['receipt_id'] for r in approved_header['original_receipts']+approved_header['new_receipts']],
            'paused_retries_preserved':True,'governed_holds_preserved':True,'source_record_writes':0,
            'planning_request':{'thread_id':'01a1dccc-3c40-7c60-b6eb-f9836bd1332e','turn_id':'01a1e178-358d-7010-825b-c35449d889f0','user_message_id':'01a1e178-3680-79c1-b2d6-50881fecdebb'},
            'processing_authorized':False,'archive_bytes_verified':False,'historical_8404_membership_reconstructed':False}
        plan['current_consideration']={k:v for k,v in current_header.items() if k not in ('member_hashes','new_receipts','original_receipts','restricted_chat_ref','operation_key','state','baseline_accepted','execution_phase_key','prior_failed_run_id')}
        plan['current_consideration'].update({'phase_key':PHASE_KEY,'receipts':fresh,
            'scope_summary':'Plan summary covers approved unresolved sources and separate availability exceptions; corpus counts are recorded here.',
            'approved_scope_current_sha256':support.digest([critical(m) for m in current_members if m['source_item_id'] in sources]),
            'github_run_id':os.getenv('SALUS_POSTSEARCH_RUN_ID','fixture'),'script_sha256':os.getenv('SALUS_POSTSEARCH_SCRIPT_SHA256','fixture')})
        current_members=None
        gc.collect()
        require(len(support.canonical(plan).encode())<=24*1024*1024, 'PLAN_RESOURCE_BOUND')
        phase('atomic_plan_batches_and_current_receipts')
        conn.writes_enabled=True
        support.create_plan_tables(conn)
        for batch in plan['batches']:
            conn.execute('INSERT INTO '+support.PLAN_TABLES[1]+' VALUES(?,?,?,?,?)',(support.TASK_KEY,batch['batch_key'],batch['record_count'],support.digest(batch),support.canonical(batch)))
        if fail_after_batches:raise ValueError('INJECTED_ROLLBACK')
        for row in fresh:conn.execute('INSERT INTO '+support.RECEIPT_TABLE+' VALUES('+','.join('?' for _ in row)+')',tuple(row.values()))
        header={k:v for k,v in plan.items() if k!='batches'}
        header['batch_hashes']=[{'batch_key':b['batch_key'],'sha256':support.digest(b)} for b in plan['batches']]
        checksum=support.digest(header)
        conn.execute('INSERT INTO '+support.PLAN_TABLES[0]+' VALUES(?,?,?,?,?)',(support.TASK_KEY,plan['state'],checksum,support.canonical(header),plan['created_at']))
        conn.execute('INSERT INTO '+support.PLAN_TABLES[2]+' VALUES(?,?,?,?)',(support.TASK_KEY,'AvailabilityReconciledAndRecoveryBatchesPrepared',support.canonical({'manifest_sha256':checksum,'summary':plan['summary'],'processing_authorized':False}),plan['created_at']))
        support.verify_plan(conn,plan);receipts(conn,approved_header);planning_receipts(conn,fresh)
        require(clock()-started<60,'TRANSACTION_BUDGET')
        COMMIT_ATTEMPTED=1;inner.commit();COMMIT_ACKNOWLEDGED=1
        print('RECOVERY_COMMIT_WINDOW_MS='+str(int((clock()-started)*1000)),flush=True)
        return plan,current_members,current_core
    except Exception:
        inner.rollback();raise
    finally:conn.writes_enabled=False;conn.deadline=None


def verify(conn, plan, approved_header, approved_members, committed_core, *, expected_manifest=MANIFEST):
    verify_baseline(conn,approved_header,approved_members,expected_manifest)
    checksum=support.verify_plan(conn,plan)
    planning_receipts(conn,plan['current_consideration']['receipts'])
    after=baseline.core_snapshot(conn)
    delta=baseline.core_delta(committed_core,after)
    baseline.emit_delta(delta,'RECOVERY_POSTCOMMIT_DRIFT')
    # Current-task search receipts describe their locked commit snapshot. A later
    # review clock or bulk-search metadata refresh cannot authorize processing.
    require(after['represented']==committed_core['represented'],'INDEPENDENT_SOURCE_DRIFT')
    for family,allowed in (('candidates',{'reviewed_at'}),('holds',{'reviewed_at'}),('bulk',{'status','reason','metadata_sha256'})):
        require(delta[family]['added']==delta[family]['removed']==0 and set(delta[family]['fields'])<=allowed,'INDEPENDENT_SOURCE_DRIFT')
    return checksum


def main():
    from database import connect_database
    from salcapa_m365_intake import GovernedM365Config,GovernedM365Intake
    inner=intake=None
    try:
        require(os.getenv('SALUS_DB_BACKEND','').lower()=='postgres','BACKEND_REQUIRED')
        require(bool(re.fullmatch('[1-9][0-9]{5,19}',os.getenv('SALUS_POSTSEARCH_RUN_ID',''))) and bool(re.fullmatch('[0-9a-f]{64}',os.getenv('SALUS_POSTSEARCH_SCRIPT_SHA256',''))),'EXECUTION_BINDING')
        phase('approved_baseline_and_eight_receipts')
        inner=connect_database();conn=baseline.begin_read_only(inner)
        header,members=read_baseline(conn);support.target_empty(conn);planning_receipts(conn)
        inner.close();inner=None
        phase('stable_physical_inventory')
        config=GovernedM365Config.from_environment();intake=GovernedM365Intake(config)
        inventory=support.establish_stable_inventory(intake)
        require(len(inventory)>=23747,'BOUNDARY_BELOW_MINIMUM')
        phase('full_current_corpus_consideration')
        inner=connect_database();conn=baseline.begin_read_only(inner)
        support.verify_membership(conn,inventory)
        core=baseline.core_snapshot(conn);evidence=support.read_evidence(conn)
        families={family:baseline.search_matrix(conn,family=family) for family in ('C','B','H')}
        preview_header,current_members=current_view(evidence,inventory,baseline.combine_families(families),core,config.drive_id)
        approved_scope(members,current_members)
        del current_members,preview_header
        phase("preview_scope_verified")
        inner.close();inner=None
        require(support.acquire_inventory(intake)==inventory,'SOURCE_INVENTORY_CHANGED')
        inner=connect_database()
        owned_context={'evidence':evidence,'families':families,'inventory':inventory,'drive_id':config.drive_id,'preview_core':core,'_transfer_owned':True}
        del evidence,families,core
        plan,committed_members,committed_core=prepare(inner,header,members,None,owned_context)
        inner.close();inner=None
        phase('independent_durable_readback')
        inner=connect_database();conn=baseline.begin_read_only(inner)
        checksum=verify(conn,plan,header,members,committed_core)
        for key,value in {'MANIFEST_SHA256':checksum,'BASELINE_SHA256':MANIFEST,'PREPARED_SOURCES':plan['summary']['prepared_sources'],
                'BATCH_COUNT':len(plan['batches']),'PRESERVED_RECEIPTS':8,'NEW_RECEIPTS':4,'SOURCE_RECORD_WRITES':0,
                'PROCESSING_AUTHORIZED':0,'FRESH_CONNECTION_VERIFIED':1,'PLAN_COMPLETE':1}.items():print('RECOVERY_'+key+'='+str(value),flush=True)
        for key,value in plan['summary']['categories'].items():print('RECOVERY_CATEGORY_'+key.upper()+'='+str(value),flush=True)
        for row,(label,_) in zip(plan['current_consideration']['receipts'],baseline.QUERIES):
            print('RECOVERY_RECEIPT_'+label.upper()+'_ID='+row['receipt_id'],flush=True)
            print('RECOVERY_RECEIPT_'+label.upper()+'_MATCHED='+str(row['matched_count']),flush=True)
    except Exception as exc:
        allowed={'MEMORY_BUDGET','QUERY_DENIED','TRANSACTION_BUDGET','RESOURCE_BOUND','APPROVED_MANIFEST_DRIFT','BASELINE_HEADER_DRIFT','BASELINE_MEMBER_DRIFT','BASELINE_EVENT_DRIFT','BASELINE_MISSING','PRESERVED_RECEIPT_DRIFT','APPROVED_SOURCE_MEMBERSHIP_DRIFT','APPROVED_SOURCE_RIGHTS_VERSION_DRIFT','TASK_RECEIPT_DRIFT','PLANNING_BUSY','PLAN_RESOURCE_BOUND','INDEPENDENT_SOURCE_DRIFT','BACKEND_REQUIRED','EXECUTION_BINDING','BOUNDARY_BELOW_MINIMUM','SOURCE_INVENTORY_CHANGED','MEMBERSHIP_INVALID','DRIVE_SCOPE_DRIFT','AVAILABILITY_DRIFT','UNRESOLVED_SCOPE_DRIFT','SOURCE_IDENTITY_VERSION_DRIFT','SOURCE_COHORT_MEMBERSHIP_DRIFT','REFRESH_SCOPE_EXCEEDED'}
        code=exc.code if isinstance(exc,support.CensusFailure) else str(exc) if str(exc) in allowed else 'UNEXPECTED_FAILURE'
        print('RECOVERY_FAILURE_CODE='+code,flush=True);print('RECOVERY_FAILURE_STAGE='+STAGE,flush=True)
        print('RECOVERY_COMMIT_ATTEMPTED='+str(COMMIT_ATTEMPTED),flush=True)
        print('RECOVERY_COMMIT_ACKNOWLEDGED='+str(COMMIT_ACKNOWLEDGED),flush=True)
        raise SystemExit(1) from None
    finally:
        if inner is not None:inner.close()
        if intake is not None:intake.client.close();intake.credential.close()


if __name__=='__main__':main()
