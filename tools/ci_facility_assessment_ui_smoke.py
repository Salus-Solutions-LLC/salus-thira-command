#!/usr/bin/env python3
"""Static acceptance checks for the role-aware Facility Assessment workspace."""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
js = (ROOT / "static" / "facility-assessment.js").read_text(encoding="utf-8")
css = (ROOT / "static" / "facility-assessment.css").read_text(encoding="utf-8")
runtime = (ROOT / "salcapa_runtime.py").read_text(encoding="utf-8")

required_js = [
    "facilityAssessments", "isProtectedMember()", "Salus investigative workspace",
    "/api/salintel/facility-assessment/checklist",
    "/api/salintel/facility-assessments/", "generateFacilityPlan",
    "submitFacilityContext", "submitFacilityFunction", "submitFacilityChain",
    "submitFacilityFinding", "analysis_mode='Defensive'",
    "Mission function → dependency", "Depth is not a danger or readiness rating",
    "salintelResearchPanel", "salintelHandoffPanel", "salintelRelationshipPanel",
    "Human qualification", "Recommend deeper tier", "Open governance and disclosure controls",
    "facilityCompletionReadiness", "Complete authorized tier", "completeFacilityTier",
    "intentional_scenario_types", "facilityIntentionalScenarios",
]
for marker in required_js:
    if marker not in js:
        raise SystemExit(f"Missing Facility Assessment UI marker: {marker}")

for forbidden in [
    "operational_authority_granted=true", "member_disclosure_authorized=true",
    "commercial_treatment=", "background:#d32f2f", "background:#2e7d32",
]:
    if forbidden in js.replace(" ", "").lower():
        raise SystemExit(f"Forbidden Facility UI authority or risk-color marker: {forbidden}")

required_runtime = [
    "/static/facility-assessment.css", "/static/facility-assessment.js",
    'data-view="facility_assessments"', "register_facility_assessment",
]
for marker in required_runtime:
    if marker not in runtime:
        raise SystemExit(f"Missing Facility runtime composition marker: {marker}")

for marker in [".facility-hero", ".facility-status-grid", ".facility-state",
               ".facility-context", ".facility-scenarios", "@media print"]:
    if marker not in css:
        raise SystemExit(f"Missing Facility CSS marker: {marker}")

print("Facility Assessment role-aware workspace acceptance passed")
