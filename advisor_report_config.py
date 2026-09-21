"""Fail-closed readiness contract for Protection Advisor report storage."""
from __future__ import annotations
import os
from pathlib import Path

REQUIRED = (
    "SALUS_ADVISOR_DOCX_TEMPLATE_PATH",
    "SALUS_ADVISOR_REPORT_OUTPUT_DIR",
    "SALUS_M365_ADVISOR_REPORT_FOLDER_ITEM_ID",
    "SALUS_OIDC_MANAGED_IDENTITY_CLIENT_ID",
    "SALUS_M365_REPORT_DRIVE_ID",
)

def protection_advisor_report_readiness() -> dict:
    missing=[name for name in REQUIRED if not os.getenv(name,"").strip()]
    template=os.getenv("SALUS_ADVISOR_DOCX_TEMPLATE_PATH","").strip()
    output=os.getenv("SALUS_ADVISOR_REPORT_OUTPUT_DIR","").strip()
    checks={
        "template_exists": bool(template) and Path(template).is_file(),
        "output_directory_configured": bool(output),
        "advisor_folder_configured": bool(os.getenv("SALUS_M365_ADVISOR_REPORT_FOLDER_ITEM_ID","").strip()),
        "managed_identity_configured": bool(os.getenv("SALUS_OIDC_MANAGED_IDENTITY_CLIENT_ID","").strip()),
        "drive_configured": bool(os.getenv("SALUS_M365_REPORT_DRIVE_ID","").strip()),
    }
    return {"ready": not missing and all(checks.values()), "missing": missing, "checks": checks}
