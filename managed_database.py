import os, sqlite3
from pathlib import Path
from secret_provider import secret

TARGET=os.getenv('SALUS_MANAGED_DB_TARGET','none').strip().lower()

def sqlite_runtime_status(db_path:str):
    try:
        c=sqlite3.connect(db_path); result=c.execute('PRAGMA integrity_check').fetchone()[0]; c.close()
        return {'provider':'sqlite','healthy':result=='ok','detail':f'SQLite integrity_check={result}','path':str(Path(db_path))}
    except Exception as exc:
        return {'provider':'sqlite','healthy':False,'detail':str(exc),'path':str(Path(db_path))}

def managed_target_status():
    if TARGET in ('','none','off'):
        return {'target':'none','configured':False,'healthy':True,'runtime_supported':False,'detail':'No managed database target configured'}
    if TARGET not in ('postgres','postgresql','azure_postgresql'):
        return {'target':TARGET,'configured':False,'healthy':False,'runtime_supported':False,'detail':'Unsupported managed database target'}
    dsn=secret('SALUS_POSTGRES_DSN','')
    if not dsn:
        return {'target':'postgresql','configured':False,'healthy':False,'runtime_supported':False,'detail':'SALUS_POSTGRES_DSN is not configured'}
    try:
        import psycopg
    except ImportError:
        return {'target':'postgresql','configured':True,'healthy':False,'runtime_supported':False,'detail':'psycopg is not installed'}
    try:
        with psycopg.connect(dsn,connect_timeout=5) as conn:
            with conn.cursor() as cur:
                cur.execute('SELECT current_database(), current_user, version()')
                db,user,version=cur.fetchone()
        return {'target':'postgresql','configured':True,'healthy':True,'runtime_supported':False,'database':db,'user':user,'detail':version.split(',')[0]}
    except Exception as exc:
        return {'target':'postgresql','configured':True,'healthy':False,'runtime_supported':False,'detail':f'PostgreSQL target unreachable: {exc}'}
