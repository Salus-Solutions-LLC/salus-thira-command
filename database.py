import os
import re
import sqlite3
from secret_provider import secret
from collections.abc import Mapping

DB_BACKEND = os.getenv('SALUS_DB_BACKEND', 'sqlite').strip().lower()
DB_PATH = os.getenv('SALUS_DB_PATH', os.path.join(os.path.dirname(__file__), 'thira.db'))
POSTGRES_AUTH = os.getenv('SALUS_POSTGRES_AUTH','dsn').strip().lower()
DATABASE_URL = (
    ''
    if POSTGRES_AUTH in ('entra','azure_entra','managed_identity')
    else (os.getenv('SALUS_DATABASE_URL', '').strip() or secret('SALUS_POSTGRES_DSN','').strip())
)
POSTGRES_HOST = os.getenv('SALUS_POSTGRES_HOST','').strip()
POSTGRES_PORT = int(os.getenv('SALUS_POSTGRES_PORT','5432'))
POSTGRES_DATABASE = os.getenv('SALUS_POSTGRES_DATABASE','').strip()
POSTGRES_USER = os.getenv('SALUS_POSTGRES_USER','').strip()
POSTGRES_SSLMODE = os.getenv('SALUS_POSTGRES_SSLMODE','require').strip() or 'require'
_AZURE_CREDENTIAL=None

ID_TABLES = {
    'tenants','users','auth_sessions','oidc_states','assessment_access','industry_profiles','industry_profile_items','industry_profile_events','tenant_industry_configurations','assessments',
    'threats','scenarios','capabilities','evidence','gaps','improvements','decisions','accepted_risks','risk_overrides',
    'audit_log','backup_history','security_events','reassessment_triggers','evidence_attachments','report_versions','package_agreement_artifacts','package_quote_versions','package_agreement_downloads','package_acceptances','package_intake_requests','package_product_report_versions','package_report_conformance','package_report_reconciliations','package_report_qa_evidence','package_report_qa_reviews','package_report_issue_packets','package_report_issue_deliveries','package_report_issue_acknowledgments','package_predecessor_qualifications','restore_requests','intel_findings','observation_intake_channels','observations','observation_attachments','observation_events','cop_coordination_threads','cop_coordination_messages','cop_decision_requests','cop_events','ops_service_pillars','ops_service_catalog','ops_catalog_events','expert_profiles','expert_credentials','expert_availability','expert_conflicts','ops_engagement_assignments','expert_events','ops_requests','ops_engagements','ops_engagement_readiness','ops_tasks','ops_field_reports','ops_estimates','ops_estimate_lines','ops_expenses','ops_invoice_statements',
    'entity_versions','scope_changes','workflow_events','dr_validations','governed_intake',
    'materials','material_links','material_events',
    'salintel_domains','salintel_domain_events','salintel_domain_registry_backups','salintel_domain_registry_restore_requests','salintel_investigations','salintel_investigation_items','salintel_investigation_events'
}

class DbRow(Mapping):
    def __init__(self, keys, values):
        self._keys = tuple(keys)
        self._values = tuple(values)
        self._map = dict(zip(self._keys, self._values))
    def __getitem__(self, key):
        if isinstance(key, int):
            return self._values[key]
        return self._map[key]
    def __iter__(self):
        return iter(self._keys)
    def __len__(self):
        return len(self._keys)
    def keys(self):
        return self._keys

class SyntheticCursor:
    def __init__(self, rows=None, lastrowid=None, rowcount=-1):
        self._rows = list(rows or [])
        self._idx = 0
        self.lastrowid = lastrowid
        self.rowcount = rowcount
    def fetchone(self):
        if self._idx >= len(self._rows): return None
        row = self._rows[self._idx]; self._idx += 1; return row
    def fetchall(self):
        out=self._rows[self._idx:]; self._idx=len(self._rows); return out
    def __iter__(self):
        while True:
            row=self.fetchone()
            if row is None: break
            yield row

class PostgresCursor:
    def __init__(self, cursor, buffered=None, lastrowid=None):
        self.cursor=cursor
        self.lastrowid=lastrowid
        self.rowcount=getattr(cursor,'rowcount',-1)
        self._buffer=list(buffered or [])
        self._buffer_idx=0
    def _wrap(self, row):
        if row is None: return None
        if isinstance(row, Mapping): return row
        desc=self.cursor.description or []
        keys=[getattr(d,'name',d[0]) for d in desc]
        return DbRow(keys,row)
    def fetchone(self):
        if self._buffer_idx < len(self._buffer):
            row=self._buffer[self._buffer_idx]; self._buffer_idx+=1; return row
        return self._wrap(self.cursor.fetchone())
    def fetchall(self):
        out=[]
        while self._buffer_idx < len(self._buffer):
            out.append(self._buffer[self._buffer_idx]); self._buffer_idx += 1
        out.extend(self._wrap(r) for r in self.cursor.fetchall())
        return out
    def __iter__(self):
        while True:
            row=self.fetchone()
            if row is None: break
            yield row


