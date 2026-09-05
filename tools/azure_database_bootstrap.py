#!/usr/bin/env python3
"""One-time, passwordless SalCAPA Azure PostgreSQL bootstrap.

This command is intended only for the governed transient Container Apps Job.  It
uses a short-lived PostgreSQL administrator managed identity to create the
normal runtime identity role, then initializes schema and pre-provisions exact
Microsoft Entra object-ID mappings under the runtime identity.
"""

from __future__ import annotations

import json
import os
import re
import uuid
from datetime import datetime, timezone

ALLOWED_ROLES = {
    "System Administrator",
    "Assessment Director",
    "Lead Assessor",
    "SME Assessor",
    "Client Executive",
    "Program Owner",
    "Contributor",
    "Auditor",
}
ALLOWED_CLEARANCES = {"Standard", "Restricted", "Sensitive", "Highly Sensitive"}
ALLOWED_STATUSES = {"Active", "Disabled"}
SAFE_NAME = re.compile(r"^[a-z][a-z0-9-]{2,62}$")
SAFE_SLUG = re.compile(r"^[a-z][a-z0-9-]{1,62}$")
SAFE_USERNAME = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._@+-]{1,159}$")


def required(name: str) -> str:
    value = os.getenv(name, "").strip()
    if not value:
        raise RuntimeError(f"Missing required environment variable: {name}")
    return value


def exact_uuid(value: str, field: str) -> str:
    try:
        parsed = uuid.UUID(value)
    except (ValueError, AttributeError) as exc:
        raise RuntimeError(f"{field} must be an exact UUID") from exc
    normalized = str(parsed)
    if value.lower() != normalized:
        raise RuntimeError(f"{field} must use canonical UUID form")
    return normalized


def load_contract() -> dict:
    tenant = {
        "name": required("SALUS_BOOTSTRAP_TENANT_NAME"),
        "slug": required("SALUS_BOOTSTRAP_TENANT_SLUG"),
    }
    if len(tenant["name"]) > 160 or not SAFE_SLUG.fullmatch(tenant["slug"]):
        raise RuntimeError("Invalid governed tenant mapping")
    try:
        users = json.loads(required("SALUS_BOOTSTRAP_INITIAL_USERS_JSON"))
    except json.JSONDecodeError as exc:
        raise RuntimeError("Initial identity mappings must be valid JSON") from exc
    if not isinstance(users, list) or not 1 <= len(users) <= 20:
        raise RuntimeError("Initial identity mappings must contain 1-20 users")
    seen_subjects: set[str] = set()
    seen_usernames: set[str] = set()
    normalized_users = []
    expected_keys = {
        "object_id", "username", "display_name", "role",
        "sensitivity_clearance", "status",
    }
    for item in users:
        if not isinstance(item, dict) or set(item) != expected_keys:
            raise RuntimeError("Each initial identity mapping must use the exact governed schema")
        subject = exact_uuid(str(item["object_id"]), "object_id")
        username = str(item["username"]).strip()
        display_name = str(item["display_name"]).strip()
        role = str(item["role"]).strip()
        clearance = str(item["sensitivity_clearance"]).strip()
        status = str(item["status"]).strip()
        if not SAFE_USERNAME.fullmatch(username) or len(display_name) < 1 or len(display_name) > 160:
            raise RuntimeError("Invalid governed user identity fields")
        if role not in ALLOWED_ROLES or clearance not in ALLOWED_CLEARANCES or status not in ALLOWED_STATUSES:
            raise RuntimeError("Invalid server-controlled role, clearance, or lifecycle state")
        if subject in seen_subjects or username.lower() in seen_usernames:
            raise RuntimeError("Duplicate governed identity mapping")
        seen_subjects.add(subject)
        seen_usernames.add(username.lower())
        normalized_users.append({
            "object_id": subject,
            "username": username,
            "display_name": display_name,
            "role": role,
            "sensitivity_clearance": clearance,
            "status": status,
        })
    return {"tenant": tenant, "users": normalized_users}


