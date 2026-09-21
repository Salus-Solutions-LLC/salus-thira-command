import os
from pathlib import Path
from tempfile import TemporaryDirectory

import salcapa_m365_advisor_reports as advisor_reports


class Response:
    def __init__(self, status_code, *, payload=None, content=b"", headers=None):
        self.status_code = status_code
        self._payload = payload or {}
        self.content = content
        self.headers = headers or {}

    def json(self):
        return self._payload


class DownloadClient:
    def get(self, url, headers=None):
        assert url == "https://salus.sharepoint.com/advisor.pdf"
        assert headers == {"Accept": "application/pdf"}
        return Response(200, content=b"%PDF-1.7\nthree-page-advisor-report")


class FakeReports:
    def __init__(self, config):
        self.config = config
        self.client = DownloadClient()
        self.calls = []

    def _content_url(self, filename):
        return f"https://graph.microsoft.com/v1.0/upload/{filename}"

    def _request(self, method, url, **kwargs):
        self.calls.append((method, url, kwargs))
        if method == "PUT" and url.endswith(".docx"):
            return Response(201, payload={"id": "DOCX-ITEM", "name": "advisor.docx"})
        if method == "GET" and url.endswith("content?format=pdf"):
            return Response(302, headers={"Location": "https://salus.sharepoint.com/advisor.pdf"})
        if method == "PUT" and url.endswith(".pdf"):
            return Response(201, payload={"id": "PDF-ITEM", "name": "advisor.pdf"})
        raise AssertionError((method, url))


for name, value in {
    "SALUS_OIDC_MANAGED_IDENTITY_CLIENT_ID": "00000000-0000-0000-0000-000000000001",
    "SALUS_M365_REPORT_DRIVE_ID": "DRIVE-1",
    "SALUS_M365_REPORT_FOLDER_ITEM_ID": "REPORTS-1",
    "SALUS_M365_ADVISOR_REPORT_FOLDER_ITEM_ID": "ADVISOR-1",
    "SALUS_M365_REPORT_MAX_FILE_BYTES": "26214400",
    "SALUS_M365_REPORT_RETRIES": "3",
}.items():
    os.environ[name] = value

advisor_reports.GovernedM365Reports = FakeReports
with TemporaryDirectory() as tmp:
    path = Path(tmp) / "advisor.docx"
    path.write_bytes(b"PK\x03\x04sample-docx")
    result = advisor_reports.publish_advisor_docx(str(path), "SPA-REPORT-0001")

assert result["status"] == "Stored for Salus Review"
assert result["item_id"] == "DOCX-ITEM"
assert result["pdf"]["item_id"] == "PDF-ITEM"
assert result["pdf"]["sha256"]
assert result["review_required"] is True
print("Protection Advisor Microsoft 365 DOCX and PDF smoke passed")
