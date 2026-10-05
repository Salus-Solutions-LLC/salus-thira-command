"""Bind generated Level 1A Word bytes to an unchanged buyer order and quote.

Only the first registered bytes for a quote/template pair are retained. A
candidate record is not an issued agreement or an electronic acceptance.
"""

from hashlib import sha256
from io import BytesIO

from docx import Document
from salus_level1a_quote import QuoteFacts


AGREEMENT_TABLE_SQL = '''
CREATE TABLE IF NOT EXISTS level1a_agreement_versions (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  tenant_id INTEGER NOT NULL,
  buyer_user_id INTEGER NOT NULL,
  order_id INTEGER NOT NULL,
  quote_id INTEGER NOT NULL,
  scope_version INTEGER NOT NULL,
  scope_sha256 TEXT NOT NULL,
  quote_sha256 TEXT NOT NULL,
  template_version TEXT NOT NULL,
  template_sha256 TEXT NOT NULL,
  content_sha256 TEXT NOT NULL,
  stored_name TEXT NOT NULL,
  origin TEXT NOT NULL,
  status TEXT NOT NULL,
  created_at TEXT NOT NULL,
  issued_at TEXT NOT NULL DEFAULT '',
  FOREIGN KEY (tenant_id) REFERENCES tenants(id) ON DELETE CASCADE,
  FOREIGN KEY (buyer_user_id) REFERENCES users(id) ON DELETE RESTRICT,
  FOREIGN KEY (order_id) REFERENCES level1a_orders(id) ON DELETE RESTRICT,
  FOREIGN KEY (quote_id) REFERENCES level1a_quote_versions(id) ON DELETE RESTRICT,
  UNIQUE (tenant_id,order_id,quote_id,template_sha256)
);
CREATE INDEX IF NOT EXISTS idx_level1a_agreement_buyer
  ON level1a_agreement_versions(tenant_id,buyer_user_id,order_id,id);
CREATE TABLE IF NOT EXISTS level1a_agreement_downloads (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  tenant_id INTEGER NOT NULL,
  buyer_user_id INTEGER NOT NULL,
  order_id INTEGER NOT NULL,
  agreement_id INTEGER NOT NULL,
  content_sha256 TEXT NOT NULL,
  downloaded_at TEXT NOT NULL,
  FOREIGN KEY (agreement_id) REFERENCES level1a_agreement_versions(id) ON DELETE RESTRICT
);
CREATE INDEX IF NOT EXISTS idx_level1a_agreement_download_buyer
  ON level1a_agreement_downloads(tenant_id,buyer_user_id,order_id,agreement_id);
'''


class AgreementConflict(ValueError):
    pass


# Exact five-page Word issue template approved by Marc on 5 October 2026.
# A separately governed release must place these bytes in controlled storage.
APPROVED_TEMPLATE_SHA256 = '63ad42dadc81a054fa28ef55eaadc8dfbd10c9ca983ab81c2d085e033f046cf6'
APPROVED_TEMPLATE_VERSION = 'Level1A-Rev10-20261005'
APPROVED_TEMPLATE_KEY = f'level1a/templates/{APPROVED_TEMPLATE_SHA256}.docx'


