"""Source-correlated current baseline proposal; approval and processing stay separate."""
from __future__ import annotations
import hashlib
import json
import os
import re
import time
import uuid
from datetime import datetime, timezone

try:
    import salus_postsearch_support as support
except ModuleNotFoundError:
    from tools import live_knowledge_postsearch_resume as support

KEY = 'salus-current-recovery-baseline-proposal-20261115'
PHASE_KEY = 'salus-current-recovery-baseline-refresh-20261115'
MAX_REFRESH_SOURCES = 100
ACTOR = 'System Administrator - task consideration ' + KEY + ' / '
STATE = 'Proposed - Awaiting Baseline Approval'
TABLES = ('m365_knowledge_baseline_proposals', 'm365_knowledge_baseline_members',
          'm365_knowledge_baseline_events')
EXPECTED = {'governed_review':7085, 'retry_paused':733, 'automatic_retry':512,
            'governed_hold':93, 'other_or_conflicting':5, 'complete_without_text':0, 'no_candidate':2}
QUERIES = (
    ('membership', 'recovery baseline source membership represented current historical archive version provenance'),
    ('coverage', 'knowledge corpus consideration query content metadata unavailable supportive qualifying'),
    ('contrary', 'hold restriction rights conflict unsafe contrary retry paused failure missing'),
    ('verification', 'baseline proposal receipt audit independent verification stability cleanup approval'))
DDL = (
    'CREATE TABLE IF NOT EXISTS m365_knowledge_baseline_proposals (operation_key TEXT PRIMARY KEY, state TEXT NOT NULL, manifest_sha256 TEXT NOT NULL, payload_json TEXT NOT NULL, created_at TEXT NOT NULL)',
    'CREATE TABLE IF NOT EXISTS m365_knowledge_baseline_members (operation_key TEXT NOT NULL, source_item_id TEXT NOT NULL, category TEXT NOT NULL, member_sha256 TEXT NOT NULL, payload_json TEXT NOT NULL, PRIMARY KEY(operation_key,source_item_id))',
    'CREATE TABLE IF NOT EXISTS m365_knowledge_baseline_events (operation_key TEXT PRIMARY KEY, payload_json TEXT NOT NULL, created_at TEXT NOT NULL)')
STAGE = 'not_started'
COMMIT_ATTEMPTED = COMMIT_ACKNOWLEDGED = 0


def require(ok, code):
    if not ok:
        raise ValueError(code)


def phase(value):
    global STAGE
    STAGE = value
    print('BASELINE_PHASE=' + value, flush=True)
    print('BASELINE_PHASE_AT=' + datetime.now(timezone.utc).isoformat(), flush=True)


class ProposalConnection:
    """Allow reviewed reads, and append-only writes to the named proposal/receipt tables."""
    def __init__(self, inner):
        self.inner = inner
        self.backend = getattr(inner, 'backend', 'sqlite')
        self.writes_enabled = False
        self.deadline = None
        self.clock = time.monotonic

    def execute(self, sql, params=()):
        clean = re.sub(r"'(?:''|[^'])*'", "''", sql).strip().rstrip(';').strip()
        require(';' not in clean and '--' not in clean and '/*' not in clean, 'QUERY_DENIED')
        upper = clean.upper()
        words = set(re.findall('[A-Z_]+', upper))
        reads = upper.startswith(('SELECT ', 'WITH ')) and not words.intersection(
            {'INSERT','UPDATE','DELETE','MERGE','CREATE','ALTER','DROP','TRUNCATE','COPY','CALL','INTO','LOCK'})
        writes = self.writes_enabled and (sql in DDL or bool(re.fullmatch(
            r'INSERT INTO (?:' + '|'.join((*TABLES, support.RECEIPT_TABLE)) + r') VALUES\([?,()]+\)', sql)))
        require(reads or writes, 'QUERY_DENIED')
        if self.deadline is not None:
            remaining = self.deadline - self.clock()
            require(remaining > 0, 'TRANSACTION_BUDGET')
            if self.backend == 'postgres':
                self.inner.execute("SET LOCAL statement_timeout='" + str(max(1,min(30000,int(remaining*1000)))) + "ms'")
        return self.inner.execute(sql, params)


