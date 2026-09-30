"""Prospect-isolated, versioned Protection Advisor PDF storage.

The authenticated Advisor route owns account authorization. This module accepts
only a generated filename or a stored Graph item id and never returns a Graph
URL to the browser. The database records the exact SHA-256 for each revision.
"""

from __future__ import annotations

import hashlib
import os
import re
from urllib.parse import quote

from salcapa_m365_advisor_reports import _trusted_pdf_conversion_url
from salcapa_m365_reports import GovernedM365ReportConfig, GovernedM365Reports, M365ReportError

_ITEM_ID = re.compile(r"^[A-Za-z0-9_!.-]{8,256}$")


def _client() -> GovernedM365Reports:
    folder = os.getenv("SALUS_M365_ADVISOR_MEMBER_REPORT_FOLDER_ITEM_ID", "").strip()
    if not folder:
        raise M365ReportError("Protected Member report storage is not configured")
    base = GovernedM365ReportConfig.from_environment()
    config = GovernedM365ReportConfig(
        managed_identity_client_id=base.managed_identity_client_id,
        drive_id=base.drive_id,
        folder_item_id=folder,
        max_file_bytes=base.max_file_bytes,
        retries=base.retries,
    )
    return GovernedM365Reports(config)


def store_member_pdf(report_reference: str, revision_no: int, content: bytes) -> dict[str, str | int]:
    if not re.fullmatch(r"SPA-(?:REPORT|RECEIPT)-[A-Z0-9-]+", report_reference) or revision_no < 1:
        raise M365ReportError("Protection Advisor report identity is invalid")
    client = _client()
    if not content.startswith(b"%PDF") or len(content) > client.config.max_file_bytes:
        raise M365ReportError("Protection Advisor PDF is invalid or too large")
    digest = hashlib.sha256(content).hexdigest()
    filename = f"{report_reference}-R{revision_no}-{digest}.pdf"
    response = client._request(
        "PUT", client._content_url(filename),
        headers={"Content-Type": "application/pdf"}, content=content,
    )
    if response.status_code not in (200, 201):
        raise M365ReportError("Microsoft 365 rejected the Protection Advisor PDF")
    item_id = str(response.json().get("id", ""))
    if not _ITEM_ID.fullmatch(item_id):
        raise M365ReportError("Microsoft 365 returned invalid report metadata")
    return {"item_id": item_id, "sha256": digest, "size": len(content), "filename": filename}


def read_member_pdf(item_id: str, expected_sha256: str, expected_size: int) -> bytes:
    if not _ITEM_ID.fullmatch(item_id) or not re.fullmatch(r"[a-f0-9]{64}", expected_sha256):
        raise M365ReportError("Protection Advisor report identity is invalid")
    client = _client()
    url = f"https://graph.microsoft.com/v1.0/drives/{quote(client.config.drive_id, safe='')}/items/{quote(item_id, safe='')}/content"
    response = client._request("GET", url, headers={"Accept": "application/pdf"})
    if response.status_code in (302, 303, 307, 308):
        location = response.headers.get("Location", "")
        if not _trusted_pdf_conversion_url(location):
            raise M365ReportError("Microsoft 365 returned an untrusted report location")
        response = client.client.get(location, headers={"Accept": "application/pdf"})
    if response.status_code != 200:
        raise M365ReportError("Protection Advisor report could not be retrieved")
    content = bytes(response.content)
    if (not content.startswith(b"%PDF") or len(content) != expected_size
            or len(content) > client.config.max_file_bytes
            or hashlib.sha256(content).hexdigest() != expected_sha256):
        raise M365ReportError("Protection Advisor report failed exact-version verification")
    return content


def delete_member_pdf(item_id: str) -> None:
    if not _ITEM_ID.fullmatch(item_id):
        raise M365ReportError("Protection Advisor report identity is invalid")
    client = _client()
    url = f"https://graph.microsoft.com/v1.0/drives/{quote(client.config.drive_id, safe='')}/items/{quote(item_id, safe='')}"
    response = client._request("DELETE", url)
    if response.status_code not in (204, 404):
        raise M365ReportError("Protection Advisor report could not be deleted")
