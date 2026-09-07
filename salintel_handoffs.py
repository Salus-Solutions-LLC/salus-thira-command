"""Governed internal handoffs from qualified SalINTEL investigations.

Handoffs reuse the shared investigation-item record and create only a governed
SalTHIRA reassessment trigger or SalOPS request. They never authorize member
disclosure, a deeper investigation tier, operational execution, or new cost.
"""
from __future__ import annotations

import json
import uuid
from typing import Literal

from fastapi import HTTPException, Request
from pydantic import BaseModel, ConfigDict, Field, field_validator

TargetComponent = Literal["SalTHIRA", "SalOPS"]
ELIGIBLE_RECORD_TYPES = {"personnel_finding", "salintel_research_product"}


class CreateHandoff(BaseModel):
    model_config = ConfigDict(extra="forbid")
    target_component: TargetComponent
    assessment_id: int = Field(gt=0)
    item_ids: list[int] = Field(min_length=1, max_length=100)
    summary: str = Field(min_length=1, max_length=8000)
    rationale: str = Field(min_length=1, max_length=4000)

    @field_validator("item_ids")
    @classmethod
    def unique_items(cls, value: list[int]) -> list[int]:
        if any(item_id <= 0 for item_id in value):
            raise ValueError("Handoff item identifiers must be positive")
        result = list(dict.fromkeys(value))
        if len(result) != len(value):
            raise ValueError("Handoff item identifiers must be unique")
        return result

    @field_validator("summary", "rationale")
    @classmethod
    def clean_text(cls, value: str) -> str:
        result = value.strip()
        if not result:
            raise ValueError("A non-empty value is required")
        return result


