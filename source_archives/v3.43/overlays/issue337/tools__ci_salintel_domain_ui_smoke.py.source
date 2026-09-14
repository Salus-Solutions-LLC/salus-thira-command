#!/usr/bin/env python3
"""Static acceptance for the role-aware SalINTEL Type of Investigation workspace."""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
index = (ROOT / "static/index.html").read_text(encoding="utf-8")
app = (ROOT / "static/app.js").read_text(encoding="utf-8")
ui = (ROOT / "static/salintel-domains.js").read_text(encoding="utf-8")
css = (ROOT / "static/salintel-domains.css").read_text(encoding="utf-8")

assert 'data-view="salintel_domains" data-salus-only="true">Type of Investigation<' in index
assert '/static/salintel-domains.js' in index and '/static/salintel-domains.css' in index
assert "currentView==='salintel_domains'" in app
assert "document.querySelectorAll('#nav [data-salus-only=\"true\"]')" in app
assert "item.hidden=protectedMember" in app
for marker in [
    "Type of Investigation",
    "One secure place to investigate a problem, use trusted sources",
    "Start an investigation request",
    "Type of investigation",
    "Who can see this?",
    "Limited Access — Only people working this matter",
    "Access is controlled by the server",
    "Sharing with a Protected Member is a separate decision",
    "Knowledge state",
    "Mission lens",
    "Depth is not danger",
    "Human qualification",
    "Approve for Protected Member",
    "Known unknowns and contradictions",
    "Version history",
]:
    assert marker in ui, marker
assert "salintelOption('Restricted','Limited Access — Only people working this matter'" in ui
for endpoint in [
    "/api/salintel/domains/catalog",
    "method:'PUT'",
    "configureSalintelDomain",
    "openSalintelDomainRegistry",
    "Governance basis for this new domain version",
    "/api/salintel/investigations",
    "/authorize-tier",
    "/items",
    "/qualify",
    "/complete-tier",
    "/recommend-tier",
    "/disclosure",
    "/release",
]:
    assert endpoint in ui, endpoint
assert "isProtectedMember()" in ui
for marker in ["Type of Investigation settings","Configure domain","governed version","Version","Lifecycle / version"]:
    assert marker in ui, marker
assert "Investigative Domains" not in index
assert "Start a governed investigation request" not in ui
assert "<label>Sensitivity" not in ui
assert ".salintel-registry-detail" in css
assert "var(--salus-blue)" in css
assert "@media print" in css
print("SalINTEL Type of Investigation UI acceptance passed")
