"""Deterministic acceptance checks for SalCAPA contextual guidance."""

from pathlib import Path
import re


ROOT = Path(__file__).resolve().parents[1]
HTML = (ROOT / "static" / "index.html").read_text(encoding="utf-8")
JS = (ROOT / "static" / "guidance.js").read_text(encoding="utf-8")
CSS = (ROOT / "static" / "guidance.css").read_text(encoding="utf-8")
SVG = (ROOT / "static" / "assets" / "how-salcapa-works.svg").read_text(encoding="utf-8")


def require(value: str, source: str, label: str) -> None:
    if value not in source:
        raise SystemExit(f"SalCAPA guidance acceptance is incomplete: {label}")


for value in (
    '<link rel="stylesheet" href="/static/guidance.css" />',
    '<script src="/static/guidance.js"></script>',
):
    require(value, HTML, value)

for value in (
    "Help / How SalCAPA Works",
    'role="dialog"',
    'aria-modal="true"',
    'aria-label="Close help"',
    "event.key === 'Escape'",
    "lastFocus.focus()",
    "setAttribute('aria-label'",
    'aria-current="step"',
    "button.addEventListener('click'",
    'aria-label="Breadcrumb"',
    'aria-label="SalCAPA lifecycle"',
    "new MutationObserver",
    "What is this?",
    "Why it matters.",
    "What happens next?",
    "help or navigation shortcut to bypass required approvals",
    "Protected Member",
    "Salus workspace",
    "SalCAPA™",
    "SalINTEL™",
    "SalTHIRA™",
    "SalOPS™",
    'aria-label="Salus product terminology"',
):
    require(value, JS, value)

for stage, label, view in (
    ("see", "See", "dashboard"),
    ("decide", "Decide", "assessments"),
    ("coordinate", "Coordinate", "common_operating_picture"),
    ("act", "Act", "salops"),
    ("prove", "Prove", "reports"),
):
    pattern = rf"\['{stage}',\s*'{label}',\s*'[^']+',\s*'{view}',\s*'[^']+'\]"
    if not re.search(pattern, JS):
        raise SystemExit(f"Lifecycle guidance is incomplete: {label}")

for forbidden in (
    "fetch(",
    "XMLHttpRequest",
    "/api/",
    ".submit(",
    "SALUS_AUTH_MODE",
):
    if forbidden in JS:
        raise SystemExit(
            "Guidance layer may not call application APIs, submit forms, or alter authority"
        )

for value in (
    ".guidance-trigger:focus-visible",
    ".lifecycle-step:focus-visible",
    ".help-dot:focus-visible",
    "@media (max-width: 900px)",
    "@media (max-width: 700px)",
    "@media print",
    "var(--intel)",
    "var(--thira)",
    "var(--ops)",
    ".guidance-brand-grid",
):
    require(value, CSS, value)

lower_svg = SVG.lower()
for value in (
    'role="img"',
    'aria-labelledby="title desc"',
    "<title",
    "<desc",
    "Protected Members",
    "SalCAPA™",
    "SalINTEL™",
    "SalTHIRA™",
    "SalOPS™",
):
    require(value, SVG, value)
if "<script" in lower_svg or re.search(
    r'(?:href|xlink:href)\s*=\s*["\'](?:https?:)?//',
    lower_svg,
):
    raise SystemExit("Guidance graphic contains executable or external content")

print("SALCAPA_CONTEXTUAL_GUIDANCE_PASS")
