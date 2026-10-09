"""Direct email review links keep staff authentication and the exact return path."""

import sqlite3

import pytest
from fastapi import HTTPException, Request

import app
from public_protection_advisor import _review_access_response, _review_url


SUBMISSION = "SPA-SUBMISSION-AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA"


def _request(path):
    return Request({
        "type": "http", "method": "GET", "scheme": "https", "path": path,
        "raw_path": path.encode(), "query_string": b"", "headers": [],
        "server": ("salcapa.salus.solutions", 443),
    })


def test_email_review_link_signs_staff_in_and_returns_to_exact_record():
    path = "/protection-advisor/review/" + SUBMISSION

    def unauthenticated(_request, _permission):
        raise HTTPException(401, "Authentication required")

    response = _review_access_response(_request(path), unauthenticated, "oidc")
    assert response.status_code == 302
    assert response.headers["location"] == "/api/auth/oidc/start?next=" + path.replace("/", "%2F")
    assert response.headers["cache-control"] == "no-store"
    assert app.staff_oidc_return_path(path) == path
    assert app.staff_oidc_return_path("/protection-advisor/review") == "/protection-advisor/review"


def test_review_return_cannot_leave_the_staff_review_area():
    for path in ("https://evil.example", "//evil.example", "/api/admin/readiness",
                 "/protection-advisor/review/SPA-SUBMISSION-other", "/protection-advisor/review/../"):
        assert app.staff_oidc_return_path(path) == "/"

def test_staff_email_link_uses_https_despite_http_proxy_scheme():
    path = "/protection-advisor/review/" + SUBMISSION
    request = _request(path)
    request.scope["scheme"] = "http"
    assert _review_url(request, SUBMISSION) == "https://salcapa.salus.solutions" + path



def test_staff_email_link_never_uses_the_azure_development_host():
    path = "/protection-advisor/review/" + SUBMISSION
    request = _request(path)
    request.scope["scheme"] = "http"
    request.scope["server"] = ("salcapa-dev-b48224.ashycoast-29444a28.southcentralus.azurecontainerapps.io", 80)
    assert _review_url(request, SUBMISSION) == "https://salcapa.salus.solutions" + path


def test_review_never_redirects_a_signed_in_non_admin():
    def denied(_request, _permission):
        raise HTTPException(403, "Not authorized")

    with pytest.raises(HTTPException) as exc:
        _review_access_response(_request("/protection-advisor/review/" + SUBMISSION), denied, "oidc")
    assert exc.value.status_code == 403


def test_session_mode_shows_a_readable_sign_in_instruction():
    def unauthenticated(_request, _permission):
        raise HTTPException(401, "Authentication required")

    response = _review_access_response(_request("/protection-advisor/review"), unauthenticated, "session")
    assert response.status_code == 401
    assert b"Sign in required" in response.body
    assert response.headers["x-frame-options"] == "DENY"


def test_staff_continuation_is_one_time_and_keeps_exact_path(tmp_path, monkeypatch):
    path = "/protection-advisor/review/" + SUBMISSION
    db_path = tmp_path / "continuation.db"

    def database():
        connection = sqlite3.connect(db_path)
        connection.row_factory = sqlite3.Row
        return connection

    with database() as connection:
        connection.execute("CREATE TABLE oidc_review_continuations ("
                           "state_hash TEXT PRIMARY KEY, review_path TEXT NOT NULL, "
                           "session_token_hash TEXT UNIQUE, expires_at TEXT NOT NULL)")
        connection.execute("INSERT INTO oidc_review_continuations VALUES (?,?,?,?)",
                           ("state", path, app._hash_token("fictional-session"), "9999-12-31T00:00:00Z"))

    monkeypatch.setattr(app, "db", database)
    monkeypatch.setattr(app, "require", lambda request, permission: None)
    request = _request("/api/auth/oidc/continue")
    request.scope["headers"] = [(b"cookie", b"salus_session=fictional-session")]
    response = app.oidc_continue(request)
    assert response.status_code == 302
    assert response.headers["location"] == path
    with pytest.raises(HTTPException) as exc:
        app.oidc_continue(request)
    assert exc.value.status_code == 404
