#!/usr/bin/env python3
"""Fail-closed checks for the governed Microsoft 365 folder connector."""

from __future__ import annotations

import os
import hashlib
from pathlib import Path
import sys
import types

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

# Keep the smoke runnable in the repository bootstrap environment before
# dependencies are installed; production and CI install the pinned packages.
try:
    import httpx  # noqa: F401
except ImportError:
    httpx = types.ModuleType("httpx")
    httpx.Client = lambda *args, **kwargs: None
    httpx.TimeoutException = OSError
    httpx.TransportError = OSError
    sys.modules["httpx"] = httpx
try:
    from azure.identity import ManagedIdentityCredential  # noqa: F401
except ImportError:
    azure = types.ModuleType("azure")
    identity = types.ModuleType("azure.identity")
    identity.ManagedIdentityCredential = lambda *args, **kwargs: None
    azure.identity = identity
    sys.modules["azure"] = azure
    sys.modules["azure.identity"] = identity

from salcapa_m365_intake import (
    GovernedM365Config,
    GovernedM365Intake,
    M365IntakeError,
    register_m365_intake,
)


class Token:
    token = "federated-assertion"
    expires_on = 4_102_444_800


class Credential:
    def get_token(self, scope):
        assert scope == "api://AzureADTokenExchange/.default"
        return Token()


class Response:
    def __init__(self, status, payload=None, content=b"", headers=None):
        self.status_code = status
        self._payload = payload or {}
        self.content = content
        self.headers = headers or {}

    def json(self):
        return self._payload


class Client:
    def __init__(self):
        self.gets = []

    def post(self, url, data):
        assert url == "https://login.microsoftonline.com/11111111-1111-1111-1111-111111111111/oauth2/v2.0/token"
        assert data["client_id"] == "22222222-2222-2222-2222-222222222222"
        assert data["scope"] == "https://graph.microsoft.com/.default"
        assert data["client_assertion"] == "federated-assertion"
        return Response(200, {"access_token": "graph-token", "expires_in": 3600})

    def get(self, url, headers, params=None):
        self.gets.append(url)
        if url.startswith("https://salussolutions.sharepoint.com/"):
            assert "Authorization" not in headers
            assert headers["Accept"] == "application/octet-stream"
            return Response(200, content=b"safe")
        assert headers["Authorization"] == "Bearer graph-token"
        if url.endswith("/01DBTAFUFOLDER0001/children"):
            return Response(200, {"value": [
                {"id": "01DBTAFUNESTEDFILE1", "name": "nested.docx", "size": 4,
                 "file": {"mimeType": "application/vnd.openxmlformats-officedocument.wordprocessingml.document"},
                 "lastModifiedDateTime": "2026-09-18T00:00:00Z",
                 "eTag": "etag-nested-v1", "cTag": "ctag-nested-v1",
                 "createdBy": {"user": {"email": "owner@salus.solutions", "id": "owner-id"}},
                 "lastModifiedBy": {"user": {"displayName": "Approved Owner", "id": "owner-id"}},
                 "webUrl": "https://salussolutions.sharepoint.com/sites/approved/nested/nested.docx"},
                {"id": "01DBTAFUDEEPFOLDER1", "name": "deeper", "size": 0,
                 "folder": {"childCount": 0}},
            ]})
        if url.endswith("/01DBTAFUDEEPFOLDER1/children"):
            return Response(200, {"value": []})
        if url.endswith("/children"):
            return Response(200, {"value": [
                {"id": "01DBTAFUVALIDFILE01", "name": "governed.pdf", "size": 4,
                 "file": {"mimeType": "application/pdf"}, "lastModifiedDateTime": "2026-09-17T00:00:00Z",
                 "eTag": "etag-v1", "cTag": "ctag-v1",
                 "createdBy": {"user": {"email": "owner@salus.solutions", "id": "owner-id"}},
                 "lastModifiedBy": {"user": {"displayName": "Approved Owner", "id": "owner-id"}},
                 "webUrl": "https://salussolutions.sharepoint.com/sites/approved/governed.pdf"},
                {"id": "01DBTAFUFOLDER0001", "name": "nested", "size": 0, "folder": {"childCount": 2}},
                {"id": "01DBTAFUTOOLARGE001", "name": "large.bin", "size": 11,
                 "file": {"mimeType": "application/octet-stream"}},
            ]})
        if url.endswith("/01DBTAFUVALIDFILE01/content"):
            assert headers["If-Match"] == "etag-v1"
            return Response(
                302,
                headers={"Location": (
                    "https://salussolutions.sharepoint.com/"
                    "_layouts/15/download.aspx?UniqueId=test"
                )},
            )
        if url.endswith("/01DBTAFUNESTEDFILE1/content"):
            assert headers["If-Match"] == "etag-nested-v1"
            return Response(
                302,
                headers={"Location": (
                    "https://salussolutions.sharepoint.com/"
                    "_layouts/15/download.aspx?UniqueId=nested"
                )},
            )
        return Response(404)