def runtime_configuration() -> dict:
    cfg = {
        "host": required("SALUS_POSTGRES_HOST"),
        "database": required("SALUS_POSTGRES_DATABASE"),
        "runtime_name": required("SALUS_POSTGRES_USER"),
        "runtime_client_id": exact_uuid(required("SALUS_RUNTIME_IDENTITY_CLIENT_ID"), "runtime_client_id"),
        "runtime_object_id": exact_uuid(required("SALUS_RUNTIME_IDENTITY_OBJECT_ID"), "runtime_object_id"),
        "bootstrap_name": required("SALUS_BOOTSTRAP_IDENTITY_NAME"),
        "bootstrap_client_id": exact_uuid(required("SALUS_BOOTSTRAP_IDENTITY_CLIENT_ID"), "bootstrap_client_id"),
    }
    if not SAFE_NAME.fullmatch(cfg["runtime_name"]) or not SAFE_NAME.fullmatch(cfg["bootstrap_name"]):
        raise RuntimeError("Managed identity names must use the governed Azure naming form")
    if not cfg["host"].endswith(".postgres.database.azure.com"):
        raise RuntimeError("PostgreSQL host is outside the governed Azure service")
    if cfg["database"] != "salcapa":
        raise RuntimeError("Unexpected SalCAPA database name")
    return cfg


def _connect(credential, cfg: dict, *, user: str, database: str):
    import psycopg

    token = credential.get_token(
        "https://ossrdbms-aad.database.windows.net/.default"
    ).token
    return psycopg.connect(
        host=cfg["host"],
        port=5432,
        dbname=database,
        user=user,
        password=token,
        sslmode="require",
        connect_timeout=20,
        autocommit=True,
    )


def create_runtime_role(cfg: dict) -> None:
    from azure.identity import ManagedIdentityCredential
    from psycopg import sql

    credential = ManagedIdentityCredential(client_id=cfg["bootstrap_client_id"])
    with _connect(credential, cfg, user=cfg["bootstrap_name"], database="postgres") as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT 1 FROM pg_catalog.pgaadauth_list_principals(false) "
                "WHERE objectId = %s AND principalType = 'service'",
                (cfg["runtime_object_id"],),
            )
            if cur.fetchone() is None:
                cur.execute(
                    "SELECT * FROM pgaadauth_create_principal_with_oid(%s, %s, 'service', false, false)",
                    (cfg["runtime_name"], cfg["runtime_object_id"]),
                )
            cur.execute(
                sql.SQL("ALTER ROLE {} NOSUPERUSER NOCREATEDB NOCREATEROLE NOREPLICATION").format(
                    sql.Identifier(cfg["runtime_name"])
                )
            )
            cur.execute(
                sql.SQL("GRANT CONNECT, TEMPORARY ON DATABASE {} TO {}").format(
                    sql.Identifier(cfg["database"]), sql.Identifier(cfg["runtime_name"])
                )
            )
    with _connect(credential, cfg, user=cfg["bootstrap_name"], database=cfg["database"]) as conn:
        with conn.cursor() as cur:
            cur.execute(
                sql.SQL("GRANT USAGE, CREATE ON SCHEMA public TO {}").format(
                    sql.Identifier(cfg["runtime_name"])
                )
            )


def configure_runtime_environment(cfg: dict) -> None:
    os.environ.update({
        "AZURE_CLIENT_ID": cfg["runtime_client_id"],
        "SALUS_DB_BACKEND": "postgres",
        "SALUS_POSTGRES_AUTH": "managed_identity",
        "SALUS_POSTGRES_HOST": cfg["host"],
        "SALUS_POSTGRES_DATABASE": cfg["database"],
        "SALUS_POSTGRES_USER": cfg["runtime_name"],
        "SALUS_POSTGRES_SSLMODE": "require",
        "SALUS_AUTH_MODE": "oidc",
        "SALUS_OIDC_AUTO_PROVISION": "0",
        "SALUS_SEED_DEMO": "0",
        "SALUS_ALLOW_RESTORE": "0",
        "SALUS_ALLOW_SQLITE_PRODUCTION": "0",
        "SALUS_STORAGE_BACKEND": "local",
        "SALUS_SECRET_BACKEND": "environment",
        "SALUS_TELEMETRY_BACKEND": "off",
    })


