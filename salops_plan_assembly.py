"""Governed autonomous emergency-plan research, assembly, and revision foundation.

Issue #184 extends SalOPS Preparedness, Planning & Exercises.  Chat may inspect,
research, reconcile, draft, compare, and recommend.  This module deliberately
keeps plan authority, approval, release, policy, commercial treatment, and
Protected Member disclosure outside automated control.
"""
from __future__ import annotations

import hashlib
import json
import uuid
from typing import Any, Literal, Optional

from fastapi import HTTPException, Request
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


RUN_STATES = (
    "Research Planning", "Collecting", "Drafting", "Submitted for Human Review",
    "Human Reviewed", "Qualified", "Returned for Revision", "Rejected",
)
SOURCE_KINDS = (
    "Protected Member Data", "Salus Library", "SalINTEL", "SalTHIRA", "SalOPS",
    "PROVE", "Incident / Exercise", "Uploaded Material", "External Research",
    "Approved Partner Return",
)
ACCESS_STATES = ("Accessed", "Unavailable", "Human / Field Needed", "Partner Needed")
EPISTEMIC_STATES = (
    "Verified Fact", "Reported Information", "Inference", "Analyst Judgment",
    "Hypothesis", "Unresolved Allegation", "Assumption", "Contradiction",
    "Information Gap", "Unknown",
)
QUESTION_TARGETS = (
    "Protected Member", "Salus Investigator", "Interview / Call", "Site / Field",
    "Document Request", "Specialist", "Approved Partner",
)
REVISION_STATES = ("Pending Salus Review", "Accepted for Drafting", "Rejected")


