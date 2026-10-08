"""Least-privilege Microsoft 365 intake for the governed SalCAPA folder.

The runtime managed identity is used only as a short-lived federated client assertion.  The
resulting Microsoft Graph token represents the configured SalCAPA application,
which must have an explicit permission on the configured drive folder.
"""

from __future__ import annotations

import os
import re
import time
import hashlib
from dataclasses import dataclass
from typing import Any
from urllib.parse import urlparse

import httpx
from azure.identity import ManagedIdentityCredential


GRAPH_ROOT = "https://graph.microsoft.com/v1.0"
ASSERTION_SCOPE = "api://AzureADTokenExchange/.default"
ASSERTION_TYPE = "urn:ietf:params:oauth:client-assertion-type:jwt-bearer"
_IDENTIFIER = re.compile(r"^[A-Za-z0-9_!.-]{8,256}$")
_ACCESS_CLASSIFICATIONS = {
    "Salus Internal", "Standard", "Restricted", "Sensitive", "Highly Sensitive",
}
_MAX_FOLDER_DEPTH = 20
_MAX_DISCOVERED_ITEMS = 20000
_DEFAULT_MAX_FILE_BYTES = 100 * 1024 * 1024
_MAX_FILE_BYTES = 100 * 1024 * 1024


class M365IntakeError(RuntimeError):
    """A fail-closed Microsoft 365 intake error safe for internal handling."""


class M365RouteError(M365IntakeError):
    """Source has no approved enterprise route within the pending subtree."""


