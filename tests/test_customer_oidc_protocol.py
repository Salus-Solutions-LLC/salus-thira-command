"""The customer OIDC authority and certificate must be independently pinned."""

import unittest

import jwt
from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.x509.oid import NameOID
from datetime import datetime, timedelta, timezone

from salus_customer_oidc import create_certificate_assertion, validate_discovery


HOST = 'salusmemberaccess.ciamlogin.com'
TENANT = 'c4582c39-7d49-4419-b504-005c31e69549'
BASE = f'https://{HOST}/{TENANT}'


class CustomerOidcProtocolTests(unittest.TestCase):
    def test_discovery_rejects_workforce_or_external_endpoints(self):
        metadata = {'issuer': BASE + '/v2.0',
                    'authorization_endpoint': BASE + '/oauth2/v2.0/authorize',
                    'token_endpoint': BASE + '/oauth2/v2.0/token',
                    'jwks_uri': BASE + '/discovery/v2.0/keys'}
        self.assertEqual(validate_discovery(metadata, tenant_host=HOST, tenant_id=TENANT),
                         metadata)
        for key, bad_value in (
            ('issuer', f'https://login.microsoftonline.com/{TENANT}/v2.0'),
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


if __name__ == '__main__':
    unittest.main()