SCHEMA = r"""
CREATE TABLE IF NOT EXISTS salops_plan_assembly_runs (
  id TEXT PRIMARY KEY,
  tenant_id INTEGER NOT NULL,
  base_plan_id TEXT,
  base_plan_version INTEGER NOT NULL DEFAULT 0,
  base_plan_status TEXT NOT NULL DEFAULT '',
  base_plan_snapshot_json TEXT NOT NULL DEFAULT '{}',
  base_plan_sha256 TEXT NOT NULL DEFAULT '',
  assembly_mode TEXT NOT NULL,
  plan_title TEXT NOT NULL,
  plan_type TEXT NOT NULL,
  purpose TEXT NOT NULL,
  scope_statement TEXT NOT NULL,
  portfolio_scope_json TEXT NOT NULL DEFAULT '{}',
  internal_record_refs_json TEXT NOT NULL DEFAULT '[]',
  library_refs_json TEXT NOT NULL DEFAULT '[]',
  authorized_external_sources_json TEXT NOT NULL DEFAULT '[]',
  source_exclusions_json TEXT NOT NULL DEFAULT '[]',
  research_questions_json TEXT NOT NULL DEFAULT '[]',
  known_unknowns_json TEXT NOT NULL DEFAULT '[]',
  assumptions_to_validate_json TEXT NOT NULL DEFAULT '[]',
  contradictions_json TEXT NOT NULL DEFAULT '[]',
  missing_authorities_json TEXT NOT NULL DEFAULT '[]',
  unresolved_dependencies_json TEXT NOT NULL DEFAULT '[]',
  affected_sections_json TEXT NOT NULL DEFAULT '[]',
  proposed_training_actions_json TEXT NOT NULL DEFAULT '[]',
  proposed_exercise_actions_json TEXT NOT NULL DEFAULT '[]',
  proposed_validation_actions_json TEXT NOT NULL DEFAULT '[]',
  completion_statement TEXT NOT NULL DEFAULT '',
  change_rationale TEXT NOT NULL DEFAULT '',
  sensitivity TEXT NOT NULL DEFAULT 'Standard',
  status TEXT NOT NULL DEFAULT 'Research Planning',
  current_iteration INTEGER NOT NULL DEFAULT 1,
  content_sha256 TEXT NOT NULL DEFAULT '',
  created_by TEXT NOT NULL,
  created_at TEXT NOT NULL,
  updated_by TEXT NOT NULL,
  updated_at TEXT NOT NULL,
  submitted_by TEXT NOT NULL DEFAULT '',
  submitted_at TEXT NOT NULL DEFAULT '',
  reviewed_by TEXT NOT NULL DEFAULT '',
  reviewed_at TEXT NOT NULL DEFAULT '',
  review_reason TEXT NOT NULL DEFAULT '',
  qualified_by TEXT NOT NULL DEFAULT '',
  qualified_at TEXT NOT NULL DEFAULT '',
  qualification_reason TEXT NOT NULL DEFAULT '',
  FOREIGN KEY (base_plan_id) REFERENCES salops_preparedness_plans(id) ON DELETE SET NULL
);
CREATE INDEX IF NOT EXISTS idx_plan_assembly_runs_scope ON salops_plan_assembly_runs(tenant_id,status,base_plan_id,created_at);

CREATE TABLE IF NOT EXISTS salops_plan_assembly_sources (
  id TEXT PRIMARY KEY,
  tenant_id INTEGER NOT NULL,
  run_id TEXT NOT NULL,
  source_kind TEXT NOT NULL,
  access_status TEXT NOT NULL,
  locator TEXT NOT NULL DEFAULT '',
  citation TEXT NOT NULL DEFAULT '',
  governed_material_id INTEGER,
  linked_record_type TEXT NOT NULL DEFAULT '',
  linked_record_id TEXT NOT NULL DEFAULT '',
  search_or_collection_method TEXT NOT NULL DEFAULT '',
  source_summary TEXT NOT NULL DEFAULT '',
  source_derived_statements_json TEXT NOT NULL DEFAULT '[]',
  reliability TEXT NOT NULL DEFAULT 'Not Assessed',
  confidence TEXT NOT NULL DEFAULT 'Not Assessed',
  unavailable_reason TEXT NOT NULL DEFAULT '',
  accessed_by TEXT NOT NULL DEFAULT '',
  accessed_at TEXT NOT NULL DEFAULT '',
  created_by TEXT NOT NULL,
  created_at TEXT NOT NULL,
  FOREIGN KEY (run_id) REFERENCES salops_plan_assembly_runs(id) ON DELETE CASCADE
);
CREATE INDEX IF NOT EXISTS idx_plan_assembly_sources_scope ON salops_plan_assembly_sources(tenant_id,run_id,source_kind,access_status);

CREATE TABLE IF NOT EXISTS salops_plan_assembly_questions (
  id TEXT PRIMARY KEY,
  tenant_id INTEGER NOT NULL,
  run_id TEXT NOT NULL,
  target_type TEXT NOT NULL,
  question TEXT NOT NULL,
  purpose TEXT NOT NULL,
  requested_method TEXT NOT NULL DEFAULT '',
  related_section_keys_json TEXT NOT NULL DEFAULT '[]',
  priority TEXT NOT NULL DEFAULT 'Normal',
  status TEXT NOT NULL DEFAULT 'Open',
  response_summary TEXT NOT NULL DEFAULT '',
  response_source_ref TEXT NOT NULL DEFAULT '',
  created_by TEXT NOT NULL,
  created_at TEXT NOT NULL,
  answered_by TEXT NOT NULL DEFAULT '',
  answered_at TEXT NOT NULL DEFAULT '',
  FOREIGN KEY (run_id) REFERENCES salops_plan_assembly_runs(id) ON DELETE CASCADE
);
CREATE INDEX IF NOT EXISTS idx_plan_assembly_questions_scope ON salops_plan_assembly_questions(tenant_id,run_id,status,target_type);

CREATE TABLE IF NOT EXISTS salops_plan_assembly_sections (
  id TEXT PRIMARY KEY,
  tenant_id INTEGER NOT NULL,
  run_id TEXT NOT NULL,
  section_key TEXT NOT NULL,
  section_version INTEGER NOT NULL,
  title TEXT NOT NULL,
  content TEXT NOT NULL,
  source_refs_json TEXT NOT NULL DEFAULT '[]',
  epistemic_items_json TEXT NOT NULL DEFAULT '[]',
  unsupported_assumptions_json TEXT NOT NULL DEFAULT '[]',
  known_unknowns_json TEXT NOT NULL DEFAULT '[]',
  dependencies_json TEXT NOT NULL DEFAULT '[]',
  alternate_capabilities_json TEXT NOT NULL DEFAULT '[]',
  capability_gaps_json TEXT NOT NULL DEFAULT '[]',
  change_rationale TEXT NOT NULL DEFAULT '',
  support_status TEXT NOT NULL,
  human_authority_required INTEGER NOT NULL DEFAULT 0,
  created_by TEXT NOT NULL,
  created_at TEXT NOT NULL,
  UNIQUE(tenant_id,run_id,section_key,section_version),
  FOREIGN KEY (run_id) REFERENCES salops_plan_assembly_runs(id) ON DELETE CASCADE
);
CREATE INDEX IF NOT EXISTS idx_plan_assembly_sections_scope ON salops_plan_assembly_sections(tenant_id,run_id,section_key,section_version);

CREATE TABLE IF NOT EXISTS salops_plan_revision_recommendations (
  id TEXT PRIMARY KEY,
  tenant_id INTEGER NOT NULL,
  run_id TEXT NOT NULL,
  approved_plan_id TEXT NOT NULL,
  approved_plan_version INTEGER NOT NULL,
  approved_plan_sha256 TEXT NOT NULL,
  material_change_summary TEXT NOT NULL,
  affected_sections_json TEXT NOT NULL DEFAULT '[]',
  supporting_source_refs_json TEXT NOT NULL DEFAULT '[]',
  recommendation TEXT NOT NULL,
  status TEXT NOT NULL DEFAULT 'Pending Salus Review',
  approved_plan_preserved INTEGER NOT NULL DEFAULT 1,
  creates_plan_version INTEGER NOT NULL DEFAULT 0,
  creates_release INTEGER NOT NULL DEFAULT 0,
  creates_authority INTEGER NOT NULL DEFAULT 0,
  creates_charge INTEGER NOT NULL DEFAULT 0,
  created_by TEXT NOT NULL,
  created_at TEXT NOT NULL,
  reviewed_by TEXT NOT NULL DEFAULT '',
  reviewed_at TEXT NOT NULL DEFAULT '',
  review_reason TEXT NOT NULL DEFAULT '',
  FOREIGN KEY (run_id) REFERENCES salops_plan_assembly_runs(id) ON DELETE CASCADE,
  FOREIGN KEY (approved_plan_id) REFERENCES salops_preparedness_plans(id) ON DELETE RESTRICT
);
CREATE INDEX IF NOT EXISTS idx_plan_revision_recommendations_scope ON salops_plan_revision_recommendations(tenant_id,status,approved_plan_id,created_at);

CREATE TABLE IF NOT EXISTS salops_plan_assembly_events (
  id TEXT PRIMARY KEY,
  tenant_id INTEGER NOT NULL,
  run_id TEXT NOT NULL,
  event_no INTEGER NOT NULL,
  event_type TEXT NOT NULL,
  reason TEXT NOT NULL,
  snapshot_json TEXT NOT NULL,
  changed_by TEXT NOT NULL,
  changed_by_role TEXT NOT NULL,
  created_at TEXT NOT NULL,
  UNIQUE(tenant_id,run_id,event_no),
  FOREIGN KEY (run_id) REFERENCES salops_plan_assembly_runs(id) ON DELETE CASCADE
);
CREATE INDEX IF NOT EXISTS idx_plan_assembly_events_scope ON salops_plan_assembly_events(tenant_id,run_id,event_no);
"""


JSON_COLUMNS = {
    "salops_plan_assembly_runs": (
        "portfolio_scope", "internal_record_refs", "library_refs",
        "authorized_external_sources", "source_exclusions", "research_questions",
        "known_unknowns", "assumptions_to_validate", "contradictions",
        "missing_authorities", "unresolved_dependencies", "affected_sections",
        "proposed_training_actions", "proposed_exercise_actions",
        "proposed_validation_actions",
    ),
    "salops_plan_assembly_sources": ("source_derived_statements",),
    "salops_plan_assembly_questions": ("related_section_keys",),
    "salops_plan_assembly_sections": (
        "source_refs", "epistemic_items", "unsupported_assumptions", "known_unknowns",
        "dependencies", "alternate_capabilities", "capability_gaps",
    ),
    "salops_plan_revision_recommendations": ("affected_sections", "supporting_source_refs"),
}
BACKUP_TABLES = (
    "salops_plan_assembly_runs", "salops_plan_assembly_sources",
    "salops_plan_assembly_questions", "salops_plan_assembly_sections",
    "salops_plan_revision_recommendations", "salops_plan_assembly_events",
)
RESTORE_ORDER = BACKUP_TABLES
DELETE_ORDER = tuple(reversed(RESTORE_ORDER))


def _json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), default=str)


def _loads(value: Any, fallback: Any) -> Any:
    if value in (None, ""):
        return fallback
    try:
        return json.loads(value)
    except (TypeError, json.JSONDecodeError):
        return fallback


