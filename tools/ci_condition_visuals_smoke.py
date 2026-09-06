"""Acceptance checks for the Salus condition/readiness visual doctrine."""

from pathlib import Path
import re


ROOT = Path(__file__).resolve().parents[1]
HTML = (ROOT / "static" / "index.html").read_text(encoding="utf-8")
JS = (ROOT / "static" / "condition-visuals.js").read_text(encoding="utf-8")
CSS = (ROOT / "static" / "condition-visuals.css").read_text(encoding="utf-8")


def require(value: str, source: str, label: str) -> None:
    if value not in source:
        raise SystemExit(f"Condition visual acceptance is incomplete: {label}")


for value in (
    '<link rel="stylesheet" href="/static/condition-visuals.css" />',
    '<script src="/static/condition-visuals.js"></script>',
):
    require(value, HTML, value)

tokens = (
    "--condition-red",
    "--condition-red-orange",
    "--condition-orange",
    "--condition-amber",
    "--condition-yellow-green",
    "--condition-green",
)
for token in tokens:
    if not re.search(rf"{re.escape(token)}\s*:\s*#[0-9a-f]{{6}}\s*;", CSS, re.I):
        raise SystemExit(f"Condition continuum token is missing: {token}")

for value in (
    "--condition-gradient: linear-gradient(90deg",
    "var(--condition-red) 0%",
    "var(--condition-red-orange) 20%",
    "var(--condition-orange) 40%",
    "var(--condition-amber) 58%",
    "var(--condition-yellow-green) 78%",
    "var(--condition-green) 100%",
    ".condition-symbol",
    ".workflow-progress",
    ".workflow-progress.intel",
    ".workflow-progress.thira",
    ".workflow-progress.ops",
    "@media print",
    "linear-gradient(90deg, #222 0%, #555 35%, #888 60%, #bbb 82%, #eee 100%)",
):
    require(value, CSS, value)

for key, css_class, symbol in (
    ("critical", "condition-critical", "!"),
    ("high", "condition-high", "!"),
    ("elevated", "condition-elevated", "▲"),
    ("guarded", "condition-guarded", "▲"),
    ("improving", "condition-improving", "●"),
    ("ready", "condition-ready", "✓"),
):
    pattern = (
        rf"key:'{re.escape(key)}'.*?cls:'{re.escape(css_class)}'.*?"
        rf"symbol:'{re.escape(symbol)}'"
    )
    if not re.search(pattern, JS):
        raise SystemExit(f"Condition mapping is incomplete: {key}")

for term in (
    "approved",
    "rejected",
    "deferred",
    "awaiting approval",
    "draft",
    "implementation",
    "validation",
    "open",
    "closed",
    "current",
    "verified",
    "stale",
):
    require(f"'{term}'", JS, f"workflow exclusion {term}")

for value in (
    "Color supplements the text and symbol",
    "it does not represent workflow completion",
    "badge.setAttribute('aria-label'",
    "symbol.setAttribute('aria-hidden', 'true')",
    "window.SalusConditionVisuals = Object.freeze",
):
    require(value, JS, value)

for forbidden in ("fetch(", "XMLHttpRequest", "/api/", ".submit(", "localStorage"):
    if forbidden in JS:
        raise SystemExit(
            "Condition visual layer may not call APIs, submit forms, or persist authority"
        )

print("SALUS_CONDITION_VISUAL_DOCTRINE_PASS")
