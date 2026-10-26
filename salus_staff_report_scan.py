"""Version-bound quarantine for staff Level 1A report material.

This module only stages originals. A trusted queue worker must authenticate a
Defender event and re-read the named version before making a report available.
"""

import hashlib
import re
import uuid

from salus_scan_quarantine import QuarantineError
from salus_scan_results import defender_result_for_pending, same_blob_etag


_ACCOUNT = re.compile(r'https://[a-z0-9]{3,24}\.blob\.core\.windows\.net\Z')
_SHA256 = re.compile(r'[0-9a-f]{64}\Z')
_PRODUCTS = {'SalINTEL', 'SalTHIRA', 'SalOPS', 'SalCAPA'}
_PURPOSES = {'draft': 10 * 1024 * 1024,
             'qa-archive': 50 * 1024 * 1024,
             'qa-pdf': 50 * 1024 * 1024}


STAFF_SCAN_SQL = '''
CREATE TABLE IF NOT EXISTS level1a_staff_pending_scans (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  tenant_id INTEGER NOT NULL,
  order_id INTEGER NOT NULL,
  assessment_id INTEGER NOT NULL,
  report_id INTEGER,
  product TEXT NOT NULL,
  purpose TEXT NOT NULL,
  group_sha256 TEXT NOT NULL DEFAULT '',
  source_record_sha256 TEXT NOT NULL,
  method_version TEXT NOT NULL DEFAULT '',
  template_version TEXT NOT NULL DEFAULT '',
  submitted_by_user_id INTEGER NOT NULL,
  original_name TEXT NOT NULL,
  blob_name TEXT NOT NULL,
  blob_uri TEXT NOT NULL,
  blob_version_id TEXT NOT NULL,
  etag TEXT NOT NULL,
  content_sha256 TEXT NOT NULL,
  size_bytes INTEGER NOT NULL,
  safe_stored_name TEXT NOT NULL DEFAULT '',
  finalized_record_id INTEGER,
  status TEXT NOT NULL DEFAULT 'Pending',
  scan_event_id TEXT NOT NULL DEFAULT '',
  scan_result TEXT NOT NULL DEFAULT '',
  scanned_at TEXT NOT NULL DEFAULT '',
  received_at TEXT NOT NULL,
  updated_at TEXT NOT NULL,
  UNIQUE(blob_uri,blob_version_id),
  FOREIGN KEY (order_id) REFERENCES level1a_orders(id) ON DELETE RESTRICT,
  FOREIGN KEY (assessment_id) REFERENCES assessments(id) ON DELETE RESTRICT,
  FOREIGN KEY (report_id) REFERENCES level1a_product_report_versions(id) ON DELETE RESTRICT
);
CREATE INDEX IF NOT EXISTS idx_level1a_staff_pending_age
  ON level1a_staff_pending_scans(status,received_at,id);
CREATE INDEX IF NOT EXISTS idx_level1a_staff_pending_scope
  ON level1a_staff_pending_scans(tenant_id,order_id,assessment_id,product,purpose,id);
CREATE INDEX IF NOT EXISTS idx_level1a_staff_pending_group
  ON level1a_staff_pending_scans(tenant_id,report_id,group_sha256,purpose,status);
'''


def _scope(tenant_id, order_id, assessment_id, product, purpose, report_id):
    if any(type(value) is not int or value < 1 for value in
           (tenant_id, order_id, assessment_id)):
        raise QuarantineError('Staff report scope is incomplete.')
    if product not in _PRODUCTS or purpose not in _PURPOSES:
        raise QuarantineError('Unknown staff report scan scope.')
    if purpose == 'draft':
        if report_id is not None:
            raise QuarantineError('A draft scan cannot name a saved report.')
        subject = 'working-draft'
    else:
        if type(report_id) is not int or report_id < 1:
            raise QuarantineError('QA material must name its exact report.')
        subject = f'report-{report_id}'
    return (f'tenant-{tenant_id}/assessment-{assessment_id}/order-{order_id}/'
            f'staff-report/{product}/{subject}/{purpose}/')


