#!/usr/bin/env python3
"""Acceptance checks for exact-location and source-region visual review."""

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
from PIL.TiffImagePlugin import IFDRational


ROOT = Path(__file__).resolve().parents[1]
WORKSPACE = tempfile.TemporaryDirectory()
os.chdir(ROOT)
os.environ.update({
    "SALUS_AUTH_MODE": "prototype", "SALUS_SEED_DEMO": "1",
    "SALUS_DB_BACKEND": os.environ.get("SALUS_DB_BACKEND", "sqlite"),
    "SALUS_DB_PATH": str(Path(WORKSPACE.name) / "visual-geospatial.db"),
    "SALUS_LOCAL_STORAGE_DIR": str(Path(WORKSPACE.name) / "attachments"),
    "SALUS_BACKUP_DIR": str(Path(WORKSPACE.name) / "backups"),
})
sys.path.insert(0, str(ROOT))

import app as core  # noqa: E402
from salcapa_visual_geospatial import register_salcapa_visual_geospatial  # noqa: E402
from tools import salcapa_visual_geospatial_worker as geo_worker  # noqa: E402


register_salcapa_visual_geospatial(core.app, core.__dict__)

REQUESTER = {
    "X-Salus-Tenant": "1", "X-Salus-Role": "Assessment Director",
    "X-Salus-User": "Location Review Requester",
}
REVIEWER = {**REQUESTER, "X-Salus-User": "Independent Visual Reviewer"}
MEMBER = {
    "X-Salus-Tenant": "1", "X-Salus-Role": "Contributor",
    "X-Salus-User": "Protected Member Contributor",
}
OTHER = {**REQUESTER, "X-Salus-Tenant": "2", "X-Salus-User": "Other Tenant Lead"}


class FakeExif(dict):
    def __init__(self, gps: dict):
        super().__init__({34853: 1})
        self.gps = gps

    def get_ifd(self, tag: int):
        assert tag == 34853
        return self.gps


def expect_worker_failure(gps: dict, code: str) -> None:
    try:
        geo_worker._location(FakeExif(gps))
    except geo_worker.WorkerFailure as exc:
        assert exc.code == code, (exc.code, code)
    else:
        raise AssertionError(f"Expected {code}")


def image_bytes(*, gps: bool = True) -> bytes:
    image = Image.new("RGB", (640, 480), "white")
    exif = Image.Exif()
    exif[274] = 1
    if gps:
        rational = IFDRational
        gps_ifd = exif.get_ifd(34853)
        gps_ifd[1] = "N"
        gps_ifd[2] = (rational(30, 1), rational(15, 1), rational(0, 1))
        gps_ifd[3] = "W"
        gps_ifd[4] = (rational(97, 1), rational(44, 1), rational(30, 1))
        gps_ifd[5] = 0
        gps_ifd[6] = rational(505, 10)
        gps_ifd[7] = (rational(12, 1), rational(34, 1), rational(56, 1))
        gps_ifd[16] = "T"
        gps_ifd[17] = rational(900, 10)
        gps_ifd[18] = "WGS-84"
        gps_ifd[29] = "2026:09:10"
    output = io.BytesIO()
    image.save(output, "JPEG", exif=exif)
    return output.getvalue()


def upload(client: TestClient, name: str, data: bytes, headers: dict = REQUESTER) -> dict:
    response = client.post(
        "/api/materials/upload", headers=headers,
        files={"file": (name, data, "image/jpeg")},
        data={
            "title": f"Fictional {name}", "material_kind": "Image",
            "source_origin": "Authorized fictional demonstration", "sensitivity": "Restricted",
        },
    )
    assert response.status_code == 200, response.text
    return response.json()


valid_dms = ((30, 1), (15, 1), (0, 1))
expect_worker_failure({1: "N", 2: valid_dms}, "LOCATION_METADATA_INCOMPLETE")
expect_worker_failure(
    {1: "N", 2: ((91, 1), (0, 1), (0, 1)), 3: "W", 4: valid_dms},
    "LOCATION_METADATA_RANGE",
)
expect_worker_failure(
    {1: "N", 2: valid_dms, 3: "W", 4: valid_dms, 16: "T"},
    "LOCATION_METADATA_INCOMPLETE",
)
expect_worker_failure({29: "2026:13:10"}, "LOCATION_METADATA_RANGE")


