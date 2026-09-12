#!/usr/bin/env python3
"""Acceptance checks for governed facility-imagery relationship records."""

from __future__ import annotations

import copy
import io
import json
import os
from pathlib import Path
import sys
import tempfile

from fastapi.testclient import TestClient
from PIL import Image


ROOT = Path(__file__).resolve().parents[1]
WORKSPACE = tempfile.TemporaryDirectory()
os.chdir(ROOT)
os.environ.update({
    "SALUS_AUTH_MODE": "prototype", "SALUS_SEED_DEMO": "1",
    "SALUS_DB_BACKEND": os.environ.get("SALUS_DB_BACKEND", "sqlite"),
    "SALUS_DB_PATH": str(Path(WORKSPACE.name) / "facility-imagery.db"),
    "SALUS_LOCAL_STORAGE_DIR": str(Path(WORKSPACE.name) / "attachments"),
    "SALUS_BACKUP_DIR": str(Path(WORKSPACE.name) / "backups"),
})
sys.path.insert(0, str(ROOT))

import app as core  # noqa: E402
from salcapa_facility_imagery import register_salcapa_facility_imagery  # noqa: E402


register_salcapa_facility_imagery(core.app, core.__dict__)

REQUESTER = {
    "X-Salus-Tenant": "1", "X-Salus-Role": "Assessment Director",
    "X-Salus-User": "Facility Relationship Requester",
}
REVIEWER = {**REQUESTER, "X-Salus-User": "Independent Facility Reviewer"}
MEMBER = {
    "X-Salus-Tenant": "1", "X-Salus-Role": "Contributor",
    "X-Salus-User": "Protected Member Contributor",
}
OTHER = {**REQUESTER, "X-Salus-Tenant": "2", "X-Salus-User": "Other Tenant Lead"}


def image_bytes() -> bytes:
    image = Image.new("RGB", (800, 600), "white")
    output = io.BytesIO()
    image.save(output, "PNG")
    return output.getvalue()


