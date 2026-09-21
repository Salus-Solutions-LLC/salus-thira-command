"""Separate governed Microsoft 365 storage for Protection Advisor prospect reports."""
from __future__ import annotations
import os
from pathlib import Path
from salcapa_m365_reports import GovernedM365ReportConfig, GovernedM365Reports, M365ReportError

def publish_advisor_docx(path: str, report_reference: str) -> dict:
    folder = os.getenv("SALUS_M365_ADVISOR_REPORT_FOLDER_ITEM_ID", "").strip()
    if not folder:
        return {"status": "Not Configured", "review_required": True}
    base = GovernedM365ReportConfig.from_environment()
    config = GovernedM365ReportConfig(
        managed_identity_client_id=base.managed_identity_client_id,
        drive_id=base.drive_id,
        folder_item_id=folder,
        max_file_bytes=base.max_file_bytes,
        retries=base.retries,
    )
    source = Path(path)
    if not source.is_file():
        raise M365ReportError("Protection Advisor DOCX artifact was not found")
    name = f"Salus-Protection-Advisor-{report_reference}.docx"
    if "/" in name or "\\" in name or len(name) > 200:
        raise M365ReportError("Protection Advisor report filename is invalid")
    content = source.read_bytes()
    if not content or len(content) > config.max_file_bytes:
        raise M365ReportError("Protection Advisor DOCX artifact size is invalid")
    client = GovernedM365Reports(config)
    # Use the existing fail-closed Graph client with a prospect-only folder.
    url = client._content_url(name)
    response = client._request("PUT", url, headers={"Content-Type":"application/vnd.openxmlformats-officedocument.wordprocessingml.document"}, content=content)
    if response.status_code not in (200,201):
        raise M365ReportError("Microsoft 365 rejected the Protection Advisor report")
    payload = response.json()
    item_id = str(payload.get("id",""))
    if not item_id:
        raise M365ReportError("Microsoft 365 returned invalid Protection Advisor report metadata")
    import hashlib
    return {"status":"Stored for Salus Review","item_id":item_id,"name":str(payload.get("name",name))[:256],"size":len(content),"sha256":hashlib.sha256(content).hexdigest(),"review_required":True}