def begin_read_only(inner):
    if getattr(inner,'backend','sqlite') == 'postgres':
        inner.execute('SET TRANSACTION ISOLATION LEVEL REPEATABLE READ READ ONLY')
        inner.execute("SET LOCAL statement_timeout='120s'")
    else:
        inner.execute('PRAGMA query_only=ON')
        inner.execute('BEGIN')
    return ProposalConnection(inner)


def exists(conn, table):
    require(table in TABLES, 'TABLE_SCOPE')
    if conn.backend == 'postgres':
        return bool(conn.execute('SELECT to_regclass(?)',(table,)).fetchone()[0])
    return bool(conn.execute("SELECT name FROM sqlite_master WHERE type='table' AND name=?",(table,)).fetchone())


def empty_target(conn):
    support.preserved_receipts(conn)
    support.target_empty(conn)
    for table in TABLES:
        require(not exists(conn,table) or conn.execute('SELECT COUNT(*) FROM '+table+' WHERE operation_key=?',(KEY,)).fetchone()[0] == 0, 'PROPOSAL_ALREADY_PRESENT')
    require(conn.execute('SELECT COUNT(*) FROM '+support.RECEIPT_TABLE+' WHERE actor LIKE ?',(ACTOR+'%',)).fetchone()[0] == 0, 'NEW_RECEIPTS_ALREADY_PRESENT')


def sql_hash(conn, expr):
    expr = "COALESCE(" + expr + ",'')"
    return ("encode(sha256(convert_to("+expr+",'UTF8')),'hex')" if conn.backend=='postgres' else 'sha256text('+expr+')')


def core_snapshot(conn):
    """No JSON parsing or text transfer: hash all search inputs and source/rights fields."""
    candidates = [dict(r) for r in conn.execute('SELECT id,source_drive_id,source_item_id,source_etag,source_sha256,source_size,source_modified_at,source_archive_item_id,source_archive_etag,source_archived_at,status,decision,reviewed_at,reviewed_by,review_rationale,destination_item_id,destination_etag,source_removed_at,source_name,source_relative_path,source_owner,target_folder,' + sql_hash(conn,'classification_json') + ' classification_sha256 FROM m365_knowledge_candidates ORDER BY id').fetchall()]
    holds = [dict(r) for r in conn.execute("SELECT source_drive_id,source_item_id,source_parent_id,source_etag,source_size,source_modified_at,source_area,status,hold_reason,research_disposition,teaching_disposition,citation_disposition,reviewed_by,reviewed_at,review_rationale,source_name,source_relative_path FROM m365_knowledge_holds WHERE status='Governed Hold' ORDER BY source_drive_id,source_item_id").fetchall()]
    # The deployed search includes Removed file rows when another representation
    # keeps their source in the union. Bind those search inputs too.
    bulk = [dict(r) for r in conn.execute("SELECT drive_id,pending_id,item_id,parent_id,etag,size,status,reason,name," + sql_hash(conn,'metadata_json') + " metadata_sha256 FROM m365_bulk_items WHERE kind='file' AND item_id IN (SELECT source_item_id FROM m365_knowledge_candidates UNION SELECT source_item_id FROM m365_knowledge_holds WHERE status='Governed Hold' UNION SELECT item_id FROM m365_bulk_items WHERE kind='file' AND status<>'Removed') ORDER BY drive_id,pending_id,item_id").fetchall()]
    require(all(len(rows)<=150000 for rows in (candidates,holds,bulk)), 'RESOURCE_BOUND')
    return {'candidates':candidates,'holds':holds,'bulk':bulk,'represented':sorted(support.represented_ids(conn))}


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


def combine_families(families):
    keys=set(families['C'])
    require(all(set(families[k])==keys for k in ('B','H')), 'COVERAGE_INVALID')
    return {s:[max(families[k][s][i] for k in ('C','B','H')) for i in range(len(QUERIES))] for s in sorted(keys)}


