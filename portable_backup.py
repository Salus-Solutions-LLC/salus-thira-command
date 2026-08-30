import json
from database import ID_TABLES, is_postgres

ASSESSMENT_TABLES = [
    'threats','scenarios','capabilities','evidence','gaps','improvements','decisions',
    'reassessment_triggers','evidence_attachments','entity_versions','scope_changes','workflow_events'
]
RESTORE_ORDER = [
    'users','assessments','assessment_access','threats','scenarios','capabilities','evidence',
    'gaps','improvements','decisions','reassessment_triggers','assessment_weights',
    'evidence_attachments','entity_versions','scope_changes','workflow_events','audit_log','security_events'
]

def _rows(conn, sql, params=()):
    return [dict(r) for r in conn.execute(sql, params)]

def collect_tenant_records(conn, tenant_id:int):
    records={}
    records['tenants']=_rows(conn,'SELECT * FROM tenants WHERE id=?',(tenant_id,))
    records['users']=_rows(conn,'SELECT * FROM users WHERE tenant_id=? ORDER BY id',(tenant_id,))
    records['assessments']=_rows(conn,'SELECT * FROM assessments WHERE tenant_id=? ORDER BY id',(tenant_id,))
    assessment_ids=[r['id'] for r in records['assessments']]
    user_ids=[r['id'] for r in records['users']]
    if assessment_ids:
        marks=','.join('?'*len(assessment_ids)); P=tuple(assessment_ids)
        for table in ASSESSMENT_TABLES:
            records[table]=_rows(conn,f'SELECT * FROM {table} WHERE assessment_id IN ({marks}) ORDER BY id',P)
        records['assessment_weights']=_rows(conn,f'SELECT * FROM assessment_weights WHERE assessment_id IN ({marks}) ORDER BY assessment_id',P)
    else:
        for table in ASSESSMENT_TABLES: records[table]=[]
        records['assessment_weights']=[]
    if user_ids or assessment_ids:
        clauses=[]; params=[]
        if user_ids:
            marks=','.join('?'*len(user_ids)); clauses.append(f'user_id IN ({marks})'); params.extend(user_ids)
        if assessment_ids:
            marks=','.join('?'*len(assessment_ids)); clauses.append(f'assessment_id IN ({marks})'); params.extend(assessment_ids)
        records['assessment_access']=_rows(conn,'SELECT * FROM assessment_access WHERE '+' OR '.join(clauses)+' ORDER BY id',tuple(params))
    else: records['assessment_access']=[]
    records['audit_log']=_rows(conn,'SELECT * FROM audit_log WHERE tenant_id=? ORDER BY id',(tenant_id,))
    records['security_events']=_rows(conn,'SELECT * FROM security_events WHERE tenant_id=? ORDER BY id',(tenant_id,))
    return records

def validate_records(records, tenant_id:int|None=None):
    errors=[]
    required={'tenants','users','assessments','threats','scenarios','capabilities','evidence','gaps','improvements','decisions','audit_log'}
    missing=sorted(required-set(records))
    if missing: errors.append('Missing required record sets: '+', '.join(missing))
    tenants=records.get('tenants',[])
    if len(tenants)!=1: errors.append(f'Expected exactly one tenant record; found {len(tenants)}')
    elif tenant_id is not None and int(tenants[0].get('id',-1))!=int(tenant_id): errors.append('Tenant ID does not match backup manifest')
    assessments={int(r['id']) for r in records.get('assessments',[]) if r.get('id') is not None}
    if not assessments: errors.append('Recovery records contain no assessments')
    for table in ASSESSMENT_TABLES:
        for row in records.get(table,[]):
            if int(row.get('assessment_id',-1)) not in assessments: errors.append(f'{table} record {row.get("id")} references an assessment outside the tenant package')
    users={int(r['id']) for r in records.get('users',[]) if r.get('id') is not None}
    for row in records.get('assessment_access',[]):
        if int(row.get('assessment_id',-1)) not in assessments: errors.append(f'assessment_access {row.get("id")} has invalid assessment_id')
        if int(row.get('user_id',-1)) not in users: errors.append(f'assessment_access {row.get("id")} has invalid user_id')
    evidence={int(r['id']) for r in records.get('evidence',[]) if r.get('id') is not None}
    for row in records.get('evidence_attachments',[]):
        if int(row.get('evidence_id',-1)) not in evidence: errors.append(f'evidence_attachment {row.get("id")} has invalid evidence_id')
    return errors

def _safe_columns(conn, table):
    return {r['name'] for r in conn.execute(f'PRAGMA table_info({table})')}

def _insert_row(conn, table, row):
    allowed=_safe_columns(conn,table)
    data={k:v for k,v in row.items() if k in allowed}
    if not data: return
    cols=','.join(data)
    marks=','.join('?'*len(data))
    conn.execute(f'INSERT INTO {table}({cols}) VALUES({marks})',tuple(data.values()))

def _reset_postgres_sequences(conn):
    if not is_postgres(): return
    for table in sorted(ID_TABLES):
        sql=(f"SELECT setval(pg_get_serial_sequence('{table}','id'), "
             f"COALESCE((SELECT MAX(id) FROM {table}),1), "
             f"EXISTS(SELECT 1 FROM {table})) WHERE pg_get_serial_sequence('{table}','id') IS NOT NULL")
        conn.execute(sql)

def replace_tenant_records(conn, tenant_id:int, records:dict):
    errors=validate_records(records,tenant_id)
    if errors: raise ValueError('; '.join(errors))
    tenant=records['tenants'][0]
    conn.execute('DELETE FROM auth_sessions WHERE user_id IN (SELECT id FROM users WHERE tenant_id=?)',(tenant_id,))
    conn.execute('DELETE FROM assessment_access WHERE user_id IN (SELECT id FROM users WHERE tenant_id=?) OR assessment_id IN (SELECT id FROM assessments WHERE tenant_id=?)',(tenant_id,tenant_id))
    conn.execute('DELETE FROM assessments WHERE tenant_id=?',(tenant_id,))
    conn.execute('DELETE FROM users WHERE tenant_id=?',(tenant_id,))
    conn.execute('DELETE FROM audit_log WHERE tenant_id=?',(tenant_id,))
    conn.execute('DELETE FROM security_events WHERE tenant_id=?',(tenant_id,))
    conn.execute('DELETE FROM dr_validations WHERE tenant_id=?',(tenant_id,))
    tenant_cols=_safe_columns(conn,'tenants')
    updates={k:v for k,v in tenant.items() if k in tenant_cols and k!='id'}
    if updates:
        conn.execute('UPDATE tenants SET '+','.join(f'{k}=?' for k in updates)+' WHERE id=?',tuple(updates.values())+(tenant_id,))
    for table in RESTORE_ORDER:
        for row in records.get(table,[]): _insert_row(conn,table,row)
    _reset_postgres_sequences(conn)
