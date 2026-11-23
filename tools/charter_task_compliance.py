"""Local evidence gate for every Salus task. No network, credentials or runtime writes.

The gate checks coverage, versions, evidence integrity and recorded dispositions.
It cannot establish the truth of prose, authenticate a human, or intercept chats.
Run it before making a completion claim; retain its exact claim boundary.
"""
from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import os
import re
import tempfile
from datetime import datetime, timezone
from pathlib import Path, PurePosixPath

# This tool is also loaded by file path from private, out-of-tree assurance scripts.
# Resolve its maintained sibling independently of the operator's working directory.
_research_spec = importlib.util.spec_from_file_location(
    'assessment_research_entry', Path(__file__).with_name('assessment_research_entry.py'))
_research_module = importlib.util.module_from_spec(_research_spec)
_research_spec.loader.exec_module(_research_module)
check_research_entry = _research_module.check_research_entry

VERSION = 1
MIN_SUBSTANTIVE_PASSES = 8
ANALYTICAL_LENSES = {'assumptions', 'methodologies', 'evidence_and_consequences', 'recommendations'}
ROOTS = (
    'SALUS_PROGRAM_CHARTER.md', 'SALUS_DECISION_REGISTER.md',
    'APPROVED_ARTIFACTS.md', 'SALUS_CHAT_STARTUP_PROTOCOL.md',
    'SALUS_TASK_COMPLIANCE_ASSURANCE_STANDARD.md', 'AGENTS.md',
)
STATES = {'met', 'not_applicable', 'superseded', 'pending', 'blocked'}
LOCATIONS = {'knowledge', 'osint', 'internet', 'other_authorized_locations'}


def fingerprint(value):
    if isinstance(value, bytes):
        return hashlib.sha256(value).hexdigest()
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(',', ':'),
                                    ensure_ascii=False).encode()).hexdigest()


def load(path):
    return json.loads(Path(path).read_text(encoding='utf-8-sig'))


def confined(root, relative):
    """Reject absolute paths, traversals, foreign drives and symlink escapes."""
    if not isinstance(relative, str) or not relative or '\\' in relative:
        raise ValueError('invalid relative path')
    p = PurePosixPath(relative)
    if p.is_absolute() or ':' in relative or '..' in p.parts:
        raise ValueError('path escapes evidence root')
    resolved = (Path(root).resolve() / relative).resolve()
    if not resolved.is_relative_to(Path(root).resolve()):
        raise ValueError('path escapes evidence root')
    return resolved


def register(root):
    """Index every nonblank source line, without guessing which clauses apply.

    Backtick Markdown references are discovered transitively. Unavailable,
    external or volatile handoff references remain explicit catalog entries.
    Source text is not copied into the generated register.
    """
    sources, units, references, queue = {}, [], {}, list(ROOTS)
    while queue:
        name = queue.pop(0)
        if name in sources:
            continue
        path = confined(root, name)
        if not path.is_file():
            raise ValueError('missing core/discovered authority: ' + name)
        text = path.read_text(encoding='utf-8-sig').replace('\r\n', '\n')
        sources[name] = fingerprint(text.encode())
        heading = []
        occurrences = {}
        for number, line in enumerate(text.splitlines(), 1):
            clean = line.strip()
            if not clean:
                continue
            if clean.startswith('#'):
                level = len(clean) - len(clean.lstrip('#'))
                heading = heading[:level - 1] + [clean.lstrip('#').strip()]
            # Include headings, table headers, context and history too. Their
            # applicability/supersession is a recorded analyst responsibility.
            digest = fingerprint(clean.encode())
            occurrences[digest] = occurrences.get(digest, 0) + 1
            uid = 'REQ-' + fingerprint([name, digest, occurrences[digest]])[:24]
            units.append({'id': uid, 'source': name, 'line': number,
                          'section': ' / '.join(heading), 'text_sha256': digest,
                          'decision_ids': sorted(set(re.findall(r'SAL-D\d{3}', clean)))})
        for ref in sorted(set(re.findall(r'`([^`\r\n]+\.md)`', text))):
            if ref == name:
                continue
            key = ref
            try:
                candidate = confined(root, ref)
                available = candidate.is_file() and ref != 'CURRENT_HANDOFF.md'
            except ValueError:
                available = False
            references.setdefault(key, {'reference': ref, 'cited_by': [],
                                         'state': 'indexed' if available else 'unexpanded'})
            references[key]['cited_by'].append(name)
            if available and ref not in sources and ref not in queue:
                queue.append(ref)
    result = {'schema_version': VERSION, 'roots': list(ROOTS),
              'sources': dict(sorted(sources.items())),
              'units': sorted(units, key=lambda u: (u['source'], u['line'])),
              'references': sorted(references.values(), key=lambda r: r['reference']),
              'coverage_rule': 'Every nonblank line; no automated applicability or truth claim',
              'newline_rule': 'UTF-8, LF canonical source fingerprints'}
    result['register_sha256'] = fingerprint(result)
    return result


