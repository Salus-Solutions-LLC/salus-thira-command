#!/usr/bin/env python3
"""Static acceptance for governed SalINTEL handoff presentation."""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
runtime = (ROOT / "salcapa_runtime.py").read_text(encoding="utf-8")
personnel = (ROOT / "static/personnel-assessment.js").read_text(encoding="utf-8")
ui = (ROOT / "static/salintel-handoffs.js").read_text(encoding="utf-8")
css = (ROOT / "static/salintel-handoffs.css").read_text(encoding="utf-8")

for marker in ("register_salintel_handoffs", "/static/salintel-handoffs.js",
               "/static/salintel-handoffs.css"):
    assert marker in runtime, marker
for marker in (
    "Qualified internal handoffs", "completed, human-qualified outputs",
    "SalTHIRA™ assessment", "SalOPS™ request", "Internal routing is not member disclosure",
    "cannot change tier, price, disclosure, or execution authority",
    "Qualified outputs to reference", "Authorize internal handoff",
    "Immutable source references; live target status",
):
    assert marker in ui, marker
for endpoint in ("/handoffs`", "api('/api/assessments')"):
    assert endpoint in ui, endpoint
assert "salintelHandoffPanel(record)" in personnel
assert "loadSalintelHandoffs(detail.investigation)" in personnel
assert "red" not in css.lower() and "yellow" not in css.lower() and "green" not in css.lower()
assert "@media print" in css
print("SalINTEL governed handoff interface acceptance passed")
