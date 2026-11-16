"""Print numeric and allowlisted termination telemetry only; never raw ARM payloads."""
import hashlib
import json
import sys


def summarize(value):
    props=value.get('properties',{})
    states={'Running','Processing','Stopped','Degraded','Failed','Unknown','Succeeded'}
    reasons={'BackoffLimitExceeded','DeadlineExceeded','OOMKilled','Completed','Error','ContainerCreateFailure','ContainerCrashing','JobExecutionTimeout'}
    containers=[c for r in props.get('detailedStatus',{}).get('replicas',[]) for c in r.get('containers',[])]
    assert len(containers)<=100
    codes=sorted({c['code'] for c in containers if type(c.get('code')) is int and -(2**31)<=c['code']<2**31})
    info=[c.get('additionalInformation','') for c in containers]
    reason=props.get('reason','')
    return {'STATUS':props.get('status') if props.get('status') in states else 'Unknown',
        'REASON':reason if reason in reasons else 'UNCLASSIFIED',
        'REASON_SHA256':hashlib.sha256(str(reason).encode()).hexdigest(),
        'CONTAINERS':len(containers),'EXIT_CODES':','.join(str(c) for c in codes) if codes else 'UNAVAILABLE',
        'OOM_EXPLICIT':int(any(v=='OOMKilled' for v in info) or reason=='OOMKilled')}


if __name__=='__main__':
    try:
        with open(sys.argv[1],encoding='utf-8') as stream:value=json.load(stream)
        for key,item in summarize(value).items():print('RECOVERY_PLATFORM_'+key+'='+str(item),flush=True)
    except Exception:
        print('RECOVERY_PLATFORM_DIAGNOSTIC_UNAVAILABLE=1',flush=True)
        raise SystemExit(1) from None
