"""Internal scheduled quarantine inventory; never an HTTP or Member endpoint."""

import json


def run_inventory(*, inspect=None):
    if inspect is None:
        from app import inspect_package_quarantine_inventory
        inspect = inspect_package_quarantine_inventory
    summary = inspect()
    # Exact Blob names and versions stay in the restricted exception ledger.
    safe = {key: summary[key] for key in (
        'ledger_count', 'azure_version_count', 'azure_bytes', 'exceptions_observed')}
    print(json.dumps(safe, sort_keys=True))
    return safe


if __name__ == '__main__':
    result = run_inventory()
    if result['exceptions_observed']:
        raise SystemExit(2)
