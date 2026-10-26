from copy import deepcopy
from contextlib import contextmanager
import sqlite3
from types import SimpleNamespace

from salus_staff_report_scan import (STAFF_SCAN_SQL, AzureStaffReportQuarantine,
                                     qualified_staff_scan_result)
from salus_scan_quarantine import QuarantineError


@contextmanager
def raises_quarantine():
    try:
        yield
    except QuarantineError:
        return
    raise AssertionError('Expected fail-closed quarantine rejection')


class FakeBlob:
    def __init__(self, name, version=None):
        self.name, self.version = name, version
        self.data, self.etag = b'', '0xA1'

    def upload_blob(self, data, *, overwrite):
        assert overwrite is False
        self.data = data
        return {'version_id': 'v1', 'etag': self.etag}

    def get_blob_properties(self):
        return SimpleNamespace(version_id=self.version, etag=self.etag)

    def download_blob(self, *, offset, length):
        assert offset == 0
        return SimpleNamespace(readall=lambda: self.data[:length])


class FakeContainer:
    def __init__(self):
        self.blobs = {}

    def get_blob_client(self, name, version_id=None):
        original = self.blobs.setdefault(name, FakeBlob(name))
        if version_id is None:
            return original
        result = FakeBlob(name, 'v1')
        result.data, result.etag = original.data, original.etag
        return result


class FakeService:
    def __init__(self):
        self.container = FakeContainer()

    def get_container_client(self, name):
        assert name == 'quarantine'
        return self.container


def test_staff_original_requires_exact_scope_version_and_bytes():
    service = FakeService()
    quarantine = AzureStaffReportQuarantine(
        'https://salusquarantine.blob.core.windows.net', service=service)
    pending = quarantine.stage_bytes(tenant_id=7, order_id=10,
        assessment_id=8, product='SalINTEL', purpose='draft', data=b'Word draft')
    assert quarantine.read_version(pending)['bytes'] == b'Word draft'
    assert '/staff-report/SalINTEL/working-draft/draft/' in pending['blob_uri']
    for field, changed_value in (
            ('tenant_id', 8), ('order_id', 11), ('assessment_id', 9),
            ('product', 'SalOPS'), ('purpose', 'qa-archive'),
            ('report_id', 3), ('blob_version_id', 'v2'),
            ('etag', '0xOLD'), ('sha256', 'a' * 64),
            ('size_bytes', 11), ('status', 'Clean')):
        changed = deepcopy(pending)
        changed[field] = changed_value
        with raises_quarantine():
            quarantine.read_version(changed)
    service.container.blobs[pending['blob_name']].data = b'other data'
    with raises_quarantine():
        quarantine.read_version(pending)


def test_archive_and_pdf_use_distinct_scoped_originals():
    quarantine = AzureStaffReportQuarantine(
        'https://salusquarantine.blob.core.windows.net', service=FakeService())
    common = {'tenant_id': 7, 'order_id': 10, 'assessment_id': 8,
              'product': 'SalCAPA', 'report_id': 12}
    archive = quarantine.stage_bytes(**common, purpose='qa-archive', data=b'ZIP')
    pdf = quarantine.stage_bytes(**common, purpose='qa-pdf', data=b'PDF')
    assert archive['blob_uri'] != pdf['blob_uri']
    assert quarantine.read_version(archive)['bytes'] == b'ZIP'
    assert quarantine.read_version(pdf)['bytes'] == b'PDF'
    with raises_quarantine():
        quarantine.stage_bytes(**common, purpose='draft', data=b'wrong')
    with raises_quarantine():
        quarantine.stage_bytes(tenant_id=7, order_id=10, assessment_id=8,
            product='SalCAPA', purpose='qa-pdf', data=b'no report')


def test_clean_result_needs_exact_named_version_and_bytes():
    quarantine = AzureStaffReportQuarantine(
        'https://salusquarantine.blob.core.windows.net', service=FakeService())
    pending = quarantine.stage_bytes(tenant_id=7, order_id=10,
        assessment_id=8, product='SalINTEL', purpose='draft', data=b'Word draft')
    snapshot = quarantine.read_version(pending)
    event = {'eventType': 'Microsoft.Security.MalwareScanningResult',
             'topic': '/subscriptions/test',
             'data': {'blobUri': pending['blob_uri'], 'eTag': pending['etag'],
                      'scanResultType': 'No threats found'}}
    assert qualified_staff_scan_result(event, pending, snapshot,
        topic='/subscriptions/test') == 'Clean'
    changed = deepcopy(snapshot)
    changed['blob_version_id'] = 'another-version'
    assert qualified_staff_scan_result(event, pending, changed,
        topic='/subscriptions/test') == 'Unmatched'
    changed = deepcopy(event)
    changed['data']['eTag'] = '0xBAD'
    assert qualified_staff_scan_result(changed, pending, snapshot,
        topic='/subscriptions/test') == 'Unmatched'
    changed = deepcopy(event)
    changed['data']['scanResultType'] = 'Malicious'
    assert qualified_staff_scan_result(changed, pending, None,
        topic='/subscriptions/test') == 'Malicious'


def test_staff_scan_ledger_has_distinct_archive_and_pdf_rows():
    conn = sqlite3.connect(':memory:')
    conn.executescript(STAFF_SCAN_SQL)
    fields = ('tenant_id', 'order_id', 'assessment_id', 'report_id', 'product',
              'purpose', 'group_sha256', 'source_record_sha256',
              'submitted_by_user_id', 'original_name', 'blob_name', 'blob_uri',
              'blob_version_id', 'etag', 'content_sha256', 'size_bytes',
              'received_at', 'updated_at')
    values = (7, 10, 8, 12, 'SalCAPA', 'qa-archive', 'a' * 64, 'b' * 64,
              3, 'qa.zip', 'name', 'https://example.test/one', 'v1', '0xA1',
              'c' * 64, 123, '2026-10-26T00:00:00Z', '2026-10-26T00:00:00Z')
    conn.execute(f"INSERT INTO level1a_staff_pending_scans ({','.join(fields)}) "
                 f"VALUES ({','.join('?' for _ in fields)})", values)
    conn.execute(f"INSERT INTO level1a_staff_pending_scans ({','.join(fields)}) "
                 f"VALUES ({','.join('?' for _ in fields)})",
                 values[:5] + ('qa-pdf',) + values[6:11]
                 + ('https://example.test/two',) + values[12:])
    assert conn.execute('SELECT COUNT(*) FROM level1a_staff_pending_scans').fetchone()[0] == 2
    conn.close()


if __name__ == '__main__':
    test_staff_original_requires_exact_scope_version_and_bytes()
    test_archive_and_pdf_use_distinct_scoped_originals()
    test_clean_result_needs_exact_named_version_and_bytes()
    test_staff_scan_ledger_has_distinct_archive_and_pdf_rows()
    print('staff_quarantine_tests=passed')
