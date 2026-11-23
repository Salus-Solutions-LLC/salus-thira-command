"""Validate a local assessment delivery record; not proof of delivery or quality."""
from datetime import datetime, timedelta, timezone
from pathlib import Path
import argparse
import json

def instant(value):
    if not isinstance(value, str):
        raise ValueError('timestamp required')
    dt = datetime.fromisoformat(value.replace('Z', '+00:00'))
    if dt.tzinfo is None or dt.utcoffset() is None:
        raise ValueError('timezone required')
    return dt.astimezone(timezone.utc)

def check(record, now):
    errors = []
    try:
        start = instant(record['observed_acceptance_at'])
        deadline = instant(record['original_deadline_at'])
        current = instant(now)
        if deadline != start + timedelta(hours=24):
            errors.append('DEADLINE_NOT_24_HOURS')
        if current < start:
            errors.append('CLOCK_BEFORE_START')
        for key in ['task_id','instruction_reference','timezone','scope','analyst','capacity',
                    'source_inventory_reference','quality_record_reference']:
            if not record.get(key):
                errors.append('MISSING_'+key.upper())
        original = record.get('original_acceptance_at', record['observed_acceptance_at'])
        if instant(original) != start:
            errors.append('ORIGINAL_CLOCK_DRIFT')
        if record.get('legacy_transition'):
            if not record.get('historical_start_reference') or not record.get('legacy_exception'):
                errors.append('LEGACY_HISTORY_MISSING')
        returned = record.get('returned_at')
        if returned:
            at = instant(returned)
            if at < start or at > current:
                errors.append('RETURN_TIME_INVALID')
            if not record.get('return_evidence_reference'):
                errors.append('RETURN_EVIDENCE_MISSING')
            time_state = 'timely_return_recorded' if at <= deadline else 'late_return_recorded'
        else:
            time_state = 'deadline_breached_no_return' if current > deadline else 'open_before_deadline'
        quality = record.get('quality_state')
        if quality not in ['open','bounded_internal','verified_for_issue']:
            errors.append('QUALITY_STATE_INVALID')
        if record.get('material_gaps') and quality == 'verified_for_issue':
            errors.append('GAPS_CONFLICT_WITH_ISSUE_QUALITY')
        if record.get('qualification_pending') and quality == 'verified_for_issue':
            errors.append('QUALIFICATION_CONFLICT_WITH_ISSUE_QUALITY')
        if quality == 'verified_for_issue' and not record.get('qualification_evidence_reference'):
            errors.append('QUALIFICATION_EVIDENCE_MISSING')
        if record.get('external_issue_authorized') and not record.get('issue_authority_reference'):
            errors.append('ISSUE_AUTHORITY_MISSING')
        return {'record_valid':not errors,'errors':sorted(set(errors)),
                'time_state':time_state,'quality_state':quality,
                'elapsed_hours':round((current-start).total_seconds()/3600,4),
                'original_deadline_at':deadline.isoformat(),
                'proof_limit':'Record consistency only; inspect referenced originals and actual delivery/quality proof separately.'}
    except (ValueError, KeyError, TypeError, OverflowError):
        return {'record_valid':False,'errors':['RECORD_INVALID'],'proof_limit':'No completion inference permitted.'}

if __name__ == '__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('record', type=Path)
    p.add_argument('--now',required=True)
    a=p.parse_args()
    r=check(json.loads(a.record.read_text(encoding='utf-8-sig')),a.now)
    print(json.dumps(r,indent=2))
    raise SystemExit(0 if r['record_valid'] else 2)
