"""Paid Level 1A assessment and selective records request identity.

This module never grants file disclosure from a purchase alone.  The buyer
must separately attest authority to send records before the scan gate opens.
"""

from salus_package_intake import CATALOG_VERSION, INITIAL_KEYS, ITEMS


INTAKE_SQL = '''
CREATE TABLE IF NOT EXISTS level1a_assessment_links (
  tenant_id INTEGER NOT NULL,
  buyer_user_id INTEGER NOT NULL,
  order_id INTEGER NOT NULL PRIMARY KEY,
  assessment_id INTEGER NOT NULL UNIQUE,
  acceptance_id INTEGER NOT NULL,
  scope_sha256 TEXT NOT NULL,
  agreement_sha256 TEXT NOT NULL,
  receipt_sha256 TEXT NOT NULL,
  created_at TEXT NOT NULL,
  FOREIGN KEY (order_id) REFERENCES level1a_orders(id) ON DELETE RESTRICT,
  FOREIGN KEY (assessment_id) REFERENCES assessments(id) ON DELETE RESTRICT
);
CREATE TABLE IF NOT EXISTS level1a_intake_items (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  tenant_id INTEGER NOT NULL,
  order_id INTEGER NOT NULL,
  assessment_id INTEGER NOT NULL,
  item_key TEXT NOT NULL,
  catalog_version TEXT NOT NULL,
  title TEXT NOT NULL,
  decision_use TEXT NOT NULL,
  requested_form TEXT NOT NULL,
  acceptable_equivalent TEXT NOT NULL,
  status TEXT NOT NULL DEFAULT 'Requested',
  requested_at TEXT NOT NULL,
  UNIQUE(tenant_id,order_id,item_key),
  FOREIGN KEY (order_id) REFERENCES level1a_orders(id) ON DELETE RESTRICT,
  FOREIGN KEY (assessment_id) REFERENCES assessments(id) ON DELETE RESTRICT
);
CREATE TABLE IF NOT EXISTS level1a_disclosure_authority (
  tenant_id INTEGER NOT NULL,
  order_id INTEGER NOT NULL PRIMARY KEY,
  buyer_user_id INTEGER NOT NULL,
  scope_sha256 TEXT NOT NULL,
  statement_version TEXT NOT NULL,
  authority_basis TEXT NOT NULL,
  affirmed_at TEXT NOT NULL,
  FOREIGN KEY (order_id) REFERENCES level1a_orders(id) ON DELETE RESTRICT
);
CREATE TABLE IF NOT EXISTS level1a_intake_uploads (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  tenant_id INTEGER NOT NULL,
  buyer_user_id INTEGER NOT NULL,
  order_id INTEGER NOT NULL,
  assessment_id INTEGER NOT NULL,
  quote_id INTEGER NOT NULL,
  intake_request_id INTEGER NOT NULL,
  original_name TEXT NOT NULL,
  stored_name TEXT NOT NULL UNIQUE,
  content_sha256 TEXT NOT NULL,
  size_bytes INTEGER NOT NULL,
  scan_status TEXT NOT NULL,
  uploaded_at TEXT NOT NULL,
  UNIQUE(tenant_id,intake_request_id,content_sha256),
  FOREIGN KEY (order_id) REFERENCES level1a_orders(id) ON DELETE RESTRICT,
  FOREIGN KEY (assessment_id) REFERENCES assessments(id) ON DELETE RESTRICT,
  FOREIGN KEY (quote_id) REFERENCES level1a_quote_versions(id) ON DELETE RESTRICT,
  FOREIGN KEY (intake_request_id) REFERENCES level1a_intake_items(id) ON DELETE RESTRICT
);
CREATE TABLE IF NOT EXISTS level1a_pending_scans (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  tenant_id INTEGER NOT NULL,
  buyer_user_id INTEGER NOT NULL,
  order_id INTEGER NOT NULL,
  assessment_id INTEGER NOT NULL,
  quote_id INTEGER NOT NULL,
  intake_request_id INTEGER NOT NULL,
  original_name TEXT NOT NULL,
  blob_name TEXT NOT NULL,
  blob_uri TEXT NOT NULL,
  blob_version_id TEXT NOT NULL,
  etag TEXT NOT NULL,
  content_sha256 TEXT NOT NULL,
  size_bytes INTEGER NOT NULL,
  status TEXT NOT NULL DEFAULT 'Pending',
  scan_event_id TEXT NOT NULL DEFAULT '',
  scan_result TEXT NOT NULL DEFAULT '',
  scanned_at TEXT NOT NULL DEFAULT '',
  promoted_upload_id INTEGER,
  received_at TEXT NOT NULL,
  updated_at TEXT NOT NULL,
  UNIQUE(tenant_id,intake_request_id,content_sha256),
  UNIQUE(blob_uri,blob_version_id),
  FOREIGN KEY (order_id) REFERENCES level1a_orders(id) ON DELETE RESTRICT,
  FOREIGN KEY (assessment_id) REFERENCES assessments(id) ON DELETE RESTRICT,
  FOREIGN KEY (quote_id) REFERENCES level1a_quote_versions(id) ON DELETE RESTRICT,
  FOREIGN KEY (intake_request_id) REFERENCES level1a_intake_items(id) ON DELETE RESTRICT,
  FOREIGN KEY (promoted_upload_id) REFERENCES level1a_intake_uploads(id) ON DELETE RESTRICT
);
CREATE INDEX IF NOT EXISTS idx_level1a_pending_age
  ON level1a_pending_scans(status,received_at,id);
CREATE INDEX IF NOT EXISTS idx_level1a_upload_scope
  ON level1a_intake_uploads(tenant_id,order_id,intake_request_id);
'''

