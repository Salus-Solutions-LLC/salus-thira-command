#!/usr/bin/env python3
"""Static and runtime acceptance for Facility Assessment and Mission Map imagery guidance."""

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
    "SALUS_DB_PATH": str(Path(WORKSPACE.name) / "facility-imagery-ui.db"),
    "SALUS_LOCAL_STORAGE_DIR": str(Path(WORKSPACE.name) / "attachments"),
    "SALUS_BACKUP_DIR": str(Path(WORKSPACE.name) / "backups"),
})
sys.path.insert(0, str(ROOT))

import salcapa_runtime  # noqa: E402


script = (ROOT / "static" / "salcapa-facility-imagery.js").read_text(encoding="utf-8")
style = (ROOT / "static" / "salcapa-facility-imagery.css").read_text(encoding="utf-8")
runtime = (ROOT / "salcapa_runtime.py").read_text(encoding="utf-8")

for required in (
    "Derived — Unverified", "not a Facility Assessment finding", "engineering conclusion",
    "exact source region", "authority", "scale limits", "contradictions", "uncertainty",
    "destination's own authority", "/api/facility-imagery/triage",
    "facilityAssessments", "salcapaMissionMap", "isProtectedMember",
):
    assert required.casefold() in script.casefold(), required
for forbidden in ("generate with ai", "ai recommendation", "automatic finding", "auto-accept"):
    assert forbidden not in script.casefold(), forbidden
assert "overflow-wrap:break-word" in style
assert "/static/salcapa-facility-imagery.css" in runtime
assert "/static/salcapa-facility-imagery.js" in runtime

salus = {
    "X-Salus-Tenant": "1", "X-Salus-Role": "Assessment Director",
    "X-Salus-User": "Facility Guidance Reviewer",
}
member = {
    "X-Salus-Tenant": "1", "X-Salus-Role": "Contributor",
    "X-Salus-User": "Protected Member Contributor",
}
with TestClient(salcapa_runtime.app) as client:
    root = client.get("/", headers=salus)
    assert root.status_code == 200
    assert '<link rel="stylesheet" href="/static/salcapa-facility-imagery.css" />' in root.text
    assert '<script src="/static/salcapa-facility-imagery.js"></script>' in root.text
    assert root.text.index("/static/facility-assessment.js") < root.text.index("/static/salcapa-facility-imagery.js")
    assert root.text.index("/static/mission-map.js") < root.text.index("/static/salcapa-facility-imagery.js")
    status = client.get("/api/facility-imagery/status", headers=salus)
    assert status.status_code == 200
    assert status.json()["external_processing"] is False
    assert status.json()["standing_gpu"] is False
    assert "No paid" in status.json()["cost_note"]
    assert client.get("/api/facility-imagery/triage", headers=member).status_code == 403

print("SALCAPA_FACILITY_IMAGERY_UI_SMOKE_PASS")
