"""Restricted, read-only reconciliation of quarantine originals and the ledger.

This does not delete an object or grant Member access. Callers must persist and
review every exception before any separate, authorized disposition action.
"""

from collections.abc import Iterable
import hashlib


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


_EXCEPTION_FIELDS = {
    'unlinked_versions': 'Unlinked',
    'missing_versions': 'Missing',
    'size_mismatches': 'SizeMismatch',
    'hold_mismatches': 'HoldMismatch',
}


def record_inventory_exceptions(conn, account_url: str, ledger_rows: Iterable[dict],
                                comparison: dict, *, detected_at: str) -> int:
    """Persist exact restricted exceptions without assigning an orphan to a Member.

    The caller owns the transaction. Repeated observations update last_seen and
    reopen a recurring exception; nothing is auto-disposed or client-visible.
    """
    if not isinstance(account_url, str) or not account_url.startswith('https://'):
        raise InventoryError('The inventory account is invalid.')
    if not isinstance(detected_at, str) or not detected_at:
        raise InventoryError('The inventory time is missing.')
    tenants = {}
    for row in ledger_rows:
        key = _key(row, azure=False)
        tenant = row.get('tenant_id')
        if type(tenant) is not int or tenant < 1:
            raise InventoryError('The ledger tenant scope is invalid.')
        tenants[key] = tenant
    recorded = 0
    for field, kind in _EXCEPTION_FIELDS.items():
        for name, version in comparison[field]:
            key = hashlib.sha256(
                f'{account_url}\x00{kind}\x00{name}\x00{version}'.encode('utf-8')).hexdigest()
            conn.execute('''INSERT INTO package_quarantine_inventory_exceptions
                (exception_key,account_url,exception_type,blob_name,blob_version_id,
                 candidate_tenant_id,status,first_seen,last_seen)
                VALUES(?,?,?,?,?,?,'Open',?,?)
                ON CONFLICT(exception_key) DO UPDATE SET
                  last_seen=excluded.last_seen,status='Open' ''',
                (key,account_url,kind,name,version,tenants.get((name,version)),
                 detected_at,detected_at))
            recorded += 1
    return recorded
