from types import SimpleNamespace

import pytest

from salus_scan_inventory import (InventoryError, compare_quarantine_versions,
                                  list_azure_quarantine_versions)


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