def new_task(catalog, task_id, objective, task_type='unclassified'):
    if not task_id.strip() or not objective.strip():
        raise ValueError('task identity and objective required')
    return {'schema_version': VERSION, 'task_id': task_id, 'objective': objective,
            'task_type': task_type, 'started_at': datetime.now(timezone.utc).isoformat(),
            **({'assessment_research': {}} if task_type == 'assessment' else {}),
            'model_reminder': {}, 'analytical_review': {}, 'review_passes': [],
            'register_sha256': catalog['register_sha256'],
            'scope': {'authorization': '', 'boundary': '', 'limitations': []},
            'requirements': [{'id': u['id'], 'state': 'pending', 'reason': '',
                              'evidence': [], 'checks': []} for u in catalog['units']],
            'references': {r['reference']: {'state': 'pending', 'reason': '',
                                           'evidence': []}
                           for r in catalog['references'] if r['state'] == 'unexpanded'},
            'evidence': {}, 'locations': {}, 'capture': {}, 'outputs': [],
            'protected_actions': [], 'corrective_actions': [], 'holds': {}, 'verification_owner': 'Salus assistant',
            'routine_human_attestation_required': False}


def review_pass_checks(task, verified):
    """Correlate distinct review records with the actual bytes examined and delivered."""
    errors = set()
    counts = {'substantive': 0, 'editorial': 0}
    passes = task.get('review_passes')
    if not isinstance(passes, list):
        return {'REVIEW_PASS_HISTORY_MISSING'}, counts

    # A label change cannot turn one finding on the same work into another pass.
    hashes = {eid: task['evidence'][eid]['sha256'] for eid in verified}
    receipt_hashes = {hashes[eid] for row in passes if isinstance(row, dict)
                      and isinstance(row.get('evidence'), list)
                      for eid in row['evidence'] if isinstance(eid, str) and eid in hashes}
    seen_receipts = set()
    seen_work = set()
    final_reviewed = set()
    for sequence, row in enumerate(passes, 1):
        try:
            kind = row['kind']
            fields = ('focus', 'finding', 'disposition')
            if kind not in counts or any(not isinstance(row[k], str) or not row[k].strip() for k in fields):
                raise ValueError('review type, purpose, finding and disposition required')
            ids = row['reviewed']
            if (not isinstance(ids, list) or not ids or
                    any(not isinstance(i, str) or i not in verified for i in ids) or len(set(ids)) != len(ids)):
                raise ValueError('reviewed material is absent or duplicated')
            receipts = row['evidence']
            if not isinstance(receipts, list) or len(receipts) != 1:
                raise ValueError('one independent pass record required')
            raw = verified[receipts[0]]
            receipt = json.loads(raw)
            digests = {i: hashes[i] for i in ids}
            if receipt_hashes.intersection(digests.values()):
                errors.add('REVIEW_RECEIPT_USED_AS_WORK')
                raise ValueError('pass receipt cannot stand in for examined material')
            if (receipt['task_id'] != task['task_id'] or type(receipt['sequence']) is not int or
                    receipt['sequence'] != sequence or receipt['kind'] != kind or
                    any(receipt[k] != row[k] for k in fields) or receipt['reviewed_sha256'] != digests):
                raise ValueError('pass record does not match its task, position, or reviewed material')
            receipt_hash = hashes[receipts[0]]
            work = (tuple(sorted(set(digests.values()))),
                    ' '.join(row['finding'].casefold().split()), ' '.join(row['disposition'].casefold().split()))
            if receipt_hash in seen_receipts or work in seen_work:
                raise ValueError('replayed receipt or duplicate work')
            seen_receipts.add(receipt_hash)
            seen_work.add(work)
            counts[kind] += 1
            if sequence == len(passes) and kind == 'editorial':
                final_reviewed = set(ids)
        except (ValueError, KeyError, TypeError, UnicodeError):
            errors.add('REVIEW_PASS_NOT_VERIFIED:' + str(sequence))
    if counts['substantive'] < MIN_SUBSTANTIVE_PASSES:
        errors.add('EIGHT_SUBSTANTIVE_REPASSES_REQUIRED')
    outputs = task.get('outputs')
    if (not isinstance(outputs, list) or not outputs or not final_reviewed or
            any(not isinstance(o, dict) or not isinstance(o.get('evidence'), str) or
                o['evidence'] not in final_reviewed for o in outputs)):
        errors.add('FINAL_EDITORIAL_PASS_NOT_VERIFIED')
    return errors, counts


