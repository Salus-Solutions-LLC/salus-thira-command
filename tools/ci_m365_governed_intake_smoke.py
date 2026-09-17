#!/usr/bin/env python3
"""Fail-closed checks for the governed Microsoft 365 folder connector."""

from __future__ import annotations

import os
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

from salcapa_m365_intake import GovernedM365Config, GovernedM365Intake, M365IntakeError


class Token:
    token = "federated-assertion"
    expires_on = 4_102_444_800


class Credential:
    def get_token(self, scope):
        assert scope == "api://AzureADTokenExchange/.default"
        return Token()


class Response:
    def __init__(self, status, payload=None, content=b""):
        self.status_code = status
        self._payload = payload or {}
        self.content = content

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
        assert headers["Authorization"] == "Bearer graph-token"
        self.gets.append(url)
        if url.endswith("/children"):
            return Response(200, {"value": [
                {"id": "01DBTAFUVALIDFILE01", "name": "governed.pdf", "size": 4,
                 "file": {"mimeType": "application/pdf"}, "lastModifiedDateTime": "2026-09-17T00:00:00Z", "eTag": "etag"},
                {"id": "01DBTAFUFOLDER0001", "name": "nested", "size": 0, "folder": {"childCount": 1}},
                {"id": "01DBTAFUTOOLARGE001", "name": "large.bin", "size": 11, "file": {"mimeType": "application/octet-stream"}},
            ]})
        if url.endswith("/01DBTAFUVALIDFILE01/content"):
            return Response(200, content=b"safe")
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
    assert [x["name"] for x in intake.list_files()] == ["governed.pdf"]
    assert intake.read_file("01DBTAFUVALIDFILE01") == b"safe"
    try:
        intake.read_file("01DBTAFUOUTSIDE0001")
    except M365IntakeError:
        pass
    else:
        raise AssertionError("An item outside the governed folder was accepted")
    assert all("OUTSIDE" not in url for url in client.gets)
    try:
        GovernedM365Config("bad/tenant", "a", "b", "c", "d").validate()
    except M365IntakeError:
        pass
    else:
        raise AssertionError("Invalid identifiers were accepted")
    print("M365_GOVERNED_INTAKE_PASS")


if __name__ == "__main__":
    main()