with TestClient(core.app) as client:
    source = upload(client, "fictional-location.jpg", image_bytes())
    original_hash = source["sha256"]

    prepared = client.post(
        f"/api/materials/{source['id']}/location-metadata-review-aids", headers=REQUESTER,
        json={"purpose": "Review source-stored location metadata for a fictional facility record."},
    )
    assert prepared.status_code == 200, prepared.text
    summary = prepared.json()["metadata"]
    assert summary["metadata_status"] == "Location Metadata Present"
    assert summary["exact_location_available"] is True
    assert "latitude_decimal" not in summary and "source_components_json" not in summary

    reused = client.post(
        f"/api/materials/{source['id']}/location-metadata-review-aids", headers=REQUESTER,
        json={"purpose": "Confirm idempotent review-aid reuse."},
    )
    assert reused.status_code == 200 and reused.json()["idempotent_reuse"] is True

    exact = client.post(
        f"/api/visual-geospatial/location-metadata/{summary['id']}/view", headers=REQUESTER,
        json={"purpose": "Compare the exact source metadata with an authorized fictional facility."},
    )
    assert exact.status_code == 200, exact.text
    exact_record = exact.json()
    assert exact_record["latitude_decimal"] == "30.25000000"
    assert exact_record["longitude_decimal"] == "-97.74166667"
    assert exact_record["altitude_meters"] == "50.500"
    assert exact_record["image_direction_degrees"] == "90.000"
    assert exact_record["gps_date"] == "10 September 2026"
    assert exact_record["gps_time_utc"] == "12:34:56 UTC"
    assert exact_record["source_components"]["longitude_ref"] == "W"

    assert client.post(
        f"/api/visual-geospatial/location-metadata/{summary['id']}/view", headers=MEMBER,
        json={"purpose": "Attempt member access."},
    ).status_code == 403
    assert client.post(
        f"/api/visual-geospatial/location-metadata/{summary['id']}/view", headers=OTHER,
        json={"purpose": "Attempt cross-tenant access."},
    ).status_code == 403

    self_review = client.post(
        f"/api/visual-geospatial/location-metadata/{summary['id']}/review", headers=REQUESTER,
        json={"status": "Human Reviewed", "reason": "Requester cannot independently review."},
    )
    assert self_review.status_code == 409
    reviewed_location = client.post(
        f"/api/visual-geospatial/location-metadata/{summary['id']}/review", headers=REVIEWER,
        json={
            "status": "Corrected", "reason": "Recorded a human interpretation without changing source tags.",
            "corrected_latitude_decimal": "30.2501", "corrected_longitude_decimal": "-97.7417",
        },
    )
    assert reviewed_location.status_code == 200 and reviewed_location.json()["review_status"] == "Corrected"

    observation = client.post(
        f"/api/materials/{source['id']}/visual-observations", headers=REQUESTER,
        json={
            "purpose": "Document a visible fictional facility condition for independent review.",
            "observation_text": "A marked assembly-point sign is visible beside the north access gate.",
            "uncertainty_note": "The image alone does not establish whether the gate or sign remains in this condition.",
            "region_x": 10, "region_y": 20, "region_width": 220, "region_height": 140,
        },
    )
    assert observation.status_code == 200, observation.text
    aid = observation.json()
    assert aid["record_type"] == "Visible Observation — Unverified"
    assert aid["record_origin"] == "Person-entered"
    assert aid["review_status"] == "Awaiting Human Review"
    assert aid["region_x"] == 10 and aid["region_width"] == 220
    assert aid["processor_profile_key"] == "VPR-MANUAL-SOURCE-REGION-V1"
    assert len(aid["processor_profile_hash"]) == 64

    out_of_bounds = client.post(
        f"/api/materials/{source['id']}/visual-observations", headers=REQUESTER,
        json={
            "purpose": "Test source-region validation.", "observation_text": "Fictional condition.",
            "uncertainty_note": "Demonstration only.",
            "region_x": 630, "region_y": 470, "region_width": 20, "region_height": 20,
        },
    )
    assert out_of_bounds.status_code == 422

    assert client.post(
        f"/api/visual-geospatial/observations/{aid['id']}/review", headers=REQUESTER,
        json={"status": "Human Reviewed", "reason": "Self-review is not independent.", "corrected_text": ""},
    ).status_code == 409
    corrected = client.post(
        f"/api/visual-geospatial/observations/{aid['id']}/review", headers=REVIEWER,
        json={
            "status": "Corrected", "reason": "Compared the wording with the exact source region.",
            "corrected_text": "A sign marked ASSEMBLY POINT is visible near an access gate.",
        },
    )
    assert corrected.status_code == 200, corrected.text
    assert corrected.json()["current_text"].startswith("A sign marked")
    assert corrected.json()["observation_text"].startswith("A marked assembly")

    proposal = client.post(
        f"/api/visual-geospatial/observations/{aid['id']}/governed-link-proposals", headers=REVIEWER,
        json={
            "destination_product": "Facility Assessment", "destination_type": "facility_observation",
            "destination_id": 0, "purpose": "Ask the Facility Assessment authority to review this source-linked observation.",
        },
    )
    assert proposal.status_code == 200, proposal.text
    assert proposal.json()["status"] == "Awaiting Destination Review"

    no_gps_source = upload(client, "fictional-no-location.jpg", image_bytes(gps=False))
    no_gps = client.post(
        f"/api/materials/{no_gps_source['id']}/location-metadata-review-aids", headers=REQUESTER,
        json={"purpose": "Record that the fictional source contains no GPS metadata."},
    )
    assert no_gps.status_code == 200 and no_gps.json()["metadata"]["metadata_status"] == "Location Metadata Not Present"

    triage = client.get("/api/visual-geospatial/triage", headers=REQUESTER)
    assert triage.status_code == 200, triage.text
    body = triage.json()
    assert len(body["location_metadata"]) == 2 and body["observations"]
    assert "latitude_decimal" not in json.dumps(body)
    assert client.get("/api/visual-geospatial/triage", headers=MEMBER).status_code == 403

    profiles = client.get("/api/visual-geospatial/processor-profiles", headers=REQUESTER)
    assert profiles.status_code == 200
    assert profiles.json()["items"][0]["execution_boundary"] == "Human review"
    assert "No visual model or external provider" in profiles.json()["scope_note"]

    downloaded = client.get(f"/api/materials/{source['id']}/download", headers=REQUESTER)
    assert downloaded.status_code == 200
    assert downloaded.headers["X-Content-SHA256"] == original_hash

    conn = core.db()
    audit_details = "\n".join(
        row["detail"] for row in conn.execute(
            "SELECT detail FROM audit_log WHERE tenant_id=? AND action LIKE 'VISUAL_%' ORDER BY id", (1,)
        )
    )
    assert "30.25000000" not in audit_details and "-97.74166667" not in audit_details
    assert conn.execute("SELECT COUNT(*) c FROM visual_observation_revisions WHERE observation_id=?", (aid["id"],)).fetchone()["c"] == 2
    conn.close()

    records = core.collect_tenant_records(core.db(), 1)
    for table in (
        "visual_processor_profiles", "visual_location_metadata", "visual_observations",
        "visual_observation_revisions", "visual_location_events", "visual_governed_link_proposals",
    ):
        assert table in records and records[table]
    validation_errors = core.validate_records(records, 1)
    assert validation_errors == [], validation_errors
    tampered = copy.deepcopy(records)
    tampered["visual_observations"][0]["tenant_id"] = 2
    assert any("crosses the tenant boundary" in item for item in core.validate_records(tampered, 1))

module = (ROOT / "salcapa_visual_geospatial.py").read_text(encoding="utf-8")
worker = (ROOT / "tools/salcapa_visual_geospatial_worker.py").read_text(encoding="utf-8")
for forbidden in ("requests.get(", "urlopen(", "shell=True", "latitude_decimal={", "longitude_decimal={"):
    assert forbidden not in module + worker

print("SALCAPA_VISUAL_GEOSPATIAL_SMOKE_PASS")
