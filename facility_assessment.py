"""Governed SalINTEL Facility Assessment domain extension.

Facility records use the shared SalINTEL investigation, item, material, event,
relationship, disclosure, search, and recovery architecture.  This module adds
only domain-specific defensive structure; it never duplicates source bytes or
authorizes operational action.
"""
from __future__ import annotations

import json
import uuid
from typing import Literal

from fastapi import HTTPException, Request
from pydantic import BaseModel, ConfigDict, Field, field_validator

PLAN_VERSION = "facility-assessment-1.0"
Origin = Literal["Chat Research", "Human Investigator", "Protected Member Input",
                 "Source Extraction", "Analyst Assessment", "Site or Field Work",
                 "Approved Partner Return"]
Epistemic = Literal["Verified Fact", "Reported Information", "Reasonable Inference",
                    "Analyst Judgment", "Hypothesis", "Unresolved Allegation",
                    "Assumption", "Contradiction", "Information Gap", "Unknown"]
FailureMode = Literal["Natural", "Accidental", "Intentional / Adversarial"]
GeometryType = Literal["Point", "Path", "Area"]
GeospatialCategory = Literal[
    "Facility Location", "Authorized Assessment Boundary", "Access or Egress",
    "Critical Dependency", "Neighboring Hazard", "Emergency Resource",
    "Alternate Site", "Public-Safety Resource", "Transportation or Logistics",
    "Other Operating Context"
]
IntentionalScenario = Literal[
    "Sabotage", "Active-Assailant", "Insider-Enabled Disruption",
    "Coordinated Cyber-Physical Incident", "Deliberate Fire or Destructive Act",
    "Theft or Diversion", "Supply-Chain Interference", "Workplace Violence",
    "Attack Timed with Emergency", "Exploitation of Degraded Conditions"
]
INTENTIONAL_SCENARIO_TYPES = [
    "Sabotage", "Active-Assailant", "Insider-Enabled Disruption",
    "Coordinated Cyber-Physical Incident", "Deliberate Fire or Destructive Act",
    "Theft or Diversion", "Supply-Chain Interference", "Workplace Violence",
    "Attack Timed with Emergency", "Exploitation of Degraded Conditions",
]
Category = Literal[
    "Facility Identity and Operating Context", "Mission and Essential Functions",
    "Dependencies and Interdependencies", "Natural and Accidental Conditions",
    "Intentional and Adversarial Conditions", "Preventive, Detective and Protective Controls",
    "Alternate Capability and Restoration", "Operational and Emergency Capabilities",
    "Neighborhood and Contextual Hazards", "Insider-Threat Relevance",
    "Emergency-Exploitation Scenarios", "Precursors and Detection Intelligence",
    "Competing and Shared Resources", "Known Unknowns and Reassessment"
]

CHECKLIST = [
    ("FA1-IDENTITY", 1, "Facility Identity and Operating Context",
     "Resolve the facility, site, jurisdiction, operating purpose, geographic context and authorized assessment bounds."),
    ("FA1-MISSION", 1, "Mission and Essential Functions",
     "Identify the mission and essential functions whose disruption would matter to the Protected Member."),
    ("FA1-DEPENDENCIES", 1, "Dependencies and Interdependencies",
     "Identify readily available physical, cyber-physical, utility, workforce, vendor, transportation and information dependencies."),
    ("FA1-CONDITIONS", 1, "Natural and Accidental Conditions",
     "Screen material natural and accidental failure conditions using authorized current sources."),
    ("FA1-ADVERSARIAL", 1, "Intentional and Adversarial Conditions",
     "Perform a defensive baseline screen for sabotage, active-assailant, insider-enabled, cyber-physical, destructive-act, theft/diversion, supply-chain and workplace-violence exposure."),
    ("FA1-CONTROLS", 1, "Preventive, Detective and Protective Controls",
     "Record known preventive, detective and protective controls without assuming effectiveness."),
    ("FA1-ALTERNATES", 1, "Alternate Capability and Restoration",
     "Identify obvious alternate capability, continuity constraints and restoration requirements."),
    ("FA1-CAPABILITY", 1, "Operational and Emergency Capabilities",
     "Record readily available internal and external emergency capabilities and material limitations."),
    ("FA1-CONTEXT", 1, "Neighborhood and Contextual Hazards",
     "Screen access, egress, crime/public-safety, neighboring industrial, aviation, transportation, construction and public-event context."),
    ("FA1-PRECURSORS", 1, "Precursors and Detection Intelligence",
     "Record relevant warning indicators, anomalies and detection questions with source date and uncertainty."),
    ("FA1-UNKNOWNS", 1, "Known Unknowns and Reassessment",
     "Govern unavailable sources, unresolved questions, blind-spot exposure, collection requirements and Tier 1 stopping points."),
    ("FA2-FUNCTIONS", 2, "Mission and Essential Functions",
     "Expand essential-function criticality, dependencies, consequences and time-sensitive restoration analysis."),
    ("FA2-CHAINS", 2, "Dependencies and Interdependencies",
     "Build targeted defensive function-to-restoration chains for material natural, accidental and intentional failure modes."),
    ("FA2-INSIDER", 2, "Insider-Threat Relevance",
     "Assess legitimate-access abuse, privileged roles, vendors, temporary labor, separation of duties, change authorization, credential lifecycle and access removal."),
    ("FA2-EXPLOIT", 2, "Emergency-Exploitation Scenarios",
     "Assess defensive compound scenarios involving malicious activity during outages, evacuation, fire, flooding, severe weather, saturated public safety, communications loss or misinformation."),
    ("FA2-RESOURCES", 2, "Competing and Shared Resources",
     "Assess shared vendors, utilities, responders, contractors, specialists, logistics, communications, alternate sites and other concurrency constraints."),
    ("FA2-CONTROLS", 2, "Preventive, Detective and Protective Controls",
     "Evaluate source-supported control design, coverage, detection and material control gaps without treating untested controls as effective."),
    ("FA2-NEIGHBORHOOD", 2, "Neighborhood and Contextual Hazards",
     "Conduct targeted operating-environment and public-safety resource saturation research."),
    ("FA2-REASSESS", 2, "Known Unknowns and Reassessment",
     "Record residual unknowns, contradiction-resolution attempts, triggers and questions beyond Tier 2."),
    ("FA3-COMPREHENSIVE", 3, "Dependencies and Interdependencies",
     "Complete the fullest authorized cross-domain dependency and interdependency analysis."),
    ("FA3-DEFENSIVE", 3, "Intentional and Adversarial Conditions",
     "Complete comprehensive defensive adversarial, insider, cyber-physical, supply-chain and emergency-exploitation analysis."),
    ("FA3-RESILIENCE", 3, "Alternate Capability and Restoration",
     "Develop detailed alternate-capability, scarcity, surge, restoration-sequence and competing-resource analysis."),
    ("FA3-DETECTION", 3, "Precursors and Detection Intelligence",
     "Reconcile warning indicators, weak signals, anomalies, source conflicts and detection dependencies."),
    ("FA3-RESIDUAL", 3, "Known Unknowns and Reassessment",
     "State residual unknowns, unavailable sources, limitations, reassessment triggers and lawful follow-on options."),
]


