"""Folder-scoped Microsoft 365 storage for released SalCAPA reports.

Only deterministic, member-safe report artifacts are written.  Every Graph URL is
anchored to the configured drive and folder item; callers cannot supply a path.
"""

from __future__ import annotations

import hashlib
import json
import logging
import os
import re
import time
from dataclasses import dataclass
from typing import Any, Callable
from urllib.parse import quote, urlparse

import httpx
from azure.identity import ManagedIdentityCredential


GRAPH_ROOT = "https://graph.microsoft.com/v1.0"
_IDENTIFIER = re.compile(r"^[A-Za-z0-9_!.-]{8,256}$")
_LOG = logging.getLogger("salcapa.m365.reports")


class M365ReportError(RuntimeError):
    """Fail-closed report-storage error safe for internal handling."""


@dataclass(frozen=True)
class GovernedM365ReportConfig:
    managed_identity_client_id: str
    drive_id: str
    folder_item_id: str
    max_file_bytes: int = 25 * 1024 * 1024
    retries: int = 3

    @classmethod
    def from_environment(cls) -> "GovernedM365ReportConfig":
        return cls(
            managed_identity_client_id=os.getenv("SALUS_OIDC_MANAGED_IDENTITY_CLIENT_ID", "").strip(),
            drive_id=os.getenv("SALUS_M365_REPORT_DRIVE_ID", "").strip(),
            folder_item_id=os.getenv("SALUS_M365_REPORT_FOLDER_ITEM_ID", "").strip(),
            max_file_bytes=int(os.getenv("SALUS_M365_REPORT_MAX_FILE_BYTES", str(25 * 1024 * 1024))),
            retries=int(os.getenv("SALUS_M365_REPORT_RETRIES", "3")),
        )

    def validate(self) -> None:
        for value in (self.managed_identity_client_id, self.drive_id, self.folder_item_id):
            if not _IDENTIFIER.fullmatch(value):
                raise M365ReportError("Microsoft 365 report identifiers are incomplete or invalid")
        if not 1 <= self.max_file_bytes <= 100 * 1024 * 1024:
            raise M365ReportError("Microsoft 365 report size limit is invalid")
        if not 1 <= self.retries <= 5:
            raise M365ReportError("Microsoft 365 report retry limit is invalid")


def _canonical_json(payload: dict[str, Any]) -> bytes:
    return json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str).encode("utf-8")


def report_filename(row: dict[str, Any]) -> str:
    return (
        f"SalCAPA-Report-T{int(row['tenant_id'])}-A{int(row['assessment_id'])}"
        f"-R{int(row['id'])}-{str(row['snapshot_sha256'])[:16]}.json"
    )


class GovernedM365Reports:
    def __init__(self, config: GovernedM365ReportConfig, *, credential=None, client=None, sleeper=None):
        config.validate()
        self.config = config
        self.credential = credential or ManagedIdentityCredential(client_id=config.managed_identity_client_id)
        self.client = client or httpx.Client(timeout=20.0, follow_redirects=False)
        self.sleeper = sleeper or time.sleep
        self._token: tuple[str, int] | None = None

    def _graph_token(self) -> str:
        now = int(time.time())
        if self._token and self._token[1] > now + 60:
            return self._token[0]
        token = self.credential.get_token("https://graph.microsoft.com/.default")
        value = str(getattr(token, "token", "") or "")
        if not value:
            raise M365ReportError("Managed identity did not return a Microsoft Graph token")
        self._token = (value, int(getattr(token, "expires_on", now + 300)))
        return value

    def _request(self, method: str, url: str, **kwargs):
        headers = dict(kwargs.pop("headers", {}))
        headers["Authorization"] = f"Bearer {self._graph_token()}"
        headers.setdefault("Accept", "application/json")
        for attempt in range(1, self.config.retries + 1):
            try:
                response = self.client.request(method, url, headers=headers, **kwargs)
            except (httpx.TimeoutException, httpx.TransportError) as exc:
                if attempt == self.config.retries:
                    raise M365ReportError("Microsoft 365 report request failed") from exc
                self.sleeper(min(2 ** (attempt - 1), 4))
                continue
            if response.status_code not in (429, 500, 502, 503, 504):
                return response
            if attempt == self.config.retries:
                return response
            retry_after = response.headers.get("Retry-After", "")
            delay = int(retry_after) if retry_after.isdigit() else min(2 ** (attempt - 1), 4)
            self.sleeper(min(delay, 10))
        raise M365ReportError("Microsoft 365 report request failed")

    def _content_url(self, filename: str) -> str:
        encoded = quote(filename, safe="")
        return (
            f"{GRAPH_ROOT}/drives/{self.config.drive_id}/items/"
            f"{self.config.folder_item_id}:/{encoded}:/content"
        )

    def upload(self, filename: str, content: bytes) -> dict[str, Any]:
        if not filename.endswith(".json") or "/" in filename or "\\" in filename:
            raise M365ReportError("Report filename is invalid")
        if not content or len(content) > self.config.max_file_bytes:
            raise M365ReportError("Report artifact size is invalid")
        response = self._request(
            "PUT",
            self._content_url(filename),
            headers={"Content-Type": "application/json; charset=utf-8"},
            content=content,
        )
        if response.status_code not in (200, 201):
            raise M365ReportError("Microsoft 365 rejected the report artifact")
        payload = response.json()
        item_id = str(payload.get("id", ""))
        if not _IDENTIFIER.fullmatch(item_id):
            raise M365ReportError("Microsoft 365 returned invalid report metadata")
        _LOG.info("report_upload_succeeded item_id=%s bytes=%d", item_id, len(content))
        return {
            "item_id": item_id,
            "name": str(payload.get("name", filename))[:512],
            "size": int(payload.get("size", len(content))),
            "etag": str(payload.get("eTag", ""))[:512],
            "sha256": hashlib.sha256(content).hexdigest(),
        }

    def read(self, filename: str) -> bytes:
        response = self._request("GET", self._content_url(filename))
        if response.status_code in (302, 303, 307, 308):
            location = response.headers.get("Location", "")
            parsed = urlparse(location)
            hostname = (parsed.hostname or "").lower()
            if parsed.scheme != "https" or not hostname.endswith(".sharepoint.com"):
                raise M365ReportError("Microsoft 365 returned an untrusted report download location")
            try:
                response = self.client.get(location, headers={"Accept": "application/octet-stream"})
            except (httpx.TimeoutException, httpx.TransportError) as exc:
                raise M365ReportError("Microsoft 365 report download failed") from exc
        if response.status_code == 404:
            raise M365ReportError("Released report artifact was not found")
        if response.status_code != 200:
            raise M365ReportError("Microsoft 365 report artifact could not be read")
        if len(response.content) > self.config.max_file_bytes:
            raise M365ReportError("Microsoft 365 report artifact exceeds the configured limit")
        return bytes(response.content)


