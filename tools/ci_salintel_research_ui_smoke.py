#!/usr/bin/env python3
"""Static acceptance for Chat-led SalINTEL research and reconciliation UI."""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
runtime = (ROOT / "salcapa_runtime.py").read_text(encoding="utf-8")
personnel = (ROOT / "static/personnel-assessment.js").read_text(encoding="utf-8")
domains = (ROOT / "static/salintel-domains.js").read_text(encoding="utf-8")
ui = (ROOT / "static/salintel-research.js").read_text(encoding="utf-8")
css = (ROOT / "static/salintel-research.css").read_text(encoding="utf-8")

for marker in ("register_salintel_research", "/static/salintel-research.js",
               "/static/salintel-research.css"):
    assert marker in runtime, marker
for marker in (
    "Chat-led research & mixed-source collection", "what Chat accessed",
    "Salus Human Investigator", "Protected Member / Form", "Document / Material",
    "Prior SalCAPA Context", "Approved Partner Return", "Source-access truth applies",
    "Accessed sources require captured governed material", "Unavailable sources remain unavailable",
    "Original bytes are reused by reference", "Create tier-specific Chat research product",
    "Reported Information", "Reasonable Inference", "Contradiction", "Information Gap",
    "Known unknowns, unavailable sources, and collection requirements",
    "recommendations only; no automatic handoff", "Tier recommendation does not authorize scope or cost",
    "Submit for Salus human review", "Qualify", "Reject",
    "Run governed material search", "Research tool execution receipts",
    "actual server-side search", "no external network", "no external cost",
    "Salus review notifications", "In-app delivery only", "Acknowledge",
    "refreshSalintelResearchHost",
):
    assert marker in ui, marker
for endpoint in ("/research`", "/research-plans`", "/source-results`",
                 "/executions`", "/products`", "/research-products/${productId}/review`",
                 "/research-notifications/${notificationId}/acknowledge`"):
    assert endpoint in ui, endpoint
assert "salintelResearchPanel(record)" in personnel
assert "loadSalintelResearch(detail.investigation)" in personnel
assert "salintelResearchPanel(record)" in domains
assert "loadSalintelResearch(detail)" in domains
assert "red" not in css.lower() and "yellow" not in css.lower() and "green" not in css.lower()
assert "@media print" in css
print("SalINTEL Chat-led research interface acceptance passed")
