#!/usr/bin/env python3
"""Static acceptance for the SalINTEL relationship and where-used interface."""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
runtime = (ROOT / "salcapa_runtime.py").read_text(encoding="utf-8")
personnel = (ROOT / "static/personnel-assessment.js").read_text(encoding="utf-8")
ui = (ROOT / "static/salintel-relationships.js").read_text(encoding="utf-8")
css = (ROOT / "static/salintel-relationships.css").read_text(encoding="utf-8")

for marker in ("register_salintel_relationships", "/static/salintel-relationships.js",
               "/static/salintel-relationships.css"):
    assert marker in runtime, marker
for marker in (
    "Enterprise relationships & where used", "without duplicating source material",
    "Add governed relationship", "Chat Suggestion", "Source Extraction",
    "Approved Partner Return", "Possible duplicate", "Competing-resource condition",
    "Source conflict or contradiction", "Add for human review",
    "Enterprise relationship search", "tenant- and sensitivity-scoped",
    "Outgoing relationships", "Incoming / where used", "Qualify", "Reject",
    "Approve tenant release", "Return to Salus control",
):
    assert marker in ui, marker
for endpoint in (
    "/api/salintel/relationship-types/", "/relationships`,",
    "/review`,", "/disclosure`,", "/api/salintel/relationship-search?",
):
    assert endpoint in ui, endpoint
assert "salintelRelationshipPanel(record)" in personnel
assert "loadSalintelRelationships(detail.investigation)" in personnel
assert "red" not in css.lower() and "yellow" not in css.lower() and "green" not in css.lower()
assert "@media print" in css
print("SalINTEL relationship interface acceptance passed")
