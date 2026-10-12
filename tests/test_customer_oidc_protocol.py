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
                                 CustomerGraphObjectIdMissing,
                                 CustomerGraphAccountMismatch,
                                 CustomerGraphSignInIdentitiesMissing,
                                 CustomerGraphSignInIdentityCountMismatch,
                                 CustomerGraphSignInEmailMismatch,
                                 CustomerEmailVerificationContradicted,
                                 CustomerEmailVerificationMissing,
                                 CustomerVerifiedEmailMismatch,
                                 create_certificate_assertion,
                                 create_certificate_assertion_from_pfx,
                                 validate_discovery, verified_customer_email,
                                 verified_customer_email_from_graph)


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

    def test_email_otp_graph_binding_requires_the_signed_account_and_one_mail_identity(self):
        claims = {'email': ' Buyer@Example.Test ', 'oid': 'fictional-object-id',
                  'idp': 'mail', 'amr': ['otp']}
        profile = {'id': 'fictional-object-id',
                   'identities': [{'signInType': 'federated', 'issuer': 'mail',
                                   'issuerAssignedId': 'buyer@example.test'}]}
        self.assertEqual(verified_customer_email_from_graph(claims, profile),
                         'buyer@example.test')
        # Entra's OIDC v2.0 email passcode method is `emailotp`.
        self.assertEqual(verified_customer_email_from_graph(
            dict(claims, amr=['emailotp']), profile), 'buyer@example.test')
        local_identity = {'signInType': 'emailAddress',
                          'issuer': 'salusmemberaccess.onmicrosoft.com',
                          'issuerAssignedId': 'buyer@example.test'}
        local_profile = dict(profile, identities=[local_identity])
        self.assertEqual(verified_customer_email_from_graph(
            dict(claims, amr=['emailotp']), local_profile), 'buyer@example.test')
        invalid = (
            (dict(claims, amr=[]), profile),
            (dict(claims, amr=['mfa']), profile),
            (dict(claims, amr=['pwd', 'otp']), profile),
            (dict(claims, amr=['pwd', 'emailotp']), profile),
            (dict(claims, amr=['fed', 'emailotp']), profile),
            (dict(claims, idp='google'), profile),
            (dict(claims, email_verified=False), profile),
            (dict(claims, email='other@example.test'), profile),
            (dict(claims, oid='other-object-id'), profile),
            (claims, dict(profile, id='other-object-id')),
            (claims, dict(profile, identities=[])),
            (claims, dict(profile, identities=[
                profile['identities'][0], profile['identities'][0]])),
            (claims, dict(profile, identities=[
                {'signInType': 'emailAddress', 'issuer': 'mail',
                 'issuerAssignedId': 'buyer@example.test'}])),
            (claims, dict(local_profile, id='other-object-id')),
            (claims, dict(local_profile, identities=[
                dict(local_identity, issuer='unrelated.onmicrosoft.com')])),
            (claims, dict(local_profile, identities=[
                dict(local_identity, issuerAssignedId='other@example.test')])),
            (claims, dict(local_profile, identities=[
                local_identity, local_identity])),
            (claims, dict(local_profile, identities=[
                local_identity, profile['identities'][0]])),
        )
        for bad_claims, bad_profile in invalid:
            with self.subTest(claims=bad_claims, profile=bad_profile):
                with self.assertRaises(ValueError):
                    verified_customer_email_from_graph(bad_claims, bad_profile)

    def test_graph_failure_types_reveal_only_the_failed_check(self):
        claims = {'email': 'buyer@example.test', 'oid': 'fictional-object-id',
                  'idp': 'mail', 'amr': ['emailotp']}
        identity = {'signInType': 'federated', 'issuer': 'mail',
                    'issuerAssignedId': 'buyer@example.test'}
        profile = {'id': 'fictional-object-id', 'identities': [identity]}
        cases = (
            (dict(claims, oid=''), profile, CustomerGraphObjectIdMissing),
            (claims, dict(profile, id='other-object-id'),
             CustomerGraphAccountMismatch),
            (claims, dict(profile, identities=None),
             CustomerGraphSignInIdentitiesMissing),
            (claims, dict(profile, identities=[]),
             CustomerGraphSignInIdentityCountMismatch),
            (claims, dict(profile, identities=[identity, identity]),
             CustomerGraphSignInIdentityCountMismatch),
            (claims, dict(profile, identities=[
                dict(identity, issuerAssignedId='other@example.test')]),
             CustomerGraphSignInEmailMismatch),
        )
        for token, graph, expected in cases:
            with self.subTest(expected=expected.__name__):
                with self.assertRaises(expected) as caught:
                    verified_customer_email_from_graph(token, graph)
                self.assertEqual(type(caught.exception).__name__, expected.__name__)
                self.assertNotIn('buyer@example.test',
                                 type(caught.exception).__name__)

    def test_invalid_pfx_secret_fails_closed(self):
        for bad in ('not-base64!', base64.b64encode(b'not a certificate').decode('ascii')):
            with self.assertRaises(ValueError):
                create_certificate_assertion_from_pfx(
                    client_id='fictional-client',
                    token_endpoint=BASE+'/oauth2/v2.0/token', pfx_base64=bad)


if __name__ == '__main__':
    unittest.main()
