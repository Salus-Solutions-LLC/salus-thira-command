"""Least-privilege Microsoft 365 intake for the governed SalCAPA folder.

The runtime managed identity is used only as a short-lived federated client assertion.  The
resulting Microsoft Graph token represents the configured SalCAPA application,
which must have an explicit permission on the configured drive folder.
"""

from __future__ import annotations

import os
import re
import time
from dataclasses import dataclass
from typing import Any
from urllib.parse import urlparse

import httpx
from azure.identity import ManagedIdentityCredential


GRAPH_ROOT = "https://graph.microsoft.com/v1.0"
ASSERTION_SCOPE = "api://AzureADTokenExchange/.default"
ASSERTION_TYPE = "urn:ietf:params:oauth:client-assertion-type:jwt-bearer"
_IDENTIFIER = re.compile(r"^[A-Za-z0-9_!.-]{8,256}$")


class M365IntakeError(RuntimeError):
    """A fail-closed Microsoft 365 intake error safe for internal handling."""


@dataclass(frozen=True)
class GovernedM365Config:
    tenant_id: str
    application_client_id: str
    managed_identity_client_id: str
    drive_id: str
    folder_item_id: str
    max_file_bytes: int = 25 * 1024 * 1024

    @classmethod
    def from_environment(cls) -> "GovernedM365Config":
        return cls(
            tenant_id=os.getenv("SALUS_OIDC_TENANT_ID", "").strip(),
            application_client_id=os.getenv("SALUS_OIDC_CLIENT_ID", "").strip(),
            managed_identity_client_id=os.getenv("SALUS_OIDC_MANAGED_IDENTITY_CLIENT_ID", "").strip(),
            drive_id=os.getenv("SALUS_M365_INTAKE_DRIVE_ID", "").strip(),
            folder_item_id=os.getenv("SALUS_M365_INTAKE_FOLDER_ITEM_ID", "").strip(),
            max_file_bytes=int(os.getenv("SALUS_M365_INTAKE_MAX_FILE_BYTES", str(25 * 1024 * 1024))),
        )

    def validate(self) -> None:
        values = {
            "tenant": self.tenant_id,
            "application": self.application_client_id,
            "managed identity": self.managed_identity_client_id,
            "drive": self.drive_id,
            "folder": self.folder_item_id,
        }
        if any(not _IDENTIFIER.fullmatch(value) for value in values.values()):
            raise M365IntakeError("Microsoft 365 intake identifiers are incomplete or invalid")
        if not 1 <= self.max_file_bytes <= 100 * 1024 * 1024:
            raise M365IntakeError("Microsoft 365 intake size limit is invalid")


