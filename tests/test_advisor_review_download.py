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
