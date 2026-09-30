"""Versioned, selective Level 1 records menu; no personal directories or files."""

CATALOG_VERSION = 'L1-INTAKE-1.0.0'

ITEMS = {
    'GOV': ('Governance and roles',
            'Show who can decide, delegate and coordinate for the covered work.',
            'Current charter or bylaws and a simple organization chart with roles and responsibilities.',
            'A one-page role and authority summary is acceptable.'),
    'FUN': ('Essential work and locations',
            'Define the functions and people affected by an interruption.',
            'A short list of essential work, included sites and aggregate people served.',
            'An existing operations summary is acceptable; omit personal rosters.'),
    'PLAN': ('Current response and continuity plans',
             'Compare planned actions with the decision the Member needs to make.',
             'Current emergency, continuity or crisis communication plans and effective dates, if held.',
             'A short description of actual practice is acceptable if no plan exists.'),
    'INC': ('Recent incident and exercise lessons',
            'Identify demonstrated strengths and unresolved actions.',
            'Redacted summaries of relevant incidents, exercises and corrective actions, if held.',
            'A dated short summary is acceptable; omit personal case details.'),
    'DEP': ('Critical utilities and suppliers',
            'Find interruption dependencies and possible single points of failure.',
            'A high-level list of essential utilities, systems, suppliers and responsible roles.',
            'An existing dependency map is acceptable; do not send credentials or security details.'),
    'MAP': ('Site or function map',
            'Check the covered boundary, access and nearby dependencies.',
            'An available public or Member-approved site, floor or function map.',
            'A simple sketch or written boundary description is acceptable.'),
    'AUTH': ('Decision and emergency-spending rules',
             'Check who can approve actions when normal processes are disrupted.',
             'Current delegation, succession and emergency-spending policy, if held.',
             'A role-based summary is acceptable; disputed authority needs counsel review.'),
    'STAFF': ('Critical staffing and partner roles',
              'Identify role coverage, qualifications and external dependencies.',
              'Role counts and partner agreement types relevant to the covered work.',
              'An aggregate role summary is acceptable; do not send personnel files.'),
    'FIN': ('Insurance and recovery resources',
            'Test whether the Member can fund and authorize recovery options.',
            'Policy schedule, main limits and reserve or budget range, if held.',
            'A broker or finance-owner summary is acceptable; detailed policies may follow later.'),
    'COMP': ('Permits, licenses and inspections',
             'Screen applicable duties and current evidence without assuming a violation.',
             'Existing compliance register or relevant permit and inspection list, if held.',
             'A list of known authorities and record custodians is acceptable.'),
    'PRIO': ('Leadership priorities and constraints',
             'Focus the assessment on decisions that matter to the Member.',
             'A short statement of priorities, timing, constraints and prior actions.',
             'A brief role-approved note is acceptable.'),
}

INITIAL_KEYS = ('GOV', 'FUN', 'PLAN', 'INC', 'DEP', 'MAP', 'PRIO')


def catalog_rows():
    return [dict(key=key, title=fields[0], decision_use=fields[1], requested_form=fields[2],
                 acceptable_equivalent=fields[3], initial_candidate=key in INITIAL_KEYS)
            for key, fields in ITEMS.items()]
