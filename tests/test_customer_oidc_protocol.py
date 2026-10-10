"""The customer OIDC authority and certificate must be independently pinned."""

import unittest
import base64

import jwt
from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.hazmat.primitives.serialization import pkcs12
from cryptography.x509.oid import NameOID
from datetime import datetime, timedelta, timezone

from salus_customer_oidc import (CustomerEmailInvalid, CustomerEmailMissing,
                                 CustomerEmailVerificationContradicted,
                                 CustomerEmailVerificationMissing,
                                 CustomerVerifiedEmailMismatch,
                                 create_certificate_assertion,
                                 create_certificate_assertion_from_pfx,
                                 validate_discovery, verified_customer_email)


HOST = 'salusmemberaccess.ciamlogin.com'
TENANT = 'c4582c39-7d49-4419-b504-005c31e69549'
BASE = f'https://{HOST}/{TENANT}'


class CustomerOidcProtocolTests(unittest.TestCase):
    def test_discovery_rejects_workforce_or_external_endpoints(self):
        metadata = {'issuer': f'https://{TENANT}.ciamlogin.com/{TENANT}/v2.0',
                    'authorization_endpoint': BASE + '/oauth2/v2.0/authorize',
                    'token_endpoint': BASE + '/oauth2/v2.0/token',
                    'jwks_uri': BASE + '/discovery/v2.0/keys'}
        self.assertEqual(validate_discovery(metadata, tenant_host=HOST, tenant_id=TENANT),
                         metadata)
        for key, bad_value in (
            ('issuer', f'https://login.microsoftonline.com/{TENANT}/v2.0'),
            ('issuer', BASE + '/v2.0'),
            ('token_endpoint', 'https://attacker.example.test/token'),
            ('jwks_uri', f'https://{HOST}/different-tenant/discovery/v2.0/keys'),
        ):
            changed = dict(metadata, **{key: bad_value})
            with self.assertRaises(ValueError):
                validate_discovery(changed, tenant_host=HOST, tenant_id=TENANT)

    def test_certificate_assertion_is_short_lived_and_bound_to_client_and_endpoint(self):
        key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
        subject = issuer = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME,
                                                         'Fictional Salus test')])
        certificate = (x509.CertificateBuilder().subject_name(subject)
                       .issuer_name(issuer).public_key(key.public_key())
                       .serial_number(x509.random_serial_number())
                       .not_valid_before(datetime.now(timezone.utc)-timedelta(minutes=1))
                       .not_valid_after(datetime.now(timezone.utc)+timedelta(days=1))
                       .sign(key, hashes.SHA256()))
        key_pem = key.private_bytes(serialization.Encoding.PEM,
                                    serialization.PrivateFormat.PKCS8,
                                    serialization.NoEncryption()).decode()
        cert_pem = certificate.public_bytes(serialization.Encoding.PEM).decode()
        token = create_certificate_assertion(
            client_id='fictional-client', token_endpoint=BASE+'/oauth2/v2.0/token',
            private_key_pem=key_pem, certificate_pem=cert_pem, issued_at=1000000)
        header = jwt.get_unverified_header(token)
        self.assertEqual(header['alg'], 'PS256')
        self.assertTrue(header['x5t#S256'])
        claims = jwt.decode(token, key.public_key(), algorithms=['PS256'],
                            audience=BASE+'/oauth2/v2.0/token', options={'verify_exp':False})
        self.assertEqual(claims['iss'], 'fictional-client')
        self.assertEqual(claims['sub'], 'fictional-client')
        self.assertEqual(claims['exp']-claims['iat'], 300)

    def test_key_vault_pfx_secret_signs_same_bound_assertion(self):
        key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
        subject = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME,
                                               'Fictional Salus vault test')])
        certificate = (x509.CertificateBuilder().subject_name(subject)
                       .issuer_name(subject).public_key(key.public_key())
                       .serial_number(x509.random_serial_number())
                       .not_valid_before(datetime.now(timezone.utc)-timedelta(minutes=1))
                       .not_valid_after(datetime.now(timezone.utc)+timedelta(days=1))
                       .sign(key, hashes.SHA256()))
        pfx = pkcs12.serialize_key_and_certificates(
            b'fictional-test', key, certificate, None, serialization.NoEncryption())
        token = create_certificate_assertion_from_pfx(
            client_id='fictional-client', token_endpoint=BASE+'/oauth2/v2.0/token',
            pfx_base64=base64.b64encode(pfx).decode('ascii'))
        claims = jwt.decode(token, key.public_key(), algorithms=['PS256'],
                            audience=BASE+'/oauth2/v2.0/token')
        self.assertEqual(claims['iss'], 'fictional-client')
        self.assertEqual(claims['exp']-claims['iat'], 300)
        self.assertEqual(jwt.get_unverified_header(token)['x5t#S256'],
                         base64.urlsafe_b64encode(certificate.fingerprint(hashes.SHA256())
                                                  ).rstrip(b'=').decode('ascii'))

    def test_customer_email_requires_a_matching_provider_verification_claim(self):
        self.assertEqual(verified_customer_email({
            'email': ' Buyer@Example.Test ', 'verified_primary_email': 'buyer@example.test'}),
            'buyer@example.test')
        self.assertEqual(verified_customer_email({
            'email': 'buyer@example.test', 'email_verified': True}),
            'buyer@example.test')

    def test_customer_email_claims_fail_closed_on_absence_or_contradiction(self):
        invalid = (
            {'email': 'buyer@example.test', 'idp': 'mail'},
            {'email': 'buyer@example.test', 'email_verified': False},
            {'email': 'buyer@example.test', 'email_verified': False,
             'verified_primary_email': 'buyer@example.test'},
            {'email': 'buyer@example.test', 'verified_primary_email': 'other@example.test'},
            {'email': 'buyer@example.test', 'email_verified': True,
             'verified_primary_email': 'other@example.test'},
            {'email': 'buyer@example.test', 'verified_primary_email': ['buyer@example.test']},
            {'email': 'buyer@example.test', 'verified_primary_email': ''},
            {'email': ['buyer@example.test'], 'email_verified': True},
            {'email': 'buyer @example.test', 'email_verified': True},
        )
        for claims in invalid:
            with self.subTest(claims=claims), self.assertRaises(ValueError):
                verified_customer_email(claims)

    def test_customer_email_failure_types_are_safe_and_specific(self):
        cases = (
            ({'email': None}, CustomerEmailMissing),
            ({'email': 'not-an-address'}, CustomerEmailInvalid),
            ({'email': 'buyer@example.test',
              'verified_primary_email': 'other@example.test'},
             CustomerVerifiedEmailMismatch),
            ({'email': 'buyer@example.test', 'email_verified': False},
             CustomerEmailVerificationContradicted),
            ({'email': 'buyer@example.test'},
             CustomerEmailVerificationMissing),
        )
        for claims, expected in cases:
            with self.subTest(expected=expected), self.assertRaises(expected):
                verified_customer_email(claims)

    def test_invalid_pfx_secret_fails_closed(self):
        for bad in ('not-base64!', base64.b64encode(b'not a certificate').decode('ascii')):
            with self.assertRaises(ValueError):
                create_certificate_assertion_from_pfx(
                    client_id='fictional-client',
                    token_endpoint=BASE+'/oauth2/v2.0/token', pfx_base64=bad)


if __name__ == '__main__':
    unittest.main()
