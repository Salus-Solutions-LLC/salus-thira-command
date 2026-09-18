import os, json, logging, sys
from datetime import datetime, timezone

LOGGER=logging.getLogger('salus.security')
if not LOGGER.handlers:
    h=logging.StreamHandler(sys.stdout)
    h.setFormatter(logging.Formatter('%(message)s'))
    LOGGER.addHandler(h)
    LOGGER.setLevel(logging.INFO)
    LOGGER.propagate=False

_AZURE_CONFIGURED=False
_AZURE_ERROR=''

def configure_telemetry():
    global _AZURE_CONFIGURED,_AZURE_ERROR
    backend=os.getenv('SALUS_TELEMETRY_BACKEND','json').strip().lower()
    if backend not in ('azure','azure_monitor','applicationinsights'):
        return
    conn=os.getenv('APPLICATIONINSIGHTS_CONNECTION_STRING','').strip()
    if not conn:
        _AZURE_ERROR='APPLICATIONINSIGHTS_CONNECTION_STRING is required for Azure Monitor telemetry'
        return
    try:
        from azure.monitor.opentelemetry import configure_azure_monitor
        configure_azure_monitor(connection_string=conn)
        _AZURE_CONFIGURED=True
        # Preserve the structured stdout record and also pass it to the root
        # OpenTelemetry handler installed by configure_azure_monitor().
        LOGGER.propagate=True
    except Exception:
        _AZURE_ERROR='Azure Monitor initialization failed'

configure_telemetry()

def emit(event_type:str,severity:str='Info',**fields):
    payload={'ts':datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace('+00:00','Z'),'event_type':event_type,'severity':severity,**fields}
    LOGGER.info(json.dumps(payload,default=str,separators=(',',':')))

def readiness():
    backend=os.getenv('SALUS_TELEMETRY_BACKEND','json').strip().lower()
    if backend in ('azure','azure_monitor','applicationinsights'):
        return {'backend':'azure_monitor','healthy':_AZURE_CONFIGURED,'detail':'Azure Monitor configured' if _AZURE_CONFIGURED else (_AZURE_ERROR or 'Azure Monitor not configured')}
    return {'backend':'json','healthy':True,'detail':'Structured JSON security telemetry to stdout'}
