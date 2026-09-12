#!/usr/bin/env python3
"""Acceptance checks for server-controlled local facility review profiles."""

from __future__ import annotations

import copy
import io
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
    "SALUS_DB_PATH": str(Path(WORKSPACE.name) / "facility-review-profiles.db"),
    "SALUS_LOCAL_STORAGE_DIR": str(Path(WORKSPACE.name) / "attachments"),
    "SALUS_BACKUP_DIR": str(Path(WORKSPACE.name) / "backups"),
})
sys.path.insert(0, str(ROOT))

import app as core  # noqa: E402
from salcapa_facility_imagery import register_salcapa_facility_imagery  # noqa: E402
from salcapa_facility_review_profiles import register_salcapa_facility_review_profiles  # noqa: E402


register_salcapa_facility_imagery(core.app, core.__dict__)
register_salcapa_facility_review_profiles(core.app, core.__dict__)

REQUESTER = {"X-Salus-Tenant": "1", "X-Salus-Role": "Assessment Director", "X-Salus-User": "Facility Profile Requester"}
MEMBER = {"X-Salus-Tenant": "1", "X-Salus-Role": "Contributor", "X-Salus-User": "Protected Member Contributor"}
OTHER = {**REQUESTER, "X-Salus-Tenant": "2", "X-Salus-User": "Other Tenant Lead"}


def image_bytes() -> bytes:
    image = Image.new("RGB", (640, 480), "white")
    output = io.BytesIO()
    image.save(output, "PNG")
    return output.getvalue()


with TestClient(core.app) as client:
    uploaded = client.post(
        "/api/materials/upload", headers=REQUESTER,
        files={"file": ("fictional-layout.png", image_bytes(), "image/png")},
        data={
            "title": "Fictional facility layout", "material_kind": "Image",
            "source_origin": "Authorized fictional demonstration", "sensitivity": "Restricted",
        },
    )
    assert uploaded.status_code == 200, uploaded.text
    material = uploaded.json()
    created = client.post(
        f"/api/materials/{material['id']}/facility-image-sources", headers=REQUESTER,
        json={
            "representation_class": "Diagram or Schematic",
            "purpose": "Review the fictional layout and route relationships.",
            "source_revision": "Working copy 1", "source_date": "12 September 2026",
            "coordinate_space": "Image Pixels", "source_width": 640, "source_height": 480,
            "region_x": 20, "region_y": 20, "region_width": 500, "region_height": 400,
            "scale_status": "Not to Scale", "north_reference": "Unknown", "datum": "Unknown",
            "projection": "Unknown", "precision_status": "Unknown",
            "limitations": "The fictional diagram is not a surveyed plan and does not establish route safety.",
        },
    )
    assert created.status_code == 200, created.text
    source = created.json()

    profiles = client.get("/api/facility-imagery/review-profiles", headers=REQUESTER)
    assert profiles.status_code == 200, profiles.text
    body = profiles.json()
    assert len(body["items"]) == 6
    assert body["external_processing"] is False and body["standing_gpu"] is False
    assert body["manual_review_available"] is True
    keys = {item["profile_key"] for item in body["items"]}
    assert keys == {
        "FRP-LAYOUT-V1", "FRP-SYMBOL-V1", "FRP-CONDITION-V1",
        "FRP-DAMAGE-V1", "FRP-EQUIPMENT-V1", "FRP-PROTECTIVE-CONTROL-V1",
    }
    for item in body["items"]:
        assert len(item["profile_snapshot_sha256"]) == 64
        assert item["external_processing"] is False and item["standing_gpu"] is False and item["no_network"] is True
        assert "does not" in item["negative_inference_rule"].casefold()
    assert client.get("/api/facility-imagery/review-profiles", headers=MEMBER).status_code == 403

    assert client.post(
        f"/api/facility-imagery/sources/{source['id']}/profile-applications", headers=REQUESTER,
        json={"profile_key": "NOT-APPROVED", "purpose": "Review layout.", "review_question": "What is depicted?"},
    ).status_code == 422
    assert client.post(
        f"/api/facility-imagery/sources/{source['id']}/profile-applications", headers=REQUESTER,
        json={"profile_key": "FRP-LAYOUT-V1", "purpose": "Unrelated request.", "review_question": "What is depicted?"},
    ).status_code == 403
    assert client.post(
        f"/api/facility-imagery/sources/{source['id']}/profile-applications", headers=REQUESTER,
        json={"profile_key": "FRP-DAMAGE-V1", "purpose": "Review damage indicators.", "review_question": "What is visibly depicted?"},
    ).status_code == 409
    assert client.post(
        f"/api/facility-imagery/sources/{source['id']}/profile-applications", headers=OTHER,
        json={"profile_key": "FRP-LAYOUT-V1", "purpose": "Review layout.", "review_question": "What route relationship is depicted?"},
    ).status_code == 403
    assert client.post(
        f"/api/facility-imagery/sources/{source['id']}/profile-applications", headers=MEMBER,
        json={"profile_key": "FRP-LAYOUT-V1", "purpose": "Review layout.", "review_question": "What route relationship is depicted?"},
    ).status_code == 403

    prepared = client.post(
        f"/api/facility-imagery/sources/{source['id']}/profile-applications", headers=REQUESTER,
        json={
            "profile_key": "FRP-LAYOUT-V1",
            "purpose": "Review the layout and route relationship within this exact region.",
            "review_question": "What room, area, route, or access relationship is depicted?",
            "destination_under_consideration": "Facility Assessment",
            "expected_region_count": 3,
        },
    )
    assert prepared.status_code == 200, prepared.text
    application = prepared.json()
    assert application["application_status"] == "Prepared — Human Review Required"
    assert application["external_processing"] == 0 and application["standing_gpu"] == 0 and application["no_network"] == 1
    assert len(application["profile_snapshot_sha256"]) == 64
    assert application["profile_snapshot"]["capability_class"] == "Layout"
    assert "does not process source bytes" in application["authority_note"]

    triage = client.get("/api/facility-imagery/profile-applications", headers=REQUESTER)
    assert triage.status_code == 200 and len(triage.json()["items"]) == 1
    assert "Derived — Unverified" in triage.json()["guidance"]

    records = core.collect_tenant_records(core.db(), 1)
    assert len(records["facility_review_profile_applications"]) == 1
    assert core.validate_records(records, 1) == []
    tampered = copy.deepcopy(records)
    tampered["facility_review_profile_applications"][0]["profile_snapshot_sha256"] = "bad"
    assert any("profile snapshot hash" in error for error in core.validate_records(tampered, 1))
    cost_tampered = copy.deepcopy(records)
    cost_tampered["facility_review_profile_applications"][0]["external_processing"] = 1
    assert any("local cost boundary" in error for error in core.validate_records(cost_tampered, 1))

module = (ROOT / "salcapa_facility_review_profiles.py").read_text(encoding="utf-8")
for forbidden in ("requests.get(", "urlopen(", "http://", "https://", "shell=True"):
    assert forbidden not in module
for required in (
    "No paid external call", "no standing GPU", "Derived — Unverified",
    "does not process source bytes", "does not prove absence", "Human Review Required",
):
    assert required.casefold() in module.casefold(), required

print("SALCAPA_FACILITY_REVIEW_PROFILES_SMOKE_PASS")
