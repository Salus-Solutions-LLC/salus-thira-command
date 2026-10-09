"""Separate governed Microsoft 365 storage for Protection Advisor prospect reports."""
from __future__ import annotations
import os
import hashlib
import re
from pathlib import Path
from urllib.parse import quote, urlparse

import httpx
from salcapa_m365_reports import GovernedM365ReportConfig, GovernedM365Reports, M365ReportError

def _trusted_pdf_conversion_url(location: str) -> bool:
    parsed = urlparse(location)
    hostname = (parsed.hostname or "").lower()
    return parsed.scheme == "https" and (
        hostname.endswith(".sharepoint.com")
        or bool(re.fullmatch(r"[a-z0-9-]+-mediap\.svc\.ms", hostname))
    )


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

    conversion_url = (
        f"https://graph.microsoft.com/v1.0/drives/{quote(config.drive_id, safe='')}/"
        f"items/{quote(item_id, safe='')}/content?format=pdf"
    )
    pdf_response = client._request("GET", conversion_url, headers={"Accept": "application/pdf"})
    if pdf_response.status_code in (302, 303, 307, 308):
        location = pdf_response.headers.get("Location", "")
        if not _trusted_pdf_conversion_url(location):
            raise M365ReportError("Microsoft 365 returned an untrusted Advisor PDF location")
        try:
            pdf_response = client.client.get(location, headers={"Accept": "application/pdf"})
        except (httpx.TimeoutException, httpx.TransportError) as exc:
            raise M365ReportError("Microsoft 365 Advisor PDF conversion download failed") from exc
    if pdf_response.status_code != 200:
        raise M365ReportError("Microsoft 365 could not convert the Advisor DOCX to PDF")
    pdf_content = bytes(pdf_response.content)
    if not pdf_content.startswith(b"%PDF") or len(pdf_content) > config.max_file_bytes:
        raise M365ReportError("Microsoft 365 returned an invalid Advisor PDF")

    pdf_name = f"Salus-Protection-Advisor-{report_reference}.pdf"
    pdf_upload = client._request(
        "PUT",
        client._content_url(pdf_name),
        headers={"Content-Type": "application/pdf"},
        content=pdf_content,
    )
    if pdf_upload.status_code not in (200, 201):
        raise M365ReportError("Microsoft 365 rejected the Protection Advisor PDF")
    pdf_payload = pdf_upload.json()
    pdf_item_id = str(pdf_payload.get("id", ""))
    if not pdf_item_id:
        raise M365ReportError("Microsoft 365 returned invalid Protection Advisor PDF metadata")

    return {
        "status": "Stored for Salus Review",
        "item_id": item_id,
        "name": str(payload.get("name", name))[:256],
        "size": len(content),
        "sha256": hashlib.sha256(content).hexdigest(),
        "pdf": {
            "item_id": pdf_item_id,
            "name": str(pdf_payload.get("name", pdf_name))[:256],
            "size": len(pdf_content),
            "sha256": hashlib.sha256(pdf_content).hexdigest(),
        },
        "review_required": True,
    }

def read_advisor_report(submission_key: str, file_format: str) -> bytes:
    """Read one stored prospect report for an already-authorized staff route."""
    if not re.fullmatch(r"SPA-SUBMISSION-[A-F0-9]{32}", submission_key):
        raise M365ReportError("Protection Advisor submission key is invalid")
    if file_format not in {"docx", "pdf"}:
        raise M365ReportError("Protection Advisor report format is invalid")
    folder = os.getenv("SALUS_M365_ADVISOR_REPORT_FOLDER_ITEM_ID", "").strip()
    if not folder:
        raise M365ReportError("Protection Advisor report storage is not configured")
    base = GovernedM365ReportConfig.from_environment()
    config = GovernedM365ReportConfig(
        managed_identity_client_id=base.managed_identity_client_id,
        drive_id=base.drive_id,
        folder_item_id=folder,
        max_file_bytes=base.max_file_bytes,
        retries=base.retries,
    )
    client = GovernedM365Reports(config)
    report_reference = "SPA-REPORT-" + submission_key.removeprefix("SPA-SUBMISSION-")
    filename = f"Salus-Protection-Advisor-{report_reference}.{file_format}"
    response = client._request("GET", client._content_url(filename), headers={"Accept": "application/octet-stream"})
    if response.status_code in (302, 303, 307, 308):
        location = response.headers.get("Location", "")
        if not _trusted_pdf_conversion_url(location):
            raise M365ReportError("Microsoft 365 returned an untrusted Advisor report location")
        try:
            response = client.client.get(location, headers={"Accept": "application/octet-stream"})
        except (httpx.TimeoutException, httpx.TransportError) as exc:
            raise M365ReportError("Microsoft 365 Advisor report download failed") from exc
    if response.status_code != 200:
        raise M365ReportError("Stored Protection Advisor report is unavailable")
    content = bytes(response.content)
    if not content or len(content) > config.max_file_bytes:
        raise M365ReportError("Stored Protection Advisor report size is invalid")
    if file_format == "pdf" and not content.startswith(b"%PDF"):
        raise M365ReportError("Stored Protection Advisor PDF is invalid")
    if file_format == "docx" and not content.startswith(b"PK\\x03\\x04"):
        raise M365ReportError("Stored Protection Advisor Word file is invalid")
    return content
