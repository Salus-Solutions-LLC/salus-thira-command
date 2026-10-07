"""Separate, fail-closed Microsoft External ID customer OIDC trust boundary."""

import base64
import binascii
import hashlib
import secrets
import time
from urllib.parse import urlparse

import jwt
from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.hazmat.primitives.serialization import pkcs12


CLIENT_ASSERTION_TYPE = 'urn:ietf:params:oauth:client-assertion-type:jwt-bearer'


def validate_discovery(metadata, *, tenant_host, tenant_id):
    """Accept only the reviewed single External tenant and its HTTPS endpoints."""
    # The reviewed External ID discovery URL uses the tenant-name host for
    # endpoints, but its issuer is the tenant-ID host. Pin both independently.
    expected_issuer = f'https://{tenant_id}.ciamlogin.com/{tenant_id}/v2.0'
    if metadata.get('issuer', '').rstrip('/') != expected_issuer:
        raise ValueError('Customer identity issuer mismatch')
    for key in ('authorization_endpoint', 'token_endpoint', 'jwks_uri'):
        parsed = urlparse(str(metadata.get(key) or ''))
        if (parsed.scheme != 'https' or parsed.hostname != tenant_host
                or parsed.port is not None or parsed.username or parsed.password
                or not parsed.path.startswith(f'/{tenant_id}/')):
            raise ValueError('Customer identity endpoint outside the reviewed tenant')
    return metadata


def create_certificate_assertion(*, client_id, token_endpoint, private_key_pem,
                                 certificate_pem, issued_at=None):
    """Sign a short-lived client assertion; only the public certificate is registered."""
    key = serialization.load_pem_private_key(private_key_pem.encode('utf-8'), password=None)
    certificate = x509.load_pem_x509_certificate(certificate_pem.encode('utf-8'))
    if key.public_key().public_numbers() != certificate.public_key().public_numbers():
        raise ValueError('Customer identity certificate and private key differ')
    return _sign_certificate_assertion(client_id=client_id, token_endpoint=token_endpoint,
                                       key=key, certificate=certificate, issued_at=issued_at)


def create_certificate_assertion_from_pfx(*, client_id, token_endpoint,
                                          pfx_base64, issued_at=None):
    """Sign with the exportable certificate secret returned by Azure Key Vault."""
    try:
        encoded = ''.join(str(pfx_base64).split())
        raw = base64.b64decode(encoded, validate=True)
        key, certificate, _ = pkcs12.load_key_and_certificates(raw, None)
    except (ValueError, TypeError, binascii.Error) as exc:
        raise ValueError('Invalid customer certificate secret') from exc
    if not isinstance(key, rsa.RSAPrivateKey) or certificate is None:
        raise ValueError('Customer certificate private key is unavailable')
    if key.public_key().public_numbers() != certificate.public_key().public_numbers():
        raise ValueError('Customer certificate and private key differ')
    return _sign_certificate_assertion(client_id=client_id, token_endpoint=token_endpoint,
                                       key=key, certificate=certificate, issued_at=issued_at)


def _sign_certificate_assertion(*, client_id, token_endpoint, key, certificate,
                                issued_at=None):
    moment = int(time.time()) if issued_at is None else int(issued_at)
    thumbprint = base64.urlsafe_b64encode(
        certificate.fingerprint(hashes.SHA256())).rstrip(b'=').decode('ascii')
    payload = {'aud': token_endpoint, 'iss': client_id, 'sub': client_id,
               'jti': secrets.token_hex(16), 'iat': moment, 'nbf': moment,
               'exp': moment + 300}
    return jwt.encode(payload, key, algorithm='PS256',
                      headers={'x5t#S256': thumbprint, 'typ': 'JWT'})


def pkce_challenge(verifier):
    return base64.urlsafe_b64encode(hashlib.sha256(verifier.encode('ascii')).digest()
                                    ).rstrip(b'=').decode('ascii')


def verified_customer_email(claims):
    """Return an address only when a signed provider claim verifies that address.

    The caller must first validate token signature, issuer, audience, tenant,
    nonce and subject. The ordinary email claim alone is never sufficient.
    """
    if not isinstance(claims, dict):
        raise ValueError('Customer identity claims are invalid')
    raw_email = claims.get('email')
    if not isinstance(raw_email, str):
        raise ValueError('Customer email is missing')
    email = raw_email.strip().lower()
    if (not email or email.count('@') != 1
            or any(character.isspace() for character in email)):
        raise ValueError('Customer email is invalid')
    primary = claims.get('verified_primary_email')
    if primary is not None:
        if (not isinstance(primary, str)
                or not primary.strip()
                or primary.strip().lower() != email):
            raise ValueError('Verified primary email differs from customer email')
    asserted = claims.get('email_verified')
    if asserted is not None and asserted is not True:
        raise ValueError('Customer email verification is contradicted')
    if asserted is not True and primary is None:
        raise ValueError('Customer email verification is missing')
    return email
