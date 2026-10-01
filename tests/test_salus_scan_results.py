from copy import deepcopy

from salus_scan_results import defender_result_for_pending, qualified_clean_quarantine_object
import hashlib


TOPIC = '/subscriptions/test/resourceGroups/test/providers/Microsoft.EventGrid/topics/salus-test'
URI = 'https://salustest.blob.core.windows.net/quarantine/tenant-1/object-1'
ETAG = '0xABC123'
SHA = 'a' * 64


def event(result='No threats found'):
    return {
        'eventType': 'Microsoft.Security.MalwareScanningResult',
        'topic': TOPIC,
        'data': {
            'blobUri': URI,
            'eTag': ETAG,
            'scanResultType': result,
            'scanResultDetails': {'sha256': SHA.upper(), 'malwareNamesFound': []},
        },
    }


def evaluate(item):
    return defender_result_for_pending(item, topic=TOPIC, blob_uri=URI,
                                       etag=ETAG, sha256=SHA)


def test_exact_clean_and_malicious_results():
    assert evaluate(event()) == 'Clean'
    assert evaluate(event('Malicious')) == 'Malicious'


def test_mismatched_or_unsupported_results_never_clear_file():
    for key, value in (
        ('eventType', 'Microsoft.Storage.BlobCreated'),
        ('topic', TOPIC + '-other'),
    ):
        item = event()
        item[key] = value
        assert evaluate(item) == 'Unscanned'
    for key, value in (
        ('blobUri', URI + '-other'),
        ('eTag', '0xOLD'),
        ('scanResultType', 'Not scanned'),
    ):
        item = event()
        item['data'][key] = value
        assert evaluate(item) == 'Unscanned'
    for value in ('b' * 64, 'not-a-hash'):
        item = event()
        item['data']['scanResultDetails']['sha256'] = value
        assert evaluate(item) == 'Unscanned'
    item = event()
    item['data']['scanResultDetails']['malwareNamesFound'] = ['EICAR']
    assert evaluate(item) == 'Unscanned'
    assert evaluate({'data': None}) == 'Unscanned'
    assert evaluate(deepcopy(event('Error'))) == 'Unscanned'


def test_pending_versioned_bytes_must_match_clean_event_and_tenant_scope():
    data = b'fictional clean document'
    digest = hashlib.sha256(data).hexdigest()
    manifest = {
        'tenant_id': 7, 'assessment_id': 8, 'intake_request_id': 9,
        'status': 'Pending', 'blob_uri': URI, 'blob_version_id': 'version-1',
        'etag': ETAG, 'sha256': digest, 'size_bytes': len(data),
    }
    snapshot = {'blob_uri': URI, 'blob_version_id': 'version-1',
                'etag': ETAG, 'bytes': data}
    clean = event()
    clean['data']['scanResultDetails']['sha256'] = digest.upper()

    def approved(candidate=clean, pending=manifest, blob=snapshot, tenant=7):
        return qualified_clean_quarantine_object(
            candidate, pending, blob, topic=TOPIC, tenant_id=tenant,
            assessment_id=8, intake_request_id=9)

    assert approved()
    assert not approved(tenant=10)
    for key, value in (('status', 'Clean'), ('blob_version_id', 'version-2'),
                       ('etag', '0xOLD'), ('size_bytes', len(data) + 1),
                       ('sha256', 'b' * 64)):
        changed = dict(manifest, **{key: value})
        assert not approved(pending=changed)
    for key, value in (('blob_uri', URI + '-other'),
                       ('blob_version_id', 'version-2'), ('etag', '0xOLD'),
                       ('bytes', b'changed bytes')):
        changed = dict(snapshot, **{key: value})
        assert not approved(blob=changed)
    assert not approved(candidate=event('Malicious'))
    assert not approved(candidate=event('Not scanned'))
    assert not approved(candidate={'data': None})