def issue_generated_agreement(conn, *, tenant_id, buyer_user_id, order_id,
                              quote_id, agreement_id, approved_template_sha256,
                              readback, timestamp):
    """Issue only a complete Salus-generated version from an approved template.

    The approved hash must come from a protected release manifest, never from
    a buyer request. The caller owns the transaction and storage readback.
    """
    if approved_template_sha256 != APPROVED_TEMPLATE_SHA256:
        raise AgreementConflict('No exact approved agreement template is configured.')
    row=conn.execute('''SELECT * FROM level1a_agreement_versions WHERE id=?
        AND tenant_id=? AND buyer_user_id=? AND order_id=? AND quote_id=?''',
        (agreement_id,tenant_id,buyer_user_id,order_id,quote_id)).fetchone()
    order=conn.execute('''SELECT * FROM level1a_orders WHERE id=? AND tenant_id=?
        AND buyer_user_id=?''',(order_id,tenant_id,buyer_user_id)).fetchone()
    quote=conn.execute('''SELECT * FROM level1a_quote_versions WHERE id=? AND tenant_id=?
        AND buyer_user_id=? AND order_id=?''',
        (quote_id,tenant_id,buyer_user_id,order_id)).fetchone()
    if (not row or not order or not quote or row['status']!='Candidate' or
            row['origin']!='SalusGenerated' or order['status']!='ReadyForAgreement' or
            row['scope_version']!=order['scope_version'] or
            row['scope_sha256']!=order['scope_sha256'] or
            row['scope_sha256']!=quote['scope_sha256'] or
            row['quote_sha256']!=quote['quote_sha256'] or
            row['template_version']!=APPROVED_TEMPLATE_VERSION or
            row['template_sha256']!=approved_template_sha256):
        raise AgreementConflict('The candidate is not the current approved order version.')
    facts=QuoteFacts(**{key: quote[key] for key in QuoteFacts.__dataclass_fields__})
    if (facts.sha256()!=quote['quote_sha256'] or
            facts.base_price_cents!=150_000 or facts.tax_cents<0 or
            facts.total_cents!=facts.base_price_cents+facts.tax_cents or
            facts.currency!='USD'):
        raise AgreementConflict('The candidate price no longer matches its approved facts.')
    if (not isinstance(readback,bytes) or len(readback)>2_000_000 or
            sha256(readback).hexdigest()!=row['content_sha256']):
        raise AgreementConflict('The stored agreement bytes differ from the candidate.')
    try:
        doc=Document(BytesIO(readback))
        text='\n'.join(p.text for p in doc.paragraphs)
        headers='\n'.join(p.text for section in doc.sections
                          for p in section.header.paragraphs)
        footers='\n'.join(p.text for section in doc.sections
                          for p in section.footer.paragraphs)
    except Exception as exc:
        raise AgreementConflict('The stored agreement is not a readable Word document.') from exc
    required=(f'Protected Member legal name  {order["buyer_legal_name"]}',
              f'Primary operating activity  {order["operating_activity"]}',
              f'Covered boundary  {order["covered_boundary"]}',
              f'Express exclusions  {order["exclusions"]}',
              f'Order and notices  L1A-{order_id} / Q{quote_id} / v{order["scope_version"]}; {order["notice_email"]}',
              f'${facts.total_cents / 100:,.2f} total USD; {facts.tax_rule_id} ({facts.tax_decision_reference})')
    if ('Standard terms revision 10, 5 October 2026' not in text or
            any(item not in text for item in required) or
            any(marker in text+headers+footers for marker in
                ('[Complete before issue]','Review Draft','CANDIDATE FOR REVIEW',
                 'Confidential review copy','Applicable tax and total  ['))):
        raise AgreementConflict('The agreement still contains drafting or incomplete text.')
    result=conn.execute('''UPDATE level1a_agreement_versions
        SET status='Issued',issued_at=? WHERE id=? AND tenant_id=?
        AND buyer_user_id=? AND status='Candidate' AND content_sha256=?''',
        (timestamp,agreement_id,tenant_id,buyer_user_id,row['content_sha256']))
    if result.rowcount!=1:
        raise AgreementConflict('The agreement changed before issue.')
    return dict(conn.execute('SELECT * FROM level1a_agreement_versions WHERE id=?',
                             (agreement_id,)).fetchone())


