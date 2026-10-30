"""Regression coverage for metadata-only governed-hold reconciliation."""

from __future__ import annotations

import os
import sqlite3
import sys
import tempfile
from types import SimpleNamespace

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
from tools import live_knowledge_hold_reconcile as hold


class Response:
    status_code = 200

    def __init__(self, value):
        self.value = value

    def json(self):
        return {"value": self.value}


class Client:
    def __init__(self):
        self.version = 1
        self.include_second = True
        self.urls: list[str] = []
        self.root = "root-12345678"
        self.folders = {
            name: f"folder-{index:08d}" for index, name in enumerate(
                sorted(hold.SOURCE_AREAS), start=1
            )
        }

    def get(self, url, **kwargs):
        self.urls.append(url)
        folder_id = url.split("/items/", 1)[1].split("/children", 1)[0]
        if folder_id == self.root:
            return Response([
                {"id": item_id, "name": name, "folder": {},
                 "parentReference": {"id": self.root}}
                for name, item_id in self.folders.items()
            ])
        if folder_id != self.folders[hold.SOURCE_AREA]:
            return Response([])
        files = [{
            "id": "held-file-0001", "name": "one.docx", "file": {}, "size": 10,
            "eTag": f'"v{self.version}"',
            "lastModifiedDateTime": "2026-10-29T00:00:00Z",
            "createdBy": {"user": {"displayName": "Owner", "id": "owner-1"}},
            "webUrl": "https://salus.sharepoint.com/one.docx",
            "parentReference": {"id": folder_id},
        }]
        if self.include_second:
            files.append({
                "id": "held-file-0002", "name": "two.pdf", "file": {}, "size": 20,
                "eTag": '"v1"', "lastModifiedDateTime": "2026-10-29T00:00:00Z",
                "createdBy": {"user": {"displayName": "Owner", "id": "owner-1"}},
                "webUrl": "https://salus.sharepoint.com/two.pdf",
                "parentReference": {"id": folder_id},
            })
        return Response(files)


def check() -> None:
    with tempfile.TemporaryDirectory() as directory:
        path = os.path.join(directory, "holds.sqlite")

        def connect():
            conn = sqlite3.connect(path)
            conn.row_factory = sqlite3.Row
            return conn

        client = Client()
        intake = SimpleNamespace(
            config=SimpleNamespace(drive_id="drive-12345678", folder_item_id=client.root),
            client=client,
            _headers=lambda: {},
            _identity=lambda value: (
                str((value or {}).get("user", {}).get("displayName", "")),
                str((value or {}).get("user", {}).get("id", "")),
            ),
            _trusted_source_url=lambda value: str(value or ""),
        )
        original = hold.EXPECTED_HOLD_FILES
        try:
            hold.EXPECTED_HOLD_FILES = 2
            first = hold.reconcile(intake, connect)
            assert first["inserted"] == 2 and first["active_holds"] == 2, first
            assert first["events_added"] == 2 and first["content_downloads"] == 0, first
            assert first["hold_reconciliation_complete"] == 1, first
            second = hold.reconcile(intake, connect)
            assert second["refreshed"] == 2 and second["events_added"] == 0, second
            client.version = 2
            client.include_second = False
            hold.EXPECTED_HOLD_FILES = 1
            third = hold.reconcile(intake, connect)
            assert third["changed"] == 1 and third["removed"] == 1, third
            assert third["active_holds"] == 1 and third["events_added"] == 2, third
        finally:
            hold.EXPECTED_HOLD_FILES = original
        conn = connect()
        active = conn.execute(
            "SELECT status,research_disposition,teaching_disposition,citation_disposition "
            "FROM m365_knowledge_holds WHERE source_item_id='held-file-0001'"
        ).fetchone()
        removed = conn.execute(
            "SELECT status FROM m365_knowledge_holds WHERE source_item_id='held-file-0002'"
        ).fetchone()
        event_count = conn.execute(
            "SELECT COUNT(*) FROM m365_knowledge_hold_events"
        ).fetchone()[0]
        conn.close()
        assert tuple(active) == (
            "Governed Hold", hold.REVIEW_REQUIRED, hold.REVIEW_REQUIRED,
            hold.REVIEW_REQUIRED,
        ), active
        assert removed["status"] == "Source Removed", removed
        assert event_count == 4, event_count
        assert all("/content" not in url for url in client.urls), client.urls
    print("KNOWLEDGE_HOLD_RECONCILE_PASS")


if __name__ == "__main__":
    check()