def provision_identity_mappings(contract: dict) -> None:
    import app  # noqa: F401 - importing performs the governed schema migration
    from database import connect_database

    timestamp = datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")
    conn = connect_database()
    try:
        tenant = conn.execute(
            "SELECT * FROM tenants WHERE slug=?", (contract["tenant"]["slug"],)
        ).fetchone()
        if tenant is None:
            prototype = conn.execute(
                "SELECT * FROM tenants WHERE slug='salus-prototype'"
            ).fetchone()
            user_count = conn.execute("SELECT COUNT(*) c FROM users").fetchone()["c"]
            assessment_count = conn.execute("SELECT COUNT(*) c FROM assessments").fetchone()["c"]
            if prototype is not None and user_count == 0 and assessment_count == 0:
                conn.execute(
                    "UPDATE tenants SET name=?,slug=?,status='Active' WHERE id=?",
                    (contract["tenant"]["name"], contract["tenant"]["slug"], prototype["id"]),
                )
                tenant_id = prototype["id"]
            else:
                cursor = conn.execute(
                    "INSERT INTO tenants(name,slug,status,created_at) VALUES(?,?,?,?)",
                    (contract["tenant"]["name"], contract["tenant"]["slug"], "Active", timestamp),
                )
                tenant_id = cursor.lastrowid
        else:
            tenant_id = tenant["id"]
            conn.execute(
                "UPDATE tenants SET name=?,status='Active' WHERE id=?",
                (contract["tenant"]["name"], tenant_id),
            )

        for user in contract["users"]:
            existing_subject = conn.execute(
                "SELECT * FROM users WHERE identity_provider='entra' AND external_subject=?",
                (user["object_id"],),
            ).fetchone()
            existing_username = conn.execute(
                "SELECT * FROM users WHERE lower(username)=lower(?)", (user["username"],)
            ).fetchone()
            if existing_username is not None and (
                existing_subject is None or existing_username["id"] != existing_subject["id"]
            ):
                raise RuntimeError("Governed username is already bound to another identity")
            if existing_subject is None:
                cursor = conn.execute(
                    "INSERT INTO users(tenant_id,username,display_name,password_hash,role,sensitivity_clearance,status,created_at,updated_at,email,external_subject,identity_provider) "
                    "VALUES(?,?,?,?,?,?,?,?,?,?,?,?)",
                    (tenant_id, user["username"], user["display_name"], "", user["role"],
                     user["sensitivity_clearance"], user["status"], timestamp, timestamp, "",
                     user["object_id"], "entra"),
                )
                user_id = cursor.lastrowid
            else:
                user_id = existing_subject["id"]
                conn.execute(
                    "UPDATE users SET tenant_id=?,username=?,display_name=?,role=?,sensitivity_clearance=?,status=?,updated_at=? WHERE id=?",
                    (tenant_id, user["username"], user["display_name"], user["role"],
                     user["sensitivity_clearance"], user["status"], timestamp, user_id),
                )
            conn.execute(
                "INSERT INTO audit_log(ts,user_name,action,entity_type,entity_id,detail,tenant_id) VALUES(?,?,?,?,?,?,?)",
                (timestamp, "governed-bootstrap", "IDENTITY_MAPPING_PROVISIONED", "user", user_id,
                 "Immutable Entra object-ID mapping provisioned", tenant_id),
            )
        conn.commit()

        for user in contract["users"]:
            row = conn.execute(
                "SELECT tenant_id,username,role,sensitivity_clearance,status FROM users "
                "WHERE identity_provider='entra' AND external_subject=?",
                (user["object_id"],),
            ).fetchone()
            if row is None or row["tenant_id"] != tenant_id or any(
                row[key] != user[key]
                for key in ("username", "role", "sensitivity_clearance", "status")
            ):
                raise RuntimeError("Persisted identity mapping verification failed")
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def main() -> int:
    contract = load_contract()
    cfg = runtime_configuration()
    if os.getenv("SALUS_BOOTSTRAP_VALIDATE_ONLY", "0") == "1":
        print("SALCAPA_DATABASE_BOOTSTRAP_CONTRACT_PASS")
        return 0
    create_runtime_role(cfg)
    configure_runtime_environment(cfg)
    provision_identity_mappings(contract)
    print("SALCAPA_DATABASE_BOOTSTRAP_PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
