"""Deterministic acceptance checks for the shared SalCAPA visual system."""

from pathlib import Path
import re


ROOT = Path(__file__).resolve().parents[1]
CSS = (ROOT / "static" / "styles.css").read_text(encoding="utf-8")
HTML = (ROOT / "static" / "index.html").read_text(encoding="utf-8")


def require(value: str, source: str, label: str) -> None:
    if value not in source:
        raise SystemExit(f"SalCAPA brand acceptance is incomplete: {label}")


tokens = {
    "--bg": "#f6f7f7",
    "--panel": "#ffffff",
    "--ink": "#17242f",
    "--nav": "#0b2236",
    "--accent": "#2b7d76",
    "--intel": "#147fa6",
    "--thira": "#ad7720",
    "--ops": "#337a65",
    "--danger": "#a51d2a",
}
for name, value in tokens.items():
    if not re.search(rf"{re.escape(name)}\s*:\s*{re.escape(value)}\s*;", CSS, re.IGNORECASE):
        raise SystemExit(f"SalCAPA brand token is missing or changed: {name}")

for required in (
    '"Avenir Next", Avenir, "Helvetica Neue", Helvetica, Arial, sans-serif',
    "button:focus-visible",
    "outline: 2px solid var(--accent)",
    ".component.intel { background: var(--intel); }",
    ".component.thira { background: var(--thira); }",
    ".component.ops { background: var(--ops); }",
    ".btn.danger { background: var(--danger);",
    "@media (max-width: 1050px)",
    "@media (max-width: 900px)",
    "@media (max-width: 760px)",
    "@media print",
    ".brand-logo {",
):
    require(required, CSS, required)

combined = (CSS + "\n" + HTML).lower()
for forbidden in ("@font-face", "fonts.googleapis.com", "fonts.gstatic.com"):
    if forbidden in combined:
        raise SystemExit("External or bundled proprietary font path is not permitted")

logo_match = re.search(
    r'<img\s+src="/static/assets/salus-solutions-horizontal-white[.]svg"\s+'
    r'class="brand-logo"\s+alt="Salus Solutions"\s*/?>',
    HTML,
)
if not logo_match:
    raise SystemExit("Official horizontal Salus logo is not bound to navigation")
if "style=" in logo_match.group(0).lower():
    raise SystemExit("Navigation logo styling must remain in the shared stylesheet")
require("SalCAPA™", HTML, "SalCAPA trademark label")

for view in (
    "dashboard",
    "common_operating_picture",
    "salintel",
    "assessments",
    "salops",
    "reports",
    "salthira",
):
    require(f'data-view="{view}"', HTML, f"navigation view {view}")

for name in (
    "salus-solutions-horizontal-white.svg",
    "salus-solutions-stacked-white.svg",
):
    content = (ROOT / "static" / "assets" / name).read_text(encoding="utf-8")
    lowered = content.lower()
    has_scalable_geometry = "viewbox=" in lowered or (
        "width=" in lowered and "height=" in lowered
    )
    if "<svg" not in lowered or not has_scalable_geometry:
        raise SystemExit(f"Official logo asset is not a valid responsive SVG: {name}")
    if "<script" in lowered or re.search(
        r'(?:href|xlink:href)\s*=\s*["\'](?:https?:)?//',
        lowered,
    ):
        raise SystemExit(f"Official logo asset contains executable or external content: {name}")

print("SALCAPA_BRAND_SYSTEM_PASS")