def read_evidence(task, evidence_root):
    errors = set()
    evidence, verified = task.get('evidence', {}), {}
    if not isinstance(evidence, dict):
        errors.add('EVIDENCE_INVALID')
        evidence = {}
    for eid, item in evidence.items():
        try:
            path = confined(evidence_root, item['path'])
            raw = path.read_bytes()
            if not raw or fingerprint(raw) != item['sha256']:
                raise ValueError('evidence changed/empty')
            if not item.get('provenance') or not item.get('method') or item.get('result') != 'verified':
                raise ValueError('evidence verification missing')
            if item['method'] in {'attestation', 'filename', 'metadata_only'}:
                raise ValueError('assertion is not performance evidence')
            verified[eid] = raw
        except (OSError, ValueError, KeyError, TypeError):
            errors.add('EVIDENCE_INVALID:' + str(eid))
    return evidence, verified, errors


def location_checks(task, verified, now):
    errors = set()
    def proof(ids):
        return isinstance(ids, list) and bool(ids) and all(isinstance(i, str) and i in verified for i in ids)
    locations = task.get('locations', {})
    if set(locations) != LOCATIONS:
        errors.add('LOCATION_MEMBERSHIP_MISMATCH')
    for kind in LOCATIONS:
        loc = locations.get(kind, {})
        if loc.get('state') != 'considered' or not proof(loc.get('evidence')):
            errors.add('LOCATION_OPEN:' + kind)
            continue
        try:
            before = json.loads(verified[loc['before']])
            after = json.loads(verified[loc['after']])
            review = json.loads(verified[loc['review']])
            if any(loc[k] not in loc.get('evidence', []) for k in ('before', 'after', 'review')):
                raise ValueError('unbound inventory')
            # Independent reads have different observation times. Compare the
            # complete source projection separately; never ignore membership,
            # version, boundary, authority or unknown envelope-field changes.
            before_projection = {k: v for k, v in before.items() if k != 'observed_at'}
            after_projection = {k: v for k, v in after.items() if k != 'observed_at'}
            if before_projection != after_projection:
                raise ValueError('inventory drift')
            if before['task_id'] != task['task_id'] or review['task_id'] != task['task_id'] or before['boundary'] != loc['boundary']:
                raise ValueError('foreign receipt')
            timestamps = [datetime.fromisoformat(record['observed_at'])
                          for record in (before, after)]
            for timestamp in timestamps:
                if timestamp.tzinfo is None or not 0 <= (now - timestamp).total_seconds() <= 86400:
                    raise ValueError('stale or future snapshot')
            if timestamps[1] < timestamps[0]:
                raise ValueError('snapshot observation order reversed')
            inventory = before['items']
            members = [(i['id'], i['version']) for i in inventory]
            considered = [(i['id'], i['version']) for i in review['items']]
            if len(members) != len(set(members)) or len(considered) != len(set(considered)) or set(members) != set(considered):
                raise ValueError('coverage does not reconcile')
            if not before.get('authority') or not loc.get('discovery_method'):
                raise ValueError('unidentified boundary')
            for item in review['items']:
                if not item.get('reason') or item.get('state') not in {'content_reviewed', 'screened_no_match', 'unavailable'}:
                    raise ValueError('no source disposition')
                if item.get('relevant') is not False and item.get('state') != 'content_reviewed':
                    raise ValueError('required relevant content unavailable')
                if item['state'] == 'content_reviewed' and (not proof(item.get('evidence')) or not item.get('portion_reviewed') or not item.get('where_used')):
                    raise ValueError('content-review proof missing')
            if kind == 'internet':
                queries = loc['queries']
                if not queries or any(not q.get('query') or not q.get('searched_at') or not proof(q.get('evidence')) for q in queries):
                    raise ValueError('internet search missing')
                for item in review['items']:
                    if not item.get('url', '').startswith(('https://', 'http://')) or not item.get('publisher') or not item.get('title') or not item.get('accessed_at'):
                        raise ValueError('source bibliography incomplete')
        except (OSError, ValueError, KeyError, TypeError):
            errors.add('COVERAGE_NOT_VERIFIED:' + kind)
    return errors


