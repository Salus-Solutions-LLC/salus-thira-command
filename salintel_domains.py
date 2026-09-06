"""Shared, governed SalINTEL investigative-domain records.

Domain-specific investigations extend this module. Investigation depth, lifecycle,
qualification, disclosure, tenancy, commercial treatment, and audit state are
server-controlled; source bytes remain in the generic material capability.
"""
from __future__ import annotations
import json
import uuid
from typing import Literal
from fastapi import HTTPException, Request
from pydantic import BaseModel, ConfigDict, Field, field_validator

Tier = Literal[1, 2, 3]
Sensitivity = Literal["Standard", "Restricted", "Sensitive", "Highly Sensitive"]
Epistemic = Literal[
    "Verified Fact", "Reported Information", "Reasonable Inference",
    "Analyst Judgment", "Hypothesis", "Unresolved Allegation", "Assumption",
    "Contradiction", "Information Gap", "Unknown",
]
ItemKind = Literal[
    "Finding", "Indicator / Warning", "Question", "Collection Requirement",
    "Reassessment Trigger", "Contradiction",
]
Qualification = Literal["Unqualified", "Analyst Reviewed", "Qualified", "Rejected"]
Commercial = Literal["Not Determined", "Included", "Bundled", "Separate Proposal", "Waived"]
Lens = Literal["Prevention", "Protection", "Mitigation", "Response", "Recovery"]