def _qmark_to_percent(sql: str) -> str:
    """Translate SQLite qmark placeholders for psycopg and preserve literal percent signs.

    Psycopg parses percent placeholders before PostgreSQL parses SQL, including percent
    characters inside SQL string literals. Every literal ``%`` from the qmark SQL
    therefore must become ``%%`` while unquoted ``?`` placeholders become ``%s``.
    """
    out=[]; in_single=False; in_double=False; i=0
    while i < len(sql):
        ch=sql[i]
        if ch=="'" and not in_double:
            if in_single and i+1<len(sql) and sql[i+1]=="'":
                out.extend([ch,sql[i+1]]); i+=2; continue
            in_single=not in_single; out.append(ch)
        elif ch=='"' and not in_single:
            in_double=not in_double; out.append(ch)
        elif ch=='?' and not in_single and not in_double:
            out.append('%s')
        elif ch=='%':
            out.append('%%')
        else: out.append(ch)
        i+=1
    return ''.join(out)


def _postgres_ddl(sql: str) -> str:
    sql=re.sub(r'INTEGER\s+PRIMARY\s+KEY\s+AUTOINCREMENT', 'BIGSERIAL PRIMARY KEY', sql, flags=re.I)
    sql=re.sub(r'\bREAL\b', 'DOUBLE PRECISION', sql, flags=re.I)
    sql=re.sub(r'\b([A-Za-z_][A-Za-z0-9_]*_id)\s+INTEGER\b', r'\1 BIGINT', sql, flags=re.I)
    sql=re.sub(r'DEFAULT\s+"([^"]*)"', lambda m: "DEFAULT '"+m.group(1).replace("'","''")+"'", sql, flags=re.I)
    return sql


def _split_script(script: str):
    statements=[]; buf=[]; in_single=False; in_double=False
    i=0
    while i < len(script):
        ch=script[i]
        if ch=="'" and not in_double:
            if in_single and i+1<len(script) and script[i+1]=="'":
                buf.extend([ch,script[i+1]]); i+=2; continue
            in_single=not in_single
        elif ch=='"' and not in_single:
            in_double=not in_double
        if ch==';' and not in_single and not in_double:
            stmt=''.join(buf).strip(); buf=[]
            if stmt: statements.append(stmt)
        else: buf.append(ch)
        i+=1
    stmt=''.join(buf).strip()
    if stmt: statements.append(stmt)
    return statements

