"""Append-only planning from SAL-D137; never starts processing or changes source state."""
import hashlib
import json
import os
import re
import time
try:
    import salus_baseline_support as baseline
except ImportError:
    from tools import live_knowledge_baseline_proposal as baseline
support = baseline.support
require = baseline.require
PHASE_KEY = 'salus-approved-baseline-recovery-plan-20261115'
ACTOR = 'System Administrator - task consideration ' + PHASE_KEY + ' / '
MANIFEST = '9a662aa94726890dfc7e4845620161ab372d81c2cc27ba8f45d84ee694840821'
AUTHORITY_COMMIT = '0f0d9fa46904e78a36027c4f45a801a7de0f47c8'
STAGE = 'not_started'
COMMIT_ATTEMPTED = COMMIT_ACKNOWLEDGED = 0


def phase(name):
    global STAGE
    STAGE = name
    print('RECOVERY_PHASE=' + name, flush=True)


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


def verify_baseline(conn, header, members, expected_manifest=MANIFEST):
    require(support.digest(header)==expected_manifest, 'APPROVED_MANIFEST_DRIFT')
    rows=conn.execute('SELECT * FROM '+baseline.TABLES[0]+' WHERE operation_key=?',(baseline.KEY,)).fetchall()
    require(len(rows)==1 and rows[0]['manifest_sha256']==expected_manifest and rows[0]['state']==baseline.STATE
            and rows[0]['created_at']==header['created_at'] and rows[0]['payload_json']==support.canonical(header), 'BASELINE_HEADER_DRIFT')
    # SQL hashes every complete stored member, including private provenance, without transferring it again.
    rows=conn.execute('SELECT source_item_id,category,member_sha256,'+baseline.sql_hash(conn,'payload_json')+
        ' payload_sha256 FROM '+baseline.TABLES[1]+' WHERE operation_key=? ORDER BY source_item_id',(baseline.KEY,)).fetchall()
    require(len(rows)==len(members), 'BASELINE_MEMBER_DRIFT')
    expected=[{'source_item_id':m['source_item_id'],'sha256':support.digest(m)} for m in members]
    require(expected==header['member_hashes'], 'BASELINE_MEMBER_DRIFT')
    for row,member,binding in zip(rows,members,expected):
        require(row['source_item_id']==member['source_item_id'] and row['category']==member['category']
                and row['member_sha256']==row['payload_sha256']==binding['sha256'], 'BASELINE_MEMBER_DRIFT')
    event=conn.execute('SELECT * FROM '+baseline.TABLES[2]+' WHERE operation_key=?',(baseline.KEY,)).fetchall()
    expected_event={'manifest_sha256':expected_manifest,'state':baseline.STATE,'processing_authorized':False,
                    'baseline_accepted':False,'member_count':len(members)}
    require(len(event)==1 and event[0]['created_at']==header['created_at'] and event[0]['payload_json']==support.canonical(expected_event), 'BASELINE_EVENT_DRIFT')
    return receipts(conn,header)


def read_baseline(conn, expected_manifest=MANIFEST):
    row=conn.execute('SELECT payload_json FROM '+baseline.TABLES[0]+' WHERE operation_key=?',(baseline.KEY,)).fetchone()
    require(row is not None, 'BASELINE_MISSING')
    header=json.loads(row['payload_json'])
    require(support.digest(header)==expected_manifest, 'APPROVED_MANIFEST_DRIFT')
    members=[json.loads(r['payload_json']) for r in conn.execute('SELECT payload_json FROM '+baseline.TABLES[1]+' WHERE operation_key=? ORDER BY source_item_id',(baseline.KEY,)).fetchall()]
    verify_baseline(conn,header,members,expected_manifest)
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


def scoped_evidence(conn, sources):
    ordered=sorted(sources)
    candidates=[]
    for offset in range(0,len(ordered),100):
        candidates.extend(baseline.candidate_subset(conn,set(ordered[offset:offset+100])))
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
        current_header,current_members=baseline.refresh_current(conn,preview_core,current_core,context)
        sources=approved_scope(approved_members,current_members)
        evidence=scoped_evidence(conn,sources)
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
            'per_source_coverage':[{'source_item_id':m['source_item_id'],'considered_by_queries':m['considered_by_queries'],'matched_queries':m['matched_queries']} for m in current_members],
            'approved_scope_current_sha256':support.digest([critical(m) for m in current_members if m['source_item_id'] in sources]),
            'github_run_id':os.getenv('SALUS_POSTSEARCH_RUN_ID','fixture'),'script_sha256':os.getenv('SALUS_POSTSEARCH_SCRIPT_SHA256','fixture')})
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
        _,current_members=baseline.build_proposal(evidence,inventory,baseline.combine_families(families),core,config.drive_id)
        approved_scope(members,current_members)
        inner.close();inner=None
        require(support.acquire_inventory(intake)==inventory,'SOURCE_INVENTORY_CHANGED')
        inner=connect_database()
        plan,committed_members,committed_core=prepare(inner,header,members,core,{'evidence':evidence,'families':families,'inventory':inventory,'drive_id':config.drive_id})
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
        allowed={'QUERY_DENIED','TRANSACTION_BUDGET','RESOURCE_BOUND','APPROVED_MANIFEST_DRIFT','BASELINE_HEADER_DRIFT','BASELINE_MEMBER_DRIFT','BASELINE_EVENT_DRIFT','BASELINE_MISSING','PRESERVED_RECEIPT_DRIFT','APPROVED_SOURCE_MEMBERSHIP_DRIFT','APPROVED_SOURCE_RIGHTS_VERSION_DRIFT','TASK_RECEIPT_DRIFT','PLANNING_BUSY','PLAN_RESOURCE_BOUND','INDEPENDENT_SOURCE_DRIFT','BACKEND_REQUIRED','EXECUTION_BINDING','BOUNDARY_BELOW_MINIMUM','SOURCE_INVENTORY_CHANGED','MEMBERSHIP_INVALID','DRIVE_SCOPE_DRIFT','AVAILABILITY_DRIFT','UNRESOLVED_SCOPE_DRIFT','SOURCE_IDENTITY_VERSION_DRIFT','SOURCE_COHORT_MEMBERSHIP_DRIFT','REFRESH_SCOPE_EXCEEDED'}
        code=exc.code if isinstance(exc,support.CensusFailure) else str(exc) if str(exc) in allowed else 'UNEXPECTED_FAILURE'
        print('RECOVERY_FAILURE_CODE='+code,flush=True);print('RECOVERY_FAILURE_STAGE='+STAGE,flush=True)
        print('RECOVERY_COMMIT_ATTEMPTED='+str(COMMIT_ATTEMPTED),flush=True)
        print('RECOVERY_COMMIT_ACKNOWLEDGED='+str(COMMIT_ACKNOWLEDGED),flush=True)
        raise SystemExit(1) from None
    finally:
        if inner is not None:inner.close()
        if intake is not None:intake.client.close();intake.credential.close()


if __name__=='__main__':main()
