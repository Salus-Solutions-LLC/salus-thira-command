#!/usr/bin/env python3
"""End-to-end regression from governed M365 capture through human-reviewed extraction."""

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

from material_capability import SCHEMA as MATERIAL_SCHEMA
from salcapa_m365_intake import GovernedM365Document
import salcapa_m365_material_ingestion as m365
from salintel_material_index import MaterialIndexIn, register_salintel_material_index
from salthira_material_evidence_routing import (
    SalTHIRAEvidenceRouteIn,
    register_salthira_material_evidence_routing,
)
from salcapa_material_processing import (
    DerivativeReviewIn,
    MaterialProcessIn,
    register_salcapa_material_processing,
)


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
    def __init__(self, user, role="System Administrator"):
        self.user = user
        self.role = role


class Storage:
    def __init__(self):
        self.objects = {}

    def put_bytes(self, key, data):
        self.objects[key] = data

    def get_bytes(self, key):
        return self.objects[key]

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
        assert config.folder_item_id == Config.folder_item_id

    def read_document(self, item_id, *, access_classification):
        content = b"Approved source statement\nSecond governed line\n"
        return GovernedM365Document(
            item_id=item_id,
            name="approved.txt",
            content=content,
            size=len(content),
            mime_type="text/plain",
            sha256=hashlib.sha256(content).hexdigest(),
            etag="etag-v8",
            ctag="ctag-v8",
            last_modified="2026-09-18T22:00:00Z",
            source_owner="owner@salus.solutions",
            source_owner_id="owner-id",
            last_modified_by="Approved Owner",
            web_url="https://salussolutions.sharepoint.com/sites/approved/approved.txt",
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
        conn.executescript(
            """
            CREATE TABLE assessments (
              id INTEGER PRIMARY KEY, tenant_id INTEGER NOT NULL, name TEXT NOT NULL
            );
            CREATE TABLE capabilities (
              id INTEGER PRIMARY KEY, assessment_id INTEGER NOT NULL
            );
            CREATE TABLE scenarios (
              id INTEGER PRIMARY KEY, assessment_id INTEGER NOT NULL
            );
            CREATE TABLE evidence (
              id INTEGER PRIMARY KEY AUTOINCREMENT,
              assessment_id INTEGER NOT NULL,
              capability_id INTEGER,
              scenario_id INTEGER,
              title TEXT NOT NULL,
              evidence_type TEXT NOT NULL,
              source TEXT NOT NULL,
              owner TEXT NOT NULL,
              evidence_date TEXT NOT NULL,
              reliability TEXT NOT NULL,
              verification_status TEXT NOT NULL,
              sensitivity TEXT NOT NULL,
              notes TEXT NOT NULL,
              created_at TEXT NOT NULL,
              updated_at TEXT NOT NULL
            );
            """
        )
        conn.execute("INSERT INTO assessments(id,tenant_id,name) VALUES(?,?,?)", (900, 41, "Governed Assessment"))
        conn.execute("INSERT INTO capabilities(id,assessment_id) VALUES(?,?)", (901, 900))
        conn.execute("INSERT INTO scenarios(id,assessment_id) VALUES(?,?)", (902, 900))
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
            "scan_bytes": lambda content, name: {"ok": True, "status": "Clean", "detail": "passed"},
            "safe_filename": lambda name: name,
            "now": lambda: "2026-09-18T22:01:00Z",
            "actor": lambda request: request.user,
            "role": lambda request: request.role,
            "tenant_id": lambda request: 41,
            "auth_context": lambda request: {"role": request.role, "user_id": 7},
            "RETENTION_DEFAULT_DAYS": 365,
            "_iso_now_dt": lambda: datetime(2026, 9, 18, 22, 1, tzinfo=timezone.utc),
            "require": lambda request, permission: None,
            "require_sensitivity": lambda request, sensitivity: None,
            "protected_member_request": lambda request: False,
            "require_salus_component_authority": lambda request, component: None,
            "security_event": lambda *args: None,
            "clearance_level": lambda request: 3,
            "SENSITIVITY_LEVELS": {"Standard": 0, "Restricted": 1, "Sensitive": 2, "Highly Sensitive": 3},
            "collect_tenant_records": lambda conn, tenant: {},
            "validate_records": lambda records, tenant=None: [],
            "replace_tenant_records": lambda conn, tenant, records: None,
            "assessment_row_for_request": lambda request, assessment_id: {"id": assessment_id, "tenant_id": 41},
            "snapshot_entity": lambda *args: None,
        }

        original_config = m365.GovernedM365Config
        original_intake = m365.GovernedM365Intake
        m365.GovernedM365Config = Config
        m365.GovernedM365Intake = Intake
        try:
            register_salcapa_material_processing(app, core)
            register_salintel_material_index(app, core)
            register_salthira_material_evidence_routing(app, core)
            m365.register_m365_material_ingestion(app, core)

            ingest = app.routes[("POST", "/api/integrations/m365/intake/files/{item_id}/ingest")]
            captured = ingest(
                "01APPROVEDTEXT",
                m365.M365MaterialIngestCommand(
                    recording_authority_basis="Approved for governed research extraction",
                    sensitivity="Restricted",
                ),
                Request("Capture Administrator"),
            )
            assert captured["processing_endpoint"] == (
                f"/api/materials/{captured['material_id']}/safe-text-processing"
            )
            assert captured["human_review_required"] is True
            assert captured["indexing_status"] == "Not Indexed"
            assert captured["finding_status"] == "None Created"

            process = app.routes[("POST", "/api/materials/{material_id}/safe-text-processing")]
            processed = process(
                captured["material_id"],
                MaterialProcessIn(reason="Prepare source text for independent human review"),
                Request("Processing Analyst"),
            )
            derivative = processed["derivative"]
            assert derivative["source_material_id"] == captured["material_id"]
            assert derivative["source_sha256"] == captured["sha256"]
            assert derivative["review_status"] == "Awaiting Human Review"
            assert derivative["confidence_status"] == "Derived — Unverified"
            assert "Approved source statement" in derivative["content_preview"]

            conn = db()
            material = conn.execute(
                "SELECT * FROM materials WHERE id=?", (captured["material_id"],)
            ).fetchone()
            assert material["processing_status"] == "Ready for Human Review"
            assert material["immutable_original"] == 1
            assert conn.execute(
                "SELECT COUNT(*) FROM material_derivative_events WHERE derivative_id=?",
                (derivative["id"],),
            ).fetchone()[0] == 1
            conn.close()

            review = app.routes[(
                "POST", "/api/material-processing/derivatives/{derivative_id}/review"
            )]
            reviewed = review(
                derivative["id"],
                DerivativeReviewIn(
                    status="Human Reviewed",
                    reason="Compared the derived representation to the governed source.",
                ),
                Request("Independent Reviewer"),
            )
            assert reviewed["review_status"] == "Human Reviewed"
            assert reviewed["reviewed_by"] == "Independent Reviewer"

            index_route = app.routes[(
                "POST", "/api/salintel/research/material-derivatives/{derivative_id}/index"
            )]
            indexed = index_route(
                derivative["id"],
                MaterialIndexIn(
                    basis="Approved human-reviewed source aid for tenant-scoped research."
                ),
                Request("Research Indexer"),
            )
            assert indexed["source_material_id"] == captured["material_id"]
            assert indexed["source_sha256"] == captured["sha256"]
            assert indexed["content_sha256"] == derivative["content_sha256"]
            assert indexed["evidence_status"] == "Human Reviewed Source Aid"
            assert indexed["finding_status"] == "None Created"
            assert indexed["salthira_routing_status"] == "Not Routed"
            assert indexed["disclosure_status"] == "Salus Internal"

            search = app.routes[("GET", "/api/salintel/research/material-index")]
            results = search(Request("Research Analyst"), q="governed line", limit=10)
            assert len(results["items"]) == 1
            result = results["items"][0]
            assert result["derivative_id"] == derivative["id"]
            assert result["source_attribution"]["source_sha256"] == captured["sha256"]
            locator = json.loads(result["source_attribution"]["source_locator"])
            assert locator["item_id"] == "01APPROVEDTEXT"
            assert result["finding_status"] == "None Created"
            assert result["salthira_routing_status"] == "Not Routed"

            route_evidence = app.routes[(
                "POST", "/api/salthira/material-index/{index_id}/route-evidence"
            )]
            routed = route_evidence(
                indexed["index_id"],
                SalTHIRAEvidenceRouteIn(
                    assessment_id=900,
                    capability_id=901,
                    scenario_id=902,
                    title="Approved M365 source aid",
                    reliability="Medium",
                    routing_basis=(
                        "Authorized for SalTHIRA evidence review; no finding or "
                        "risk conclusion is authorized."
                    ),
                ),
                Request("SalTHIRA Evidence Router"),
            )
            assert routed["assessment_id"] == 900
            assert routed["evidence_status"] == "Pending SalTHIRA Evidence Verification"
            assert routed["verification_status"] == "Pending"
            assert routed["finding_status"] == "None Created"
            assert routed["risk_conclusion_status"] == "None Created"
            assert routed["recommendation_status"] == "None Created"
            assert routed["disclosure_status"] == "Salus Internal"

            conn = db()
            evidence = conn.execute(
                "SELECT * FROM evidence WHERE id=?", (routed["evidence_id"],)
            ).fetchone()
            assert evidence["assessment_id"] == 900
            assert evidence["capability_id"] == 901
            assert evidence["scenario_id"] == 902
            assert evidence["verification_status"] == "Pending"
            assert evidence["sensitivity"] == "Restricted"
            assert "does not establish source truth" in evidence["notes"]
            route = conn.execute(
                "SELECT * FROM salthira_material_evidence_routes WHERE id=?",
                (routed["route_id"],),
            ).fetchone()
            attribution = json.loads(route["attribution_json"])
            assert attribution["source_sha256"] == captured["sha256"]
            assert attribution["content_sha256"] == derivative["content_sha256"]
            assert route["routed_by"] == "SalTHIRA Evidence Router"
            events = [
                row[0] for row in conn.execute(
                    "SELECT event_type FROM material_derivative_events "
                    "WHERE derivative_id=? ORDER BY id", (derivative["id"],)
                )
            ]
            assert events == ["CREATED", "HUMAN_REVIEW_RECORDED"]
            assert conn.execute(
                "SELECT COUNT(*) FROM audit_log WHERE action='MATERIAL_DERIVATIVE_REVIEWED'"
            ).fetchone()[0] == 1
            conn.close()
        finally:
            m365.GovernedM365Config = original_config
            m365.GovernedM365Intake = original_intake

    print("SALTHIRA_MATERIAL_EVIDENCE_ROUTING_PASS")


if __name__ == "__main__":
    main()