def readiness() -> dict[str, Any]:
    try:
        GovernedM365ReportConfig.from_environment().validate()
        return {"configured": True, "mode": "folder_selected", "read_write": True}
    except Exception:
        return {"configured": False, "mode": "folder_selected", "read_write": True}


def member_safe_artifact(row: dict[str, Any], member_view: Callable[[dict[str, Any]], dict[str, Any]]) -> bytes:
    snapshot = str(row["snapshot_json"])
    if hashlib.sha256(snapshot.encode("utf-8")).hexdigest() != str(row["snapshot_sha256"]):
        raise M365ReportError("Report snapshot failed integrity verification")
    payload = json.loads(snapshot)
    if payload.get("assessment"):
        payload["assessment"] = member_view(payload["assessment"])
    return _canonical_json(payload)


def publish_member_safe_report(row: dict[str, Any], member_view) -> dict[str, Any]:
    content = member_safe_artifact(row, member_view)
    return GovernedM365Reports(GovernedM365ReportConfig.from_environment()).upload(
        report_filename(row), content
    )


def register_m365_reports(app, namespace: dict[str, Any]) -> None:
    Request = namespace["Request"]
    HTTPException = namespace["HTTPException"]
    JSONResponse = namespace["JSONResponse"]
    auth_context = namespace["auth_context"]
    require = namespace["require"]
    db = namespace["db"]
    tenant_id = namespace["tenant_id"]
    assessment_row_for_request = namespace["assessment_row_for_request"]
    member_view = namespace["_member_assessment_view"]
    protected_member_request = namespace["protected_member_request"]

    def require_release_authority(request):
        context = auth_context(request)
        if context.get("role") not in {"System Administrator", "Assessment Director"}:
            raise HTTPException(403, "Report release authority is required")

    def load_row(report_id: int, request):
        conn = db()
        row = conn.execute(
            "SELECT * FROM report_versions WHERE id=? AND tenant_id=?",
            (report_id, tenant_id(request)),
        ).fetchone()
        conn.close()
        if not row:
            raise HTTPException(404, "Report version not found")
        assessment_row_for_request(request, row["assessment_id"])
        if row["status"] != "Released":
            raise HTTPException(404 if protected_member_request(request) else 409, "Released report not found")
        return dict(row)

    def m365_report_status(request):
        require(request, "read")
        require_release_authority(request)
        return readiness()

    m365_report_status.__annotations__["request"] = Request
    app.get("/api/integrations/m365/reports/status", include_in_schema=False)(m365_report_status)

    def publish_report(report_id: int, request):
        require(request, "read")
        require_release_authority(request)
        row = load_row(report_id, request)
        try:
            result = publish_member_safe_report(row, member_view)
        except Exception as exc:
            raise HTTPException(503, "Governed Microsoft 365 report storage is unavailable") from exc
        return {"report_id": report_id, "folder_scoped": True, **result}

    publish_report.__annotations__["request"] = Request
    app.post("/api/integrations/m365/reports/versions/{report_id}", include_in_schema=False)(publish_report)

    def read_report(report_id: int, request):
        require(request, "read")
        row = load_row(report_id, request)
        expected = member_safe_artifact(row, member_view)
        try:
            content = GovernedM365Reports(GovernedM365ReportConfig.from_environment()).read(report_filename(row))
        except Exception as exc:
            raise HTTPException(503, "Governed Microsoft 365 report storage is unavailable") from exc
        if not hashlib.sha256(content).digest() == hashlib.sha256(expected).digest():
            raise HTTPException(409, "Stored report artifact failed integrity verification")
        response = JSONResponse(json.loads(content))
        response.headers["ETag"] = f'"{hashlib.sha256(content).hexdigest()}"'
        response.headers["X-Salus-Report-Status"] = "Released"
        response.headers["X-Salus-Storage-Scope"] = "folder-selected"
        return response

    read_report.__annotations__["request"] = Request
    app.get("/api/integrations/m365/reports/versions/{report_id}", include_in_schema=False)(read_report)
