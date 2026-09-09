"""Governed contextual intake proposals for existing SalCAPA material records.

Context captured here is deliberately a proposal, not an authoritative link. The
existing material lifecycle still requires human review before a source can be
linked or promoted into intelligence, assessment, decision, or operational work.
"""

from __future__ import annotations

import json
from typing import Literal

from fastapi import HTTPException, Request
from pydantic import BaseModel, ConfigDict, Field, field_validator


TargetType = Literal[
    "assessment", "governed_intake", "evidence", "intel_finding",
    "observation", "threat", "scenario", "capability", "gap",
    "improvement", "decision", "ops_request", "ops_engagement",
    "ops_task", "ops_field_report", "report", "salintel_investigation",
]


class MaterialContextProposalIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    target_type: TargetType
    target_id: int = Field(gt=0)
    context_label: str = Field(min_length=1, max_length=500)
    purpose: str = Field(min_length=1, max_length=1000)

    @field_validator("context_label", "purpose")
    @classmethod
    def normalize_text(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("Context label and purpose are required.")
        return value


TARGETS = {
    "assessment": ("assessments", "tenant"),
    "governed_intake": ("governed_intake", "tenant"),
    "evidence": ("evidence", "assessment"),
    "intel_finding": ("intel_findings", "tenant_assessment"),
    "observation": ("observations", "tenant"),
    "threat": ("threats", "assessment"),
    "scenario": ("scenarios", "assessment"),
    "capability": ("capabilities", "assessment"),
    "gap": ("gaps", "assessment"),
    "improvement": ("improvements", "assessment"),
    "decision": ("decisions", "assessment"),
    "ops_request": ("ops_requests", "tenant_assessment"),
    "ops_engagement": ("ops_engagements", "tenant_assessment"),
    "ops_task": ("ops_tasks", "tenant_assessment"),
    "ops_field_report": ("ops_field_reports", "tenant_assessment"),
    "report": ("report_versions", "tenant_assessment"),
    "salintel_investigation": ("salintel_investigations", "tenant"),
}


def register_salcapa_contextual_intake(fastapi_app, core: dict) -> None:
    db = core["db"]
    now = core["now"]
    actor = core["actor"]
    role = core["role"]
    tenant_id = core["tenant_id"]
    require = core["require"]
    require_sensitivity = core["require_sensitivity"]
    protected_member_request = core["protected_member_request"]
    assessment_row_for_request = core["assessment_row_for_request"]
    security_event = core["security_event"]

    def material_for_request(conn, material_id: int, request: Request):
        row = conn.execute("SELECT * FROM materials WHERE id=?", (material_id,)).fetchone()
        if not row:
            raise HTTPException(404, "Material not found")
        if int(row["tenant_id"]) != tenant_id(request):
            security_event(
                request, "MATERIAL_CONTEXT_TENANT_BOUNDARY_VIOLATION", "High",
                f"material_id={material_id}",
            )
            raise HTTPException(403, "Tenant boundary violation")
        require_sensitivity(request, row["sensitivity"])
        if protected_member_request(request):
            visible = row["disclosure_status"] == "Approved for Tenant"
            submitted = row["disclosure_status"] == "Protected Member Submitted"
            visible = visible or (
                submitted and (
                    role(request) == "Client Executive" or row["uploaded_by"] == actor(request)
                )
            )
            if not visible:
                raise HTTPException(403, "Material is not available for this Protected Member user")
        return row

    def target_scope(conn, payload: MaterialContextProposalIn, request: Request):
        table, mode = TARGETS[payload.target_type]
        if mode == "assessment":
            row = conn.execute(
                f"SELECT t.id target_id,a.tenant_id,a.id assessment_id FROM {table} t "
                "JOIN assessments a ON a.id=t.assessment_id WHERE t.id=?",
                (payload.target_id,),
            ).fetchone()
        elif mode == "tenant_assessment":
            row = conn.execute(
                f"SELECT id target_id,tenant_id,assessment_id FROM {table} WHERE id=?",
                (payload.target_id,),
            ).fetchone()
        elif table == "assessments":
            row = conn.execute(
                "SELECT id target_id,tenant_id,id assessment_id FROM assessments WHERE id=?",
                (payload.target_id,),
            ).fetchone()
        else:
            row = conn.execute(
                f"SELECT id target_id,tenant_id,NULL assessment_id FROM {table} WHERE id=?",
                (payload.target_id,),
            ).fetchone()
        if not row:
            raise HTTPException(404, "Context target not found")
        if int(row["tenant_id"]) != tenant_id(request):
            security_event(
                request, "MATERIAL_CONTEXT_TARGET_BOUNDARY_VIOLATION", "High",
                f"target_type={payload.target_type}; target_id={payload.target_id}",
            )
            raise HTTPException(403, "Tenant boundary violation")
        assessment_id = row["assessment_id"]
        if assessment_id not in (None, ""):
            assessment_row_for_request(request, int(assessment_id))
        return int(assessment_id) if assessment_id not in (None, "") else None

    @fastapi_app.post("/api/materials/{material_id}/context-proposals")
    def propose_material_context(
        material_id: int, payload: MaterialContextProposalIn, request: Request,
    ):
        require(request, "write")
        conn = db()
        material = material_for_request(conn, material_id, request)
        if material["disposition_status"] != "Active":
            conn.close()
            raise HTTPException(409, "Disposed material cannot receive a context proposal")
        assessment_id = target_scope(conn, payload, request)
        proposed_at = now()
        proposal = {
            "target_type": payload.target_type,
            "target_id": payload.target_id,
            "assessment_id": assessment_id,
            "context_label": payload.context_label,
            "purpose": payload.purpose,
            "proposal_state": "Awaiting Human Review",
            "authoritative_link": False,
        }
        reason = json.dumps(proposal, sort_keys=True, separators=(",", ":"))
        conn.execute(
            "INSERT INTO material_events(tenant_id,material_id,event_type,from_status,to_status,"
            "reason,snapshot_json,changed_by,changed_by_role,created_at) VALUES(?,?,?,?,?,?,?,?,?,?)",
            (
                tenant_id(request), material_id, "CONTEXT_PROPOSED", "", "",
                reason, json.dumps(dict(material), sort_keys=True, default=str),
                actor(request), role(request), proposed_at,
            ),
        )
        conn.execute(
            "INSERT INTO audit_log(ts,user_name,action,entity_type,entity_id,detail,tenant_id) "
            "VALUES(?,?,?,?,?,?,?)",
            (
                proposed_at, actor(request), "MATERIAL_CONTEXT_PROPOSED", "material",
                material_id,
                f"target_type={payload.target_type}; target_id={payload.target_id}; awaiting human review",
                tenant_id(request),
            ),
        )
        conn.commit()
        conn.close()
        return {"material_id": material_id, **proposal, "proposed_at": proposed_at}

