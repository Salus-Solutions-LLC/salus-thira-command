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


class CustomerEmailMissing(ValueError):
    """The signed token did not include an email claim."""


class CustomerEmailInvalid(ValueError):
    """The signed token email was not a usable address."""


class CustomerVerifiedEmailMismatch(ValueError):
    """The signed authoritative address did not match the email claim."""


class CustomerEmailVerificationContradicted(ValueError):
    """The provider explicitly denied verification."""


class CustomerEmailVerificationMissing(ValueError):
    """The provider did not assert verification."""


class CustomerOtpMethodMissing(ValueError):
    """The signed token did not assert one-time-passcode authentication."""


class CustomerGraphIdentityMismatch(ValueError):
    """The signed subject and Graph email sign-in identity did not agree."""


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
        raise CustomerEmailMissing('Customer email is missing')
    email = raw_email.strip().lower()
    if (not email or email.count('@') != 1
            or any(character.isspace() for character in email)):
        raise CustomerEmailInvalid('Customer email is invalid')
    primary = claims.get('verified_primary_email')
    if primary is not None:
        if (not isinstance(primary, str)
                or not primary.strip()
                or primary.strip().lower() != email):
            raise CustomerVerifiedEmailMismatch(
                'Verified primary email differs from customer email')
    asserted = claims.get('email_verified')
    if asserted is not None and asserted is not True:
        raise CustomerEmailVerificationContradicted(
            'Customer email verification is contradicted')
    if asserted is not True and primary is None:
        raise CustomerEmailVerificationMissing(
            'Customer email verification is missing')
    return email

def verified_customer_email_from_graph(claims, profile):
    """Verify an OTP-only customer's address against Graph's own sign-in identity.

    This path is only used after the signed ID token has passed issuer, audience,
    tenant, nonce and subject validation and lacks an authoritative email claim.
    The delegated Graph token must come from the same authorization-code exchange.
    """
    try:
        verified_customer_email(claims)
    except CustomerEmailVerificationMissing:
        pass
    else:
        raise ValueError('Graph fallback requires missing provider verification')
    if claims.get('idp') != 'mail':
        raise CustomerOtpMethodMissing('Customer did not use the mail provider')
    amr = claims.get('amr')
    if not isinstance(amr, list) or not {'otp', 'emailotp'}.intersection(amr) or any(
            method in amr for method in ('pwd', 'fed', 'none')):
        raise CustomerOtpMethodMissing('Customer OTP authentication is not asserted')
    oid = claims.get('oid')
    if not isinstance(oid, str) or not oid.strip():
        raise CustomerGraphIdentityMismatch('Customer object ID is missing')
    if not isinstance(profile, dict) or profile.get('id') != oid:
        raise CustomerGraphIdentityMismatch('Graph account differs from signed customer')
    identities = profile.get('identities')
    if not isinstance(identities, list):
        raise CustomerGraphIdentityMismatch('Graph sign-in identities are missing')
    email = claims['email'].strip().lower()
    mail_identities = [identity for identity in identities
                       if isinstance(identity, dict)
                       and identity.get('signInType') == 'federated'
                       and identity.get('issuer') == 'mail']
    if (len(mail_identities) != 1
            or not isinstance(mail_identities[0].get('issuerAssignedId'), str)
            or mail_identities[0]['issuerAssignedId'].strip().lower() != email):
        raise CustomerGraphIdentityMismatch('Graph mail sign-in identity differs')
    return email
