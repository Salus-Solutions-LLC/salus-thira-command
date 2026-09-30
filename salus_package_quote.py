"""Pure validation and immutable digest rules for a Salus package quote."""

import hashlib
import json
from datetime import date, datetime, timezone

from salus_package_path import validate_requested_package_path


def validate_quote(data: dict, requested: dict) -> None:
    level, band, variant = data['level'], data['band'], data['variant']
    validate_requested_package_path(level, band, variant)
    if level == 0 or not band:
        raise ValueError('A quote requires a Level 1, 2 or 3 package and a band.')
    if (level, band, variant) != (
        requested['requested_package_level'],
        requested['requested_scope_band'],
        requested['requested_access_variant'],
    ):
        raise ValueError('The quote must match the requested package path; update the scope first.')
    if not data['covered_operation'].strip() or not data['decision_owner'].strip():
        raise ValueError('Name the covered operation and the Member decision owner.')
    if not data['exclusions'].strip() or not data['scope_basis'].strip():
        raise ValueError('Name the exclusions and the basis for this scope.')
    for field in ('included_work','member_inputs','evidence_allowance','clarification_allowance',
                  'field_specialist_terms','payment_terms','tax_treatment','change_triggers'):
        if not data[field].strip():
            raise ValueError(f'The written quote must state {field.replace("_", " ")}.')
    if not data['agreement_reference'].strip() or len(data['agreement_sha256']) != 64:
        raise ValueError('Identify the exact agreement version and its SHA-256 digest.')
    if not data['capacity_confirmed']:
        raise ValueError('Salus must confirm capacity before issuing a quote.')
    if data['fee_cents'] <= 0 or data['fee_cents'] > 1_000_000_000:
        raise ValueError('Enter an approved positive package fee in cents.')
    if data['currency'] != 'USD':
        raise ValueError('Only USD quotes are supported in this candidate.')
    if date.fromisoformat(data['valid_until']) < datetime.now(timezone.utc).date():
        raise ValueError('The quote validity date has passed.')
    if level == 1 and band == 'A' and variant == 'Access':
        if not data['access_eligibility_confirmed'] or not data['access_eligibility_basis'].strip():
            raise ValueError('Document Level 1A Access eligibility before using its fixed fee.')
        if data['fee_cents'] != 150_000:
            raise ValueError('Eligible Level 1A Access has a $1,500 package fee.')
    elif data['access_eligibility_confirmed']:
        raise ValueError('Access eligibility applies only to Level 1A Access.')


def quote_digest(data: dict) -> str:
    canonical = json.dumps(data, sort_keys=True, separators=(',', ':'), ensure_ascii=False)
    return hashlib.sha256(canonical.encode('utf-8')).hexdigest()


def assessment_scope_digest(assessment: dict) -> str:
    """Bind a quote to the complete governed assessment decision boundary."""
    keys = ('version', 'organization', 'purpose', 'mission', 'scope', 'covered_operation',
            'exclusions', 'requested_package_level', 'requested_scope_band',
            'requested_access_variant')
    canonical = json.dumps({key: assessment[key] for key in keys},
                           sort_keys=True, separators=(',', ':'), ensure_ascii=False)
    return hashlib.sha256(canonical.encode('utf-8')).hexdigest()
