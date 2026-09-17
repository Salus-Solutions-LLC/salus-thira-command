#!/usr/bin/env python3
"""Regression checks for passwordless runtime initialization."""

from __future__ import annotations

import importlib
import os
import sys
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def reset(name: str):
    sys.modules.pop(name, None)
    return importlib.import_module(name)


def main() -> None:
    os.environ.update(
        {
            "SALUS_DB_BACKEND": "postgres",
            "SALUS_POSTGRES_AUTH": "entra",
            "SALUS_POSTGRES_HOST": "salcapa.example.postgres.database.azure.com",
            "SALUS_POSTGRES_DATABASE": "salcapa",
            "SALUS_POSTGRES_USER": "salcapa-runtime",
            "SALUS_STORAGE_BACKEND": "azure",
            "SALUS_AZURE_STORAGE_ACCOUNT_URL": "https://salcapaexample.blob.core.windows.net/",
            "SALUS_AZURE_STORAGE_CONTAINER": "evidence",
            "SALUS_OIDC_CLIENT_AUTH_METHOD": "managed_identity",
            "AZURE_CLIENT_ID": "00000000-0000-0000-0000-000000000001",
        }
    )
    for name in ("SALUS_DATABASE_URL", "SALUS_POSTGRES_DSN", "SALUS_AZURE_STORAGE_CONNECTION_STRING", "SALUS_OIDC_CLIENT_SECRET"):
        os.environ.pop(name, None)

    with patch("secret_provider.secret", side_effect=AssertionError("PostgreSQL Entra path requested a DSN secret")):
        database = reset("database")
    assert database.DATABASE_URL == ""

    managed_database = reset("managed_database")
    with patch.object(managed_database, "secret", side_effect=AssertionError("Managed database Entra path requested a DSN secret")):
        assert managed_database._postgres_dsn() == ""

    storage = reset("storage")
    with (
        patch.object(storage, "secret", side_effect=AssertionError("Managed storage path requested a connection-string secret")),
        patch.object(storage, "AzureBlobStorage") as azure_storage,
    ):
        storage.build_storage("/tmp/salcapa-passwordless-runtime")
    azure_storage.assert_called_once_with(
        "",
        "evidence",
        "https://salcapaexample.blob.core.windows.net/",
    )

    app_source = Path("app.py").read_text()
    method_line = "OIDC_CLIENT_AUTH_METHOD = os.getenv('SALUS_OIDC_CLIENT_AUTH_METHOD','client_secret').strip().lower()"
    secret_line = "else secret('SALUS_OIDC_CLIENT_SECRET','').strip()"
    assert method_line in app_source and secret_line in app_source
    assert app_source.index(method_line) < app_source.index(secret_line)
    assert "if OIDC_CLIENT_AUTH_METHOD == 'managed_identity'" in app_source
    infrastructure_source = Path("infra/azure/main.bicep").read_text()
    assert "name: 'AZURE_CLIENT_ID'" in infrastructure_source
    assert "value: workloadIdentity.properties.clientId" in infrastructure_source
    assert "var runtimeRedirectUri = environmentName == 'dev' ? 'https://salcapa.salus.solutions/api/auth/oidc/callback'" in infrastructure_source
    assert "value: runtimeRedirectUri" in infrastructure_source
    assert "output runtimeRedirectUri string = runtimeRedirectUri" in infrastructure_source
    app_ui_source = Path("static/app.js").read_text()
    assert '<a class="btn" id="oidc-login" href="/api/auth/oidc/start">Sign in with SSO</a>' in app_ui_source
    assert "$('#oidc-login').onclick" not in app_ui_source
    print("PASSWORDLESS_RUNTIME_SECRET_PATHS_PASS")


if __name__ == "__main__":
    main()
