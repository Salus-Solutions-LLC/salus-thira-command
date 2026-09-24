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

from tools.live_bulk_delta_probe import probe
from salcapa_m365_intake import GRAPH_ROOT


class Response:
    status_code = 200

    def __init__(self, payload):
        self.payload = payload

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
        config=SimpleNamespace(drive_id=drive, folder_item_id=root_id),
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
    print("BULK_DELTA_PROBE_PASS")


if __name__ == "__main__":
    main()
