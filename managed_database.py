import os, sqlite3
from pathlib import Path
from secret_provider import secret

TARGET=os.getenv('SALUS_MANAGED_DB_TARGET','none').strip().lower()
DB_BACKEND=os.getenv('SALUS_DB_BACKEND','sqlite').strip().lower()
POSTGRES_AUTH=os.getenv('SALUS_POSTGRES_AUTH','dsn').strip().lower()

def _postgres_dsn():
    return os.getenv('SALUS_DATABASE_URL','').strip() or secret('SALUS_POSTGRES_DSN','').strip()

def _postgres_connect(connect_timeout=5):
    try:
        import psycopg
    except ImportError as exc:
        raise RuntimeError('psycopg is not installed; install requirements.txt') from exc
    if POSTGRES_AUTH in ('entra','azure_entra','managed_identity'):
        host=os.getenv('SALUS_POSTGRES_HOST','').strip(); db=os.getenv('SALUS_POSTGRES_DATABASE','').strip(); user=os.getenv('SALUS_POSTGRES_USER','').strip(); port=int(os.getenv('SALUS_POSTGRES_PORT','5432')); sslmode=os.getenv('SALUS_POSTGRES_SSLMODE','require').strip() or 'require'
        if not (host and db and user): raise RuntimeError('Entra PostgreSQL auth requires SALUS_POSTGRES_HOST, SALUS_POSTGRES_DATABASE, and SALUS_POSTGRES_USER')
        try:
            from azure.identity import DefaultAzureCredential
        except ImportError as exc: raise RuntimeError('azure-identity is required for PostgreSQL Entra authentication') from exc
        token=DefaultAzureCredential().get_token('https://ossrdbms-aad.database.windows.net/.default').token
        return psycopg.connect(host=host,port=port,dbname=db,user=user,password=token,sslmode=sslmode,connect_timeout=connect_timeout)
    dsn=_postgres_dsn()
    if not dsn: raise RuntimeError('SALUS_DATABASE_URL / SALUS_POSTGRES_DSN is not configured')
    return psycopg.connect(dsn,connect_timeout=connect_timeout)

def sqlite_runtime_status(db_path:str):
    try:
        c=sqlite3.connect(db_path); result=c.execute('PRAGMA integrity_check').fetchone()[0]; c.close()
        return {'provider':'sqlite','healthy':result=='ok','detail':f'SQLite integrity_check={result}','path':str(Path(db_path))}
    except Exception as exc:
        return {'provider':'sqlite','healthy':False,'detail':str(exc),'path':str(Path(db_path))}

def postgres_runtime_status():
    configured=bool(_postgres_dsn()) or (POSTGRES_AUTH in ('entra','azure_entra','managed_identity') and all(os.getenv(x,'').strip() for x in ('SALUS_POSTGRES_HOST','SALUS_POSTGRES_DATABASE','SALUS_POSTGRES_USER')))
    if not configured: return {'provider':'postgresql','healthy':False,'configured':False,'auth':POSTGRES_AUTH,'detail':'PostgreSQL runtime configuration is incomplete'}
    try:
        with _postgres_connect(5) as conn:
            with conn.cursor() as cur:
                cur.execute('SELECT current_database(), current_user, current_schema(), version()')
                db,user,schema,version=cur.fetchone()
        return {'provider':'postgresql','healthy':True,'configured':True,'auth':POSTGRES_AUTH,'database':db,'user':user,'schema':schema,'detail':version.split(',')[0]}
    except Exception as exc:
        return {'provider':'postgresql','healthy':False,'configured':configured,'auth':POSTGRES_AUTH,'detail':f'PostgreSQL runtime unavailable: {exc}'}

def runtime_database_status(db_path:str):
    if DB_BACKEND=='postgres': return postgres_runtime_status()
    return sqlite_runtime_status(db_path)

def managed_target_status():
    target=TARGET
    if target in ('','none','off'):
        if DB_BACKEND=='postgres':
            status=postgres_runtime_status(); status.update({'target':'postgresql','runtime_supported':True,'active_runtime':True}); return status
        return {'target':'none','configured':False,'healthy':True,'runtime_supported':True,'active_runtime':False,'detail':'No separate managed database target configured'}
    if target not in ('postgres','postgresql','azure_postgresql'):
        return {'target':target,'configured':False,'healthy':False,'runtime_supported':False,'active_runtime':False,'detail':'Unsupported managed database target'}
    status=postgres_runtime_status(); status.update({'target':'postgresql','runtime_supported':True,'active_runtime':DB_BACKEND=='postgres'}); return status