def _key(prefix: str) -> str:
    return f"{prefix}_{uuid.uuid4().hex}"


def _digest(value: Any) -> str:
    return hashlib.sha256(_json(value).encode("utf-8")).hexdigest()


def _clean_list(value: list[str]) -> list[str]:
    return list(dict.fromkeys(str(item).strip() for item in value if str(item).strip()))


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class AssemblyCreate(StrictModel):
    base_plan_id: Optional[str] = None
    plan_title: str = Field(min_length=3, max_length=300)
    plan_type: str = Field(min_length=2, max_length=200)
    purpose: str = Field(min_length=3, max_length=12000)
    scope_statement: str = Field(min_length=3, max_length=12000)
    portfolio_scope: dict[str, Any] = Field(default_factory=dict)
    internal_record_refs: list[str] = Field(default_factory=list, max_length=300)
    library_refs: list[str] = Field(default_factory=list, max_length=300)
    authorized_external_sources: list[str] = Field(default_factory=list, max_length=300)
    source_exclusions: list[str] = Field(default_factory=list, max_length=300)
    research_questions: list[str] = Field(default_factory=list, max_length=300)
    known_unknowns: list[str] = Field(default_factory=list, max_length=300)
    assumptions_to_validate: list[str] = Field(default_factory=list, max_length=300)
    sensitivity: Literal["Standard", "Sensitive", "Highly Sensitive"] = "Standard"

    @field_validator(
        "internal_record_refs", "library_refs", "authorized_external_sources",
        "source_exclusions", "research_questions", "known_unknowns",
        "assumptions_to_validate",
    )
    @classmethod
    def clean_lists(cls, value: list[str]) -> list[str]:
        cleaned = _clean_list(value)
        if any(len(item) > 2000 for item in cleaned):
            raise ValueError("Planning entries may not exceed 2000 characters")
        return cleaned

    @model_validator(mode="after")
    def research_plan_required(self):
        if not (self.research_questions or self.internal_record_refs or self.library_refs or self.authorized_external_sources):
            raise ValueError("An assembly run requires at least one research question or authorized source stream")
        return self


class SourceStatement(StrictModel):
    state: Literal[
        "Reported Information", "Inference", "Analyst Judgment", "Hypothesis",
        "Unresolved Allegation", "Assumption", "Contradiction",
        "Information Gap", "Unknown",
    ]
    statement: str = Field(min_length=1, max_length=8000)


class SourceCreate(StrictModel):
    source_kind: Literal[
        "Protected Member Data", "Salus Library", "SalINTEL", "SalTHIRA", "SalOPS",
        "PROVE", "Incident / Exercise", "Uploaded Material", "External Research",
        "Approved Partner Return",
    ]
    access_status: Literal["Accessed", "Unavailable", "Human / Field Needed", "Partner Needed"]
    locator: str = Field(default="", max_length=4000)
    citation: str = Field(default="", max_length=8000)
    governed_material_id: Optional[int] = Field(default=None, gt=0)
    linked_record_type: str = Field(default="", max_length=200)
    linked_record_id: str = Field(default="", max_length=500)
    search_or_collection_method: str = Field(default="", max_length=4000)
    source_summary: str = Field(default="", max_length=12000)
    source_derived_statements: list[SourceStatement] = Field(default_factory=list, max_length=300)
    reliability: str = Field(default="Not Assessed", max_length=200)
    confidence: str = Field(default="Not Assessed", max_length=200)
    unavailable_reason: str = Field(default="", max_length=8000)

    @model_validator(mode="after")
    def truthful_access(self):
        if self.access_status == "Accessed":
            if not self.locator.strip() or not self.citation.strip() or not self.source_summary.strip() or not self.governed_material_id:
                raise ValueError("Accessed sources require locator, citation, summary, and a governed material record")
        else:
            if self.source_derived_statements:
                raise ValueError("Unavailable or human/partner-needed sources cannot assert source-derived statements")
            if not self.unavailable_reason.strip():
                raise ValueError("Unavailable or human/partner-needed sources require a truthful reason")
        return self


class CollectionQuestionCreate(StrictModel):
    target_type: Literal[
        "Protected Member", "Salus Investigator", "Interview / Call", "Site / Field",
        "Document Request", "Specialist", "Approved Partner",
    ]
    question: str = Field(min_length=3, max_length=8000)
    purpose: str = Field(min_length=3, max_length=8000)
    requested_method: str = Field(default="", max_length=1000)
    related_section_keys: list[str] = Field(default_factory=list, max_length=100)
    priority: Literal["Low", "Normal", "High", "Immediate"] = "Normal"


class CollectionAnswer(StrictModel):
    response_summary: str = Field(min_length=3, max_length=12000)
    response_source_ref: str = Field(min_length=1, max_length=1000)


class EpistemicItem(StrictModel):
    state: Literal[
        "Reported Information", "Inference", "Analyst Judgment", "Hypothesis",
        "Unresolved Allegation", "Assumption", "Contradiction",
        "Information Gap", "Unknown",
    ]
    statement: str = Field(min_length=1, max_length=8000)
    source_refs: list[str] = Field(default_factory=list, max_length=100)


class SectionCreate(StrictModel):
    section_key: str = Field(pattern=r"^[a-z0-9][a-z0-9_-]{1,79}$")
    title: str = Field(min_length=2, max_length=300)
    content: str = Field(min_length=3, max_length=60000)
    source_refs: list[str] = Field(default_factory=list, max_length=300)
    epistemic_items: list[EpistemicItem] = Field(default_factory=list, max_length=500)
    unsupported_assumptions: list[str] = Field(default_factory=list, max_length=200)
    known_unknowns: list[str] = Field(default_factory=list, max_length=200)
    dependencies: list[str] = Field(default_factory=list, max_length=200)
    alternate_capabilities: list[str] = Field(default_factory=list, max_length=200)
    capability_gaps: list[str] = Field(default_factory=list, max_length=200)
    change_rationale: str = Field(default="", max_length=12000)
    human_authority_required: bool = False

    @model_validator(mode="after")
    def distinguish_support(self):
        if not self.source_refs and not self.unsupported_assumptions and not self.known_unknowns:
            raise ValueError("A draft section requires source support or an explicit unsupported assumption/known unknown")
        return self


class RunAdvance(StrictModel):
    status: Literal["Collecting", "Drafting"]
    reason: str = Field(min_length=3, max_length=4000)