@dataclass(frozen=True)
class GovernedM365Config:
    tenant_id: str
    application_client_id: str
    managed_identity_client_id: str
    drive_id: str
    folder_item_id: str
    max_file_bytes: int = _DEFAULT_MAX_FILE_BYTES

    @classmethod
    def from_environment(cls) -> "GovernedM365Config":
        return cls(
            tenant_id=os.getenv("SALUS_OIDC_TENANT_ID", "").strip(),
            application_client_id=os.getenv("SALUS_OIDC_CLIENT_ID", "").strip(),
            managed_identity_client_id=os.getenv("SALUS_OIDC_MANAGED_IDENTITY_CLIENT_ID", "").strip(),
            drive_id=os.getenv("SALUS_M365_INTAKE_DRIVE_ID", "").strip(),
            folder_item_id=os.getenv("SALUS_M365_INTAKE_FOLDER_ITEM_ID", "").strip(),
            max_file_bytes=int(os.getenv("SALUS_M365_INTAKE_MAX_FILE_BYTES", str(_DEFAULT_MAX_FILE_BYTES))),
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
        if not 1 <= self.max_file_bytes <= _MAX_FILE_BYTES:
            raise M365IntakeError("Microsoft 365 intake size limit is invalid")


@dataclass(frozen=True)
class GovernedM365Document:
    """Exact source bytes bound to governed Microsoft 365 provenance."""

    item_id: str
    name: str
    content: bytes
    size: int
    mime_type: str
    sha256: str
    etag: str
    ctag: str
    last_modified: str
    source_owner: str
    source_owner_id: str
    last_modified_by: str
    web_url: str
    access_classification: str
    relative_path: str = ""


class GovernedM365Intake:
    def __init__(self, config: GovernedM365Config, *, credential=None, client=None):
        config.validate()
        self.config = config
        self.credential = credential or ManagedIdentityCredential(
            client_id=config.managed_identity_client_id
        )
        self.client = client or httpx.Client(timeout=15.0, follow_redirects=False)
        self._token: tuple[str, int] | None = None
        self._listed_folder_ids: set[str] = set()
        self._listed_items: dict[str, dict[str, Any]] = {}
        self._oversize_items: list[dict[str, Any]] = []
        self._pending_folder_id = ""

    @property
    def oversize_items(self) -> list[dict[str, Any]]:
        """Metadata only; oversized source bytes are never read by this scanner."""
        return [item.copy() for item in self._oversize_items]

    @property
    def pending_folder_id(self) -> str:
        return self._pending_folder_id

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

    @staticmethod
    def _identity(value: Any) -> tuple[str, str]:
        if not isinstance(value, dict):
            return "", ""
        principal = value.get("user") or value.get("application") or {}
        if not isinstance(principal, dict):
            return "", ""
        label = str(principal.get("email") or principal.get("displayName") or "")[:320]
        identifier = str(principal.get("id") or "")[:256]
        return label, identifier

    @staticmethod
    def _trusted_source_url(value: Any) -> str:
        url = str(value or "")[:2048]
        if not url:
            return ""
        parsed = urlparse(url)
        hostname = (parsed.hostname or "").lower()
        if (
            parsed.scheme != "https"
            or parsed.username is not None
            or parsed.password is not None
            or not hostname.endswith(".sharepoint.com")
        ):
            raise M365IntakeError("Microsoft 365 returned an untrusted source location")
        return url

    @staticmethod
    def _safe_path_component(value: Any) -> str:
        name = str(value or "")[:512]
        if not name or name in {".", ".."} or "/" in name or "\\" in name:
            raise M365IntakeError(
                "Governed Microsoft 365 response contained an invalid path component"
            )
        return name

    def list_files(self, *, pending_only: bool = False, processed_only: bool = False, max_files: int | None = None) -> list[dict[str, Any]]:
        """List bounded files; optionally select a finite pending batch window."""
        if max_files is not None and (
            not (pending_only or processed_only)
            or not isinstance(max_files, int)
            or not 1 <= max_files <= 1000
        ):
            raise ValueError("A bounded file window requires one intake subtree")
        if pending_only and processed_only:
            raise ValueError("Only one intake subtree can be selected")
        select = (
            "id,name,size,file,folder,remoteItem,lastModifiedDateTime,eTag,cTag,"
            "createdBy,lastModifiedBy,webUrl,parentReference"
        )
        folders: list[tuple[str, str, int]] = [
            (self.config.folder_item_id, "", 0)
        ]
        visited_folders: set[str] = set()
        visited_items: set[str] = set()
        result: list[dict[str, Any]] = []
        discovered = 0
        self._oversize_items = []
        self._pending_folder_id = ""

        while folders:
            folder_id, folder_path, depth = folders.pop(0)
            if folder_id in visited_folders:
                raise M365IntakeError(
                    "Governed Microsoft 365 folder traversal contained a cycle"
                )
            visited_folders.add(folder_id)
            url = (
                f"{GRAPH_ROOT}/drives/{self.config.drive_id}/items/"
                f"{folder_id}/children"
            )
            page_url = url
            page_params = {"$select": select, "$top": "200"}
            visited_pages: set[str] = set()
            folder_items: list[dict[str, Any]] = []
            while page_url:
                if page_url in visited_pages or len(visited_pages) >= _MAX_DISCOVERED_ITEMS:
                    raise M365IntakeError("Governed Microsoft 365 folder pagination contained a cycle")
                visited_pages.add(page_url)
                response = self.client.get(
                    page_url, headers=self._headers(), params=page_params,
                )
                if response.status_code != 200:
                    raise M365IntakeError("Governed Microsoft 365 folder could not be read")
                payload = response.json()
                values = payload.get("value")
                if not isinstance(values, list):
                    raise M365IntakeError("Governed Microsoft 365 response was incomplete")
                if discovered + len(folder_items) + len(values) > _MAX_DISCOVERED_ITEMS:
                    raise M365IntakeError("Governed Microsoft 365 intake exceeds the traversal limit")
                folder_items.extend(values)
                next_link = payload.get("@odata.nextLink")
                if next_link:
                    if (
                        not isinstance(next_link, str)
                        or len(next_link) > 8192
                        or not next_link.startswith(url + "?")
                        or urlparse(next_link).fragment
                        or urlparse(next_link).username is not None
                        or urlparse(next_link).password is not None
                    ):
                        raise M365IntakeError("Governed Microsoft 365 pagination link was invalid")
                    page_url = next_link
                    page_params = None
                else:
                    page_url = ""

            for item in folder_items:
                discovered += 1
                if discovered > _MAX_DISCOVERED_ITEMS:
                    raise M365IntakeError(
                        "Governed Microsoft 365 intake exceeds the traversal limit"
                    )
                if not isinstance(item, dict):
                    raise M365IntakeError(
                        "Governed Microsoft 365 response contained an invalid item"
                    )
                if "remoteItem" in item:
                    raise M365IntakeError(
                        "Governed Microsoft 365 intake cannot follow shortcuts"
                    )
                item_id = str(item.get("id", ""))
                if not _IDENTIFIER.fullmatch(item_id):
                    raise M365IntakeError(
                        "Governed Microsoft 365 response contained an invalid item"
                    )
                # Concurrent moves can repeat an item at a Graph page boundary.
                # Keep one occurrence; the next scan and If-Match reconcile moves.
                if item_id in visited_items:
                    continue
                visited_items.add(item_id)
                name = self._safe_path_component(item.get("name"))
                relative_path = f"{folder_path}/{name}" if folder_path else name

                if "folder" in item:
                    if "file" in item or not isinstance(item.get("folder"), dict):
                        raise M365IntakeError(
                            "Governed Microsoft 365 response contained an invalid folder"
                        )
                    if depth >= _MAX_FOLDER_DEPTH:
                        raise M365IntakeError(
                            "Governed Microsoft 365 intake exceeds the folder depth limit"
                        )
                    if not folder_path and (
                        (pending_only and name != "10 Pending Classification")
                        or (processed_only and name != "90 Processed Intake")
                    ):
                        continue
                    if pending_only and not folder_path:
                        self._pending_folder_id = item_id
                    folders.append((item_id, relative_path, depth + 1))
                    continue
                if "file" not in item:
                    continue

                size = int(item.get("size", -1))
                if size < 0:
                    raise M365IntakeError("Governed Microsoft 365 item size was invalid")
                etag = str(item.get("eTag", ""))[:512]
                last_modified = str(item.get("lastModifiedDateTime", ""))[:64]
                if not etag or not last_modified:
                    raise M365IntakeError(
                        "Governed Microsoft 365 item provenance was incomplete"
                    )
                source_owner, source_owner_id = self._identity(item.get("createdBy"))
                last_modified_by, _ = self._identity(item.get("lastModifiedBy"))
                record = {
                    "id": item_id,
                    "parent_id": folder_id,
                    "name": name,
                    "relative_path": relative_path,
                    "size": size,
                    "mime_type": str(item.get("file", {}).get("mimeType", ""))[:255],
                    "last_modified": last_modified,
                    "etag": etag,
                    "ctag": str(item.get("cTag", ""))[:512],
                    "source_owner": source_owner,
                    "source_owner_id": source_owner_id,
                    "last_modified_by": last_modified_by,
                    "web_url": self._trusted_source_url(item.get("webUrl")),
                }
                if size > self.config.max_file_bytes:
                    self._oversize_items.append(record)
                    continue
                result.append(record)
                if max_files is not None and len(result) >= max_files:
                    folders.clear()
                    break
        self._listed_folder_ids = visited_folders
        self._listed_items = {row["id"]: row.copy() for row in result}
        return result

    def read_listed_document(
        self, item: dict[str, Any], *, access_classification: str
    ) -> GovernedM365Document:
        """Read an item from a governed listing after verifying its current parent."""
        if access_classification not in _ACCESS_CLASSIFICATIONS:
            raise M365IntakeError("Microsoft 365 intake access classification is invalid")
        item_id = str(item.get("id", ""))
        if not _IDENTIFIER.fullmatch(item_id):
            raise M365IntakeError("Governed Microsoft 365 response contained an invalid item")
        response = self.client.get(
            f"{GRAPH_ROOT}/drives/{self.config.drive_id}/items/{item_id}",
            headers=self._headers(),
            params={"$select": "id,name,size,eTag,parentReference,file"},
        )
        if response.status_code != 200:
            raise M365IntakeError("Governed Microsoft 365 item could not be read")
        current = response.json()
        parent = current.get("parentReference") or {}
        if (
            current.get("id") != item_id
            or current.get("name") != item["name"]
            or current.get("eTag") != item["etag"]
            or current.get("size") != item["size"]
            or parent.get("id") not in self._listed_folder_ids
            or self._listed_items.get(item_id) != item
        ):
            raise M365IntakeError("Governed Microsoft 365 item changed after listing")
        content = self._read_allowed_item(item)
        return GovernedM365Document(
            item_id=item_id, name=item["name"], relative_path=item["relative_path"],
            content=content, size=item["size"], mime_type=item["mime_type"],
            sha256=hashlib.sha256(content).hexdigest(), etag=item["etag"],
            ctag=item["ctag"], last_modified=item["last_modified"],
            source_owner=item["source_owner"], source_owner_id=item["source_owner_id"],
            last_modified_by=item["last_modified_by"], web_url=item["web_url"],
            access_classification=access_classification,
        )

    def verify_sibling_folder(self, pending_folder_id: str, customer_folder_id: str) -> bool:
        """Fail closed unless the customer source is a separate live sibling."""
        if (not _IDENTIFIER.fullmatch(pending_folder_id)
                or not _IDENTIFIER.fullmatch(customer_folder_id)
                or pending_folder_id == customer_folder_id):
            return False
        endpoint = f"{GRAPH_ROOT}/drives/{self.config.drive_id}/items/"
        parents = []
        for item_id in (pending_folder_id, customer_folder_id):
            response = self.client.get(
                endpoint + item_id, headers=self._headers(),
                params={"$select": "id,name,parentReference,folder,remoteItem"},
            )
            if response.status_code != 200:
                return False
            item = response.json()
            parent = str((item.get("parentReference") or {}).get("id", ""))
            if (item.get("id") != item_id or "folder" not in item
                    or "remoteItem" in item or not _IDENTIFIER.fullmatch(parent)):
                return False
            parents.append(parent)
        return parents[0] == parents[1]

    def read_scoped_document(
        self, item: dict[str, Any], *, pending_folder_id: str,
        required_ancestor_id: str | None = None,
        access_classification: str = "Salus Internal",
    ) -> GovernedM365Document:
        """Read a delta-ledger item after rechecking its live pending-folder ancestry.

        A delta row alone does not authorize source bytes: items can move out of
        the granted subtree between discovery and work. The source ETag and every
        ancestor are checked before the content request, which uses If-Match.
        """
        if access_classification not in _ACCESS_CLASSIFICATIONS:
            raise M365IntakeError("Microsoft 365 intake access classification is invalid")
        item_id = str(item.get("id", ""))
        if not _IDENTIFIER.fullmatch(item_id) or not _IDENTIFIER.fullmatch(pending_folder_id):
            raise M365IntakeError("Governed Microsoft 365 item identity is invalid")
        if required_ancestor_id is not None and (
            not _IDENTIFIER.fullmatch(required_ancestor_id)
            or required_ancestor_id == pending_folder_id
        ):
            raise M365IntakeError("Approved enterprise source route is invalid")
        if item_id == pending_folder_id:
            raise M365IntakeError("Pending directory cannot be read as a file")
        expected_size = int(item.get("size", -1))
        if expected_size < 0 or expected_size > self.config.max_file_bytes:
            raise M365IntakeError("Governed Microsoft 365 item exceeds the file-size limit")
        endpoint = f"{GRAPH_ROOT}/drives/{self.config.drive_id}/items/"
        response = self.client.get(
            endpoint + item_id, headers=self._headers(),
            params={"$select": "id,name,size,eTag,parentReference,file,remoteItem"},
        )
        if response.status_code != 200:
            raise M365IntakeError("Governed Microsoft 365 item could not be read")
        current = response.json()
        parent = str((current.get("parentReference") or {}).get("id", ""))
        if (
            current.get("id") != item_id or "file" not in current
            or "remoteItem" in current or not _IDENTIFIER.fullmatch(parent)
            or current.get("name") != item.get("name")
            or current.get("eTag") != item.get("etag")
            or current.get("size") != expected_size
            or parent != item.get("parent_id")
        ):
            raise M365IntakeError("Governed Microsoft 365 item changed after discovery")
        names = [self._safe_path_component(item["name"])]
        seen = {item_id}
        routed = parent == required_ancestor_id
        while parent != pending_folder_id:
            if parent in seen or len(seen) > 128:
                raise M365IntakeError("Governed Microsoft 365 folder ancestry is invalid")
            seen.add(parent)
            ancestor = self.client.get(
                endpoint + parent, headers=self._headers(),
                params={"$select": "id,name,parentReference,folder,remoteItem"},
            )
            if ancestor.status_code != 200:
                raise M365IntakeError("Governed Microsoft 365 folder ancestry could not be verified")
            folder = ancestor.json()
            next_parent = str((folder.get("parentReference") or {}).get("id", ""))
            if (folder.get("id") != parent or "folder" not in folder
                    or "remoteItem" in folder or not _IDENTIFIER.fullmatch(next_parent)):
                raise M365IntakeError("Governed Microsoft 365 folder left the pending subtree")
            names.append(self._safe_path_component(folder.get("name")))
            parent = next_parent
            routed = routed or parent == required_ancestor_id
        if required_ancestor_id is not None and not routed:
            raise M365RouteError("Source has no approved enterprise route")
        path = "10 Pending Classification/" + "/".join(reversed(names))
        verified = dict(item, relative_path=path)
        content = self._read_allowed_item(verified)
        return GovernedM365Document(
            item_id=item_id, name=item["name"], relative_path=path,
            content=content, size=expected_size, mime_type=item["mime_type"],
            sha256=hashlib.sha256(content).hexdigest(), etag=item["etag"],
            ctag=item["ctag"], last_modified=item["last_modified"],
            source_owner=item["source_owner"], source_owner_id=item["source_owner_id"],
            last_modified_by=item["last_modified_by"], web_url=item["web_url"],
            access_classification=access_classification,
        )

    def read_file(self, item_id: str) -> bytes:
        allowed = {item["id"]: item for item in self.list_files()}
        item = allowed.get(item_id)
        if item is None:
            raise M365IntakeError("Microsoft 365 item is outside the governed intake folder")
        return self._read_allowed_item(item)

    def _read_allowed_item(self, item: dict[str, Any]) -> bytes:
        item_id = item["id"]
        response = self.client.get(
            f"{GRAPH_ROOT}/drives/{self.config.drive_id}/items/{item_id}/content",
            headers={
                "Authorization": f"Bearer {self._graph_token()}",
                "If-Match": item["etag"],
            },
        )
        if response.status_code in (302, 303, 307, 308):
            location = response.headers.get("Location", "")
            parsed = urlparse(location)
            hostname = (parsed.hostname or "").lower()
            if (
                parsed.scheme != "https"
                or parsed.username is not None
                or parsed.password is not None
                or not hostname.endswith(".sharepoint.com")
            ):
                raise M365IntakeError(
                    "Microsoft 365 returned an untrusted intake download location"
                )
            try:
                response = self.client.get(
                    location,
                    headers={"Accept": "application/octet-stream"},
                )
            except (httpx.TimeoutException, httpx.TransportError) as exc:
                raise M365IntakeError("Microsoft 365 intake download failed") from exc
        if response.status_code != 200:
            raise M365IntakeError("Governed Microsoft 365 item could not be read")
        if len(response.content) != item["size"] or len(response.content) > self.config.max_file_bytes:
            raise M365IntakeError("Governed Microsoft 365 item size did not match metadata")
        return bytes(response.content)

    def read_document(
        self, item_id: str, *, access_classification: str
    ) -> GovernedM365Document:
        """Read one governed-subtree file and bind its bytes to source provenance."""
        if access_classification not in _ACCESS_CLASSIFICATIONS:
            raise M365IntakeError("Microsoft 365 intake access classification is invalid")
        allowed = {item["id"]: item for item in self.list_files()}
        item = allowed.get(item_id)
        if item is None:
            raise M365IntakeError("Microsoft 365 item is outside the governed intake folder")
        content = self._read_allowed_item(item)
        return GovernedM365Document(
            item_id=item_id,
            name=item["name"],
            relative_path=item["relative_path"],
            content=content,
            size=item["size"],
            mime_type=item["mime_type"],
            sha256=hashlib.sha256(content).hexdigest(),
            etag=item["etag"],
            ctag=item["ctag"],
            last_modified=item["last_modified"],
            source_owner=item["source_owner"],
            source_owner_id=item["source_owner_id"],
            last_modified_by=item["last_modified_by"],
            web_url=item["web_url"],
            access_classification=access_classification,
        )


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