def membership_signature(evidence):
    rows={}
    for row in evidence['candidates']:rows.setdefault(row['source_item_id'],[]).append(row)
    held={r['source_item_id'] for r in evidence['holds']}
    available={s for s,versions in rows.items() if any(r['legacy_complete'] for r in versions)}
    exact={s for s,versions in rows.items() if any(r['extraction_status']=='Complete' and r['has_text'] for r in versions)}
    exceptions=available-exact
    return {s:('legacy_available' if s in available else support.cohort(rows.get(s,[]),s in held),s in exceptions,s in exact)
            for s in evidence['represented']}


def core_delta(before, after):
    specs={'candidates':('id',),'holds':('source_drive_id','source_item_id'),
           'bulk':('drive_id','pending_id','item_id')}
    result={}
    for table,keys in specs.items():
        left={tuple(r[k] for k in keys):r for r in before[table]}
        right={tuple(r[k] for k in keys):r for r in after[table]}
        rows=[];fields={}
        for key in sorted(left.keys()|right.keys()):
            a,b=left.get(key),right.get(key)
            if a==b:continue
            changed=sorted(k for k in (a or {}).keys()|(b or {}).keys() if (a or {}).get(k)!=(b or {}).get(k))
            for field in changed:fields[field]=fields.get(field,0)+1
            row=b or a
            rows.append({'key':list(key),'source_item_id':row.get('source_item_id',row.get('item_id')),
                         'before_sha256':support.digest(a),'after_sha256':support.digest(b),'fields':changed})
        result[table]={'added':len(right.keys()-left.keys()),'removed':len(left.keys()-right.keys()),
                       'changed':len(rows),'fields':fields,'rows':rows}
    result['represented_added']=len(set(after['represented'])-set(before['represented']))
    result['represented_removed']=len(set(before['represented'])-set(after['represented']))
    return result


def emit_delta(delta, prefix='BASELINE_DRIFT'):
    for table in ('candidates','holds','bulk'):
        for kind in ('added','removed','changed'):
            print(prefix+'_'+table.upper()+'_'+kind.upper()+'='+str(delta[table][kind]),flush=True)
        for field,count in sorted(delta[table]['fields'].items()):
            print(prefix+'_'+table.upper()+'_FIELD_'+field.upper()+'='+str(count),flush=True)
    for kind in ('represented_added','represented_removed'):
        print(prefix+'_'+kind.upper()+'='+str(delta[kind]),flush=True)


def candidate_subset(conn, sources):
    if not sources:return []
    require(len(sources)<=MAX_REFRESH_SOURCES,'REFRESH_SCOPE_EXCEEDED')
    parameters=tuple(sorted(sources));where='source_item_id IN ('+','.join('?' for _ in parameters)+')'
    postgres=conn.backend=='postgres'
    prefix=("WITH decoded AS MATERIALIZED (SELECT id,classification_json::jsonb doc,"+sql_hash(conn,'classification_json')+" classification_sha256,CASE WHEN classification_json LIKE '%\"status\": \"Complete\"%' THEN 1 ELSE 0 END legacy_complete FROM m365_knowledge_candidates WHERE "+where+") " if postgres else '')
    text_expr=support.scalar(conn,'extraction,text')
    whitespace="char(32)||char(9)||char(10)||char(13)||char(11)||char(12)"
    if postgres:whitespace=whitespace.replace('char(','chr(')
    trim=('btrim(' if postgres else 'trim(')+text_expr+','+whitespace+')'
    fields={'extraction_status':'extraction,status','failure_code':'extraction,failure_code','retry_eligible':'extraction,retry_eligible','automatic_retry_paused':'extraction,automatic_retry_paused','disposition':'extraction,disposition','disposition_reason':'extraction,disposition_reason'}
    query=prefix+'SELECT c.id,c.source_drive_id,c.source_item_id,c.source_etag,c.source_sha256,c.source_size,c.source_modified_at,c.source_archive_item_id,c.source_archive_etag,c.source_archived_at,c.status,c.decision,c.reviewed_at,c.reviewed_by,c.review_rationale,c.destination_item_id,c.destination_etag,c.source_removed_at,'+('p.classification_sha256' if postgres else sql_hash(conn,'c.classification_json'))+' classification_sha256,'+','.join(support.scalar(conn,path)+' '+name for name,path in fields.items())+',CASE WHEN LENGTH(TRIM('+text_expr+'))>0 THEN 1 ELSE 0 END has_text,CASE WHEN '+support.json_type(conn,'extraction,text')+"='"+('string' if postgres else 'text')+"' AND LENGTH("+trim+")>0 THEN 1 ELSE 0 END strict_text,"+('p.legacy_complete' if postgres else "CASE WHEN c.classification_json LIKE '%\"status\": \"Complete\"%' THEN 1 ELSE 0 END")+' legacy_complete FROM m365_knowledge_candidates c'+(' JOIN decoded p ON p.id=c.id' if postgres else ' WHERE c.'+where)+' ORDER BY c.id'
    return [dict(r) for r in conn.execute(query,parameters).fetchall()]


