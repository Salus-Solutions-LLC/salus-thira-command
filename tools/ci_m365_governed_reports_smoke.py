"""Dependency-light CI smoke for governed Microsoft 365 report storage."""

import hashlib
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import httpx

from salcapa_m365_reports import (
    GovernedM365ReportConfig,
    GovernedM365Reports,
    M365ReportError,
    member_safe_artifact,
    report_filename,
)


class Token:
    token = "ci-token"
    expires_on = 4102444800


class Credential:
    def get_token(self, scope):
        assert scope == "https://graph.microsoft.com/.default"
        return Token()


CONFIG = GovernedM365ReportConfig(
    managed_identity_client_id="00000000-0000-4000-8000-000000000001",
    drive_id="b!TESTDRIVE0123456789",
    folder_item_id="01TESTFOLDERITEM1234567890",
    retries=3,
)


def main():
    snapshot = json.dumps(
        {"assessment": {"name": "Member", "internal": "remove"}},
        sort_keys=True,
        separators=(",", ":"),
    )
    row = {
        "id": 7,
        "tenant_id": 2,
        "assessment_id": 11,
        "snapshot_json": snapshot,
        "snapshot_sha256": hashlib.sha256(snapshot.encode()).hexdigest(),
    }
    artifact = member_safe_artifact(row, lambda assessment: {"name": assessment["name"]})
    assert json.loads(artifact) == {"assessment": {"name": "Member"}}
    assert report_filename(row).startswith("SalCAPA-Report-T2-A11-R7-")

    calls = []

    def handler(request):
        calls.append(request)
        if request.method == "PUT" and len(calls) == 1:
            return httpx.Response(503)
        if request.method == "PUT":
            return httpx.Response(201, json={"id": "01TESTREPORTITEM123456", "name": "report.json", "size": 2})
        if request.url.host == "graph.microsoft.com":
            return httpx.Response(302, headers={"Location": "https://tenant.sharepoint.com/download/report"})
        assert "Authorization" not in request.headers
        return httpx.Response(200, content=b"{}")

    store = GovernedM365Reports(
        CONFIG,
        credential=Credential(),
        client=httpx.Client(transport=httpx.MockTransport(handler)),
        sleeper=lambda _seconds: None,
    )
    uploaded = store.upload("report.json", b"{}")
    assert uploaded["item_id"] == "01TESTREPORTITEM123456"
    assert f"/items/{CONFIG.folder_item_id}:/report.json:/content" in str(calls[0].url)
    assert store.read("report.json") == b"{}"

    def malicious_redirect(_request):
        return httpx.Response(302, headers={"Location": "https://malicious.example/report"})

    unsafe_store = GovernedM365Reports(
        CONFIG,
        credential=Credential(),
        client=httpx.Client(transport=httpx.MockTransport(malicious_redirect)),
    )
    try:
        unsafe_store.read("report.json")
    except M365ReportError:
        pass
    else:
        raise AssertionError("untrusted report redirect was accepted")

    print("Governed Microsoft 365 report smoke passed")


if __name__ == "__main__":
    main()