class AzureStaffReportQuarantine:
    """Private, purpose-separated Blob staging with exact-version readback."""

    def __init__(self, account_url, *, managed_identity_client_id='', service=None):
        account_url = account_url.rstrip('/')
        if not _ACCOUNT.fullmatch(account_url):
            raise QuarantineError('The scanner account URL is not governed.')
        if service is None:
            from azure.identity import ManagedIdentityCredential
            from azure.storage.blob import BlobServiceClient
            credential = ManagedIdentityCredential(
                client_id=managed_identity_client_id or None)
            service = BlobServiceClient(account_url=account_url,
                                        credential=credential)
        self.account_url = account_url
        self.container = service.get_container_client('quarantine')

    def stage_bytes(self, *, tenant_id, order_id, assessment_id, product,
                    purpose, report_id=None, data):
        prefix = _scope(tenant_id, order_id, assessment_id, product,
                        purpose, report_id)
        if (not isinstance(data, bytes) or not data or
                len(data) > _PURPOSES[purpose]):
            raise QuarantineError('Staff report original exceeds its scan limit.')
        digest = hashlib.sha256(data).hexdigest()
        name = f'{prefix}{uuid.uuid4().hex}_{digest[:16]}'
        result = self.container.get_blob_client(name).upload_blob(
            data, overwrite=False)
        version, etag = result.get('version_id'), result.get('etag')
        if not isinstance(version, str) or not version or not isinstance(etag, str) or not etag:
            raise QuarantineError('Quarantine did not return a version and ETag.')
        return {'tenant_id': tenant_id, 'order_id': order_id,
                'assessment_id': assessment_id, 'product': product,
                'purpose': purpose, 'report_id': report_id,
                'status': 'Pending', 'blob_name': name,
                'blob_uri': f'{self.account_url}/quarantine/{name}',
                'blob_version_id': version, 'etag': etag,
                'sha256': digest, 'size_bytes': len(data)}

    def read_version(self, manifest):
        """Worker-only read of the exact recorded original, never latest Blob."""
        if not isinstance(manifest, dict):
            raise QuarantineError('Missing staff scan manifest.')
        prefix = _scope(*(manifest.get(key) for key in
                          ('tenant_id', 'order_id', 'assessment_id', 'product',
                           'purpose', 'report_id')))
        name = manifest.get('blob_name')
        digest = manifest.get('sha256')
        size = manifest.get('size_bytes')
        version = manifest.get('blob_version_id')
        suffix = name[len(prefix):] if isinstance(name, str) and name.startswith(prefix) else ''
        if (manifest.get('status') != 'Pending' or
                not re.fullmatch(r'[0-9a-f]{32}_[0-9a-f]{16}', suffix) or
                not isinstance(digest, str) or not _SHA256.fullmatch(digest) or
                not name.endswith('_' + digest[:16]) or
                manifest.get('blob_uri') != f'{self.account_url}/quarantine/{name}' or
                not isinstance(version, str) or not version or
                type(size) is not int or not 1 <= size <= _PURPOSES[manifest['purpose']]):
            raise QuarantineError('Staff scan manifest failed scope validation.')
        blob = self.container.get_blob_client(name, version_id=version)
        props = blob.get_blob_properties()
        if props.version_id != version or props.etag != manifest.get('etag'):
            raise QuarantineError('Quarantined staff version or ETag changed.')
        data = blob.download_blob(offset=0, length=size + 1).readall()
        if len(data) != size or hashlib.sha256(data).hexdigest() != digest:
            raise QuarantineError('Quarantined staff bytes failed integrity validation.')
        return {'blob_uri': manifest['blob_uri'], 'blob_version_id': version,
                'etag': props.etag, 'bytes': data}


def qualified_staff_scan_result(event, manifest, snapshot, *, topic):
    """Accept Clean only after an authenticated exact-version byte read.

    Non-clean events never grant access. Their result can be recorded as held
    only when the event identifies the same Blob URI and ETag.
    """
    if (not isinstance(event, dict) or not isinstance(event.get('data'), dict)
            or not isinstance(manifest, dict) or manifest.get('status') != 'Pending'
            or not isinstance(topic, str) or not topic):
        return 'Unmatched'
    uri, etag = manifest.get('blob_uri'), manifest.get('etag')
    digest = manifest.get('sha256')
    if (not isinstance(uri, str) or not uri or not isinstance(etag, str)
            or not etag or not isinstance(digest, str)
            or not _SHA256.fullmatch(digest)
            or event.get('eventType') != 'Microsoft.Security.MalwareScanningResult'
            or event.get('topic') != topic
            or event['data'].get('blobUri') != uri
            or not same_blob_etag(etag, event['data'].get('eTag'))):
        return 'Unmatched'
    result = defender_result_for_pending(event, topic=topic,
        blob_uri=uri, etag=etag, sha256=digest)
    if result != 'Clean':
        return result
    data = snapshot.get('bytes') if isinstance(snapshot, dict) else None
    if (not isinstance(data, bytes)
            or snapshot.get('blob_uri') != uri
            or snapshot.get('blob_version_id') != manifest.get('blob_version_id')
            or not same_blob_etag(etag, snapshot.get('etag'))
            or type(manifest.get('size_bytes')) is not int
            or len(data) != manifest['size_bytes']
            or hashlib.sha256(data).hexdigest() != digest):
        return 'Unmatched'
    return 'Clean'
