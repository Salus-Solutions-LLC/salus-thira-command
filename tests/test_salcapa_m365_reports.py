import hashlib
import json

import httpx

from salcapa_m365_reports import (
    GovernedM365ReportConfig,
    GovernedM365Reports,
    M365ReportError,
    member_safe_artifact,
    report_filename,
)


class Token:
    token = "test-token"
    expires_on = 4102444800


class Credential:
    def get_token(self, scope):
        assert scope == "https://graph.microsoft.com/.default"
        return Token()


def config(**changes):
    values = dict(
        managed_identity_client_id="00000000-0000-4000-8000-000000000001",
        drive_id="b!TESTDRIVE0123456789",
        folder_item_id="01TESTFOLDERITEM1234567890",
        retries=3,
    )
    values.update(changes)
    return GovernedM365ReportConfig(**values)


def row():
    snapshot = json.dumps({"assessment": {"name": "Member", "internal": "remove"}}, sort_keys=True, separators=(",", ":"))
    return {
        "id": 7,
        "tenant_id": 2,
        "assessment_id": 11,
        "snapshot_json": snapshot,
        "snapshot_sha256": hashlib.sha256(snapshot.encode()).hexdigest(),
    }


def test_upload_is_anchored_to_configured_folder():
    seen = []

    def handler(request):
        seen.append(request)
        return httpx.Response(201, json={"id": "01XK22UMTESTITEM123", "name": "report.json", "size": 2, "eTag": "etag"})

    client = httpx.Client(transport=httpx.MockTransport(handler))
    store = GovernedM365Reports(config(), credential=Credential(), client=client)
    result = store.upload("report.json", b"{}")
    assert result["item_id"] == "01XK22UMTESTITEM123"
    assert "/items/01TESTFOLDERITEM1234567890:/report.json:/content" in str(seen[0].url)
    assert "01TESTLIBRARYROOT1234567890" not in str(seen[0].url)


def test_retry_then_success():
    calls = []
    sleeps = []

    def handler(request):
        calls.append(request)
        if len(calls) == 1:
            return httpx.Response(503)
        return httpx.Response(201, json={"id": "01XK22UMTESTITEM123", "name": "report.json", "size": 2})

    store = GovernedM365Reports(
        config(), credential=Credential(), client=httpx.Client(transport=httpx.MockTransport(handler)), sleeper=sleeps.append
    )
    store.upload("report.json", b"{}")
    assert len(calls) == 2 and sleeps == [1]


def test_member_artifact_removes_internal_fields_and_is_deterministic():
    content = member_safe_artifact(row(), lambda assessment: {"name": assessment["name"]})
    assert json.loads(content) == {"assessment": {"name": "Member"}}
    assert report_filename(row()).startswith("SalCAPA-Report-T2-A11-R7-")


def test_integrity_failure_is_denied():
    changed = row()
    changed["snapshot_json"] += " "
    try:
        member_safe_artifact(changed, lambda value: value)
    except M365ReportError as exc:
        assert "integrity" in str(exc).lower()
    else:
        raise AssertionError("tampered report was accepted")


def test_invalid_filename_is_denied():
    store = GovernedM365Reports(config(), credential=Credential(), client=httpx.Client())
    try:
        store.upload("../outside.json", b"{}")
    except M365ReportError:
        pass
    else:
        raise AssertionError("path traversal filename was accepted")
