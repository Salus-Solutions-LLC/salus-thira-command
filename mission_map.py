"""Governed SalCAPA Mission Map and Mission Structure.

Issue #213. Mission Map is a server-derived way-finding projection over governed
records. It shows purpose, current location, ownership, waiting conditions, next
steps, evidence state, and reassessment without allowing the browser to create or
forge workflow position. Protected Member projections expose only explicitly
released member-facing content within the active tenant and sensitivity boundary.
"""
from __future__ import annotations

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


def _attention_state(item: dict[str, Any]) -> str:
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
                "Ownership / next step needed", "No recorded hold",
            ],
            "routes": list(ROUTES), "marker_shapes": MARKER_SHAPES,
            "mission_structure": "Mission → Priorities → Objectives → Strategies → Tactics → Tasks / Assignments → Evidence & Results → Reassessment / Improvement",
            "principle": "People lead. Methods guide. Technology supports. Evidence proves.",
            "filter_guidance": "Filters narrow the records already authorized for your view. They do not change scope, priority, ownership, or workflow state.",
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
            "Ownership / next step needed", "No recorded hold",
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
        return {
            "name": "Mission Map", "assessment_id": assessment_id, "routes": list(ROUTES),
            "items": visible, "links": links,
            "active_filters": {
                "functional_area": functional_area, "workflow_status": workflow_status,
                "attention": attention, "owner": owner.strip() if owner else None,
            },
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