class GeneratePlan(BaseModel):
    model_config = ConfigDict(extra="forbid")
    reason: str = Field(min_length=1, max_length=4000)


class FacilityContext(BaseModel):
    model_config = ConfigDict(extra="forbid")
    facility_name: str = Field(min_length=1, max_length=240)
    facility_reference: str = Field(min_length=1, max_length=240)
    location_context: str = Field(min_length=1, max_length=4000)
    mission_summary: str = Field(min_length=1, max_length=8000)
    jurisdiction: str = Field(default="", max_length=240)
    geographic_bounds: str = Field(default="", max_length=2000)
    source_material_id: int | None = Field(default=None, gt=0)


class GeospatialFeature(BaseModel):
    model_config = ConfigDict(extra="forbid")
    title: str = Field(min_length=1, max_length=240)
    category: GeospatialCategory
    geometry_type: GeometryType
    coordinates: list[list[float]] = Field(min_length=1, max_length=200)
    description: str = Field(min_length=1, max_length=8000)
    jurisdiction: str = Field(default="", max_length=240)
    location_date: str = Field(min_length=1, max_length=80)
    spatial_precision: Literal["Exact", "Approximate", "Generalized"]
    origin_type: Origin
    epistemic_state: Epistemic
    source_reliability: str = Field(default="Not Assessed", max_length=80)
    information_confidence: str = Field(default="Not Assessed", max_length=80)
    source_material_id: int = Field(gt=0)

    @field_validator("coordinates")
    @classmethod
    def validate_coordinates(cls, value: list[list[float]]) -> list[list[float]]:
        for coordinate in value:
            if len(coordinate) != 2:
                raise ValueError("Each coordinate must contain longitude and latitude.")
            longitude, latitude = coordinate
            if not -180 <= longitude <= 180 or not -90 <= latitude <= 90:
                raise ValueError("Coordinates must be valid WGS84 longitude and latitude.")
        return value


class EssentialFunction(BaseModel):
    model_config = ConfigDict(extra="forbid")
    title: str = Field(min_length=1, max_length=240)
    mission_statement: str = Field(min_length=1, max_length=8000)
    criticality_basis: str = Field(min_length=1, max_length=4000)
    maximum_tolerable_disruption: str = Field(default="", max_length=1000)
    origin_type: Origin
    epistemic_state: Epistemic
    source_material_id: int | None = Field(default=None, gt=0)


class DependencyAnalysis(BaseModel):
    model_config = ConfigDict(extra="forbid")
    analysis_mode: Literal["Defensive"]
    dependency: str = Field(min_length=1, max_length=4000)
    failure_mode_type: FailureMode
    failure_mode: str = Field(min_length=1, max_length=8000)
    preventive_controls: str = Field(min_length=1, max_length=8000)
    detection: str = Field(min_length=1, max_length=8000)
    consequences: str = Field(min_length=1, max_length=8000)
    alternate_capability: str = Field(min_length=1, max_length=8000)
    restoration_requirement: str = Field(min_length=1, max_length=8000)
    origin_type: Origin
    epistemic_state: Epistemic
    source_reliability: str = Field(default="Not Assessed", max_length=80)
    information_confidence: str = Field(default="Not Assessed", max_length=80)
    source_material_id: int | None = Field(default=None, gt=0)
    insider_threat_relevance: bool = False
    emergency_exploitation_relevance: bool = False
    competing_resource_relevance: bool = False
    intentional_scenario_types: list[IntentionalScenario] = Field(
        default_factory=list, max_length=10
    )


