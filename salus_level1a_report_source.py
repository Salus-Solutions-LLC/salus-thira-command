"""Immutable provenance between one paid Level 1A order and its assessment.

This is source identity only. It cannot qualify, issue, or deliver a report.
"""

from hashlib import sha256
import json


REPORT_SOURCE_SQL = '''
CREATE TABLE IF NOT EXISTS level1a_report_sources (
  order_id INTEGER PRIMARY KEY,
  tenant_id INTEGER NOT NULL,
  buyer_user_id INTEGER NOT NULL,
  assessment_id INTEGER NOT NULL UNIQUE,
  quote_id INTEGER NOT NULL,
  acceptance_id INTEGER NOT NULL,
  checkout_id INTEGER NOT NULL,
  scope_sha256 TEXT NOT NULL,
  quote_sha256 TEXT NOT NULL,
  agreement_sha256 TEXT NOT NULL,
  receipt_document_sha256 TEXT NOT NULL,
  assessment_scope_sha256 TEXT NOT NULL,
  record_sha256 TEXT NOT NULL,
  created_at TEXT NOT NULL,
  FOREIGN KEY (order_id) REFERENCES level1a_orders(id) ON DELETE RESTRICT,
  FOREIGN KEY (assessment_id) REFERENCES assessments(id) ON DELETE RESTRICT,
  FOREIGN KEY (quote_id) REFERENCES level1a_quote_versions(id) ON DELETE RESTRICT,
  FOREIGN KEY (acceptance_id) REFERENCES level1a_acceptances(id) ON DELETE RESTRICT,
  FOREIGN KEY (checkout_id) REFERENCES level1a_checkout_sessions(id) ON DELETE RESTRICT,
  FOREIGN KEY (buyer_user_id) REFERENCES users(id) ON DELETE RESTRICT
);
CREATE INDEX IF NOT EXISTS idx_level1a_report_source_scope
  ON level1a_report_sources(tenant_id,assessment_id,buyer_user_id);
CREATE TABLE IF NOT EXISTS level1a_product_report_versions (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  tenant_id INTEGER NOT NULL,
  buyer_user_id INTEGER NOT NULL,
  order_id INTEGER NOT NULL,
  assessment_id INTEGER NOT NULL,
  product TEXT NOT NULL,
  version_no INTEGER NOT NULL,
  source_record_sha256 TEXT NOT NULL,
  original_name TEXT NOT NULL,
  stored_name TEXT NOT NULL UNIQUE,
  content_sha256 TEXT NOT NULL,
  size_bytes INTEGER NOT NULL,
  method_version TEXT NOT NULL,
  template_version TEXT NOT NULL,
  status TEXT NOT NULL DEFAULT 'Draft',
  retention_until TEXT NOT NULL,
  legal_hold INTEGER NOT NULL DEFAULT 0,
  disposition_status TEXT NOT NULL DEFAULT 'Active',
  created_by_user_id INTEGER NOT NULL,
  created_at TEXT NOT NULL,
  supersedes_id INTEGER,
  FOREIGN KEY (order_id) REFERENCES level1a_report_sources(order_id) ON DELETE RESTRICT,
  FOREIGN KEY (assessment_id) REFERENCES assessments(id) ON DELETE RESTRICT,
  FOREIGN KEY (created_by_user_id) REFERENCES users(id) ON DELETE RESTRICT,
  FOREIGN KEY (supersedes_id) REFERENCES level1a_product_report_versions(id) ON DELETE RESTRICT,
  UNIQUE(tenant_id,order_id,product,version_no)
);
CREATE INDEX IF NOT EXISTS idx_level1a_report_versions_scope
  ON level1a_product_report_versions(tenant_id,assessment_id,product,id);
CREATE TABLE IF NOT EXISTS level1a_report_qa_evidence (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  tenant_id INTEGER NOT NULL,
  order_id INTEGER NOT NULL,
  assessment_id INTEGER NOT NULL,
  report_id INTEGER NOT NULL,
  content_sha256 TEXT NOT NULL,
  archive_sha256 TEXT NOT NULL,
  stored_name TEXT NOT NULL UNIQUE,
  manifest_json TEXT NOT NULL,
  manifest_sha256 TEXT NOT NULL,
  submitted_by_user_id INTEGER NOT NULL,
  submitted_at TEXT NOT NULL,
  retention_until TEXT NOT NULL,
  legal_hold INTEGER NOT NULL DEFAULT 0,
  FOREIGN KEY (report_id) REFERENCES level1a_product_report_versions(id) ON DELETE RESTRICT,
  FOREIGN KEY (submitted_by_user_id) REFERENCES users(id) ON DELETE RESTRICT,
  UNIQUE(tenant_id,report_id,archive_sha256)
);
CREATE TABLE IF NOT EXISTS level1a_report_qa_reviews (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  tenant_id INTEGER NOT NULL,
  order_id INTEGER NOT NULL,
  assessment_id INTEGER NOT NULL,
  report_id INTEGER NOT NULL,
  evidence_id INTEGER NOT NULL,
  content_sha256 TEXT NOT NULL,
  archive_sha256 TEXT NOT NULL,
  decision TEXT NOT NULL,
  checks_json TEXT NOT NULL,
  qualification_basis TEXT NOT NULL,
  review_note TEXT NOT NULL,
  record_sha256 TEXT NOT NULL,
  reviewer_user_id INTEGER NOT NULL,
  reviewer_at TEXT NOT NULL,
  FOREIGN KEY (report_id) REFERENCES level1a_product_report_versions(id) ON DELETE RESTRICT,
  FOREIGN KEY (evidence_id) REFERENCES level1a_report_qa_evidence(id) ON DELETE RESTRICT,
  FOREIGN KEY (reviewer_user_id) REFERENCES users(id) ON DELETE RESTRICT,
  UNIQUE(tenant_id,evidence_id,record_sha256)
);
CREATE TABLE IF NOT EXISTS level1a_report_conformance (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  tenant_id INTEGER NOT NULL,
  order_id INTEGER NOT NULL,
  assessment_id INTEGER NOT NULL,
  report_id INTEGER NOT NULL,
  content_sha256 TEXT NOT NULL,
  checks_json TEXT NOT NULL,
  summary TEXT NOT NULL,
  status TEXT NOT NULL,
  record_sha256 TEXT NOT NULL,
  recorded_by_user_id INTEGER NOT NULL,
  recorded_at TEXT NOT NULL,
  FOREIGN KEY (report_id) REFERENCES level1a_product_report_versions(id) ON DELETE RESTRICT,
  FOREIGN KEY (recorded_by_user_id) REFERENCES users(id) ON DELETE RESTRICT,
  UNIQUE(tenant_id,report_id,record_sha256)
);
CREATE TABLE IF NOT EXISTS level1a_report_reconciliations (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  tenant_id INTEGER NOT NULL,
  order_id INTEGER NOT NULL,
  assessment_id INTEGER NOT NULL,
  salcapa_report_id INTEGER NOT NULL,
  salcapa_sha256 TEXT NOT NULL,
  sources_json TEXT NOT NULL,
  summary TEXT NOT NULL,
  status TEXT NOT NULL,
  record_sha256 TEXT NOT NULL,
  recorded_by_user_id INTEGER NOT NULL,
  recorded_at TEXT NOT NULL,
  FOREIGN KEY (salcapa_report_id) REFERENCES level1a_product_report_versions(id) ON DELETE RESTRICT,
  FOREIGN KEY (recorded_by_user_id) REFERENCES users(id) ON DELETE RESTRICT,
  UNIQUE(tenant_id,order_id,record_sha256)
);
CREATE TABLE IF NOT EXISTS level1a_report_issue_packets (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  tenant_id INTEGER NOT NULL,
  order_id INTEGER NOT NULL,
  assessment_id INTEGER NOT NULL,
  source_record_sha256 TEXT NOT NULL,
  recipient_user_id INTEGER NOT NULL,
  reports_json TEXT NOT NULL,
  reconciliation_id INTEGER NOT NULL,
  issue_basis TEXT NOT NULL,
  record_sha256 TEXT NOT NULL,
  issued_by_user_id INTEGER NOT NULL,
  issued_at TEXT NOT NULL,
  supersedes_id INTEGER,
  FOREIGN KEY (order_id) REFERENCES level1a_report_sources(order_id) ON DELETE RESTRICT,
  FOREIGN KEY (recipient_user_id) REFERENCES users(id) ON DELETE RESTRICT,
  FOREIGN KEY (reconciliation_id) REFERENCES level1a_report_reconciliations(id) ON DELETE RESTRICT,
  FOREIGN KEY (issued_by_user_id) REFERENCES users(id) ON DELETE RESTRICT,
  FOREIGN KEY (supersedes_id) REFERENCES level1a_report_issue_packets(id) ON DELETE RESTRICT,
  UNIQUE(tenant_id,order_id,record_sha256)
);
CREATE TABLE IF NOT EXISTS level1a_report_downloads (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  tenant_id INTEGER NOT NULL,
  issue_id INTEGER NOT NULL,
  report_id INTEGER NOT NULL,
  product TEXT NOT NULL,
  recipient_user_id INTEGER NOT NULL,
  content_sha256 TEXT NOT NULL,
  downloaded_at TEXT NOT NULL,
  FOREIGN KEY (issue_id) REFERENCES level1a_report_issue_packets(id) ON DELETE RESTRICT,
  FOREIGN KEY (report_id) REFERENCES level1a_product_report_versions(id) ON DELETE RESTRICT,
  FOREIGN KEY (recipient_user_id) REFERENCES users(id) ON DELETE RESTRICT
);
CREATE TABLE IF NOT EXISTS level1a_report_issue_acknowledgments (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  tenant_id INTEGER NOT NULL,
  issue_id INTEGER NOT NULL UNIQUE,
  issue_sha256 TEXT NOT NULL,
  recipient_user_id INTEGER NOT NULL,
  acknowledgment_note TEXT NOT NULL,
  idempotency_key TEXT NOT NULL UNIQUE,
  record_sha256 TEXT NOT NULL,
  acknowledged_at TEXT NOT NULL,
  FOREIGN KEY (issue_id) REFERENCES level1a_report_issue_packets(id) ON DELETE RESTRICT,
  FOREIGN KEY (recipient_user_id) REFERENCES users(id) ON DELETE RESTRICT
);
'''

