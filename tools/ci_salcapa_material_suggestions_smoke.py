#!/usr/bin/env python3
"""Acceptance checks for governed source suggestions and duplicate review."""

import json
import os
import sys
import tempfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
WORKSPACE = tempfile.TemporaryDirectory()
os.environ.setdefault("SALUS_DB_BACKEND", "sqlite")
os.environ.setdefault("SALUS_DB_PATH", str(Path(WORKSPACE.name) / "material-suggestions.db"))
os.environ.setdefault("SALUS_BACKUP_DIR", str(Path(WORKSPACE.name) / "backups"))
os.environ.setdefault("SALUS_LOCAL_STORAGE_DIR", str(Path(WORKSPACE.name) / "attachments"))
os.environ.setdefault("SALUS_AUTH_MODE", "prototype")
os.environ.setdefault("SALUS_SEED_DEMO", "1")
sys.path.insert(0, str(ROOT))

from fastapi.testclient import TestClient

import app as core
from salcapa_material_processing import register_salcapa_material_processing
from salcapa_material_suggestions import register_salcapa_material_suggestions


PROCESSOR = {
    "X-Salus-Tenant": "6", "X-Salus-Role": "Assessment Director",
    "X-Salus-User": "Processing Lead",
}
REPRESENTATION_REVIEWER = {**PROCESSOR, "X-Salus-User": "Representation Reviewer"}
SUGGESTION_REQUESTER = {**PROCESSOR, "X-Salus-User": "Suggestion Requester"}
SUGGESTION_REVIEWER = {**PROCESSOR, "X-Salus-User": "Suggestion Reviewer"}
MEMBER = {
    "X-Salus-Tenant": "6", "X-Salus-Role": "Contributor",
    "X-Salus-User": "Protected Member Contributor",
}
OTHER_TENANT = {**PROCESSOR, "X-Salus-Tenant": "7", "X-Salus-User": "Other Tenant Lead"}


def upload_process_review(client: TestClient, name: str, content: bytes) -> tuple[int, int]:
    uploaded = client.post(
        "/api/materials/upload", headers=PROCESSOR,
        data={
            "title": name, "material_kind": "Text",
            "source_origin": "Authorized fictional demonstration submission",
            "sensitivity": "Restricted",
            "purpose_tags": json.dumps(["Source review", "Demonstration"]),
        },
        files={"file": (f"{name.casefold().replace(' ', '-')}.txt", content, "text/plain")},
    )
    assert uploaded.status_code == 200, uploaded.text
    material_id = int(uploaded.json()["id"])
    processed = client.post(
        f"/api/materials/{material_id}/safe-text-processing", headers=PROCESSOR,
        json={"reason": "Prepare an inert representation for independent review."},
    )
    assert processed.status_code == 200, processed.text
    derivative_id = int(processed.json()["derivative"]["id"])
    reviewed = client.post(
        f"/api/material-processing/derivatives/{derivative_id}/review",
        headers=REPRESENTATION_REVIEWER,
        json={
            "status": "Human Reviewed",
            "reason": "Compared line by line with the unchanged source; this confirms the representation only.",
        },
    )
    assert reviewed.status_code == 200, reviewed.text
    return material_id, derivative_id


def prepare(client: TestClient, derivative_id: int):
    result = client.post(
        f"/api/material-processing/derivatives/{derivative_id}/review-suggestions",
        headers=SUGGESTION_REQUESTER,
        json={"reason": "Prepare bounded source-review aids for independent human review."},
    )
    assert result.status_code == 200, result.text
    return result.json()


