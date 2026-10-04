from copy import deepcopy

from salus_scan_results import (defender_event_matches_pending,
                                defender_result_for_pending,
                                qualified_clean_quarantine_object,
                                same_blob_etag)
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
    assert defender_event_matches_pending(event('Not scanned'),topic=TOPIC,
                                          blob_uri=URI,etag=ETAG,sha256=SHA)
    assert not defender_event_matches_pending(event(),topic=TOPIC,
                                              blob_uri=URI,etag='0xOLD',sha256=SHA)


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


def test_quoted_etag_and_missing_clean_digest_require_exact_versioned_bytes():
    assert same_blob_etag('"0xABC123"', ETAG)
    assert same_blob_etag(ETAG, '"0xABC123"')
    for observed in ('0xABC124', '"0xABC124"', '""0xABC123""',
                     'W/"0xABC123"', '0xABC123 ', None):
        assert not same_blob_etag(ETAG, observed)

    data = b'fictional clean document'
    digest = hashlib.sha256(data).hexdigest()
    manifest = {
        'tenant_id': 7, 'assessment_id': 8, 'intake_request_id': 9,
        'status': 'Pending', 'blob_uri': URI, 'blob_version_id': 'version-1',
        'etag': '"0xABC123"', 'sha256': digest, 'size_bytes': len(data),
    }
    snapshot = {'blob_uri': URI, 'blob_version_id': 'version-1',
                'etag': manifest['etag'], 'bytes': data}
    clean = event()
    clean['data']['eTag'] = ETAG
    clean['data']['scanResultDetails'].pop('sha256')
    assert defender_result_for_pending(clean, topic=TOPIC, blob_uri=URI,
                                       etag=manifest['etag'], sha256=digest) == 'Clean'
    def qualified(item=clean, recorded=manifest, actual=snapshot):
        return qualified_clean_quarantine_object(
            item, recorded, actual, topic=TOPIC, tenant_id=7,
            assessment_id=8, intake_request_id=9)

    assert qualified()
    assert not qualified(actual=dict(snapshot, blob_version_id='version-2'))
    assert not qualified(actual=dict(snapshot, bytes=b'changed bytes'))
    assert not qualified(actual=dict(snapshot, etag=ETAG))
    assert not qualified(recorded=dict(manifest, sha256='b' * 64))
    different = deepcopy(clean)
    different['data']['scanResultDetails']['sha256'] = 'b' * 64
    assert not qualified(item=different)
    malicious = deepcopy(clean)
    malicious['data']['scanResultType'] = 'Malicious'
    assert defender_result_for_pending(malicious, topic=TOPIC, blob_uri=URI,
                                       etag=manifest['etag'], sha256=digest) == 'Malicious'


def test_null_or_missing_details_remain_provisional_until_named_version_bytes_match():
    data = b'fictional clean document'
    digest = hashlib.sha256(data).hexdigest()
    manifest = {
        'tenant_id': 7, 'assessment_id': 8, 'intake_request_id': 9,
        'status': 'Pending', 'blob_uri': URI, 'blob_version_id': 'version-1',
        'etag': '"0xABC123"', 'sha256': digest, 'size_bytes': len(data),
    }
    snapshot = {'blob_uri': URI, 'blob_version_id': 'version-1',
                'etag': manifest['etag'], 'bytes': data}

    def qualified(item, recorded=manifest, actual=snapshot):
        return qualified_clean_quarantine_object(
            item, recorded, actual, topic=TOPIC, tenant_id=7,
            assessment_id=8, intake_request_id=9)

    for absent in (False, True):
        clean = event()
        clean['data']['eTag'] = ETAG
        if absent:
            clean['data'].pop('scanResultDetails')
        else:
            clean['data']['scanResultDetails'] = None
        assert defender_event_matches_pending(
            clean, topic=TOPIC, blob_uri=URI,
            etag=manifest['etag'], sha256=digest)
        assert defender_result_for_pending(clean, topic=TOPIC, blob_uri=URI,
                                          etag=manifest['etag'], sha256=digest) == 'Clean'
        assert qualified(clean)
        assert not qualified(clean, actual=dict(snapshot, blob_version_id='version-2'))
        assert not qualified(clean, actual=dict(snapshot, bytes=b'changed bytes'))
        assert not qualified(clean, actual=dict(snapshot, etag=ETAG))
        assert not qualified(clean, recorded=dict(manifest, sha256='b' * 64))
        for key, value in (('eventType', 'Microsoft.Storage.BlobCreated'),
                           ('topic', TOPIC + '-other')):
            wrong = deepcopy(clean)
            wrong[key] = value
            assert not qualified(wrong)
        for key, value in (('blobUri', URI + '-other'), ('eTag', '0xOLD')):
            wrong = deepcopy(clean)
            wrong['data'][key] = value
            assert not qualified(wrong)
        adverse = deepcopy(clean)
        adverse['data']['scanResultType'] = 'Malicious'
        assert defender_result_for_pending(
            adverse, topic=TOPIC, blob_uri=URI,
            etag=manifest['etag'], sha256=digest) == 'Malicious'
        assert not qualified(adverse)
        unknown = deepcopy(clean)
        unknown['data']['scanResultType'] = 'Not scanned'
        assert not qualified(unknown)

    malformed = event()
    malformed['data']['scanResultDetails'] = 'invalid'
    assert not qualified(malformed)
