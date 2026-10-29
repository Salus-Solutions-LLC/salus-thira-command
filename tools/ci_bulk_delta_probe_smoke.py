"""Exercise bounded Graph delta capability probe without live content."""

from pathlib import Path
from types import ModuleType, SimpleNamespace
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.modules.setdefault("httpx", ModuleType("httpx"))
azure = ModuleType("azure")
azure.__path__ = []
identity = ModuleType("azure.identity")
identity.ManagedIdentityCredential = object
sys.modules.setdefault("azure", azure)
sys.modules.setdefault("azure.identity", identity)

from tools.live_bulk_delta_probe import EXPECTED_TOP_LEVEL_FOLDERS, census, probe
from salcapa_m365_intake import GRAPH_ROOT


class Response:
    def __init__(self, payload, status_code=200):
        self.payload = payload
        self.status_code = status_code

    def json(self):
        return self.payload


class Client:
    def __init__(self, pages):
        self.pages = pages

    def get(self, url, **kwargs):
        assert url in self.pages, url
        return Response(self.pages[url])


def main():
    drive = "drive00001"
    root_id = "intakeroot01"
    pending_id = "pending00001"
    root = f"{GRAPH_ROOT}/drives/{drive}/items/{root_id}/children"
    delta = f"{GRAPH_ROOT}/drives/{drive}/items/{pending_id}/delta"
    pages = {
        root: {"value": [{"id": pending_id, "name": "10 Pending Classification", "folder": {}}]},
        delta: {"value": [{"id": "item0000001", "file": {}}],
                "@odata.nextLink": delta + "?token=opaque"},
    }
    intake = SimpleNamespace(
        config=SimpleNamespace(drive_id=drive, folder_item_id=root_id,
                               max_file_bytes=100),
        client=Client(pages), _headers=lambda: {},
    )
    assert probe(intake) == (200, "next", True)
    pages[delta]["@odata.nextLink"] = "https://other.example/escape"
    assert probe(intake) == (200, "next", False)
    pages[root]["@odata.nextLink"] = "https://other.example/escape"
    try:
        probe(intake)
    except RuntimeError as exc:
        assert "continuation invalid" in str(exc)
    else:
        raise AssertionError("Cross-origin root continuation was accepted")

    def folder(folder_id, name, parent):
        return {"id": folder_id, "name": name, "size": 0, "folder": {},
                "parentReference": {"id": parent}}

    def file(item_id, name, parent, size):
        return {"id": item_id, "name": name, "size": size,
                "file": {"mimeType": "application/octet-stream"},
                "eTag": f'"{item_id}"',
                "lastModifiedDateTime": "2026-10-29T00:00:00Z",
                "parentReference": {"id": parent}}

    root = f"{GRAPH_ROOT}/drives/{drive}/items/{root_id}/children"
    census_pages = {root: {"value": []}}
    for index, name in enumerate(sorted(EXPECTED_TOP_LEVEL_FOLDERS), start=1):
        child_id = f"folder{index:05d}"
        census_pages[root]["value"].append(folder(child_id, name, root_id))
        endpoint = f"{GRAPH_ROOT}/drives/{drive}/items/{child_id}/children"
        census_pages[endpoint] = {"value": []}
        if name == "90 Processed Intake":
            next_page = endpoint + "?page=2"
            census_pages[endpoint] = {
                "value": [file("file00000001", "one.pdf", child_id, 80)],
                "@odata.nextLink": next_page,
            }
            census_pages[next_page] = {
                "value": [file("file00000002", "two.pptx", child_id, 120)]
            }
    intake.client = Client(census_pages)
    counts = census(intake)
    assert counts == {"files": 2, "folders": 7, "bytes": 200,
                      "oversize": 1, "pages": 9, "complete": 1}
    census_pages[root]["value"][0]["remoteItem"] = {}
    try:
        census(intake)
    except RuntimeError as exc:
        assert "item invalid" in str(exc)
    else:
        raise AssertionError("Boundary shortcut was accepted")
    print("BULK_DELTA_PROBE_PASS")


if __name__ == "__main__":
    main()
