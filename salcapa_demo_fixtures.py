"""Governed fictional-environment fixtures for the SalCAPA demonstration.

This module is deliberately inert during ordinary application startup.  It exposes
an explicit seed/reseed operation for the three Issue #124 environments and a
small registration hook for their role contract and additive schema metadata.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import uuid
from dataclasses import dataclass
from typing import Any, Callable

from database import reset_identity_sequences, table_columns


FIXTURE_VERSION = "issue-124-foundation-v1"
FIXTURE_AUTHORITY = "ISSUE-124"
DEMONSTRATION_ACKNOWLEDGEMENT = "FICTIONAL DEMONSTRATION DATA ONLY"
RESEED_CONFIRMATION = "DELETE AND REBUILD FICTIONAL DEMONSTRATION ENVIRONMENTS"
FIXTURE_NAMESPACE = uuid.UUID("c546a8fa-2b46-5dc8-a6f2-12c3c9a0bb12")


@dataclass(frozen=True)
class Persona:
    key: str
    label: str
    role: str
    clearance: str


@dataclass(frozen=True)
class Environment:
    key: str
    slug: str
    name: str
    sector: str
    mission: str


PERSONAS = (
    Persona("member-executive-sponsor", "Protected Member Executive Sponsor", "Client Executive", "Sensitive"),
    Persona("member-security-risk-lead", "Protected Member Security and Risk Lead", "Contributor", "Restricted"),
    Persona("member-operations-lead", "Protected Member Operations Lead", "Contributor", "Restricted"),
    Persona("member-read-only", "Protected Member Read-only User", "Protected Member Viewer", "Standard"),
    Persona("salus-intelligence-analyst", "Salus Intelligence Analyst", "SME Assessor", "Sensitive"),
    Persona("salus-assessment-director", "Salus Assessment Director", "Assessment Director", "Highly Sensitive"),
    Persona("salus-operations-coordinator", "Salus Operations Coordinator", "Program Owner", "Restricted"),
    Persona("salus-system-administrator", "Salus System Administrator", "System Administrator", "Highly Sensitive"),
)

ENVIRONMENTS = (
    Environment(
        "aster-ridge-airport",
        "demo-aster-ridge-airport",
        "Aster Ridge International Airport — fictional demonstration",
        "Aviation and transportation",
        "Protect people, sustain safe airport operations, and coordinate continuity during disruption.",
    ),
    Environment(
        "cedar-vale-energy",
        "demo-cedar-vale-energy",
        "Cedar Vale Energy Systems — fictional demonstration",
        "Energy and utilities",
        "Protect people and critical energy services while sustaining coordinated response and recovery.",
    ),
    Environment(
        "northstar-applied-technologies",
        "demo-northstar-applied-technologies",
        "Northstar Applied Technologies — fictional demonstration",
        "Technology and advanced manufacturing",
        "Protect people, sensitive operations, and essential technology capabilities during disruption.",
    ),
)

PILLARS = (
    ("readiness", "Readiness and Preparedness", "Risk, preparedness, planning, training, exercise, and readiness services.", 10),
    ("protective", "Protective Operations", "Protective intelligence, executive protection, security, and investigation services.", 20),
    ("incident", "Incident and Crisis Support", "Incident management, disaster response, crisis communications, and urgent support services.", 30),
    ("recovery", "Recovery and Sustainment", "Recovery, continuity, after-action, improvement, and sustained-support services.", 40),
)


def fixture_manifest() -> dict[str, Any]:
    manifest = {
        "fixture_version": FIXTURE_VERSION,
        "authority": FIXTURE_AUTHORITY,
        "label": DEMONSTRATION_ACKNOWLEDGEMENT,
        "environments": [environment.__dict__ for environment in ENVIRONMENTS],
        "personas": [persona.__dict__ for persona in PERSONAS],
        "baseline_record_state": "Draft",
        "approval_state": "No approval, release, or decision is represented by these fixtures.",
    }
    canonical = json.dumps(manifest, sort_keys=True, separators=(",", ":"))
    return {**manifest, "sha256": hashlib.sha256(canonical.encode("utf-8")).hexdigest()}


def _ensure_column(conn: Any, table: str, column: str, ddl: str) -> None:
    if column not in table_columns(conn, table):
        conn.execute(f"ALTER TABLE {table} ADD COLUMN {column} {ddl}")


def ensure_demo_fixture_schema(conn: Any, timestamp: str) -> None:
    _ensure_column(conn, "tenants", "environment_kind", "TEXT NOT NULL DEFAULT 'Operational'")
    _ensure_column(conn, "tenants", "display_label", "TEXT NOT NULL DEFAULT ''")
    _ensure_column(conn, "tenants", "fixture_key", "TEXT NOT NULL DEFAULT ''")
    _ensure_column(conn, "tenants", "fixture_version", "TEXT NOT NULL DEFAULT ''")
    _ensure_column(conn, "users", "fixture_key", "TEXT NOT NULL DEFAULT ''")
    _ensure_column(conn, "assessments", "fixture_key", "TEXT NOT NULL DEFAULT ''")
    conn.executescript(
        """
        CREATE TABLE IF NOT EXISTS demo_fixture_runs (
          run_key TEXT PRIMARY KEY,
          fixture_version TEXT NOT NULL,
          manifest_sha256 TEXT NOT NULL,
          operation TEXT NOT NULL,
          authority TEXT NOT NULL,
          environment_count INTEGER NOT NULL,
          persona_count INTEGER NOT NULL,
          assessment_count INTEGER NOT NULL,
          result TEXT NOT NULL,
          executed_at TEXT NOT NULL
        );
        CREATE INDEX IF NOT EXISTS idx_demo_fixture_runs_time
          ON demo_fixture_runs(executed_at,run_key);
        """
    )
    conn.execute(
        "INSERT INTO schema_migrations(version,applied_at) VALUES(?,?) ON CONFLICT(version) DO NOTHING",
        ("3.110-demo-fixture-foundation", timestamp),
    )


def register_demo_fixture_contract(core: Any) -> None:
    """Register the read-only member role and additive fixture metadata only."""
    core.ROLE_PERMISSIONS.setdefault("Protected Member Viewer", {"read"})
    core.ROLE_CLEARANCE.setdefault("Protected Member Viewer", 1)
    core.PROTECTED_MEMBER_ROLES.add("Protected Member Viewer")
    conn = core.db()
    try:
        ensure_demo_fixture_schema(conn, core.now())
        conn.commit()
    finally:
        conn.close()


def _validate_controls(environment: str, authority: str, acknowledgement: str, operation: str, confirmation: str) -> None:
    if environment.strip().lower() in {"prod", "production"}:
        raise RuntimeError("Fictional demonstration fixtures are prohibited in production.")
    if authority.strip().upper() != FIXTURE_AUTHORITY:
        raise RuntimeError(f"Fixture authority must be {FIXTURE_AUTHORITY}.")
    if acknowledgement != DEMONSTRATION_ACKNOWLEDGEMENT:
        raise RuntimeError("The fictional-demonstration acknowledgement is required.")
    if operation not in {"seed", "reseed"}:
        raise RuntimeError("Operation must be seed or reseed.")
    if operation == "reseed" and confirmation != RESEED_CONFIRMATION:
        raise RuntimeError("Reseed requires the exact destructive-operation confirmation.")


def _delete_fixture_environments(conn: Any) -> None:
    expected_slugs = {environment.slug for environment in ENVIRONMENTS}
    rows = list(conn.execute("SELECT id,slug,environment_kind,fixture_key FROM tenants WHERE fixture_key<>''"))
    for row in rows:
        if row["environment_kind"] != "Fictional Demonstration" or row["slug"] not in expected_slugs:
            raise RuntimeError("Fixture metadata is inconsistent; reseed stopped without deleting tenant data.")
    for row in rows:
        conn.execute("DELETE FROM tenants WHERE id=? AND fixture_key=?", (row["id"], row["fixture_key"]))


def _tenant(conn: Any, environment: Environment, timestamp: str) -> int:
    existing = conn.execute("SELECT * FROM tenants WHERE slug=?", (environment.slug,)).fetchone()
    if existing and (existing["fixture_key"] != environment.key or existing["environment_kind"] != "Fictional Demonstration"):
        raise RuntimeError(f"Tenant slug {environment.slug} exists outside the governed fixture set.")
    if existing:
        conn.execute(
            "UPDATE tenants SET name=?,status='Active',environment_kind='Fictional Demonstration',display_label=?,fixture_version=? WHERE id=?",
            (environment.name, DEMONSTRATION_ACKNOWLEDGEMENT, FIXTURE_VERSION, existing["id"]),
        )
        return int(existing["id"])
    cur = conn.execute(
        "INSERT INTO tenants(name,slug,status,created_at,environment_kind,display_label,fixture_key,fixture_version) VALUES(?,?,?,?,?,?,?,?)",
        (environment.name, environment.slug, "Active", timestamp, "Fictional Demonstration", DEMONSTRATION_ACKNOWLEDGEMENT, environment.key, FIXTURE_VERSION),
    )
    return int(cur.lastrowid)


def _assessment(conn: Any, tenant_id: int, environment: Environment, timestamp: str) -> int:
    key = f"{environment.key}:baseline-assessment"
    existing = conn.execute("SELECT id FROM assessments WHERE fixture_key=?", (key,)).fetchone()
    values = (
        tenant_id,
        f"{environment.name} — baseline assessment",
        environment.name,
        "Enterprise",
        "Provide a governed starting point for the fictional SalCAPA demonstration.",
        environment.mission,
        f"Fictional {environment.sector.lower()} enterprise environment; demonstration use only.",
        "No real people, organizations, facilities, incidents, intelligence, or operational data.",
        "Draft",
        "Protected Member Executive Sponsor",
        "Salus Assessment Director",
        "Salus Intelligence Analyst",
        "",
        "",
        "",
        "Standard",
        0,
        1,
        timestamp,
        timestamp,
        key,
    )
    if existing:
        conn.execute(
            """UPDATE assessments SET tenant_id=?,name=?,organization=?,assessment_type=?,purpose=?,mission=?,scope=?,exclusions=?,status=?,executive_sponsor=?,assessment_director=?,lead_assessor=?,start_date=?,target_completion=?,reassessment_date=?,classification=?,scope_locked=?,version=?,updated_at=?,fixture_key=? WHERE id=?""",
            values[:18] + (timestamp, key, existing["id"]),
        )
        return int(existing["id"])
    cur = conn.execute(
        """INSERT INTO assessments(tenant_id,name,organization,assessment_type,purpose,mission,scope,exclusions,status,executive_sponsor,assessment_director,lead_assessor,start_date,target_completion,reassessment_date,classification,scope_locked,version,created_at,updated_at,fixture_key) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
        values,
    )
    return int(cur.lastrowid)