def main():
    config = GovernedM365Config(
        tenant_id="11111111-1111-1111-1111-111111111111",
        application_client_id="22222222-2222-2222-2222-222222222222",
        managed_identity_client_id="33333333-3333-3333-3333-333333333333",
        drive_id="b!nLoH4rpIs0Ko75C0IRSSqNFy_EdwB-BMgQS848yr84pGrXen1bnSR6zYkxtw-PFF",
        folder_item_id="01DBTAFUO2ZTFI6EP7Q5GZZHXQV435DDBJ",
        max_file_bytes=10,
    )
    client = Client()
    intake = GovernedM365Intake(config, credential=Credential(), client=client)
    files = intake.list_files()
    assert [x["name"] for x in files] == ["governed.pdf", "nested.docx"]
    assert [x["relative_path"] for x in files] == [
        "governed.pdf", "nested/nested.docx",
    ]
    assert intake.read_file("01DBTAFUNESTEDFILE1") == b"safe"
    assert intake.read_file("01DBTAFUVALIDFILE01") == b"safe"
    assert client.gets[-1].startswith("https://salussolutions.sharepoint.com/")
    document = intake.read_document(
        "01DBTAFUVALIDFILE01", access_classification="Restricted"
    )
    assert document.name == "governed.pdf"
    assert document.relative_path == "governed.pdf"
    assert document.sha256 == hashlib.sha256(b"safe").hexdigest()
    assert document.etag == "etag-v1"
    assert document.ctag == "ctag-v1"
    assert document.last_modified == "2026-09-17T00:00:00Z"
    assert document.source_owner == "owner@salus.solutions"
    assert document.source_owner_id == "owner-id"
    assert document.last_modified_by == "Approved Owner"
    assert document.web_url.startswith("https://salussolutions.sharepoint.com/")
    assert document.access_classification == "Restricted"
    try:
        intake.read_document(
            "01DBTAFUVALIDFILE01", access_classification="Public"
        )
    except M365IntakeError as exc:
        assert "classification" in str(exc).lower()
    else:
        raise AssertionError("An unsupported intake classification was accepted")

    class UntrustedRedirectClient(Client):
        def get(self, url, headers, params=None):
            if url.endswith("/children"):
                return super().get(url, headers, params)
            if url.endswith("/01DBTAFUVALIDFILE01/content"):
                return Response(302, headers={"Location": "https://malicious.example/report"})
            raise AssertionError("An untrusted redirect was followed")

    try:
        GovernedM365Intake(
            config,
            credential=Credential(),
            client=UntrustedRedirectClient(),
        ).read_file("01DBTAFUVALIDFILE01")
    except M365IntakeError as exc:
        assert "untrusted" in str(exc).lower()
    else:
        raise AssertionError("An untrusted intake redirect was accepted")
    try:
        intake.read_file("01DBTAFUOUTSIDE0001")
    except M365IntakeError:
        pass
    else:
        raise AssertionError("An item outside the governed folder was accepted")
    assert all("OUTSIDE" not in url for url in client.gets)

    class ShortcutClient(Client):
        def get(self, url, headers, params=None):
            if url.endswith("/children"):
                return Response(200, {"value": [{
                    "id": "01DBTAFUSHORTCUT001",
                    "name": "outside-shortcut",
                    "remoteItem": {"id": "01OUTSIDE"},
                    "folder": {"childCount": 1},
                }]})
            return super().get(url, headers, params)

    try:
        GovernedM365Intake(
            config, credential=Credential(), client=ShortcutClient()
        ).list_files()
    except M365IntakeError as exc:
        assert "shortcut" in str(exc).lower()
    else:
        raise AssertionError("A shortcut outside the governed tree was followed")
    try:
        GovernedM365Config("bad/tenant", "a", "b", "c", "d").validate()
    except M365IntakeError:
        pass
    else:
        raise AssertionError("Invalid identifiers were accepted")

    class Request:
        pass

    class HTTPException(Exception):
        pass

    class App:
        def __init__(self):
            self.routes = {}

        def get(self, path, **kwargs):
            def decorator(function):
                self.routes[path] = function
                return function
            return decorator

    app = App()
    register_m365_intake(app, {
        "Request": Request,
        "HTTPException": HTTPException,
        "auth_context": lambda request: {"role": "System Administrator"},
    })
    assert set(app.routes) == {
        "/api/integrations/m365/intake/status",
        "/api/integrations/m365/intake/files",
    }
    assert all(
        route.__annotations__.get("request") is Request
        for route in app.routes.values()
    )
    print("M365_GOVERNED_INTAKE_PASS")


if __name__ == "__main__":
    main()