def refresh_current(conn, before, current, context):
    delta=core_delta(before,current);emit_delta(delta)
    require(before['represented']==current['represented'],'SOURCE_IDENTITY_VERSION_DRIFT')
    mutable={'candidates':{'classification_sha256','status','decision','reviewed_at','reviewed_by','review_rationale','target_folder'},
             'holds':{'hold_reason','research_disposition','teaching_disposition','citation_disposition','reviewed_by','reviewed_at','review_rationale'},
             'bulk':{'status','reason','metadata_sha256'}}
    for table in ('candidates','holds','bulk'):
        require(delta[table]['added']==delta[table]['removed']==0 and set(delta[table]['fields'])<=mutable[table], 'SOURCE_IDENTITY_VERSION_DRIFT')
    sources={r['source_item_id'] for r in delta['candidates']['rows']}
    require(len(sources)<=MAX_REFRESH_SOURCES,'REFRESH_SCOPE_EXCEEDED')
    evidence={**context['evidence'],'holds':current['holds'],'represented':current['represented']}
    rows=candidate_subset(conn,sources)
    evidence['candidates']=sorted([r for r in evidence['candidates'] if r['source_item_id'] not in sources]+rows,key=lambda r:r['id'])
    families={k:dict(v) for k,v in context['families'].items()}
    if sources:families['C'].update(search_matrix(conn,family='C',source_ids=sources))
    # Metadata families are cheap and are always fully refreshed under the locks;
    # unchanged candidate search inputs alone reuse their proven snapshot flags.
    for family in ('B','H'):families[family]=search_matrix(conn,family=family)
    header,members=build_proposal(evidence,context['inventory'],combine_families(families),current,context['drive_id'],
        expected=context.get('expected',EXPECTED),expected_exceptions=context.get('expected_exceptions',5),emit_observed=True)
    require(membership_signature(context['evidence'])=={m['source_item_id']:(m['category'],m['availability_exception'],m['exact_complete_text']) for m in members},'SOURCE_COHORT_MEMBERSHIP_DRIFT')
    header['execution_phase_key']=PHASE_KEY
    header['prior_failed_run_id']=43765713976
    header['locked_refresh']={'preview_core_sha256':support.digest(before),'committed_core_sha256':support.digest(current),
        'candidate_sources_refreshed':len(sources),'maximum_candidate_sources':MAX_REFRESH_SOURCES,'delta':delta,
        'unchanged_candidate_search_flags_reused':True,'bulk_and_hold_flags_refreshed':True}
    return header,members