SOURCE_KEYS = (
    'order_id', 'tenant_id', 'buyer_user_id', 'assessment_id',
    'quote_id', 'acceptance_id', 'checkout_id', 'scope_sha256',
    'quote_sha256', 'agreement_sha256', 'receipt_document_sha256',
    'assessment_scope_sha256',
)


class ReportSourceConflict(ValueError):
    pass


def _digest(values):
    return sha256(json.dumps({key: values[key] for key in SOURCE_KEYS},
                             sort_keys=True, separators=(',', ':')).encode()).hexdigest()


def ensure_report_source(conn, *, binding, paid, link, assessment_scope_sha256,
                         timestamp):
    """Record only verified, same-buyer paid facts in the intake transaction."""
    if (not paid or paid['status'] != 'Paid' or not paid['receipt_document_sha256']
            or not isinstance(assessment_scope_sha256, str)
            or len(assessment_scope_sha256) != 64):
        raise ReportSourceConflict('The paid report source is incomplete.')
    values = dict(order_id=binding.order_id, tenant_id=binding.tenant_id,
                  buyer_user_id=binding.buyer_user_id,
                  assessment_id=link['assessment_id'], quote_id=binding.quote_id,
                  acceptance_id=binding.acceptance_id, checkout_id=paid['id'],
                  scope_sha256=binding.scope_sha256,
                  quote_sha256=binding.quote_sha256,
                  agreement_sha256=binding.agreement_sha256,
                  receipt_document_sha256=paid['receipt_document_sha256'],
                  assessment_scope_sha256=assessment_scope_sha256)
    expected = {
        'tenant_id': binding.tenant_id,
        'buyer_user_id': binding.buyer_user_id,
        'order_id': binding.order_id,
        'quote_id': binding.quote_id,
        'acceptance_id': binding.acceptance_id,
        'scope_sha256': binding.scope_sha256,
        'quote_sha256': binding.quote_sha256,
        'agreement_sha256': binding.agreement_sha256,
    }
    if (any(paid[key] != value for key, value in expected.items())
            or any(link[key] != value for key, value in (
                ('tenant_id', binding.tenant_id),
                ('buyer_user_id', binding.buyer_user_id),
                ('order_id', binding.order_id),
                ('acceptance_id', binding.acceptance_id),
                ('scope_sha256', binding.scope_sha256),
                ('agreement_sha256', binding.agreement_sha256),
                ('receipt_sha256', paid['receipt_document_sha256'])))):
        raise ReportSourceConflict('The paid report source identities disagree.')
    digest = _digest(values)
    previous = conn.execute('SELECT * FROM level1a_report_sources WHERE order_id=?',
                            (binding.order_id,)).fetchone()
    if previous:
        if (any(previous[key] != value for key, value in values.items())
                or previous['record_sha256'] != digest):
            raise ReportSourceConflict('The existing report source changed.')
        return dict(previous), True
    columns = (*SOURCE_KEYS, 'record_sha256', 'created_at')
    conn.execute(f'INSERT INTO level1a_report_sources ({",".join(columns)}) '
                 f'VALUES ({",".join("?" for _ in columns)})',
                 (*values.values(), digest, timestamp))
    return dict(conn.execute('SELECT * FROM level1a_report_sources WHERE order_id=?',
                             (binding.order_id,)).fetchone()), False


