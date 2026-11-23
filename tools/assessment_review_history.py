"""Validate supplied review-event records; cannot authenticate people or review quality."""

def summarize(events):
    ids=set(); references=set(); result={'human_assessment_review_events':0,'investigator_events':0,
        'other_personnel_events':0,'human_source_review_events':0,'source_decisions':0,
        'automated_substantive_passes':0,'automated_editorial_passes':0}
    for event in events:
        eid=event.get('id'); ref=event.get('evidence_reference')
        if not isinstance(eid,str) or not eid.strip() or eid in ids:
            raise ValueError('missing or duplicate event ID')
        if not isinstance(ref,str) or not ref.strip() or ref in references:
            raise ValueError('missing or repeated review evidence')
        ids.add(eid); references.add(ref)
        if not all(isinstance(event.get(k),str) and event[k].strip() for k in ['edition','scope','result','date_status']):
            raise ValueError('review scope and provenance required')
        kind=event.get('kind'); roles=event.get('roles',[])
        if not isinstance(roles,list) or not all(r in ['investigator','other_salus_personnel'] for r in roles):
            raise ValueError('unrecognized human role')
        if isinstance(kind,str) and kind.startswith('automated_'):
            if roles:raise ValueError('automation cannot carry personnel roles')
            if kind=='automated_substantive':result['automated_substantive_passes']+=1
            elif kind=='automated_editorial':result['automated_editorial_passes']+=1
            else:raise ValueError('unknown automated review type')
        elif kind in ['human_assessment','human_source','human_specialist','human_reader','human_issue']:
            if not roles or event.get('human_confirmation') is not True:
                raise ValueError('documented human review confirmation required')
            if kind=='human_assessment':
                result['human_assessment_review_events']+=1
                result['investigator_events']+=int('investigator'in roles)
                result['other_personnel_events']+=int('other_salus_personnel'in roles)
            elif kind=='human_source':
                n=event.get('source_decisions')
                if type(n)is not int or n<0:raise ValueError('invalid source-decision count')
                result['human_source_review_events']+=1;result['source_decisions']+=n
        else:raise ValueError('unknown review type')
    result['scope']='Documented events only; overlapping roles are not additive; no authentication or quality certification'
    return result
