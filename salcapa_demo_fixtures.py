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


FIXTURE_VERSION = "issue-124-role-preflight-v3"
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


@dataclass(frozen=True)
class Journey:
    indicator: str
    source_locator: str
    threat: str
    threat_category: str
    scenario: str
    initiating_event: str
    capability: str
    required_outcome: str
    required_standard: float
    current_performance: float
    gap: str
    improvement: str
    coordination_subject: str
    operations_request: str


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

JOURNEYS = {
    "aster-ridge-airport": Journey(
        "Regional weather and utility advisory — fictional demonstration",
        "demo://aster-ridge/regional-advisory",
        "Severe weather and extended utility disruption — fictional demonstration",
        "Natural and infrastructure",
        "Terminal operations during a 72-hour regional outage — fictional demonstration",
        "A severe storm disrupts commercial power, telecommunications, road access, and fuel resupply.",
        "Airport continuity coordination — fictional demonstration",
        "Maintain life-safety communications and prioritized airport operations throughout the disruption.",
        95,
        68,
        "Evidence is needed to demonstrate alternate communications coverage and fuel-resupply endurance.",
        "Validate alternate communications and fuel-resupply coordination",
        "Review airport continuity priorities and information needs — fictional demonstration",
        "Prepare an airport continuity coordination exercise draft",
    ),
    "cedar-vale-energy": Journey(
        "Grid reliability and field-access notice — fictional demonstration",
        "demo://cedar-vale/grid-field-notice",
        "Concurrent grid instability and field-access constraints — fictional demonstration",
        "Infrastructure and operational",
        "Control-center and field coordination during regional disruption — fictional demonstration",
        "Severe weather produces grid instability while road closures delay access to critical field assets.",
        "Control-center and field-team continuity — fictional demonstration",
        "Sustain safe control-center operations and coordinate priority field access under degraded conditions.",
        90,
        61,
        "Evidence is needed for alternate communications, field-access priorities, and restoration dependencies.",
        "Validate alternate field coordination and restoration priorities",
        "Review energy continuity dependencies and decision needs — fictional demonstration",
        "Prepare a control-center and field coordination exercise draft",
    ),
    "northstar-applied-technologies": Journey(
        "Supplier and telecommunications disruption notice — fictional demonstration",
        "demo://northstar/supplier-telecom-notice",
        "Critical supplier and telecommunications interruption — fictional demonstration",
        "Supply chain and infrastructure",
        "Protected operations during a supplier and communications interruption — fictional demonstration",
        "A regional telecommunications failure coincides with delayed delivery of a critical production input.",
        "Protected production continuity — fictional demonstration",
        "Protect people and sensitive operations while sustaining the highest-priority production capabilities.",
        92,
        64,
        "Evidence is needed for alternate supplier, communications, and production-priority arrangements.",
        "Validate alternate supplier and communications arrangements",
        "Review production continuity assumptions and decisions — fictional demonstration",
        "Prepare a protected production continuity exercise draft",
    ),
}

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
        "journeys": {key: journey.__dict__ for key, journey in JOURNEYS.items()},
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
        ("3.110-demo-fixture-role-preflight-v3", timestamp),
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


def _upsert_named(conn: Any, select_sql: str, select_params: tuple[Any, ...], insert_sql: str, insert_params: tuple[Any, ...]) -> int:
    existing = conn.execute(select_sql, select_params).fetchone()
    if existing:
        return int(existing["id"])
    return int(conn.execute(insert_sql, insert_params).lastrowid)