def record_issued_download(conn, *, tenant_id, buyer_user_id, order_id,
                           agreement_id, readback, timestamp):
    """Record a signed-in buyer's successful retrieval of exact issued bytes."""
    row=conn.execute('''SELECT * FROM level1a_agreement_versions WHERE id=?
        AND tenant_id=? AND buyer_user_id=? AND order_id=?''',
        (agreement_id,tenant_id,buyer_user_id,order_id)).fetchone()
    order=conn.execute('''SELECT * FROM level1a_orders WHERE id=? AND tenant_id=?
        AND buyer_user_id=?''',(order_id,tenant_id,buyer_user_id)).fetchone()
    if (not row or not order or row['status']!='Issued' or
            row['scope_version']!=order['scope_version'] or
            row['scope_sha256']!=order['scope_sha256'] or
            order['status'] not in ('ReadyForAgreement','Accepted')):
        raise AgreementConflict('No current issued agreement is available to download.')
    if not isinstance(readback, bytes) or sha256(readback).hexdigest()!=row['content_sha256']:
        raise AgreementConflict('The issued agreement failed storage readback.')
    conn.execute('''INSERT INTO level1a_agreement_downloads
        (tenant_id,buyer_user_id,order_id,agreement_id,content_sha256,downloaded_at)
        VALUES(?,?,?,?,?,?)''',
        (tenant_id,buyer_user_id,order_id,agreement_id,row['content_sha256'],timestamp))
    return dict(row)


def record_generated_candidate(conn, *, tenant_id, buyer_user_id, order_id,
                               quote_id, template_version, template_sha256,
                               content, stored_name, readback, timestamp):
    """Record one exact Salus-generated candidate after storage readback.

    The caller must get `readback` from the intended governed storage object,
    not echo the generated bytes. No Member-provided file is accepted here.
    """
    if not isinstance(content, bytes) or not content.startswith(b'PK') or len(content)>2_000_000:
        raise AgreementConflict('The generated Word document is invalid or too large.')
    if not isinstance(readback, bytes) or readback != content:
        raise AgreementConflict('The saved agreement differs from the generated bytes.')
    if (not isinstance(template_version,str) or not template_version or
            len(template_version)>120 or not isinstance(template_sha256,str) or
            len(template_sha256)!=64):
        raise AgreementConflict('The controlled template identity is incomplete.')
    content_hash=sha256(content).hexdigest()
    if stored_name != f'level1a/{tenant_id}/{order_id}/{quote_id}/{content_hash}.docx':
        raise AgreementConflict('The agreement storage key is outside its order.')
    order=conn.execute('''SELECT * FROM level1a_orders WHERE id=? AND tenant_id=?
        AND buyer_user_id=?''',(order_id,tenant_id,buyer_user_id)).fetchone()
    quote=conn.execute('''SELECT * FROM level1a_quote_versions WHERE id=? AND tenant_id=?
        AND buyer_user_id=? AND order_id=?''',
        (quote_id,tenant_id,buyer_user_id,order_id)).fetchone()
    if (not order or not quote or order['status']!='ReadyForAgreement' or
            order['scope_version']!=quote['scope_version'] or
            order['scope_sha256']!=quote['scope_sha256']):
        raise AgreementConflict('The selected scope or quote changed before agreement storage.')
    conn.execute('''INSERT INTO level1a_agreement_versions
        (tenant_id,buyer_user_id,order_id,quote_id,scope_version,scope_sha256,
         quote_sha256,template_version,template_sha256,content_sha256,
         stored_name,origin,status,created_at)
        VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?)
        ON CONFLICT(tenant_id,order_id,quote_id,template_sha256) DO NOTHING''',
        (tenant_id,buyer_user_id,order_id,quote_id,order['scope_version'],
         order['scope_sha256'],quote['quote_sha256'],template_version,
         template_sha256.lower(),content_hash,stored_name,
         'SalusGenerated','Candidate',timestamp))
    row=conn.execute('''SELECT * FROM level1a_agreement_versions
        WHERE tenant_id=? AND buyer_user_id=? AND order_id=? AND quote_id=?
        AND template_sha256=?''',
        (tenant_id,buyer_user_id,order_id,quote_id,template_sha256.lower())).fetchone()
    if (not row or row['content_sha256']!=content_hash or
            row['stored_name']!=stored_name or row['status']!='Candidate'):
        raise AgreementConflict('This agreement version already has different content.')
    return dict(row)