def entry_bindings(task, verified):
    entry = task['assessment_research']
    reviews = {kind: task['locations'][kind]['review'] for kind in sorted(LOCATIONS)}
    pending = [entry['scope'], entry['research'], *reviews.values()]
    bound = {}
    while pending:
        eid = pending.pop()
        if eid in bound:
            continue
        raw = verified[eid]
        source = task['evidence'][eid]
        bound[eid] = fingerprint([fingerprint(raw), source['provenance'], source['method']])
        # Records refer to underlying originals, searches, extracts and request bytes by ID.
        # New report evidence can be appended later without changing this closed research set.
        try:
            values = [json.loads(raw)]
        except (UnicodeError, ValueError):
            continue
        while values:
            value = values.pop()
            if isinstance(value, dict):
                values.extend(value.values())
            elif isinstance(value, list):
                values.extend(value)
            elif isinstance(value, str) and value in verified and value not in bound:
                pending.append(value)
    return {
        'scope_sha256': fingerprint(verified[entry['scope']]),
        'research_sha256': fingerprint(verified[entry['research']]),
        'location_reviews': {kind: fingerprint(verified[ref]) for kind, ref in reviews.items()},
        'research_evidence_sha256': fingerprint(bound),
    }


def make_entry_checkpoint(root, catalog, task, evidence_root, now=None):
    now = now or datetime.now(timezone.utc)
    _, verified, errors = read_evidence(task, evidence_root)
    if task.get('task_type') != 'assessment' or not task.get('task_id') or not task.get('objective'):
        errors.add('ASSESSMENT_SCOPE_REQUIRED')
    if not task.get('scope', {}).get('authorization') or not task.get('scope', {}).get('boundary'):
        errors.add('SCOPE_OR_AUTHORIZATION_MISSING')
    if register(root) != catalog or task.get('register_sha256') != catalog.get('register_sha256'):
        errors.add('AUTHORITY_OR_REGISTER_DRIFT')
    errors.update(location_checks(task, verified, now))
    errors.update(check_research_entry(task, verified, now, preflight=True))
    recommendations = task.get('analytical_review', {}).get('recommendations', {})
    if (task.get('assessment_research', {}).get('analysis') or task.get('outputs') or
            recommendations.get('state') == 'reviewed'):
        errors.add('ENTRY_AFTER_SUBSTANTIVE_ASSESSMENT')
    return {'kind': 'assessment_research_entry', 'task_id': task.get('task_id'),
            'checked_at': now.isoformat(), 'register_sha256': catalog.get('register_sha256'),
            'task_sha256': fingerprint(task), 'result': 'entry_verified' if not errors else 'candidate_only',
            'errors': sorted(errors), 'prior_evidence_sha256': sorted({fingerprint(raw) for raw in verified.values()}),
            'bindings': entry_bindings(task, verified) if not errors else {}}


def check_entry_checkpoint(task, verified, catalog, now, journal_path):
    try:
        checkpoint = json.loads(verified[task['assessment_entry_receipt']])
        entry = task['assessment_research']
        scope = json.loads(verified[entry['scope']])
        research = json.loads(verified[entry['research']])
        analysis = json.loads(verified[entry['analysis']])
        examined = {eid for row in task.get('review_passes', []) if isinstance(row, dict)
                    for eid in row.get('reviewed', []) if isinstance(eid, str)}
        delivered = {row.get('evidence') for row in task.get('outputs', []) if isinstance(row, dict)}
        if (analysis['output'] not in examined | delivered or
                fingerprint(verified[analysis['output']]) in checkpoint['prior_evidence_sha256']):
            raise ValueError('the recorded first analysis has no link to the reviewed or delivered work')
        start, research_at, checked_at, analysis_at = (
            datetime.fromisoformat(value) for value in
            (scope['at'], research['at'], checkpoint['checked_at'], analysis['at']))
        if not journal_path or checkpoint not in [event['result'] for event in read_journal(
                journal_path, task['task_id'])['events']]:
            raise ValueError('the retained task journal does not contain this entry decision')
        if (checkpoint['kind'] != 'assessment_research_entry' or
                checkpoint['task_id'] != task['task_id'] or checkpoint['result'] != 'entry_verified' or
                checkpoint['register_sha256'] != catalog['register_sha256'] or
                checkpoint['errors'] != [] or checkpoint['bindings'] != entry_bindings(task, verified) or
                not start <= research_at <= checked_at < analysis_at <= now):
            raise ValueError('entry record no longer matches the assessed research or its timing')
    except (KeyError, ValueError, TypeError, UnicodeError, OSError):
        return {'PROSPECTIVE_ASSESSMENT_ENTRY_NOT_VERIFIED'}
    return set()


