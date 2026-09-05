#!/usr/bin/env python3
import json
import os
import subprocess
import sys

BASE = {
    "SALUS_POSTGRES_HOST": "salcapa-dev-b48224-pg.postgres.database.azure.com",
    "SALUS_POSTGRES_DATABASE": "salcapa",
    "SALUS_POSTGRES_USER": "salcapa-dev-b48224-identity",
    "SALUS_RUNTIME_IDENTITY_CLIENT_ID": "11111111-1111-4111-8111-111111111111",
    "SALUS_RUNTIME_IDENTITY_OBJECT_ID": "22222222-2222-4222-8222-222222222222",
    "SALUS_BOOTSTRAP_IDENTITY_NAME": "salcapa-dev-b48224-db-bootstrap",
    "SALUS_BOOTSTRAP_IDENTITY_CLIENT_ID": "33333333-3333-4333-8333-333333333333",
    "SALUS_BOOTSTRAP_TENANT_NAME": "Salus Solutions",
    "SALUS_BOOTSTRAP_TENANT_SLUG": "salus",
    "SALUS_BOOTSTRAP_INITIAL_USERS_JSON": json.dumps([{
        "object_id": "44444444-4444-4444-8444-444444444444",
        "username": "marc.duncan",
        "display_name": "Marc Duncan",
        "role": "System Administrator",
        "sensitivity_clearance": "Highly Sensitive",
        "status": "Active",
    }], separators=(",", ":")),
    "SALUS_BOOTSTRAP_VALIDATE_ONLY": "1",
}


def run(env):
    return subprocess.run(
        [sys.executable, "tools/azure_database_bootstrap.py"],
        env={**os.environ, **env}, capture_output=True, text=True,
    )


ok = run(BASE)
if ok.returncode or "SALCAPA_DATABASE_BOOTSTRAP_CONTRACT_PASS" not in ok.stdout:
    raise SystemExit(ok.stderr or ok.stdout)

bad = dict(BASE)
users = json.loads(bad["SALUS_BOOTSTRAP_INITIAL_USERS_JSON"])
users[0]["role"] = "Client Supplied Administrator"
bad["SALUS_BOOTSTRAP_INITIAL_USERS_JSON"] = json.dumps(users)
if run(bad).returncode == 0:
    raise SystemExit("Bootstrap accepted a client-controlled role")

bad = dict(BASE)
bad["SALUS_RUNTIME_IDENTITY_OBJECT_ID"] = "not-a-uuid"
if run(bad).returncode == 0:
    raise SystemExit("Bootstrap accepted an invalid runtime object ID")

bad = dict(BASE)
users = json.loads(bad["SALUS_BOOTSTRAP_INITIAL_USERS_JSON"])
users.append(dict(users[0]))
bad["SALUS_BOOTSTRAP_INITIAL_USERS_JSON"] = json.dumps(users)
if run(bad).returncode == 0:
    raise SystemExit("Bootstrap accepted duplicate identity authority")

print("AZURE_DATABASE_BOOTSTRAP_SMOKE_PASS")