DISCLOSURE_STATEMENT_VERSION = 'L1A-RECORD-DISCLOSURE-1'


class IntakeConflict(ValueError):
    pass


def ensure_paid_assessment(conn, *, binding, paid, order, timestamp):
    """Create exactly one scoped assessment for one verified paid order."""
    if (not paid or paid['status'] != 'Paid' or
            not paid['receipt_document_sha256'] or
            paid['tenant_id'] != binding.tenant_id or
            paid['buyer_user_id'] != binding.buyer_user_id or
            paid['order_id'] != binding.order_id or
            paid['acceptance_id'] != binding.acceptance_id or
            paid['scope_sha256'] != binding.scope_sha256 or
            paid['agreement_sha256'] != binding.agreement_sha256 or
            order['id'] != binding.order_id or
            order['tenant_id'] != binding.tenant_id or
            order['buyer_user_id'] != binding.buyer_user_id or
            order['scope_sha256'] != binding.scope_sha256):
        raise IntakeConflict('The paid order identity is incomplete or changed.')
    previous = conn.execute('SELECT * FROM level1a_assessment_links WHERE order_id=?',
                            (binding.order_id,)).fetchone()
    if previous:
        if any(previous[key] != value for key, value in (
                ('tenant_id', binding.tenant_id),
                ('buyer_user_id', binding.buyer_user_id),
                ('acceptance_id', binding.acceptance_id),
                ('scope_sha256', binding.scope_sha256),
                ('agreement_sha256', binding.agreement_sha256),
                ('receipt_sha256', paid['receipt_document_sha256']))):
            raise IntakeConflict('The existing assessment belongs to different terms.')
        return dict(previous), True
    scope = f"{order['unit_kind']}: {order['unit_name']}. {order['covered_boundary']}"
    result = conn.execute('''INSERT INTO assessments
        (tenant_id,name,organization,assessment_type,purpose,scope,covered_operation,
         requested_package_level,requested_scope_band,requested_access_variant,
         exclusions,status,executive_sponsor,scope_locked,version,created_at,updated_at)
        VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)''',
        (binding.tenant_id, order['unit_name'], order['buyer_legal_name'],
         order['unit_kind'], 'Level 1A Assessment', scope,
         order['operating_activity'], 1, 'A', 'Access', order['exclusions'],
         'Draft', order['decision_owner_role'], 1, 1, timestamp, timestamp))
    assessment_id = result.lastrowid
    conn.execute('''INSERT INTO level1a_assessment_links
        (tenant_id,buyer_user_id,order_id,assessment_id,acceptance_id,
         scope_sha256,agreement_sha256,receipt_sha256,created_at)
        VALUES(?,?,?,?,?,?,?,?,?)''',
        (binding.tenant_id,binding.buyer_user_id,binding.order_id,assessment_id,
         binding.acceptance_id,binding.scope_sha256,binding.agreement_sha256,
         paid['receipt_document_sha256'],timestamp))
    conn.execute('''INSERT INTO assessment_access(user_id,assessment_id,created_at)
        VALUES(?,?,?)''',(binding.buyer_user_id,assessment_id,timestamp))
    for key in INITIAL_KEYS:
        title, decision_use, requested_form, equivalent = ITEMS[key]
        conn.execute('''INSERT INTO level1a_intake_items
            (tenant_id,order_id,assessment_id,item_key,catalog_version,title,
             decision_use,requested_form,acceptable_equivalent,requested_at)
            VALUES(?,?,?,?,?,?,?,?,?,?)''',
            (binding.tenant_id,binding.order_id,assessment_id,key,CATALOG_VERSION,
             title,decision_use,requested_form,equivalent,timestamp))
    return dict(conn.execute('SELECT * FROM level1a_assessment_links WHERE order_id=?',
                             (binding.order_id,)).fetchone()), False


def record_disclosure_authority(conn, *, binding, authority_basis, timestamp):
    basis = ' '.join(authority_basis.split()) if isinstance(authority_basis,str) else ''
    if len(basis) < 12 or len(basis) > 1000:
        raise IntakeConflict('Describe your authority to share these records.')
    prior = conn.execute('SELECT * FROM level1a_disclosure_authority WHERE order_id=?',
                         (binding.order_id,)).fetchone()
    if prior:
        if (prior['tenant_id'] != binding.tenant_id or
                prior['buyer_user_id'] != binding.buyer_user_id or
                prior['scope_sha256'] != binding.scope_sha256 or
                prior['authority_basis'] != basis or
                prior['statement_version'] != DISCLOSURE_STATEMENT_VERSION):
            raise IntakeConflict('The existing record-sharing authority needs review.')
        return dict(prior), True
    conn.execute('''INSERT INTO level1a_disclosure_authority
        (tenant_id,order_id,buyer_user_id,scope_sha256,statement_version,
         authority_basis,affirmed_at) VALUES(?,?,?,?,?,?,?)''',
        (binding.tenant_id,binding.order_id,binding.buyer_user_id,
         binding.scope_sha256,DISCLOSURE_STATEMENT_VERSION,basis,timestamp))
    return dict(conn.execute('SELECT * FROM level1a_disclosure_authority WHERE order_id=?',
                             (binding.order_id,)).fetchone()), False
