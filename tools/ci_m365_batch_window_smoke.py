"""Regression: a later file remains visible beyond the former 500-file window."""

from pathlib import Path
import sys
import types

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.modules.setdefault("httpx", types.ModuleType("httpx"))
azure = types.ModuleType("azure")
azure.__path__ = []
identity = types.ModuleType("azure.identity")
identity.ManagedIdentityCredential = object
sys.modules.setdefault("azure", azure)
sys.modules.setdefault("azure.identity", identity)

from salcapa_m365_intake import GovernedM365Config, GovernedM365Intake, GRAPH_ROOT


class Response:
    status_code = 200

    def __init__(self, data):
        self.data = data

    def json(self):
        return self.data


class Client:
    def __init__(self, pages):
        self.pages = pages

    def get(self, url, **kwargs):
        assert url in self.pages, url
        return Response(self.pages[url])


def main():
    config = GovernedM365Config(
        tenant_id="tenant0001",
        application_client_id="client0001",
        managed_identity_client_id="managed0001",
        drive_id="drive00001",
        folder_item_id="intakeroot01",
    )
    root = f"{GRAPH_ROOT}/drives/{config.drive_id}/items/intakeroot01/children"
    pending = f"{GRAPH_ROOT}/drives/{config.drive_id}/items/pending00001/children"
    nested = f"{GRAPH_ROOT}/drives/{config.drive_id}/items/nested000001/children"
    pages = {
        root: {"value": [
            {"id": "pending00001", "name": "10 Pending Classification", "folder": {}},
            {"id": "archived0001", "name": "90 Processed Intake", "folder": {}},
        ]},
    }
    for page in range(3):
        url = pending if page == 0 else pending + f"?page={page}"
        rows = []
        end = (page + 1) * 200 if page < 2 else 599
        for index in range(page * 200, end):
            rows.append({
                "id": f"item{index:08d}",
                "name": f"document-{index}.txt",
                "file": {"mimeType": "text/plain"},
                "size": 10,
                "eTag": f"etag-{index}",
                "lastModifiedDateTime": "2026-09-24T00:00:00Z",
            })
        data = {"value": rows}
        if page < 2:
            data["@odata.nextLink"] = pending + f"?page={page + 1}"
        else:
            data["value"].append({"id": "nested000001", "name": "member-folder", "folder": {}})
        pages[url] = data
    pages[nested] = {"value": [{
        "id": "item00000599",
        "name": "document-599.txt",
        "file": {"mimeType": "text/plain"},
        "size": 10,
        "eTag": "etag-599",
        "lastModifiedDateTime": "2026-09-24T00:00:00Z",
    }]}
    intake = GovernedM365Intake(config, credential=object(), client=Client(pages))
    intake._headers = lambda: {}
    listed = intake.list_files(pending_only=True)
    assert len(listed) == 600
    assert listed[-1]["name"] == "document-599.txt"
    assert listed[-1]["relative_path"].endswith(
        "10 Pending Classification/member-folder/document-599.txt"
    )

    archive = f"{GRAPH_ROOT}/drives/{config.drive_id}/items/archived0001/children"
    pages[archive] = {"value": [
        {
            "id": "archive00001", "name": "fixture.txt",
            "file": {"mimeType": "text/plain"}, "size": 7,
            "eTag": "archive-etag",
            "lastModifiedDateTime": "2026-10-07T00:00:00Z",
        },
        {
            "id": "archive00002", "name": "later.txt",
            "file": {"mimeType": "text/plain"}, "size": 8,
            "eTag": "later-etag",
            "lastModifiedDateTime": "2026-10-07T00:00:00Z",
        },
    ]}
    processed = intake.list_files(processed_only=True, max_files=1)
    assert len(processed) == 1
    assert processed[0]["relative_path"] == "90 Processed Intake/fixture.txt"
    assert processed[0]["id"] in intake._listed_items
    assert all("Pending Classification" not in row["relative_path"] for row in processed)

    print("M365_BATCH_WINDOW_PASS")


if __name__ == "__main__":
    main()
