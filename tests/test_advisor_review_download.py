"""The staff review action serves governed Word and PDF files, not raw API JSON."""

import json
from types import SimpleNamespace

import pytest

import salcapa_m365_advisor_reports as storage
from public_protection_advisor import _review_detail


SUBMISSION = "SPA-SUBMISSION-" + "A" * 32


def test_approved_review_page_prepares_then_offers_both_downloads():
    row = {
        "submission_key": SUBMISSION,
        "organization_name": "Fictional Organization",
        "contact_name": "Fictional Contact",
        "contact_email": "fictional@example.invalid",
        "created_at": "2026-10-09T00:00:00Z",
        "status": "Awaiting Salus Review",
        "result_json": json.dumps({"recommendation": "Review needed", "notice": "",
                                   "attention_count": 1, "information_gap_count": 1}),
        "answer_snapshot_json": "{}",
    }
    approved = {"handling_status": "Approved", "handling_profile": "Commercial Confidential",
                "revision_no": 1}
    page = _review_detail(row, approved)
    base = "/api/protection-advisor/review/" + SUBMISSION
    assert "id='report-form'" in page
    assert "event.preventDefault()" in page
    assert "role='status'" in page
    assert base + "/report.docx" in page
    assert base + "/report.pdf" in page
    assert "Download Word report" in page and "Download PDF report" in page
    assert "result.storage?.status!=='Stored for Salus Review'" in page
    unapproved = _review_detail(row, {**approved, "handling_status": "Pending"})
    assert "id='report-form'" not in unapproved
    assert base + "/report.docx" not in unapproved


def test_stored_advisor_download_is_anchored_and_validated(monkeypatch):
    monkeypatch.setenv("SALUS_M365_ADVISOR_REPORT_FOLDER_ITEM_ID", "advisorfolder123")
    seen = []

    class FakeClient:
        def __init__(self, config):
            assert config.folder_item_id == "advisorfolder123"
            self.client = SimpleNamespace(get=self.get)

        def _content_url(self, filename):
            seen.append(filename)
            return "https://graph.microsoft.com/content/" + filename

        def _request(self, method, url, **kwargs):
            assert method == "GET"
            return SimpleNamespace(
                status_code=302,
                headers={"Location": "https://tenant.sharepoint.com/report"},
                content=b"",
            )

        def get(self, location, **kwargs):
            assert location == "https://tenant.sharepoint.com/report"
            return SimpleNamespace(status_code=200, headers={}, content=b"%PDF-1.7\nfictional")

    monkeypatch.setattr(storage, "GovernedM365Reports", FakeClient)
    assert storage.read_advisor_report(SUBMISSION, "pdf").startswith(b"%PDF")
    assert seen == ["Salus-Protection-Advisor-SPA-REPORT-" + "A" * 32 + ".pdf"]
    with pytest.raises(storage.M365ReportError):
        storage.read_advisor_report(SUBMISSION + "/other", "pdf")
    with pytest.raises(storage.M365ReportError):
        storage.read_advisor_report(SUBMISSION, "html")


def test_stored_advisor_download_rejects_untrusted_redirect(monkeypatch):
    monkeypatch.setenv("SALUS_M365_ADVISOR_REPORT_FOLDER_ITEM_ID", "advisorfolder123")

    class FakeClient:
        def __init__(self, config):
            self.client = SimpleNamespace(get=lambda *_args, **_kwargs: pytest.fail("untrusted fetch"))

        def _content_url(self, filename):
            return "https://graph.microsoft.com/content/" + filename

        def _request(self, method, url, **kwargs):
            return SimpleNamespace(
                status_code=302,
                headers={"Location": "https://outside.example/report"},
                content=b"",
            )

    monkeypatch.setattr(storage, "GovernedM365Reports", FakeClient)
    with pytest.raises(storage.M365ReportError, match="untrusted"):
        storage.read_advisor_report(SUBMISSION, "docx")


