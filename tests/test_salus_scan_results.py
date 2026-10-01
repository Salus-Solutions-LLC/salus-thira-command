from copy import deepcopy

from salus_scan_results import defender_result_for_pending


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
