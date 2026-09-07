"""Governed SalINTEL Personnel Assessment domain extension.

This capability stores its research plan, identity candidates, and structured
findings in the shared SalINTEL investigation/item/event model. Source bytes,
tenant authority, qualification, disclosure, and recovery remain shared.
"""
from __future__ import annotations

import hashlib
import json
import uuid
from typing import Literal

from fastapi import HTTPException, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ConfigDict, Field, field_validator

PLAN_VERSION = "personnel-assessment-1.0"
Origin = Literal["Chat Research", "Human Investigator", "Protected Member Input",
                 "Source Extraction", "Analyst Assessment", "Approved Partner Return"]
Category = Literal["Identity Resolution", "Professional and Employment History",
                   "Credentials and Qualifications", "Business and Vendor Relationships",
                   "Public Record and Open-Source Corroboration", "Contradictions",
                   "Relationship and Network Context", "Competing Resources and Conflicts",
                   "Insider-Threat Relevance", "Protective-Intelligence Relevance",
                   "Known Unknowns and Collection Requirements"]
Epistemic = Literal["Verified Fact", "Reported Information", "Reasonable Inference",
                    "Analyst Judgment", "Hypothesis", "Unresolved Allegation",
                    "Assumption", "Contradiction", "Information Gap", "Unknown"]
CandidateDecision = Literal["Match", "Excluded", "Ambiguous", "Contradiction"]

CHECKLIST = [
    ("PA1-IDENTITY", 1, "Identity Resolution",
     "Resolve the subject identity using authorized identifiers and distinguish same-name candidates.",
     ["Chat Research", "Human Investigator", "Protected Member Input"]),
    ("PA1-CURRENT", 1, "Professional and Employment History",
     "Corroborate relevant current employment, professional role, and organizational association.",
     ["Chat Research", "Protected Member Input", "Source Extraction"]),
    ("PA1-CREDENTIALS", 1, "Credentials and Qualifications",
     "Check claimed credentials, licenses, qualifications, and readily available issuing-source records.",
     ["Chat Research", "Human Investigator", "Source Extraction"]),
    ("PA1-BUSINESS", 1, "Business and Vendor Relationships",
     "Identify readily available business, corporate, vendor, contractor, or service-provider relationships.",
     ["Chat Research", "Source Extraction"]),
    ("PA1-OPEN", 1, "Public Record and Open-Source Corroboration",
     "Collect lawful high-value public-record and open-source corroboration within the approved purpose.",
     ["Chat Research", "Human Investigator"]),
    ("PA1-CONTRADICTIONS", 1, "Contradictions",
     "Record material contradictions, unresolved identity questions, and source conflicts without converting allegations into facts.",
     ["Chat Research", "Human Investigator"]),
    ("PA1-RELATIONSHIPS", 1, "Relationship and Network Context",
     "Map obvious relevant relationships while distinguishing reported association from verified relationship.",
     ["Chat Research", "Protected Member Input"]),
    ("PA1-UNKNOWNS", 1, "Known Unknowns and Collection Requirements",
     "Document unresolved questions, unavailable sources, collection requirements, and bounded Tier 1 stopping points.",
     ["Chat Research", "Human Investigator"]),
    ("PA2-HISTORY", 2, "Professional and Employment History",
     "Conduct separately authorized deeper historical employment and organizational-association review.",
     ["Chat Research", "Human Investigator", "Source Extraction"]),
    ("PA2-DISCREPANCIES", 2, "Contradictions",
     "Target material discrepancies and unresolved claimed-history questions using broader authorized sources.",
     ["Chat Research", "Human Investigator"]),
    ("PA2-CORPORATE", 2, "Business and Vendor Relationships",
     "Expand corporate, vendor, contractor, beneficial-role, and professional relationship research where lawful.",
     ["Chat Research", "Human Investigator", "Approved Partner Return"]),
    ("PA2-NETWORK", 2, "Relationship and Network Context",
     "Evaluate expanded relationship context and competing explanations without inferring guilt by association.",
     ["Chat Research", "Analyst Assessment"]),
    ("PA2-RESOURCES", 2, "Competing Resources and Conflicts",
     "Assess shared roles, divided obligations, availability conflicts, and competing-resource indicators.",
     ["Chat Research", "Human Investigator", "Protected Member Input"]),
    ("PA2-INSIDER", 2, "Insider-Threat Relevance",
     "Assess legitimate-access, privileged-role, credential, contractor, and separation-of-duty relevance defensively.",
     ["Chat Research", "Human Investigator", "Protected Member Input"]),
    ("PA2-PROTECTIVE", 2, "Protective-Intelligence Relevance",
     "Assess relevance to protective intelligence, exposure, reliability, and protective decisions.",
     ["Analyst Assessment", "Human Investigator"]),
    ("PA2-FOLLOWUP", 2, "Known Unknowns and Collection Requirements",
     "Create targeted follow-up requirements and identify questions outside the authorized Tier 2 scope.",
     ["Chat Research", "Human Investigator"]),
    ("PA3-HISTORY", 3, "Professional and Employment History",
     "Conduct the fullest lawful approved historical review within explicit time, jurisdiction, and source bounds.",
     ["Chat Research", "Human Investigator", "Approved Partner Return"]),
    ("PA3-NETWORK", 3, "Relationship and Network Context",
     "Conduct deeper network, timeline, pattern, and cross-domain correlation with alternative-hypothesis testing.",
     ["Chat Research", "Analyst Assessment", "Approved Partner Return"]),
    ("PA3-CORROBORATION", 3, "Public Record and Open-Source Corroboration",
     "Apply the approved comprehensive source set and reconcile source reliability, conflicts, and gaps.",
     ["Chat Research", "Human Investigator", "Source Extraction"]),
    ("PA3-CONFLICT", 3, "Competing Resources and Conflicts",
     "Complete authorized deep competing-resource, divided-obligation, and reliability analysis.",
     ["Chat Research", "Human Investigator", "Analyst Assessment"]),
    ("PA3-IMPLICATIONS", 3, "Protective-Intelligence Relevance",
     "Develop qualified protective implications while separating evidence, inference, judgment, and hypothesis.",
     ["Analyst Assessment"]),
    ("PA3-RESIDUAL", 3, "Known Unknowns and Collection Requirements",
     "State residual unknowns, unavailable sources, blind-spot exposure, reassessment triggers, and lawful follow-on options.",
     ["Chat Research", "Analyst Assessment"]),
]