def check(root, catalog, task, evidence_root, now=None, *, journal_path=None):
    """Return fail-closed codes; never execute evidence commands or repair data."""
    errors = set()
    def fail(code):
        errors.add(code)
    try:
        current = register(root)
        if current != catalog:
            fail('AUTHORITY_OR_REGISTER_DRIFT')
    except (OSError, ValueError, KeyError, TypeError, AttributeError):
        fail('AUTHORITY_UNAVAILABLE')
    if task.get('schema_version') != VERSION or not task.get('task_id') or not task.get('objective'):
        fail('TASK_IDENTITY_INVALID')
    if task.get('register_sha256') != catalog.get('register_sha256'):
        fail('TASK_REGISTER_STALE')
    if not task.get('scope', {}).get('authorization') or not task.get('scope', {}).get('boundary'):
        fail('SCOPE_OR_AUTHORIZATION_MISSING')
    if task.get('routine_human_attestation_required') is not False:
        fail('ROUTINE_COMPLIANCE_IS_ASSISTANT_RESPONSIBILITY')
    if task.get('verification_owner') != 'Salus assistant':
        fail('VERIFICATION_OWNER_MISSING')
    evidence, verified, proof_errors = read_evidence(task, evidence_root)
    errors.update(proof_errors)
    def proof(ids):
        return isinstance(ids, list) and bool(ids) and all(isinstance(i, str) and i in verified for i in ids)
    review_errors, review_counts = review_pass_checks(task, verified)
    errors.update(review_errors)
    # A reminder is evidence of a request, never evidence of a model switch.
    def normalize_reminder(value):
        return value.translate(str.maketrans({'\u2011': '-', '\u2013': '-', '\u2014': '-'})).replace('**', '').casefold()
    def reminder_proved(eid, text_value):
        try:
            observed = json.loads(verified[eid])
            return (isinstance(observed, dict) and observed.get('task_id') == task['task_id']
                    and normalize_reminder(observed['visible_text']) == text_value)
        except (ValueError, KeyError, TypeError, AttributeError, UnicodeError):
            return False
    reminder = task.get('model_reminder', {})
    required = {'assessment': ('gpt-6.2-astra', 'highest_available', 'gpt-6.2 astra', 'highest'),
                'other': ('gpt-6.1-sol', 'medium', 'gpt-6.1 sol', 'medium')}.get(task.get('task_type'))
    try:
        text_value = normalize_reminder(reminder['text'])
        if not required or reminder['task_id'] != task['task_id'] or (
                reminder.get('model'), reminder.get('reasoning')) != required[:2]:
            raise ValueError('unclassified, foreign or mismatched reminder')
        if reminder.get('automatic_switching_claimed') is not False or not proof(reminder.get('evidence')):
            raise ValueError('no reminder proof or false automatic-switch claim')
        if not all(part in text_value for part in (required[2], required[3], 'reasoning', 'switch')):
            raise ValueError('visible reminder does not request the required settings')
        if not any(reminder_proved(eid, text_value) for eid in reminder['evidence']):
            raise ValueError('reminder text not present in retained evidence')
    except (ValueError, KeyError, TypeError, AttributeError, UnicodeError):
        fail('TASK_MODEL_REMINDER_NOT_VERIFIED')
    # Correlate all four recorded analytical duties; meaning/adequacy remains
    # an analyst responsibility backed by actual sources, tests and outputs.
    def analytical_proved(eid, lens, row):
        try:
            payload = json.loads(verified[eid])
            return (isinstance(payload, dict) and payload.get('task_id') == task['task_id']
                    and payload.get('lens') == lens and all(payload.get(k) == row[k]
                    for k in ('conclusion', 'reasoning', 'limitations')))
        except (ValueError, KeyError, TypeError, AttributeError, UnicodeError):
            return False
    analytical = task.get('analytical_review', {})
    if not isinstance(analytical, dict) or set(analytical) != ANALYTICAL_LENSES:
        fail('ANALYTICAL_REVIEW_MEMBERSHIP_MISMATCH')
    else:
        for lens, row in analytical.items():
            try:
                if not isinstance(row, dict) or row.get('state') != 'reviewed':
                    raise ValueError('analytical duty not reviewed')
                if any(not isinstance(row.get(k), str) or not row[k].strip()
                       for k in ('conclusion', 'reasoning')):
                    raise ValueError('analytical conclusion or reasoning missing')
                limits = row.get('limitations')
                if not isinstance(limits, list) or not limits or any(
                        not isinstance(v, str) or not v.strip() for v in limits):
                    raise ValueError('analytical scope/uncertainty limits missing')
                if not proof(row.get('evidence')) or not any(
                        analytical_proved(eid, lens, row) for eid in row['evidence']):
                    raise ValueError('analytical review has no current task-correlated proof')
            except (ValueError, KeyError, TypeError, AttributeError, UnicodeError):
                fail('ANALYTICAL_REVIEW_NOT_VERIFIED:' + lens)
    expected = {u['id'] for u in catalog['units']}
    records = task.get('requirements', [])
    ids = [r.get('id') for r in records if isinstance(r, dict)]
    if len(ids) != len(records) or len(ids) != len(set(ids)) or set(ids) != expected:
        fail('REQUIREMENT_MEMBERSHIP_MISMATCH')
    for item in records:
        if not isinstance(item, dict):
            continue
        state = item.get('state')
        if state not in STATES or state in {'pending', 'blocked'}:
            fail('REQUIREMENTS_OPEN')
        elif not item.get('reason') or not proof(item.get('evidence')):
            fail('REQUIREMENT_PROOF_MISSING')
        if state == 'met':
            checks = item.get('checks')
            if not isinstance(checks, list) or not checks or any(
                not c.get('criterion') or c.get('result') != 'pass' or not proof(c.get('evidence'))
                for c in checks if isinstance(c, dict)) or any(not isinstance(c, dict) for c in checks):
                fail('REQUIREMENT_ACCEPTANCE_CHECK_MISSING')
        if state == 'superseded' and item.get('superseded_by') not in expected:
            fail('SUPERSESSION_UNRESOLVED')
    pending_refs = {r['reference'] for r in catalog['references'] if r['state'] == 'unexpanded'}
    refs = task.get('references', {})
    if set(refs) != pending_refs:
        fail('REFERENCED_AUTHORITY_MEMBERSHIP_MISMATCH')
    for value in refs.values():
        if value.get('state') not in {'resolved', 'not_applicable'} or not value.get('reason') or not proof(value.get('evidence')):
            fail('REFERENCED_AUTHORITY_OPEN')
    now = now or datetime.now(timezone.utc)
    errors.update(location_checks(task, verified, now))
    if task.get('task_type') == 'assessment':
        errors.update(check_research_entry(task, verified, now))
        errors.update(check_entry_checkpoint(task, verified, catalog, now, journal_path))
    capture = task.get('capture', {})
    if capture.get('state') != 'reconciled' or capture.get('expected') != capture.get('retained') or not isinstance(capture.get('expected'), int) or capture.get('expected', 0) < 1 or not proof(capture.get('evidence')) or not capture.get('destination'):
        fail('CAPTURE_NOT_RECONCILED')
    holds = task.get('holds', {})
    if not proof(holds.get('before_evidence')) or not proof(holds.get('after_evidence')):
        fail('HOLD_STATE_PROOF_MISSING')
    else:
        try:
            before = json.loads(verified[holds['before_evidence'][0]])
            after = json.loads(verified[holds['after_evidence'][0]])
            if before != after or before != holds['expected']:
                fail('PROTECTED_HOLD_STATE_DRIFT')
        except (ValueError, KeyError, TypeError):
            fail('HOLD_STATE_INVALID')
    outputs = task.get('outputs', [])
    if not isinstance(outputs, list):
        fail('OUTPUT_VERIFICATION_MISSING')
        outputs = []
    for item in outputs:
        if not isinstance(item, dict):
            fail('OUTPUT_VERIFICATION_MISSING')
            continue
        if not proof([item.get('evidence')]) or not item.get('claim') or not proof(item.get('verification_evidence')):
            fail('OUTPUT_VERIFICATION_MISSING')
        if item.get('format') in {'docx', 'pdf', 'pptx'}:
            try:
                qa = json.loads(verified[item['page_review']])
                if qa['artifact_sha256'] != evidence[item['evidence']]['sha256'] or type(qa['pages']) is not int or qa['pages'] < 1 or sorted(qa['reviewed_pages']) != list(range(1, qa['pages'] + 1)) or qa['defects_open'] != 0:
                    raise ValueError('exact rendered-page coverage missing')
            except (ValueError, TypeError, KeyError):
                fail('DOCUMENT_EXACT_PAGE_REVIEW_MISSING')
    for action in task.get('protected_actions', []):
        try:
            approval = json.loads(verified[action['approval_evidence']])
            if approval['actor_role'] != 'human' or approval['decision'] != 'authorized' or approval['action'] != action['action'] or approval['target'] != action['target'] or not approval['source_reference']:
                raise ValueError('human approval mismatch')
        except (ValueError, KeyError, TypeError):
            fail('HUMAN_AUTHORIZATION_MISSING_OR_MISMATCHED')
    corrections = task.get('corrective_actions', [])
    if not isinstance(corrections, list) or len({c.get('id') for c in corrections if isinstance(c, dict)}) != len(corrections) or any(not isinstance(c, dict) or not c.get('id')
            or not c.get('cause') or not c.get('affected_work') or not c.get('correction')
            or not proof(c.get('evidence')) for c in corrections):
        fail('CORRECTIVE_ACTION_PROOF_INVALID')
        corrections = []
    return {'schema_version': VERSION, 'task_id': task.get('task_id'),
            'checked_at': now.isoformat(), 'register_sha256': catalog.get('register_sha256'),
            'task_sha256': fingerprint(task), 'evidence_sha256': fingerprint(evidence),
            'result': 'verified_record' if not errors else 'incomplete',
            'errors': sorted(errors), 'counts': {'requirements': len(expected),
                                               'verified_evidence': len(verified),
                                               'verified_substantive_passes': review_counts['substantive'],
                                               'verified_editorial_passes': review_counts['editorial']},
            'verified_evidence_ids': sorted(verified), 'correction_annotations': corrections,
            'limits': 'Record/coverage/integrity verification only; no semantic truth, human authenticity, inaccessible corpus or cross-chat enforcement guarantee.'}


