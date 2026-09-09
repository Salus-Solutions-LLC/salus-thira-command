"""Governed SalCAPA Mission Map and Mission Structure.

Issue #213. Mission Map is a server-derived way-finding projection over governed
records. It shows purpose, current location, ownership, waiting conditions, next
steps, evidence state, and reassessment without allowing the browser to create or
forge workflow position. Protected Member projections expose only explicitly
released member-facing content within the active tenant and sensitivity boundary.
"""
from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone
from typing import Any, Literal, Optional

from fastapi import HTTPException, Query, Request
from pydantic import BaseModel, ConfigDict, Field


NODE_TYPES = (
    "Mission", "Priority", "Objective", "Strategy", "Tactic",
    "Task / Assignment", "Evidence & Result", "Reassessment / Improvement",
)
NODE_RANK = {name: index for index, name in enumerate(NODE_TYPES)}
FUNCTIONAL_AREAS = (
    "Mission Structure", "SalINTEL", "SalTHIRA", "SalCAPA", "SalOPS", "PROVE",
)
EVIDENCE_STATES = (
    "Not Applicable", "Evidence Needed", "Partially Demonstrated",
    "Awaiting Validation", "Demonstrated",
)
WORKFLOW_STATES = (
    "Draft", "Planned", "Awaiting Input", "Awaiting Review", "Awaiting Approval",
    "Authorized", "In Progress", "Waiting", "Completed", "Awaiting Validation",
    "Validated", "Needs Reassessment", "Closed",
)
TRANSITIONS = {
    "Draft": {"Planned"},
    "Planned": {"Awaiting Input", "Awaiting Review", "Awaiting Approval", "Authorized", "Closed"},
    "Awaiting Input": {"Planned", "Awaiting Review", "Awaiting Approval", "Waiting"},
    "Awaiting Review": {"Planned", "Awaiting Approval"},
    "Awaiting Approval": {"Planned", "Authorized"},
    "Authorized": {"In Progress"},
    "In Progress": {"Waiting", "Awaiting Input", "Awaiting Review", "Completed"},
    "Waiting": {"Planned", "Awaiting Input", "Awaiting Review", "Awaiting Approval", "Authorized"},
    "Completed": {"Awaiting Validation", "Validated", "Needs Reassessment", "Closed"},
    "Awaiting Validation": {"In Progress", "Validated", "Needs Reassessment"},
    "Validated": {"Needs Reassessment", "Closed"},
    "Needs Reassessment": {"Planned", "Awaiting Review", "Awaiting Approval", "Authorized", "Closed"},
    "Closed": set(),
}
LINK_TYPES = (
    "Supports", "Depends On", "Produces Evidence For", "Reassesses", "Related To",
)

ROUTES = (
    {
        "key": "mission-structure", "label": "Mission Structure",
        "description": "Purpose and direction: why the work exists and how it contributes.",
        "stations": ["Mission", "Priority", "Objective", "Strategy", "Tactic"],
    },
    {
        "key": "salintel", "label": "SEE — SalINTEL™",
        "description": "Our intelligence process establishes what is known, unknown, changing, and significant.",
        "stations": ["Intake", "Collection", "Analysis", "Qualification", "Qualified"],
    },
    {
        "key": "salthira", "label": "DECIDE — SalTHIRA™ and authorized people",
        "description": "SalTHIRA identifies risk, consequences, capability gaps, and priorities; authorized people decide.",
        "stations": ["Scope", "Context", "Capability Assessment", "Gap / Priority", "Ready for Decision"],
    },
    {
        "key": "salcapa", "label": "COORDINATE — SalCAPA™",
        "description": "SalCAPA coordinates Protected Members, information, decisions, requests, workflows, actions, and status.",
        "stations": ["Intake", "Coordination", "Awaiting Input", "Awaiting Review", "Awaiting Decision", "Authorized", "Handoff"],
    },
    {
        "key": "salops", "label": "ACT — SalOPS™",
        "description": "Our operational teams implement approved priorities and sustain protective capability.",
        "stations": ["Planning", "Assigned", "In Progress", "Waiting", "Completed", "Validation Handoff"],
    },
    {
        "key": "prove", "label": "PROVE — cross-cutting Assurance & Results",
        "description": "Evidence, accountability, results, validation, traceability, learning, and improvement span the work.",
        "stations": ["Evidence Needed", "Evidence Received", "Review", "Awaiting Validation", "Validated", "Results", "Reassessment"],
    },
)
ROUTE_BY_AREA = {
    "Mission Structure": "mission-structure", "SalINTEL": "salintel", "SalTHIRA": "salthira",
    "SalCAPA": "salcapa", "SalOPS": "salops", "PROVE": "prove",
}
MARKER_SHAPES = {
    "Mission": "compass", "Priority": "flag", "Objective": "target", "Strategy": "hexagon",
    "Tactic": "diamond", "Task / Assignment": "square", "Evidence & Result": "circle",
    "Reassessment / Improvement": "loop",
}

PREPAREDNESS_OVERLAY_TYPES = ("Plan", "Training", "Exercise")
PROVE_RECORD_KEYS = {
    "Plan": "preparedness_plan",
    "Training": "preparedness_training",
    "Exercise": "preparedness_exercise",
    "Evidence": "evidence",
    "Improvement": "improvement",
    "Reassessment Trigger": "reassessment_trigger",
    "Operations Request": "ops_request",
    "Operations Task": "ops_task",
}
PLAN_OVERLAY_STATES = {
    "Draft": "Draft", "Reviewed": "Awaiting Approval",
    "Approved": "Authorized", "Retired": "Closed",
}
TRAINING_OVERLAY_STATES = {
    "Draft": "Draft", "Scheduled": "Planned", "In Progress": "In Progress",
    "Completed": "Awaiting Validation", "Cancelled": "Closed",
}
EXERCISE_OVERLAY_STATES = {
    "Planned": "Planned", "Reviewed": "Awaiting Approval", "Approved": "Authorized",
    "In Progress": "In Progress", "Completed": "Awaiting Validation",
    "Evaluated": "Awaiting Validation", "Closed": "Closed", "Cancelled": "Closed",
}

PREPAREDNESS_NEXT_STEPS = {
    "Plan": {
        "Draft": "Review the current draft with the responsible planners and authorities.",
        "Reviewed": "Record the authorized approval decision or return the plan for revision.",
        "Approved": "Maintain the approved plan and review it when conditions or governed review dates require.",
        "Retired": "Use the approved successor or retained historical record as applicable.",
    },
    "Training": {
        "Draft": "Complete the training record and schedule the authorized delivery.",
        "Scheduled": "Deliver the scheduled training and preserve the completion record.",
        "In Progress": "Complete the training and preserve relevant performance evidence.",
        "Completed": "Review completion evidence and determine any validation or follow-up need.",
        "Cancelled": "Review whether replacement training or another capability measure is needed.",
    },
    "Exercise": {
        "Planned": "Review the exercise design and prepare it for the required authority gates.",
        "Reviewed": "Record the authorized approval decision or return the exercise for revision.",
        "Approved": "Coordinate the approved exercise start within the recorded scope and controls.",
        "In Progress": "Conduct the exercise, preserve observations, and maintain real-world safety controls.",
        "Completed": "Evaluate observations and identify any improvement or validation needs.",
        "Evaluated": "Review results, approve any appropriate follow-up actions, and determine closure.",
        "Closed": "Maintain the record and feed validated learning into reassessment and improvement.",
        "Cancelled": "Review whether a replacement exercise or alternate validation method is needed.",
    },
}

MONITORING_PROFILE_STATES = {
    "Awaiting Salus Approval": "Awaiting Approval",
    "Active": "In Progress", "Paused": "Waiting",
    "Completed": "Closed", "Cancelled": "Closed",
}
MONITORING_PROFILE_NEXT_STEPS = {
    "Awaiting Salus Approval": "Authorized Salus personnel review the requested scope, cadence, sources, boundaries, and commercial treatment.",
    "Active": "Continue research at the approved cadence and preserve source-grounded cycle outcomes for Salus review.",
    "Paused": "An authorized person decides whether to resume or end this monitoring profile.",
    "Completed": "Maintain the historical record; future monitoring requires a new governed request and approval.",
    "Cancelled": "Maintain the cancellation record; future monitoring requires a new governed request and approval.",
}

