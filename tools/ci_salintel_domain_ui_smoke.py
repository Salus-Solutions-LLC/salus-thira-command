#!/usr/bin/env python3
"""Static acceptance for the role-aware SalINTEL Investigative Domains workspace."""
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
index = (ROOT / "static/index.html").read_text(encoding="utf-8")
app = (ROOT / "static/app.js").read_text(encoding="utf-8")
ui = (ROOT / "static/salintel-domains.js").read_text(encoding="utf-8")
css = (ROOT / "static/salintel-domains.css").read_text(encoding="utf-8")
assert 'data-view="salintel_domains" data-salus-only="true">Investigative Domains<' in index
assert '/static/salintel-domains.js' in index and '/static/salintel-domains.css' in index
assert "currentView==='salintel_domains'" in app
assert "document.querySelectorAll('#nav [data-salus-only=\"true\"]')" in app
assert "item.hidden=protectedMember" in app
for marker in ["Investigative Domains","Start a governed investigation request","Knowledge state","Mission lens","Depth is not danger","Human qualification","Approve for Protected Member","Known unknowns and contradictions","Version history"]:
    assert marker in ui, marker
for endpoint in ["/api/salintel/domains/catalog","/api/salintel/investigations","/authorize-tier","/items","/qualify","/complete-tier","/recommend-tier","/disclosure","/release"]:
    assert endpoint in ui, endpoint
assert "isProtectedMember()" in ui
assert "@media print" in css
print("SalINTEL Investigative Domains UI acceptance passed")
