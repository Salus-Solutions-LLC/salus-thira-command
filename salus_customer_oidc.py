"""Separate, fail-closed Microsoft External ID customer OIDC trust boundary."""

import base64
import hashlib
import secrets
import time
from urllib.parse import urlparse

import jwt
from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization


CLIENT_ASSERTION_TYPE = 'urn:ietf:params:oauth:client-assertion-type:jwt-bearer'


def validate_discovery(metadata, *, tenant_host, tenant_id):
    """Accept only the reviewed single External tenant and its HTTPS endpoints."""
    expected_issuer = f'https://{tenant_host}/{tenant_id}/v2.0'
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