class PostgresConnection:
    backend='postgres'
    def __init__(self, url: str):
        if not url and POSTGRES_AUTH not in ('entra','azure_entra','managed_identity'):
            raise RuntimeError('SALUS_DATABASE_URL or SALUS_POSTGRES_DSN is required when SALUS_DB_BACKEND=postgres')
        try:
            import psycopg
        except ImportError as exc:
            raise RuntimeError('PostgreSQL runtime requires psycopg. Install requirements.txt.') from exc
        self._psycopg=psycopg
        global _AZURE_CREDENTIAL
        if POSTGRES_AUTH in ('entra','azure_entra','managed_identity'):
            if not (POSTGRES_HOST and POSTGRES_DATABASE and POSTGRES_USER):
                raise RuntimeError('Entra PostgreSQL auth requires SALUS_POSTGRES_HOST, SALUS_POSTGRES_DATABASE, and SALUS_POSTGRES_USER')
            try:
                from azure.identity import DefaultAzureCredential
            except ImportError as exc:
                raise RuntimeError('azure-identity is required for PostgreSQL Entra authentication') from exc
            if _AZURE_CREDENTIAL is None: _AZURE_CREDENTIAL=DefaultAzureCredential()
            token=_AZURE_CREDENTIAL.get_token('https://ossrdbms-aad.database.windows.net/.default').token
            self.raw=psycopg.connect(host=POSTGRES_HOST,port=POSTGRES_PORT,dbname=POSTGRES_DATABASE,user=POSTGRES_USER,password=token,sslmode=POSTGRES_SSLMODE)
        else:
            self.raw=psycopg.connect(url)
        self._lastrowid=None
    def execute(self, sql, params=()):
        stripped=sql.strip()
        if re.match(r'^PRAGMA\s+foreign_keys', stripped, re.I):
            return SyntheticCursor([])
        m=re.match(r'^PRAGMA\s+table_info\(([^)]+)\)', stripped, re.I)
        if m:
            table=m.group(1).strip().strip('"\'')
            cur=self.raw.cursor(); cur.execute("SELECT column_name FROM information_schema.columns WHERE table_schema=current_schema() AND table_name=%s ORDER BY ordinal_position",(table,))
            rows=[DbRow(['name'],[r[0]]) for r in cur.fetchall()]
            return SyntheticCursor(rows)
        if re.match(r'^SELECT\s+last_insert_rowid\(\)', stripped, re.I):
            return SyntheticCursor([DbRow(['last_insert_rowid'],[self._lastrowid])])
        translated=_qmark_to_percent(_postgres_ddl(sql))
        insert_match=re.match(r'^\s*INSERT\s+INTO\s+([A-Za-z_][A-Za-z0-9_]*)', translated, re.I)
        wants_id=False
        if insert_match and insert_match.group(1).lower() in ID_TABLES and not re.search(r'\bRETURNING\b',translated,re.I):
            translated=translated.rstrip().rstrip(';')+' RETURNING id'
            wants_id=True
        cur=self.raw.cursor(); cur.execute(translated, tuple(params) if params is not None else ())
        if wants_id:
            r=cur.fetchone(); self._lastrowid=r[0] if r else None
            return PostgresCursor(cur,lastrowid=self._lastrowid)
        return PostgresCursor(cur,lastrowid=self._lastrowid)
    def executescript(self, script):
        statements=_split_script(script)
        order={'tenants':10,'users':20,'auth_sessions':30,'oidc_states':30,'backup_history':30,'governed_intake':35,'materials':41,'salintel_domains':42,'salintel_domain_events':43,'salintel_investigations':44,'salintel_investigation_items':52,'salintel_investigation_events':52,'material_links':53,'material_events':53,'industry_profiles':36,'industry_profile_items':37,'industry_profile_events':38,'tenant_industry_configurations':39,'assessments':40,'assessment_access':50,'threats':60,'scenarios':70,'capabilities':80,'evidence':90,'gaps':100,'improvements':110,'decisions':120,'accepted_risks':125,'risk_overrides':127,'audit_log':130,'security_events':140,'reassessment_triggers':140,'assessment_weights':140,'evidence_attachments':150,'entity_versions':150,'scope_changes':150,'workflow_events':150,'dr_validations':160,'observation_intake_channels':170,'observations':180,'observation_attachments':190,'observation_events':190,'cop_coordination_threads':200,'cop_coordination_messages':210,'cop_decision_requests':210,'cop_events':220,'ops_service_pillars':225,'ops_service_catalog':226,'ops_catalog_events':227,'expert_profiles':228,'expert_credentials':229,'expert_availability':229,'ops_requests':230,'ops_engagements':240,'ops_engagement_readiness':245,'expert_conflicts':246,'ops_engagement_assignments':247,'expert_events':248,'ops_tasks':250,'ops_field_reports':250,'ops_estimates':250,'ops_estimate_lines':260,'ops_expenses':260,'ops_invoice_statements':260}
        table_stmts=[]; other=[]
        for idx,stmt in enumerate(statements):
            m=re.match(r'^\s*CREATE\s+TABLE\s+IF\s+NOT\s+EXISTS\s+([A-Za-z_][A-Za-z0-9_]*)',stmt,re.I)
            if m: table_stmts.append((order.get(m.group(1).lower(),1000),idx,stmt))
            else: other.append((idx,stmt))
        for _,_,stmt in sorted(table_stmts): self.execute(stmt)
        for _,stmt in other: self.execute(stmt)
        return self
    def commit(self): self.raw.commit()
    def rollback(self): self.raw.rollback()
    def close(self): self.raw.close()


def connect_database():
    if DB_BACKEND == 'postgres':
        return PostgresConnection(DATABASE_URL)
    if DB_BACKEND != 'sqlite':
        raise RuntimeError(f'Unsupported SALUS_DB_BACKEND={DB_BACKEND!r}')
    os.makedirs(os.path.dirname(DB_PATH) or os.path.dirname(__file__), exist_ok=True)
    conn=sqlite3.connect(DB_PATH)
    conn.row_factory=sqlite3.Row
    conn.execute('PRAGMA foreign_keys = ON')
    return conn


def backend_name(): return DB_BACKEND

def is_sqlite(): return DB_BACKEND=='sqlite'
def is_postgres(): return DB_BACKEND=='postgres'


def table_columns(conn, table: str):
    return {r['name'] for r in conn.execute(f'PRAGMA table_info({table})')}

def reset_identity_sequences(conn, tables=None):
    if not is_postgres(): return
    selected=sorted((set(tables) if tables else ID_TABLES) & ID_TABLES)
    for table in selected:
        conn.execute(
            f"SELECT setval(pg_get_serial_sequence('{table}','id'), "
            f"COALESCE((SELECT MAX(id) FROM {table}),1), "
            f"EXISTS(SELECT 1 FROM {table})) WHERE pg_get_serial_sequence('{table}','id') IS NOT NULL"
        )
