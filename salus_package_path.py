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
    if units == 'Group' and group == 'Yes':
        band, reason = 'C', 'You described a group decision that needs priorities across named units.'
    elif units == 'Two' and separate == 'Yes' and group == 'No':
        band, reason = 'B', 'You described separate findings and a comparison for two units or distinct operations.'
    elif units == 'One' and separate == 'No' and group == 'No':
        band, reason = 'A', 'You described one covered operation and one combined decision.'
    else:
        band, reason = '', 'The covered units, comparisons and group priorities need a short scoping conversation before Salus suggests a band.'
    if band == 'A':
        next_step = ('Start with the fixed $1,500 prepaid Level 1A Access assessment for one named unit. Save other needs for a later human discussion and separate quote after qualified reports.')
    elif band:
        next_step = (f'Start with the fixed $1,500 prepaid Level 1A Access assessment for one named unit; the possible Level 1{band} need is considered and priced separately after qualified Level 1A completion.')
    else:
        next_step = 'Choose the first named Level 1A Access unit at the fixed $1,500 prepaid price; save wider or deeper needs for discussion and separate pricing after qualified reports.'
    return {
        'label': f'Possible Level 1{band}' if band else 'Level 1 band to confirm',
        'band': band,
        'reason': reason,
        'next_step': next_step,
        'status': 'Provisional — starting unit and any later scope need confirmation',
        'required_first_path': 'Level 1A',
        'later_path': f'Possible Level 1{band}' if band in {'B', 'C'} else '',
    }


def draft_level_1_scope_receipt(profile: dict, path: dict[str, str]) -> dict:
    """Give the prospect a short preparation record, not a quote or contract."""
    boundary = str(profile.get('covered_operation') or 'the operation to confirm')
    price = ('$1,500 prepaid for the first named Level 1A Access unit. Wider or deeper work is not added to that price; Salus discusses and quotes it after the qualified Level 1A reports')
    return {
        'version': 'SPA-SCOPE-RECEIPT-0.6.0',
        'receipt_id': '',  # Bound to the single submission identity at save time.
        'status': 'Provisional preparation summary — no assessment or purchase authorized',
        'lead_sentence': (f'Level 1A is the required starting point for one named unit within {boundary}. ' + (f'{path["label"]} describes a possible later, separately scoped need. ' if path['band'] in {'B', 'C'} else '') + f'The price is {price}.'),
        'requested_boundary': str(profile.get('covered_operation') or 'Operation or function to confirm'),
        'requested_location': str(profile.get('facility_locations') or 'Location to confirm'),
        'possible_path': path['label'],
        'outside_boundary': 'Other sites and functions are outside the first $1,500 Level 1A Access assessment. Any added coverage requires a later discussion, separate written scope, price and authorization after the qualified first reports.',
        'member_prepares': [
            'A simple organization chart showing reporting lines, decision authority and role responsibilities.',
            'If available: a site or floor map, emergency or continuity plan and recent incident summary.',
            'If available: a list of critical utilities and suppliers, without passwords or sensitive access details.',
        ],
        'salus_deliverable': 'A qualified Level 1 package contains separate SalINTEL, SalTHIRA, SalOPS and SalCAPA reports for the agreed boundary.',
        'price_state': 'The first Level 1A Access unit is $1,500 prepaid, with applicable tax shown before checkout. Other Part 2 selections are not priced add-ons; additional work is discussed and separately quoted after qualified Level 1A reports.',
        'schedule_state': 'Start and delivery dates are set in the written scope after Salus confirms capacity and receives authorization.',
        'decision_owner': str(profile.get('decision_authority') or 'Assign a decision role before agreeing to Level 1.'),
        'records_coordinator': str(profile.get('records_coordinator_role') or 'Assign a records coordinator before authorized file transfer.'),
        'next_step': 'Choose one named Level 1A Access unit and its exclusions, then review the exact $1,500 prepaid agreement and applicable tax. Revisit wider needs with Salus after qualified Level 1A reports.',
        'milestones': [
            {'step': 'Confirm scope', 'owner': 'Protected Member decision owner', 'complete_when': 'The exact first Level 1A Access unit, exclusions and fixed $1,500 price are recorded.'},
            {'step': 'Provide records', 'owner': 'Authorized records coordinator', 'complete_when': 'The agreed minimum packet or a missing-record explanation is received securely.'},
            {'step': 'Complete assessment', 'owner': 'Qualified Salus team', 'complete_when': 'The four scoped reports pass evidence, analyst and quality review.'},
            {'step': 'Review results', 'owner': 'Salus and decision owner', 'complete_when': 'Findings, limits and options are explained to the Member.'},
            {'step': 'Decide actions', 'owner': 'Protected Member decision owner', 'complete_when': 'Selected, deferred or declined actions and owners are recorded.'},
        ],
        'choices': [
            {'choice': 'Correct the scope', 'effect': 'Revise the first one-unit boundary before agreement or payment; wider needs remain separate.'},
            {'choice': 'Discuss later work', 'effect': 'The first Access unit stays fixed at $1,500; Salus discusses and quotes any additional scope after qualified Level 1A reports.'},
            {'choice': 'Discuss a separate service', 'effect': 'Salus checks suitability and sends a separate proposal if appropriate.'},
            {'choice': 'Decline for now', 'effect': 'No assessment or separate service begins.'},
        ],
    }