SCHEMA = r"""
CREATE TABLE IF NOT EXISTS salcapa_mission_nodes (
  id TEXT PRIMARY KEY,
  tenant_id INTEGER NOT NULL,
  assessment_id INTEGER,
  node_type TEXT NOT NULL,
  title TEXT NOT NULL,
  purpose TEXT NOT NULL,
  parent_id TEXT,
  functional_area TEXT NOT NULL,
  status TEXT NOT NULL DEFAULT 'Draft',
  owner TEXT NOT NULL DEFAULT '',
  authority TEXT NOT NULL DEFAULT '',
  internal_next_step TEXT NOT NULL DEFAULT '',
  internal_waiting_on TEXT NOT NULL DEFAULT '',
  member_summary TEXT NOT NULL DEFAULT '',
  member_next_step TEXT NOT NULL DEFAULT '',
  member_waiting_on TEXT NOT NULL DEFAULT '',
  member_owner TEXT NOT NULL DEFAULT '',
  evidence_state TEXT NOT NULL DEFAULT 'Not Applicable',
  result_summary TEXT NOT NULL DEFAULT '',
  sensitivity TEXT NOT NULL DEFAULT 'Standard',
  visibility TEXT NOT NULL DEFAULT 'Salus Only',
  created_by TEXT NOT NULL,
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL,
  released_by TEXT NOT NULL DEFAULT '',
  released_at TEXT NOT NULL DEFAULT '',
  FOREIGN KEY (parent_id) REFERENCES salcapa_mission_nodes(id)
);
CREATE INDEX IF NOT EXISTS idx_salcapa_mission_nodes_scope
  ON salcapa_mission_nodes(tenant_id,assessment_id,functional_area,status);
CREATE INDEX IF NOT EXISTS idx_salcapa_mission_nodes_parent
  ON salcapa_mission_nodes(tenant_id,parent_id);

CREATE TABLE IF NOT EXISTS salcapa_mission_links (
  id TEXT PRIMARY KEY,
  tenant_id INTEGER NOT NULL,
  assessment_id INTEGER,
  source_node_id TEXT NOT NULL,
  target_node_id TEXT NOT NULL,
  relationship TEXT NOT NULL,
  basis TEXT NOT NULL,
  created_by TEXT NOT NULL,
  created_at TEXT NOT NULL,
  FOREIGN KEY (source_node_id) REFERENCES salcapa_mission_nodes(id),
  FOREIGN KEY (target_node_id) REFERENCES salcapa_mission_nodes(id)
);
CREATE INDEX IF NOT EXISTS idx_salcapa_mission_links_scope
  ON salcapa_mission_links(tenant_id,assessment_id,source_node_id,target_node_id);

CREATE TABLE IF NOT EXISTS salcapa_mission_events (
  id TEXT PRIMARY KEY,
  tenant_id INTEGER NOT NULL,
  node_id TEXT NOT NULL,
  event_type TEXT NOT NULL,
  from_state TEXT NOT NULL DEFAULT '',
  to_state TEXT NOT NULL DEFAULT '',
  reason TEXT NOT NULL,
  actor_name TEXT NOT NULL,
  member_visible INTEGER NOT NULL DEFAULT 0,
  created_at TEXT NOT NULL,
  FOREIGN KEY (node_id) REFERENCES salcapa_mission_nodes(id)
);
CREATE INDEX IF NOT EXISTS idx_salcapa_mission_events_node
  ON salcapa_mission_events(tenant_id,node_id,created_at);
"""


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class MissionNodeCreate(StrictModel):
    assessment_id: Optional[int] = Field(default=None, gt=0)
    node_type: Literal[
        "Mission", "Priority", "Objective", "Strategy", "Tactic",
        "Task / Assignment", "Evidence & Result", "Reassessment / Improvement",
    ]
    title: str = Field(min_length=3, max_length=240)
    purpose: str = Field(min_length=3, max_length=4000)
    parent_id: Optional[str] = Field(default=None, max_length=80)
    functional_area: Literal["Mission Structure", "SalINTEL", "SalTHIRA", "SalCAPA", "SalOPS", "PROVE"] = "Mission Structure"
    owner: str = Field(default="", max_length=240)
    authority: str = Field(default="", max_length=1000)
    internal_next_step: str = Field(default="", max_length=2000)
    internal_waiting_on: str = Field(default="", max_length=2000)
    member_summary: str = Field(default="", max_length=2000)
    member_next_step: str = Field(default="", max_length=2000)
    member_waiting_on: str = Field(default="", max_length=2000)
    member_owner: str = Field(default="", max_length=240)
    evidence_state: Literal[
        "Not Applicable", "Evidence Needed", "Partially Demonstrated",
        "Awaiting Validation", "Demonstrated",
    ] = "Not Applicable"
    sensitivity: str = Field(default="Standard", min_length=3, max_length=80)


class MissionTransition(StrictModel):
    status: Literal[
        "Draft", "Planned", "Awaiting Input", "Awaiting Review", "Awaiting Approval",
        "Authorized", "In Progress", "Waiting", "Completed", "Awaiting Validation",
        "Validated", "Needs Reassessment", "Closed",
    ]
    reason: str = Field(min_length=3, max_length=4000)
    internal_next_step: Optional[str] = Field(default=None, max_length=2000)
    internal_waiting_on: Optional[str] = Field(default=None, max_length=2000)
    member_next_step: Optional[str] = Field(default=None, max_length=2000)
    member_waiting_on: Optional[str] = Field(default=None, max_length=2000)


class EvidenceStateUpdate(StrictModel):
    evidence_state: Literal[
        "Not Applicable", "Evidence Needed", "Partially Demonstrated",
        "Awaiting Validation", "Demonstrated",
    ]
    result_summary: str = Field(default="", max_length=4000)
    reason: str = Field(min_length=3, max_length=4000)


class MissionLinkCreate(StrictModel):
    source_node_id: str = Field(min_length=3, max_length=80)
    target_node_id: str = Field(min_length=3, max_length=80)
    relationship: Literal["Supports", "Depends On", "Produces Evidence For", "Reassesses", "Related To"]
    basis: str = Field(min_length=3, max_length=3000)


class MemberRelease(StrictModel):
    reason: str = Field(min_length=3, max_length=4000)


def _new_id(prefix: str) -> str:
    return f"{prefix}-{uuid.uuid4().hex}"


def _route_station(node: dict[str, Any]) -> tuple[str, str]:
    area = node["functional_area"]
    status = node["status"]
    if area == "Mission Structure":
        station = node["node_type"] if node["node_type"] in ROUTES[0]["stations"] else "Tactic"
        return "mission-structure", station
    if area == "SalINTEL":
        station = {
            "Draft": "Intake", "Planned": "Intake", "Awaiting Input": "Collection",
            "Waiting": "Collection", "In Progress": "Analysis", "Awaiting Review": "Qualification",
            "Awaiting Approval": "Qualification", "Authorized": "Qualified", "Completed": "Qualified",
            "Awaiting Validation": "Qualification", "Validated": "Qualified", "Needs Reassessment": "Analysis",
            "Closed": "Qualified",
        }[status]
        return "salintel", station
    if area == "SalTHIRA":
        station = {
            "Draft": "Scope", "Planned": "Scope", "Awaiting Input": "Context", "Waiting": "Context",
            "In Progress": "Capability Assessment", "Awaiting Review": "Gap / Priority",
            "Awaiting Approval": "Ready for Decision", "Authorized": "Ready for Decision",
            "Completed": "Ready for Decision", "Awaiting Validation": "Gap / Priority",
            "Validated": "Ready for Decision", "Needs Reassessment": "Capability Assessment", "Closed": "Ready for Decision",
        }[status]
        return "salthira", station
    if area == "SalCAPA":
        station = {
            "Draft": "Intake", "Planned": "Coordination", "Awaiting Input": "Awaiting Input",
            "Waiting": "Coordination", "In Progress": "Coordination", "Awaiting Review": "Awaiting Review",
            "Awaiting Approval": "Awaiting Decision", "Authorized": "Authorized", "Completed": "Handoff",
            "Awaiting Validation": "Handoff", "Validated": "Handoff", "Needs Reassessment": "Coordination", "Closed": "Handoff",
        }[status]
        return "salcapa", station
    if area == "SalOPS":
        station = {
            "Draft": "Planning", "Planned": "Planning", "Awaiting Input": "Waiting", "Waiting": "Waiting",
            "Awaiting Review": "Planning", "Awaiting Approval": "Planning", "Authorized": "Assigned",
            "In Progress": "In Progress", "Completed": "Completed", "Awaiting Validation": "Validation Handoff",
            "Validated": "Completed", "Needs Reassessment": "Planning", "Closed": "Completed",
        }[status]
        return "salops", station
    station = {
        "Draft": "Evidence Needed", "Planned": "Evidence Needed", "Awaiting Input": "Evidence Needed",
        "Waiting": "Evidence Needed", "In Progress": "Evidence Received", "Awaiting Review": "Review",
        "Awaiting Approval": "Review", "Authorized": "Review", "Completed": "Results",
        "Awaiting Validation": "Awaiting Validation", "Validated": "Validated",
        "Needs Reassessment": "Reassessment", "Closed": "Results",
    }[status]
    return "prove", station


