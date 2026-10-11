"""Regression checks for bounded governed Microsoft 365 folder listing."""

import httpx
import pytest

from salcapa_m365_intake import (
    GovernedM365Config,
    GovernedM365Intake,
    M365IntakeError,
)


ROOT = "01SALUSROOTITEM123456789"
PENDING = "01SALUSPENDINGITEM123456789"
DRIVE = "b!SALUSDRIVE0123456789"


def _intake(*, malicious_next_link=False):
    pages = []

    def handler(request):
        path = request.url.path
        if path.endswith(f"/items/{ROOT}/children"):
            return httpx.Response(
                200,
                json={"value": [{"id": PENDING, "name": "10 Pending Classification", "folder": {}}]},
            )
        assert path.endswith(f"/items/{PENDING}/children")
        offset = int(request.url.params.get("$skip", "0"))
        pages.append(offset)
        values = [
            {
                "id": f"01SALUSFILE{index:08d}",
                "name": f"sample-{index}.txt",
                "file": {"mimeType": "text/plain"},
                "size": 1,
                "eTag": f"etag-{index}",
                "lastModifiedDateTime": "2026-10-11T00:00:00Z",
                "webUrl": f"https://salus.sharepoint.com/sample-{index}.txt",
            }
            for index in range(offset, offset + 200)
        ]
        next_link = (
            "https://outside.example/children?$skip=200"
            if malicious_next_link
            else f"https://graph.microsoft.com/v1.0/drives/{DRIVE}/items/{PENDING}/children?$skip={offset + 200}"
        )
        return httpx.Response(200, json={"value": values, "@odata.nextLink": next_link})

    config = GovernedM365Config(
        tenant_id="00000000-0000-4000-8000-000000000001",
        application_client_id="00000000-0000-4000-8000-000000000002",
        managed_identity_client_id="00000000-0000-4000-8000-000000000003",
        drive_id=DRIVE,
        folder_item_id=ROOT,
    )
    intake = GovernedM365Intake(
        config, client=httpx.Client(transport=httpx.MockTransport(handler))
    )
    intake._token = ("test-token", 4102444800)
    return intake, pages


def test_bounded_window_stops_inside_large_folder_before_traversal_limit():
    intake, pages = _intake()
    files = intake.list_files(pending_only=True, max_files=500)
    assert len(files) == 500
    assert files[0]["relative_path"] == "10 Pending Classification/sample-0.txt"
    assert pages == [0, 200, 400]


def test_unbounded_listing_still_enforces_traversal_limit():
    intake, pages = _intake()
    with pytest.raises(M365IntakeError, match="traversal limit"):
        intake.list_files(pending_only=True)
    assert len(pages) == 101


def test_bounded_listing_rejects_untrusted_next_link_before_yield():
    intake, _ = _intake(malicious_next_link=True)
    with pytest.raises(M365IntakeError, match="pagination link"):
        intake.list_files(pending_only=True, max_files=1)
