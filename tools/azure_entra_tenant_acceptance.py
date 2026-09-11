#!/usr/bin/env python3
"""Bounded Entra and tenant-isolation acceptance for the exact SalCAPA image."""
import hashlib
import json
import os
import sys
import tempfile
from pathlib import Path
from types import SimpleNamespace
from urllib.parse import parse_qs, urlparse

ROOT = Path(os.environ.get("SALCAPA_ACCEPTANCE_ROOT", "/app"))
WORKSPACE = tempfile.TemporaryDirectory()
os.environ["SALUS_DB_BACKEND"] = "sqlite"
os.environ["SALUS_DB_PATH"] = str(Path(WORKSPACE.name) / "entra-acceptance.db")
os.environ["SALUS_BACKUP_DIR"] = str(Path(WORKSPACE.name) / "backups")
os.environ["SALUS_LOCAL_STORAGE_DIR"] = str(Path(WORKSPACE.name) / "attachments")
os.environ["SALUS_AUTH_MODE"] = "oidc"
os.environ["SALUS_ENV"] = "development"
os.environ["SALUS_SEED_DEMO"] = "1"
os.environ["SALUS_OIDC_CLIENT_AUTH_METHOD"] = "managed_identity"
os.environ["SALUS_OIDC_PROVIDER_NAME"] = "entra"
os.environ["SALUS_OIDC_AUTO_PROVISION"] = "0"
sys.path.insert(0, str(ROOT))

from fastapi.testclient import TestClient
import app

ISSUER = f"https://login.microsoftonline.com/{app.OIDC_TENANT_ID}/v2.0"
claims = {}
decode_failure = None
token_requests = []


class FakeResponse:
    def __init__(self, payload):
        self.payload = payload

    def raise_for_status(self):
        return None

    def json(self):
        return self.payload


class FakeCredential:
    def __init__(self, client_id=None):
        assert client_id == app.OIDC_MANAGED_IDENTITY_CLIENT_ID

    def get_token(self, scope):
        assert scope == app.OIDC_ASSERTION_SCOPE
        return SimpleNamespace(token="bounded-managed-identity-assertion", expires_on=4102444800)


class FakeJWKClient:
    def __init__(self, uri):
        assert uri == "https://login.microsoftonline.com/common/discovery/v2.0/keys"

    def get_signing_key_from_jwt(self, value):
        assert value == "signed-acceptance-id-token"
        return SimpleNamespace(key="acceptance-signing-key")


def fake_get(url, timeout):
    assert url == app.OIDC_DISCOVERY_URL and timeout == 10
    return FakeResponse({
        "authorization_endpoint": ISSUER + "/oauth2/v2.0/authorize",
        "token_endpoint": ISSUER + "/oauth2/v2.0/token",
        "jwks_uri": "https://login.microsoftonline.com/common/discovery/v2.0/keys",
        "issuer": ISSUER,
    })


def fake_post(url, data, timeout):
    assert url == ISSUER + "/oauth2/v2.0/token" and timeout == 15
    assert data["client_id"] == app.OIDC_CLIENT_ID
    assert data["client_assertion"] == "bounded-managed-identity-assertion"
    assert data["client_assertion_type"] == app.OIDC_CLIENT_ASSERTION_TYPE
    assert "client_secret" not in data
    token_requests.append(dict(data))
    return FakeResponse({"id_token": "signed-acceptance-id-token"})


def fake_decode(value, key, algorithms, audience, issuer):
    if decode_failure:
        raise decode_failure("rejected")
    assert value == "signed-acceptance-id-token"
    assert key == "acceptance-signing-key"
    assert audience == app.OIDC_CLIENT_ID and issuer == ISSUER
    return dict(claims)


def start(client):
    response = client.get("/api/auth/oidc/start", follow_redirects=False)
    assert response.status_code == 302, response.text
    values = parse_qs(urlparse(response.headers["location"]).query)
    return values["state"][0], values["nonce"][0]


def callback(client, state, expected=302):
    response = client.get(
        "/api/auth/oidc/callback",
        params={"code": "bounded-authorization-code", "state": state},
        follow_redirects=False,
    )
    assert response.status_code == expected, response.text
    return response


def set_claims(nonce, oid, tenant=None, email="fictional@example.invalid"):
    claims.clear()
    claims.update({
        "sub": "pairwise-acceptance-subject",
        "oid": oid,
        "tid": tenant or app.OIDC_TENANT_ID,
        "nonce": nonce,
        "name": "Fictional Demonstration User",
        "email": email,
        "email_verified": True,
        "roles": ["System Administrator"],
        "tenant_id": 999999,
    })


def add_tenant(conn, slug, name):
    row = conn.execute("SELECT id FROM tenants WHERE slug=?", (slug,)).fetchone()
    if not row:
        conn.execute(
            "INSERT INTO tenants(name,slug,status,created_at) VALUES(?,?,?,?)",
            (name, slug, "Active", app.now()),
        )
        row = conn.execute("SELECT id FROM tenants WHERE slug=?", (slug,)).fetchone()
    return int(row["id"])


