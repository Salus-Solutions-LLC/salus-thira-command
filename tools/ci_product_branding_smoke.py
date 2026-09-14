"""Deterministic acceptance checks for trademark-first navigation and the light-airy SalCAPA shell."""
from pathlib import Path
import re

ROOT=Path(__file__).resolve().parents[1]
HTML=(ROOT/"static/index.html").read_text(encoding="utf-8")
APP=(ROOT/"static/app.js").read_text(encoding="utf-8")
TERMS=(ROOT/"static/product-branding.js").read_text(encoding="utf-8")
CSS=(ROOT/"static/product-branding.css").read_text(encoding="utf-8")
SHELL=(ROOT/"static/styles.css").read_text(encoding="utf-8")
VERSION=(ROOT/"static/product-version.js").read_text(encoding="utf-8")

def req(value,source,label):
    if value not in source:
        raise SystemExit(f"SalCAPA shell acceptance is incomplete: {label}")

for mark in ("SalCAPA™","SalINTEL™","SalTHIRA™","SalOPS™"):
    req(mark,HTML,mark)
    req(mark,TERMS,f"central terminology {mark}")
if len(re.findall(r'<button[^>]+data-view="salintel"',HTML))!=1:
    raise SystemExit("SalINTEL navigation must have exactly one intelligence overview destination")
if re.search(r'<button[^>]*>\s*Intelligence\s*</button>',HTML):
    raise SystemExit("Generic Intelligence may not remain a peer navigation destination")
for value in (
    'data-view="salintel">Intelligence Overview</button>',
    'data-view="salintel_domains" data-salus-only="true">Type of Investigation</button>',
    'data-view="salthira">Risk Assessments</button>',
    'data-view="salops">Operations & Requests</button>',
    'aria-label="SalCAPA product navigation"',
    '/static/assets/salus-solutions-horizontal-blue.svg',
    'Command Center</button><span class="nav-view-description">Coordinate decisions',
    'Common Operating Picture</button><span class="nav-view-description">See what is happening',
):
    req(value,HTML,value)
if HTML.index('/static/product-branding.js')>=HTML.index('/static/app.js'):
    raise SystemExit("Central Salus terminology must load before application navigation")
for value in (
    "const PRODUCT_TERMS=window.SalusProductTerms",
    "const viewTitles=",
    "document.querySelectorAll('#nav [data-salus-only=\"true\"]')",
    "item.hidden=protectedMember",
    "const isCop=currentView==='common_operating_picture'",
    "Command Center · Coordinate and act",
    "Common Operating Picture · See and understand",
    "Needs Your Attention",
    "Current Work",
    "Coordinate action &gt;",
    "View the situation &gt;",
):
    req(value,APP,value)
if "['SalINTEL','Investigative Domains','SalTHIRA','SalOPS']" in APP:
    raise SystemExit("Role navigation may not hide trademark product groups by display text")
if "General Notes" in APP:
    raise SystemExit("General Notes must use the approved plain-language label")
for value in (".nav-product-group",".nav-product-title",".nav-product-description","@media print"):
    req(value,CSS,value)
for value in (
    "--salus-blue: #174a73",
    "--salus-orange: #b84d16",
    ".sidebar {",
    "background: var(--panel);",
    ".topbar {",
    "position: sticky",
    ".workspace-handoff",
    ".action-link",
    ".command-stats",
):
    req(value,SHELL,value)
req("fetch('/api/system/mode'",VERSION,"authoritative product version source")
req("SalCAPA™ v",VERSION,"trademarked product version label")
for forbidden in ("branch","commit","sha","workflow","ci status","build number"):
    if forbidden in VERSION.lower():
        raise SystemExit(f"Product version renderer exposes engineering metadata: {forbidden}")
print("SALCAPA_LIGHT_AIRY_SHELL_PASS")
