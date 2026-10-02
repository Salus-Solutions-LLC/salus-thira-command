"""Isolated, version-bound staging for accepted small package uploads.

Only a governed queue processor may call ``read_version``. Neither this
module nor a Defender event grants Member access to a quarantined object.
"""

import hashlib
import re
import uuid


_ACCOUNT = re.compile(r'https://[a-z0-9]{3,24}\.blob\.core\.windows\.net\Z')
_SHA256 = re.compile(r'[0-9a-f]{64}\Z')
_MAX_SMALL_UPLOAD_BYTES = 25 * 1024 * 1024


class QuarantineError(RuntimeError):
    pass


class AzureScanQuarantine:
    """Use one private Azure account and a managed identity, never a key/SAS."""

    def __init__(self, account_url, *, managed_identity_client_id='', service=None):
        account_url = account_url.rstrip('/')
        if not _ACCOUNT.fullmatch(account_url):
            raise QuarantineError('The scanner account URL is not a governed Azure Blob endpoint.')
        if service is None:
            from azure.identity import ManagedIdentityCredential
            from azure.storage.blob import BlobServiceClient
            credential = ManagedIdentityCredential(client_id=managed_identity_client_id or None)
            service = BlobServiceClient(account_url=account_url, credential=credential)
        self.account_url = account_url
        self.container = service.get_container_client('quarantine')

    @staticmethod
    def _positive_ids(tenant_id, assessment_id, quote_id, intake_request_id):
        values = (tenant_id, assessment_id, quote_id, intake_request_id)
        if any(type(value) is not int or value < 1 for value in values):
            raise QuarantineError('The package scope is incomplete.')

    def stage_bytes(self, *, tenant_id, assessment_id, quote_id,
                    intake_request_id, data):
        self._positive_ids(tenant_id, assessment_id, quote_id, intake_request_id)
        if not isinstance(data, bytes) or not data or len(data) > _MAX_SMALL_UPLOAD_BYTES:
            raise QuarantineError('Quarantine requires original bytes within the small-upload limit.')
        digest = hashlib.sha256(data).hexdigest()
        name = (f'tenant-{tenant_id}/assessment-{assessment_id}/quote-{quote_id}/'
                f'item-{intake_request_id}/{uuid.uuid4().hex}_{digest[:16]}')
        blob = self.container.get_blob_client(name)
        result = blob.upload_blob(data, overwrite=False)
        version = result.get('version_id')
        etag = result.get('etag')
        if not isinstance(version, str) or not version or not isinstance(etag, str) or not etag:
            # The original remains isolated; without a version it cannot be qualified.
            raise QuarantineError('The quarantine account did not return a blob version and ETag.')
        return {
            'tenant_id': tenant_id, 'assessment_id': assessment_id,
            'quote_id': quote_id, 'intake_request_id': intake_request_id,
            'status': 'Pending', 'blob_name': name,
            'blob_uri': f'{self.account_url}/quarantine/{name}',
            'blob_version_id': version, 'etag': etag,
            'sha256': digest, 'size_bytes': len(data),
        }

    def read_version(self, manifest):
        """Return only the recorded version, bounded by its original size."""
        if not isinstance(manifest, dict):
            raise QuarantineError('Missing pending scan manifest.')
        ids = tuple(manifest.get(key) for key in
                    ('tenant_id', 'assessment_id', 'quote_id', 'intake_request_id'))
        self._positive_ids(*ids)
        name = manifest.get('blob_name')
        version = manifest.get('blob_version_id')
        digest = manifest.get('sha256')
        size = manifest.get('size_bytes')
        prefix = (f'tenant-{ids[0]}/assessment-{ids[1]}/quote-{ids[2]}/'
                  f'item-{ids[3]}/')
        if (manifest.get('status') != 'Pending'
                or not isinstance(name, str) or not name.startswith(prefix)
                or not re.fullmatch(r'[0-9a-f]{32}_[0-9a-f]{16}', name[len(prefix):])
                or manifest.get('blob_uri') != f'{self.account_url}/quarantine/{name}'
                or not isinstance(version, str) or not version
                or not isinstance(digest, str) or not _SHA256.fullmatch(digest)
                or type(size) is not int or size < 1 or size > _MAX_SMALL_UPLOAD_BYTES):
            raise QuarantineError('Pending scan manifest failed scope or size validation.')
        if not name.endswith('_' + digest[:16]):
            raise QuarantineError('Pending scan manifest digest does not match its blob name.')
        blob = self.container.get_blob_client(name, version_id=version)
        properties = blob.get_blob_properties()
        if properties.version_id != version or properties.etag != manifest.get('etag'):
            raise QuarantineError('Quarantined blob version or ETag changed.')
        data = blob.download_blob(offset=0, length=size + 1).readall()
        if len(data) != size or hashlib.sha256(data).hexdigest() != digest:
            raise QuarantineError('Quarantined original bytes failed integrity validation.')
        return {
            'blob_uri': manifest['blob_uri'], 'blob_version_id': version,
            'etag': properties.etag, 'bytes': data,
        }
