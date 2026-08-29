#!/usr/bin/env python3
import argparse, os, sys, uuid
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]; sys.path.insert(0,str(ROOT))

def main():
    ap=argparse.ArgumentParser(description='Exercise the Salus THIRA Command PostgreSQL runtime adapter without committing test records.')
    ap.add_argument('--postgres-dsn',default='',help='PostgreSQL DSN. Omit to use existing PostgreSQL/Entra environment settings.')
    args=ap.parse_args()
    os.environ['SALUS_DB_BACKEND']='postgres'
    if args.postgres_dsn: os.environ['SALUS_DATABASE_URL']=args.postgres_dsn
    os.environ['SALUS_SEED_DEMO']='0'
    os.environ.setdefault('SALUS_AUTH_MODE','prototype')
    import app
    c=app.db()
    tables={r['name'] for r in c.execute("SELECT table_name AS name FROM information_schema.tables WHERE table_schema=current_schema()")}
    required={'tenants','users','assessments','threats','scenarios','capabilities','evidence','gaps','improvements','decisions','audit_log'}
    missing=sorted(required-tables)
    if missing: c.close(); raise SystemExit('Missing runtime tables: '+', '.join(missing))
    slug='runtime-smoke-'+uuid.uuid4().hex[:12]
    try:
        cur=c.execute('INSERT INTO tenants(name,slug,status,created_at) VALUES(?,?,?,?)',('Runtime Smoke',slug,'Active',app.now()))
        tid=cur.lastrowid
        cur=c.execute('INSERT INTO assessments(tenant_id,name,organization,assessment_type,purpose,mission,scope,status,classification,scope_locked,version,created_at,updated_at) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)',(tid,'Runtime Smoke Assessment','Runtime Smoke','Enterprise','Runtime validation','Validate PostgreSQL transaction semantics','','Draft','Standard',0,1,app.now(),app.now()))
        aid=cur.lastrowid
        got=c.execute('SELECT tenant_id,name FROM assessments WHERE id=?',(aid,)).fetchone()
        if not got or int(got['tenant_id'])!=int(tid): raise RuntimeError('Inserted assessment could not be read through PostgreSQL adapter')
        c.rollback()
    finally:
        c.close()
    print('POSTGRES_RUNTIME_SMOKE_PASS (test transaction rolled back)')

if __name__=='__main__': main()
