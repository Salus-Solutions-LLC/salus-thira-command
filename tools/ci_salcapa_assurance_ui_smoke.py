#!/usr/bin/env python3
"""Static acceptance for the role-aware PROVE Assurance & Results workspace."""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
runtime = (ROOT / "salcapa_runtime.py").read_text(encoding="utf-8")
js = (ROOT / "static" / "salcapa-assurance.js").read_text(encoding="utf-8")
css = (ROOT / "static" / "salcapa-assurance.css").read_text(encoding="utf-8")

for marker in ("PROVE — Assurance & Results", "Assurance gaps", "Direct traceability",
               "Only persisted explicit links are shown", "Missing links remain visible",
               "Released assurance outputs", "salcapaFormatDateTime"):
    assert marker in js, marker
for marker in ('data-view="prove"', "/static/salcapa-assurance.css",
               "/static/salcapa-assurance.js", 'SALCAPA_RELEASE_VERSION = "3.59"',
               "register_salcapa_assurance"):
    assert marker in runtime, marker
for forbidden in ("risk-low", "risk-high", "#dc2626", "#16a34a"):
    assert forbidden not in js + css, forbidden
assert "@media print" in css
print("SALCAPA_ASSURANCE_UI_SMOKE_PASS")
