"""Dependency-free checks for requested package-path validation."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from salus_package_path import draft_level_1_scope_receipt, requested_package_label, suggest_provisional_level_1_path

assert requested_package_label(0, '') == 'Unscoped'
assert requested_package_label(1, 'A', 'Access') == 'Level 1A Access'
assert requested_package_label(1, 'A', 'Standard') == 'Level 1A Standard'
assert requested_package_label(2, 'B') == 'Level 2B'
assert requested_package_label(3, 'C') == 'Level 3C'
for invalid in ((2, 'A', 'Access'), (1, 'B', 'Standard'), (0, 'A', ''), (1, '', ''), (4, 'C', '')):
    try:
        requested_package_label(*invalid)
    except ValueError:
        pass
    else:
        raise AssertionError(f'Accepted invalid package path: {invalid}')
assert suggest_provisional_level_1_path({'decision_units':'One','separate_findings':'No','group_priorities':'No'})['band'] == 'A'
assert suggest_provisional_level_1_path({'decision_units':'One','separate_findings':'Yes','group_priorities':'No'})['band'] == 'B'
assert suggest_provisional_level_1_path({'decision_units':'Two','separate_findings':'No','group_priorities':'Yes'})['band'] == 'C'
assert suggest_provisional_level_1_path({'decision_units':'Not sure','separate_findings':'Not sure','group_priorities':'Not sure'})['band'] == ''
assert 'revenue' not in str(suggest_provisional_level_1_path({'decision_units':'One','separate_findings':'No','group_priorities':'No','annual_revenue_range':'Over $500 million'})).lower()
access_path = suggest_provisional_level_1_path({'decision_units':'One','separate_findings':'No','group_priorities':'No'})
receipt = draft_level_1_scope_receipt({'covered_operation':'One fictional child-care site','decision_authority':'Director'}, access_path)
assert receipt['requested_boundary'] == 'One fictional child-care site'
assert '$1,500' in receipt['price_state'] and 'not priced add-ons' in receipt['price_state']
assert 'organization chart' in receipt['member_prepares'][0]
assert len(receipt['milestones']) == 5
assert [item['choice'] for item in receipt['choices']] == [
    'Correct the scope', 'Discuss later work', 'Discuss a separate service', 'Decline for now',
]
assert 'starting point' in receipt['lead_sentence']
print('Requested package path checks passed')