class GeneratePlan(BaseModel):
    model_config = ConfigDict(extra="forbid")
    reason: str = Field(min_length=1, max_length=4000)


class IdentityCandidate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    candidate_name: str = Field(min_length=1, max_length=240)
    identifiers: dict[str, str] = Field(default_factory=dict)
    origin_type: Origin
    narrative: str = Field(min_length=1, max_length=8000)
    source_material_id: int | None = Field(default=None, gt=0)

    @field_validator("candidate_name", "narrative")
    @classmethod
    def clean_required(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("A non-empty value is required.")
        return value


class DecideCandidate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    decision: CandidateDecision
    reason: str = Field(min_length=1, max_length=4000)


class PersonnelFinding(BaseModel):
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
    relationship_context: str = Field(default="", max_length=4000)
    competing_resource_relevance: bool = False
    insider_threat_relevance: bool = False
    protective_intelligence_relevance: bool = False


def register_personnel_assessment(app, core: dict) -> None:
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
        authority(request, f"SalINTEL Personnel Assessment {action}")

    def scoped(conn, investigation_id: int, request: Request):
        row = conn.execute(
            "SELECT * FROM salintel_investigations WHERE id=?", (investigation_id,)
        ).fetchone()
        if not row:
            raise HTTPException(404, "Personnel Assessment investigation not found")
        if int(row["tenant_id"]) != tenant_id(request):
            security_event(request, "PERSONNEL_ASSESSMENT_TENANT_BOUNDARY_VIOLATION",
                           "High", f"investigation_id={investigation_id}")
            raise HTTPException(403, "Tenant boundary violation")
        if row["domain_key"] != "personnel-assessment":
            raise HTTPException(422, "Investigation is not a Personnel Assessment")
        require_sensitivity(request, row["sensitivity"])
        return row

    def linked_source(conn, investigation_id: int, request: Request, material_id: int):
        row = conn.execute(
            "SELECT m.sensitivity FROM material_links l JOIN materials m ON m.id=l.material_id "
            "WHERE l.tenant_id=? AND l.material_id=? "
            "AND l.target_type='salintel_investigation' AND l.target_id=?",
            (tenant_id(request), material_id, investigation_id),
        ).fetchone()
        if not row:
            raise HTTPException(409, "Source must complete governed material review and linking")
        require_sensitivity(request, row["sensitivity"])

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
            (now(), actor(request), action, "personnel_assessment", investigation_id,
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
            (row["tenant_id"], row["id"], "PAI-" + uuid.uuid4().hex, kind,
             epistemic, title.strip(), canonical(detail), reliability.strip() or "Not Assessed",
             confidence.strip() or "Not Assessed", source_material_id, 0,
             actor(request), ts, ts),
        )
        return int(cur.lastrowid)

    def parse_detail(item):
        try:
            value = json.loads(item["detail"])
            return value if isinstance(value, dict) else {}
        except (TypeError, ValueError, json.JSONDecodeError):
            return {}

    def personnel_items(conn, investigation_id: int):
        result = []
        for row in conn.execute(
            "SELECT * FROM salintel_investigation_items WHERE investigation_id=? ORDER BY id",
            (investigation_id,),
        ):
            item = dict(row)
            item["structured_detail"] = parse_detail(item)
            result.append(item)
        return result

    def completion_readiness(conn, row):
        """Return deterministic, domain-specific bounded-tier closure readiness."""
        tier = int(row["authorized_tier"])
        items = personnel_items(conn, int(row["id"]))
        expected = [entry for entry in CHECKLIST if entry[1] <= tier]
        expected_keys = {entry[0] for entry in expected}
        plan_keys, addressed_keys, candidates = set(), set(), []
        identity_states = set()
        for item in items:
            detail = item["structured_detail"]
            record_type = detail.get("record_type")
            if record_type == "personnel_checklist":
                if detail.get("plan_version") == PLAN_VERSION:
                    plan_keys.add(detail.get("checklist_key"))
            elif record_type == "personnel_finding":
                key = detail.get("checklist_key")
                addressed_keys.add(key)
                if key == "PA1-IDENTITY":
                    identity_states.add(item["epistemic_state"])
            elif record_type == "personnel_identity_candidate":
                candidates.append(item)

        blockers = []
        if tier not in (1, 2, 3):
            blockers.append("Authorize a bounded investigation tier.")
        missing_plan = sorted(expected_keys - plan_keys)
        if missing_plan:
            blockers.append(
                f"Generate the complete {PLAN_VERSION} research plan "
                f"({len(missing_plan)} requirements missing)."
            )
        open_keys = sorted(expected_keys - addressed_keys)
        if open_keys:
            blockers.append(
                f"Address every authorized research requirement ({len(open_keys)} open)."
            )
        matched = [item for item in candidates
                   if item["structured_detail"].get("decision") == "Match"]
        unresolved = [item for item in candidates
                      if item["structured_detail"].get("decision")
                      in (None, "Unresolved", "Ambiguous")]
        if not candidates:
            blockers.append("Record and govern the identity candidates considered.")
        if len(matched) > 1:
            blockers.append("Resolve the identity collision to no more than one Match.")
        if unresolved:
            blockers.append(
                f"Disposition all identity candidates ({len(unresolved)} unresolved or ambiguous)."
            )
        if not matched and not identity_states.intersection(
                {"Unknown", "Information Gap", "Contradiction"}):
            blockers.append(
                "Resolve one evidence-linked identity Match or govern the unresolved identity as an unknown, gap, or contradiction."
            )

        research_plans = [
            item for item in items
            if item["structured_detail"].get("record_type") == "salintel_research_plan"
            and int(item["structured_detail"].get("authorized_tier", 0)) == tier
        ]
        research_plan = research_plans[-1] if research_plans else None
        research_task_count = 0
        research_tasks_dispositioned = 0
        chat_sources_accessed = 0
        qualified_research_product_count = 0
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
                item for item in items
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
                    f"Truthfully disposition every authorized mixed-source research task "
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
                item for item in items
                if item["structured_detail"].get("record_type") == "salintel_research_product"
                and int(item["structured_detail"].get("plan_id", 0)) == plan_id
                and int(item["structured_detail"].get("authorized_tier", 0)) == tier
            ]
            latest_product = products[-1] if products else None
            latest_result_at = max(
                (str(item["updated_at"]) for item in results), default=""
            )
            qualified_products = [latest_product] if (
                latest_product
                and latest_product["structured_detail"].get("review_status") == "Qualified"
                and str(latest_product["structured_detail"].get("reviewed_by", "")).strip()
                and str(latest_product["structured_detail"].get("reviewed_at", "")).strip()
                and str(latest_product["created_at"]) >= latest_result_at
            ) else []
            qualified_research_product_count = len(qualified_products)
            if not qualified_products:
                blockers.append(
                    "Obtain Salus human qualification of the current tier-specific Chat research product after the latest source result."
                )
        if row["qualification_status"] != "Qualified":
            blockers.append("Obtain human qualification after the final finding or identity decision.")
        if row["status"] in ("Tier Complete", "Closed"):
            blockers.append("Completed work cannot be silently reopened or recompleted.")
        return {
            "ready": not blockers,
            "blockers": blockers,
            "expected_requirement_count": len(expected_keys),
            "addressed_requirement_count": len(expected_keys & addressed_keys),
            "identity_candidate_count": len(candidates),
            "matched_identity_count": len(matched),
            "unresolved_identity_count": len(unresolved),
            "research_plan_id": int(research_plan["id"]) if research_plan else None,
            "research_task_count": research_task_count,
            "research_tasks_dispositioned": research_tasks_dispositioned,
            "chat_sources_accessed": chat_sources_accessed,
            "qualified_research_product_count": qualified_research_product_count,
        }

    @app.middleware("http")
    async def personnel_completion_gate(request: Request, call_next):
        """Prevent the generic tier endpoint from bypassing Personnel closure rules."""
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
            if (not row or row["domain_key"] != "personnel-assessment"
                    or int(row["tenant_id"]) != tenant_id(request)):
                row = None
            readiness = completion_readiness(conn, row) if row else None
        finally:
            conn.close()
        if row is None:
            return await call_next(request)
        try:
            require(request, "decide")
            authority(request, "SalINTEL Personnel Assessment tier completion")
        except HTTPException:
            return await call_next(request)
        if not readiness["ready"]:
            return JSONResponse(
                status_code=409,
                content={
                    "detail": "Personnel Assessment is not ready for bounded-tier completion.",
                    "blockers": readiness["blockers"],
                },
            )
        return await call_next(request)

    @app.get("/api/salintel/personnel-assessment/checklist")
    def checklist(request: Request):
        authorize(request, "checklist review")
        return {"version": PLAN_VERSION, "tiers": [
            {"key": key, "tier_required": tier, "category": category,
             "question": question, "collection_channels": channels}
            for key, tier, category, question, channels in CHECKLIST
        ]}

    @app.post("/api/salintel/personnel-assessments/{investigation_id}/research-plan")
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
            for item in personnel_items(conn, investigation_id):
                if item["structured_detail"].get("record_type") == "personnel_checklist":
                    raise HTTPException(409, "Personnel research plan already exists")
            selected = [entry for entry in CHECKLIST if entry[1] <= tier]
            for key, required_tier, category, question, channels in selected:
                create_item(
                    conn, request, row, "Collection Requirement", "Information Gap",
                    f"{key} — {category}",
                    {"record_type": "personnel_checklist", "plan_version": PLAN_VERSION,
                     "checklist_key": key, "tier_required": required_tier,
                     "category": category, "question": question,
                     "collection_channels": channels, "status": "Open"},
                )
            conn.execute(
                "UPDATE salintel_investigations SET status='In Progress',"
                "qualification_status='Unqualified',updated_by=?,updated_at=? WHERE id=?",
                (actor(request), now(), investigation_id),
            )
            event(conn, request, row, "PERSONNEL_RESEARCH_PLAN_CREATED",
                  f"{PLAN_VERSION}; bounded through Tier {tier}; {payload.reason}")
            audit(conn, request, "PERSONNEL_RESEARCH_PLAN_CREATED", investigation_id,
                  f"version={PLAN_VERSION}; tier={tier}; tasks={len(selected)}")
            conn.commit()
            return {"investigation_id": investigation_id, "plan_version": PLAN_VERSION,
                    "authorized_tier": tier, "task_count": len(selected)}
        finally:
            conn.close()

    @app.post("/api/salintel/personnel-assessments/{investigation_id}/identity-candidates")
    def add_identity_candidate(investigation_id: int, payload: IdentityCandidate,
                               request: Request):
        authorize(request, "identity resolution")
        require(request, "write")
        if len(payload.identifiers) > 20:
            raise HTTPException(422, "Too many identity discriminators")
        clean_identifiers = {
            str(key).strip(): str(value).strip()
            for key, value in payload.identifiers.items()
            if str(key).strip() and str(value).strip()
        }
        if not clean_identifiers:
            raise HTTPException(422, "At least one authorized identity discriminator is required")
        conn = db()
        try:
            row = scoped(conn, investigation_id, request)
            if int(row["authorized_tier"]) == 0:
                raise HTTPException(409, "Authorize a bounded investigation tier first")
            if payload.source_material_id:
                linked_source(conn, investigation_id, request, payload.source_material_id)
            normalized = " ".join(payload.candidate_name.lower().split())
            fingerprint = hashlib.sha256(canonical(clean_identifiers).encode("utf-8")).hexdigest()
            collisions = []
            for item in personnel_items(conn, investigation_id):
                detail = item["structured_detail"]
                if (detail.get("record_type") == "personnel_identity_candidate"
                        and detail.get("normalized_name") == normalized
                        and detail.get("discriminator_fingerprint") != fingerprint
                        and detail.get("decision") != "Excluded"):
                    collisions.append(item["id"])
            detail = {
                "record_type": "personnel_identity_candidate",
                "candidate_name": payload.candidate_name.strip(),
                "normalized_name": normalized,
                "identifiers": clean_identifiers,
                "discriminator_fingerprint": fingerprint,
                "origin_type": payload.origin_type,
                "narrative": payload.narrative.strip(),
                "decision": "Unresolved",
                "collision_with_item_ids": collisions,
            }
            item_id = create_item(
                conn, request, row, "Finding", "Reported Information",
                f"Identity candidate — {payload.candidate_name.strip()}", detail,
                "Not Assessed", "Not Assessed", payload.source_material_id,
            )
            conn.execute(
                "UPDATE salintel_investigations SET status='In Progress',"
                "qualification_status='Unqualified',updated_by=?,updated_at=? WHERE id=?",
                (actor(request), now(), investigation_id),
            )
            event(conn, request, row, "PERSONNEL_IDENTITY_CANDIDATE_ADDED",
                  f"item_id={item_id}; collision={bool(collisions)}")
            audit(conn, request, "PERSONNEL_IDENTITY_CANDIDATE_ADDED", investigation_id,
                  f"item_id={item_id}; collision={bool(collisions)}")
            conn.commit()
            return {"id": item_id, "identity_collision": bool(collisions),
                    "collision_with_item_ids": collisions}
        finally:
            conn.close()

    @app.post("/api/salintel/personnel-assessments/{investigation_id}/identity-candidates/{item_id}/decision")
    def decide_identity_candidate(investigation_id: int, item_id: int,
                                  payload: DecideCandidate, request: Request):
        authorize(request, "identity decision")
        require(request, "decide")
        conn = db()
        try:
            row = scoped(conn, investigation_id, request)
            item = conn.execute(
                "SELECT * FROM salintel_investigation_items WHERE id=? AND investigation_id=?",
                (item_id, investigation_id),
            ).fetchone()
            if not item:
                raise HTTPException(404, "Identity candidate not found")
            detail = parse_detail(item)
            if detail.get("record_type") != "personnel_identity_candidate":
                raise HTTPException(422, "Item is not an identity candidate")
            if payload.decision == "Match":
                if item["source_material_id"] in (None, ""):
                    raise HTTPException(409, "A matched identity requires linked source material")
                existing = []
                for other in personnel_items(conn, investigation_id):
                    od = other["structured_detail"]
                    if (other["id"] != item_id
                            and od.get("record_type") == "personnel_identity_candidate"
                            and od.get("decision") == "Match"):
                        existing.append(other["id"])
                if existing:
                    raise HTTPException(409, "A different identity candidate is already matched")
            detail["decision"] = payload.decision
            detail["decision_reason"] = payload.reason.strip()
            detail["decided_by"] = actor(request)
            detail["decided_at"] = now()
            epistemic = {
                "Match": "Analyst Judgment", "Excluded": "Analyst Judgment",
                "Ambiguous": "Unknown", "Contradiction": "Contradiction",
            }[payload.decision]
            conn.execute(
                "UPDATE salintel_investigation_items SET epistemic_state=?,detail=?,"
                "updated_at=? WHERE id=?",
                (epistemic, canonical(detail), now(), item_id),
            )
            conn.execute(
                "UPDATE salintel_investigations SET qualification_status='Unqualified',"
                "updated_by=?,updated_at=? WHERE id=?",
                (actor(request), now(), investigation_id),
            )
            event(conn, request, row, "PERSONNEL_IDENTITY_DECIDED",
                  f"item_id={item_id}; decision={payload.decision}; {payload.reason}")
            audit(conn, request, "PERSONNEL_IDENTITY_DECIDED", investigation_id,
                  f"item_id={item_id}; decision={payload.decision}")
            conn.commit()
            return {"id": item_id, "decision": payload.decision,
                    "epistemic_state": epistemic}
        finally:
            conn.close()

    @app.post("/api/salintel/personnel-assessments/{investigation_id}/findings")
    def add_personnel_finding(investigation_id: int, payload: PersonnelFinding,
                              request: Request):
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
            if payload.epistemic_state == "Verified Fact":
                if payload.origin_type != "Analyst Assessment" or not payload.source_material_id:
                    raise HTTPException(
                        409, "Verified Fact requires Salus analyst assessment and linked source material"
                    )
            detail = {
                "record_type": "personnel_finding",
                "plan_version": PLAN_VERSION,
                "checklist_key": payload.checklist_key,
                "tier_required": template[1],
                "category": payload.category,
                "origin_type": payload.origin_type,
                "narrative": payload.narrative.strip(),
                "relationship_context": payload.relationship_context.strip(),
                "competing_resource_relevance": payload.competing_resource_relevance,
                "insider_threat_relevance": payload.insider_threat_relevance,
                "protective_intelligence_relevance": payload.protective_intelligence_relevance,
                "human_qualification_required": True,
            }
            item_id = create_item(
                conn, request, row,
                "Contradiction" if payload.epistemic_state == "Contradiction" else "Finding",
                payload.epistemic_state, payload.title, detail,
                payload.source_reliability, payload.information_confidence,
                payload.source_material_id,
            )
            conn.execute(
                "UPDATE salintel_investigations SET status='In Progress',"
                "qualification_status='Unqualified',updated_by=?,updated_at=? WHERE id=?",
                (actor(request), now(), investigation_id),
            )
            event(conn, request, row, "PERSONNEL_FINDING_ADDED",
                  f"item_id={item_id}; checklist={payload.checklist_key}; "
                  f"epistemic={payload.epistemic_state}")
            audit(conn, request, "PERSONNEL_FINDING_ADDED", investigation_id,
                  f"item_id={item_id}; category={payload.category}")
            conn.commit()
            return {"id": item_id, "qualification_status": "Unqualified",
                    "member_visible": False}
        finally:
            conn.close()

    @app.get("/api/salintel/personnel-assessments/{investigation_id}")
    def personnel_assessment(investigation_id: int, request: Request):
        authorize(request, "review")
        conn = db()
        try:
            row = scoped(conn, investigation_id, request)
            items = personnel_items(conn, investigation_id)
            checklist_items, candidates, findings = [], [], []
            resolved = set()
            for item in items:
                detail = item["structured_detail"]
                record_type = detail.get("record_type")
                if record_type == "personnel_checklist":
                    checklist_items.append(item)
                elif record_type == "personnel_identity_candidate":
                    candidates.append(item)
                elif record_type == "personnel_finding":
                    findings.append(item)
                    resolved.add(detail.get("checklist_key"))
            for item in checklist_items:
                item["plan_status"] = (
                    "Addressed" if item["structured_detail"].get("checklist_key") in resolved
                    else "Open"
                )
            unresolved_candidates = [
                item for item in candidates
                if item["structured_detail"].get("decision") in ("Unresolved", "Ambiguous")
            ]
            matched = [
                item for item in candidates
                if item["structured_detail"].get("decision") == "Match"
            ]
            collision = any(item["structured_detail"].get("collision_with_item_ids")
                            for item in unresolved_candidates)
            identity_status = (
                "Resolved" if len(matched) == 1 and not collision
                else "Partially Resolved" if matched
                else "Unresolved"
            )
            return {
                "investigation": dict(row),
                "plan_version": PLAN_VERSION if checklist_items else "",
                "authorized_tier": int(row["authorized_tier"]),
                "checklist": checklist_items,
                "identity_candidates": candidates,
                "identity_resolution_status": identity_status,
                "identity_collision": collision,
                "findings": findings,
                "progress": {
                    "total": len(checklist_items),
                    "addressed": sum(1 for item in checklist_items
                                     if item["plan_status"] == "Addressed"),
                    "open": sum(1 for item in checklist_items
                                if item["plan_status"] == "Open"),
                },
                "qualification_status": row["qualification_status"],
                "disclosure_status": row["disclosure_status"],
                "completion_readiness": completion_readiness(conn, row),
            }
        finally:
            conn.close()