def save(path, value, exclusive=False):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    data = (json.dumps(value, ensure_ascii=False, indent=2) + '\n').encode()
    if exclusive:
        with path.open('xb') as f:
            f.write(data)
    else:
        fd, tmp = tempfile.mkstemp(dir=path.parent, prefix='.compliance-')
        try:
            with os.fdopen(fd, 'wb') as f:
                f.write(data)
                f.flush()
                os.fsync(f.fileno())
            os.replace(tmp, path)
        finally:
            if os.path.exists(tmp):
                os.unlink(tmp)
    if path.read_bytes() != data:
        raise OSError('durable readback failed')


def reconcile(task, catalog):
    """Preserve prior applicability/proof; reopen all checks after authority drift."""
    # Reconciliation of an older open task starts its new ledger empty.
    result = dict(task)
    result.setdefault('review_passes', [])
    if task.get('task_type') == 'assessment':
        result.setdefault('assessment_research', {})
    if task.get('register_sha256') == catalog['register_sha256']:
        return result
    updated = new_task(catalog, task['task_id'], task['objective'])
    result['authority_history'] = list(task.get('authority_history', [])) + [{
        'register_sha256': task['register_sha256'],
        'requirements': task['requirements'], 'references': task['references'],
        'task_sha256': fingerprint(task)}]
    result.update(register_sha256=updated['register_sha256'],
                  requirements=updated['requirements'], references=updated['references'])
    return result