def _user(conn: Any, tenant_id: int, environment: Environment, persona: Persona, timestamp: str) -> int:
    key = f"{environment.key}:{persona.key}"
    username = f"demo.{environment.key}.{persona.key}"
    email = f"{persona.key}.{environment.key}@example.invalid"
    subject = str(uuid.uuid5(FIXTURE_NAMESPACE, key))
    existing = conn.execute("SELECT * FROM users WHERE username=?", (username,)).fetchone()
    if existing and existing["fixture_key"] != key:
        raise RuntimeError(f"Username {username} exists outside the governed fixture set.")
    values = (tenant_id, persona.label, "", persona.role, persona.clearance, "Active", timestamp, email, subject, "demo-fixture", key)
    if existing:
        conn.execute(
            """UPDATE users SET tenant_id=?,display_name=?,password_hash=?,role=?,sensitivity_clearance=?,status=?,updated_at=?,email=?,external_subject=?,identity_provider=?,fixture_key=? WHERE id=?""",
            values + (existing["id"],),
        )
        return int(existing["id"])
    cur = conn.execute(
        """INSERT INTO users(tenant_id,username,display_name,password_hash,role,sensitivity_clearance,status,created_at,updated_at,email,external_subject,identity_provider,fixture_key) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)""",
        (tenant_id, username, persona.label, "", persona.role, persona.clearance, "Active", timestamp, timestamp, email, subject, "demo-fixture", key),
    )
    return int(cur.lastrowid)