def build_proposal(evidence, inventory, matrix, core, drive_id, *, expected=EXPECTED, expected_exceptions=5, emit_observed=False):
    represented = set(evidence['represented'])
    require(set(inventory)<=represented and represented==set(matrix)==set(core['represented']), 'MEMBERSHIP_INVALID')
    require(all(r['source_drive_id']==drive_id for r in (*core['candidates'],*core['holds'])) and
            all(r['drive_id']==drive_id for r in core['bulk']), 'DRIVE_SCOPE_DRIFT')
    candidates, holds, bulk, provenance = {}, {}, {}, {}
    for r in evidence['candidates']: candidates.setdefault(r['source_item_id'],[]).append(r)
    for r in core['candidates']: provenance.setdefault(r['source_item_id'],[]).append(r)
    for r in core['holds']: holds.setdefault(r['source_item_id'],[]).append(r)
    for r in core['bulk']: bulk.setdefault(r['item_id'],[]).append(r)
    available = {s for s,rows in candidates.items() if any(r['legacy_complete'] for r in rows)}
    exact = {s for s,rows in candidates.items() if any(r['extraction_status']=='Complete' and r['has_text'] for r in rows)}
    strict = {s for s,rows in candidates.items() if any(r['extraction_status']=='Complete' and r['strict_text'] for r in rows)}
    exceptions=available-exact
    if emit_observed:
        for key,value in {'REPRESENTED':len(represented),'LEGACY_AVAILABLE':len(available),'UNRESOLVED':len(represented-available),'EXACT_TEXT':len(exact),'STRICT_TEXT':len(strict),'AVAILABILITY_EXCEPTIONS':len(available-exact)}.items():
            print('BASELINE_OBSERVED_'+key+'='+str(value),flush=True)
    require(exact==strict and not exact-available and len(available-exact)==expected_exceptions, 'AVAILABILITY_DRIFT')
    counts = {k:0 for k in support.CATEGORIES}
    members = []
    for source in sorted(represented):
        category = 'legacy_available' if source in available else support.cohort(candidates.get(source,[]),source in holds)
        if source not in available: counts[category] += 1
        versions = [{k:v for k,v in row.items() if k!='checkpoint'} for row in candidates.get(source,[])]
        member = {'source_item_id':source,'source_drive_id':drive_id,'category':category,
                  'candidate_state':'Unvetted Candidate','processing_authorized':False,
                  'current_source':inventory.get(source),'current_inventory_member':source in inventory,
                  'candidate_versions':versions,'candidate_source_provenance':provenance.get(source,[]),
                  'holds':holds.get(source,[]),'bulk_provenance':bulk.get(source,[]),
                  'availability_exception':source in exceptions,'exact_complete_text':source in exact,
                  'considered_by_queries':[label for label,_ in QUERIES],
                  'matched_queries':[label for index,(label,_) in enumerate(QUERIES) if matrix[source][index]],
                  'content_reviewed_or_qualified_by_task':False}
        members.append(member)
    if emit_observed:
        for key,value in counts.items():print('BASELINE_OBSERVED_CATEGORY_'+key.upper()+'='+str(value),flush=True)
    require(counts==expected and sum(counts.values())==len(represented-available), 'UNRESOLVED_SCOPE_DRIFT')
    created = datetime.now(timezone.utc).isoformat()
    receipts = []
    for index,(label,query) in enumerate(QUERIES):
        receipts.append({'receipt_id':str(uuid.uuid4()),'query_sha256':hashlib.sha256(query.strip().encode()).hexdigest(),
                         'boundary_count':len(inventory),'considered_count':len(represented),
                         'matched_count':sum(v[index] for v in matrix.values()),'content_available_count':len(available),
                         'metadata_only_count':len(represented-available),'governed_hold_count':len(holds),
                         'actor':ACTOR+label,'created_at':created})
    header = {'operation_key':KEY,'state':STATE,'created_at':created,'baseline_accepted':False,
              'processing_authorized':False,'candidate_state':'Unvetted Candidate','physical_files':len(inventory),
              'represented_files':len(represented),'unresolved_files':len(represented-available),'categories':counts,
              'legacy_available':len(available),'exact_complete_text':len(exact),'availability_exceptions':len(available-exact),
              'represented_not_in_current_inventory':len(represented-set(inventory)),
              'inventory_sha256':support.snapshot_digest(inventory),'core_sha256':support.digest(core),
              'search_matrix_sha256':support.digest(matrix),'recovery_projection_sha256':support.baseline_digest(evidence),
              'member_hashes':[{'source_item_id':m['source_item_id'],'sha256':support.digest(m)} for m in members],
              'original_receipts':support.EXPECTED_RECEIPTS,'original_receipt_snapshot_sha256':'cbb850ab8dd3a06e300b5ce2edc40764efc821a9f2fa25d4beca73d6319c01af',
              'new_receipts':receipts,'queries':[{'label':l,'query':q} for l,q in QUERIES],
              'historical_membership_reconstructed':False,'historical_membership_gap':'No source-correlated original-window manifest was located in inspected authorized task evidence; aggregate hashes and counts cannot reconstruct it.',
              'reference_diagnostic_run':43761349512,'reference_diagnostic_projection':'6f0da7b4a7181cc56f96828cf9cf73e5143488b2911fa56dfd62acbd6c981058',
              'restricted_chat_ref':{'thread_id':'01a1dccc-3c40-7c60-b6eb-f9836bd1332e','turn_id':'01a1e111-4697-78f0-b71d-a0aa300005dc','user_message_id':'01a1e111-4740-7141-849a-287525d661d1'},
              'execution_run_id':os.getenv('SALUS_POSTSEARCH_RUN_ID',''),'script_sha256':os.getenv('SALUS_POSTSEARCH_SCRIPT_SHA256',''),
              'repository_source_copy_in_library':False,'chat_export_backfill_complete':False}
    return header,members


