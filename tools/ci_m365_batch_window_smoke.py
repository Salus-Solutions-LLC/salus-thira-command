"""Regression: a later file remains visible beyond the former 500-file window."""

import ast
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
    pages = {
        root: {"value": [
            {"id": "pending00001", "name": "10 Pending Classification", "folder": {}},
            {"id": "archived0001", "name": "90 Processed Intake", "folder": {}},
        ]},
    }
    for page in range(3):
        url = pending if page == 0 else pending + f"?page={page}"
        rows = []
        for index in range(page * 200, (page + 1) * 200):
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
        pages[url] = data
    intake = GovernedM365Intake(config, credential=object(), client=Client(pages))
    intake._headers = lambda: {}
    listed = intake.list_files(pending_only=True)
    assert len(listed) == 600
    assert listed[-1]["name"] == "document-599.txt"

    source = Path(__file__).resolve().parents[1] / "salcapa_knowledge_promotion.py"
    tree = ast.parse(source.read_text(encoding="utf-8"))
    calls = [
        node for node in ast.walk(tree)
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Attribute)
        and node.func.attr == "list_files"
        and any(
            kw.arg == "pending_only"
            and isinstance(kw.value, ast.Constant)
            and kw.value.value is True
            for kw in node.keywords
        )
    ]
    assert len(calls) == 1
    assert not any(kw.arg == "max_files" for kw in calls[0].keywords)
    print("M365_BATCH_WINDOW_PASS")


if __name__ == "__main__":
    main()