def _journey_records(conn: Any, tenant_id: int, assessment_id: int, environment: Environment, timestamp: str) -> dict[str, int]:
    journey = JOURNEYS[environment.key]
    created_by = "Fictional demonstration fixture — no human review represented"
    finding_id = _upsert_named(
        conn,
        "SELECT id FROM intel_findings WHERE tenant_id=? AND assessment_id=? AND title=?",
        (tenant_id, assessment_id, journey.indicator),
        """INSERT INTO intel_findings(tenant_id,assessment_id,title,details,source,source_locator,relevance,credibility,validation_status,operational_significance,status,created_by,created_at,updated_at) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
        (tenant_id, assessment_id, journey.indicator, journey.initiating_event, "Fictional demonstration source", journey.source_locator, "Pending", "Unrated", "Unvalidated", "Awaiting analyst review and qualification.", "Collected", created_by, timestamp, timestamp),
    )
    threat_id = _upsert_named(
        conn,
        "SELECT id FROM threats WHERE assessment_id=? AND name=?",
        (assessment_id, journey.threat),
        """INSERT INTO threats(assessment_id,name,category,subcategory,description,likelihood,vulnerability,consequence,confidence,trend,inclusion_status,basis,status,created_at,updated_at) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
        (assessment_id, journey.threat, journey.threat_category, "Fictional demonstration", journey.initiating_event, 3, 3, 4, "Low", "Unknown", "Included - Scenario Required", "Fictional scenario basis; awaiting human review and supporting evidence.", "Active", timestamp, timestamp),
    )
    scenario_id = _upsert_named(
        conn,
        "SELECT id FROM scenarios WHERE assessment_id=? AND title=?",
        (assessment_id, journey.scenario),
        """INSERT INTO scenarios(assessment_id,threat_id,title,narrative,initiating_event,location,duration,operating_conditions,dependencies,decision_points,assumptions,uncertainties,life_safety,mission,operations,financial,legal_regulatory,reputation,recovery,evidence_confidence,created_at,updated_at) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
        (assessment_id, threat_id, journey.scenario, journey.initiating_event, journey.initiating_event, "Fictional Protected Member operating area", "72 hours", "Degraded power, communications, transportation, and supplier conditions.", "People; communications; power; transportation; suppliers; public-safety availability.", "Authorized people determine priorities, operating changes, resource commitments, and public communications.", "Fictional planning assumptions only; none are established as policy or authority.", "Duration, geographic extent, resource availability, restoration sequence, and cascading effects remain unknown.", 4, 4, 4, 3, 3, 3, 4, "Low", timestamp, timestamp),
    )
    capability_id = _upsert_named(
        conn,
        "SELECT id FROM capabilities WHERE assessment_id=? AND name=?",
        (assessment_id, journey.capability),
        """INSERT INTO capabilities(assessment_id,scenario_id,name,mission_area,capability_family,required_outcome,operating_conditions,performance_metric,measurement_type,measurement_unit,comparator,required_standard,current_performance,responsible_function,owner,dependencies,evidence_required,confidence,last_validated,next_validation,created_at,updated_at) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
        (assessment_id, scenario_id, journey.capability, "Protection, response, and recovery", "Continuity and coordination", journey.required_outcome, "Regional disruption with constrained access and communications.", "Percent of priority functions supported within the agreed operating period", "Percentage", "%", ">=", journey.required_standard, journey.current_performance, "Protected Member leadership with Salus support", "Awaiting assignment", "Current authorities, trained personnel, alternate communications, power, transport, and suppliers.", "Plans, rosters, exercise observations, operating records, and source documentation.", "Low", "", "", timestamp, timestamp),
    )
    evidence_title = f"{journey.capability} evidence collection — fictional demonstration"
    evidence_id = _upsert_named(
        conn,
        "SELECT id FROM evidence WHERE assessment_id=? AND title=?",
        (assessment_id, evidence_title),
        """INSERT INTO evidence(assessment_id,capability_id,scenario_id,title,evidence_type,source,owner,evidence_date,reliability,verification_status,sensitivity,valid_until,lifecycle_status,stale_reason,stale_at,last_lifecycle_review_at,last_lifecycle_review_by,notes,created_at,updated_at) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
        (assessment_id, capability_id, scenario_id, evidence_title, "Demonstration reference", "Fictional demonstration fixture", "Awaiting assignment", "", "Unrated", "Pending", "Standard", "", "Current", "", "", "", "", "Evidence Needed. No source has been reviewed or verified.", timestamp, timestamp),
    )
    gap_id = _upsert_named(
        conn,
        "SELECT id FROM gaps WHERE assessment_id=? AND description=?",
        (assessment_id, journey.gap),
        """INSERT INTO gaps(assessment_id,capability_id,gap_type,description,severity,root_cause,owner,status,created_at,updated_at) VALUES(?,?,?,?,?,?,?,?,?,?)""",
        (assessment_id, capability_id, "Evidence and validation", journey.gap, "Moderate", "The fictional demonstration has not yet supplied records or field validation.", "Awaiting assignment", "Open", timestamp, timestamp),
    )
    improvement_id = _upsert_named(
        conn,
        "SELECT id FROM improvements WHERE assessment_id=? AND title=?",
        (assessment_id, journey.improvement),
        """INSERT INTO improvements(assessment_id,gap_id,title,description,initial_cost,recurring_cost,implementation_days,feasibility,consequence_reduction,mission_benefit,sustainability,dependencies,owner,status,validation_status,validation_evidence_id,validation_outcome,validated_effectiveness_percent,validated_by,validated_at,created_at,updated_at) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
        (assessment_id, gap_id, journey.improvement, "Proposed demonstration improvement. Authorized people must review scope, priority, resources, and authority before action.", 0, 0, 0, 3, 3, 4, 3, "Protected Member input, source records, Salus review, and exercise design.", "Awaiting assignment", "Proposed", "Pending", None, "Awaiting validation", 0, "", "", timestamp, timestamp),
    )
    thread_id = _upsert_named(
        conn,
        "SELECT id FROM cop_coordination_threads WHERE tenant_id=? AND assessment_id=? AND subject=?",
        (tenant_id, assessment_id, journey.coordination_subject),
        """INSERT INTO cop_coordination_threads(tenant_id,assessment_id,subject,status,assigned_contact,assigned_contact_summary,created_by,created_by_role,created_at,updated_at) VALUES(?,?,?,?,?,?,?,?,?,?)""",
        (tenant_id, assessment_id, journey.coordination_subject, "Open", "Salus Operations Coordinator", "Fictional demonstration contact", created_by, "Program Owner", timestamp, timestamp),
    )
    message_body = "This fictional coordination thread collects source records, contradictions, information gaps, authority questions, and recommended next steps. No decision or operational authorization has been recorded."
    message_id = _upsert_named(
        conn,
        "SELECT id FROM cop_coordination_messages WHERE tenant_id=? AND thread_id=? AND body=?",
        (tenant_id, thread_id, message_body),
        """INSERT INTO cop_coordination_messages(tenant_id,thread_id,audience,body,author,author_role,created_at) VALUES(?,?,?,?,?,?,?)""",
        (tenant_id, thread_id, "Shared", message_body, created_by, "Program Owner", timestamp),
    )
    internal_message_body = "Salus personnel must reconcile source limitations, contradictions, assumptions, and authority questions before presenting a recommendation. This fictional note is not available in Protected Member views."
    internal_message_id = _upsert_named(
        conn,
        "SELECT id FROM cop_coordination_messages WHERE tenant_id=? AND thread_id=? AND body=?",
        (tenant_id, thread_id, internal_message_body),
        """INSERT INTO cop_coordination_messages(tenant_id,thread_id,audience,body,author,author_role,created_at) VALUES(?,?,?,?,?,?,?)""",
        (tenant_id, thread_id, "Internal", internal_message_body, created_by, "Program Owner", timestamp),
    )
    decision_title = f"Review proposed priority: {journey.improvement} — fictional demonstration"
    decision_id = _upsert_named(
        conn,
        "SELECT id FROM cop_decision_requests WHERE tenant_id=? AND source_type='improvement' AND source_id=? AND action_type='Approve Recommendation'",
        (tenant_id, improvement_id),
        """INSERT INTO cop_decision_requests(tenant_id,assessment_id,source_type,source_id,action_type,title,member_summary,allowed_choices_json,due_at,status,requested_by,requested_at,updated_at) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)""",
        (tenant_id, assessment_id, "improvement", improvement_id, "Approve Recommendation", decision_title, "Review the evidence basis, assumptions, dependencies, uncertainty, proposed scope, and next validation step.", json.dumps(["Approve", "Approve with Conditions", "Decline", "Defer"]), "", "Awaiting Decision", created_by, timestamp, timestamp),
    )
    operations_id = _upsert_named(
        conn,
        "SELECT id FROM ops_requests WHERE tenant_id=? AND source_type='Fictional Demonstration' AND source_id=?",
        (tenant_id, assessment_id),
        """INSERT INTO ops_requests(tenant_id,assessment_id,source_type,source_id,title,description,priority,status,requested_by,requested_at,updated_at) VALUES(?,?,?,?,?,?,?,?,?,?,?)""",
        (tenant_id, assessment_id, "Fictional Demonstration", assessment_id, journey.operations_request, "Requested planning support only. Scope, legal and policy authority, resources, scheduling, and release remain subject to authorized human review.", "Routine", "Requested", created_by, timestamp, timestamp),
    )
    for record_type, record_id, summary in (
        ("coordination_thread", thread_id, "Fictional demonstration coordination thread prepared; no decision represented."),
        ("decision_request", decision_id, "Fictional demonstration decision request prepared; awaiting authorized review."),
    ):
        if not conn.execute("SELECT id FROM cop_events WHERE tenant_id=? AND record_type=? AND record_id=? AND version_no=1", (tenant_id, record_type, record_id)).fetchone():
            if record_type == "coordination_thread":
                row = conn.execute("SELECT * FROM cop_coordination_threads WHERE id=?", (record_id,)).fetchone()
            else:
                row = conn.execute("SELECT * FROM cop_decision_requests WHERE id=?", (record_id,)).fetchone()
            snapshot = dict(row)
            conn.execute(
                """INSERT INTO cop_events(tenant_id,record_type,record_id,version_no,event_type,summary,snapshot_json,changed_by,changed_by_role,created_at) VALUES(?,?,?,?,?,?,?,?,?,?)""",
                (tenant_id, record_type, record_id, 1, "Fixture Prepared", summary, json.dumps(snapshot, sort_keys=True, default=str), created_by, "System Administrator", timestamp),
            )
    return {
        "finding": finding_id,
        "threat": threat_id,
        "scenario": scenario_id,
        "capability": capability_id,
        "evidence": evidence_id,
        "gap": gap_id,
        "improvement": improvement_id,
        "coordination_thread": thread_id,
        "coordination_message": message_id,
        "internal_coordination_message": internal_message_id,
        "decision_request": decision_id,
        "operations_request": operations_id,
    }


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
        assessment_count = user_count = access_count = pillar_count = journey_count = 0
        for environment_record in ENVIRONMENTS:
            tenant_id = _tenant(conn, environment_record, timestamp)
            assessment_id = _assessment(conn, tenant_id, environment_record, timestamp)
            assessment_count += 1
            _journey_records(conn, tenant_id, assessment_id, environment_record, timestamp)
            journey_count += 1
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
        "journey_count": journey_count,
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
