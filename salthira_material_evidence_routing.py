"""Human-authorized routing of indexed SalINTEL source aids into SalTHIRA evidence."""

from __future__ import annotations

import json
import uuid
from typing import Any, Literal

import database as database_support
from fastapi import HTTPException, Request
from pydantic import BaseModel, ConfigDict, Field, field_validator


SCHEMA = """
CREATE TABLE IF NOT EXISTS salthira_material_evidence_routes (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  tenant_id INTEGER NOT NULL,
  route_key TEXT NOT NULL UNIQUE,
  material_index_id INTEGER NOT NULL,
  derivative_id INTEGER NOT NULL,
  source_material_id INTEGER NOT NULL,
  assessment_id INTEGER NOT NULL,
  evidence_id INTEGER NOT NULL UNIQUE,
  attribution_json TEXT NOT NULL,
  evidence_status TEXT NOT NULL,
  routing_basis TEXT NOT NULL,
  routed_by TEXT NOT NULL,
  routed_by_role TEXT NOT NULL,
  routed_at TEXT NOT NULL,
  status TEXT NOT NULL DEFAULT 'Active',
  FOREIGN KEY (material_index_id) REFERENCES salintel_material_index(id) ON DELETE RESTRICT,
  FOREIGN KEY (derivative_id) REFERENCES material_derivatives(id) ON DELETE RESTRICT,
  FOREIGN KEY (source_material_id) REFERENCES materials(id) ON DELETE RESTRICT,
  FOREIGN KEY (assessment_id) REFERENCES assessments(id) ON DELETE CASCADE,
  FOREIGN KEY (evidence_id) REFERENCES evidence(id) ON DELETE RESTRICT,
  UNIQUE(material_index_id,assessment_id)
);
CREATE INDEX IF NOT EXISTS idx_salthira_material_routes_assessment
  ON salthira_material_evidence_routes(tenant_id,assessment_id,status,id);
CREATE INDEX IF NOT EXISTS idx_salthira_material_routes_index
  ON salthira_material_evidence_routes(material_index_id,id);
"""


class SalTHIRAEvidenceRouteIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    assessment_id: int = Field(gt=0)
    capability_id: int | None = Field(default=None, gt=0)
    scenario_id: int | None = Field(default=None, gt=0)
    title: str = Field(min_length=1, max_length=240)
    evidence_type: str = Field(default="Governed Source Aid", min_length=1, max_length=120)
    reliability: Literal["Low", "Medium", "High"] = "Medium"
    routing_basis: str = Field(min_length=1, max_length=4000)

    @field_validator("title", "evidence_type", "routing_basis")
    @classmethod
    def normalize_text(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("A documented value is required")
        return value


def register_salthira_material_evidence_routing(
    app: Any, core: dict[str, Any],
) -> None:
    required = (
        "db", "now", "actor", "role", "tenant_id", "require",
        "require_sensitivity", "protected_member_request",
        "require_salus_component_authority", "assessment_row_for_request",
        "security_event",
    )
    if any(name not in core for name in required):
        return
    db = core["db"]
    now = core["now"]
    actor = core["actor"]
    role = core["role"]
    tenant_id = core["tenant_id"]
    require = core["require"]
    require_sensitivity = core["require_sensitivity"]
    protected_member_request = core["protected_member_request"]
    require_salus_component_authority = core["require_salus_component_authority"]
    assessment_row_for_request = core["assessment_row_for_request"]
    security_event = core["security_event"]
    snapshot_entity = core.get("snapshot_entity")

    conn = db()
    try:
        conn.executescript(SCHEMA)
        conn.commit()
    finally:
        conn.close()

    portable_tables = {
        "salintel_material_index", "salthira_material_evidence_routes",
    }
    database_support.ID_TABLES.update(portable_tables)
    if not getattr(app.state, "salthira_material_route_backup_registered", False):
        base_collect = core["collect_tenant_records"]
        base_validate = core["validate_records"]
        base_replace = core["replace_tenant_records"]

        def collect_with_routes(conn, selected_tenant: int):
            records = base_collect(conn, selected_tenant)
            for table in (
                "salintel_material_index", "salthira_material_evidence_routes",
            ):
                records[table] = [
                    dict(row) for row in conn.execute(
                        f"SELECT * FROM {table} WHERE tenant_id=? ORDER BY id",
                        (selected_tenant,),
                    )
                ]
            return records

        def validate_with_routes(records: dict, selected_tenant: int | None = None):
            errors = list(base_validate(records, selected_tenant))
            derivatives = {
                int(row["id"]) for row in records.get("material_derivatives", [])
                if row.get("id") is not None
            }
            materials = {
                int(row["id"]) for row in records.get("materials", [])
                if row.get("id") is not None
            }
            indexes = {
                int(row["id"]) for row in records.get("salintel_material_index", [])
                if row.get("id") is not None
            }
            assessments = {
                int(row["id"]) for row in records.get("assessments", [])
                if row.get("id") is not None
            }
            evidence = {
                int(row["id"]) for row in records.get("evidence", [])
                if row.get("id") is not None
            }
            for table in portable_tables:
                for row in records.get(table, []):
                    if selected_tenant is not None and int(row.get("tenant_id", -1)) != int(selected_tenant):
                        errors.append(f"{table} record {row.get('id')} crosses the tenant boundary")
            for row in records.get("salintel_material_index", []):
                if int(row.get("derivative_id", -1)) not in derivatives:
                    errors.append(f"SalINTEL material index {row.get('id')} has an invalid derivative")
                if int(row.get("source_material_id", -1)) not in materials:
                    errors.append(f"SalINTEL material index {row.get('id')} has an invalid source")
            for row in records.get("salthira_material_evidence_routes", []):
                if int(row.get("material_index_id", -1)) not in indexes:
                    errors.append(f"SalTHIRA material route {row.get('id')} has an invalid index")
                if int(row.get("assessment_id", -1)) not in assessments:
                    errors.append(f"SalTHIRA material route {row.get('id')} has an invalid assessment")
                if int(row.get("evidence_id", -1)) not in evidence:
                    errors.append(f"SalTHIRA material route {row.get('id')} has invalid evidence")
            return errors

        def insert_restored_row(conn, table: str, row: dict) -> None:
            allowed = {item["name"] for item in conn.execute(f"PRAGMA table_info({table})")}
            data = {key: value for key, value in row.items() if key in allowed}
            if data:
                conn.execute(
                    f"INSERT INTO {table}({','.join(data)}) "
                    f"VALUES({','.join('?' * len(data))})",
                    tuple(data.values()),
                )

        def replace_with_routes(conn, selected_tenant: int, records: dict):
            errors = validate_with_routes(records, selected_tenant)
            if errors:
                raise ValueError("; ".join(errors))
            conn.execute(
                "DELETE FROM salthira_material_evidence_routes WHERE tenant_id=?",
                (selected_tenant,),
            )
            conn.execute(
                "DELETE FROM salintel_material_index WHERE tenant_id=?",
                (selected_tenant,),
            )
            base_replace(conn, selected_tenant, records)
            for table in (
                "salintel_material_index", "salthira_material_evidence_routes",
            ):
                for row in records.get(table, []):
                    insert_restored_row(conn, table, row)
            database_support.reset_identity_sequences(conn, portable_tables)

        core["collect_tenant_records"] = collect_with_routes
        core["validate_records"] = validate_with_routes
        core["replace_tenant_records"] = replace_with_routes
        app.state.salthira_material_route_backup_registered = True

    def internal_request(request: Request) -> None:
        if protected_member_request(request):
            raise HTTPException(
                403,
                "SalTHIRA evidence routing is restricted to authorized Salus personnel.",
            )

    def validate_optional_target(
        conn, table: str, record_id: int | None, assessment_id: int,
    ) -> None:
        if record_id is None:
            return
        row = conn.execute(
            f"SELECT assessment_id FROM {table} WHERE id=?", (record_id,),
        ).fetchone()
        if not row:
            raise HTTPException(404, f"{table[:-1].title()} not found")
        if int(row["assessment_id"]) != assessment_id:
            raise HTTPException(409, f"{table[:-1].title()} is outside the selected assessment")

    @app.post(
        "/api/salthira/material-index/{index_id}/route-evidence",
        include_in_schema=False,
    )
    def route_indexed_source_aid(
        index_id: int, payload: SalTHIRAEvidenceRouteIn, request: Request,
    ) -> dict[str, Any]:
        require(request, "decide")
        internal_request(request)
        require_salus_component_authority(
            request, "SalTHIRA governed evidence routing",
        )
        tid = int(tenant_id(request))
        assessment_row_for_request(request, payload.assessment_id)
        conn = db()
        try:
            row = conn.execute(
                "SELECT i.*,d.review_status,d.reviewed_by,d.reviewed_at,"
                "d.extraction_method,m.title source_title,m.original_name,"
                "m.source_origin,m.source_locator,m.acquired_at,m.disposition_status,"
                "m.immutable_original,m.disclosure_status "
                "FROM salintel_material_index i "
                "JOIN material_derivatives d ON d.id=i.derivative_id "
                "JOIN materials m ON m.id=i.source_material_id WHERE i.id=?",
                (index_id,),
            ).fetchone()
            if not row:
                raise HTTPException(404, "Indexed source aid not found")
            if int(row["tenant_id"]) != tid:
                security_event(
                    request, "SALTHIRA_ROUTE_TENANT_BOUNDARY_VIOLATION", "High",
                    f"material_index_id={index_id}",
                )
                raise HTTPException(403, "Tenant boundary violation")
            require_sensitivity(request, row["sensitivity"])
            if (
                row["status"] != "Active"
                or row["review_status"] != "Human Reviewed"
                or row["disposition_status"] != "Active"
                or not bool(row["immutable_original"])
            ):
                raise HTTPException(
                    409, "Only an active human-reviewed source aid with an immutable source may be routed",
                )
            validate_optional_target(
                conn, "capabilities", payload.capability_id, payload.assessment_id,
            )
            validate_optional_target(
                conn, "scenarios", payload.scenario_id, payload.assessment_id,
            )
            existing = conn.execute(
                "SELECT id FROM salthira_material_evidence_routes "
                "WHERE material_index_id=? AND assessment_id=?",
                (index_id, payload.assessment_id),
            ).fetchone()
            if existing:
                raise HTTPException(
                    409, "This indexed source aid is already routed to the assessment",
                )
            routed = now()
            route_key = "SMR-" + uuid.uuid4().hex
            attribution = json.dumps({
                "route_key": route_key,
                "material_index_id": index_id,
                "index_key": row["index_key"],
                "source_material_id": row["source_material_id"],
                "derivative_id": row["derivative_id"],
                "source_sha256": row["source_sha256"],
                "content_sha256": row["content_sha256"],
                "source_title": row["source_title"],
                "original_name": row["original_name"],
                "source_origin": row["source_origin"],
                "source_locator": row["source_locator"],
                "source_acquired_at": row["acquired_at"],
                "extraction_method": row["extraction_method"],
                "reviewed_by": row["reviewed_by"],
                "reviewed_at": row["reviewed_at"],
                "index_evidence_status": row["evidence_status"],
                "routing_basis": payload.routing_basis,
            }, sort_keys=True, separators=(",", ":"))
            source_label = (
                f"SalINTEL indexed source aid {row['index_key']}; "
                f"source-sha256={row['source_sha256']}; "
                f"content-sha256={row['content_sha256']}"
            )
            notes = (
                f"Governed attribution route {route_key}. Evidence status: "
                f"{row['evidence_status']}. Human routing does not establish source "
                "truth, a finding, risk rating, priority, recommendation, decision, "
                "operational authority, or disclosure approval."
            )
            cur = conn.execute(
                "INSERT INTO evidence(assessment_id,capability_id,scenario_id,title,"
                "evidence_type,source,owner,evidence_date,reliability,"
                "verification_status,sensitivity,notes,created_at,updated_at) "
                "VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                (
                    payload.assessment_id, payload.capability_id, payload.scenario_id,
                    payload.title, payload.evidence_type, source_label,
                    row["reviewed_by"], row["reviewed_at"], payload.reliability,
                    "Pending", row["sensitivity"], notes, routed, routed,
                ),
            )
            evidence_id = int(cur.lastrowid)
            if snapshot_entity:
                snapshot_entity(
                    conn, "evidence", evidence_id, actor(request),
                    "Human-authorized route from an attributed SalINTEL source aid",
                )
            route = conn.execute(
                "INSERT INTO salthira_material_evidence_routes(tenant_id,route_key,"
                "material_index_id,derivative_id,source_material_id,assessment_id,"
                "evidence_id,attribution_json,evidence_status,routing_basis,routed_by,"
                "routed_by_role,routed_at,status) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                (
                    tid, route_key, index_id, row["derivative_id"],
                    row["source_material_id"], payload.assessment_id, evidence_id,
                    attribution, "Pending SalTHIRA Evidence Verification",
                    payload.routing_basis, actor(request), role(request), routed, "Active",
                ),
            )
            route_id = int(route.lastrowid)
            conn.execute(
                "INSERT INTO audit_log(ts,user_name,action,entity_type,entity_id,detail,"
                "tenant_id) VALUES(?,?,?,?,?,?,?)",
                (
                    routed, actor(request), "SALTHIRA_MATERIAL_EVIDENCE_ROUTED",
                    "salthira_material_evidence_route", route_id,
                    f"index_id={index_id}; assessment_id={payload.assessment_id}; "
                    f"evidence_id={evidence_id}; no_finding_created=true", tid,
                ),
            )
            conn.commit()
            return {
                "route_id": route_id,
                "route_key": route_key,
                "material_index_id": index_id,
                "assessment_id": payload.assessment_id,
                "evidence_id": evidence_id,
                "evidence_status": "Pending SalTHIRA Evidence Verification",
                "verification_status": "Pending",
                "finding_status": "None Created",
                "risk_conclusion_status": "None Created",
                "recommendation_status": "None Created",
                "disclosure_status": row["disclosure_status"],
                "authority_note": (
                    "This record routes an attributed source aid for SalTHIRA evidence "
                    "review. It is not a finding, risk conclusion, recommendation, "
                    "decision, operational authorization, or disclosure approval."
                ),
            }
        except HTTPException:
            conn.rollback()
            raise
        except Exception as exc:
            conn.rollback()
            raise HTTPException(
                503, "The indexed source aid could not be routed to SalTHIRA evidence",
            ) from exc
        finally:
            conn.close()
