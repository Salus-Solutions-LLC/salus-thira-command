"""Deterministic acceptance checks for trademark-first SalCAPA navigation and version display."""
from pathlib import Path
import re
ROOT=Path(__file__).resolve().parents[1]
HTML=(ROOT/"static/index.html").read_text(encoding="utf-8")
APP=(ROOT/"static/app.js").read_text(encoding="utf-8")
TERMS=(ROOT/"static/product-branding.js").read_text(encoding="utf-8")
CSS=(ROOT/"static/product-branding.css").read_text(encoding="utf-8")
VERSION=(ROOT/"static/product-version.js").read_text(encoding="utf-8")
def req(value,source,label):
    if value not in source: raise SystemExit(f"Trademark-first product acceptance is incomplete: {label}")
for mark in ("SalCAPA™","SalINTEL™","SalTHIRA™","SalOPS™"):
    req(mark,HTML,mark);req(mark,TERMS,f"central terminology {mark}")
if len(re.findall(r'<button[^>]+data-view="salintel"',HTML))!=1: raise SystemExit("SalINTEL navigation must have exactly one intelligence overview destination")
if re.search(r'<button[^>]*>\s*Intelligence\s*</button>',HTML): raise SystemExit("Generic Intelligence may not remain a peer navigation destination")
for value in ('data-view="salintel">Intelligence Overview</button>','data-view="salintel_domains" data-salus-only="true"','data-view="salthira">Risk Assessments</button>','data-view="salops">Operations & Requests</button>','aria-label="SalCAPA product navigation"'): req(value,HTML,value)
if HTML.index('/static/product-branding.js')>=HTML.index('/static/app.js'): raise SystemExit("Central Salus terminology must load before application navigation")
for value in ("const PRODUCT_TERMS=window.SalusProductTerms","const viewTitles=","document.querySelectorAll('#nav [data-salus-only=\"true\"]')","item.hidden=protectedMember"): req(value,APP,value)
if "['SalINTEL','Investigative Domains','SalTHIRA','SalOPS']" in APP: raise SystemExit("Role navigation may not hide trademark product groups by display text")
for value in (".nav-product-group",".nav-product-title",".nav-product-description","@media print"): req(value,CSS,value)
req("fetch('/api/system/mode'",VERSION,"authoritative product version source");req("SalCAPA™ v",VERSION,"trademarked product version label")
for forbidden in ("branch","commit","sha","workflow","ci status","build number"):
    if forbidden in VERSION.lower(): raise SystemExit(f"Product version renderer exposes engineering metadata: {forbidden}")
print("SALCAPA_TRADEMARK_FIRST_NAVIGATION_PASS")