def seed_demo_environments(
    conn: Any,
    *,
    environment: str,
    authority: str,
    acknowledgement: str,
    operation: str = "seed",
    confirmation: str = "",
    now: Callable[[], str],
) -> dict[str, Any]:
    _validate_controls(environment, authority, acknowledgement, operation, confirmation)
    timestamp = now()
    ensure_demo_fixture_schema(conn, timestamp)
    manifest = fixture_manifest()
    try:
        if operation == "reseed":
            _delete_fixture_environments(conn)
            reset_identity_sequences(conn, {"tenants", "users", "assessments", "assessment_access", "ops_service_pillars"})
        assessment_count = user_count = access_count = pillar_count = 0
        for environment_record in ENVIRONMENTS:
            tenant_id = _tenant(conn, environment_record, timestamp)
            assessment_id = _assessment(conn, tenant_id, environment_record, timestamp)
            assessment_count += 1
            for code, name, description, sort_order in PILLARS:
                conn.execute(
                    """INSERT INTO ops_service_pillars(tenant_id,pillar_code,name,description,sort_order,status,created_by,created_at) VALUES(?,?,?,?,?,?,?,?) ON CONFLICT(tenant_id,pillar_code) DO NOTHING""",
                    (tenant_id, code, name, description, sort_order, "Active", "demo-fixture", timestamp),
                )
                pillar_count += 1
            for persona in PERSONAS:
                user_id = _user(conn, tenant_id, environment_record, persona, timestamp)
                user_count += 1
                conn.execute(
                    """INSERT INTO assessment_access(user_id,assessment_id,role_override,sensitivity_clearance,created_at) VALUES(?,?,?,?,?) ON CONFLICT(user_id,assessment_id) DO UPDATE SET role_override=?,sensitivity_clearance=?""",
                    (user_id, assessment_id, "", persona.clearance, timestamp, "", persona.clearance),
                )
                access_count += 1
        run_key = str(uuid.uuid4())
        conn.execute(
            """INSERT INTO demo_fixture_runs(run_key,fixture_version,manifest_sha256,operation,authority,environment_count,persona_count,assessment_count,result,executed_at) VALUES(?,?,?,?,?,?,?,?,?,?)""",
            (run_key, FIXTURE_VERSION, manifest["sha256"], operation, FIXTURE_AUTHORITY, len(ENVIRONMENTS), user_count, assessment_count, "Accepted", timestamp),
        )
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    return {
        "fixture_version": FIXTURE_VERSION,
        "manifest_sha256": manifest["sha256"],
        "operation": operation,
        "environment_count": len(ENVIRONMENTS),
        "persona_count": user_count,
        "assessment_count": assessment_count,
        "assessment_access_count": access_count,
        "service_pillar_count": pillar_count,
        "record_state": "Draft",
        "display_label": DEMONSTRATION_ACKNOWLEDGEMENT,
        "executed_at": timestamp,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Prepare governed fictional SalCAPA demonstration environments.")
    parser.add_argument("--operation", choices=("seed", "reseed"), default="seed")
    parser.add_argument("--authority", required=True)
    parser.add_argument("--acknowledgement", required=True)
    parser.add_argument("--confirmation", default="")
    args = parser.parse_args()
    import app as core
    conn = core.db()
    try:
        result = seed_demo_environments(
            conn,
            environment=core.ENVIRONMENT,
            authority=args.authority,
            acknowledgement=args.acknowledgement,
            operation=args.operation,
            confirmation=args.confirmation,
            now=core.now,
        )
    finally:
        conn.close()
    print(json.dumps(result, sort_keys=True))


if __name__ == "__main__":
    main()