def verify_saved(conn, header, members):
    support.preserved_receipts(conn)
    support.target_empty(conn)
    saved = conn.execute('SELECT * FROM '+TABLES[0]+' WHERE operation_key=?',(KEY,)).fetchall()
    require(len(saved)==1 and saved[0]['state']==STATE and saved[0]['payload_json']==support.canonical(header)
            and saved[0]['manifest_sha256']==support.digest(header), 'PROPOSAL_READBACK')
    rows = conn.execute('SELECT * FROM '+TABLES[1]+' WHERE operation_key=? ORDER BY source_item_id',(KEY,)).fetchall()
    require(len(rows)==len(members), 'MEMBER_READBACK')
    for row,member in zip(rows,members):
        require(row['source_item_id']==member['source_item_id'] and row['category']==member['category']
                and row['payload_json']==support.canonical(member) and row['member_sha256']==support.digest(member), 'MEMBER_READBACK')
    new = [dict(r) for r in conn.execute('SELECT * FROM '+support.RECEIPT_TABLE+' WHERE actor LIKE ? ORDER BY actor',(ACTOR+'%',)).fetchall()]
    require(new==sorted(header['new_receipts'],key=lambda r:r['actor']), 'NEW_RECEIPT_READBACK')
    event = conn.execute('SELECT * FROM '+TABLES[2]+' WHERE operation_key=?',(KEY,)).fetchall()
    expected = {'manifest_sha256':support.digest(header),'state':STATE,'processing_authorized':False,'baseline_accepted':False,'member_count':len(members)}
    require(len(event)==1 and event[0]['payload_json']==support.canonical(expected) and event[0]['created_at']==header['created_at'], 'EVENT_READBACK')


