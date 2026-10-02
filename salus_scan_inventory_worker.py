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


def main(*, inspect=None):
    try:
        result = run_inventory(inspect=inspect)
    except Exception as exc:
        # The exception message may contain a tenant path, Blob URL or token.
        # The scheduled job reports the failure class only; Azure marks it failed.
        print(json.dumps({'inventory': 'failed', 'error_type': type(exc).__name__},
                         sort_keys=True))
        return 1
    return 2 if result['exceptions_observed'] else 0


if __name__ == '__main__':
    raise SystemExit(main())