class RunSubmit(StrictModel):
    completion_statement: str = Field(min_length=3, max_length=12000)
    contradictions: list[str] = Field(default_factory=list, max_length=300)
    missing_authorities: list[str] = Field(default_factory=list, max_length=300)
    unresolved_dependencies: list[str] = Field(default_factory=list, max_length=300)
    affected_sections: list[str] = Field(default_factory=list, max_length=300)
    proposed_training_actions: list[str] = Field(default_factory=list, max_length=300)
    proposed_exercise_actions: list[str] = Field(default_factory=list, max_length=300)
    proposed_validation_actions: list[str] = Field(default_factory=list, max_length=300)
    change_rationale: str = Field(default="", max_length=12000)


class RunReview(StrictModel):
    decision: Literal["Human Reviewed", "Returned for Revision", "Rejected"]
    reason: str = Field(min_length=3, max_length=8000)


class RunQualify(StrictModel):
    reason: str = Field(min_length=3, max_length=8000)


class RevisionRecommendationCreate(StrictModel):
    material_change_summary: str = Field(min_length=3, max_length=12000)
    recommendation: str = Field(min_length=3, max_length=12000)


class RevisionRecommendationReview(StrictModel):
    decision: Literal["Accepted for Drafting", "Rejected"]
    reason: str = Field(min_length=3, max_length=8000)


