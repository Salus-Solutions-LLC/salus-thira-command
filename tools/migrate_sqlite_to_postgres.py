#!/usr/bin/env python3
import argparse, json, os, sqlite3, sys
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))

MIGRATE_TABLES=[
 'tenants','users','assessments','assessment_access','materials','material_links','material_events','threats','scenarios','capabilities','evidence',
 'gaps','improvements','decisions','audit_log','security_events','reassessment_triggers','assessment_weights',
 'evidence_attachments','entity_versions','scope_changes','workflow_events'
]
EXCLUDED=['auth_sessions','oidc_states','backup_history','dr_validations']

def source_rows(conn,table):
    try:
        conn.row_factory=sqlite3.Row
        return [dict(r) for r in conn.execute(f'SELECT * FROM {table} ORDER BY 1')]
    except sqlite3.OperationalError:
        return []

def columns(conn,table): return {r['name'] for r in conn.execute(f'PRAGMA table_info({table})')}

def main():
    ap=argparse.ArgumentParser(description='Migrate Salus THIRA Command SQLite records into the PostgreSQL runtime schema.')
    ap.add_argument('--sqlite',required=True,help='Path to source thira.db')
    ap.add_argument('--postgres-dsn',default='',help='PostgreSQL DSN / connection URL. Omit to use existing SALUS_DATABASE_URL / Entra environment settings.')
    ap.add_argument('--replace',action='store_true',help='Replace existing target application records. Intended for controlled cutover only.')
    ap.add_argument('--report',default='',help='Optional JSON report path')
    args=ap.parse_args()
    src_path=Path(args.sqlite).resolve()
    if not src_path.is_file(): raise SystemExit(f'Source database not found: {src_path}')
    src=sqlite3.connect(src_path); src.row_factory=sqlite3.Row
    integrity=src.execute('PRAGMA integrity_check').fetchone()[0]
    if integrity!='ok': raise SystemExit(f'Source SQLite integrity_check failed: {integrity}')

    os.environ['SALUS_DB_BACKEND']='postgres'
    if args.postgres_dsn: os.environ['SALUS_DATABASE_URL']=args.postgres_dsn
    os.environ['SALUS_SEED_DEMO']='0'; os.environ.setdefault('SALUS_AUTH_MODE','prototype'); os.environ.setdefault('SALUS_STORAGE_BACKEND','local')
    import app
    from database import reset_identity_sequences
    dst=app.db()
    target_existing=dst.execute('SELECT (SELECT COUNT(*) FROM assessments) assessments,(SELECT COUNT(*) FROM users) users').fetchone()
    if (target_existing['assessments'] or target_existing['users']) and not args.replace:
        dst.close(); src.close(); raise SystemExit('Target PostgreSQL database already contains users or assessments. Re-run with --replace only during an authorized cutover.')
    if args.replace:
        for table in reversed(MIGRATE_TABLES):
            try: dst.execute(f'DELETE FROM {table}')
            except Exception:
                dst.rollback(); raise
        dst.execute('DELETE FROM auth_sessions'); dst.execute('DELETE FROM oidc_states'); dst.execute('DELETE FROM dr_validations'); dst.execute('DELETE FROM backup_history')
        dst.commit()
    else:
        if not target_existing['assessments'] and not target_existing['users']:
            dst.execute('DELETE FROM tenants'); dst.commit()

    report={'source':str(src_path),'source_integrity':integrity,'tables':{},'excluded':EXCLUDED,'verified':False}
    try:
        for table in MIGRATE_TABLES:
            rows=source_rows(src,table); target_cols=columns(dst,table); inserted=0
            for row in rows:
                data={k:v for k,v in row.items() if k in target_cols}
                if not data: continue
                cols=','.join(data); marks=','.join('?'*len(data))
                dst.execute(f'INSERT INTO {table}({cols}) VALUES({marks})',tuple(data.values())); inserted+=1
            report['tables'][table]={'source_rows':len(rows),'inserted_rows':inserted}
        reset_identity_sequences(dst,MIGRATE_TABLES)
        dst.commit()
    except Exception:
        dst.rollback(); dst.close(); src.close(); raise

    mismatches=[]
    for table in MIGRATE_TABLES:
        src_count=len(source_rows(src,table)); dst_count=dst.execute(f'SELECT COUNT(*) c FROM {table}').fetchone()['c']
        report['tables'][table]['target_rows']=dst_count
        if src_count!=dst_count: mismatches.append(f'{table}: source={src_count} target={dst_count}')
    report['verified']=not mismatches; report['mismatches']=mismatches
    dst.close(); src.close()
    text=json.dumps(report,indent=2,sort_keys=True)
    if args.report: Path(args.report).write_text(text+'\n',encoding='utf-8')
    print(text)
    if mismatches: raise SystemExit(2)

if __name__=='__main__': main()
