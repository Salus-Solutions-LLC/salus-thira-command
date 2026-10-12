"""Fail-closed, tenant-isolated binding for a verified external buyer identity.

Signed-token validation and customer authentication happen before this function is called.
Email is contact data; only issuer and subject select an existing buyer account.
"""

import hashlib
import uuid


CUSTOMER_PROVIDER = 'entra_customer'


def identity_hash(issuer: str, subject: str) -> str:
    issuer = str(issuer or '').strip()
    subject = str(subject or '').strip()
    if not issuer or not subject:
        raise ValueError('A verified issuer and subject are required')
    return hashlib.sha256((issuer + '\x00' + subject).encode('utf-8')).hexdigest()


def bind_verified_buyer(conn, *, issuer: str, subject: str, email: str,
                        display_name: str, timestamp: str):
    """Return the one buyer binding, creating an isolated tenant only once.

    Caller owns the transaction. The unique database key is authoritative under
    concurrent callbacks; a constraint conflict must roll back and reread.
    """
    subject_digest = identity_hash(issuer, subject)
    normalized_email = str(email or '').strip().lower()
    if not normalized_email or '@' not in normalized_email:
        raise ValueError('A usable buyer contact email is required')
    if not timestamp:
        raise ValueError('A timestamp is required')
    existing = conn.execute(
        'SELECT tenant_id,user_id FROM customer_identity_bindings '
        'WHERE provider=? AND subject_sha256=?',
        (CUSTOMER_PROVIDER, subject_digest),
    ).fetchone()
    if existing:
        user = conn.execute('SELECT status,role,tenant_id,identity_provider,external_subject FROM users WHERE id=?',
                            (existing['user_id'],)).fetchone()
        tenant = conn.execute('SELECT status FROM tenants WHERE id=?',
                              (existing['tenant_id'],)).fetchone()
        if (not user or not tenant or user['status'] != 'Active' or tenant['status'] != 'Active'
                or user['role'] != 'Client Executive'
                or user['identity_provider'] != CUSTOMER_PROVIDER
                or user['external_subject'] != subject_digest
                or int(user['tenant_id']) != int(existing['tenant_id'])):
            raise ValueError('Existing buyer binding is inactive or inconsistent')
        return int(existing['tenant_id']), int(existing['user_id']), False

    identifier = uuid.uuid4().hex
    tenant_id = conn.execute(
        'INSERT INTO tenants(name,slug,status,created_at) VALUES(?,?,?,?)',
        ('Protected Member applicant', f'buyer-{identifier}', 'Active', timestamp),
    ).lastrowid
    user_id = conn.execute(
        'INSERT INTO users(tenant_id,username,display_name,password_hash,role,'
        'sensitivity_clearance,status,created_at,updated_at,email,external_subject,'
        'identity_provider) VALUES(?,?,?,?,?,?,?,?,?,?,?,?)',
        (tenant_id, f'buyer-{identifier}', display_name[:200], '',
         'Client Executive', 'Standard', 'Active', timestamp, timestamp,
         normalized_email, subject_digest, CUSTOMER_PROVIDER),
    ).lastrowid
    conn.execute(
        'INSERT INTO customer_identity_bindings(provider,subject_sha256,tenant_id,'
        'user_id,created_at) VALUES(?,?,?,?,?)',
        (CUSTOMER_PROVIDER, subject_digest, tenant_id, user_id, timestamp),
    )
    return int(tenant_id), int(user_id), True
