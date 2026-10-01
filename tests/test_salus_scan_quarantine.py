from copy import deepcopy
from types import SimpleNamespace

from salus_scan_quarantine import AzureScanQuarantine, QuarantineError


class FakeBlob:
    def __init__(self, name, version_id=None):
        self.name = name
        self.version_id = version_id
        self.data = b''
        self.etag = '0xE1'
        self.upload_overwrite = None

    def upload_blob(self, data, *, overwrite):
        self.data = data
        self.upload_overwrite = overwrite
        return {'version_id': 'v1', 'etag': self.etag}

    def get_blob_properties(self):
        return SimpleNamespace(version_id=self.version_id, etag=self.etag)

    def download_blob(self, *, offset, length):
        assert offset == 0
        return SimpleNamespace(readall=lambda: self.data[:length])


class FakeContainer:
    def __init__(self):
        self.blobs = {}
        self.uploaded = None

    def get_blob_client(self, name, version_id=None):
        if version_id is None:
            self.uploaded = self.blobs.setdefault(name, FakeBlob(name))
            return self.uploaded
        original = self.blobs[name]
        blob = FakeBlob(name, 'v1')
        blob.data = original.data
        blob.etag = original.etag
        return blob


class FakeService:
    def __init__(self):
        self.container = FakeContainer()

    def get_container_client(self, name):
        assert name == 'quarantine'
        return self.container


def _raises(fn):
    try:
        fn()
    except QuarantineError:
        return
    assert False, 'Expected fail-closed quarantine rejection'


def test_stage_and_read_only_exact_versioned_original():
    service = FakeService()
    quarantine = AzureScanQuarantine('https://salusquarantine.blob.core.windows.net',
                                     service=service)
    data = b'fictional member upload'
    pending = quarantine.stage_bytes(tenant_id=7, assessment_id=8, quote_id=9,
                                     intake_request_id=10, data=data)
    assert service.container.uploaded.upload_overwrite is False
    assert pending['status'] == 'Pending'
    assert pending['blob_uri'].startswith(
        'https://salusquarantine.blob.core.windows.net/quarantine/tenant-7/')
    assert quarantine.read_version(pending)['bytes'] == data
    for field, value in (('tenant_id', 11), ('assessment_id', 11),
                         ('quote_id', 11), ('intake_request_id', 11),
                         ('blob_version_id', 'v2'), ('etag', '0xOLD'),
                         ('sha256', 'b' * 64), ('size_bytes', len(data) + 1),
                         ('status', 'Clean')):
        changed = deepcopy(pending)
        changed[field] = value
        _raises(lambda: quarantine.read_version(changed))
    service.container.blobs[pending['blob_name']].data = b'changed member upload'
    _raises(lambda: quarantine.read_version(pending))


def test_quarantine_rejects_bad_scope_and_account():
    service = FakeService()
    _raises(lambda: AzureScanQuarantine('http://salusquarantine.blob.core.windows.net',
                                        service=service))
    quarantine = AzureScanQuarantine('https://salusquarantine.blob.core.windows.net',
                                     service=service)
    _raises(lambda: quarantine.stage_bytes(tenant_id=0, assessment_id=8,
                                           quote_id=9, intake_request_id=10, data=b'x'))
    _raises(lambda: quarantine.stage_bytes(tenant_id=7, assessment_id=8,
                                           quote_id=9, intake_request_id=10, data=b''))
    _raises(lambda: quarantine.stage_bytes(tenant_id=7, assessment_id=8,
                                           quote_id=9, intake_request_id=10,
                                           data=b'x' * (25 * 1024 * 1024 + 1)))


def test_manifest_name_digest_is_bound_to_original():
    service = FakeService()
    quarantine = AzureScanQuarantine('https://salusquarantine.blob.core.windows.net',
                                     service=service)
    pending = quarantine.stage_bytes(tenant_id=7, assessment_id=8, quote_id=9,
                                     intake_request_id=10, data=b'fictional bytes')
    changed = deepcopy(pending)
    changed['sha256'] = 'a' * 64
    _raises(lambda: quarantine.read_version(changed))