def read_journal(path, task_id):
    """Read and verify the local task history before trusting or extending it."""
    path = Path(path)
    state = load(path) if path.exists() else {'task_id': task_id, 'events': [], 'corrections': {}}
    if state.get('task_id') != task_id:
        raise ValueError('foreign task journal')
    if state['events'] and state['events'][-1]['corrections_sha256'] != fingerprint(state['corrections']):
        raise ValueError('corrective-action history changed')
    previous = '0' * 64
    for event in state['events']:
        payload = {k: v for k, v in event.items() if k != 'event_sha256'}
        if payload['previous_sha256'] != previous or fingerprint(payload) != event['event_sha256']:
            raise ValueError('journal history changed')
        previous = event['event_sha256']
    return state


def _journal_unlocked(path, result):
    state = read_journal(path, result['task_id'])
    previous = state['events'][-1]['event_sha256'] if state['events'] else '0' * 64
    errors = set(result['errors'])
    for code in errors:
        cid = 'CAPA-' + fingerprint([result['task_id'], code])[:16]
        row = state['corrections'].setdefault(cid, {'code': code, 'owner': 'Salus assistant',
            'cause': '', 'affected_work': '', 'correction': '', 'evidence': [], 'history': []})
        row['state'] = 'open'
        row['history'].append({'at': result['checked_at'], 'state': 'observed', 'task_sha256': result['task_sha256']})
    for annotation in result.get('correction_annotations', []):
        if annotation['id'] not in state['corrections']:
            raise ValueError('unknown corrective action')
        row = state['corrections'][annotation['id']]
        row.update({k: annotation[k] for k in ('cause', 'affected_work', 'correction', 'evidence')})
    for row in state['corrections'].values():
        if row['state'] == 'open' and row['code'] not in errors and result['result'] == 'verified_record':
            if all(row.get(k) for k in ('cause', 'affected_work', 'correction', 'evidence')) and all(e in result['verified_evidence_ids'] for e in row['evidence']):
                row['state'] = 'corrected_and_rechecked'
                row['history'].append({'at': result['checked_at'], 'state': row['state'], 'task_sha256': result['task_sha256'], 'evidence_sha256': result['evidence_sha256']})
    if result['result'] == 'verified_record' and any(r['state'] == 'open' for r in state['corrections'].values()):
        result['result'] = 'incomplete'
        result['errors'] = sorted(set(result['errors']) | {'CORRECTIVE_ACTION_DETAIL_OR_RETEST_OPEN'})
    payload = {'previous_sha256': previous, 'result': result,
               'corrections_sha256': fingerprint(state['corrections'])}
    state['events'].append({**payload, 'event_sha256': fingerprint(payload)})
    save(path, state)