def _next_station(route_key: str, station: str, status: str) -> str:
    if status in {"Waiting", "Awaiting Input"}:
        return "Waiting for the stated requirement before movement continues"
    if status == "Closed":
        return "No further movement is currently expected"
    route = next(item for item in ROUTES if item["key"] == route_key)
    stations = route["stations"]
    try:
        index = stations.index(station)
    except ValueError:
        return "Review the governed record to determine the next step"
    if index >= len(stations) - 1:
        return "Review for handoff, validation, reassessment, or closure as applicable"
    return stations[index + 1]


def _record_age(updated_at: str, reference: datetime) -> tuple[int, str]:
    """Return a neutral age measure and band without implying severity or blame."""
    try:
        recorded = datetime.fromisoformat(updated_at.replace("Z", "+00:00"))
        if recorded.tzinfo is None:
            recorded = recorded.replace(tzinfo=timezone.utc)
        age_days = max(0, (reference.date() - recorded.astimezone(timezone.utc).date()).days)
    except (TypeError, ValueError):
        age_days = 0
    if age_days <= 7:
        return age_days, "0–7 days"
    if age_days <= 30:
        return age_days, "8–30 days"
    return age_days, "31+ days"


def _report_time(value: datetime) -> str:
    """Render report preparation time using the approved day-month-year and 24-hour doctrine."""
    return value.astimezone(timezone.utc).strftime("%d %B %Y %H:%M UTC")


def _attention_state(item: dict[str, Any]) -> str:
    if item.get("attention_override"):
        return item["attention_override"]
    if item["status"] == "Needs Reassessment":
        return "Reassessment needed"
    if item["status"] in {"Waiting", "Awaiting Input"} or item.get("waiting_on"):
        return "Waiting / input needed"
    if item["status"] in {"Awaiting Review", "Awaiting Approval", "Awaiting Validation"}:
        return "Review / validation needed"
    if not item.get("owner") or not item.get("next_step"):
        return "Ownership / next step needed"
    return "No recorded hold"