class CreateInvestigation(BaseModel):
    model_config = ConfigDict(extra="forbid")
    domain_key: str = Field(min_length=2, max_length=100, pattern=r"^[a-z0-9-]+$")
    title: str = Field(min_length=1, max_length=240)
    subject_reference: str = Field(min_length=1, max_length=500)
    purpose: str = Field(min_length=1, max_length=4000)
    requested_tier: Tier
    sensitivity: Sensitivity = "Restricted"
    engagement_context: str = Field(default="", max_length=1000)

    @field_validator("title", "subject_reference", "purpose")
    @classmethod
    def required_text(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("A non-empty value is required.")
        return value


class AuthorizeTier(BaseModel):
    model_config = ConfigDict(extra="forbid")
    authorized_tier: Tier
    scope_statement: str = Field(min_length=1, max_length=8000)
    checklist_version: str = Field(min_length=1, max_length=120)
    effort_bounds: dict[str, str | int | float | bool] = Field(default_factory=dict)
    source_categories: list[str] = Field(default_factory=list, max_length=40)
    exclusions: list[str] = Field(default_factory=list, max_length=40)
    commercial_treatment: Commercial = "Not Determined"
    commercial_reference: str = Field(default="", max_length=300)
    investigative_lenses: list[Lens] = Field(default_factory=lambda: list(LENSES), max_length=5)
    reason: str = Field(min_length=1, max_length=4000)


class AddItem(BaseModel):
    model_config = ConfigDict(extra="forbid")
    item_kind: ItemKind
    epistemic_state: Epistemic
    title: str = Field(min_length=1, max_length=240)
    detail: str = Field(min_length=1, max_length=12000)
    source_reliability: str = Field(default="Not Assessed", max_length=80)
    information_confidence: str = Field(default="Not Assessed", max_length=80)
    source_material_id: int | None = Field(default=None, gt=0)


class DecideQualification(BaseModel):
    model_config = ConfigDict(extra="forbid")
    status: Qualification
    reason: str = Field(min_length=1, max_length=4000)


class CompleteTier(BaseModel):
    model_config = ConfigDict(extra="forbid")
    tier: Tier
    completion_statement: str = Field(min_length=1, max_length=8000)
    residual_unknowns: str = Field(default="", max_length=8000)


class DecideDisclosure(BaseModel):
    model_config = ConfigDict(extra="forbid")
    approved_for_tenant: bool
    reason: str = Field(min_length=1, max_length=4000)


class ReleaseItem(BaseModel):
    model_config = ConfigDict(extra="forbid")
    approved_for_tenant: bool
    reason: str = Field(min_length=1, max_length=4000)


class RecommendTier(BaseModel):
    model_config = ConfigDict(extra="forbid")
    recommended: bool
    reason: str = Field(min_length=1, max_length=4000)


_NAMES = [
    ("personnel-assessment", "Personnel Assessment"),
    ("facility-assessment", "Facility Assessment"),
    ("organizations", "Organizations"),
    ("vendors-suppliers-partners-contractors", "Vendors, Suppliers, Partners and Contractors"),
    ("products-services", "Products and Services"),
    ("transportation-assets-systems", "Transportation Assets and Systems"),
    ("events", "Events"),
    ("geographic-operating-environments", "Geographic Areas and Operating Environments"),
    ("cyber-digital-entities", "Cyber and Digital Entities"),
    ("critical-dependencies", "Critical Dependencies and Interdependencies"),
    ("financial-economic", "Financial and Economic Conditions"),
    ("organizational-governance-leadership", "Organizational Governance, Leadership and Decision Authority"),
    ("public-policy-governmental", "Public Policy and Governmental Environment"),
    ("communications-information-environment", "Communications and Information Environment"),
    ("emerging-threats-hazards", "Emerging Threats and Hazards"),
    ("emergency-capabilities-readiness", "Emergency Capabilities, Resources and Readiness"),
    ("supply-chain-logistics", "Supply Chain, Logistics and Distribution"),
    ("infrastructure-utilities", "Infrastructure, Utilities and Essential Services"),
    ("technology-data-ai-ot", "Technology, Software, Data, Cloud, AI and OT/ICS"),
    ("legal-regulatory-compliance", "Legal, Regulatory, Compliance and Policy"),
    ("public-health-healthcare-ems-biosecurity", "Public Health, Healthcare, EMS and Biosecurity"),
    ("environmental-weather-natural-hazards", "Environmental, Weather and Natural Hazards"),
    ("defensive-threat-actor", "Defensive Adversarial and Threat-Actor Intelligence"),
    ("public-safety-mutual-aid", "Public Safety, Emergency Services and Mutual Aid"),
    ("workforce-human-capital", "Workforce, Labor and Human-Capital Dependencies"),
    ("stakeholder-reputation-media", "Stakeholders, Reputation, Media and Public Information"),
    ("insurance-contracts-liability", "Insurance, Contracts, Liability and Risk Transfer"),
    ("incidents-exercises-lessons", "Incidents, Near Misses, Exercises and Lessons Learned"),
    ("continuity-resilience-restoration", "Continuity, Resilience and Restoration"),
    ("intelligence-sources", "Intelligence Sources and Source Reliability"),
    ("indicators-warnings-anomalies", "Indicators, Warnings, Precursors, Anomalies and Trends"),
    ("critical-functions-missions", "Critical Functions, Missions and Essential Services"),
    ("resources-capacity-scarcity", "Resources, Capacity, Surge and Scarcity"),
    ("strategic-assumptions", "Strategic Assumptions and Planning Premises"),
    ("geopolitical-international", "Geopolitical and International Environment"),
    ("security-controls-effectiveness", "Security Controls and Protective-System Effectiveness"),
    ("partnerships-alliances", "Partnerships, Alliances and Third-Party Relationships"),
]
TIERS = [
    {"tier": 1, "name": "Initial / Baseline Investigation", "bounded": True},
    {"tier": 2, "name": "Enhanced Investigation", "bounded": True},
    {"tier": 3, "name": "Deep-Dive / Comprehensive Investigation", "bounded": True},
]
LENSES = ["Prevention", "Protection", "Mitigation", "Response", "Recovery"]

SCHEMA = """
CREATE TABLE IF NOT EXISTS salintel_domains (
 id INTEGER PRIMARY KEY AUTOINCREMENT, domain_key TEXT NOT NULL UNIQUE,
 display_name TEXT NOT NULL, description TEXT NOT NULL,
 subject_entity_kinds TEXT NOT NULL DEFAULT 'configurable',
 lifecycle_status TEXT NOT NULL DEFAULT 'Enabled',
 default_sensitivity TEXT NOT NULL DEFAULT 'Restricted',
 default_disclosure_posture TEXT NOT NULL DEFAULT 'Salus Internal',
 investigative_lenses_json TEXT NOT NULL, handoff_types_json TEXT NOT NULL,
 allowed_relationships_json TEXT NOT NULL, required_review_level TEXT NOT NULL,
 tier_profiles_json TEXT NOT NULL, version INTEGER NOT NULL DEFAULT 1,
 approved_by TEXT NOT NULL, approved_at TEXT NOT NULL,
 created_at TEXT NOT NULL, updated_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS salintel_investigations (
 id INTEGER PRIMARY KEY AUTOINCREMENT, tenant_id INTEGER NOT NULL,
 record_key TEXT NOT NULL UNIQUE, domain_key TEXT NOT NULL, title TEXT NOT NULL,
 subject_reference TEXT NOT NULL, purpose TEXT NOT NULL,
 engagement_context TEXT NOT NULL DEFAULT '', status TEXT NOT NULL DEFAULT 'Requested',
 sensitivity TEXT NOT NULL DEFAULT 'Restricted',
 enterprise_visibility TEXT NOT NULL DEFAULT 'Salus Internal',
 disclosure_status TEXT NOT NULL DEFAULT 'Salus Internal',
 qualification_status TEXT NOT NULL DEFAULT 'Unqualified',
 requested_tier INTEGER NOT NULL, authorized_tier INTEGER NOT NULL DEFAULT 0,
 completed_tier INTEGER NOT NULL DEFAULT 0, tier_profile_version TEXT NOT NULL DEFAULT '',
 authorized_scope_json TEXT NOT NULL DEFAULT '{}', effort_bounds_json TEXT NOT NULL DEFAULT '{}',
 source_categories_json TEXT NOT NULL DEFAULT '[]', exclusions_json TEXT NOT NULL DEFAULT '[]',
 commercial_treatment TEXT NOT NULL DEFAULT 'Not Determined',
 commercial_reference TEXT NOT NULL DEFAULT '',
 deeper_tier_recommended INTEGER NOT NULL DEFAULT 0, deeper_tier_reason TEXT NOT NULL DEFAULT '',
 completion_statement TEXT NOT NULL DEFAULT '', residual_unknowns TEXT NOT NULL DEFAULT '',
 created_by TEXT NOT NULL, created_at TEXT NOT NULL, updated_by TEXT NOT NULL,
 updated_at TEXT NOT NULL, reviewed_by TEXT NOT NULL DEFAULT '',
 reviewed_at TEXT NOT NULL DEFAULT '', disclosed_by TEXT NOT NULL DEFAULT '',
 disclosed_at TEXT NOT NULL DEFAULT '',
 FOREIGN KEY (tenant_id) REFERENCES tenants(id) ON DELETE CASCADE,
 FOREIGN KEY (domain_key) REFERENCES salintel_domains(domain_key) ON DELETE RESTRICT
);
CREATE INDEX IF NOT EXISTS idx_salintel_investigation_tenant
 ON salintel_investigations(tenant_id,domain_key,status,id);
CREATE TABLE IF NOT EXISTS salintel_investigation_items (
 id INTEGER PRIMARY KEY AUTOINCREMENT, tenant_id INTEGER NOT NULL,
 investigation_id INTEGER NOT NULL, item_key TEXT NOT NULL UNIQUE,
 item_kind TEXT NOT NULL, epistemic_state TEXT NOT NULL, title TEXT NOT NULL,
 detail TEXT NOT NULL, source_reliability TEXT NOT NULL DEFAULT 'Not Assessed',
 information_confidence TEXT NOT NULL DEFAULT 'Not Assessed',
 source_material_id INTEGER, member_visible INTEGER NOT NULL DEFAULT 0,
 created_by TEXT NOT NULL, created_at TEXT NOT NULL, updated_at TEXT NOT NULL,
 FOREIGN KEY (tenant_id) REFERENCES tenants(id) ON DELETE CASCADE,
 FOREIGN KEY (investigation_id) REFERENCES salintel_investigations(id) ON DELETE CASCADE
);
CREATE INDEX IF NOT EXISTS idx_salintel_item_investigation
 ON salintel_investigation_items(investigation_id,item_kind,epistemic_state,id);
CREATE TABLE IF NOT EXISTS salintel_investigation_events (
 id INTEGER PRIMARY KEY AUTOINCREMENT, tenant_id INTEGER NOT NULL,
 investigation_id INTEGER NOT NULL, version_no INTEGER NOT NULL,
 event_type TEXT NOT NULL, reason TEXT NOT NULL, snapshot_json TEXT NOT NULL,
 changed_by TEXT NOT NULL, changed_by_role TEXT NOT NULL, created_at TEXT NOT NULL,
 FOREIGN KEY (tenant_id) REFERENCES tenants(id) ON DELETE CASCADE,
 FOREIGN KEY (investigation_id) REFERENCES salintel_investigations(id) ON DELETE CASCADE,
 UNIQUE(investigation_id,version_no)
);
"""


def register_salintel_domain_capability(app, core: dict) -> None:
    db, now = core["db"], core["now"]
    actor, role, tenant_id = core["actor"], core["role"], core["tenant_id"]
    require = core["require"]
    require_sensitivity = core["require_sensitivity"]
    is_member = core["protected_member_request"]
    salus_authority = core["require_salus_component_authority"]
    security_event = core["security_event"]

    conn = db()
    try:
        conn.executescript(SCHEMA)
        ts = now()
        tiers = json.dumps(TIERS, separators=(",", ":"))
        lenses = json.dumps(LENSES, separators=(",", ":"))
        handoffs = json.dumps(["SalTHIRA", "SalOPS", "SalCAPA COP", "Reporting"])
        relationships = json.dumps([
            "owns", "operates", "supplies", "depends_on", "affects",
            "supports", "contradicts", "requires_action", "related_to",
        ])
        for key, name in _NAMES:
            conn.execute(
                "INSERT INTO salintel_domains(domain_key,display_name,description,"
                "investigative_lenses_json,handoff_types_json,allowed_relationships_json,"
                "required_review_level,tier_profiles_json,approved_by,approved_at,created_at,updated_at) "
                "VALUES(?,?,?,?,?,?,?,?,?,?,?,?) ON CONFLICT(domain_key) DO NOTHING",
                (key, name, f"Governed SalINTEL investigation of {name.lower()}.",
                 lenses, handoffs, relationships, "Salus Analyst Qualification",
                 tiers, "Salus governed architecture #142", ts, ts, ts),
            )
        conn.commit()
    finally:
        conn.close()

    def authority(request: Request, action: str):
        salus_authority(request, f"SalINTEL {action}")

    def audit(conn, request: Request, action: str, record_id: int, detail: str):
        conn.execute(
            "INSERT INTO audit_log(ts,user_name,action,entity_type,entity_id,detail,tenant_id) "
            "VALUES(?,?,?,?,?,?,?)",
            (now(), actor(request), action, "salintel_investigation",
             record_id, detail[:2000], tenant_id(request)),
        )

    def event(conn, request: Request, record_id: int, event_type: str, reason: str):
        row = conn.execute(
            "SELECT * FROM salintel_investigations WHERE id=?", (record_id,)
        ).fetchone()
        version = int(conn.execute(
            "SELECT COUNT(*) c FROM salintel_investigation_events WHERE investigation_id=?",
            (record_id,),
        ).fetchone()["c"]) + 1
        conn.execute(
            "INSERT INTO salintel_investigation_events(tenant_id,investigation_id,version_no,"
            "event_type,reason,snapshot_json,changed_by,changed_by_role,created_at) "
            "VALUES(?,?,?,?,?,?,?,?,?)",
            (row["tenant_id"], record_id, version, event_type, reason,
             json.dumps(dict(row), sort_keys=True, default=str),
             actor(request), role(request), now()),
        )

    def parsed(value, fallback):
        try:
            return json.loads(value)
        except (TypeError, ValueError):
            return fallback

    def public(row, member=False):
        value = dict(row)
        for raw, name, fallback in (
            ("authorized_scope_json", "authorized_scope", {}),
            ("effort_bounds_json", "effort_bounds", {}),
            ("source_categories_json", "source_categories", []),
            ("exclusions_json", "exclusions", []),
        ):
            value[name] = parsed(value.pop(raw, ""), fallback)
        value["deeper_tier_recommended"] = bool(value["deeper_tier_recommended"])
        if member:
            for key in (
                "enterprise_visibility", "commercial_treatment", "commercial_reference",
                "effort_bounds", "source_categories", "exclusions", "created_by",
                "updated_by", "reviewed_by", "reviewed_at", "disclosed_by",
            ):
                value.pop(key, None)
        return value

    def scoped(conn, record_id: int, request: Request):
        row = conn.execute(
            "SELECT * FROM salintel_investigations WHERE id=?", (record_id,)
        ).fetchone()
        if not row:
            raise HTTPException(404, "SalINTEL investigation not found")
        if int(row["tenant_id"]) != tenant_id(request):
            security_event(request, "SALINTEL_TENANT_BOUNDARY_VIOLATION", "High",
                           f"investigation_id={record_id}")
            raise HTTPException(403, "Tenant boundary violation")
        require_sensitivity(request, row["sensitivity"])
        if is_member(request) and row["disclosure_status"] != "Approved for Tenant":
            raise HTTPException(403, "Investigation is not approved for Protected Member access")
        return row

    @app.get("/api/salintel/domains/catalog")
    def domains(request: Request):
        require(request, "read")
        conn = db()
        rows = []
        for row in conn.execute(
            "SELECT * FROM salintel_domains WHERE lifecycle_status='Enabled' ORDER BY display_name"
        ):
            item = dict(row)
            if is_member(request):
                item = {key: item[key] for key in ("domain_key", "display_name", "description")}
            else:
                for key in ("investigative_lenses", "handoff_types",
                            "allowed_relationships", "tier_profiles"):
                    item[key] = parsed(item.pop(key + "_json"), [])
            rows.append(item)
        conn.close()
        return rows

    @app.post("/api/salintel/investigations")
    def create(payload: CreateInvestigation, request: Request):
        require(request, "write")
        authority(request, "investigation creation")
        conn = db()
        if not conn.execute(
            "SELECT id FROM salintel_domains WHERE domain_key=? AND lifecycle_status='Enabled'",
            (payload.domain_key,),
        ).fetchone():
            conn.close()
            raise HTTPException(422, "Unknown or unavailable investigative domain")
        ts, who = now(), actor(request)
        cur = conn.execute(
            "INSERT INTO salintel_investigations(tenant_id,record_key,domain_key,title,"
            "subject_reference,purpose,engagement_context,status,sensitivity,enterprise_visibility,"
            "disclosure_status,qualification_status,requested_tier,authorized_tier,completed_tier,"
            "created_by,created_at,updated_by,updated_at) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (tenant_id(request), "SII-" + uuid.uuid4().hex, payload.domain_key,
             payload.title, payload.subject_reference, payload.purpose,
             payload.engagement_context.strip(), "Requested", payload.sensitivity,
             "Salus Internal", "Salus Internal", "Unqualified",
             payload.requested_tier, 0, 0, who, ts, who, ts),
        )
        record_id = int(cur.lastrowid)
        event(conn, request, record_id, "INVESTIGATION_REQUESTED",
              f"Requested bounded Tier {payload.requested_tier} investigation.")
        audit(conn, request, "SALINTEL_INVESTIGATION_REQUESTED", record_id,
              f"domain={payload.domain_key}; requested_tier={payload.requested_tier}")
        conn.commit()
        row = conn.execute("SELECT * FROM salintel_investigations WHERE id=?", (record_id,)).fetchone()
        conn.close()
        return public(row)

    @app.get("/api/salintel/investigations")
    def list_records(request: Request, domain_key: str = "", status: str = "",
                     authorized_tier: int = 0, epistemic_state: str = "",
                     phase: str = "", limit: int = 200):
        require(request, "read")
        if epistemic_state and epistemic_state not in set(Epistemic.__args__):
            raise HTTPException(422, "Unknown epistemic-state filter")
        if phase and phase not in LENSES:
            raise HTTPException(422, "Unknown investigative-lens filter")
        clauses, params = ["tenant_id=?"], [tenant_id(request)]
        if is_member(request):
            clauses.append("disclosure_status='Approved for Tenant'")
        if domain_key:
            clauses.append("domain_key=?"); params.append(domain_key)
        if status:
            clauses.append("status=?"); params.append(status)
        if authorized_tier in (1, 2, 3):
            clauses.append("authorized_tier=?"); params.append(authorized_tier)
        if epistemic_state:
            clauses.append("EXISTS (SELECT 1 FROM salintel_investigation_items si "
                           "WHERE si.investigation_id=salintel_investigations.id "
                           "AND si.epistemic_state=?)")
            params.append(epistemic_state)
        params.append(max(1, min(limit, 1000)))
        conn = db()
        rows = []
        for row in conn.execute(
            "SELECT * FROM salintel_investigations WHERE " + " AND ".join(clauses) +
            " ORDER BY updated_at DESC,id DESC LIMIT ?", tuple(params)
        ):
            try:
                require_sensitivity(request, row["sensitivity"])
                item = public(row, is_member(request))
                lenses = item.get("authorized_scope", {}).get("investigative_lenses", [])
                if phase and phase not in lenses:
                    continue
                rows.append(item)
            except HTTPException:
                continue
        conn.close()
        return rows

    @app.get("/api/salintel/investigations/{record_id}")
    def get_record(record_id: int, request: Request):
        require(request, "read")
        conn = db()
        row, member = scoped(conn, record_id, request), is_member(request)
        result = public(row, member)
        suffix = " AND member_visible=1" if member else ""
        result["items"] = [dict(item) for item in conn.execute(
            "SELECT * FROM salintel_investigation_items WHERE investigation_id=?" +
            suffix + " ORDER BY id", (record_id,)
        )]
        if member:
            for item in result["items"]:
                item.pop("source_material_id", None); item.pop("created_by", None)
            result["events"], result["material_links"] = [], []
        else:
            result["events"] = [dict(item) for item in conn.execute(
                "SELECT id,version_no,event_type,reason,changed_by,changed_by_role,created_at "
                "FROM salintel_investigation_events WHERE investigation_id=? ORDER BY version_no",
                (record_id,))
            ]
            result["material_links"] = [dict(item) for item in conn.execute(
                "SELECT id,material_id,purpose,linked_by,linked_by_role,linked_at FROM material_links "
                "WHERE tenant_id=? AND target_type='salintel_investigation' AND target_id=? ORDER BY id",
                (tenant_id(request), record_id))
            ]
        conn.close()
        return result

    @app.post("/api/salintel/investigations/{record_id}/authorize-tier")
    def authorize(record_id: int, payload: AuthorizeTier, request: Request):
        require(request, "decide"); authority(request, "tier authorization")
        conn = db(); row = scoped(conn, record_id, request)
        if payload.authorized_tier < int(row["completed_tier"]):
            conn.close(); raise HTTPException(409, "Authorization cannot be below a completed tier")
        if len(payload.effort_bounds) > 30:
            conn.close(); raise HTTPException(422, "Too many effort bounds")
        ts, who = now(), actor(request)
        lenses = [lens for lens in LENSES if lens in payload.investigative_lenses]
        if not lenses:
            conn.close(); raise HTTPException(422, "At least one investigative lens is required")
        scope = {"statement": payload.scope_statement.strip(),
                 "checklist_version": payload.checklist_version.strip(),
                 "investigative_lenses": lenses}
        conn.execute(
            "UPDATE salintel_investigations SET authorized_tier=?,tier_profile_version=?,"
            "authorized_scope_json=?,effort_bounds_json=?,source_categories_json=?,exclusions_json=?,"
            "commercial_treatment=?,commercial_reference=?,status='Authorized',"
            "qualification_status='Unqualified',updated_by=?,updated_at=? WHERE id=?",
            (payload.authorized_tier, f"{row['domain_key']}-{payload.checklist_version}",
             json.dumps(scope, separators=(",", ":")),
             json.dumps(payload.effort_bounds, sort_keys=True, separators=(",", ":")),
             json.dumps(payload.source_categories, separators=(",", ":")),
             json.dumps(payload.exclusions, separators=(",", ":")),
             payload.commercial_treatment, payload.commercial_reference.strip(),
             who, ts, record_id),
        )
        event(conn, request, record_id, "TIER_AUTHORIZED",
              f"Tier {payload.authorized_tier}: {payload.reason}")
        audit(conn, request, "SALINTEL_TIER_AUTHORIZED", record_id,
              f"tier={payload.authorized_tier}; commercial={payload.commercial_treatment}")
        conn.commit()
        result = conn.execute("SELECT * FROM salintel_investigations WHERE id=?", (record_id,)).fetchone()
        conn.close()
        return public(result)

    @app.post("/api/salintel/investigations/{record_id}/items")
    def add_item(record_id: int, payload: AddItem, request: Request):
        require(request, "write"); authority(request, "analysis")
        conn = db(); row = scoped(conn, record_id, request)
        if int(row["authorized_tier"]) == 0:
            conn.close(); raise HTTPException(409, "Authorize a bounded tier before analysis")
        if row["status"] in ("Tier Complete", "Closed"):
            conn.close(); raise HTTPException(409, "Completed work cannot be silently reopened")
        if payload.source_material_id is not None:
            linked = conn.execute(
                "SELECT m.sensitivity FROM material_links l JOIN materials m ON m.id=l.material_id "
                "WHERE l.tenant_id=? AND l.material_id=? AND l.target_type='salintel_investigation' "
                "AND l.target_id=?", (tenant_id(request), payload.source_material_id, record_id)
            ).fetchone()
            if not linked:
                conn.close()
                raise HTTPException(409, "Source must first complete governed material review and linking")
            require_sensitivity(request, linked["sensitivity"])
        ts = now()
        cur = conn.execute(
            "INSERT INTO salintel_investigation_items(tenant_id,investigation_id,item_key,item_kind,"
            "epistemic_state,title,detail,source_reliability,information_confidence,source_material_id,"
            "member_visible,created_by,created_at,updated_at) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (tenant_id(request), record_id, "SIT-" + uuid.uuid4().hex, payload.item_kind,
             payload.epistemic_state, payload.title, payload.detail,
             payload.source_reliability.strip() or "Not Assessed",
             payload.information_confidence.strip() or "Not Assessed",
             payload.source_material_id, 0, actor(request), ts, ts),
        )
        item_id = int(cur.lastrowid)
        conn.execute(
            "UPDATE salintel_investigations SET status='In Progress',qualification_status='Unqualified',"
            "updated_by=?,updated_at=? WHERE id=?", (actor(request), ts, record_id))
        event(conn, request, record_id, "ANALYTIC_ITEM_ADDED",
              f"{payload.item_kind}; {payload.epistemic_state}; item_id={item_id}")
        audit(conn, request, "SALINTEL_ITEM_ADDED", record_id,
              f"item_id={item_id}; epistemic_state={payload.epistemic_state}")
        conn.commit()
        result = conn.execute("SELECT * FROM salintel_investigation_items WHERE id=?", (item_id,)).fetchone()
        conn.close()
        return dict(result)

    @app.post("/api/salintel/investigations/{record_id}/qualify")
    def qualify(record_id: int, payload: DecideQualification, request: Request):
        require(request, "decide"); authority(request, "human qualification")
        conn = db(); scoped(conn, record_id, request)
        count = int(conn.execute(
            "SELECT COUNT(*) c FROM salintel_investigation_items WHERE investigation_id=?",
            (record_id,)).fetchone()["c"])
        if payload.status in ("Analyst Reviewed", "Qualified") and not count:
            conn.close(); raise HTTPException(409, "At least one analytic item is required")
        ts = now()
        conn.execute(
            "UPDATE salintel_investigations SET qualification_status=?,reviewed_by=?,reviewed_at=?,"
            "updated_by=?,updated_at=? WHERE id=?",
            (payload.status, actor(request), ts, actor(request), ts, record_id))
        event(conn, request, record_id, "QUALIFICATION_DECIDED",
              f"{payload.status}: {payload.reason}")
        audit(conn, request, "SALINTEL_QUALIFICATION_DECIDED", record_id, payload.status)
        conn.commit()
        result = conn.execute("SELECT * FROM salintel_investigations WHERE id=?", (record_id,)).fetchone()
        conn.close()
        return public(result)

    @app.post("/api/salintel/investigations/{record_id}/complete-tier")
    def complete(record_id: int, payload: CompleteTier, request: Request):
        require(request, "decide"); authority(request, "tier completion")
        conn = db(); row = scoped(conn, record_id, request)
        if payload.tier != int(row["authorized_tier"]):
            conn.close(); raise HTTPException(409, "Only the authorized tier may be completed")
        if row["qualification_status"] != "Qualified":
            conn.close(); raise HTTPException(409, "Human qualification is required")
        ts = now()
        conn.execute(
            "UPDATE salintel_investigations SET completed_tier=?,status='Tier Complete',"
            "completion_statement=?,residual_unknowns=?,updated_by=?,updated_at=? WHERE id=?",
            (payload.tier, payload.completion_statement.strip(), payload.residual_unknowns.strip(),
             actor(request), ts, record_id))
        event(conn, request, record_id, "TIER_COMPLETED",
              f"Bounded Tier {payload.tier} scope completed.")
        audit(conn, request, "SALINTEL_TIER_COMPLETED", record_id, f"tier={payload.tier}")
        conn.commit()
        result = conn.execute("SELECT * FROM salintel_investigations WHERE id=?", (record_id,)).fetchone()
        conn.close()
        return public(result)

    @app.post("/api/salintel/investigations/{record_id}/recommend-tier")
    def recommend(record_id: int, payload: RecommendTier, request: Request):
        require(request, "decide"); authority(request, "tier recommendation")
        conn = db(); row = scoped(conn, record_id, request)
        if payload.recommended and int(row["completed_tier"]) >= 3:
            conn.close(); raise HTTPException(409, "Tier 3 has no higher tier")
        conn.execute(
            "UPDATE salintel_investigations SET deeper_tier_recommended=?,deeper_tier_reason=?,"
            "updated_by=?,updated_at=? WHERE id=?",
            (1 if payload.recommended else 0, payload.reason.strip(),
             actor(request), now(), record_id))
        event(conn, request, record_id, "DEEPER_TIER_RECOMMENDATION", payload.reason)
        audit(conn, request, "SALINTEL_DEEPER_TIER_RECOMMENDED", record_id,
              f"recommended={payload.recommended}")
        conn.commit()
        result = conn.execute("SELECT * FROM salintel_investigations WHERE id=?", (record_id,)).fetchone()
        conn.close()
        return public(result)

    @app.post("/api/salintel/investigations/{record_id}/disclosure")
    def disclose(record_id: int, payload: DecideDisclosure, request: Request):
        require(request, "decide"); authority(request, "disclosure")
        conn = db(); row = scoped(conn, record_id, request)
        if payload.approved_for_tenant and (
            row["qualification_status"] != "Qualified" or int(row["completed_tier"]) == 0
        ):
            conn.close()
            raise HTTPException(409, "Disclosure requires qualified, completed work")
        target, ts = ("Approved for Tenant" if payload.approved_for_tenant else "Salus Internal"), now()
        conn.execute(
            "UPDATE salintel_investigations SET disclosure_status=?,disclosed_by=?,disclosed_at=?,"
            "updated_by=?,updated_at=? WHERE id=?",
            (target, actor(request), ts if payload.approved_for_tenant else "",
             actor(request), ts, record_id))
        event(conn, request, record_id, "DISCLOSURE_DECIDED", f"{target}: {payload.reason}")
        audit(conn, request, "SALINTEL_DISCLOSURE_DECIDED", record_id, target)
        conn.commit()
        result = conn.execute("SELECT * FROM salintel_investigations WHERE id=?", (record_id,)).fetchone()
        conn.close()
        return public(result)

    @app.post("/api/salintel/investigations/{record_id}/items/{item_id}/release")
    def release_item(record_id: int, item_id: int, payload: ReleaseItem, request: Request):
        require(request, "decide"); authority(request, "item disclosure")
        conn = db(); row = scoped(conn, record_id, request)
        item = conn.execute(
            "SELECT * FROM salintel_investigation_items WHERE id=? AND investigation_id=?",
            (item_id, record_id)).fetchone()
        if not item:
            conn.close(); raise HTTPException(404, "Investigative item not found")
        if payload.approved_for_tenant:
            if row["disclosure_status"] != "Approved for Tenant" or row["qualification_status"] != "Qualified":
                conn.close(); raise HTTPException(409, "Release requires an approved qualified investigation")
            if item["source_material_id"] not in (None, ""):
                material = conn.execute(
                    "SELECT disclosure_status FROM materials WHERE id=? AND tenant_id=?",
                    (item["source_material_id"], tenant_id(request))).fetchone()
                if not material or material["disclosure_status"] != "Approved for Tenant":
                    conn.close()
                    raise HTTPException(409, "Linked source requires independent disclosure approval")
        conn.execute(
            "UPDATE salintel_investigation_items SET member_visible=?,updated_at=? WHERE id=?",
            (1 if payload.approved_for_tenant else 0, now(), item_id))
        event(conn, request, record_id, "ITEM_DISCLOSURE_DECIDED",
              f"item_id={item_id}; approved={payload.approved_for_tenant}; {payload.reason}")
        audit(conn, request, "SALINTEL_ITEM_DISCLOSURE_DECIDED", record_id,
              f"item_id={item_id}; approved={payload.approved_for_tenant}")
        conn.commit()
        result = conn.execute("SELECT * FROM salintel_investigation_items WHERE id=?", (item_id,)).fetchone()
        conn.close()
        return dict(result)