class FacilityFinding(BaseModel):
    model_config = ConfigDict(extra="forbid")
    checklist_key: str = Field(min_length=1, max_length=80)
    category: Category
    title: str = Field(min_length=1, max_length=240)
    narrative: str = Field(min_length=1, max_length=12000)
    epistemic_state: Epistemic
    origin_type: Origin
    source_reliability: str = Field(default="Not Assessed", max_length=80)
    information_confidence: str = Field(default="Not Assessed", max_length=80)
    source_material_id: int | None = Field(default=None, gt=0)
    defensive_implication: str = Field(default="", max_length=8000)
    reassessment_trigger: str = Field(default="", max_length=4000)

    @field_validator("title", "narrative")
    @classmethod
    def clean_required(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("A non-empty value is required.")
        return value


def register_facility_assessment(app, core: dict) -> None:
    db, now = core["db"], core["now"]
    actor, role, tenant_id = core["actor"], core["role"], core["tenant_id"]
    require = core["require"]
    authority = core["require_salus_component_authority"]
    require_sensitivity = core["require_sensitivity"]
    security_event = core["security_event"]

    def canonical(value):
        return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)

    def authorize(request: Request, action: str):
        require(request, "read")
        authority(request, f"SalINTEL Facility Assessment {action}")

    def scoped(conn, investigation_id: int, request: Request):
        row = conn.execute(
            "SELECT * FROM salintel_investigations WHERE id=?", (investigation_id,)
        ).fetchone()
        if not row:
            raise HTTPException(404, "Facility Assessment investigation not found")
        if int(row["tenant_id"]) != tenant_id(request):
            security_event(request, "FACILITY_ASSESSMENT_TENANT_BOUNDARY_VIOLATION",
                           "High", f"investigation_id={investigation_id}")
            raise HTTPException(403, "Tenant boundary violation")
        if row["domain_key"] != "facility-assessment":
            raise HTTPException(422, "Investigation is not a Facility Assessment")
        require_sensitivity(request, row["sensitivity"])
        return row

    def linked_source(conn, investigation_id: int, request: Request, material_id: int):
        source = conn.execute(
            "SELECT m.sensitivity FROM material_links l JOIN materials m ON m.id=l.material_id "
            "WHERE l.tenant_id=? AND l.material_id=? AND l.target_type='salintel_investigation' "
            "AND l.target_id=?",
            (tenant_id(request), material_id, investigation_id),
        ).fetchone()
        if not source:
            raise HTTPException(409, "Source must complete governed material review and linking")
        require_sensitivity(request, source["sensitivity"])

    def parse_detail(item):
        try:
            value = json.loads(item["detail"])
            return value if isinstance(value, dict) else {}
        except (TypeError, ValueError, json.JSONDecodeError):
            return {}

    def items(conn, investigation_id: int):
        result = []
        for item in conn.execute(
            "SELECT * FROM salintel_investigation_items WHERE investigation_id=? ORDER BY id",
            (investigation_id,),
        ):
            value = dict(item)
            value["structured_detail"] = parse_detail(value)
            result.append(value)
        return result

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

    def audit(conn, request: Request, action: str, investigation_id: int, detail: str):
        conn.execute(
            "INSERT INTO audit_log(ts,user_name,action,entity_type,entity_id,detail,tenant_id) "
            "VALUES(?,?,?,?,?,?,?)",
            (now(), actor(request), action, "facility_assessment", investigation_id,
             detail[:2000], tenant_id(request)),
        )

    def create_item(conn, request: Request, row, kind: str, epistemic: str,
                    title: str, detail: dict, reliability: str = "Not Assessed",
                    confidence: str = "Not Assessed", source_material_id=None):
        ts = now()
        cur = conn.execute(
            "INSERT INTO salintel_investigation_items(tenant_id,investigation_id,item_key,"
            "item_kind,epistemic_state,title,detail,source_reliability,"
            "information_confidence,source_material_id,member_visible,created_by,"
            "created_at,updated_at) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (row["tenant_id"], row["id"], "FAI-" + uuid.uuid4().hex, kind,
             epistemic, title.strip(), canonical(detail), reliability.strip() or "Not Assessed",
             confidence.strip() or "Not Assessed", source_material_id, 0,
             actor(request), ts, ts),
        )
        return int(cur.lastrowid)

    def mark_changed(conn, request: Request, investigation_id: int):
        conn.execute(
            "UPDATE salintel_investigations SET status='In Progress',"
            "qualification_status='Unqualified',updated_by=?,updated_at=? WHERE id=?",
            (actor(request), now(), investigation_id),
        )

    def completion_readiness(conn, row):
        """Return deterministic, domain-specific bounded-tier closure readiness."""
        tier = int(row["authorized_tier"])
        records = items(conn, int(row["id"]))
        expected = [entry for entry in CHECKLIST if entry[1] <= tier]
        expected_keys = {entry[0] for entry in expected}
        planned_keys = {
            item["structured_detail"].get("checklist_key")
            for item in records
            if item["structured_detail"].get("record_type") == "facility_checklist"
            and item["structured_detail"].get("plan_version") == PLAN_VERSION
        }
        findings = [
            item for item in records
            if item["structured_detail"].get("record_type") == "facility_finding"
        ]
        addressed_keys = {
            item["structured_detail"].get("checklist_key") for item in findings
        }
        contexts = [
            item for item in records
            if item["structured_detail"].get("record_type") == "facility_context"
        ]
        geospatial_features = [
            item for item in records
            if item["structured_detail"].get("record_type") == "facility_geospatial_feature"
        ]
        functions = [
            item for item in records
            if item["structured_detail"].get("record_type") == "facility_essential_function"
        ]
        chains = [
            item for item in records
            if item["structured_detail"].get("record_type") == "facility_dependency_analysis"
        ]
        blockers = []
        if tier not in (1, 2, 3):
            blockers.append("Authorize a bounded investigation tier.")
        missing_plan = expected_keys - planned_keys
        if missing_plan:
            blockers.append(
                f"Generate the complete {PLAN_VERSION} research plan "
                f"({len(missing_plan)} requirements missing)."
            )
        open_keys = expected_keys - addressed_keys
        if open_keys:
            blockers.append(
                f"Address every authorized Facility Assessment requirement ({len(open_keys)} open)."
            )
        if not contexts:
            blockers.append("Record a governed facility context version.")
        else:
            latest_context = contexts[-1]["structured_detail"]
            if not str(latest_context.get("location_context", "")).strip():
                blockers.append("Record the facility location and operating context.")
            if not str(latest_context.get("geographic_bounds", "")).strip():
                blockers.append("Record the authorized geographic assessment bounds.")
        location_points = [
            item for item in geospatial_features
            if item["structured_detail"].get("category") == "Facility Location"
            and item["structured_detail"].get("geometry_type") == "Point"
        ]
        assessment_areas = [
            item for item in geospatial_features
            if item["structured_detail"].get("category") == "Authorized Assessment Boundary"
            and item["structured_detail"].get("geometry_type") == "Area"
        ]
        if not location_points:
            blockers.append("Map at least one governed facility-location point.")
        if not assessment_areas:
            blockers.append("Map the governed authorized-assessment boundary as an area.")
        if not functions:
            blockers.append("Record at least one governed essential function.")
        chain_types_by_function = {}
        covered_intentional = set()
        insider_reviewed = emergency_reviewed = resource_reviewed = False
        for chain in chains:
            detail = chain["structured_detail"]
            function_id = int(detail.get("essential_function_item_id", 0))
            chain_types_by_function.setdefault(function_id, set()).add(
                detail.get("failure_mode_type")
            )
            covered_intentional.update(detail.get("intentional_scenario_types", []))
            insider_reviewed = insider_reviewed or bool(
                detail.get("insider_threat_relevance")
            )
            emergency_reviewed = emergency_reviewed or bool(
                detail.get("emergency_exploitation_relevance")
            )
            resource_reviewed = resource_reviewed or bool(
                detail.get("competing_resource_relevance")
            )
        required_modes = {"Natural", "Accidental", "Intentional / Adversarial"}
        incomplete_functions = [
            int(function["id"]) for function in functions
            if not required_modes.issubset(
                chain_types_by_function.get(int(function["id"]), set())
            )
        ]
        if incomplete_functions:
            blockers.append(
                "Complete natural, accidental, and intentional/adversarial defensive "
                f"chains for every essential function ({len(incomplete_functions)} incomplete)."
            )
        missing_intentional = set(INTENTIONAL_SCENARIO_TYPES) - covered_intentional
        if missing_intentional:
            blockers.append(
                "Complete the formal defensive intentional-threat coverage "
                f"({len(missing_intentional)} scenario types not addressed)."
            )
        if not insider_reviewed:
            blockers.append("Complete and mark the dedicated insider-threat review.")
        if not emergency_reviewed:
            blockers.append("Complete and mark emergency-exploitation analysis.")
        if not resource_reviewed:
            blockers.append("Complete and mark competing/shared-resource analysis.")
        if "FA1-UNKNOWNS" not in addressed_keys:
            blockers.append(
                "Record residual known unknowns, collection requirements, and reassessment triggers."
            )

        research_plans = [
            item for item in records
            if item["structured_detail"].get("record_type") == "salintel_research_plan"
            and int(item["structured_detail"].get("authorized_tier", 0)) == tier
        ]
        research_plan = research_plans[-1] if research_plans else None
        research_task_count = research_tasks_dispositioned = 0
        chat_sources_accessed = qualified_research_product_count = 0
        if not research_plan:
            blockers.append(
                "Authorize and complete the shared Chat-led mixed-source research plan for this tier."
            )
        else:
            plan_id = int(research_plan["id"])
            tasks = research_plan["structured_detail"].get("tasks", [])
            research_task_count = len(tasks)
            task_keys = {str(task.get("task_key", "")) for task in tasks}
            results = [
                item for item in records
                if item["structured_detail"].get("record_type") == "salintel_source_result"
                and int(item["structured_detail"].get("plan_id", 0)) == plan_id
            ]
            dispositioned = {
                str(item["structured_detail"].get("task_key", "")) for item in results
            }
            research_tasks_dispositioned = len(task_keys & dispositioned)
            missing_research = task_keys - dispositioned
            if not tasks or missing_research:
                blockers.append(
                    "Truthfully disposition every authorized mixed-source research task "
                    f"({len(missing_research) if tasks else 1} open)."
                )
            chat_sources_accessed = sum(
                1 for item in results
                if item["structured_detail"].get("authorized_contributor") == "Chat Research"
                and item["structured_detail"].get("outcome") == "Accessed"
                and item["source_material_id"] not in (None, "")
                and str(item["structured_detail"].get("source_locator", "")).strip()
            )
            if not chat_sources_accessed:
                blockers.append(
                    "Complete real Chat research against at least one accessed, cited, governed source."
                )
            products = [
                item for item in records
                if item["structured_detail"].get("record_type") == "salintel_research_product"
                and int(item["structured_detail"].get("plan_id", 0)) == plan_id
                and int(item["structured_detail"].get("authorized_tier", 0)) == tier
            ]
            latest_product = products[-1] if products else None
            latest_result_at = max(
                (str(item["updated_at"]) for item in results), default=""
            )
            qualified = bool(
                latest_product
                and latest_product["structured_detail"].get("review_status") == "Qualified"
                and str(latest_product["structured_detail"].get("reviewed_by", "")).strip()
                and str(latest_product["structured_detail"].get("reviewed_at", "")).strip()
                and str(latest_product["created_at"]) >= latest_result_at
            )
            qualified_research_product_count = 1 if qualified else 0
            if not qualified:
                blockers.append(
                    "Obtain Salus human qualification of the current tier-specific Chat "
                    "research product after the latest source result."
                )
        if row["qualification_status"] != "Qualified":
            blockers.append(
                "Obtain final human qualification after the latest facility record or finding."
            )
        if row["status"] in ("Tier Complete", "Closed"):
            blockers.append("Completed work cannot be silently reopened or recompleted.")
        return {
            "ready": not blockers,
            "blockers": blockers,
            "expected_requirement_count": len(expected_keys),
            "addressed_requirement_count": len(expected_keys & addressed_keys),
            "essential_function_count": len(functions),
            "dependency_chain_count": len(chains),
            "geospatial_feature_count": len(geospatial_features),
            "facility_location_point_count": len(location_points),
            "assessment_boundary_area_count": len(assessment_areas),
            "incomplete_function_ids": incomplete_functions,
            "intentional_scenario_types_required": INTENTIONAL_SCENARIO_TYPES,
            "intentional_scenario_types_covered": sorted(covered_intentional),
            "research_plan_id": int(research_plan["id"]) if research_plan else None,
            "research_task_count": research_task_count,
            "research_tasks_dispositioned": research_tasks_dispositioned,
            "chat_sources_accessed": chat_sources_accessed,
            "qualified_research_product_count": qualified_research_product_count,
        }

    @app.middleware("http")
    async def facility_completion_gate(request: Request, call_next):
        """Prevent the generic tier endpoint from bypassing Facility closure rules."""
        prefix = "/api/salintel/investigations/"
        suffix = "/complete-tier"
        path = request.url.path
        if request.method != "POST" or not path.startswith(prefix) or not path.endswith(suffix):
            return await call_next(request)
        record_part = path[len(prefix):-len(suffix)]
        if not record_part.isdigit():
            return await call_next(request)
        conn = db()
        try:
            row = conn.execute(
                "SELECT * FROM salintel_investigations WHERE id=?", (int(record_part),)
            ).fetchone()
            if (not row or row["domain_key"] != "facility-assessment"
                    or int(row["tenant_id"]) != tenant_id(request)):
                row = None
            readiness = completion_readiness(conn, row) if row else None
        finally:
            conn.close()
        if row is None:
            return await call_next(request)
        try:
            require(request, "decide")
            authority(request, "SalINTEL Facility Assessment tier completion")
        except HTTPException:
            return await call_next(request)
        if not readiness["ready"]:
            from fastapi.responses import JSONResponse
            return JSONResponse(
                status_code=409,
                content={
                    "detail": "Facility Assessment is not ready for bounded-tier completion.",
                    "blockers": readiness["blockers"],
                },
            )
        return await call_next(request)

    def validate_epistemic(payload, source_material_id):
        if payload.epistemic_state == "Verified Fact":
            if payload.origin_type != "Analyst Assessment" or not source_material_id:
                raise HTTPException(
                    409, "Verified Fact requires Salus analyst assessment and linked source material"
                )

    @app.get("/api/salintel/facility-assessment/checklist")
    def checklist(request: Request):
        authorize(request, "checklist review")
        return {"version": PLAN_VERSION, "tiers": [
            {"key": key, "tier_required": tier, "category": category, "question": question}
            for key, tier, category, question in CHECKLIST
        ]}

    @app.post("/api/salintel/facility-assessments/{investigation_id}/research-plan")
    def generate_plan(investigation_id: int, payload: GeneratePlan, request: Request):
        authorize(request, "research planning")
        require(request, "write")
        conn = db()
        try:
            row = scoped(conn, investigation_id, request)
            tier = int(row["authorized_tier"])
            if tier not in (1, 2, 3):
                raise HTTPException(409, "Authorize a bounded investigation tier first")
            if row["status"] in ("Tier Complete", "Closed"):
                raise HTTPException(409, "Completed work cannot be silently reopened")
            existing = [
                item for item in items(conn, investigation_id)
                if item["structured_detail"].get("record_type") == "facility_checklist"
            ]
            if existing:
                raise HTTPException(409, "Facility research plan already exists")
            selected = [entry for entry in CHECKLIST if entry[1] <= tier]
            for key, required_tier, category, question in selected:
                create_item(
                    conn, request, row, "Collection Requirement", "Information Gap",
                    f"{key} — {category}",
                    {"record_type": "facility_checklist", "plan_version": PLAN_VERSION,
                     "checklist_key": key, "tier_required": required_tier,
                     "category": category, "question": question, "status": "Open",
                     "collection_channels": ["Chat Research", "Human Investigator",
                                             "Protected Member Input", "Site or Field Work",
                                             "Source Extraction"]},
                )
            mark_changed(conn, request, investigation_id)
            event(conn, request, row, "FACILITY_RESEARCH_PLAN_CREATED",
                  f"{PLAN_VERSION}; bounded through Tier {tier}; {payload.reason}")
            audit(conn, request, "FACILITY_RESEARCH_PLAN_CREATED", investigation_id,
                  f"version={PLAN_VERSION}; tier={tier}; requirements={len(selected)}")
            conn.commit()
            return {"investigation_id": investigation_id, "plan_version": PLAN_VERSION,
                    "authorized_tier": tier, "requirement_count": len(selected)}
        finally:
            conn.close()

    @app.post("/api/salintel/facility-assessments/{investigation_id}/context")
    def add_context(investigation_id: int, payload: FacilityContext, request: Request):
        authorize(request, "context analysis")
        require(request, "write")
        conn = db()
        try:
            row = scoped(conn, investigation_id, request)
            if int(row["authorized_tier"]) == 0:
                raise HTTPException(409, "Authorize a bounded investigation tier first")
            if payload.source_material_id:
                linked_source(conn, investigation_id, request, payload.source_material_id)
            versions = [
                item for item in items(conn, investigation_id)
                if item["structured_detail"].get("record_type") == "facility_context"
            ]
            detail = payload.model_dump()
            detail.update({"record_type": "facility_context",
                           "plan_version": PLAN_VERSION,
                           "context_version": len(versions) + 1,
                           "human_qualification_required": True})
            item_id = create_item(
                conn, request, row, "Finding", "Reported Information",
                f"Facility context — {payload.facility_name}", detail,
                source_material_id=payload.source_material_id,
            )
            mark_changed(conn, request, investigation_id)
            event(conn, request, row, "FACILITY_CONTEXT_RECORDED",
                  f"item_id={item_id}; context_version={len(versions)+1}")
            audit(conn, request, "FACILITY_CONTEXT_RECORDED", investigation_id,
                  f"item_id={item_id}; version={len(versions)+1}")
            conn.commit()
            return {"id": item_id, "context_version": len(versions) + 1,
                    "qualification_status": "Unqualified"}
        finally:
            conn.close()

    @app.post("/api/salintel/facility-assessments/{investigation_id}/geospatial-features")
    def add_geospatial_feature(investigation_id: int, payload: GeospatialFeature,
                               request: Request):
        authorize(request, "geospatial analysis")
        require(request, "write")
        coordinate_count = len(payload.coordinates)
        if payload.geometry_type == "Point" and coordinate_count != 1:
            raise HTTPException(422, "A point requires exactly one coordinate pair")
        if payload.geometry_type == "Path" and coordinate_count < 2:
            raise HTTPException(422, "A path requires at least two coordinate pairs")
        if payload.geometry_type == "Area":
            if coordinate_count < 4 or payload.coordinates[0] != payload.coordinates[-1]:
                raise HTTPException(
                    422, "An area requires a closed ring of at least four coordinate pairs"
                )
        if (payload.category == "Facility Location"
                and payload.geometry_type != "Point"):
            raise HTTPException(422, "Facility Location must use point geometry")
        if (payload.category == "Authorized Assessment Boundary"
                and payload.geometry_type != "Area"):
            raise HTTPException(422, "Authorized Assessment Boundary must use area geometry")
        conn = db()
        try:
            row = scoped(conn, investigation_id, request)
            if int(row["authorized_tier"]) == 0:
                raise HTTPException(409, "Authorize a bounded investigation tier first")
            linked_source(conn, investigation_id, request, payload.source_material_id)
            validate_epistemic(payload, payload.source_material_id)
            detail = payload.model_dump()
            detail.update({
                "record_type": "facility_geospatial_feature",
                "plan_version": PLAN_VERSION,
                "coordinate_reference_system": "WGS84 / EPSG:4326",
                "coordinate_order": ["longitude", "latitude"],
                "map_rendering": "local_only_no_external_tile_transmission",
                "human_qualification_required": True,
                "member_disclosure_authorized": False,
                "operational_authority_granted": False,
            })
            item_id = create_item(
                conn, request, row, "Finding", payload.epistemic_state,
                f"Geospatial context — {payload.title}", detail,
                payload.source_reliability, payload.information_confidence,
                payload.source_material_id,
            )
            mark_changed(conn, request, investigation_id)
            event(conn, request, row, "FACILITY_GEOSPATIAL_FEATURE_RECORDED",
                  f"item_id={item_id}; category={payload.category}; "
                  f"geometry={payload.geometry_type}; precision={payload.spatial_precision}")
            audit(conn, request, "FACILITY_GEOSPATIAL_FEATURE_RECORDED",
                  investigation_id,
                  f"item_id={item_id}; category={payload.category}; "
                  f"geometry={payload.geometry_type}; coordinate_count={coordinate_count}")
            conn.commit()
            return {
                "id": item_id,
                "geometry_type": payload.geometry_type,
                "coordinate_count": coordinate_count,
                "coordinate_reference_system": "WGS84 / EPSG:4326",
                "qualification_status": "Unqualified",
                "member_disclosure_authorized": False,
                "operational_authority_granted": False,
            }
        finally:
            conn.close()

    @app.post("/api/salintel/facility-assessments/{investigation_id}/essential-functions")
    def add_essential_function(investigation_id: int, payload: EssentialFunction,
                               request: Request):
        authorize(request, "essential function analysis")
        require(request, "write")
        conn = db()
        try:
            row = scoped(conn, investigation_id, request)
            if int(row["authorized_tier"]) == 0:
                raise HTTPException(409, "Authorize a bounded investigation tier first")
            if payload.source_material_id:
                linked_source(conn, investigation_id, request, payload.source_material_id)
            validate_epistemic(payload, payload.source_material_id)
            detail = payload.model_dump()
            detail.update({"record_type": "facility_essential_function",
                           "plan_version": PLAN_VERSION,
                           "defensive_analysis_only": True,
                           "human_qualification_required": True})
            item_id = create_item(
                conn, request, row, "Finding", payload.epistemic_state,
                f"Essential function — {payload.title}", detail,
                source_material_id=payload.source_material_id,
            )
            mark_changed(conn, request, investigation_id)
            event(conn, request, row, "FACILITY_ESSENTIAL_FUNCTION_RECORDED",
                  f"item_id={item_id}; {payload.title}")
            audit(conn, request, "FACILITY_ESSENTIAL_FUNCTION_RECORDED",
                  investigation_id, f"item_id={item_id}")
            conn.commit()
            return {"id": item_id, "qualification_status": "Unqualified"}
        finally:
            conn.close()

    @app.post("/api/salintel/facility-assessments/{investigation_id}/essential-functions/{function_item_id}/dependency-analysis")
    def add_dependency_analysis(investigation_id: int, function_item_id: int,
                                payload: DependencyAnalysis, request: Request):
        authorize(request, "defensive dependency analysis")
        require(request, "write")
        conn = db()
        try:
            row = scoped(conn, investigation_id, request)
            tier = int(row["authorized_tier"])
            if tier == 0:
                raise HTTPException(409, "Authorize a bounded investigation tier first")
            function_item = conn.execute(
                "SELECT * FROM salintel_investigation_items WHERE id=? AND investigation_id=?",
                (function_item_id, investigation_id),
            ).fetchone()
            if not function_item or parse_detail(function_item).get("record_type") != "facility_essential_function":
                raise HTTPException(404, "Essential function not found")
            if payload.source_material_id:
                linked_source(conn, investigation_id, request, payload.source_material_id)
            validate_epistemic(payload, payload.source_material_id)
            if payload.failure_mode_type == "Intentional / Adversarial" and not payload.detection.strip():
                raise HTTPException(422, "Defensive intentional-threat analysis requires detection")
            if (payload.failure_mode_type == "Intentional / Adversarial"
                    and not payload.intentional_scenario_types):
                raise HTTPException(
                    422, "Defensive intentional-threat analysis requires governed scenario coverage"
                )
            if (payload.failure_mode_type != "Intentional / Adversarial"
                    and payload.intentional_scenario_types):
                raise HTTPException(
                    422, "Intentional scenario types require an intentional/adversarial failure mode"
                )
            detail = payload.model_dump()
            detail.update({
                "record_type": "facility_dependency_analysis",
                "plan_version": PLAN_VERSION,
                "essential_function_item_id": function_item_id,
                "chain_order": ["mission_function", "dependency", "failure_mode",
                                "preventive_controls", "detection", "consequences",
                                "alternate_capability", "restoration_requirement"],
                "mission_function": parse_detail(function_item).get("mission_statement", ""),
                "human_qualification_required": True,
                "operational_authority_granted": False,
            })
            item_id = create_item(
                conn, request, row, "Finding", payload.epistemic_state,
                f"Defensive dependency chain — {function_item['title']}", detail,
                payload.source_reliability, payload.information_confidence,
                payload.source_material_id,
            )
            mark_changed(conn, request, investigation_id)
            event(conn, request, row, "FACILITY_DEPENDENCY_CHAIN_RECORDED",
                  f"item_id={item_id}; function_item_id={function_item_id}; "
                  f"failure_mode_type={payload.failure_mode_type}")
            audit(conn, request, "FACILITY_DEPENDENCY_CHAIN_RECORDED",
                  investigation_id, f"item_id={item_id}; function_item_id={function_item_id}")
            conn.commit()
            return {"id": item_id, "essential_function_item_id": function_item_id,
                    "analysis_mode": "Defensive", "qualification_status": "Unqualified",
                    "operational_authority_granted": False}
        finally:
            conn.close()

    @app.post("/api/salintel/facility-assessments/{investigation_id}/findings")
    def add_finding(investigation_id: int, payload: FacilityFinding, request: Request):
        authorize(request, "analysis")
        require(request, "write")
        template = next((entry for entry in CHECKLIST if entry[0] == payload.checklist_key), None)
        if not template or template[2] != payload.category:
            raise HTTPException(422, "Finding must reference a matching governed checklist item")
        conn = db()
        try:
            row = scoped(conn, investigation_id, request)
            tier = int(row["authorized_tier"])
            if tier == 0 or template[1] > tier:
                raise HTTPException(409, "Finding is outside the authorized investigation tier")
            if payload.source_material_id:
                linked_source(conn, investigation_id, request, payload.source_material_id)
            validate_epistemic(payload, payload.source_material_id)
            detail = payload.model_dump()
            detail.update({"record_type": "facility_finding",
                           "plan_version": PLAN_VERSION,
                           "tier_required": template[1],
                           "defensive_analysis_only": True,
                           "human_qualification_required": True,
                           "member_disclosure_authorized": False})
            item_id = create_item(
                conn, request, row,
                "Contradiction" if payload.epistemic_state == "Contradiction" else "Finding",
                payload.epistemic_state, payload.title, detail,
                payload.source_reliability, payload.information_confidence,
                payload.source_material_id,
            )
            mark_changed(conn, request, investigation_id)
            event(conn, request, row, "FACILITY_FINDING_RECORDED",
                  f"item_id={item_id}; key={payload.checklist_key}; "
                  f"epistemic={payload.epistemic_state}")
            audit(conn, request, "FACILITY_FINDING_RECORDED", investigation_id,
                  f"item_id={item_id}; key={payload.checklist_key}")
            conn.commit()
            return {"id": item_id, "epistemic_state": payload.epistemic_state,
                    "qualification_status": "Unqualified",
                    "member_disclosure_authorized": False}
        finally:
            conn.close()

    @app.get("/api/salintel/facility-assessments/{investigation_id}")
    def get_facility_assessment(investigation_id: int, request: Request):
        authorize(request, "record review")
        conn = db()
        try:
            row = scoped(conn, investigation_id, request)
            records = items(conn, investigation_id)
            facility_records = [
                item for item in records
                if str(item["structured_detail"].get("record_type", "")).startswith("facility_")
            ]
            contexts = [item for item in facility_records
                        if item["structured_detail"].get("record_type") == "facility_context"]
            geospatial_features = [
                item for item in facility_records
                if item["structured_detail"].get("record_type") == "facility_geospatial_feature"
            ]
            functions = [item for item in facility_records
                         if item["structured_detail"].get("record_type") == "facility_essential_function"]
            chains = [item for item in facility_records
                      if item["structured_detail"].get("record_type") == "facility_dependency_analysis"]
            findings = [item for item in facility_records
                        if item["structured_detail"].get("record_type") == "facility_finding"]
            plan = [item for item in records
                    if item["structured_detail"].get("record_type") == "facility_checklist"
                    and item["structured_detail"].get("plan_version") == PLAN_VERSION]
            expected = [entry for entry in CHECKLIST
                        if entry[1] <= int(row["authorized_tier"])]
            addressed = {item["structured_detail"].get("checklist_key") for item in findings}
            return {
                "investigation": dict(row),
                "plan_version": PLAN_VERSION,
                "latest_context": contexts[-1] if contexts else None,
                "context_history": contexts,
                "geospatial_features": geospatial_features,
                "geospatial_summary": {
                    "feature_count": len(geospatial_features),
                    "point_count": sum(
                        1 for item in geospatial_features
                        if item["structured_detail"].get("geometry_type") == "Point"
                    ),
                    "path_count": sum(
                        1 for item in geospatial_features
                        if item["structured_detail"].get("geometry_type") == "Path"
                    ),
                    "area_count": sum(
                        1 for item in geospatial_features
                        if item["structured_detail"].get("geometry_type") == "Area"
                    ),
                    "external_map_transmission": False,
                    "coordinate_reference_system": "WGS84 / EPSG:4326",
                },
                "essential_functions": functions,
                "dependency_analyses": chains,
                "findings": findings,
                "progress": {
                    "total": len(expected),
                    "planned": len(plan),
                    "addressed": len({entry[0] for entry in expected} & addressed),
                },
                "governance": {
                    "salus_only": True,
                    "defensive_analysis_only": True,
                    "member_disclosure_requires_explicit_authorization": True,
                    "tier_change_requires_salus_authorization": True,
                    "commercial_change_requires_salus_authorization": True,
                    "operational_authority_granted": False,
                },
                "completion_readiness": completion_readiness(conn, row),
            }
        finally:
            conn.close()