def register_salintel_handoffs(app, core: dict) -> None:
    db, now = core["db"], core["now"]
    actor, role, tenant_id = core["actor"], core["role"], core["tenant_id"]
    require = core["require"]
    authority = core["require_salus_component_authority"]
    require_sensitivity = core["require_sensitivity"]
    security_event = core["security_event"]

    def canonical(value):
        return json.dumps(value, sort_keys=True, separators=(",", ":"),
                          ensure_ascii=False, default=str)

    def parsed(value, fallback):
        try:
            result = json.loads(value)
            return result
        except (TypeError, ValueError, json.JSONDecodeError):
            return fallback

    def detail(item):
        value = parsed(item["detail"], {})
        return value if isinstance(value, dict) else {}

    def salus(request: Request, action: str, permission: str = "read"):
        require(request, permission)
        authority(request, f"SalINTEL governed handoff {action}")

    def investigation(conn, investigation_id: int, request: Request):
        row = conn.execute(
            "SELECT * FROM salintel_investigations WHERE id=?", (investigation_id,)
        ).fetchone()
        if not row:
            raise HTTPException(404, "SalINTEL investigation not found")
        if int(row["tenant_id"]) != tenant_id(request):
            security_event(request, "SALINTEL_HANDOFF_TENANT_BOUNDARY_VIOLATION",
                           "High", f"investigation_id={investigation_id}")
            raise HTTPException(403, "Tenant boundary violation")
        require_sensitivity(request, row["sensitivity"])
        return row

    def target_assessment(conn, assessment_id: int, request: Request):
        row = conn.execute(
            "SELECT id,name,status,tenant_id FROM assessments WHERE id=?", (assessment_id,)
        ).fetchone()
        if not row:
            raise HTTPException(404, "Target SalTHIRA assessment not found")
        if int(row["tenant_id"]) != tenant_id(request):
            security_event(request, "SALINTEL_HANDOFF_ASSESSMENT_BOUNDARY_VIOLATION",
                           "High", f"assessment_id={assessment_id}")
            raise HTTPException(403, "Tenant boundary violation")
        return row

    def investigation_items(conn, investigation_id: int):
        return list(conn.execute(
            "SELECT * FROM salintel_investigation_items WHERE investigation_id=? ORDER BY id",
            (investigation_id,),
        ))

    def eligible_item(item) -> bool:
        value = detail(item)
        record_type = value.get("record_type")
        if record_type not in ELIGIBLE_RECORD_TYPES:
            return False
        if record_type == "salintel_research_product":
            return value.get("review_status") == "Qualified"
        return item["item_kind"] == "Finding"

    def readiness(conn, row):
        domain = conn.execute(
            "SELECT display_name,handoff_types_json FROM salintel_domains WHERE domain_key=?",
            (row["domain_key"],),
        ).fetchone()
        allowed = parsed(domain["handoff_types_json"], []) if domain else []
        blockers = []
        if row["status"] not in ("Tier Complete", "Closed"):
            blockers.append("Complete the authorized bounded tier before creating a handoff.")
        if row["qualification_status"] != "Qualified":
            blockers.append("Obtain final Salus human qualification before creating a handoff.")
        if int(row["completed_tier"]) <= 0:
            blockers.append("A completed investigation tier is required.")
        items = [item for item in investigation_items(conn, row["id"])
                 if eligible_item(item)]
        if not items:
            blockers.append("Select from at least one qualified analytic output.")
        return {
            "ready": not blockers,
            "blockers": blockers,
            "allowed_targets": [target for target in ("SalTHIRA", "SalOPS")
                                if target in allowed],
            "eligible_items": [
                {"id": item["id"], "item_key": item["item_key"],
                 "title": item["title"], "epistemic_state": item["epistemic_state"],
                 "record_type": detail(item).get("record_type")}
                for item in items
            ],
        }

    def event(conn, request: Request, row, event_type: str, reason: str):
        version = int(conn.execute(
            "SELECT COUNT(*) c FROM salintel_investigation_events WHERE investigation_id=?",
            (row["id"],),
        ).fetchone()["c"]) + 1
        current = conn.execute(
            "SELECT * FROM salintel_investigations WHERE id=?", (row["id"],)
        ).fetchone()
        conn.execute(
            "INSERT INTO salintel_investigation_events(tenant_id,investigation_id,version_no,"
            "event_type,reason,snapshot_json,changed_by,changed_by_role,created_at) "
            "VALUES(?,?,?,?,?,?,?,?,?)",
            (row["tenant_id"], row["id"], version, event_type, reason[:4000],
             canonical(dict(current)), actor(request), role(request), now()),
        )

    def audit(conn, request: Request, action: str, entity_id: int, value: str):
        conn.execute(
            "INSERT INTO audit_log(ts,user_name,action,entity_type,entity_id,detail,tenant_id) "
            "VALUES(?,?,?,?,?,?,?)",
            (now(), actor(request), action, "salintel_handoff", entity_id,
             value[:2000], tenant_id(request)),
        )

    def handoff_items(conn, investigation_id: int):
        result = []
        for item in investigation_items(conn, investigation_id):
            value = detail(item)
            if value.get("record_type") != "salintel_handoff":
                continue
            target_status = "Unknown"
            if value.get("target_record_type") == "reassessment_trigger":
                target = conn.execute(
                    "SELECT status FROM reassessment_triggers WHERE id=?",
                    (value.get("target_record_id"),),
                ).fetchone()
                target_status = target["status"] if target else "Unavailable"
            elif value.get("target_record_type") == "ops_request":
                target = conn.execute(
                    "SELECT status FROM ops_requests WHERE id=? AND tenant_id=?",
                    (value.get("target_record_id"), item["tenant_id"]),
                ).fetchone()
                target_status = target["status"] if target else "Unavailable"
            result.append({"id": item["id"], "item_key": item["item_key"],
                           "created_at": item["created_at"],
                           "target_status": target_status, **value})
        return result

    @app.get("/api/salintel/investigations/{investigation_id}/handoffs")
    def get_handoffs(investigation_id: int, request: Request):
        salus(request, "review")
        conn = db()
        try:
            row = investigation(conn, investigation_id, request)
            return {"investigation_id": investigation_id,
                    "readiness": readiness(conn, row),
                    "handoffs": handoff_items(conn, investigation_id)}
        finally:
            conn.close()

    @app.post("/api/salintel/investigations/{investigation_id}/handoffs")
    def create_handoff(investigation_id: int, payload: CreateHandoff,
                       request: Request):
        salus(request, "authorization", "decide")
        conn = db()
        try:
            row = investigation(conn, investigation_id, request)
            state = readiness(conn, row)
            if not state["ready"]:
                raise HTTPException(409, {"message": "Investigation is not ready for handoff.",
                                          "blockers": state["blockers"]})
            if payload.target_component not in state["allowed_targets"]:
                raise HTTPException(409, "The investigative-domain profile does not authorize this handoff target")
            assessment = target_assessment(conn, payload.assessment_id, request)
            selected = []
            for item_id in payload.item_ids:
                item = conn.execute(
                    "SELECT * FROM salintel_investigation_items "
                    "WHERE id=? AND investigation_id=? AND tenant_id=?",
                    (item_id, investigation_id, tenant_id(request)),
                ).fetchone()
                if not item or not eligible_item(item):
                    raise HTTPException(409, "Every handoff item must be a qualified analytic output from this investigation")
                selected.append(item)
            for existing in handoff_items(conn, investigation_id):
                if (existing.get("target_component") == payload.target_component
                        and int(existing.get("assessment_id", 0)) == payload.assessment_id):
                    raise HTTPException(409, "This investigation already has a governed handoff to that component and assessment")

            ts = now()
            domain = conn.execute(
                "SELECT display_name FROM salintel_domains WHERE domain_key=?",
                (row["domain_key"],),
            ).fetchone()
            domain_name = domain["display_name"] if domain else row["domain_key"]
            title = f"{domain_name}: {row['subject_reference']}"
            if payload.target_component == "SalTHIRA":
                cur = conn.execute(
                    "INSERT INTO reassessment_triggers(assessment_id,source,trigger_type,"
                    "description,severity,affected_record_type,affected_record_id,status,"
                    "assigned_to,due_date,resolution,created_at,updated_at) "
                    "VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)",
                    (assessment["id"], "SalINTEL", f"Qualified {domain_name}",
                     payload.summary, "Moderate", "salintel_investigation",
                     investigation_id, "Open", "", "", "", ts, ts),
                )
                target_type, target_id, target_status = "reassessment_trigger", int(cur.lastrowid), "Open"
            else:
                cur = conn.execute(
                    "INSERT INTO ops_requests(tenant_id,assessment_id,source_type,source_id,"
                    "title,description,priority,status,requested_by,requested_at,updated_at) "
                    "VALUES(?,?,?,?,?,?,?,?,?,?,?)",
                    (row["tenant_id"], assessment["id"], "SalINTEL Investigation",
                     investigation_id, title, payload.summary, "Routine", "Requested",
                     actor(request), ts, ts),
                )
                target_type, target_id, target_status = "ops_request", int(cur.lastrowid), "Requested"

            value = {
                "record_type": "salintel_handoff", "schema_version": "1.0",
                "target_component": payload.target_component,
                "assessment_id": int(assessment["id"]),
                "assessment_name_snapshot": assessment["name"],
                "source_domain": row["domain_key"],
                "source_completed_tier": int(row["completed_tier"]),
                "source_qualification_status": row["qualification_status"],
                "selected_item_ids": payload.item_ids,
                "summary": payload.summary, "rationale": payload.rationale,
                "status": "Delivered", "authorized_by": actor(request),
                "authorized_by_role": role(request), "authorized_at": ts,
                "target_record_type": target_type, "target_record_id": target_id,
                "member_disclosure_authorized": False,
                "tier_change_authorized": False,
                "commercial_change_authorized": False,
                "operational_execution_authorized": False,
            }
            cur = conn.execute(
                "INSERT INTO salintel_investigation_items(tenant_id,investigation_id,item_key,"
                "item_kind,epistemic_state,title,detail,source_reliability,"
                "information_confidence,source_material_id,member_visible,created_by,"
                "created_at,updated_at) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                (row["tenant_id"], investigation_id, "SIHO-" + uuid.uuid4().hex,
                 "Handoff", "Analyst Judgment", f"{payload.target_component} governed handoff",
                 canonical(value), "Not Applicable", "Human Qualified", None, 0,
                 actor(request), ts, ts),
            )
            handoff_id = int(cur.lastrowid)
            event(conn, request, row, "SALINTEL_HANDOFF_AUTHORIZED",
                  f"handoff_id={handoff_id}; target={payload.target_component}; "
                  f"target_record={target_type}:{target_id}; assessment_id={assessment['id']}")
            audit(conn, request, "SALINTEL_HANDOFF_AUTHORIZED", handoff_id,
                  f"investigation_id={investigation_id}; target={payload.target_component}; "
                  f"target_record={target_type}:{target_id}")
            conn.commit()
            return {"id": handoff_id, "status": "Delivered",
                    "target_component": payload.target_component,
                    "target_record_type": target_type, "target_record_id": target_id,
                    "target_status": target_status,
                    "member_disclosure_authorized": False,
                    "tier_change_authorized": False,
                    "commercial_change_authorized": False,
                    "operational_execution_authorized": False}
        finally:
            conn.close()