def verified_report_source(conn, *, binding, paid, link,
                           assessment_scope_sha256):
    """Require the saved source to match the current verified paid facts."""
    row = conn.execute('''SELECT * FROM level1a_report_sources WHERE
        tenant_id=? AND buyer_user_id=? AND order_id=? AND assessment_id=?''',
        (binding.tenant_id, binding.buyer_user_id, binding.order_id,
         link['assessment_id'])).fetchone()
    if not row or paid['status'] != 'Paid':
        raise ReportSourceConflict('The paid report source is unavailable.')
    expected = dict(order_id=binding.order_id, tenant_id=binding.tenant_id,
                    buyer_user_id=binding.buyer_user_id,
                    assessment_id=link['assessment_id'],
                    quote_id=binding.quote_id,
                    acceptance_id=binding.acceptance_id,
                    checkout_id=paid['id'],
                    scope_sha256=binding.scope_sha256,
                    quote_sha256=binding.quote_sha256,
                    agreement_sha256=binding.agreement_sha256,
                    receipt_document_sha256=paid['receipt_document_sha256'],
                    assessment_scope_sha256=assessment_scope_sha256)
    if (any(row[key] != value for key, value in expected.items())
            or any(link[key] != value for key, value in (
                ('tenant_id', binding.tenant_id),
                ('buyer_user_id', binding.buyer_user_id),
                ('order_id', binding.order_id),
                ('acceptance_id', binding.acceptance_id),
                ('scope_sha256', binding.scope_sha256),
                ('agreement_sha256', binding.agreement_sha256),
                ('receipt_sha256', paid['receipt_document_sha256'])))
            or row['record_sha256'] != _digest(row)):
        raise ReportSourceConflict('The paid report source changed.')
    return dict(row)