def commit_proposal(inner, header, members, core, *, fail_after_members=False, clock=time.monotonic, refresh=None):
    global COMMIT_ATTEMPTED,COMMIT_ACKNOWLEDGED
    COMMIT_ATTEMPTED=COMMIT_ACKNOWLEDGED=0
    conn=ProposalConnection(inner)
    conn.deadline=clock()+60
    conn.clock=clock
    started=clock()
    try:
        if conn.backend=='postgres':
            inner.execute("SET LOCAL lock_timeout='2s'")
            inner.execute("SET LOCAL statement_timeout='30s'")
            require(inner.execute('SELECT pg_try_advisory_xact_lock(674160041245)').fetchone()[0], 'PLANNING_BUSY')
            inner.execute('LOCK TABLE m365_knowledge_candidates,m365_knowledge_holds,m365_bulk_items,'+support.RECEIPT_TABLE+' IN SHARE MODE NOWAIT')
        else:
            inner.execute('BEGIN IMMEDIATE')
        empty_target(conn)
        current=core_snapshot(conn)
        if refresh is None:
            require(current==core,'SOURCE_OR_SEARCH_INPUT_DRIFT')
        else:
            phase('locked_current_metadata_refresh')
            header,members=refresh_current(conn,core,current,refresh)
            phase('atomic_proposal_and_receipt_write')
        conn.writes_enabled=True
        for sql in DDL: conn.execute(sql)
        for receipt in header['new_receipts']:
            conn.execute('INSERT INTO '+support.RECEIPT_TABLE+' VALUES('+','.join('?' for _ in receipt)+')',tuple(receipt.values()))
        conn.execute('INSERT INTO '+TABLES[0]+' VALUES(?,?,?,?,?)',(KEY,STATE,support.digest(header),support.canonical(header),header['created_at']))
        for offset in range(0,len(members),100):
            group=members[offset:offset+100]
            values=[]
            for member in group: values.extend((KEY,member['source_item_id'],member['category'],support.digest(member),support.canonical(member)))
            conn.execute('INSERT INTO '+TABLES[1]+' VALUES'+','.join('(?,?,?,?,?)' for _ in group),tuple(values))
        if fail_after_members: raise ValueError('INJECTED_ROLLBACK')
        event={'manifest_sha256':support.digest(header),'state':STATE,'processing_authorized':False,'baseline_accepted':False,'member_count':len(members)}
        conn.execute('INSERT INTO '+TABLES[2]+' VALUES(?,?,?)',(KEY,support.canonical(event),header['created_at']))
        verify_saved(conn,header,members)
        require(clock()-started<60,'TRANSACTION_BUDGET')
        COMMIT_ATTEMPTED=1
        inner.commit()
        COMMIT_ACKNOWLEDGED=1
        print('BASELINE_COMMIT_WINDOW_MS='+str(int((clock()-started)*1000)),flush=True)
        return header,members,current
    except Exception:
        inner.rollback()
        raise


