"""Member-neutral package-path rules shared by SalCAPA and future Advisor routing.

These values describe a request. They do not establish eligibility, a quote,
predecessor completion, professional findings, or authority to perform work.
"""


def validate_requested_package_path(level: int, band: str, variant: str) -> None:
    if level not in (0, 1, 2, 3) or band not in ('', 'A', 'B', 'C') or variant not in ('', 'Access', 'Standard'):
        raise ValueError('Choose a valid requested package level, band and Access/Standard option.')
    if (level == 0) != (band == ''):
        raise ValueError('Choose both a requested level and band, or leave both unscoped.')
    if variant and (level != 1 or band != 'A'):
        raise ValueError('Access and Standard options apply only to a requested Level 1A path.')


def requested_package_label(level: int, band: str, variant: str = '') -> str:
    validate_requested_package_path(level, band, variant)
    if level == 0:
        return 'Unscoped'
    return f'Level {level}{band}' + (f' {variant}' if variant else '')


def suggest_provisional_level_1_path(profile: dict) -> dict[str, str]:
    """Suggest a scope discussion, never approve eligibility or a price quote.

    The Member's decision boundary and need for distinct findings drive this
    suggestion. Revenue, headcount, brand and address count alone do not.
    """
    units = profile.get('decision_units', 'Not sure')
    separate = profile.get('separate_findings', 'Not sure')
    group = profile.get('group_priorities', 'Not sure')
    if group == 'Yes' or units == 'Group':
        band, reason = 'C', 'You described a group decision that needs priorities across named units.'
    elif separate == 'Yes' or units == 'Two':
        band, reason = 'B', 'You described separate findings and a comparison for two units or distinct operations.'
    elif units == 'One' and separate == 'No' and group == 'No':
        band, reason = 'A', 'You described one covered operation and one combined decision.'
    else:
        band, reason = '', 'The covered units and decision still need a short scoping conversation.'
    if band == 'A':
        next_step = ('Salus will check whether the simple Level 1A Access scope qualifies '
                     'for the $1,500 price or whether Level 1A Standard needs a separate quote.')
    elif band:
        next_step = f'Salus will confirm the Level 1{band} boundary and give you a written quote.'
    else:
        next_step = 'Salus will clarify the boundary before recommending a band or a price.'
    return {
        'label': f'Possible Level 1{band}' if band else 'Level 1 band to confirm',
        'band': band,
        'reason': reason,
        'next_step': next_step,
        'status': 'Provisional — Salus scope review required',
    }


def draft_level_1_scope_receipt(profile: dict, path: dict[str, str]) -> dict:
    """Give the prospect a short preparation record, not a quote or contract."""
    boundary = str(profile.get('covered_operation') or 'the operation to confirm')
    price = ('$1,500 if Salus confirms Level 1A Access eligibility and the written scope'
             if path['band'] == 'A' else 'a written price after Salus confirms the scope')
    return {
        'version': 'SPA-SCOPE-RECEIPT-0.3.0',
        'receipt_id': '',  # Bound to the single submission identity at save time.
        'status': 'Draft for Salus review — no assessment or purchase authorized',
        'lead_sentence': f'{path["label"]} is a starting point for {boundary}; the price is {price}.',
        'requested_boundary': str(profile.get('covered_operation') or 'Operation or function to confirm'),
        'requested_location': str(profile.get('facility_locations') or 'Location to confirm'),
        'possible_path': path['label'],
        'outside_boundary': 'Other sites and functions remain outside the proposed scope unless the written agreement names them.',
        'member_prepares': [
            'A simple organization chart showing reporting lines, decision authority and role responsibilities.',
            'If available: a site or floor map, emergency or continuity plan and recent incident summary.',
            'If available: a list of critical utilities and suppliers, without passwords or sensitive access details.',
        ],
        'salus_deliverable': 'A qualified Level 1 package contains separate SalINTEL, SalTHIRA, SalOPS and SalCAPA reports for the agreed boundary.',
        'price_state': ('Level 1A Access is $1,500 only if Salus confirms eligibility and the written scope.'
                        if path['band'] == 'A' else 'Salus will give a written price after confirming the scope.'),
        'schedule_state': 'Start and delivery dates are set in the written scope after Salus confirms capacity and receives authorization.',
        'decision_owner': str(profile.get('decision_authority') or 'Authorized role to confirm'),
        'next_step': 'Review the boundary and available records with Salus; then accept or decline a written scope and fee.',
        'milestones': [
            {'step': 'Confirm scope', 'owner': 'Salus and decision owner', 'complete_when': 'Covered unit, exclusions and eligibility are agreed in writing.'},
            {'step': 'Provide records', 'owner': 'Authorized records coordinator', 'complete_when': 'The agreed minimum packet or a missing-record explanation is received securely.'},
            {'step': 'Complete assessment', 'owner': 'Qualified Salus team', 'complete_when': 'The four scoped reports pass evidence, analyst and quality review.'},
            {'step': 'Review results', 'owner': 'Salus and decision owner', 'complete_when': 'Findings, limits and options are explained to the Member.'},
            {'step': 'Decide actions', 'owner': 'Protected Member decision owner', 'complete_when': 'Selected, deferred or declined actions and owners are recorded.'},
        ],
        'choices': [
            {'choice': 'Correct the scope', 'effect': 'Salus reviews the changed boundary before quoting.'},
            {'choice': 'Request a fixed quote', 'effect': 'Salus validates eligibility and sends a written scope and fee for acceptance.'},
            {'choice': 'Discuss a separate service', 'effect': 'Salus checks suitability and sends a separate proposal if appropriate.'},
            {'choice': 'Decline for now', 'effect': 'No assessment or separate service begins.'},
        ],
    }