with TestClient(core.app) as client:
    uploaded = client.post(
        "/api/materials/upload", headers=REQUESTER,
        files={"file": ("fictional-site-plan.png", image_bytes(), "image/png")},
        data={
            "title": "Fictional site plan", "material_kind": "Image",
            "source_origin": "Authorized fictional demonstration", "sensitivity": "Restricted",
        },
    )
    assert uploaded.status_code == 200, uploaded.text
    material = uploaded.json()

    status = client.get("/api/facility-imagery/status", headers=REQUESTER)
    assert status.status_code == 200 and status.json()["external_processing"] is False
    assert status.json()["standing_gpu"] is False
    assert client.get("/api/facility-imagery/status", headers=MEMBER).status_code == 403

    bad_region = client.post(
        f"/api/materials/{material['id']}/facility-image-sources", headers=REQUESTER,
        json={
            "representation_class": "Diagram or Schematic", "purpose": "Review a fictional site relationship.",
            "coordinate_space": "Image Pixels", "source_width": 800, "source_height": 600,
            "region_x": 790, "region_y": 590, "region_width": 20, "region_height": 20,
            "limitations": "The diagram is not a surveyed plan.",
        },
    )
    assert bad_region.status_code == 422

    missing_authority = client.post(
        f"/api/materials/{material['id']}/facility-image-sources", headers=REQUESTER,
        json={
            "representation_class": "Authoritative Plan or Survey", "purpose": "Review a fictional plan.",
            "coordinate_space": "Image Pixels", "source_width": 800, "source_height": 600,
            "region_x": 0, "region_y": 0, "region_width": 800, "region_height": 600,
            "limitations": "Demonstration record.",
        },
    )
    assert missing_authority.status_code == 422

    created = client.post(
        f"/api/materials/{material['id']}/facility-image-sources", headers=REQUESTER,
        json={
            "representation_class": "Diagram or Schematic",
            "purpose": "Review a fictional access and assembly-area relationship.",
            "source_revision": "Working copy 2", "source_date": "12 September 2026",
            "coordinate_space": "Image Pixels", "source_width": 800, "source_height": 600,
            "region_x": 100, "region_y": 120, "region_width": 300, "region_height": 200,
            "scale_status": "Not to Scale", "north_reference": "Unknown", "datum": "Unknown",
            "projection": "Unknown", "precision_status": "Unknown",
            "limitations": "The schematic does not establish distance, safe passage, code compliance, or current field condition.",
        },
    )
    assert created.status_code == 200, created.text
    source = created.json()
    assert len(source["source_sha256"]) == 64 and len(source["geometry_sha256"]) == 64
    assert source["disclosure_status"] == "Salus Internal — Not Released"

    assert client.post(
        f"/api/materials/{material['id']}/facility-image-sources", headers=OTHER,
        json={
            "representation_class": "Diagram or Schematic", "purpose": "Cross-tenant attempt.",
            "coordinate_space": "Image Pixels", "source_width": 800, "source_height": 600,
            "region_x": 0, "region_y": 0, "region_width": 10, "region_height": 10,
            "limitations": "Test.",
        },
    ).status_code == 403

    proposal_response = client.post(
        f"/api/facility-imagery/sources/{source['id']}/relationship-proposals", headers=REQUESTER,
        json={
            "relationship_type": "Access or Egress",
            "description": "The working diagram depicts a route between an access gate and an assembly area.",
            "origin_type": "Source-stated", "target_type": "facility_route", "target_id": 0,
            "alternatives": ["The line may represent a boundary rather than a route."],
            "contradictions": "No current field survey is linked.",
            "assumptions": "The legend appears applicable but remains unverified.",
            "information_gaps": "Confirm revision, route condition, accessibility, and operational authority.",
            "uncertainty_note": "The image alone does not establish that the depicted route is current, safe, accessible, or authorized.",
        },
    )
    assert proposal_response.status_code == 200, proposal_response.text
    proposal = proposal_response.json()
    assert proposal["epistemic_state"] == "Derived — Unverified"
    assert proposal["review_status"] == "Awaiting Human Review"

    assert client.post(
        f"/api/facility-imagery/relationship-proposals/{proposal['id']}/destination-proposals", headers=REQUESTER,
        json={"destination_product": "Facility Assessment", "destination_type": "facility_route", "purpose": "Premature destination attempt."},
    ).status_code == 409
    assert client.post(
        f"/api/facility-imagery/relationship-proposals/{proposal['id']}/review", headers=REQUESTER,
        json={"status": "Accept Representation", "reason": "Self-review attempt."},
    ).status_code == 409

    review = client.post(
        f"/api/facility-imagery/relationship-proposals/{proposal['id']}/review", headers=REVIEWER,
        json={
            "status": "Corrected", "reason": "Compared the proposal with the exact source region and legend.",
            "corrected_description": "The working diagram contains a line labeled as a proposed route between a gate and assembly area.",
            "corrected_target_type": "facility_route", "corrected_target_id": 0,
            "corrected_geometry_json": json.dumps({"coordinate_space": "Image Pixels", "region": [100, 120, 300, 200]}),
        },
    )
    assert review.status_code == 200, review.text
    assert review.json()["review_status"] == "Corrected"
    assert "proposed route" in review.json()["current_description"]

    destination = client.post(
        f"/api/facility-imagery/relationship-proposals/{proposal['id']}/destination-proposals", headers=REVIEWER,
        json={
            "destination_product": "Facility Assessment", "destination_type": "facility_route",
            "purpose": "Ask the Facility Assessment authority to compare this source representation with current facility records.",
        },
    )
    assert destination.status_code == 200, destination.text
    assert destination.json()["status"] == "Awaiting Destination Review"
    assert destination.json()["disclosure_status"] == "Salus Internal — Not Released"

    triage = client.get("/api/facility-imagery/triage", headers=REQUESTER)
    assert triage.status_code == 200 and triage.json()["items"]
    assert triage.json()["external_processing"] is False
    assert client.get("/api/facility-imagery/triage", headers=MEMBER).status_code == 403
    assert client.get("/api/facility-imagery/triage", headers=OTHER).json()["items"] == []

    records = core.collect_tenant_records(core.db(), 1)
    for table in (
        "facility_image_sources", "facility_relationship_proposals",
        "facility_relationship_reviews", "facility_destination_proposals",
    ):
        assert table in records and records[table]
    assert core.validate_records(records, 1) == []
    tampered = copy.deepcopy(records)
    tampered["facility_image_sources"][0]["tenant_id"] = 2
    assert any("crosses the tenant boundary" in item for item in core.validate_records(tampered, 1))
    tampered = copy.deepcopy(records)
    tampered["facility_image_sources"][0]["geometry_sha256"] = "bad"
    assert any("invalid geometry lineage" in item for item in core.validate_records(tampered, 1))

module = (ROOT / "salcapa_facility_imagery.py").read_text(encoding="utf-8")
for forbidden in ("requests.get(", "urlopen(", "shell=True", "external provider", "face recognition"):
    assert forbidden not in module.lower()
for required in (
    "Derived — Unverified", "Salus Internal — Not Released", "Awaiting Destination Review",
    "does not establish source truth", "No paid", "engineering conclusion",
):
    assert required.casefold() in module.casefold()

print("SALCAPA_FACILITY_IMAGERY_SMOKE_PASS")
