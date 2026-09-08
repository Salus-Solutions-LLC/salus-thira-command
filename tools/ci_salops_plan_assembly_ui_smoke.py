#!/usr/bin/env python3
"""Interface acceptance for the governed SalOPS plan-assembly workspace."""
import os
import sys
import tempfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
WORKSPACE = tempfile.TemporaryDirectory()
os.environ.setdefault("SALUS_DB_BACKEND", "sqlite")
os.environ.setdefault("SALUS_DB_PATH", str(Path(WORKSPACE.name) / "plan-assembly-ui.db"))
os.environ.setdefault("SALUS_BACKUP_DIR", str(Path(WORKSPACE.name) / "backups"))
os.environ.setdefault("SALUS_LOCAL_STORAGE_DIR", str(Path(WORKSPACE.name) / "attachments"))
os.environ.setdefault("SALUS_AUTH_MODE", "prototype")
os.environ.setdefault("SALUS_SEED_DEMO", "1")
sys.path.insert(0, str(ROOT))

from fastapi.testclient import TestClient
import salcapa_runtime


JS = (ROOT / "static" / "salops-plan-assembly.js").read_text(encoding="utf-8")
CSS = (ROOT / "static" / "salops-plan-assembly.css").read_text(encoding="utf-8")
RUNTIME = (ROOT / "salcapa_runtime.py").read_text(encoding="utf-8")


def require(value: str, source: str) -> None:
    if value not in source:
        raise SystemExit(f"SalOPS plan-assembly interface is incomplete: {value}")


for value in (
    'SALCAPA_RELEASE_VERSION = "3.65"',
    '/static/salops-plan-assembly.js',
    '/static/salops-plan-assembly.css',
    'data-view="salops_plan_assembly" data-salus-only="true"',
):
    require(value, RUNTIME)

for value in (
    "Emergency Plan Assembly",
    "SalCAPA can inspect, research, reconcile, draft, compare, and recommend",
    "Salus personnel validate, establish authority, approve, and release",
    "It does not approve a plan, establish authority, release information, or create a charge",
    "Accessed",
    "Unavailable",
    "Human / Field Needed",
    "Partner Needed",
    "Missing information becomes a governed question or collection requirement",
    "Generated language remains proposed",
    "human_authority_required",
    "Approved baseline preserved",
    "The approved plan remains unchanged",
    "Numbered stages show governed workflow progress",
    "planAssemblyWhen",
    "salcapaFormatDateTime",
    "selectSalopsPlanAssembly",
    "submitSalopsPlanAssembly",
    "answerSalopsPlanAssemblyQuestion",
    "qualifySalopsPlanAssembly",
    "recommendSalopsPlanRevision",
    "Governed plan-version candidate",
    "immutable, integrity-verified proposal",
    "createSalopsPlanVersionCandidate",
    "reviewSalopsPlanVersionCandidate",
    "acceptSalopsPlanVersionCandidate",
    "Accepted for Plan Revision",
):
    require(value, JS)

for forbidden in (
    "risk-low", "risk-high", "background:#dc2626", "background:#16a34a",
    "toLocaleDateString", "Verified Fact</option>",
):
    if forbidden in JS + CSS:
        raise SystemExit(f"Plan-assembly UI contains a forbidden implication: {forbidden}")

for value in (
    ".plan-assembly-workspace",
    ".plan-assembly-stages",
    ".plan-assembly-stage.current",
    ".plan-assembly-help",
    "@media (max-width:900px)",
    "@media print",
):
    require(value, CSS)

client = TestClient(salcapa_runtime.app)
root = client.get("/")
assert root.status_code == 200, root.text
for value in (
    '/static/salops-plan-assembly.js',
    '/static/salops-plan-assembly.css',
    'data-view="salops_plan_assembly" data-salus-only="true"',
):
    require(value, root.text)

director = {
    "X-Salus-Tenant": "1", "X-Salus-Role": "Assessment Director",
    "X-Salus-User": "Preparedness Director", "X-Salus-Clearance": "Highly Sensitive",
}
member = {
    "X-Salus-Tenant": "1", "X-Salus-Role": "Contributor",
    "X-Salus-User": "Protected Member", "X-Salus-Clearance": "Standard",
}
path = "/api/salops/preparedness/plan-assembly/catalog"
assert client.get(path, headers=director).status_code == 200
assert client.get(path, headers=member).status_code == 403
assert client.get("/api/system/mode").json()["version"] == "3.65"

print("SALOPS_PLAN_ASSEMBLY_UI_PASS")
