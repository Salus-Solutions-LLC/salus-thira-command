#!/usr/bin/env python3
"""Static acceptance for the role-aware Personnel Assessment workspace."""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
index = (ROOT / "static/index.html").read_text(encoding="utf-8")
app = (ROOT / "static/app.js").read_text(encoding="utf-8")
runtime = (ROOT / "salcapa_runtime.py").read_text(encoding="utf-8")
ui = (ROOT / "static/personnel-assessment.js").read_text(encoding="utf-8")
css = (ROOT / "static/personnel-assessment.css").read_text(encoding="utf-8")

assert 'data-view="personnel_assessments" data-salus-only="true">Personnel Assessment<' in runtime
assert "/static/personnel-assessment.js" in runtime
assert "/static/personnel-assessment.css" in runtime
assert "currentView==='personnel_assessments'" in ui
assert "viewTitles.personnel_assessments=`${PRODUCT_TERMS.salintel.name} Personnel Assessment`" in ui
assert "personnelBaseRender=render" in ui
assert 'data-view="personnel_assessments"' not in index
assert "currentView==='personnel_assessments'" not in app
for marker in [
    "Personnel Assessment", "Authorized research plan", "Identity candidates",
    "Structured findings", "Depth is not a safety rating", "Same-name collision",
    "All new findings require human qualification", "Recommend deeper tier",
    "No unrestricted personal dossier", "Protected Members receive only",
]:
    assert marker in ui, marker
for endpoint in [
    "/api/salintel/investigations?domain_key=personnel-assessment",
    "/api/salintel/personnel-assessment/checklist",
    "/research-plan", "/identity-candidates", "/decision", "/findings",
]:
    assert endpoint in ui, endpoint
for controlled in [
    "source_material_id", "epistemic_state", "origin_type",
    "competing_resource_relevance", "insider_threat_relevance",
    "protective_intelligence_relevance", "isProtectedMember()",
]:
    assert controlled in ui, controlled
assert "red" not in css.lower() and "yellow" not in css.lower() and "green" not in css.lower()
assert "@media print" in css
print("SalINTEL Personnel Assessment UI acceptance passed")
