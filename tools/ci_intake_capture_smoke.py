"""Acceptance checks for the governed first universal-intake surface."""

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
HTML = (ROOT / "static" / "index.html").read_text(encoding="utf-8")
JS = (ROOT / "static" / "intake-capture.js").read_text(encoding="utf-8")
APP = (ROOT / "static" / "app.js").read_text(encoding="utf-8")
CSS = (ROOT / "static" / "intake-capture.css").read_text(encoding="utf-8")


def require(value: str, source: str, label: str) -> None:
    if value not in source:
        raise SystemExit(f"Universal intake acceptance is incomplete: {label}")


for value in (
    '<link rel="stylesheet" href="/static/intake-capture.css" />',
    '<script src="/static/intake-capture.js"></script>',
):
    require(value, HTML, value)

for value in (
    "＋ Add Information",
    "GOVERNED INTAKE",
    "Paste / Enter Text",
    "Upload Material",
    "/api/intake",
    "/api/evidence/",
    "/attachments",
    "multiple required",
    "MAX_FILE_BYTES = 25 * 1024 * 1024",
    "sourceContext",
    "recordingBasis",
    "Human review and governed promotion are required",
    "Existing evidence controls remain authoritative",
    "canCaptureInformation",
    "(accessState?.permissions||[]).includes('write')",
    "WRITE_ROLES.has(currentRole)",
    "window.SalusIntakeCapture=Object.freeze",
):
    require(value, JS, value)

for role in (
    "System Administrator",
    "Assessment Director",
    "Lead Assessor",
    "SME Assessor",
    "Contributor",
):
    require(role, JS, f"authorized capture role {role}")

for forbidden_role in ("Client Executive", "Program Owner", "Auditor"):
    if forbidden_role in JS.split("const WRITE_ROLES", 1)[1].split(");", 1)[0]:
        raise SystemExit(f"Non-write role exposed in capture allowlist: {forbidden_role}")

for value in (
    "window.SalusIntakeCapture?.sync()",
    "accessState=null;window.SalusIntakeCapture?.sync()",
):
    require(value, APP, value)

for value in (
    ".intake-dialog",
    ".intake-tab:focus-visible",
    ".intake-status",
    "@media(max-width:720px)",
    "@media print",
):
    require(value, CSS, value)

for forbidden in (
    "lifecycle_status",
    "verification_status",
    "tenant_id",
    "authority_status",
    "release_state",
    "qualified_intelligence",
):
    if forbidden in JS:
        raise SystemExit(
            "Client intake surface may not submit server-controlled state: " + forbidden
        )

print("GOVERNED_UNIVERSAL_INTAKE_SURFACE_PASS")