def register_salops_plan_assembly(app, core: dict[str, Any]) -> None:
    db = core["db"]
    now = core["now"]
    actor = core["actor"]
    role = core["role"]
    tenant_id = core["tenant_id"]
    require = core["require"]
    require_salus = core["require_salus_component_authority"]
    require_sensitivity = core.get("require_sensitivity")
    audit = core["audit"]

    conn = db()
    conn.executescript(SCHEMA)
    conn.commit()
    conn.close()

    def salus_access(request: Request, permission: str = "read") -> None:
        require(request, permission)
        require_salus(request, "autonomous emergency-plan research and assembly")

    def decode(table: str, row: dict[str, Any]) -> dict[str, Any]:
        out = dict(row)
        for name in JSON_COLUMNS.get(table, ()):
            storage = f"{name}_json"
            out[name] = _loads(out.pop(storage, None), {} if name == "portfolio_scope" else [])
        for name in ("human_authority_required", "approved_plan_preserved", "creates_plan_version", "creates_release", "creates_authority", "creates_charge"):
            if name in out:
                out[name] = bool(out[name])
        return out

    def plan_row(conn, plan_id: str, request: Request) -> dict[str, Any]:
        row = conn.execute(
            "SELECT * FROM salops_preparedness_plans WHERE id=? AND tenant_id=?",
            (plan_id, tenant_id(request)),
        ).fetchone()
        if not row:
            raise HTTPException(404, "Preparedness plan not found")
        data = dict(row)
        if require_sensitivity:
            require_sensitivity(request, str(data.get("sensitivity") or "Standard"))
        return data

    def run_row(conn, run_id: str, request: Request) -> dict[str, Any]:
        row = conn.execute(
            "SELECT * FROM salops_plan_assembly_runs WHERE id=? AND tenant_id=?",
            (run_id, tenant_id(request)),
        ).fetchone()
        if not row:
            raise HTTPException(404, "Plan assembly run not found")
        data = dict(row)
        if require_sensitivity:
            require_sensitivity(request, str(data.get("sensitivity") or "Standard"))
        return data

    def event(conn, row: dict[str, Any], event_type: str, reason: str, request: Request) -> None:
        number = int(conn.execute(
            "SELECT COUNT(*) c FROM salops_plan_assembly_events WHERE tenant_id=? AND run_id=?",
            (row["tenant_id"], row["id"]),
        ).fetchone()["c"]) + 1
        conn.execute(
            "INSERT INTO salops_plan_assembly_events(id,tenant_id,run_id,event_no,event_type,reason,snapshot_json,changed_by,changed_by_role,created_at) VALUES(?,?,?,?,?,?,?,?,?,?)",
            (_key("pae"), row["tenant_id"], row["id"], number, event_type, reason,
             _json(row), actor(request), role(request), now()),
        )
        audit(conn, f"SALOPS_PLAN_ASSEMBLY_{event_type.upper().replace(' ', '_')}",
              "salops_plan_assembly", None, f"{row['id']}: {reason}"[:1000], actor(request))

    def source_ids(conn, run_id: str, request: Request) -> set[str]:
        return {str(row["id"]) for row in conn.execute(
            "SELECT id FROM salops_plan_assembly_sources WHERE tenant_id=? AND run_id=?",
            (tenant_id(request), run_id),
        )}

    def source_support(conn, run_id: str, refs: list[str], request: Request) -> None:
        missing = sorted(set(refs) - source_ids(conn, run_id, request))
        if missing:
            raise HTTPException(422, f"Unknown plan-assembly source references: {', '.join(missing)}")

    def run_bundle(conn, row: dict[str, Any], request: Request) -> dict[str, Any]:
        run_id = row["id"]
        sources = [decode("salops_plan_assembly_sources", dict(item)) for item in conn.execute(
            "SELECT * FROM salops_plan_assembly_sources WHERE tenant_id=? AND run_id=? ORDER BY created_at,id",
            (tenant_id(request), run_id),
        )]
        questions = [decode("salops_plan_assembly_questions", dict(item)) for item in conn.execute(
            "SELECT * FROM salops_plan_assembly_questions WHERE tenant_id=? AND run_id=? ORDER BY created_at,id",
            (tenant_id(request), run_id),
        )]
        sections = [decode("salops_plan_assembly_sections", dict(item)) for item in conn.execute(
            "SELECT * FROM salops_plan_assembly_sections WHERE tenant_id=? AND run_id=? ORDER BY section_key,section_version",
            (tenant_id(request), run_id),
        )]
        recommendations = [decode("salops_plan_revision_recommendations", dict(item)) for item in conn.execute(
            "SELECT * FROM salops_plan_revision_recommendations WHERE tenant_id=? AND run_id=? ORDER BY created_at,id",
            (tenant_id(request), run_id),
        )]
        events = [dict(item) for item in conn.execute(
            "SELECT event_no,event_type,reason,changed_by,changed_by_role,created_at FROM salops_plan_assembly_events WHERE tenant_id=? AND run_id=? ORDER BY event_no",
            (tenant_id(request), run_id),
        )]
        return {"run": decode("salops_plan_assembly_runs", row), "sources": sources,
                "questions": questions, "sections": sections,
                "revision_recommendations": recommendations, "events": events}

    @app.get("/api/salops/preparedness/plan-assembly/catalog")
    def catalog(request: Request):
        salus_access(request)
        return {
            "capability": "Autonomous Emergency-Plan Research & Assembly",
            "source_kinds": list(SOURCE_KINDS), "access_states": list(ACCESS_STATES),
            "epistemic_states": list(EPISTEMIC_STATES), "question_targets": list(QUESTION_TARGETS),
            "automated_draft_epistemic_states": [state for state in EPISTEMIC_STATES if state != "Verified Fact"],
            "workflow": list(RUN_STATES),
            "authority": {
                "chat_may": ["Inspect", "Research", "Reconcile", "Draft", "Compare", "Recommend"],
                "human_controls": ["Legal authority", "Organizational policy", "Emergency command authority",
                                   "Evacuation authority", "Use-of-force policy", "Contractual commitments",
                                   "Commercial treatment", "Approval", "Release"],
                "automatic_release": False, "automatic_plan_replacement": False,
                "automatic_charge": False, "protected_member_disclosure": False,
            },
        }

    @app.get("/api/salops/preparedness/plan-assembly")
    def list_runs(request: Request, status: str = ""):
        salus_access(request)
        clauses = ["tenant_id=?"]
        params: list[Any] = [tenant_id(request)]
        if status:
            if status not in RUN_STATES:
                raise HTTPException(422, "Unknown plan-assembly status")
            clauses.append("status=?")
            params.append(status)
        conn = db()
        rows = [decode("salops_plan_assembly_runs", dict(row)) for row in conn.execute(
            "SELECT * FROM salops_plan_assembly_runs WHERE " + " AND ".join(clauses) + " ORDER BY created_at DESC,id",
            tuple(params),
        )]
        conn.close()
        return rows

    @app.post("/api/salops/preparedness/plan-assembly")
    def create_run(payload: AssemblyCreate, request: Request):
        salus_access(request, "write")
        conn = db()
        try:
            base: dict[str, Any] = {}
            if payload.base_plan_id:
                base = plan_row(conn, payload.base_plan_id, request)
            snapshot = base if base else {}
            stamp = now()
            who = actor(request)
            run_id = _key("par")
            data = payload.model_dump()
            values = (
                run_id, tenant_id(request), data["base_plan_id"], int(base.get("version") or 0),
                str(base.get("status") or ""), _json(snapshot), _digest(snapshot) if snapshot else "",
                "Revision" if base else "New Plan", data["plan_title"], data["plan_type"],
                data["purpose"], data["scope_statement"], _json(data["portfolio_scope"]),
                _json(data["internal_record_refs"]), _json(data["library_refs"]),
                _json(data["authorized_external_sources"]), _json(data["source_exclusions"]),
                _json(data["research_questions"]), _json(data["known_unknowns"]),
                _json(data["assumptions_to_validate"]), data["sensitivity"],
                "Research Planning", 1, who, stamp, who, stamp,
            )
            conn.execute(
                """INSERT INTO salops_plan_assembly_runs(
                id,tenant_id,base_plan_id,base_plan_version,base_plan_status,base_plan_snapshot_json,
                base_plan_sha256,assembly_mode,plan_title,plan_type,purpose,scope_statement,
                portfolio_scope_json,internal_record_refs_json,library_refs_json,
                authorized_external_sources_json,source_exclusions_json,research_questions_json,
                known_unknowns_json,assumptions_to_validate_json,sensitivity,status,current_iteration,
                created_by,created_at,updated_by,updated_at)
                VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                values,
            )
            row = dict(conn.execute("SELECT * FROM salops_plan_assembly_runs WHERE id=?", (run_id,)).fetchone())
            event(conn, row, "Create", "Governed plan research and collection plan created; no plan authority, approval, release, or charge was created.", request)
            conn.commit()
            return decode("salops_plan_assembly_runs", row)
        finally:
            conn.close()

    @app.get("/api/salops/preparedness/plan-assembly/{run_id}")
    def get_run(run_id: str, request: Request):
        salus_access(request)
        conn = db()
        try:
            return run_bundle(conn, run_row(conn, run_id, request), request)
        finally:
            conn.close()

    @app.post("/api/salops/preparedness/plan-assembly/{run_id}/sources")
    def add_source(run_id: str, payload: SourceCreate, request: Request):
        salus_access(request, "write")
        conn = db()
        try:
            run = run_row(conn, run_id, request)
            if run["status"] not in ("Research Planning", "Collecting", "Drafting", "Returned for Revision"):
                raise HTTPException(409, "Sources cannot be added after submission unless the run is returned for revision")
            data = payload.model_dump()
            source_id = _key("pas")
            stamp = now()
            accessed = data["access_status"] == "Accessed"
            if accessed:
                material = conn.execute(
                    "SELECT * FROM materials WHERE id=? AND tenant_id=?",
                    (data["governed_material_id"], tenant_id(request)),
                ).fetchone()
                if not material:
                    raise HTTPException(409, "Accessed source must use an existing governed material record in this tenant")
                if require_sensitivity:
                    require_sensitivity(request, material["sensitivity"])
            conn.execute(
                """INSERT INTO salops_plan_assembly_sources(
                id,tenant_id,run_id,source_kind,access_status,locator,citation,governed_material_id,
                linked_record_type,linked_record_id,search_or_collection_method,source_summary,
                source_derived_statements_json,reliability,confidence,unavailable_reason,accessed_by,
                accessed_at,created_by,created_at) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                (source_id, tenant_id(request), run_id, data["source_kind"], data["access_status"],
                 data["locator"], data["citation"], data["governed_material_id"],
                 data["linked_record_type"], data["linked_record_id"],
                 data["search_or_collection_method"], data["source_summary"],
                 _json([item.model_dump() for item in payload.source_derived_statements]),
                 data["reliability"], data["confidence"], data["unavailable_reason"],
                 actor(request) if accessed else "", stamp if accessed else "", actor(request), stamp),
            )
            source = dict(conn.execute("SELECT * FROM salops_plan_assembly_sources WHERE id=?", (source_id,)).fetchone())
            event(conn, run, "Source Recorded", f"{source_id}: {data['source_kind']} recorded as {data['access_status']}; unavailable sources yielded no facts.", request)
            conn.commit()
            return decode("salops_plan_assembly_sources", source)
        finally:
            conn.close()

    @app.post("/api/salops/preparedness/plan-assembly/{run_id}/questions")
    def add_question(run_id: str, payload: CollectionQuestionCreate, request: Request):
        salus_access(request, "write")
        conn = db()
        try:
            run = run_row(conn, run_id, request)
            if run["status"] in ("Qualified", "Rejected"):
                raise HTTPException(409, "Collection requirements cannot be added to a terminal assembly run")
            data = payload.model_dump()
            question_id = _key("paq")
            stamp = now()
            conn.execute(
                """INSERT INTO salops_plan_assembly_questions(
                id,tenant_id,run_id,target_type,question,purpose,requested_method,
                related_section_keys_json,priority,status,created_by,created_at)
                VALUES(?,?,?,?,?,?,?,?,?,?,?,?)""",
                (question_id, tenant_id(request), run_id, data["target_type"], data["question"],
                 data["purpose"], data["requested_method"], _json(data["related_section_keys"]),
                 data["priority"], "Open", actor(request), stamp),
            )
            question = dict(conn.execute("SELECT * FROM salops_plan_assembly_questions WHERE id=?", (question_id,)).fetchone())
            event(conn, run, "Collection Requirement", f"{question_id}: missing information assigned to {data['target_type']}; no answer was inferred.", request)
            conn.commit()
            return decode("salops_plan_assembly_questions", question)
        finally:
            conn.close()

    @app.post("/api/salops/preparedness/plan-assembly/{run_id}/questions/{question_id}/answer")
    def answer_question(run_id: str, question_id: str, payload: CollectionAnswer, request: Request):
        salus_access(request, "write")
        conn = db()
        try:
            run = run_row(conn, run_id, request)
            row = conn.execute(
                "SELECT * FROM salops_plan_assembly_questions WHERE id=? AND run_id=? AND tenant_id=?",
                (question_id, run_id, tenant_id(request)),
            ).fetchone()
            if not row:
                raise HTTPException(404, "Plan collection requirement not found")
            if row["status"] != "Open":
                raise HTTPException(409, "Collection requirement already answered")
            stamp = now()
            conn.execute(
                "UPDATE salops_plan_assembly_questions SET status='Answered',response_summary=?,response_source_ref=?,answered_by=?,answered_at=? WHERE id=? AND tenant_id=?",
                (payload.response_summary, payload.response_source_ref, actor(request), stamp,
                 question_id, tenant_id(request)),
            )
            updated = dict(conn.execute("SELECT * FROM salops_plan_assembly_questions WHERE id=?", (question_id,)).fetchone())
            event(conn, run, "Collection Answer", f"{question_id}: response linked to governed source {payload.response_source_ref}.", request)
            conn.commit()
            return decode("salops_plan_assembly_questions", updated)
        finally:
            conn.close()

    @app.post("/api/salops/preparedness/plan-assembly/{run_id}/advance")
    def advance_run(run_id: str, payload: RunAdvance, request: Request):
        salus_access(request, "write")
        conn = db()
        try:
            run = run_row(conn, run_id, request)
            current = run["status"]
            if current == "Returned for Revision" and payload.status == "Drafting":
                pass
            elif {"Research Planning": "Collecting", "Collecting": "Drafting"}.get(current) != payload.status:
                raise HTTPException(409, f"Plan assembly cannot move from {current} to {payload.status}")
            if payload.status == "Drafting":
                count = int(conn.execute(
                    "SELECT COUNT(*) c FROM salops_plan_assembly_sources WHERE tenant_id=? AND run_id=?",
                    (tenant_id(request), run_id),
                ).fetchone()["c"])
                if not count:
                    raise HTTPException(409, "Drafting requires at least one truthful source-access or unavailability record")
            stamp = now()
            conn.execute(
                "UPDATE salops_plan_assembly_runs SET status=?,current_iteration=current_iteration+1,updated_by=?,updated_at=? WHERE id=? AND tenant_id=?",
                (payload.status, actor(request), stamp, run_id, tenant_id(request)),
            )
            updated = dict(conn.execute("SELECT * FROM salops_plan_assembly_runs WHERE id=?", (run_id,)).fetchone())
            event(conn, updated, f"Advance {payload.status}", payload.reason, request)
            conn.commit()
            return decode("salops_plan_assembly_runs", updated)
        finally:
            conn.close()

    @app.post("/api/salops/preparedness/plan-assembly/{run_id}/sections")
    def add_section(run_id: str, payload: SectionCreate, request: Request):
        salus_access(request, "write")
        conn = db()
        try:
            run = run_row(conn, run_id, request)
            if run["status"] not in ("Drafting", "Returned for Revision"):
                raise HTTPException(409, "Draft sections may be added only during drafting or returned revision")
            data = payload.model_dump()
            all_refs = list(data["source_refs"])
            for item in data["epistemic_items"]:
                all_refs.extend(item["source_refs"])
            source_support(conn, run_id, all_refs, request)
            version = int(conn.execute(
                "SELECT COUNT(*) c FROM salops_plan_assembly_sections WHERE tenant_id=? AND run_id=? AND section_key=?",
                (tenant_id(request), run_id, data["section_key"]),
            ).fetchone()["c"]) + 1
            support_status = "Source Supported" if data["source_refs"] else "Needs Corroboration"
            if data["human_authority_required"]:
                support_status = "Needs Human Authority"
            section_id = _key("pasec")
            stamp = now()
            conn.execute(
                """INSERT INTO salops_plan_assembly_sections(
                id,tenant_id,run_id,section_key,section_version,title,content,source_refs_json,
                epistemic_items_json,unsupported_assumptions_json,known_unknowns_json,dependencies_json,
                alternate_capabilities_json,capability_gaps_json,change_rationale,support_status,
                human_authority_required,created_by,created_at)
                VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                (section_id, tenant_id(request), run_id, data["section_key"], version,
                 data["title"], data["content"], _json(data["source_refs"]),
                 _json(data["epistemic_items"]), _json(data["unsupported_assumptions"]),
                 _json(data["known_unknowns"]), _json(data["dependencies"]),
                 _json(data["alternate_capabilities"]), _json(data["capability_gaps"]),
                 data["change_rationale"], support_status,
                 1 if data["human_authority_required"] else 0, actor(request), stamp),
            )
            section = dict(conn.execute("SELECT * FROM salops_plan_assembly_sections WHERE id=?", (section_id,)).fetchone())
            event(conn, run, "Draft Section", f"{data['section_key']} v{version}: {support_status}; source distinctions preserved.", request)
            conn.commit()
            return decode("salops_plan_assembly_sections", section)
        finally:
            conn.close()

    @app.post("/api/salops/preparedness/plan-assembly/{run_id}/submit")
    def submit_run(run_id: str, payload: RunSubmit, request: Request):
        salus_access(request, "write")
        conn = db()
        try:
            run = run_row(conn, run_id, request)
            if run["status"] not in ("Drafting", "Returned for Revision"):
                raise HTTPException(409, "Only a drafted or returned run may be submitted")
            section_count = int(conn.execute(
                "SELECT COUNT(*) c FROM salops_plan_assembly_sections WHERE tenant_id=? AND run_id=?",
                (tenant_id(request), run_id),
            ).fetchone()["c"])
            source_count = int(conn.execute(
                "SELECT COUNT(*) c FROM salops_plan_assembly_sources WHERE tenant_id=? AND run_id=?",
                (tenant_id(request), run_id),
            ).fetchone()["c"])
            if not section_count or not source_count:
                raise HTTPException(409, "Submission requires at least one source record and one structured draft section")
            data = payload.model_dump()
            stamp = now()
            bundle_for_hash = {
                "run": decode("salops_plan_assembly_runs", run),
                "sources": [dict(item) for item in conn.execute(
                    "SELECT * FROM salops_plan_assembly_sources WHERE tenant_id=? AND run_id=? ORDER BY id",
                    (tenant_id(request), run_id),
                )],
                "sections": [dict(item) for item in conn.execute(
                    "SELECT * FROM salops_plan_assembly_sections WHERE tenant_id=? AND run_id=? ORDER BY section_key,section_version",
                    (tenant_id(request), run_id),
                )],
                "submission": data,
            }
            sets = {
                "contradictions_json": _json(data["contradictions"]),
                "missing_authorities_json": _json(data["missing_authorities"]),
                "unresolved_dependencies_json": _json(data["unresolved_dependencies"]),
                "affected_sections_json": _json(data["affected_sections"]),
                "proposed_training_actions_json": _json(data["proposed_training_actions"]),
                "proposed_exercise_actions_json": _json(data["proposed_exercise_actions"]),
                "proposed_validation_actions_json": _json(data["proposed_validation_actions"]),
                "completion_statement": data["completion_statement"],
                "change_rationale": data["change_rationale"],
                "status": "Submitted for Human Review", "content_sha256": _digest(bundle_for_hash),
                "submitted_by": actor(request), "submitted_at": stamp,
                "updated_by": actor(request), "updated_at": stamp,
            }
            conn.execute(
                "UPDATE salops_plan_assembly_runs SET " + ",".join(f"{name}=?" for name in sets) + " WHERE id=? AND tenant_id=?",
                tuple(sets.values()) + (run_id, tenant_id(request)),
            )
            updated = dict(conn.execute("SELECT * FROM salops_plan_assembly_runs WHERE id=?", (run_id,)).fetchone())
            event(conn, updated, "Submit for Human Review", "Proposed plan draft submitted; no policy, authority, plan approval, release, disclosure, or charge was created.", request)
            conn.commit()
            return decode("salops_plan_assembly_runs", updated)
        finally:
            conn.close()

    @app.post("/api/salops/preparedness/plan-assembly/{run_id}/review")
    def review_run(run_id: str, payload: RunReview, request: Request):
        salus_access(request, "write")
        conn = db()
        try:
            run = run_row(conn, run_id, request)
            if run["status"] != "Submitted for Human Review":
                raise HTTPException(409, "Human review requires a submitted plan assembly run")
            if role(request) not in ("System Administrator", "Assessment Director", "Program Owner", "Lead Assessor"):
                raise HTTPException(403, "This role cannot record the plan-assembly human review gate")
            stamp = now()
            conn.execute(
                "UPDATE salops_plan_assembly_runs SET status=?,reviewed_by=?,reviewed_at=?,review_reason=?,updated_by=?,updated_at=? WHERE id=? AND tenant_id=?",
                (payload.decision, actor(request), stamp, payload.reason, actor(request), stamp,
                 run_id, tenant_id(request)),
            )
            updated = dict(conn.execute("SELECT * FROM salops_plan_assembly_runs WHERE id=?", (run_id,)).fetchone())
            event(conn, updated, f"Review {payload.decision}", payload.reason, request)
            conn.commit()
            return decode("salops_plan_assembly_runs", updated)
        finally:
            conn.close()

    @app.post("/api/salops/preparedness/plan-assembly/{run_id}/qualify")
    def qualify_run(run_id: str, payload: RunQualify, request: Request):
        salus_access(request, "write")
        conn = db()
        try:
            run = run_row(conn, run_id, request)
            if run["status"] != "Human Reviewed":
                raise HTTPException(409, "Qualification requires a separate completed human review")
            if role(request) not in ("System Administrator", "Assessment Director", "Program Owner"):
                raise HTTPException(403, "This role cannot qualify a plan-assembly product")
            stamp = now()
            conn.execute(
                "UPDATE salops_plan_assembly_runs SET status='Qualified',qualified_by=?,qualified_at=?,qualification_reason=?,updated_by=?,updated_at=? WHERE id=? AND tenant_id=?",
                (actor(request), stamp, payload.reason, actor(request), stamp, run_id, tenant_id(request)),
            )
            updated = dict(conn.execute("SELECT * FROM salops_plan_assembly_runs WHERE id=?", (run_id,)).fetchone())
            event(conn, updated, "Qualified", "Human-qualified planning product; approved plan, release, authority, disclosure, and commercial state remain unchanged.", request)
            conn.commit()
            return decode("salops_plan_assembly_runs", updated)
        finally:
            conn.close()

    @app.post("/api/salops/preparedness/plan-assembly/{run_id}/revision-recommendations")
    def create_revision_recommendation(run_id: str, payload: RevisionRecommendationCreate, request: Request):
        salus_access(request, "write")
        conn = db()
        try:
            run = run_row(conn, run_id, request)
            if run["status"] != "Qualified" or not run.get("base_plan_id"):
                raise HTTPException(409, "A revision recommendation requires a qualified run linked to a governed baseline plan")
            if run["base_plan_status"] != "Approved":
                raise HTTPException(409, "Revision impact must be based on an approved plan version")
            current = plan_row(conn, run["base_plan_id"], request)
            if int(current["version"]) != int(run["base_plan_version"]) or current["status"] != "Approved" or _digest(current) != run["base_plan_sha256"]:
                raise HTTPException(409, "The approved baseline changed; start a new assembly run before recommending revision")
            affected = _loads(run["affected_sections_json"], [])
            if not affected:
                raise HTTPException(409, "A revision recommendation requires identified affected sections")
            supporting = [str(row["id"]) for row in conn.execute(
                "SELECT id FROM salops_plan_assembly_sources WHERE tenant_id=? AND run_id=? AND access_status='Accessed' ORDER BY id",
                (tenant_id(request), run_id),
            )]
            if not supporting:
                raise HTTPException(409, "A revision recommendation requires at least one actually accessed supporting source")
            recommendation_id = _key("parr")
            stamp = now()
            conn.execute(
                """INSERT INTO salops_plan_revision_recommendations(
                id,tenant_id,run_id,approved_plan_id,approved_plan_version,approved_plan_sha256,
                material_change_summary,affected_sections_json,supporting_source_refs_json,
                recommendation,status,approved_plan_preserved,creates_plan_version,creates_release,
                creates_authority,creates_charge,created_by,created_at)
                VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                (recommendation_id, tenant_id(request), run_id, run["base_plan_id"],
                 run["base_plan_version"], run["base_plan_sha256"],
                 payload.material_change_summary, _json(affected), _json(supporting),
                 payload.recommendation, "Pending Salus Review", 1, 0, 0, 0, 0,
                 actor(request), stamp),
            )
            recommendation = dict(conn.execute("SELECT * FROM salops_plan_revision_recommendations WHERE id=?", (recommendation_id,)).fetchone())
            event(conn, run, "Revision Recommended", f"{recommendation_id}: approved plan v{run['base_plan_version']} preserved unchanged pending Salus review.", request)
            conn.commit()
            return decode("salops_plan_revision_recommendations", recommendation)
        finally:
            conn.close()

    @app.post("/api/salops/preparedness/plan-assembly/revision-recommendations/{recommendation_id}/review")
    def review_revision_recommendation(recommendation_id: str, payload: RevisionRecommendationReview, request: Request):
        salus_access(request, "write")
        conn = db()
        try:
            row = conn.execute(
                "SELECT * FROM salops_plan_revision_recommendations WHERE id=? AND tenant_id=?",
                (recommendation_id, tenant_id(request)),
            ).fetchone()
            if not row:
                raise HTTPException(404, "Plan revision recommendation not found")
            if row["status"] != "Pending Salus Review":
                raise HTTPException(409, "Plan revision recommendation already reviewed")
            if role(request) not in ("System Administrator", "Assessment Director", "Program Owner"):
                raise HTTPException(403, "This role cannot review plan revision recommendations")
            stamp = now()
            conn.execute(
                "UPDATE salops_plan_revision_recommendations SET status=?,reviewed_by=?,reviewed_at=?,review_reason=? WHERE id=? AND tenant_id=?",
                (payload.decision, actor(request), stamp, payload.reason,
                 recommendation_id, tenant_id(request)),
            )
            updated = dict(conn.execute("SELECT * FROM salops_plan_revision_recommendations WHERE id=?", (recommendation_id,)).fetchone())
            run = run_row(conn, updated["run_id"], request)
            event(conn, run, f"Revision Recommendation {payload.decision}",
                  f"{recommendation_id}: {payload.reason}; approved plan remains unchanged and no new version or release was created.", request)
            conn.commit()
            return decode("salops_plan_revision_recommendations", updated)
        finally:
            conn.close()

    original_collect = core.get("collect_tenant_records")
    original_validate = core.get("validate_records")
    original_replace = core.get("replace_tenant_records")
    if original_collect and original_validate and original_replace:
        def extended_collect(conn, tid: int):
            records = original_collect(conn, tid)
            for table in BACKUP_TABLES:
                records[table] = [dict(row) for row in conn.execute(
                    f"SELECT * FROM {table} WHERE tenant_id=? ORDER BY id", (tid,)
                )]
            return records

        def assembly_validate(records: dict, tid: int) -> list[str]:
            errors: list[str] = []
            ids = {table: {str(row.get("id")) for row in records.get(table, []) if row.get("id")} for table in BACKUP_TABLES}
            run_ids = ids["salops_plan_assembly_runs"]
            plan_ids = {str(row.get("id")) for row in records.get("salops_preparedness_plans", []) if row.get("id")}
            source_ids_in_backup = ids["salops_plan_assembly_sources"]
            for table in BACKUP_TABLES:
                for row in records.get(table, []):
                    if int(row.get("tenant_id", -1)) != int(tid):
                        errors.append(f"{table} record {row.get('id')} crosses the tenant boundary")
            for row in records.get("salops_plan_assembly_runs", []):
                if row.get("base_plan_id") and str(row["base_plan_id"]) not in plan_ids:
                    errors.append(f"plan assembly run {row.get('id')} has invalid base_plan_id")
            for table in BACKUP_TABLES[1:]:
                for row in records.get(table, []):
                    if row.get("run_id") and str(row["run_id"]) not in run_ids:
                        errors.append(f"{table} record {row.get('id')} has invalid run_id")
            for row in records.get("salops_plan_assembly_sections", []):
                refs = _loads(row.get("source_refs_json"), [])
                if any(str(ref) not in source_ids_in_backup for ref in refs):
                    errors.append(f"plan assembly section {row.get('id')} has invalid source reference")
            for row in records.get("salops_plan_revision_recommendations", []):
                if str(row.get("approved_plan_id")) not in plan_ids:
                    errors.append(f"plan revision recommendation {row.get('id')} has invalid approved_plan_id")
            return errors

        def extended_validate(records: dict, tid: Optional[int] = None):
            errors = list(original_validate(records, tid))
            if tid is not None:
                errors.extend(assembly_validate(records, int(tid)))
            return errors

        def insert_row(conn, table: str, row: dict[str, Any]) -> None:
            allowed = {item["name"] for item in conn.execute(f"PRAGMA table_info({table})")}
            data = {key: value for key, value in row.items() if key in allowed}
            if data:
                conn.execute(
                    f"INSERT INTO {table}({','.join(data)}) VALUES({','.join('?' * len(data))})",
                    tuple(data.values()),
                )

        def extended_replace(conn, tid: int, records: dict):
            errors = list(original_validate(records, tid)) + assembly_validate(records, tid)
            if errors:
                raise ValueError("; ".join(errors))
            for table in DELETE_ORDER:
                conn.execute(f"DELETE FROM {table} WHERE tenant_id=?", (tid,))
            original_replace(conn, tid, records)
            for table in RESTORE_ORDER:
                for row in records.get(table, []):
                    insert_row(conn, table, row)

        core["collect_tenant_records"] = extended_collect
        core["validate_records"] = extended_validate
        core["replace_tenant_records"] = extended_replace