def main():
    from database import connect_database
    from salcapa_m365_intake import GovernedM365Config,GovernedM365Intake
    require(os.getenv('SALUS_DB_BACKEND','').lower()=='postgres','BACKEND_REQUIRED')
    require(bool(re.fullmatch('[1-9][0-9]{5,19}',os.getenv('SALUS_POSTSEARCH_RUN_ID',''))) and
            bool(re.fullmatch('[0-9a-f]{64}',os.getenv('SALUS_POSTSEARCH_SCRIPT_SHA256',''))),'EXECUTION_BINDING')
    inner=intake=None
    try:
        phase('original_receipts_and_empty_target')
        inner=connect_database()
        empty_target(begin_read_only(inner))
        inner.close();inner=None
        phase('stable_physical_inventory')
        config=GovernedM365Config.from_environment()
        intake=GovernedM365Intake(config)
        inventory=support.establish_stable_inventory(intake)
        require(len(inventory)>=23747,'BOUNDARY_BELOW_MINIMUM')
        phase('consistent_current_metadata_and_full_search')
        inner=connect_database()
        conn=begin_read_only(inner)
        empty_target(conn)
        support.verify_membership(conn,inventory)
        core=core_snapshot(conn)
        evidence=support.read_evidence(conn)
        families={family:search_matrix(conn,family=family) for family in ('C','B','H')}
        matrix=combine_families(families)
        header,members=build_proposal(evidence,inventory,matrix,core,config.drive_id,emit_observed=True)
        inner.close();inner=None
        phase('final_physical_inventory')
        final=support.acquire_inventory(intake)
        require(final==inventory,'SOURCE_INVENTORY_CHANGED')
        phase('bounded_atomic_proposal_and_receipts')
        inner=connect_database()
        header,members,committed_core=commit_proposal(inner,header,members,core,refresh={
            'evidence':evidence,'families':families,'inventory':inventory,'drive_id':config.drive_id})
        inner.close();inner=None
        phase('independent_durable_readback')
        inner=connect_database()
        conn=begin_read_only(inner)
        verify_saved(conn,header,members)
        after=core_snapshot(conn)
        if after!=committed_core:
            emit_delta(core_delta(committed_core,after),'BASELINE_POSTCOMMIT_DRIFT')
            raise ValueError('INDEPENDENT_SOURCE_DRIFT')
        require(header.get('execution_phase_key')==PHASE_KEY,'EXECUTION_BINDING')
        print('BASELINE_LOCKED_REFRESH_VERIFIED=1',flush=True)
        print('BASELINE_CANDIDATE_SOURCES_REFRESHED='+str(header['locked_refresh']['candidate_sources_refreshed']),flush=True)
        for key,value in {'REPRESENTED_FILES':header['represented_files'],'PHYSICAL_FILES':header['physical_files'],
                          'UNRESOLVED_FILES':header['unresolved_files'],'MEMBER_ROWS':len(members),
                          'MANIFEST_SHA256':support.digest(header),'CORE_SHA256':header['core_sha256'],
                          'SEARCH_MATRIX_SHA256':header['search_matrix_sha256'],'INVENTORY_SHA256':header['inventory_sha256'],
                          'PRESERVED_RECEIPTS':4,'NEW_RECEIPTS':4,'SOURCE_RECORD_WRITES':0,
                          'BASELINE_ACCEPTED':0,'PROCESSING_AUTHORIZED':0,'RECOVERY_BATCHES_PREPARED':0,
                          'HISTORICAL_MEMBERSHIP_RECONSTRUCTED':0,'FRESH_CONNECTION_VERIFIED':1,'PROPOSAL_COMPLETE':1}.items():
            print('BASELINE_'+key+'='+str(value),flush=True)
        for row in header['new_receipts']:
            label=row['actor'].removeprefix(ACTOR).upper()
            print('BASELINE_RECEIPT_'+label+'_ID='+row['receipt_id'],flush=True)
            print('BASELINE_RECEIPT_'+label+'_MATCHED='+str(row['matched_count']),flush=True)
            print('BASELINE_RECEIPT_'+label+'_QUERY_SHA256='+row['query_sha256'],flush=True)
        for key,value in header['categories'].items(): print('BASELINE_CATEGORY_'+key.upper()+'='+str(value),flush=True)
    except Exception as exc:
        allowed={'QUERY_DENIED','TABLE_SCOPE','RESOURCE_BOUND','DUPLICATE_MEMBERSHIP','COVERAGE_INVALID','MEMBERSHIP_INVALID','DRIVE_SCOPE_DRIFT','AVAILABILITY_DRIFT','UNRESOLVED_SCOPE_DRIFT','PROPOSAL_ALREADY_PRESENT','NEW_RECEIPTS_ALREADY_PRESENT','SOURCE_OR_SEARCH_INPUT_DRIFT','SOURCE_IDENTITY_VERSION_DRIFT','SOURCE_COHORT_MEMBERSHIP_DRIFT','REFRESH_SCOPE_EXCEEDED','PROPOSAL_READBACK','MEMBER_READBACK','NEW_RECEIPT_READBACK','EVENT_READBACK','TRANSACTION_BUDGET','PLANNING_BUSY','SOURCE_INVENTORY_CHANGED','BOUNDARY_BELOW_MINIMUM','INDEPENDENT_SOURCE_DRIFT','EXECUTION_BINDING'}
        code=exc.code if isinstance(exc,support.CensusFailure) else str(exc) if str(exc) in allowed else 'UNEXPECTED_FAILURE'
        state=getattr(exc,'sqlstate','')
        if not isinstance(state,str) or not re.fullmatch('[A-Z0-9]{5}',state):state='UNAVAILABLE'
        print('BASELINE_FAILURE_CODE='+code,flush=True)
        print('BASELINE_FAILURE_STAGE='+STAGE,flush=True)
        print('BASELINE_SQLSTATE='+state,flush=True)
        print('BASELINE_COMMIT_ATTEMPTED='+str(COMMIT_ATTEMPTED),flush=True)
        print('BASELINE_COMMIT_ACKNOWLEDGED='+str(COMMIT_ACKNOWLEDGED),flush=True)
        raise SystemExit(1) from None
    finally:
        if inner is not None:inner.close()
        if intake is not None:
            intake.client.close();intake.credential.close()


if __name__=='__main__':main()