class GovernedM365Intake:
    def __init__(self, config: GovernedM365Config, *, credential=None, client=None):
        config.validate()
        self.config = config
        self.credential = credential or ManagedIdentityCredential(
            client_id=config.managed_identity_client_id
        )
        self.client = client or httpx.Client(timeout=15.0, follow_redirects=False)
        self._token: tuple[str, int] | None = None

    def _graph_token(self) -> str:
        now = int(time.time())
        if self._token and self._token[1] > now + 60:
            return self._token[0]
        assertion = self.credential.get_token(ASSERTION_SCOPE)
        assertion_value = str(getattr(assertion, "token", "") or "")
        if not assertion_value:
            raise M365IntakeError("Managed identity did not return a client assertion")
        response = self.client.post(
            f"https://login.microsoftonline.com/{self.config.tenant_id}/oauth2/v2.0/token",
            data={
                "client_id": self.config.application_client_id,
                "scope": "https://graph.microsoft.com/.default",
                "grant_type": "client_credentials",
                "client_assertion_type": ASSERTION_TYPE,
                "client_assertion": assertion_value,
            },
        )
        if response.status_code != 200:
            raise M365IntakeError("Microsoft 365 token exchange was rejected")
        payload = response.json()
        token = str(payload.get("access_token", ""))
        if not token:
            raise M365IntakeError("Microsoft 365 token response was incomplete")
        expires = now + min(max(int(payload.get("expires_in", 300)), 120), 3600)
        self._token = (token, expires)
        return token

    def _headers(self) -> dict[str, str]:
        return {"Authorization": f"Bearer {self._graph_token()}", "Accept": "application/json"}

    def list_files(self) -> list[dict[str, Any]]:
        url = (
            f"{GRAPH_ROOT}/drives/{self.config.drive_id}/items/"
            f"{self.config.folder_item_id}/children"
        )
        params = {
            "$select": "id,name,size,file,folder,lastModifiedDateTime,eTag,parentReference",
            "$top": "200",
        }
        response = self.client.get(url, headers=self._headers(), params=params)
        if response.status_code != 200:
            raise M365IntakeError("Governed Microsoft 365 folder could not be read")
        payload = response.json()
        if payload.get("@odata.nextLink"):
            raise M365IntakeError("Governed Microsoft 365 folder exceeds the bounded intake page")
        values = payload.get("value")
        if not isinstance(values, list):
            raise M365IntakeError("Governed Microsoft 365 response was incomplete")
        result = []
        for item in values:
            if not isinstance(item, dict) or "file" not in item or "folder" in item:
                continue
            item_id = str(item.get("id", ""))
            if not _IDENTIFIER.fullmatch(item_id):
                raise M365IntakeError("Governed Microsoft 365 response contained an invalid item")
            size = int(item.get("size", -1))
            if size < 0 or size > self.config.max_file_bytes:
                continue
            result.append({
                "id": item_id,
                "name": str(item.get("name", ""))[:512],
                "size": size,
                "mime_type": str(item.get("file", {}).get("mimeType", ""))[:255],
                "last_modified": str(item.get("lastModifiedDateTime", ""))[:64],
                "etag": str(item.get("eTag", ""))[:512],
            })
        return result

    def read_file(self, item_id: str) -> bytes:
        allowed = {item["id"]: item for item in self.list_files()}
        item = allowed.get(item_id)
        if item is None:
            raise M365IntakeError("Microsoft 365 item is outside the governed intake folder")
        response = self.client.get(
            f"{GRAPH_ROOT}/drives/{self.config.drive_id}/items/{item_id}/content",
            headers={"Authorization": f"Bearer {self._graph_token()}"},
        )
        if response.status_code != 200:
            raise M365IntakeError("Governed Microsoft 365 item could not be read")
        if len(response.content) != item["size"] or len(response.content) > self.config.max_file_bytes:
            raise M365IntakeError("Governed Microsoft 365 item size did not match metadata")
        return bytes(response.content)


def readiness() -> dict[str, Any]:
    try:
        config = GovernedM365Config.from_environment()
        config.validate()
        return {"configured": True, "mode": "folder_selected", "read_only": True}
    except Exception:
        return {"configured": False, "mode": "folder_selected", "read_only": True}


def register_m365_intake(app, namespace: dict[str, Any]) -> None:
    """Register Salus-administrator-only connector verification routes."""
    Request = namespace["Request"]
    HTTPException = namespace["HTTPException"]
    auth_context = namespace["auth_context"]

    def require_admin(request):
        context = auth_context(request)
        if context.get("role") != "System Administrator":
            raise HTTPException(403, "System Administrator authority is required")
        return context

    def m365_intake_status(request):
        require_admin(request)
        status = readiness()
        if not status["configured"]:
            return status | {"accessible": False, "file_count": 0}
        try:
            files = GovernedM365Intake(GovernedM365Config.from_environment()).list_files()
            return status | {"accessible": True, "file_count": len(files)}
        except Exception:
            return status | {"accessible": False, "file_count": 0}

    # Request is supplied by the host application. Bind the concrete class
    # before FastAPI inspects the route; postponed annotations cannot resolve a
    # function-local alias and otherwise expose request as a query field.
    m365_intake_status.__annotations__["request"] = Request
    app.get("/api/integrations/m365/intake/status", include_in_schema=False)(
        m365_intake_status
    )

    def m365_intake_files(request):
        require_admin(request)
        try:
            files = GovernedM365Intake(GovernedM365Config.from_environment()).list_files()
        except Exception as exc:
            raise HTTPException(503, "Governed Microsoft 365 intake is unavailable") from exc
        return {"items": files, "count": len(files), "read_only": True}

    m365_intake_files.__annotations__["request"] = Request
    app.get("/api/integrations/m365/intake/files", include_in_schema=False)(
        m365_intake_files
    )
