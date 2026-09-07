#!/usr/bin/env python3
"""Static interface checks for neutral, explicit recurring monitoring."""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
js = (ROOT / "static" / "salintel-monitoring.js").read_text(encoding="utf-8")
css = (ROOT / "static" / "salintel-monitoring.css").read_text(encoding="utf-8")
runtime = (ROOT / "salcapa_runtime.py").read_text(encoding="utf-8")
personnel = (ROOT / "static" / "personnel-assessment.js").read_text(encoding="utf-8")
facility = (ROOT / "static" / "facility-assessment.js").read_text(encoding="utf-8")

for marker in ("Recurring Monitoring", "<option selected>No</option>", "<option>Yes</option>",
               "Approve and activate", "Pause", "Resume", "End", "Cancel",
               "No automatic tier change, charge, disclosure, or external escalation",
               "Immutable version history"):
    assert marker in js, marker
for forbidden in ("risk-low", "risk-high", "background:#dc2626", "background:#16a34a"):
    assert forbidden not in js + css, forbidden
assert "/static/salintel-monitoring.js" in runtime
assert "/static/salintel-monitoring.css" in runtime
assert "salintelMonitoringPanel" in personnel and "loadSalintelMonitoring" in personnel
assert "salintelMonitoringPanel" in facility and "loadSalintelMonitoring" in facility
print("SALINTEL_MONITORING_UI_SMOKE_PASS")
