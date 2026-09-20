#!/usr/bin/env python3
"""Regression checks for governed M365 source change and reprocessing."""

from __future__ import annotations

import hashlib
import json
import sqlite3
import tempfile
from datetime import datetime, timezone
from pathlib import Path
import sys
import types

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from fastapi import HTTPException
from material_capability import SCHEMA as MATERIAL_SCHEMA
from salcapa_m365_intake import GovernedM365Document
import salcapa_m365_material_ingestion as ingestion
import salcapa_m365_source_change as changes


class App:
    def __init__(self):
        self.routes = {}
        self.state = types.SimpleNamespace()

    def _route(self, method, path):
        def decorator(function):
            self.routes[(method, path)] = function
            return function
        return decorator

    def post(self, path, **kwargs):
        return self._route("POST", path)

    def get(self, path, **kwargs):
        return self._route("GET", path)


class Request:
    role = "System Administrator"
    user = "Source Control Administrator"


class Storage:
    def __init__(self):
        self.objects = {}

    def put_bytes(self, key, value):
        self.objects[key] = value

    def delete(self, key):
        self.objects.pop(key, None)


class Config:
    drive_id = "b!approved-drive"
    folder_item_id = "01APPROVEDINTAKE"

    @classmethod
    def from_environment(cls):
        return cls()


class Intake:
    version = 1
    include_new = False
    visible_versioned = True

    def __init__(self, config):
        assert config.folder_item_id == Config.folder_item_id

    @classmethod
    def metadata(cls):
        return {
            "id": "01VERSIONEDFILE",
            "name": "versioned.txt",
            "size": len(cls.content()),
            "mime_type": "text/plain",
            "last_modified": f"2026-09-19T0{cls.version}:00:00Z",
            "etag": f"etag-v{cls.version}",
            "ctag": f"ctag-v{cls.version}",
            "source_owner": "owner@salus.solutions",
            "source_owner_id": "owner-id",
            "last_modified_by": "Approved Owner",
            "web_url": "https://salussolutions.sharepoint.com/sites/approved/versioned.txt",
        }

    @classmethod
    def content(cls):
        return f"Approved source version {cls.version}\n".encode()

    def list_files(self):
        items = [self.metadata()] if self.visible_versioned else []
        if self.include_new:
            items.append({
                "id": "01NEWFILE",
                "name": "new.pdf",
                "size": 321,
                "mime_type": "application/pdf",
                "last_modified": "2026-09-19T09:00:00Z",
                "etag": "etag-new",
                "ctag": "ctag-new",
                "source_owner": "owner@salus.solutions",
                "source_owner_id": "owner-id",
                "last_modified_by": "Approved Owner",
                "web_url": "https://salussolutions.sharepoint.com/sites/approved/new.pdf",
                "relative_path": "Operations/Nested/new.pdf",
            })
        return items

    def read_document(self, item_id, *, access_classification):
        item = self.metadata()
        assert item_id == item["id"]
        content = self.content()
        return GovernedM365Document(
            item_id=item_id,
            name=item["name"],
            content=content,
            size=len(content),
            mime_type=item["mime_type"],
            sha256=hashlib.sha256(content).hexdigest(),
            etag=item["etag"],
            ctag=item["ctag"],
            last_modified=item["last_modified"],
            source_owner=item["source_owner"],
            source_owner_id=item["source_owner_id"],
            last_modified_by=item["last_modified_by"],
            web_url=item["web_url"],
            access_classification=access_classification,
        )


