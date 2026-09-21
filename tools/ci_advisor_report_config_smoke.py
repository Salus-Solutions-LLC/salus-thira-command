import os
from advisor_report_config import protection_advisor_report_readiness
for name in ("SALUS_ADVISOR_DOCX_TEMPLATE_PATH","SALUS_ADVISOR_REPORT_OUTPUT_DIR","SALUS_M365_ADVISOR_REPORT_FOLDER_ITEM_ID","SALUS_OIDC_MANAGED_IDENTITY_CLIENT_ID","SALUS_M365_REPORT_DRIVE_ID"):
    os.environ.pop(name, None)
result=protection_advisor_report_readiness()
assert result["ready"] is False
assert "SALUS_ADVISOR_DOCX_TEMPLATE_PATH" in result["missing"]
print("Protection Advisor report readiness smoke passed")
