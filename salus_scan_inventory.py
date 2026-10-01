"""Restricted, read-only reconciliation of quarantine originals and the ledger.

This does not delete an object or grant Member access. Callers must persist and
review every exception before any separate, authorized disposition action.
"""

from collections.abc import Iterable


class InventoryError(RuntimeError):
    pass


def _key(row, *, azure):
    name = row.get('name' if azure else 'blob_name')
    version = row.get('version_id' if azure else 'blob_version_id')
    if not isinstance(name, str) or not name or not isinstance(version, str) or not version:
        raise InventoryError('Quarantine inventory has an unnamed or unversioned object.')
    return name, version


def compare_quarantine_versions(ledger_rows: Iterable[dict], azure_rows: Iterable[dict],
                                *, max_versions: int = 10000) -> dict:
    """Find orphan, missing, changed-size and unsupported-hold versions.

    Fail rather than return a partial inventory when the bounded pilot capacity
    is exceeded. The returned exact names are restricted operational records.
    """
    if type(max_versions) is not int or not 1 <= max_versions <= 100000:
        raise InventoryError('The inventory limit is invalid.')
    expected = {}
    for row in ledger_rows:
        key = _key(row, azure=False)
        if key in expected or len(expected) >= max_versions:
            raise InventoryError('The ledger inventory is duplicate or over limit.')
        if type(row.get('size_bytes')) is not int or row['size_bytes'] < 1:
            raise InventoryError('The ledger has an invalid original size.')
        expected[key] = row
    seen = set()
    orphans = []
    size_mismatches = []
    hold_mismatches = []
    total_bytes = 0
    for row in azure_rows:
        key = _key(row, azure=True)
        if key in seen or len(seen) >= max_versions:
            raise InventoryError('The Azure inventory is duplicate or over limit.')
        if type(row.get('size_bytes')) is not int or row['size_bytes'] < 0:
            raise InventoryError('The Azure inventory has an invalid original size.')
        seen.add(key)
        total_bytes += row['size_bytes']
        recorded = expected.get(key)
        if recorded is None:
            orphans.append(key)
            continue
        if row['size_bytes'] != recorded['size_bytes']:
            size_mismatches.append(key)
        if recorded.get('legal_hold') not in (0, 1, False, True):
            raise InventoryError('The ledger hold state is invalid.')
        ledger_hold = bool(recorded['legal_hold'])
        azure_hold = row.get('legal_hold')
        if azure_hold is None or bool(azure_hold) != ledger_hold:
            hold_mismatches.append(key)
    return {
        'ledger_count': len(expected),
        'azure_version_count': len(seen),
        'azure_bytes': total_bytes,
        'unlinked_versions': sorted(orphans),
        'missing_versions': sorted(expected.keys() - seen),
        'size_mismatches': sorted(size_mismatches),
        'hold_mismatches': sorted(hold_mismatches),
    }


def list_azure_quarantine_versions(container):
    """Read version and hold metadata through a separately authorized reader."""
    for blob in container.list_blobs(include=['versions', 'legalhold']):
        yield {
            'name': blob.name,
            'version_id': blob.version_id,
            'size_bytes': blob.size,
            'legal_hold': getattr(blob, 'has_legal_hold', None),
        }