def main():
    with tempfile.NamedTemporaryFile(suffix=".sqlite") as handle:
        def db():
            conn = sqlite3.connect(handle.name)
            conn.row_factory = sqlite3.Row
            return conn

        conn = db()
        conn.executescript(MATERIAL_SCHEMA)
        conn.execute(
            "CREATE TABLE audit_log (id INTEGER PRIMARY KEY AUTOINCREMENT, ts TEXT, "
            "user_name TEXT, action TEXT, entity_type TEXT, entity_id INTEGER, "
            "detail TEXT, tenant_id INTEGER)"
        )
        conn.commit()
        conn.close()

        storage = Storage()
        app = App()
        core = {
            "db": db,
            "storage": storage,
            "scan_bytes": lambda content, name: {
                "ok": True, "status": "Clean", "detail": "passed",
            },
            "safe_filename": lambda name: name,
            "now": lambda: "2026-09-19T10:00:00Z",
            "actor": lambda request: request.user,
            "role": lambda request: request.role,
            "tenant_id": lambda request: 41,
            "auth_context": lambda request: {"role": request.role, "user_id": 7},
            "require_sensitivity": lambda request, sensitivity: None,
            "security_event": lambda *args: None,
            "RETENTION_DEFAULT_DAYS": 365,
            "_iso_now_dt": lambda: datetime(2026, 9, 19, 10, tzinfo=timezone.utc),
        }
        originals = (
            ingestion.GovernedM365Config,
            ingestion.GovernedM365Intake,
            changes.GovernedM365Config,
            changes.GovernedM365Intake,
        )
        ingestion.GovernedM365Config = Config
        ingestion.GovernedM365Intake = Intake
        changes.GovernedM365Config = Config
        changes.GovernedM365Intake = Intake
        try:
            ingestion.register_m365_material_ingestion(app, core)
            changes.register_m365_source_change_control(app, core)
            ingest = app.routes[(
                "POST", "/api/integrations/m365/intake/files/{item_id}/ingest"
            )]
            command = ingestion.M365MaterialIngestCommand(
                recording_authority_basis="Approved initial governed capture",
                sensitivity="Restricted",
            )
            first = ingest("01VERSIONEDFILE", command, Request())
            assert first["source_version_status"] == "Initial Version"

            check = app.routes[(
                "POST",
                "/api/integrations/m365/intake/materials/{material_id}/check-source-version",
            )]
            unchanged = check(first["material_id"], Request())
            assert unchanged["status"] == "Unchanged"
            assert unchanged["reprocessing_required"] is False

            reconcile = app.routes[(
                "POST",
                "/api/integrations/m365/intake/reconcile-source-versions",
            )]
            baseline = reconcile(Request())
            assert baseline["scope"] == "Authorized folder and all nested folders"
            assert baseline["counts"] == {
                "New": 0, "Unchanged": 1, "Changed": 0, "Missing": 0,
            }
            assert baseline["automatic_ingestion"] is False
            assert baseline["automatic_reprocessing"] is False

            Intake.include_new = True
            with_new = reconcile(Request())
            assert with_new["counts"]["New"] == 1
            assert with_new["counts"]["Unchanged"] == 1
            new_item = next(item for item in with_new["items"] if item["status"] == "New")
            assert new_item["relative_path"] == "Operations/Nested/new.pdf"
            assert new_item["human_review_required"] is True

            Intake.version = 2
            changed_tree = reconcile(Request())
            assert changed_tree["counts"]["Changed"] == 1
            assert changed_tree["counts"]["New"] == 1
            assert next(
                item for item in changed_tree["items"] if item["item_id"] == "01VERSIONEDFILE"
            )["automatic_reprocessing"] is False

            Intake.visible_versioned = False
            missing_tree = reconcile(Request())
            assert missing_tree["counts"]["Missing"] == 1
            assert missing_tree["counts"]["New"] == 1

            batch_decide = app.routes[(
                "POST",
                "/api/integrations/m365/intake/review-queue/batch-decision",
            )]
            decision = batch_decide(
                changes.M365BatchReviewDecisionIn(
                    item_ids=["01VERSIONEDFILE", "01NEWFILE"],
                    decision="Approve",
                    reason="Administrator approved these current reconciliation items.",
                ),
                Request(),
            )
            assert decision["count"] == 2
            assert decision["batch_limit"] == 50
            assert decision["automatic_ingestion"] is False
            assert decision["automatic_reprocessing"] is False

            reviewed = reconcile(Request())
            assert {
                item["review_decision"] for item in reviewed["items"]
                if item["item_id"] in {"01VERSIONEDFILE", "01NEWFILE"}
            } == {"Approve"}

            denied = Request()
            denied.role = "Protected Member"
            try:
                batch_decide(
                    changes.M365BatchReviewDecisionIn(
                        item_ids=["01NEWFILE"],
                        decision="Defer",
                        reason="Unauthorized role test.",
                    ),
                    denied,
                )
            except HTTPException as exc:
                assert exc.status_code == 403
            else:
                raise AssertionError("A non-administrator recorded a batch review decision")

            try:
                changes.M365BatchReviewDecisionIn(
                    item_ids=[f"ITEM-{index}" for index in range(51)],
                    decision="Approve",
                    reason="Bounded batch test.",
                )
            except Exception as exc:
                assert "50" in str(exc)
            else:
                raise AssertionError("A review batch exceeded the 50-item limit")

            Intake.visible_versioned = True
            stale_review = reconcile(Request())
            versioned = next(
                item for item in stale_review["items"]
                if item["item_id"] == "01VERSIONEDFILE"
            )
            assert versioned["status"] == "Changed"
            assert versioned["review_decision"] == "Pending"

            changed = check(first["material_id"], Request())
            assert changed["status"] == "Changed"
            assert changed["recorded_etag"] == "etag-v1"
            assert changed["observed_etag"] == "etag-v2"
            assert changed["reprocessing_required"] is True

            try:
                ingest(
                    "01VERSIONEDFILE",
                    ingestion.M365MaterialIngestCommand(
                        recording_authority_basis="Unauthorized changed capture",
                        sensitivity="Restricted",
                    ),
                    Request(),
                )
            except HTTPException as exc:
                assert exc.status_code == 409
                assert "authorization" in exc.detail.lower()
            else:
                raise AssertionError("A changed source was captured without authorization")

            authorize = app.routes[(
                "POST",
                "/api/integrations/m365/intake/source-checks/{check_id}/authorize-reprocessing",
            )]
            authorization = authorize(
                changed["check_id"],
                changes.M365ReprocessingAuthorizationIn(
                    reason="Approved source update requires a new immutable version."
                ),
                Request(),
            )
            assert authorization["status"] == "Authorized"
            assert authorization["automatic_processing"] is False
            assert authorization["human_review_required"] is True

            second = ingest(
                "01VERSIONEDFILE",
                ingestion.M365MaterialIngestCommand(
                    recording_authority_basis="Approved governed version update",
                    sensitivity="Restricted",
                    supersedes_material_id=first["material_id"],
                    reprocessing_authorization_id=authorization["authorization_id"],
                ),
                Request(),
            )
            assert second["source_etag"] == "etag-v2"
            assert second["supersedes_material_id"] == first["material_id"]
            assert second["source_version_status"] == "Authorized New Version"
            assert second["human_review_required"] is True
            assert second["indexing_status"] == "Not Indexed"
            assert second["finding_status"] == "None Created"

            conn = db()
            row = conn.execute(
                "SELECT * FROM materials WHERE id=?", (second["material_id"],)
            ).fetchone()
            assert row["parent_material_id"] == first["material_id"]
            assert row["derivation_type"] == "M365 Source Version"
            auth = conn.execute(
                "SELECT * FROM m365_material_reprocessing_authorizations WHERE id=?",
                (authorization["authorization_id"],),
            ).fetchone()
            assert auth["status"] == "Consumed"
            assert auth["new_material_id"] == second["material_id"]
            events = [
                event[0] for event in conn.execute(
                    "SELECT event_type FROM material_events WHERE material_id=? ORDER BY id",
                    (first["material_id"],),
                )
            ]
            assert "M365_SOURCE_VERSION_SUPERSEDED" in events
            conn.close()

            latest = check(second["material_id"], Request())
            assert latest["status"] == "Unchanged"
        finally:
            (
                ingestion.GovernedM365Config,
                ingestion.GovernedM365Intake,
                changes.GovernedM365Config,
                changes.GovernedM365Intake,
            ) = originals

    print("M365_SOURCE_CHANGE_REPROCESSING_PASS")


if __name__ == "__main__":
    main()