def journal(path, result):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    lock = path.with_name(path.name + '.lock')
    with lock.open('x', encoding='utf-8') as handle:
        handle.write(result['task_id'])
        handle.flush()
    try:
        _journal_unlocked(path, result)
    finally:
        lock.unlink()


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('command', choices=['register', 'init', 'reconcile', 'research-entry', 'verify'])
    parser.add_argument('--root', type=Path, required=True)
    parser.add_argument('--register', type=Path, required=True)
    parser.add_argument('--task', type=Path)
    parser.add_argument('--task-id')
    parser.add_argument('--objective')
    parser.add_argument('--task-type', choices=['assessment', 'other'])
    parser.add_argument('--evidence-root', type=Path)
    parser.add_argument('--receipt', type=Path)
    parser.add_argument('--journal', type=Path)
    args = parser.parse_args(argv)
    try:
        if args.command == 'register':
            if args.register.suffix != '.json':
                raise ValueError('register must be JSON, never an authority source')
            save(args.register, register(args.root))
        elif args.command in {'init', 'reconcile'}:
            if not args.task or (args.command == 'init' and (not args.task_id or not args.objective)):
                raise ValueError('task arguments required')
            if args.task.resolve().is_relative_to(args.root.resolve()):
                raise ValueError('task records belong outside source repository')
            catalog = load(args.register)
            if catalog != register(args.root):
                raise ValueError('stale register')
            if args.command == 'init':
                save(args.task, new_task(catalog, args.task_id, args.objective,
                                        args.task_type or 'unclassified'), exclusive=True)
            else:
                save(args.task, reconcile(load(args.task), catalog))
        else:
            if not all([args.task, args.evidence_root, args.receipt, args.journal]):
                raise ValueError('verification arguments required')
            task = load(args.task)
            catalog = load(args.register)
            inputs = {args.task.resolve(), args.register.resolve()}
            for e in task.get('evidence', {}).values():
                inputs.add(confined(args.evidence_root, e['path']))
            targets = {args.receipt.resolve(), args.journal.resolve()}
            if len(targets) != 2 or targets & inputs or any(t.is_relative_to(args.root.resolve()) for t in targets):
                raise ValueError('record destinations must be separate and outside repository/authority root')
            if args.command == 'research-entry':
                result = make_entry_checkpoint(args.root, catalog, task, args.evidence_root)
                save(args.receipt, result, exclusive=True)
                # A receipt alone cannot establish a prior event. If journaling fails, retain
                # the unanchored candidate and retry to a fresh path after repairing the ledger.
                journal(args.journal, result)
                print(json.dumps({'result': result['result'], 'errors': result['errors']}))
                return 0 if result['result'] == 'entry_verified' else 2
            result = check(args.root, catalog, task, args.evidence_root, journal_path=args.journal)
            journal(args.journal, result)
            save(args.receipt, result)
            print(json.dumps({'task_id': result['task_id'], 'result': result['result'],
                              'error_count': len(result['errors']), 'counts': result['counts']}))
            return 0 if result['result'] == 'verified_record' else 2
        return 0
    except (OSError, ValueError, KeyError, TypeError):
        print('TASK_COMPLIANCE_INVALID_OR_UNAVAILABLE')
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