def main():
    global decode_failure
    required = [
        app.OIDC_TENANT_ID,
        app.OIDC_DISCOVERY_URL,
        app.OIDC_CLIENT_ID,
        app.OIDC_MANAGED_IDENTITY_CLIENT_ID,
        app.OIDC_REDIRECT_URI,
    ]
    assert all(required)
    assert app.OIDC_AUTO_PROVISION is False
    assert app.OIDC_PROVIDER_NAME == "entra"
    assert app.OIDC_CLIENT_AUTH_METHOD == "managed_identity"

    app.ManagedIdentityCredential = FakeCredential
    app.httpx.get = fake_get
    app.httpx.post = fake_post
    app.jwt.PyJWKClient = FakeJWKClient
    app.jwt.decode = fake_decode
    app._oidc_cache.clear()
    app._oidc_credential = None

    conn = app.db()
    tenant_specs = [
        ("identity-acceptance-northstar", "Fictional Northstar Member", "entra-fictional-northstar", "Client Executive", "Confidential"),
        ("identity-acceptance-harbor", "Fictional Harbor Member", "entra-fictional-harbor", "Contributor", "Standard"),
        ("identity-acceptance-summit", "Fictional Summit Member", "entra-fictional-summit", "System Administrator", "Highly Sensitive"),
    ]
    mapped = []
    created = app.now()
    for index, (slug, name, oid, role, clearance) in enumerate(tenant_specs):
        tenant_id = add_tenant(conn, slug, name)
        username = f"identity-acceptance-{index + 1}"
        email = f"fictional-{index + 1}@example.invalid"
        conn.execute("DELETE FROM users WHERE username=?", (username,))
        conn.execute(
            "INSERT INTO users(tenant_id,username,display_name,password_hash,role,sensitivity_clearance,status,created_at,updated_at,email,external_subject,identity_provider) VALUES(?,?,?,?,?,?,?,?,?,?,?,?)",
            (tenant_id, username, "Fictional Demonstration User", "", role, clearance, "Active", created, created, email, oid, "entra"),
        )
        mapped.append((tenant_id, oid, email, role, clearance))
    disabled_tenant = mapped[0][0]
    conn.execute("DELETE FROM users WHERE username='identity-acceptance-disabled'")
    conn.execute(
        "INSERT INTO users(tenant_id,username,display_name,password_hash,role,sensitivity_clearance,status,created_at,updated_at,email,external_subject,identity_provider) VALUES(?,?,?,?,?,?,?,?,?,?,?,?)",
        (disabled_tenant, "identity-acceptance-disabled", "Fictional Disabled User", "", "Contributor", "Standard", "Disabled", created, created, "disabled@example.invalid", "entra-fictional-disabled", "entra"),
    )
    conn.commit()
    conn.close()

    status = app.oidc_federation_status()
    assert status["configured"] and status["healthy"] and status["mode"] == "managed_identity"

    sessions = []
    for tenant_id, oid, email, role, clearance in mapped:
        client = TestClient(app.app)
        state, nonce = start(client)
        set_claims(nonce, oid, email=email)
        assert callback(client, state).headers["location"] == "/"
        session = client.get("/api/auth/session").json()
        assert session["tenant_id"] == tenant_id
        assert session["role"] == role and session["clearance"] == clearance
        assert session["tenant_id"] != 999999 and session["role"] != "System Administrator" or role == "System Administrator"
        sessions.append((client, session))

    assert token_requests and all("client_secret" not in request for request in token_requests)
    assert len({session["tenant_id"] for _, session in sessions}) == 3

    for client, session in sessions:
        response = client.get("/api/admin/identity-acceptance")
        if session["role"] == "System Administrator":
            assert response.status_code == 200
            records = response.json()
            assert len(records) == 1
            assert all(record["tenant_id"] == session["tenant_id"] for record in records)
        else:
            assert response.status_code == 403

    replay_client = TestClient(app.app)
    replay_state, replay_nonce = start(replay_client)
    set_claims(replay_nonce, mapped[0][1], email=mapped[0][2])
    callback(replay_client, replay_state)
    attacker = TestClient(app.app)
    attacker.cookies.set("salus_oidc_state", replay_state)
    callback(attacker, replay_state, 401)

    negative = TestClient(app.app)
    state, nonce = start(negative)
    set_claims(nonce, "entra-fictional-unknown", email=mapped[0][2])
    callback(negative, state, 403)
    state, nonce = start(negative)
    set_claims(nonce, "entra-fictional-disabled", email="disabled@example.invalid")
    callback(negative, state, 403)
    state, nonce = start(negative)
    set_claims(nonce, mapped[0][1], tenant="00000000-0000-0000-0000-000000000000", email=mapped[0][2])
    callback(negative, state, 401)
    for failure in (app.jwt.InvalidIssuerError, app.jwt.InvalidAudienceError):
        decode_failure = failure
        state, nonce = start(negative)
        set_claims(nonce, mapped[0][1], email=mapped[0][2])
        callback(negative, state, 401)
    decode_failure = None

    conn = app.db()
    records = [dict(row) for row in conn.execute("SELECT * FROM identity_acceptance_events ORDER BY accepted_at,event_key")]
    conn.close()
    assert len(records) == 4
    assert {int(record["tenant_id"]) for record in records} == {item[0] for item in mapped}
    assert all(record["authority_source"] == "server_user_mapping" for record in records)
    assert all(record["identity_provider"] == "entra" for record in records)
    assert all(len(record["external_subject_sha256"]) == 64 for record in records)
    assert all("entra-fictional-" not in str(record) for record in records)
    expected_hashes = {hashlib.sha256(item[1].encode()).hexdigest() for item in mapped}
    assert expected_hashes.issubset({record["external_subject_sha256"] for record in records})

    print(json.dumps({
        "acceptance": "ENTRA_TENANT_ISOLATION_ACCEPTED",
        "fictional_tenants_verified": 3,
        "server_authority_verified": True,
        "cross_tenant_visibility_denied": True,
        "unknown_disabled_foreign_denied": True,
        "issuer_audience_replay_denied": True,
        "managed_identity_no_client_secret": True,
        "interactive_human_login_used": False,
    }, sort_keys=True))


if __name__ == "__main__":
    main()
