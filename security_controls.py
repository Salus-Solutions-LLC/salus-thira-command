import os, re, shutil, subprocess, tempfile
from pathlib import Path
from datetime import datetime, timedelta, timezone

AV_MODE=os.getenv('SALUS_AV_MODE','off').strip().lower()
AV_REQUIRED=os.getenv('SALUS_REQUIRE_AV','0').strip().lower() in ('1','true','yes')
CLAMSCAN_PATH=os.getenv('SALUS_CLAMSCAN_PATH','clamscan')


def current_daily_signatures(database_dir=None, now_utc=None):
    """Require a verified official daily database built within 72 hours."""
    directory=Path(database_dir or os.getenv('SALUS_CLAMAV_DATABASE_DIR','/var/lib/clamav'))
    database=next((directory / name for name in ('daily.cld','daily.cvd')
                   if (directory / name).is_file()), None)
    sigtool=shutil.which('sigtool')
    if database is None or not sigtool:
        return False
    try:
        result=subprocess.run([sigtool,'--info',str(database)],capture_output=True,
                              text=True,timeout=10)
        if result.returncode!=0 or 'Verification OK.' not in result.stdout:
            return False
        match=re.search(r'^Build time:\s*(.+)$',result.stdout,re.MULTILINE)
        if not match:
            return False
        built=datetime.strptime(match.group(1).strip(),'%d %b %Y %H:%M %z')
        age=(now_utc or datetime.now(timezone.utc))-built.astimezone(timezone.utc)
        return -timedelta(hours=1)<=age<=timedelta(hours=72)
    except (OSError,ValueError,subprocess.TimeoutExpired):
        return False

def scanner_configuration():
    """Report scanner configuration only; signature currency needs a live scan."""
    if AV_MODE!='clamav':
        return {'mode':AV_MODE,'configured':False}
    executable=shutil.which(CLAMSCAN_PATH)
    if not executable:
        return {'mode':AV_MODE,'configured':False}
    try:
        version=subprocess.run([executable,'--version'],capture_output=True,text=True,timeout=2)
        configured=version.returncode==0 and version.stdout.startswith('ClamAV ')
    except (OSError,subprocess.TimeoutExpired):
        configured=False
    return {'mode':AV_MODE,'configured':configured}

def scan_bytes(data: bytes, filename: str='upload.bin'):
    if AV_MODE in ('off','none',''):
        if AV_REQUIRED:
            return {'ok':False,'status':'Unavailable','detail':'Malware scanning is required but no scanner is configured.'}
        return {'ok':True,'status':'Not Configured','detail':'Malware scanner disabled.'}
    if AV_MODE!='clamav':
        return {'ok':False,'status':'Unavailable','detail':f'Unsupported scanner mode: {AV_MODE}'}
    if not current_daily_signatures():
        return {'ok':False,'status':'Unavailable','detail':'ClamAV daily signatures are missing, unverified or stale.'}
    suffix=Path(filename).suffix[:20]
    fd,path=tempfile.mkstemp(prefix='salus-quarantine-',suffix=suffix); os.close(fd)
    try:
        Path(path).write_bytes(data)
        p=subprocess.run([CLAMSCAN_PATH,'--no-summary',path],capture_output=True,text=True,timeout=120)
        detail=(p.stdout or p.stderr or '').strip()[-1000:]
        if p.returncode==0: return {'ok':True,'status':'Clean','detail':detail}
        if p.returncode==1: return {'ok':False,'status':'Infected','detail':detail}
        return {'ok':False,'status':'Scan Error','detail':detail or f'clamav return code {p.returncode}'}
    except FileNotFoundError:
        return {'ok':False,'status':'Unavailable','detail':f'ClamAV executable not found: {CLAMSCAN_PATH}'}
    except Exception as exc:
        return {'ok':False,'status':'Scan Error','detail':str(exc)}
    finally:
        try: os.unlink(path)
        except OSError: pass

def retention_active(retention_until: str) -> bool:
    if not retention_until: return False
    try:
        dt=datetime.fromisoformat(retention_until.replace('Z','+00:00'))
        if dt.tzinfo is None: dt=dt.replace(tzinfo=timezone.utc)
        return dt > datetime.now(timezone.utc)
    except Exception:
        return False