def test_staff_download_requires_authority_and_approved_handling(tmp_path):
    """Exercise the live route shape with a fictional, isolated database."""
    import os
    import subprocess
    import sys
    import textwrap

    env = os.environ.copy()
    env.update({
        "SALUS_DB_PATH": str(tmp_path / "advisor-download.db"),
        "SALUS_LOCAL_STORAGE_DIR": str(tmp_path / "files"),
        "SALUS_SEED_DEMO": "0",
        "SALUS_AUTH_MODE": "prototype",
        "PYTHONPATH": os.pathsep.join(filter(None, (os.getcwd(), env.get("PYTHONPATH", "")))),
    })
    program = textwrap.dedent(r'''
        import json
        from fastapi.testclient import TestClient
        import app
        import public_protection_advisor as advisor

        key = "SPA-SUBMISSION-" + "A" * 32
        session = "SPA-SESSION-DOWNLOAD"
        conn = app.db()
        conn.execute("""INSERT INTO advisor_public_sessions
          (session_key,token_sha256,csrf_sha256,organization_type,primary_consent,
           secondary_deidentified_consent,consent_notice_version,retention_policy_version,
           questionnaire_version,status,created_at,expires_at,submitted_at)
           VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)""",
          (session,advisor._sha("fictional-session"),advisor._sha("csrf"),"Business",1,0,
           "consent-v1","retention-v1","questions-v1","Submitted",app.now(),
           "2099-01-01T00:00:00Z",app.now()))
        conn.execute("""INSERT INTO advisor_public_submissions
          (submission_key,session_key,organization_name,contact_name,contact_email,
           answer_snapshot_json,answer_snapshot_sha256,questionnaire_version,recommendation_version,
           consent_notice_version,retention_policy_version,secondary_deidentified_consent,
           result_json,status,created_at) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
          (key,session,"Fictional Organization","Fictional Contact","fictional@example.invalid",
           "{}","a"*64,"questions-v1","recommendation-v1","consent-v1","retention-v1",0,
           "{}","Awaiting Salus Review",app.now()))
        conn.execute("""INSERT INTO advisor_public_report_identity_revisions
          (revision_key,account_key,session_key,revision_no,protected_member_code_name,
           project_code_name,handling_profile,handling_status,created_by,created_at,content_sha256)
          VALUES(?,?,?,?,?,?,?,?,?,?,?)""",
          ("SPA-IDENTITY-DOWNLOAD","SPA-ACCOUNT-DOWNLOAD",session,1,"Fictional Member",
           "Fictional Project","Commercial Confidential","Approved","Salus Reviewer",app.now(),"b"*64))
        conn.commit()
        conn.close()
        advisor.read_advisor_report = lambda submission, file_format: (
            b"%PDF-1.4\nfictional" if submission == key and file_format == "pdf"
            else b"PK\x03\x04fictional"
        )
        base = "/api/protection-advisor/review/" + key
        admin = TestClient(app.app, headers={"X-Salus-Role": "System Administrator"})
        pdf = admin.get(base + "/report.pdf")
        assert pdf.status_code == 200, pdf.text
        assert pdf.content.startswith(b"%PDF")
        assert pdf.headers["content-type"].startswith("application/pdf")
        assert "attachment" in pdf.headers["content-disposition"]
        assert pdf.headers["cache-control"] == "no-store"
        word = admin.get(base + "/report.docx")
        assert word.status_code == 200, word.text
        assert word.content.startswith(b"PK\x03\x04")
        nonadmin = TestClient(app.app, headers={"X-Salus-Role": "Contributor"})
        assert nonadmin.get(base + "/report.pdf").status_code == 403
        assert admin.get(base + "/report.html").status_code == 404
        conn = app.db()
        conn.execute("UPDATE advisor_public_report_identity_revisions SET handling_status='Pending' WHERE session_key=?",
                     (session,))
        conn.commit()
        conn.close()
        assert admin.get(base + "/report.pdf").status_code == 409
    ''')
    completed = subprocess.run([sys.executable, "-c", program], env=env, capture_output=True,
                               text=True, timeout=80)
    assert completed.returncode == 0, completed.stdout + completed.stderr
