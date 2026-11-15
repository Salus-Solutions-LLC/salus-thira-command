"""Reduce one bounded original-job log query to fixed, content-free diagnostics."""
import hashlib
import json
from pathlib import Path
import re
import sys

STAGES=frozenset(('new_operation_precheck','stable_inventory','source_correlated_recovery_plan',
 'task_search_and_durable_receipts','final_source_stability','atomic_manifest_commit','independent_durable_readback',
 'represented_precheck','duplicate_receipt_precheck','source_census','membership_prequery','create_receipt',
 'verify_durable_receipt','membership_postquery','source_census_readback'))
CODES=frozenset({'UNEXPECTED_FAILURE','RECOVERY_METADATA_CHANGED','RECOVERY_RECEIPT_DISAGREEMENT',
 'SOURCE_CHANGED_DURING_SEARCH','STABILITY_NOT_ESTABLISHED','MISSING_REPRESENTATION','BOUNDARY_BELOW_MINIMUM'}|
 {f'PLAN_{n:02d}' for n in range(1,21)}|
 {p+'_'+s for p in ('ROOT','PAGE') for s in ('REQUEST_FAILED','JSON_INVALID','PAYLOAD_INVALID','HTTP_BAD_REQUEST',
  'HTTP_UNAUTHORIZED','HTTP_FORBIDDEN','HTTP_NOT_FOUND','HTTP_THROTTLED','HTTP_RESYNC_REQUIRED','HTTP_SERVER_ERROR','HTTP_OTHER')})
RECEIPTS=frozenset(('95838b67-b96f-4d75-a079-d1c4b72bfddb','fb31513b-df74-4e08-8a33-40f63ea306f6',
                   '4a7de341-6c03-4233-9b9f-41fdcf43abd8','99bf8254-40d4-4327-8511-f834127623ef'))


def reduce_history(rows, available=True):
    result={'original_run_id':43743532577,'query_state':'UNAVAILABLE','failure_code':'NOT_OBSERVED',
        'failure_stage':'NOT_OBSERVED','complete_inventory_markers':0,'query_receipt_markers':0,
        'accepted_record_count':0,'accepted_records_sha256':hashlib.sha256(b'[]').hexdigest()}
    if not available:return result
    if not isinstance(rows,list) or len(rows)>300 or any(not isinstance(v,str) or len(v)>500 for v in rows):
        result['query_state']='INVALID_RESULT'
        return result
    codes,stages,inventory,receipts,accepted=set(),set(),set(),set(),set()
    unrecognized=False
    for value in rows:
        m=re.fullmatch(r'STABILITY_FAILURE_CODE=([A-Z0-9_]{1,80})',value)
        if m:
            if m[1] in CODES:codes.add(m[1]);accepted.add(value)
            else:unrecognized=True
        m=re.fullmatch(r'STABILITY_FAILURE_STAGE=([a-z_]{1,80})',value)
        if m and m[1] in STAGES:stages.add(m[1]);accepted.add(value)
        m=re.fullmatch(r'STABILITY_SAMPLE_([1-6])_COMPLETE=1',value)
        if m:inventory.add(m[1]);accepted.add(value)
        m=re.fullmatch(r'TASK_KNOWLEDGE_Q[1-4]_RECEIPT_ID=([a-f0-9-]{36})',value)
        if m and m[1] in RECEIPTS:receipts.add(m[1]);accepted.add(value)
    state='RECOVERED' if codes else 'NO_FAILURE_MARKER'
    if len(codes)>1 or len(stages)>1:state='CONFLICTING_MARKERS'
    if unrecognized:state='UNRECOGNIZED_CODE'
    result.update(query_state=state,failure_code=next(iter(codes)) if len(codes)==1 else 'NOT_OBSERVED',
        failure_stage=next(iter(stages)) if len(stages)==1 else 'NOT_OBSERVED',
        complete_inventory_markers=len(inventory),query_receipt_markers=len(receipts),accepted_record_count=len(accepted),
        accepted_records_sha256=hashlib.sha256(json.dumps(sorted(accepted),separators=(',',':')).encode()).hexdigest())
    return result


def main():
    available=len(sys.argv)==3 and sys.argv[2]=='available'
    rows=[]
    try:
        path=Path(sys.argv[1])
        if path.stat().st_size>1024*1024:raise ValueError('bound')
        rows=json.loads(path.read_text(encoding='utf-8'))
    except Exception:
        available=False
    # Only a fixed-field summary leaves this reducer; never echo raw log/error text.
    print(json.dumps(reduce_history(rows,available),sort_keys=True,separators=(',',':')))


if __name__=='__main__':main()
