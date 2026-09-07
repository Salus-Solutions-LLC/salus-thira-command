"""Acceptance checks for the canonical role-aware contextual-guidance increment."""
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
RUNTIME = (ROOT / "salcapa_runtime.py").read_text(encoding="utf-8")
JS = (ROOT / "static" / "salcapa-contextual-guidance.js").read_text(encoding="utf-8")
CSS = (ROOT / "static" / "salcapa-contextual-guidance.css").read_text(encoding="utf-8")


def require(value: str, source: str) -> None:
    if value not in source:
        raise SystemExit(f"SalCAPA contextual guidance is incomplete: {value}")


for value in (
    'SALCAPA_RELEASE_VERSION = "3.63"',
    "/static/salcapa-contextual-guidance.css",
    "/static/salcapa-contextual-guidance.js",
):
    require(value, RUNTIME)

for value in (
    "SalINTEL™",
    "Develops qualified intelligence.",
    "SalTHIRA™",
    "authorized people decide",
    "SalCAPA™",
    "Coordinates Protected Members, information, decisions, and action.",
    "SalOPS™",
    "Implements, sustains, and improves protective capability.",
    "PROVE is a cross-cutting SalCAPA assurance capability, not a separate fifth product",
    "Tier is depth and effort—not a risk, danger, or readiness rating.",
    "Monitoring does not activate automatically.",
    "SalCAPA never creates a charge automatically.",
    "Cross-Protected-Member identifiable disclosure requires explicit Salus approval.",
    "Missing governed links remain visible gaps",
    "Guidance cannot grant authority",
    "Protected Member",
    "Salus personnel",
    "Purpose, authority, and next step",
    "What happens next?",
    "MutationObserver",
    "requestAnimationFrame",
    "description && description.textContent !== 'Assure every function'",
    "decide && decide.textContent !== 'Risk and priorities; people decide'",
    "coordinate && coordinate.textContent !== 'SalCAPA aligns people and action'",
    "data-action-guidance",
    "aria-label",
):
    require(value, JS)

for forbidden in (
    "fetch(",
    "XMLHttpRequest",
    "/api/",
    ".submit(",
    "localStorage.setItem",
):
    if forbidden in JS:
        raise SystemExit("Guidance may not call APIs, submit forms, or mutate governed state")

for value in (
    ".salcapa-action-guidance",
    ".salcapa-doctrine-grid",
    ".salcapa-prove-band",
    ":focus-visible",
    "@media (max-width: 700px)",
    "@media print",
):
    require(value, CSS)

print("SALCAPA_CANONICAL_CONTEXTUAL_GUIDANCE_PASS")
