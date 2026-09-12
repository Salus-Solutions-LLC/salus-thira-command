#!/usr/bin/env python3
"""Static and runtime acceptance for facility review profiles in governed interfaces."""

from pathlib import Path
import os
import sys
import tempfile

from fastapi.testclient import TestClient


ROOT = Path(__file__).resolve().parents[1]
WORKSPACE = tempfile.TemporaryDirectory()
os.chdir(ROOT)
os.environ.update({
    "SALUS_AUTH_MODE": "prototype",
    "SALUS_SEED_DEMO": "1",
    "SALUS_DB_BACKEND": "sqlite",
    "SALUS_DB_PATH": str(Path(WORKSPACE.name) / "facility-review-profiles-ui.db"),
    "SALUS_LOCAL_STORAGE_DIR": str(Path(WORKSPACE.name) / "attachments"),
    "SALUS_BACKUP_DIR": str(Path(WORKSPACE.name) / "backups"),
})
sys.path.insert(0, str(ROOT))

import salcapa_runtime  # noqa: E402


script = (ROOT / "static" / "salcapa-facility-review-profiles.js").read_text(encoding="utf-8")
runtime = (ROOT / "salcapa_runtime.py").read_text(encoding="utf-8")

for required in (
    "Facility Assessment", "Mission Map", "Human Review Required", "Review aid — not a conclusion",
    "exact source region", "Derived — Unverified", "destination's own authority",
    "/api/facility-imagery/review-profiles", "/api/facility-imagery/profile-applications",
    "Prepare review profile", "isProtectedMember", "facilityAssessments", "salcapaMissionMap",
):
    assert required.casefold() in script.casefold(), required
for forbidden in (
    "generate with ai", "ai recommendation", "automatic finding", "auto-accept",
    "safe route confirmed", "engineering verified",
):
    assert forbidden not in script.casefold(), forbidden
assert "/static/salcapa-facility-review-profiles.js" in runtime

salus = {
    "X-Salus-Tenant": "1", "X-Salus-Role": "Assessment Director",
    "X-Salus-User": "Facility Profile Interface Reviewer",
}
member = {
    "X-Salus-Tenant": "1", "X-Salus-Role": "Contributor",
    "X-Salus-User": "Protected Member Contributor",
}
with TestClient(salcapa_runtime.app) as client:
    root = client.get("/", headers=salus)
    assert root.status_code == 200
    assert '<script src="/static/salcapa-facility-review-profiles.js"></script>' in root.text
    assert root.text.index("/static/salcapa-facility-imagery.js") < root.text.index("/static/salcapa-facility-review-profiles.js")
    profiles = client.get("/api/facility-imagery/review-profiles", headers=salus)
    assert profiles.status_code == 200
    assert len(profiles.json()["items"]) == 6
    assert profiles.json()["external_processing"] is False
    assert profiles.json()["standing_gpu"] is False
    assert profiles.json()["manual_review_available"] is True
    assert client.get("/api/facility-imagery/review-profiles", headers=member).status_code == 403
    assert client.get("/api/facility-imagery/profile-applications", headers=member).status_code == 403

print("SALCAPA_FACILITY_REVIEW_PROFILES_UI_SMOKE_PASS")