def main() -> None:
    register_salcapa_material_processing(core.app, core.__dict__)
    register_salcapa_material_suggestions(core.app, core.__dict__)
    client = TestClient(core.app)
    conn = core.db()
    conn.execute(
        "INSERT INTO tenants(id,name,slug,status,created_at) VALUES(?,?,?,?,?) ON CONFLICT(id) DO NOTHING",
        (6, "Source Review Test Tenant", "source-review-test", "Active", core.now()),
    )
    conn.execute(
        "INSERT INTO tenants(id,name,slug,status,created_at) VALUES(?,?,?,?,?) ON CONFLICT(id) DO NOTHING",
        (7, "Other Source Review Test Tenant", "source-review-other", "Active", core.now()),
    )
    if not conn.execute("SELECT id FROM assessments WHERE tenant_id=? LIMIT 1", (6,)).fetchone():
        conn.execute(
            "INSERT INTO assessments(name,organization,tenant_id,created_at,updated_at) VALUES(?,?,?,?,?)",
            ("Fictional source review assessment", "Demonstration organization", 6, core.now(), core.now()),
        )
    conn.commit()
    conn.close()

    person = client.post(
        "/api/material-suggestions/references", headers=PROCESSOR,
        json={
            "reference_type": "Person", "display_name": "Jordan Example",
            "aliases": ["J. Example"], "target_type": "personnel_assessment_subject",
            "target_id": 42, "sensitivity": "Restricted",
        },
    )
    assert person.status_code == 200, person.text
    facility = client.post(
        "/api/material-suggestions/references", headers=PROCESSOR,
        json={
            "reference_type": "Facility", "display_name": "Fictional Harbor Facility",
            "aliases": ["Harbor Facility"], "target_type": "facility",
            "target_id": 17, "sensitivity": "Restricted",
        },
    )
    assert facility.status_code == 200, facility.text
    assert client.get("/api/material-suggestions/references", headers=MEMBER).status_code == 403
    assert client.get("/api/material-suggestions/references", headers=OTHER_TENANT).json()["items"] == []

    first_text = (
        b"Jordan Example will review Harbor Facility on 09/10/2026 at 21:30 CDT. "
        b"Generator endurance needs field validation. Alternate fuel vendor remains unconfirmed. "
        b"The continuity team will compare the authorized plan, current contacts, and facility records."
    )
    _, first_derivative = upload_process_review(client, "Fictional continuity note one", first_text)
    first = prepare(client, first_derivative)
    assert first["job"]["status"] == "Completed" and not first["idempotent_reuse"]
    by_type = {}
    for suggestion in first["suggestions"]:
        by_type.setdefault(suggestion["suggestion_type"], []).append(suggestion)
        assert suggestion["confidence_status"] == "Derived — Unverified"
        assert suggestion["review_status"] == "Awaiting Human Review"
        assert "does not establish" in suggestion["authority_note"]
    assert {"Entity", "Location", "Date", "Time"}.issubset(by_type)
    ambiguous = next(item for item in by_type["Date"] if item["proposed_value"] == "Ambiguous numeric date")
    assert ambiguous["alternatives"] == ["09 October 2026", "10 September 2026"]
    assert by_type["Time"][0]["proposed_value"] == "21:30"
    assert by_type["Entity"][0]["proposed_value"] == "Jordan Example"
    assert by_type["Location"][0]["proposed_value"] == "Fictional Harbor Facility"

    reused = prepare(client, first_derivative)
    assert reused["idempotent_reuse"] and reused["job"]["id"] == first["job"]["id"]
    assert len(reused["suggestions"]) == len(first["suggestions"])

    unreviewed_upload = client.post(
        "/api/materials/upload", headers=PROCESSOR,
        data={"title": "Awaiting representation review", "material_kind": "Text", "source_origin": "Demonstration"},
        files={"file": ("unreviewed.txt", b"Harbor Facility at 21:30", "text/plain")},
    )
    unreviewed_material = int(unreviewed_upload.json()["id"])
    unreviewed_process = client.post(
        f"/api/materials/{unreviewed_material}/safe-text-processing", headers=PROCESSOR,
        json={"reason": "Prepare for representation review."},
    )
    unreviewed_derivative = int(unreviewed_process.json()["derivative"]["id"])
    too_early = client.post(
        f"/api/material-processing/derivatives/{unreviewed_derivative}/review-suggestions",
        headers=SUGGESTION_REQUESTER, json={"reason": "Attempt before representation review."},
    )
    assert too_early.status_code == 409, too_early.text

    second_text = first_text + b" Follow-up pending."
    _, second_derivative = upload_process_review(client, "Fictional continuity note two", second_text)
    second = prepare(client, second_derivative)
    near = next(item for item in second["comparisons"] if item["comparison_class"] == "Near-duplicate text suggestion")
    assert 6000 <= near["similarity_basis_points"] < 10000
    assert "does not prove" in near["authority_note"]

    _, exact_derivative = upload_process_review(client, "Fictional continuity note exact copy", first_text)
    exact = prepare(client, exact_derivative)
    exact_match = next(item for item in exact["comparisons"] if item["comparison_class"] == "Exact source-byte match")
    assert exact_match["similarity_basis_points"] == 10000

    suggestion_id = int(ambiguous["id"])
    self_review = client.post(
        f"/api/material-suggestions/{suggestion_id}/review", headers=SUGGESTION_REQUESTER,
        json={"status": "Human Reviewed", "reason": "Requester cannot review their own aid."},
    )
    assert self_review.status_code == 409, self_review.text
    missing_correction = client.post(
        f"/api/material-suggestions/{suggestion_id}/review", headers=SUGGESTION_REVIEWER,
        json={"status": "Corrected", "reason": "Context resolves the date order."},
    )
    assert missing_correction.status_code == 422, missing_correction.text
    corrected = client.post(
        f"/api/material-suggestions/{suggestion_id}/review", headers=SUGGESTION_REVIEWER,
        json={
            "status": "Corrected", "reason": "The authorized schedule resolves the date order.",
            "corrected_value": "09 October 2026",
        },
    )
    assert corrected.status_code == 200, corrected.text
    assert corrected.json()["proposed_value"] == "Ambiguous numeric date"
    assert corrected.json()["current_value"] == "09 October 2026"
    assert corrected.json()["review_status"] == "Corrected"

    proposed = client.post(
        f"/api/material-suggestions/{suggestion_id}/governed-link-proposals",
        headers=SUGGESTION_REVIEWER,
        json={
            "destination_product": "SalOPS", "destination_type": "exercise_schedule",
            "destination_id": 0,
            "purpose": "Propose this reviewed date for consideration by the plan and exercise authority.",
        },
    )
    assert proposed.status_code == 200, proposed.text
    assert proposed.json()["status"] == "Awaiting Destination Review"
    assert "has not created" in proposed.json()["authority_note"]

    comparison_review = client.post(
        f"/api/material-suggestions/comparisons/{int(near['id'])}/review",
        headers=SUGGESTION_REVIEWER,
        json={"status": "Human Reviewed", "reason": "Compared both original records and their distinct custody."},
    )
    assert comparison_review.status_code == 200, comparison_review.text
    assert comparison_review.json()["review_status"] == "Human Reviewed"

    triage = client.get("/api/material-suggestions/triage", headers=SUGGESTION_REVIEWER)
    assert triage.status_code == 200, triage.text
    assert triage.json()["suggestions"] and triage.json()["comparisons"]
    assert client.get("/api/material-suggestions/triage", headers=MEMBER).status_code == 403
    assert client.get("/api/material-suggestions/triage", headers=OTHER_TENANT).json()["suggestions"] == []
    assert client.post(
        f"/api/material-suggestions/{suggestion_id}/review", headers=OTHER_TENANT,
        json={"status": "Rejected", "reason": "Cross-tenant attempt."},
    ).status_code == 403

    conn = core.db()
    assert conn.execute("SELECT COUNT(*) c FROM material_links").fetchone()["c"] == 0
    assert conn.execute("SELECT COUNT(*) c FROM proposed_governed_links").fetchone()["c"] == 1
    assert conn.execute(
        "SELECT COUNT(*) c FROM material_suggestion_events WHERE record_type='Suggestion' AND record_id=?",
        (suggestion_id,),
    ).fetchone()["c"] == 1
    portable = core.collect_tenant_records(conn, 6)
    for table in (
        "material_reference_terms", "material_suggestion_jobs", "material_suggestions",
        "material_duplicate_suggestions", "material_suggestion_events", "proposed_governed_links",
    ):
        assert table in portable and portable[table], table
    validation_errors = core.validate_records(portable, 6)
    assert validation_errors == [], validation_errors
    tampered = json.loads(json.dumps(portable))
    tampered["material_suggestions"][0]["tenant_id"] = 7
    assert any("crosses the tenant boundary" in item for item in core.validate_records(tampered, 6))
    conn.close()

    administrator = {**PROCESSOR, "X-Salus-Role": "System Administrator", "X-Salus-User": "Recovery Custodian"}
    backup = client.post("/api/admin/backups", headers=administrator)
    assert backup.status_code == 200, backup.text
    backup_id = int(backup.json()["id"])
    verified = client.post(f"/api/admin/backups/{backup_id}/verify", headers=administrator)
    assert verified.status_code == 200 and verified.json()["ok"], verified.text
    recovery = client.post(f"/api/admin/backups/{backup_id}/dr-validate", headers=administrator)
    assert recovery.status_code == 200 and recovery.json()["ok"], recovery.text

    module = (ROOT / "salcapa_material_suggestions.py").read_text(encoding="utf-8")
    interface = (ROOT / "static" / "salcapa-material-suggestions.js").read_text(encoding="utf-8")
    stylesheet = (ROOT / "static" / "salcapa-material-suggestions.css").read_text(encoding="utf-8")
    runtime = (ROOT / "salcapa_runtime.py").read_text(encoding="utf-8")
    for required in (
        "Derived — Unverified", "Awaiting Human Review", "Ambiguous numeric date",
        "does not establish", "does not prove", "Awaiting Destination Review",
        "Cross-tenant comparison", "SHINGLE_WIDTH", "RULESET_HASH",
    ):
        assert required in module, required
    for prohibited in ("automatic finding", "automatic intelligence", "silent merge"):
        assert prohibited not in module.casefold()
    for required in (
        "Prepare source-review suggestions", "Suggested references, dates, times, and locations",
        "Source comparisons", "People", "does not establish", "Propose governed link",
    ):
        assert required in interface, required
    assert "@media print" in stylesheet
    assert 'SALCAPA_RELEASE_VERSION = "3.107"' in runtime
    assert "salcapa-material-suggestions.js" in runtime and "salcapa-material-suggestions.css" in runtime
    print("SALCAPA_MATERIAL_SUGGESTIONS_PASS", core.DB_BACKEND)


if __name__ == "__main__":
    main()
