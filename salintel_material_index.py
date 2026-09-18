"""Tenant-scoped SalINTEL research indexing for human-reviewed material derivatives."""

from __future__ import annotations

import json
import uuid
from typing import Any

from fastapi import HTTPException, Query, Request
from pydantic import BaseModel, ConfigDict, Field, field_validator


SCHEMA = """
CREATE TABLE IF NOT EXISTS salintel_material_index (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  tenant_id INTEGER NOT NULL,
  index_key TEXT NOT NULL UNIQUE,
  derivative_id INTEGER NOT NULL UNIQUE,
  source_material_id INTEGER NOT NULL,
  source_sha256 TEXT NOT NULL,
  content_sha256 TEXT NOT NULL,
  source_attribution_json TEXT NOT NULL,
  evidence_status TEXT NOT NULL,
  evidence_note TEXT NOT NULL,
  sensitivity TEXT NOT NULL,
  status TEXT NOT NULL DEFAULT 'Active',
  indexed_by TEXT NOT NULL,
  indexed_by_role TEXT NOT NULL,
  indexed_at TEXT NOT NULL,
  FOREIGN KEY (derivative_id) REFERENCES material_derivatives(id) ON DELETE RESTRICT,
  FOREIGN KEY (source_material_id) REFERENCES materials(id) ON DELETE RESTRICT
);
CREATE INDEX IF NOT EXISTS idx_salintel_material_index_tenant
  ON salintel_material_index(tenant_id,status,indexed_at,id);
CREATE INDEX IF NOT EXISTS idx_salintel_material_index_source
  ON salintel_material_index(source_material_id,id);
"""


class MaterialIndexIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    basis: str = Field(min_length=1, max_length=4000)
    evidence_note: str = Field(
        default=(
            "Human review confirms that the derivative represents the governed source. "
            "It does not independently establish source truth, relevance, or a finding."
        ),
        min_length=1,
        max_length=4000,
    )

    @field_validator("basis", "evidence_note")
    @classmethod
    def normalize_text(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("A documented basis is required")
        return value


def register_salintel_material_index(app: Any, core: dict[str, Any]) -> None:
    required = (
        "db", "now", "actor", "role", "tenant_id", "require",
        "require_sensitivity", "protected_member_request",
        "require_salus_component_authority", "security_event",
        "clearance_level", "SENSITIVITY_LEVELS",
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
    security_event = core["security_event"]
    clearance_level = core["clearance_level"]
    sensitivity_levels = core["SENSITIVITY_LEVELS"]

    conn = db()
    try:
        conn.executescript(SCHEMA)
        conn.commit()
    finally:
        conn.close()

    def internal_request(request: Request) -> None:
        require(request, "read")
        if protected_member_request(request):
            raise HTTPException(
                403,
                "SalINTEL research indexing is restricted to authorized Salus personnel.",
            )

    def audit(
        conn, request: Request, action: str, entity_id: int, detail: str,
    ) -> None:
        conn.execute(
            "INSERT INTO audit_log(ts,user_name,action,entity_type,entity_id,detail,tenant_id) "
            "VALUES(?,?,?,?,?,?,?)",
            (
                now(), actor(request), action, "salintel_material_index", entity_id,
                detail[:2000], tenant_id(request),
            ),
        )

    @app.post(
        "/api/salintel/research/material-derivatives/{derivative_id}/index",
        include_in_schema=False,
    )
    def index_reviewed_derivative(
        derivative_id: int, payload: MaterialIndexIn, request: Request,
    ) -> dict[str, Any]:
        require(request, "write")
        internal_request(request)
        require_salus_component_authority(request, "SalINTEL governed research indexing")
        tid = int(tenant_id(request))
        conn = db()
        try:
            row = conn.execute(
                "SELECT d.*,m.title source_title,m.original_name,m.source_origin,"
                "m.source_locator,m.acquired_at,m.sensitivity,m.disposition_status,"
                "m.disclosure_status,m.immutable_original "
                "FROM material_derivatives d JOIN materials m ON m.id=d.source_material_id "
                "WHERE d.id=?",
                (derivative_id,),
            ).fetchone()
            if not row:
                raise HTTPException(404, "Human-reviewed derivative not found")
            if int(row["tenant_id"]) != tid:
                security_event(
                    request, "SALINTEL_INDEX_TENANT_BOUNDARY_VIOLATION", "High",
                    f"derivative_id={derivative_id}",
                )
                raise HTTPException(403, "Tenant boundary violation")
            require_sensitivity(request, row["sensitivity"])
            if row["review_status"] != "Human Reviewed":
                raise HTTPException(
                    409, "Only a human-reviewed derivative may enter the research index",
                )
            if row["disposition_status"] != "Active":
                raise HTTPException(409, "Disposed source material cannot be indexed")
            if not bool(row["immutable_original"]):
                raise HTTPException(409, "The indexed source must retain an immutable original")
            existing = conn.execute(
                "SELECT id FROM salintel_material_index WHERE derivative_id=?",
                (derivative_id,),
            ).fetchone()
            if existing:
                raise HTTPException(409, "This derivative is already indexed")
            attribution = json.dumps({
                "source_material_id": int(row["source_material_id"]),
                "source_title": row["source_title"],
                "original_name": row["original_name"],
                "source_origin": row["source_origin"],
                "source_locator": row["source_locator"],
                "source_acquired_at": row["acquired_at"],
                "source_sha256": row["source_sha256"],
                "derivative_id": derivative_id,
                "derivative_key": row["derivative_key"],
                "content_sha256": row["content_sha256"],
                "processor": row["processor"],
                "processor_version": row["processor_version"],
                "extraction_method": row["extraction_method"],
                "reviewed_by": row["reviewed_by"],
                "reviewed_by_role": row["reviewed_by_role"],
                "reviewed_at": row["reviewed_at"],
                "review_basis": row["review_basis"],
            }, sort_keys=True, separators=(",", ":"))
            indexed = now()
            cur = conn.execute(
                "INSERT INTO salintel_material_index(tenant_id,index_key,derivative_id,"
                "source_material_id,source_sha256,content_sha256,source_attribution_json,"
                "evidence_status,evidence_note,sensitivity,status,indexed_by,indexed_by_role,"
                "indexed_at) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                (
                    tid, "SMI-" + uuid.uuid4().hex, derivative_id,
                    int(row["source_material_id"]), row["source_sha256"],
                    row["content_sha256"], attribution, "Human Reviewed Source Aid",
                    payload.evidence_note, row["sensitivity"], "Active",
                    actor(request), role(request), indexed,
                ),
            )
            index_id = int(cur.lastrowid)
            audit(
                conn, request, "SALINTEL_MATERIAL_INDEXED", index_id,
                f"derivative_id={derivative_id}; source_material_id={row['source_material_id']}; "
                f"basis={payload.basis}; no_finding_created=true; no_salthira_route=true",
            )
            conn.commit()
            return {
                "index_id": index_id,
                "index_key": conn.execute(
                    "SELECT index_key FROM salintel_material_index WHERE id=?", (index_id,)
                ).fetchone()["index_key"],
                "derivative_id": derivative_id,
                "source_material_id": int(row["source_material_id"]),
                "source_sha256": row["source_sha256"],
                "content_sha256": row["content_sha256"],
                "evidence_status": "Human Reviewed Source Aid",
                "sensitivity": row["sensitivity"],
                "status": "Active",
                "finding_status": "None Created",
                "salthira_routing_status": "Not Routed",
                "disclosure_status": row["disclosure_status"],
            }
        except HTTPException:
            conn.rollback()
            raise
        except Exception as exc:
            conn.rollback()
            raise HTTPException(503, "The reviewed source aid could not be indexed") from exc
        finally:
            conn.close()

    @app.get("/api/salintel/research/material-index", include_in_schema=False)
    def search_material_index(
        request: Request,
        q: str = Query(default="", max_length=300),
        limit: int = Query(default=50, ge=1, le=100),
    ) -> dict[str, Any]:
        internal_request(request)
        tid = int(tenant_id(request))
        query = q.strip().casefold()
        conn = db()
        try:
            rows = conn.execute(
                "SELECT i.*,d.content_text,m.title source_title,m.original_name "
                "FROM salintel_material_index i "
                "JOIN material_derivatives d ON d.id=i.derivative_id "
                "JOIN materials m ON m.id=i.source_material_id "
                "WHERE i.tenant_id=? AND i.status='Active' ORDER BY i.id DESC LIMIT ?",
                (tid, min(limit * 20, 2000)),
            ).fetchall()
        finally:
            conn.close()
        allowed_level = clearance_level(request)
        results = []
        for row in rows:
            if sensitivity_levels.get(row["sensitivity"], 99) > allowed_level:
                continue
            content = row["content_text"]
            location = content.casefold().find(query) if query else 0
            if query and location < 0:
                continue
            start = max(0, location - 180)
            end = min(len(content), location + max(len(query), 1) + 320)
            results.append({
                "index_id": row["id"],
                "index_key": row["index_key"],
                "derivative_id": row["derivative_id"],
                "source_material_id": row["source_material_id"],
                "source_title": row["source_title"],
                "original_name": row["original_name"],
                "source_sha256": row["source_sha256"],
                "content_sha256": row["content_sha256"],
                "source_attribution": json.loads(row["source_attribution_json"]),
                "evidence_status": row["evidence_status"],
                "evidence_note": row["evidence_note"],
                "sensitivity": row["sensitivity"],
                "content_preview": content[start:end],
                "finding_status": "None Created",
                "salthira_routing_status": "Not Routed",
            })
            if len(results) >= limit:
                break
        return {
            "items": results,
            "scope_note": (
                "Tenant- and clearance-scoped human-reviewed source aids only. "
                "Search results are not findings, decisions, disclosure approvals, or SalTHIRA routes."
            ),
        }
