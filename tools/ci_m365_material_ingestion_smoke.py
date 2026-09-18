#!/usr/bin/env python3
"""Regression checks for governed M365 material persistence."""

from __future__ import annotations

import hashlib
import json
import sqlite3
import tempfile
from datetime import datetime, timezone
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from fastapi import HTTPException
from material_capability import SCHEMA
from salcapa_m365_intake import GovernedM365Document
import salcapa_m365_material_ingestion as ingestion


class App:
    def __init__(self):
        self.routes = {}

    def post(self, path, **kwargs):
        def decorator(function):
            self.routes[path] = function
            return function
        return decorator


class Request:
    role = "System Administrator"


class Storage:
    def __init__(self):
        self.objects = {}

    def put_bytes(self, key, data):
        self.objects[key] = data

    def delete(self, key):
        self.objects.pop(key, None)


class Config:
    drive_id = "b!approved-drive"
    folder_item_id = "01APPROVEDINTAKE"

    @classmethod
    def from_environment(cls):
        return cls()


class Intake:
    def __init__(self, config):
        assert config.drive_id == Config.drive_id

    def read_document(self, item_id, *, access_classification):
        content = b"approved source bytes"
        return GovernedM365Document(
            item_id=item_id,
            name="approved.docx",
            content=content,
            size=len(content),
            mime_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            sha256=hashlib.sha256(content).hexdigest(),
            etag="etag-v7",
            ctag="ctag-v7",
            last_modified="2026-09-18T12:00:00Z",
            source_owner="owner@salus.solutions",
            source_owner_id="owner-id",
            last_modified_by="Approved Owner",
            web_url="https://salussolutions.sharepoint.com/sites/approved/approved.docx",
            access_classification=access_classification,
        )


def main():
    with tempfile.NamedTemporaryFile(suffix=".sqlite") as handle:
        def db():
            conn = sqlite3.connect(handle.name)
            conn.row_factory = sqlite3.Row
            return conn

        conn = db()
        conn.executescript(SCHEMA)
        conn.execute(
            "CREATE TABLE audit_log (id INTEGER PRIMARY KEY AUTOINCREMENT, ts TEXT, "
            "user_name TEXT, action TEXT, entity_type TEXT, entity_id INTEGER, "
            "detail TEXT, tenant_id INTEGER)"
        )
        conn.commit()
        conn.close()

        storage = Storage()
        app = App()
        original_config = ingestion.GovernedM365Config
        original_intake = ingestion.GovernedM365Intake
        ingestion.GovernedM365Config = Config
        ingestion.GovernedM365Intake = Intake
        try:
            ingestion.register_m365_material_ingestion(app, {
                "db": db,
                "storage": storage,
                "scan_bytes": lambda content, name: {"ok": True, "status": "Clean", "detail": "passed"},
                "safe_filename": lambda name: name,
                "now": lambda: "2026-09-18T12:01:00Z",
                "actor": lambda request: "Regression Admin",
                "tenant_id": lambda request: 41,
                "auth_context": lambda request: {"role": request.role, "user_id": 7},
                "RETENTION_DEFAULT_DAYS": 365,
                "_iso_now_dt": lambda: datetime(2026, 9, 18, 12, 1, tzinfo=timezone.utc),
            })
            route = app.routes["/api/integrations/m365/intake/files/{item_id}/ingest"]
            command = ingestion.M365MaterialIngestCommand(
                recording_authority_basis="Approved for governed research intake",
                sensitivity="Restricted",
                purpose_tags=["SalINTEL research"],
            )
            result = route("01APPROVEDFILE", command, Request())
            assert result["processing_status"] == "Ready for Processing"
            assert result["disclosure_status"] == "Salus Internal"
            assert result["immutable_original"] is True
            assert result["source_etag"] == "etag-v7"
            assert len(storage.objects) == 1

            conn = db()
            row = conn.execute("SELECT * FROM materials WHERE id=?", (result["material_id"],)).fetchone()
            locator = json.loads(row["source_locator"])
            provenance = json.loads(row["recording_authority_basis"])
            assert row["tenant_id"] == 41
            assert row["sha256"] == hashlib.sha256(b"approved source bytes").hexdigest()
            assert row["processing_status"] == "Ready for Processing"
            assert row["disclosure_status"] == "Salus Internal"
            assert row["immutable_original"] == 1
            assert locator["drive_id"] == Config.drive_id
            assert locator["folder_item_id"] == Config.folder_item_id
            assert locator["item_id"] == "01APPROVEDFILE"
            assert locator["etag"] == "etag-v7"
            assert provenance["source_owner"] == "owner@salus.solutions"
            assert conn.execute("SELECT COUNT(*) FROM material_events").fetchone()[0] == 1
            assert conn.execute("SELECT COUNT(*) FROM audit_log").fetchone()[0] == 1
            conn.close()

            try:
                route("01APPROVEDFILE", command, Request())
            except HTTPException as exc:
                assert exc.status_code == 409
            else:
                raise AssertionError("An already-ingested M365 version was accepted")

            denied = Request()
            denied.role = "Protected Member"
            try:
                route("01OTHERFILE", command, denied)
            except HTTPException as exc:
                assert exc.status_code == 403
            else:
                raise AssertionError("A non-administrator ingested M365 material")
        finally:
            ingestion.GovernedM365Config = original_config
            ingestion.GovernedM365Intake = original_intake

    print("M365_MATERIAL_INGESTION_PASS")


if __name__ == "__main__":
    main()
