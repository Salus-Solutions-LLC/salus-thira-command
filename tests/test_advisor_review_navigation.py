"""Direct email review links keep staff authentication and the exact return path."""

import pytest
from fastapi import HTTPException, Request

import app
from public_protection_advisor import _review_access_response


SUBMISSION = "SPA-SUBMISSION-9569A6E7F2A970D329F58FE7685CC964"


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