def register_mission_map(app, core: dict[str, Any]) -> None:
    db = core["db"]
    require = core["require"]
    require_salus = core["require_salus_component_authority"]
    require_sensitivity = core["require_sensitivity"]
    tenant_id = core["tenant_id"]
    protected_member = core["protected_member_request"]
    accessible_assessment_ids = core["accessible_assessment_ids"]
    actor = core["actor"]
    role = core["role"]
    audit = core["audit"]
    now = core["now"]
    sensitivity_levels = core["SENSITIVITY_LEVELS"]

    conn = db()
    conn.executescript(SCHEMA)
    conn.commit()
    conn.close()

    def rows(conn, sql: str, params=()):
        return [dict(item) for item in conn.execute(sql, params)]

    def salus_read(request: Request) -> None:
        require(request, "read")
        require_salus(request, "SalCAPA Mission Map")

    def salus_write(request: Request) -> None:
        require(request, "write")
        require_salus(request, "SalCAPA Mission Map")

    def decision_authority(request: Request) -> None:
        require(request, "decide")
        require_salus(request, "SalCAPA Mission Map")

    def assessment_allowed(request: Request, assessment_id: Optional[int]) -> None:
        if assessment_id is None:
            return
        if assessment_id not in set(accessible_assessment_ids(request)):
            raise HTTPException(403, "Assessment access denied")
        conn = db()
        found = conn.execute("SELECT tenant_id,classification FROM assessments WHERE id=?", (assessment_id,)).fetchone()
        conn.close()
        if not found:
            raise HTTPException(404, "Assessment not found")
        if int(found["tenant_id"]) != tenant_id(request):
            raise HTTPException(403, "Assessment access denied")
        require_sensitivity(request, found["classification"])

    def node_for_request(conn, request: Request, node_id: str, *, member_release_required: bool = False) -> dict[str, Any]:
        found = conn.execute(
            "SELECT * FROM salcapa_mission_nodes WHERE id=? AND tenant_id=?", (node_id, tenant_id(request))
        ).fetchone()
        if not found:
            raise HTTPException(404, "Mission Structure item not found")
        node = dict(found)
        assessment_allowed(request, node["assessment_id"])
        require_sensitivity(request, node["sensitivity"])
        if (member_release_required or protected_member(request)) and node["visibility"] != "Released":
            raise HTTPException(404, "Mission Structure item not found")
        return node

    def validate_parent(conn, request: Request, payload: MissionNodeCreate) -> None:
        if not payload.parent_id:
            return
        parent = node_for_request(conn, request, payload.parent_id)
        if parent["assessment_id"] != payload.assessment_id:
            raise HTTPException(409, "Parent and child must share the same governed assessment scope")
        if NODE_RANK[parent["node_type"]] >= NODE_RANK[payload.node_type]:
            raise HTTPException(409, "Mission Structure parent must be a higher-level purpose element")

    def event(conn, request: Request, node_id: str, event_type: str, reason: str,
              from_state: str = "", to_state: str = "", member_visible: bool = False) -> None:
        conn.execute(
            "INSERT INTO salcapa_mission_events(id,tenant_id,node_id,event_type,from_state,to_state,reason,actor_name,member_visible,created_at) VALUES(?,?,?,?,?,?,?,?,?,?)",
            (_new_id("mme"), tenant_id(request), node_id, event_type, from_state, to_state,
             reason, actor(request), 1 if member_visible else 0, now()),
        )

    def safe_projection(request: Request, node: dict[str, Any]) -> dict[str, Any]:
        is_member = protected_member(request)
        route_key, station = _route_station(node)
        next_station = _next_station(route_key, station, node["status"])
        common = {
            "id": node["id"], "assessment_id": node["assessment_id"],
            "node_type": node["node_type"], "title": node["title"],
            "functional_area": node["functional_area"], "status": node["status"],
            "route_key": route_key, "station": station, "next_station": next_station,
            "marker_shape": MARKER_SHAPES[node["node_type"]],
            "evidence_state": node["evidence_state"], "updated_at": node["updated_at"],
            "released_at": node["released_at"] if is_member else node["released_at"],
        }
        if is_member:
            common.update({
                "purpose": node["member_summary"], "owner": node["member_owner"],
                "next_step": node["member_next_step"], "waiting_on": node["member_waiting_on"],
                "result_summary": node["result_summary"] if node["evidence_state"] == "Demonstrated" else "",
                "guidance": "This view shows released work in your authorized scope. Salus personnel retain review, decision, release, and operational authority as applicable.",
            })
        else:
            common.update({
                "purpose": node["purpose"], "owner": node["owner"], "authority": node["authority"],
                "next_step": node["internal_next_step"], "waiting_on": node["internal_waiting_on"],
                "result_summary": node["result_summary"], "visibility": node["visibility"],
                "sensitivity": node["sensitivity"],
                "guidance": "Mission Map reflects governed server state. Move work through controlled records and human authority; do not treat visual position as a substitute for the underlying record.",
            })
        return common

    def preparedness_plan_path(conn, request: Request, plan_id: Optional[str]) -> list[dict[str, Any]]:
        """Return only a plan reference already authorized for the requesting role."""
        if not plan_id:
            return []
        found = conn.execute(
            "SELECT id,tenant_id,assessment_id,title,status,sensitivity FROM salops_preparedness_plans "
            "WHERE id=? AND tenant_id=?", (plan_id, tenant_id(request)),
        ).fetchone()
        if not found:
            return []
        plan = dict(found)
        if plan["assessment_id"] is not None and plan["assessment_id"] not in set(accessible_assessment_ids(request)):
            return []
        try:
            require_sensitivity(request, plan["sensitivity"])
        except HTTPException:
            return []
        if protected_member(request) and plan["status"] != "Approved":
            return []
        return [{"id": f"salops-plan:{plan['id']}", "node_type": "Plan", "title": plan["title"]}]

    def preparedness_overlay(
        request: Request,
        source_type: str,
        source: dict[str, Any],
    ) -> dict[str, Any]:
        """Project an authoritative SalOPS record without duplicating or changing it."""
        source_status = source["status"]
        if source_type == "Plan":
            status = PLAN_OVERLAY_STATES[source_status]
            purpose = source.get("purpose") or source.get("scope_statement") or "Plan purpose is not yet recorded."
            owner = source.get("owner", "")
            evidence_state = "Not Applicable"
            marker_shape = "hexagon"
            released_at = source.get("approved_at", "")
            authority = "Plan approval and member adoption remain governed by the SalOPS plan record and authorized people."
        elif source_type == "Training":
            status = TRAINING_OVERLAY_STATES[source_status]
            purpose = source.get("objective") or "Training objective is not yet recorded."
            owner = source.get("instructor", "")
            evidence_state = "Awaiting Validation" if source_status == "Completed" else (
                "Not Applicable" if source_status == "Cancelled" else "Evidence Needed"
            )
            marker_shape = "square"
            released_at = source.get("released_at", "")
            authority = "Training delivery, completion, disclosure, and capability judgments remain governed by the authoritative training record and authorized people."
        else:
            status = EXERCISE_OVERLAY_STATES[source_status]
            purpose = source.get("purpose") or source.get("scope_statement") or "Exercise purpose is not yet recorded."
            owner = ""
            evidence_state = "Awaiting Validation" if source_status in {"Completed", "Evaluated", "Closed"} else (
                "Not Applicable" if source_status == "Cancelled" else "Evidence Needed"
            )
            marker_shape = "circle"
            released_at = source.get("approved_at", "")
            authority = "Exercise approval, conduct, evaluation, and closure remain governed by the authoritative exercise record and authorized people."
        item = {
            "id": f"salops-{source_type.casefold()}:{source['id']}",
            "assessment_id": source.get("assessment_id"),
            "node_type": source_type,
            "title": source["title"], "functional_area": "SalOPS", "status": status,
            "route_key": "salops", "station": _route_station({"functional_area": "SalOPS", "status": status})[1],
            "marker_shape": marker_shape, "evidence_state": evidence_state,
            "updated_at": source["updated_at"], "released_at": released_at,
            "purpose": purpose, "owner": owner, "waiting_on": "",
            "next_step": PREPAREDNESS_NEXT_STEPS[source_type][source_status],
            "result_summary": "", "read_only": True,
            "projection_kind": "Preparedness overlay", "source_type": source_type,
            "source_id": source["id"], "source_status": source_status,
            "projection_basis": (
                "Read-only projection of the authoritative SalOPS preparedness record. "
                "Change status, ownership, dates, or disclosure only in that source record."
            ),
            "guidance": (
                "This marker reflects the current authorized SalOPS record. It does not create a new assignment, "
                "approval, completion judgment, or readiness finding."
            ),
        }
        route_key, station = _route_station(item)
        item["route_key"], item["station"] = route_key, station
        item["next_station"] = _next_station(route_key, station, status)
        if not protected_member(request):
            item.update({
                "authority": authority, "visibility": (
                    "Released" if (
                        (source_type == "Plan" and source_status == "Approved")
                        or (source_type == "Training" and source.get("member_release_status") == "Released")
                        or (source_type == "Exercise" and source_status in {"Approved", "In Progress", "Completed", "Evaluated", "Closed"})
                    ) else "Salus Only"
                ),
                "sensitivity": source.get("sensitivity", "Inherited from governed scope"),
            })
        return item

    def preparedness_overlays(
        conn, request: Request, assessment_id: Optional[int], workflow_status: Optional[str],
    ) -> list[dict[str, Any]]:
        """Read role-safe source rows using the disclosure rules of SalOPS Preparedness."""
        tid = tenant_id(request)
        is_member = protected_member(request)
        permitted_assessments = set(accessible_assessment_ids(request))
        if is_member:
            specs = (
                ("Plan", "SELECT * FROM salops_preparedness_plans WHERE tenant_id=? AND status='Approved'"),
                ("Training", "SELECT * FROM salops_preparedness_training WHERE tenant_id=? AND member_release_status='Released'"),
                ("Exercise", "SELECT * FROM salops_preparedness_exercises WHERE tenant_id=? AND status IN ('Approved','In Progress','Completed','Evaluated','Closed')"),
            )
        else:
            specs = (
                ("Plan", "SELECT * FROM salops_preparedness_plans WHERE tenant_id=?"),
                ("Training", "SELECT * FROM salops_preparedness_training WHERE tenant_id=?"),
                ("Exercise", "SELECT * FROM salops_preparedness_exercises WHERE tenant_id=?"),
            )
        projected: list[dict[str, Any]] = []
        for source_type, sql in specs:
            params: list[Any] = [tid]
            if assessment_id is not None:
                sql += " AND assessment_id=?"
                params.append(assessment_id)
            sql += " ORDER BY updated_at,id"
            for found in conn.execute(sql, tuple(params)):
                source = dict(found)
                if source.get("assessment_id") is not None and source["assessment_id"] not in permitted_assessments:
                    continue
                sensitivity = source.get("sensitivity")
                if source_type == "Training" and source.get("plan_id"):
                    plan = conn.execute(
                        "SELECT sensitivity,status FROM salops_preparedness_plans WHERE id=? AND tenant_id=?",
                        (source["plan_id"], tid),
                    ).fetchone()
                    if plan:
                        sensitivity = plan["sensitivity"]
                if sensitivity:
                    try:
                        require_sensitivity(request, sensitivity)
                    except HTTPException:
                        continue
                item = preparedness_overlay(request, source_type, source)
                if workflow_status is not None and item["status"] != workflow_status:
                    continue
                item["mission_path"] = (
                    [] if source_type == "Plan" else preparedness_plan_path(conn, request, source.get("plan_id"))
                )
                projected.append(item)
        return projected

    def monitoring_records(conn, investigation_id: int) -> list[dict[str, Any]]:
        result: list[dict[str, Any]] = []
        for stored in conn.execute(
            "SELECT id,detail,created_at,updated_at FROM salintel_investigation_items "
            "WHERE investigation_id=? ORDER BY id", (investigation_id,),
        ):
            try:
                value = json.loads(stored["detail"])
            except (TypeError, ValueError, json.JSONDecodeError):
                continue
            if not isinstance(value, dict) or not str(value.get("record_type", "")).startswith("salintel_monitoring_"):
                continue
            value["_record_id"] = int(stored["id"])
            value["_created_at"] = stored["created_at"]
            value["_updated_at"] = stored["updated_at"]
            result.append(value)
        return result

    def monitoring_common(
        request: Request, investigation: dict[str, Any], *, marker_id: str,
        title: str, node_type: str, status: str, purpose: str, owner: str,
        waiting_on: str, next_step: str, evidence_state: str, updated_at: str,
        source_type: str, source_id: str, source_status: str,
    ) -> dict[str, Any]:
        item = {
            "id": marker_id, "assessment_id": None, "node_type": node_type,
            "title": title, "functional_area": "SalINTEL", "status": status,
            "marker_shape": "loop" if source_type == "Monitoring Profile" else "circle",
            "evidence_state": evidence_state, "updated_at": updated_at,
            "released_at": investigation.get("disclosed_at", ""),
            "purpose": purpose, "owner": owner, "waiting_on": waiting_on,
            "next_step": next_step, "result_summary": "", "read_only": True,
            "projection_kind": "Ongoing monitoring overlay", "source_type": source_type,
            "source_id": source_id, "source_status": source_status,
            "projection_basis": (
                "Read-only projection of the authoritative SalINTEL monitoring record. "
                "Change scope, cadence, lifecycle, review, or disclosure only through that governed source record."
            ),
            "guidance": (
                "Ongoing Monitoring remains separate from investigation depth. A marker does not activate monitoring, "
                "change a tier, reopen an investigation, create a charge, release information, or authorize external action."
            ),
            "mission_path": [],
        }
        route_key, station = _route_station(item)
        item["route_key"], item["station"] = route_key, station
        item["next_station"] = _next_station(route_key, station, status)
        if not protected_member(request):
            item.update({
                "authority": "Monitoring authority, human qualification, disclosure, tier changes, and action decisions remain with authorized people.",
                "visibility": "Released" if investigation["disclosure_status"] == "Approved for Tenant" else "Salus Only",
                "sensitivity": investigation["sensitivity"],
                "scope_note": "Tenant-level SalINTEL record; no governed assessment relationship is recorded.",
            })
        return item

    def monitoring_overlays(
        conn, request: Request, assessment_id: Optional[int], workflow_status: Optional[str],
    ) -> list[dict[str, Any]]:
        """Project current monitoring profiles and Salus-only latest cycle review state."""
        if assessment_id is not None:
            return []
        is_member = protected_member(request)
        if is_member:
            investigations = conn.execute(
                "SELECT * FROM salintel_investigations WHERE tenant_id=? AND disclosure_status='Approved for Tenant' "
                "ORDER BY updated_at,id", (tenant_id(request),),
            )
        else:
            investigations = conn.execute(
                "SELECT * FROM salintel_investigations WHERE tenant_id=? ORDER BY updated_at,id",
                (tenant_id(request),),
            )
        projected: list[dict[str, Any]] = []
        for found in investigations:
            investigation = dict(found)
            try:
                require_sensitivity(request, investigation["sensitivity"])
            except HTTPException:
                continue
            records = monitoring_records(conn, int(investigation["id"]))
            profiles: dict[str, dict[str, Any]] = {}
            for value in records:
                if value.get("record_type") != "salintel_monitoring_profile":
                    continue
                profile_key = str(value.get("profile_key", ""))
                if not profile_key:
                    continue
                if profile_key not in profiles or int(value.get("version_no", 0)) > int(profiles[profile_key].get("version_no", 0)):
                    profiles[profile_key] = value
            for profile_key, profile in profiles.items():
                source_status = str(profile.get("status", ""))
                if profile.get("explicit_selection") != "Yes" or source_status not in MONITORING_PROFILE_STATES:
                    continue
                if is_member and profile.get("requested_by") != actor(request):
                    continue
                status = MONITORING_PROFILE_STATES[source_status]
                if workflow_status is not None and status != workflow_status:
                    pass
                else:
                    owner = "Authorized Salus reviewer" if source_status == "Awaiting Salus Approval" else (
                        "Authorized Salus decision-maker" if source_status == "Paused" else ""
                    )
                    waiting_on = "Salus approval" if source_status == "Awaiting Salus Approval" else (
                        ("Recorded lifecycle decision" if is_member else str(profile.get("lifecycle_reason", "") or "Recorded lifecycle decision"))
                        if source_status == "Paused" else ""
                    )
                    purpose = str(
                        profile.get("approved_scope") or profile.get("requested_scope")
                        or profile.get("purpose") or investigation["purpose"]
                    )
                    item = monitoring_common(
                        request, investigation,
                        marker_id=f"salintel-monitoring:{investigation['id']}:{profile_key}",
                        title=f"Ongoing Monitoring — {investigation['title']}",
                        node_type="Ongoing Monitoring", status=status, purpose=purpose,
                        owner=owner, waiting_on=waiting_on,
                        next_step=MONITORING_PROFILE_NEXT_STEPS[source_status],
                        evidence_state="Not Applicable", updated_at=profile["_updated_at"],
                        source_type="Monitoring Profile", source_id=profile_key,
                        source_status=source_status,
                    )
                    item["cadence"] = profile.get("cadence") or profile.get("requested_cadence") or ""
                    projected.append(item)
                if is_member:
                    continue
                executions = [value for value in records if value.get("record_type") == "salintel_monitoring_cycle_execution" and value.get("profile_key") == profile_key]
                if not executions:
                    continue
                execution = max(executions, key=lambda value: int(value.get("cycle_number", 0)))
                outcomes = [value for value in records if value.get("record_type") == "salintel_monitoring_cycle_outcome" and int(value.get("execution_id", 0)) == execution["_record_id"]]
                if not outcomes:
                    status = "Awaiting Input"
                    if workflow_status is None or workflow_status == status:
                        projected.append(monitoring_common(
                            request, investigation,
                            marker_id=f"salintel-monitoring-cycle:{investigation['id']}:{execution['_record_id']}",
                            title=f"Monitoring cycle {execution.get('cycle_number', '')} — {investigation['title']}",
                            node_type="Monitoring Cycle", status=status,
                            purpose="Complete the governed cycle by recording its source-grounded outcome.",
                            owner="Authorized Salus analyst", waiting_on="Source-grounded monitoring outcome",
                            next_step="Record the monitoring outcome, evidence basis, uncertainty, and implications for Salus review.",
                            evidence_state="Evidence Needed", updated_at=execution["_updated_at"],
                            source_type="Monitoring Cycle", source_id=str(execution["_record_id"]),
                            source_status=str(execution.get("status", "Outcome required")),
                        ))
                    continue
                outcome = max(outcomes, key=lambda value: int(value["_record_id"]))
                reviews = [value for value in records if value.get("record_type") == "salintel_monitoring_outcome_review" and int(value.get("outcome_id", 0)) == outcome["_record_id"]]
                review = max(reviews, key=lambda value: int(value["_record_id"])) if reviews else None
                decision = str(review.get("decision")) if review else "Awaiting Salus Review"
                if decision == "Qualified":
                    status, owner, waiting_on = "Completed", "Authorized decision-maker", ""
                    next_step = "Determine whether a governed reassessment, coordination step, protective action, or continued watch is appropriate."
                    result = "Salus human review qualified the monitoring outcome; this does not itself authorize disclosure, reassessment, a tier change, investigation reopening, charges, or external action."
                elif decision == "Return for Supplement":
                    status, owner, waiting_on = "Awaiting Input", "Authorized Salus analyst", "Additional source-grounded information"
                    next_step = "Supplement the outcome within the approved scope and return it for Salus review."
                    result = "The outcome was returned for additional support and is not a qualified finding."
                elif decision == "Rejected":
                    status, owner, waiting_on = "Closed", "", ""
                    next_step = "Maintain the preserved outcome and separate rejection record; no action follows from the rejected outcome."
                    result = "Salus human review rejected the outcome; it must not be treated as a qualified finding."
                else:
                    status, owner, waiting_on = "Awaiting Review", "Authorized Salus reviewer", "Salus human qualification"
                    next_step = "Review the source basis, distinctions, contradictions, uncertainty, and implications before any further decision."
                    result = "Reported monitoring outcome awaiting Salus human qualification; it is not a final finding or decision."
                if workflow_status is not None and status != workflow_status:
                    continue
                item = monitoring_common(
                    request, investigation,
                    marker_id=f"salintel-monitoring-outcome:{investigation['id']}:{outcome['_record_id']}",
                    title=f"Monitoring outcome — {outcome.get('outcome', 'Review required')} — {investigation['title']}",
                    node_type="Monitoring Outcome", status=status,
                    purpose="Review the source-grounded monitoring outcome and determine the authorized next step.",
                    owner=owner, waiting_on=waiting_on, next_step=next_step,
                    evidence_state="Not Applicable" if decision in {"Qualified", "Rejected"} else "Awaiting Validation",
                    updated_at=(review or outcome)["_updated_at"],
                    source_type="Monitoring Outcome", source_id=str(outcome["_record_id"]),
                    source_status=decision,
                )
                item["result_summary"] = result
                item["reported_outcome"] = outcome.get("outcome", "")
                if decision == "Qualified" and outcome.get("outcome") in {"Material Change", "Escalation / Immediate Attention"}:
                    item["attention_override"] = "Decision / coordination needed"
                projected.append(item)
        return projected

    def assurance_views(
        conn, request: Request, selected_assessment_id: Optional[int],
    ) -> list[tuple[dict[str, Any], dict[str, Any]]]:
        """Reuse PROVE's role-aware assurance projection; never duplicate its lifecycle."""
        builder = getattr(request.app.state, "salcapa_assurance_builder", None)
        if not callable(builder):
            return []
        allowed = set(accessible_assessment_ids(request))
        params: list[Any] = [tenant_id(request)]
        sql = "SELECT * FROM assessments WHERE tenant_id=?"
        if selected_assessment_id is not None:
            sql += " AND id=?"
            params.append(selected_assessment_id)
        sql += " ORDER BY id"
        result: list[tuple[dict[str, Any], dict[str, Any]]] = []
        for found in conn.execute(sql, tuple(params)):
            assessment = dict(found)
            if int(assessment["id"]) not in allowed:
                continue
            try:
                require_sensitivity(request, assessment["classification"])
            except HTTPException:
                continue
            result.append((assessment, builder(conn, request, assessment)))
        return result

    def prove_record_key(item: dict[str, Any]) -> Optional[str]:
        prefix = PROVE_RECORD_KEYS.get(str(item.get("source_type", "")))
        source_id = item.get("source_id")
        if prefix and source_id not in (None, ""):
            return f"{prefix}:{source_id}"
        return None

    def apply_prove_trace(
        item: dict[str, Any], assurance_by_assessment: dict[int, dict[str, Any]], is_member: bool,
    ) -> None:
        """Attach only explicit PROVE relationships already permitted for this request."""
        aid = item.get("assessment_id")
        record_key = prove_record_key(item)
        assurance = assurance_by_assessment.get(int(aid)) if aid is not None else None
        if not record_key or not assurance:
            return
        nodes = {node["key"]: node for node in assurance["nodes"]}
        if record_key not in nodes:
            return
        relationships: list[dict[str, Any]] = []
        for edge in assurance["explicit_edges"]:
            if edge["source"] == record_key:
                linked_key, direction = edge["target"], "supports"
            elif edge["target"] == record_key:
                linked_key, direction = edge["source"], "supported by"
            else:
                continue
            linked = nodes.get(linked_key)
            if not linked:
                continue
            relationships.append({
                "direction": direction,
                "relationship": edge["relationship"],
                "linked_record_key": linked_key,
                "linked_record_type": linked["record_type"],
                "linked_label": linked["label"],
                "linked_status": linked["status"],
                "basis": "Explicit relationship in authoritative source records",
            })
        gaps = [] if is_member else [
            {"stage": gap["stage"], "reason": gap["reason"]}
            for gap in assurance["assurance_gaps"] if gap.get("record_key") == record_key
        ]
        if gaps:
            state = "Trace gap identified"
        elif relationships:
            state = "Explicit trace recorded"
        else:
            state = "No released explicit trace available" if is_member else "No explicit trace recorded"
        item["prove_trace"] = {
            "record_key": record_key,
            "state": state,
            "explicit_relationships": relationships,
            "relationship_count": len(relationships),
            "gaps": gaps,
            "guidance": (
                "PROVE shows explicit persisted relationships and qualifying evidence available to this authorized view. "
                "Absence of a link is an information gap, not proof that work, evidence, or a result does not exist."
            ),
        }

    def prove_gap_overlay(
        request: Request, assessment: dict[str, Any], gap: dict[str, Any], reference: datetime,
    ) -> dict[str, Any]:
        """Present an internal trace gap without converting it into a finding or decision."""
        stage = str(gap["stage"])
        lowered = stage.casefold()
        status = "Needs Reassessment" if "reassessment" in lowered else (
            "Awaiting Validation" if "validation" in lowered or "evidence" in lowered else "Awaiting Review"
        )
        evidence_state = "Awaiting Validation" if "validation" in lowered else "Evidence Needed"
        item = {
            "id": f"prove-gap:{assessment['id']}:{gap['gap_key']}",
            "assessment_id": int(assessment["id"]),
            "node_type": "Evidence & Result",
            "title": f"Trace review — {stage}",
            "functional_area": "PROVE", "status": status,
            "marker_shape": "circle", "evidence_state": evidence_state,
            "updated_at": reference.astimezone(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z"),
            "released_at": "", "purpose": str(gap["reason"]),
            "owner": "Authorized Salus reviewer",
            "waiting_on": "Qualifying persisted evidence or an explicit governed relationship",
            "next_step": (
                "Review the cited source records and preserve any missing evidence or explicit relationship in the authoritative source. "
                "An authorized reviewer determines what follows."
            ),
            "result_summary": (
                "No conclusion is established by this gap. It identifies missing qualifying persisted support or a missing explicit link."
            ),
            "read_only": True, "projection_kind": "PROVE assurance gap overlay",
            "source_type": "PROVE Assurance Gap", "source_id": gap["gap_key"],
            "source_status": "Evidence or trace review needed",
            "projection_basis": (
                "Read-only projection from the existing PROVE assurance model. Resolve it through the authoritative source record; "
                "Mission Map cannot create evidence, validate a result, or close this gap."
            ),
            "guidance": (
                "A trace gap is not a score, fault determination, adverse judgment, or proof that the underlying work did not occur."
            ),
            "authority": "Evidence qualification, validation, disclosure, and resulting decisions remain with authorized people.",
            "visibility": "Salus Only", "sensitivity": assessment["classification"],
            "mission_path": [], "attention_override": "Review / validation needed",
            "prove_trace": {
                "record_key": gap.get("record_key") or "",
                "state": "Trace gap identified", "explicit_relationships": [],
                "relationship_count": 0,
                "gaps": [{"stage": stage, "reason": str(gap["reason"])}],
                "guidance": "Review authoritative records and preserve explicit evidence or trace relationships when available.",
            },
        }
        item["route_key"], item["station"] = _route_station(item)
        item["next_station"] = _next_station(item["route_key"], item["station"], status)
        return item

    def parent_path(conn, request: Request, node: dict[str, Any]) -> list[dict[str, Any]]:
        path: list[dict[str, Any]] = []
        seen: set[str] = set()
        current = node
        for _ in range(16):
            parent_id = current.get("parent_id")
            if not parent_id:
                break
            if parent_id in seen:
                raise HTTPException(409, "Mission Structure hierarchy contains a cycle")
            seen.add(parent_id)
            parent = node_for_request(conn, request, parent_id, member_release_required=protected_member(request))
            path.append({"id": parent["id"], "node_type": parent["node_type"], "title": parent["title"]})
            current = parent
        return list(reversed(path))

    @app.get("/api/salcapa/mission-map/catalog")
    def mission_map_catalog(request: Request):
        require(request, "read")
        return {
            "name": "Mission Map", "node_types": list(NODE_TYPES),
            "functional_areas": list(FUNCTIONAL_AREAS), "workflow_states": list(WORKFLOW_STATES),
            "evidence_states": list(EVIDENCE_STATES), "link_types": list(LINK_TYPES),
            "attention_states": [
                "Waiting / input needed", "Review / validation needed", "Reassessment needed",
                "Decision / coordination needed", "Ownership / next step needed", "No recorded hold",
            ],
            "routes": list(ROUTES), "marker_shapes": MARKER_SHAPES,
            "preparedness_overlay_types": list(PREPAREDNESS_OVERLAY_TYPES),
            "mission_structure": "Mission → Priorities → Objectives → Strategies → Tactics → Tasks / Assignments → Evidence & Results → Reassessment / Improvement",
            "principle": "People lead. Methods guide. Technology supports. Evidence proves.",
            "filter_guidance": "Filters narrow the records already authorized for your view. They do not change scope, priority, ownership, or workflow state.",
            "overlay_guidance": "Plans, training, exercises, and ongoing monitoring appear as read-only projections of their authoritative records. Update the source record to change state, scope, cadence, dates, ownership, review, or disclosure.",
            "report_guidance": "Prepare a printable summary of this authorized view. Printing does not approve, release, validate, assign, or change the underlying work.",
            "keyboard_guidance": "Use Tab to reach a route, then use the arrow keys, Home, or End to move among its work markers. Select a marker to review its governed details.",
            "accessibility_guidance": "Route names, station labels, marker shapes, text states, and the conventional list provide equivalent meaning without relying on color, pointer use, or animation.",
            "prove_guidance": "PROVE is the cross-cutting Assurance & Results layer. It shows qualifying evidence, explicit persisted relationships, validation needs, results, and learning without creating facts, authority, or a separate fifth product.",
        }

    @app.get("/api/salcapa/mission-map")
    def mission_map(
        request: Request,
        assessment_id: Optional[int] = Query(default=None, gt=0),
        functional_area: Optional[Literal[
            "Mission Structure", "SalINTEL", "SalTHIRA", "SalCAPA", "SalOPS", "PROVE",
        ]] = None,
        workflow_status: Optional[Literal[
            "Draft", "Planned", "Awaiting Input", "Awaiting Review", "Awaiting Approval",
            "Authorized", "In Progress", "Waiting", "Completed", "Awaiting Validation",
            "Validated", "Needs Reassessment", "Closed",
        ]] = None,
        attention: Optional[Literal[
            "Waiting / input needed", "Review / validation needed", "Reassessment needed",
            "Decision / coordination needed", "Ownership / next step needed", "No recorded hold",
        ]] = None,
        owner: Optional[str] = Query(default=None, max_length=120),
    ):
        require(request, "read")
        assessment_allowed(request, assessment_id)
        tid = tenant_id(request)
        conn = db()
        sql = "SELECT * FROM salcapa_mission_nodes WHERE tenant_id=?"
        params: list[Any] = [tid]
        if assessment_id is not None:
            sql += " AND assessment_id=?"
            params.append(assessment_id)
        if functional_area is not None:
            sql += " AND functional_area=?"
            params.append(functional_area)
        if workflow_status is not None:
            sql += " AND status=?"
            params.append(workflow_status)
        if protected_member(request):
            sql += " AND visibility='Released'"
        sql += " ORDER BY created_at,id"
        visible: list[dict[str, Any]] = []
        try:
            reference = datetime.fromisoformat(now().replace("Z", "+00:00"))
            if reference.tzinfo is None:
                reference = reference.replace(tzinfo=timezone.utc)
        except (TypeError, ValueError):
            reference = datetime.now(timezone.utc)
        is_member = protected_member(request)
        assurance_pairs = assurance_views(conn, request, assessment_id)
        assurance_by_assessment = {
            int(assessment["id"]): assurance for assessment, assurance in assurance_pairs
        }
        for item in conn.execute(sql, tuple(params)):
            node = dict(item)
            if node["assessment_id"] is not None and node["assessment_id"] not in set(accessible_assessment_ids(request)):
                continue
            try:
                require_sensitivity(request, node["sensitivity"])
            except HTTPException:
                continue
            projected = safe_projection(request, node)
            projected["age_days"], projected["age_band"] = _record_age(node["updated_at"], reference)
            projected["attention"] = _attention_state(projected)
            if owner and owner.strip().casefold() not in projected.get("owner", "").casefold():
                continue
            if attention and projected["attention"] != attention:
                continue
            try:
                projected["mission_path"] = parent_path(conn, request, node)
            except HTTPException:
                if protected_member(request):
                    projected["mission_path"] = []
                else:
                    raise
            visible.append(projected)
        if functional_area in (None, "SalOPS"):
            for projected in preparedness_overlays(conn, request, assessment_id, workflow_status):
                projected["age_days"], projected["age_band"] = _record_age(projected["updated_at"], reference)
                projected["attention"] = _attention_state(projected)
                if owner and owner.strip().casefold() not in projected.get("owner", "").casefold():
                    continue
                if attention and projected["attention"] != attention:
                    continue
                visible.append(projected)
        for projected in visible:
            apply_prove_trace(projected, assurance_by_assessment, is_member)
        if functional_area == "PROVE" and not is_member:
            for assessment, assurance in assurance_pairs:
                for gap in assurance["assurance_gaps"]:
                    projected = prove_gap_overlay(request, assessment, gap, reference)
                    if workflow_status is not None and projected["status"] != workflow_status:
                        continue
                    projected["age_days"], projected["age_band"] = 0, "0–7 days"
                    projected["attention"] = _attention_state(projected)
                    projected.pop("attention_override", None)
                    if owner and owner.strip().casefold() not in projected["owner"].casefold():
                        continue
                    if attention and projected["attention"] != attention:
                        continue
                    visible.append(projected)
        if functional_area in (None, "SalINTEL"):
            for projected in monitoring_overlays(conn, request, assessment_id, workflow_status):
                projected["age_days"], projected["age_band"] = _record_age(projected["updated_at"], reference)
                projected["attention"] = _attention_state(projected)
                projected.pop("attention_override", None)
                if owner and owner.strip().casefold() not in projected.get("owner", "").casefold():
                    continue
                if attention and projected["attention"] != attention:
                    continue
                visible.append(projected)
        by_route = {route["key"]: 0 for route in ROUTES}
        by_status: dict[str, int] = {}
        by_evidence: dict[str, int] = {}
        by_attention: dict[str, int] = {}
        by_age = {"0–7 days": 0, "8–30 days": 0, "31+ days": 0}
        for item in visible:
            by_route[item["route_key"]] += 1
            by_status[item["status"]] = by_status.get(item["status"], 0) + 1
            by_evidence[item["evidence_state"]] = by_evidence.get(item["evidence_state"], 0) + 1
            by_attention[item["attention"]] = by_attention.get(item["attention"], 0) + 1
            by_age[item["age_band"]] += 1
        visible_ids = {item["id"] for item in visible}
        links = []
        for item in conn.execute(
            "SELECT * FROM salcapa_mission_links WHERE tenant_id=? ORDER BY created_at,id", (tid,)
        ):
            link = dict(item)
            if link["source_node_id"] in visible_ids and link["target_node_id"] in visible_ids:
                links.append({
                    "id": link["id"], "source_node_id": link["source_node_id"],
                    "target_node_id": link["target_node_id"], "relationship": link["relationship"],
                    "basis": "Released governed relationship" if protected_member(request) else link["basis"],
                })
        conn.close()
        active_filters = {
            "functional_area": functional_area, "workflow_status": workflow_status,
            "attention": attention, "owner": owner.strip() if owner else None,
        }
        if is_member:
            member_relationships = {
                (item["prove_trace"]["record_key"], relation["linked_record_key"], relation["relationship"])
                for item in visible if item.get("prove_trace")
                for relation in item["prove_trace"]["explicit_relationships"]
            }
            explicit_relationship_count = len(member_relationships)
        else:
            explicit_relationship_count = sum(
                len(assurance["explicit_edges"]) for _, assurance in assurance_pairs
            )
        prove_traceability = {
            "available_assessment_count": len(assurance_pairs),
            "items_with_trace_context": len([item for item in visible if item.get("prove_trace")]),
            "explicit_relationship_count": explicit_relationship_count,
            "trace_policy": {
                "server_derived": True, "explicit_links_only": True,
                "missing_links_are_information_gaps": True,
                "automatic_completion": False, "automatic_validation": False,
                "automatic_disclosure": False, "automatic_authority": False,
            },
            "interpretation": (
                "PROVE is the cross-cutting Assurance & Results layer, not a separate product. Counts describe qualifying governed "
                "records and explicit persisted relationships available to this view; they are not capability, readiness, performance, "
                "or personnel scores. Missing trace does not prove that work or evidence does not exist."
            ),
        }
        if not is_member:
            prove_traceability["assurance_gaps_identified"] = sum(
                len(assurance["assurance_gaps"]) for _, assurance in assurance_pairs
            )
        return {
            "name": "Mission Map", "assessment_id": assessment_id, "routes": list(ROUTES),
            "items": visible, "links": links,
            "active_filters": active_filters,
            "prove_traceability": prove_traceability,
            "portfolio": {
                "total_items": len(visible), "by_route": by_route,
                "by_status": by_status, "by_evidence_state": by_evidence,
                "by_attention": by_attention, "by_age_band": by_age,
                "interpretation": (
                    "These are counts of governed records in this authorized view, not scores or judgments about people. "
                    "Age shows time since the latest recorded update and does not by itself establish urgency, risk, or fault."
                ),
            },
            "fallback": {
                "available": True,
                "description": "The same governed items remain available as a conventional list when the visual map is not useful or unavailable.",
            },
            "report": {
                "title": "Mission Map — Authorized Work Summary",
                "release_version": str(getattr(request.app.state, "salcapa_release_version", "")),
                "prepared_at": reference.astimezone(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z"),
                "prepared_at_display": _report_time(reference),
                "audience": "Protected Member authorized view" if is_member else "Salus internal authorized view",
                "scope": (
                    f"Authorized records for assessment {assessment_id}"
                    if assessment_id is not None else "All records authorized for this current view"
                ),
                "status": "Prepared view of governed records — not a separate approval or release",
                "included_item_count": len(visible),
                "active_filters": active_filters,
                "authorization_basis": (
                    "Only released records within the Protected Member's authorized scope, role, and sensitivity boundary are included."
                    if is_member else
                    "Only records allowed by the current tenant, role, assessment, sensitivity, and disclosure controls are included."
                ),
                "governance": (
                    "This printable view reflects authorized records at the preparation time. It does not approve, release, validate, "
                    "assign, prioritize, or change work. Authoritative source records, human judgment, and recorded authority control."
                ),
                "correction_and_lifecycle": (
                    "Later corrections, reviews, releases, superseding records, or lifecycle changes may make this prepared view outdated. "
                    "Return to SalCAPA for the current governed record."
                ),
            },
            "interpretation": "Mission Map shows where governed work is, why it exists, what is expected next, and how evidence and results feed reassessment. Visual position does not create authority or prove completion.",
        }

    @app.post("/api/salcapa/mission-map/nodes")
    def create_mission_node(payload: MissionNodeCreate, request: Request):
        salus_write(request)
        if payload.sensitivity not in sensitivity_levels:
            raise HTTPException(422, "Sensitivity is not recognized by the governed classification model")
        require_sensitivity(request, payload.sensitivity)
        assessment_allowed(request, payload.assessment_id)
        if payload.node_type in {"Mission", "Priority", "Objective", "Strategy", "Tactic"} and payload.functional_area != "Mission Structure":
            raise HTTPException(422, "Mission, priority, objective, strategy, and tactic belong to the Mission Structure route")
        if payload.node_type == "Evidence & Result" and payload.functional_area != "PROVE":
            raise HTTPException(422, "Evidence & Result items belong to the cross-cutting PROVE route")
        conn = db()
        validate_parent(conn, request, payload)
        node_id = _new_id("mmn")
        created = now()
        conn.execute(
            """INSERT INTO salcapa_mission_nodes(
              id,tenant_id,assessment_id,node_type,title,purpose,parent_id,functional_area,status,
              owner,authority,internal_next_step,internal_waiting_on,member_summary,member_next_step,
              member_waiting_on,member_owner,evidence_state,result_summary,sensitivity,visibility,
              created_by,created_at,updated_at
            ) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (node_id, tenant_id(request), payload.assessment_id, payload.node_type, payload.title.strip(),
             payload.purpose.strip(), payload.parent_id, payload.functional_area, "Draft", payload.owner.strip(),
             payload.authority.strip(), payload.internal_next_step.strip(), payload.internal_waiting_on.strip(),
             payload.member_summary.strip(), payload.member_next_step.strip(), payload.member_waiting_on.strip(),
             payload.member_owner.strip(), payload.evidence_state, "", payload.sensitivity, "Salus Only",
             actor(request), created, created),
        )
        event(conn, request, node_id, "Created", "Mission Structure item created", to_state="Draft")
        audit(conn, "CREATE", "mission_map", None, f"Mission Map item {node_id} created as {payload.node_type}", actor(request))
        conn.commit()
        node = dict(conn.execute("SELECT * FROM salcapa_mission_nodes WHERE id=?", (node_id,)).fetchone())
        out = safe_projection(request, node)
        out["mission_path"] = parent_path(conn, request, node)
        conn.close()
        return out

    @app.post("/api/salcapa/mission-map/nodes/{node_id}/transition")
    def transition_mission_node(node_id: str, payload: MissionTransition, request: Request):
        salus_write(request)
        conn = db()
        node = node_for_request(conn, request, node_id)
        current, target = node["status"], payload.status
        if current == target:
            conn.close()
            raise HTTPException(409, "Mission Structure item is already in that state")
        allowed = target in TRANSITIONS[current]
        documented_override = role(request) in {"Assessment Director", "System Administrator"} and len(payload.reason.strip()) >= 3
        if not allowed and not documented_override:
            conn.close()
            raise HTTPException(409, "Mission Structure transition is not available from the current state")
        if target in {"Authorized", "Validated", "Closed"}:
            decision_authority(request)
        updates = {
            "status": target, "updated_at": now(),
            "internal_next_step": payload.internal_next_step if payload.internal_next_step is not None else node["internal_next_step"],
            "internal_waiting_on": payload.internal_waiting_on if payload.internal_waiting_on is not None else node["internal_waiting_on"],
            "member_next_step": payload.member_next_step if payload.member_next_step is not None else node["member_next_step"],
            "member_waiting_on": payload.member_waiting_on if payload.member_waiting_on is not None else node["member_waiting_on"],
        }
        conn.execute(
            "UPDATE salcapa_mission_nodes SET status=?,updated_at=?,internal_next_step=?,internal_waiting_on=?,member_next_step=?,member_waiting_on=? WHERE id=? AND tenant_id=?",
            (updates["status"], updates["updated_at"], updates["internal_next_step"], updates["internal_waiting_on"],
             updates["member_next_step"], updates["member_waiting_on"], node_id, tenant_id(request)),
        )
        member_visible = node["visibility"] == "Released"
        event(conn, request, node_id, "Transition", payload.reason.strip(), current, target, member_visible)
        audit(conn, "TRANSITION", "mission_map", None, f"Mission Map item {node_id}: {current} -> {target}. {payload.reason.strip()}", actor(request))
        conn.commit()
        updated = dict(conn.execute("SELECT * FROM salcapa_mission_nodes WHERE id=?", (node_id,)).fetchone())
        out = safe_projection(request, updated)
        out["mission_path"] = parent_path(conn, request, updated)
        conn.close()
        return out

    @app.post("/api/salcapa/mission-map/nodes/{node_id}/evidence-state")
    def update_evidence_state(node_id: str, payload: EvidenceStateUpdate, request: Request):
        salus_write(request)
        if payload.evidence_state == "Demonstrated":
            decision_authority(request)
            if not payload.result_summary.strip():
                raise HTTPException(422, "Demonstrated evidence state requires a result summary")
        conn = db()
        node = node_for_request(conn, request, node_id)
        old = node["evidence_state"]
        conn.execute(
            "UPDATE salcapa_mission_nodes SET evidence_state=?,result_summary=?,updated_at=? WHERE id=? AND tenant_id=?",
            (payload.evidence_state, payload.result_summary.strip(), now(), node_id, tenant_id(request)),
        )
        event(conn, request, node_id, "Evidence State", payload.reason.strip(), old, payload.evidence_state,
              node["visibility"] == "Released")
        audit(conn, "EVIDENCE_STATE", "mission_map", None,
              f"Mission Map item {node_id}: {old} -> {payload.evidence_state}. {payload.reason.strip()}", actor(request))
        conn.commit()
        updated = dict(conn.execute("SELECT * FROM salcapa_mission_nodes WHERE id=?", (node_id,)).fetchone())
        out = safe_projection(request, updated)
        out["mission_path"] = parent_path(conn, request, updated)
        conn.close()
        return out

    @app.post("/api/salcapa/mission-map/nodes/{node_id}/release")
    def release_mission_node(node_id: str, payload: MemberRelease, request: Request):
        decision_authority(request)
        conn = db()
        node = node_for_request(conn, request, node_id)
        if node["visibility"] == "Released":
            conn.close()
            raise HTTPException(409, "Mission Structure item is already released to the Protected Member view")
        if not node["member_summary"].strip() or not node["member_next_step"].strip():
            conn.close()
            raise HTTPException(409, "Member release requires a member summary and member next-step explanation")
        released_at = now()
        conn.execute(
            "UPDATE salcapa_mission_nodes SET visibility='Released',released_by=?,released_at=?,updated_at=? WHERE id=? AND tenant_id=?",
            (actor(request), released_at, released_at, node_id, tenant_id(request)),
        )
        event(conn, request, node_id, "Member Release", payload.reason.strip(), node["visibility"], "Released", True)
        audit(conn, "RELEASE", "mission_map", None, f"Mission Map item {node_id} released. {payload.reason.strip()}", actor(request))
        conn.commit()
        updated = dict(conn.execute("SELECT * FROM salcapa_mission_nodes WHERE id=?", (node_id,)).fetchone())
        out = safe_projection(request, updated)
        out["mission_path"] = parent_path(conn, request, updated)
        conn.close()
        return out

    @app.post("/api/salcapa/mission-map/links")
    def create_mission_link(payload: MissionLinkCreate, request: Request):
        salus_write(request)
        if payload.source_node_id == payload.target_node_id:
            raise HTTPException(409, "Mission Map relationship cannot point an item to itself")
        conn = db()
        source = node_for_request(conn, request, payload.source_node_id)
        target = node_for_request(conn, request, payload.target_node_id)
        if source["assessment_id"] != target["assessment_id"]:
            conn.close()
            raise HTTPException(409, "Mission Map relationship cannot cross governed assessment scope")
        existing = conn.execute(
            "SELECT id FROM salcapa_mission_links WHERE tenant_id=? AND source_node_id=? AND target_node_id=? AND relationship=?",
            (tenant_id(request), source["id"], target["id"], payload.relationship),
        ).fetchone()
        if existing:
            conn.close()
            raise HTTPException(409, "Equivalent Mission Map relationship already exists")
        link_id = _new_id("mml")
        conn.execute(
            "INSERT INTO salcapa_mission_links(id,tenant_id,assessment_id,source_node_id,target_node_id,relationship,basis,created_by,created_at) VALUES(?,?,?,?,?,?,?,?,?)",
            (link_id, tenant_id(request), source["assessment_id"], source["id"], target["id"],
             payload.relationship, payload.basis.strip(), actor(request), now()),
        )
        audit(conn, "LINK", "mission_map", None,
              f"Mission Map {payload.relationship}: {source['id']} -> {target['id']}. {payload.basis.strip()}", actor(request))
        conn.commit()
        result = dict(conn.execute("SELECT * FROM salcapa_mission_links WHERE id=?", (link_id,)).fetchone())
        conn.close()
        return result

    @app.get("/api/salcapa/mission-map/nodes/{node_id}/history")
    def mission_node_history(node_id: str, request: Request):
        require(request, "read")
        conn = db()
        node_for_request(conn, request, node_id, member_release_required=protected_member(request))
        history = rows(
            conn,
            "SELECT event_type,from_state,to_state,reason,actor_name,member_visible,created_at FROM salcapa_mission_events WHERE tenant_id=? AND node_id=? ORDER BY created_at,id",
            (tenant_id(request), node_id),
        )
        conn.close()
        if protected_member(request):
            return [
                {"event_type": item["event_type"], "from_state": item["from_state"],
                 "to_state": item["to_state"], "created_at": item["created_at"]}
                for item in history if int(item["member_visible"])
            ]
        return history
