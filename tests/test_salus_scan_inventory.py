from types import SimpleNamespace
import sqlite3

import pytest

from salus_scan_inventory import (InventoryError, compare_quarantine_versions,
                                  list_azure_quarantine_versions,
                                  record_inventory_exceptions)


def test_orphan_and_missing_versions_are_not_hidden_by_a_clean_copy():
    ledger = [
        {'blob_name': 'tenant-1/a', 'blob_version_id': 'v1', 'size_bytes': 10, 'legal_hold': 0},
        {'blob_name': 'tenant-1/b', 'blob_version_id': 'v2', 'size_bytes': 20, 'legal_hold': 1},
    ]
    listed = [
        {'name': 'tenant-1/a', 'version_id': 'v1', 'size_bytes': 10, 'legal_hold': False},
        {'name': 'tenant-1/orphan', 'version_id': 'v3', 'size_bytes': 7, 'legal_hold': False},
    ]
    result = compare_quarantine_versions(ledger, listed)
    assert result['unlinked_versions'] == [('tenant-1/orphan', 'v3')]
    assert result['missing_versions'] == [('tenant-1/b', 'v2')]
    assert result['azure_bytes'] == 17


def test_ledger_hold_needs_a_verified_azure_hold_and_size():
    ledger = [{'blob_name': 'tenant-1/a', 'blob_version_id': 'v1',
               'size_bytes': 10, 'legal_hold': 1}]
    listed = [{'name': 'tenant-1/a', 'version_id': 'v1',
               'size_bytes': 11, 'legal_hold': None}]
    result = compare_quarantine_versions(ledger, listed)
    assert result['hold_mismatches'] == [('tenant-1/a', 'v1')]
    assert result['size_mismatches'] == [('tenant-1/a', 'v1')]


def test_inventory_fails_closed_when_incomplete_or_duplicate():
    ledger = [{'blob_name': 'tenant-1/a', 'blob_version_id': 'v1',
               'size_bytes': 10, 'legal_hold': 0}]
    with pytest.raises(InventoryError):
        compare_quarantine_versions(ledger, [], max_versions=0)
    with pytest.raises(InventoryError):
        compare_quarantine_versions(
            ledger, [{'name': 'tenant-1/a', 'version_id': 'v1', 'size_bytes': 10,
                      'legal_hold': False}] * 2, max_versions=1)
    with pytest.raises(InventoryError):
        compare_quarantine_versions(ledger, [{'name': 'tenant-1/a',
                                               'version_id': '', 'size_bytes': 10}])


def test_azure_listing_includes_versions_and_hold_state():
    class Container:
        def list_blobs(self, *, include):
            assert include == ['versions', 'legalhold']
            return [SimpleNamespace(name='tenant-1/a', version_id='v1',
                                    size=10, has_legal_hold=True)]

    assert list(list_azure_quarantine_versions(Container())) == [
        {'name': 'tenant-1/a', 'version_id': 'v1', 'size_bytes': 10, 'legal_hold': True}]


def test_restricted_exceptions_are_idempotent_and_orphans_unassigned():
    conn = sqlite3.connect(':memory:')
    conn.execute('''CREATE TABLE package_quarantine_inventory_exceptions (
        id INTEGER PRIMARY KEY, exception_key TEXT UNIQUE, account_url TEXT,
        exception_type TEXT, blob_name TEXT, blob_version_id TEXT,
        candidate_tenant_id INTEGER, status TEXT, first_seen TEXT,
        last_seen TEXT, assigned_to TEXT DEFAULT '', disposition TEXT DEFAULT '')''')
    ledger = [{'tenant_id': 7, 'blob_name': 'tenant-7/a',
               'blob_version_id': 'v1', 'size_bytes': 10, 'legal_hold': 1}]
    listed = [{'name': 'tenant-7/a', 'version_id': 'v1',
               'size_bytes': 10, 'legal_hold': False},
              {'name': 'tenant-unknown/orphan', 'version_id': 'v2',
               'size_bytes': 4, 'legal_hold': False}]
    result = compare_quarantine_versions(ledger, listed)
    account = 'https://scanner.blob.core.windows.net'
    assert record_inventory_exceptions(conn, account, ledger, result,
                                       detected_at='2026-10-01T01:00:00Z') == 2
    conn.execute("UPDATE package_quarantine_inventory_exceptions SET status='Reviewed'")
    assert record_inventory_exceptions(conn, account, ledger, result,
                                       detected_at='2026-10-01T02:00:00Z') == 2
    rows = conn.execute('''SELECT exception_type,candidate_tenant_id,status,
        first_seen,last_seen FROM package_quarantine_inventory_exceptions
        ORDER BY exception_type''').fetchall()
    assert rows == [
        ('HoldMismatch', 7, 'Open', '2026-10-01T01:00:00Z', '2026-10-01T02:00:00Z'),
        ('Unlinked', None, 'Open', '2026-10-01T01:00:00Z', '2026-10-01T02:00:00Z'),
    ]
    conn.close()


def test_internal_inventory_records_orphan_without_member_attribution(tmp_path, monkeypatch):
    import app

    path = tmp_path / 'inventory.db'
    conn = sqlite3.connect(path)
    conn.execute('''CREATE TABLE package_intake_pending_scans (
        tenant_id INTEGER,blob_name TEXT,blob_version_id TEXT,
        size_bytes INTEGER,legal_hold INTEGER)''')
    conn.execute('''CREATE TABLE package_quarantine_inventory_exceptions (
        id INTEGER PRIMARY KEY, exception_key TEXT UNIQUE, account_url TEXT,
        exception_type TEXT, blob_name TEXT, blob_version_id TEXT,
        candidate_tenant_id INTEGER, status TEXT, first_seen TEXT,
        last_seen TEXT, assigned_to TEXT DEFAULT '', disposition TEXT DEFAULT '')''')
    conn.execute('''INSERT INTO package_intake_pending_scans VALUES(7,'tenant-7/a','v1',10,0)''')
    conn.commit()
    conn.close()

    def connection():
        opened = sqlite3.connect(path)
        opened.row_factory = sqlite3.Row
        return opened

    class Container:
        def list_blobs(self, *, include):
            assert include == ['versions', 'legalhold']
            return [SimpleNamespace(name='tenant-7/a', version_id='v1',
                                    size=10, has_legal_hold=False),
                    SimpleNamespace(name='unknown/orphan', version_id='v2',
                                    size=4, has_legal_hold=False)]

    reader = SimpleNamespace(account_url='https://scanner.blob.core.windows.net',
                             container=Container())
    monkeypatch.setattr(app, 'PACKAGE_SCAN_MODE', 'defender')
    monkeypatch.setattr(app, 'db', connection)
    result = app.inspect_package_quarantine_inventory(quarantine=reader)
    assert result == {'ledger_count': 1, 'azure_version_count': 2,
                      'azure_bytes': 14, 'exceptions_observed': 1}
    conn = connection()
    row = conn.execute('''SELECT exception_type,candidate_tenant_id,status
        FROM package_quarantine_inventory_exceptions''').fetchone()
    assert tuple(row) == ('Unlinked', None, 'Open')
    conn.close()
