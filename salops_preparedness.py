"""Governed SalOPS preparedness, planning, training, exercise, AAR, and validation capability.

Issue #162 development capability. The module is registered after the core SalCAPA
application so it can reuse authoritative tenancy, role, sensitivity, audit, and
backup helpers without creating a parallel security model.
"""
from __future__ import annotations

import json
import uuid
from typing import Any, Literal, Optional

from fastapi import HTTPException, Request
from pydantic import BaseModel, ConfigDict, Field, field_validator

MISSION_LENSES = ("Prevention", "Protection", "Mitigation", "Response", "Recovery")
EXERCISE_TYPES = (
    "Orientation / Seminar", "Workshop", "Drill", "Tabletop Exercise",
    "Functional Exercise", "Full-Scale Exercise", "Custom",
)
PLAN_STATUSES = ("Draft", "Reviewed", "Approved", "Retired")
EXERCISE_STATUSES = ("Planned", "Reviewed", "Approved", "In Progress", "Completed", "Evaluated", "Closed", "Cancelled")
TRAINING_STATUSES = ("Scheduled", "In Progress", "Completed", "Cancelled")
CORRECTIVE_STATUSES = ("Open", "In Progress", "Implemented", "Awaiting Validation", "Validated", "Closed", "Deferred")
AAR_STATUSES = ("Draft", "Reviewed", "Approved", "Released")
EPISTEMIC_STATES = (
    "Verified Fact", "Reported Information", "Inference", "Judgment", "Hypothesis",
    "Unresolved Allegation", "Assumption", "Contradiction", "Information Gap", "Unknown",
)
COMMERCIAL_TREATMENTS = (
    "Not Determined", "Membership Included", "Discounted", "Preferred Rate",
    "Credit Eligible", "Separately Quoted", "Pass-Through", "Custom",
)
SENSITIVITY_LEVELS = ("Standard", "Sensitive", "Highly Sensitive")

SCHEMA = r"""
CREATE TABLE IF NOT EXISTS salops_preparedness_plans (
  id TEXT PRIMARY KEY,
  tenant_id INTEGER NOT NULL,
  assessment_id INTEGER,
  title TEXT NOT NULL,
  plan_type TEXT NOT NULL,
  purpose TEXT NOT NULL DEFAULT '',
  scope_statement TEXT NOT NULL,
  portfolio_scope_json TEXT NOT NULL DEFAULT '{}',
  mission_lenses_json TEXT NOT NULL DEFAULT '[]',
  authorities_references TEXT NOT NULL DEFAULT '',
  assumptions TEXT NOT NULL DEFAULT '',
  roles_responsibilities TEXT NOT NULL DEFAULT '',
  concept_of_operations TEXT NOT NULL DEFAULT '',
  activation_criteria TEXT NOT NULL DEFAULT '',
  command_coordination TEXT NOT NULL DEFAULT '',
  communications TEXT NOT NULL DEFAULT '',
  resource_requirements TEXT NOT NULL DEFAULT '',
  dependencies TEXT NOT NULL DEFAULT '',
  alternate_capability TEXT NOT NULL DEFAULT '',
  checklists_job_aids TEXT NOT NULL DEFAULT '',
  annexes_appendices TEXT NOT NULL DEFAULT '',
  training_requirements TEXT NOT NULL DEFAULT '',
  exercise_validation_requirements TEXT NOT NULL DEFAULT '',
  evidence_refs_json TEXT NOT NULL DEFAULT '[]',
  known_unknowns TEXT NOT NULL DEFAULT '',
  salintel_refs_json TEXT NOT NULL DEFAULT '[]',
  salthira_refs_json TEXT NOT NULL DEFAULT '[]',
  salops_refs_json TEXT NOT NULL DEFAULT '[]',
  sensitivity TEXT NOT NULL DEFAULT 'Standard',
  owner TEXT NOT NULL DEFAULT '',
  approver TEXT NOT NULL DEFAULT '',
  effective_date TEXT NOT NULL DEFAULT '',
  review_date TEXT NOT NULL DEFAULT '',
  expiration_date TEXT NOT NULL DEFAULT '',
  status TEXT NOT NULL DEFAULT 'Draft',
  member_adoption_status TEXT NOT NULL DEFAULT 'Not Recorded',
  member_adoption_reason TEXT NOT NULL DEFAULT '',
  member_adopted_by TEXT NOT NULL DEFAULT '',
  member_adopted_at TEXT NOT NULL DEFAULT '',
  commercial_treatment TEXT NOT NULL DEFAULT 'Not Determined',
  commercial_reference TEXT NOT NULL DEFAULT '',
  membership_entitlement_ref TEXT NOT NULL DEFAULT '',
  version INTEGER NOT NULL DEFAULT 1,
  created_by TEXT NOT NULL,
  created_at TEXT NOT NULL,
  updated_by TEXT NOT NULL,
  updated_at TEXT NOT NULL,
  reviewed_by TEXT NOT NULL DEFAULT '',
  reviewed_at TEXT NOT NULL DEFAULT '',
  approved_by TEXT NOT NULL DEFAULT '',
  approved_at TEXT NOT NULL DEFAULT ''
);
CREATE INDEX IF NOT EXISTS idx_salops_prep_plans_scope ON salops_preparedness_plans(tenant_id,status,assessment_id,review_date);

CREATE TABLE IF NOT EXISTS salops_preparedness_training (
  id TEXT PRIMARY KEY,
  tenant_id INTEGER NOT NULL,
  assessment_id INTEGER,
  plan_id TEXT,
  title TEXT NOT NULL,
  objective TEXT NOT NULL,
  capability_ref TEXT NOT NULL DEFAULT '',
  role_addressed TEXT NOT NULL DEFAULT '',
  audience TEXT NOT NULL DEFAULT '',
  participants_json TEXT NOT NULL DEFAULT '[]',
  prerequisites TEXT NOT NULL DEFAULT '',
  delivery_type TEXT NOT NULL DEFAULT '',
  materials_json TEXT NOT NULL DEFAULT '[]',
  instructor TEXT NOT NULL DEFAULT '',
  scheduled_at TEXT NOT NULL DEFAULT '',
  completed_at TEXT NOT NULL DEFAULT '',
  performance_check TEXT NOT NULL DEFAULT '',
  observations TEXT NOT NULL DEFAULT '',
  follow_up_requirements TEXT NOT NULL DEFAULT '',
  evidence_refs_json TEXT NOT NULL DEFAULT '[]',
  recurrence_schedule TEXT NOT NULL DEFAULT '',
  mission_lenses_json TEXT NOT NULL DEFAULT '[]',
  status TEXT NOT NULL DEFAULT 'Scheduled',
  member_release_status TEXT NOT NULL DEFAULT 'Internal',
  released_by TEXT NOT NULL DEFAULT '',
  released_at TEXT NOT NULL DEFAULT '',
  commercial_treatment TEXT NOT NULL DEFAULT 'Not Determined',
  commercial_reference TEXT NOT NULL DEFAULT '',
  membership_entitlement_ref TEXT NOT NULL DEFAULT '',
  version INTEGER NOT NULL DEFAULT 1,
  created_by TEXT NOT NULL,
  created_at TEXT NOT NULL,
  updated_by TEXT NOT NULL,
  updated_at TEXT NOT NULL,
  FOREIGN KEY (plan_id) REFERENCES salops_preparedness_plans(id) ON DELETE SET NULL
);
CREATE INDEX IF NOT EXISTS idx_salops_prep_training_scope ON salops_preparedness_training(tenant_id,status,scheduled_at,assessment_id);

CREATE TABLE IF NOT EXISTS salops_preparedness_exercises (
  id TEXT PRIMARY KEY,
  tenant_id INTEGER NOT NULL,
  assessment_id INTEGER,
  plan_id TEXT,
  title TEXT NOT NULL,
  exercise_type TEXT NOT NULL,
  purpose TEXT NOT NULL DEFAULT '',
  objectives_json TEXT NOT NULL DEFAULT '[]',
  capabilities_json TEXT NOT NULL DEFAULT '[]',
  scope_statement TEXT NOT NULL,
  portfolio_scope_json TEXT NOT NULL DEFAULT '{}',
  mission_lenses_json TEXT NOT NULL DEFAULT '[]',
  salthira_refs_json TEXT NOT NULL DEFAULT '[]',
  assumptions_artificialities TEXT NOT NULL DEFAULT '',
  participating_organizations_json TEXT NOT NULL DEFAULT '[]',
  control_evaluation_roles_json TEXT NOT NULL DEFAULT '[]',
  scenario_summary TEXT NOT NULL DEFAULT '',
  scenario_control_json TEXT NOT NULL DEFAULT '{}',
  expected_actions_json TEXT NOT NULL DEFAULT '[]',
  evaluation_criteria_json TEXT NOT NULL DEFAULT '[]',
  safety_real_world_controls TEXT NOT NULL DEFAULT '',
  logistics_resources TEXT NOT NULL DEFAULT '',
  scheduled_at TEXT NOT NULL DEFAULT '',
  location TEXT NOT NULL DEFAULT '',
  external_partners_json TEXT NOT NULL DEFAULT '[]',
  communications_plan TEXT NOT NULL DEFAULT '',
  documentation_requirements TEXT NOT NULL DEFAULT '',
  sensitivity TEXT NOT NULL DEFAULT 'Standard',
  status TEXT NOT NULL DEFAULT 'Planned',
  commercial_treatment TEXT NOT NULL DEFAULT 'Not Determined',
  commercial_reference TEXT NOT NULL DEFAULT '',
  membership_entitlement_ref TEXT NOT NULL DEFAULT '',
  version INTEGER NOT NULL DEFAULT 1,
  created_by TEXT NOT NULL,
  created_at TEXT NOT NULL,
  updated_by TEXT NOT NULL,
  updated_at TEXT NOT NULL,
  approved_by TEXT NOT NULL DEFAULT '',
  approved_at TEXT NOT NULL DEFAULT '',
  FOREIGN KEY (plan_id) REFERENCES salops_preparedness_plans(id) ON DELETE SET NULL
);
CREATE INDEX IF NOT EXISTS idx_salops_prep_exercises_scope ON salops_preparedness_exercises(tenant_id,status,scheduled_at,assessment_id);

CREATE TABLE IF NOT EXISTS salops_preparedness_injects (
  id TEXT PRIMARY KEY,
  tenant_id INTEGER NOT NULL,
  exercise_id TEXT NOT NULL,
  sequence_no INTEGER NOT NULL,
  inject_code TEXT NOT NULL DEFAULT '',
  scheduled_offset TEXT NOT NULL DEFAULT '',
  title TEXT NOT NULL,
  inject_text TEXT NOT NULL,
  intended_recipient TEXT NOT NULL DEFAULT '',
  expected_decision TEXT NOT NULL DEFAULT '',
  evaluation_link TEXT NOT NULL DEFAULT '',
  controller_notes TEXT NOT NULL DEFAULT '',
  status TEXT NOT NULL DEFAULT 'Planned',
  created_by TEXT NOT NULL,
  created_at TEXT NOT NULL,
  delivered_by TEXT NOT NULL DEFAULT '',
  delivered_at TEXT NOT NULL DEFAULT '',
  FOREIGN KEY (exercise_id) REFERENCES salops_preparedness_exercises(id) ON DELETE CASCADE
);
CREATE INDEX IF NOT EXISTS idx_salops_prep_injects_scope ON salops_preparedness_injects(tenant_id,exercise_id,sequence_no);

CREATE TABLE IF NOT EXISTS salops_preparedness_observations (
  id TEXT PRIMARY KEY,
  tenant_id INTEGER NOT NULL,
  exercise_id TEXT NOT NULL,
  objective_ref TEXT NOT NULL DEFAULT '',
  capability_ref TEXT NOT NULL DEFAULT '',
  epistemic_state TEXT NOT NULL,
  title TEXT NOT NULL,
  observation TEXT NOT NULL,
  expected_standard TEXT NOT NULL DEFAULT '',
  what_occurred TEXT NOT NULL DEFAULT '',
  strength_to_sustain TEXT NOT NULL DEFAULT '',
  deficiency_gap TEXT NOT NULL DEFAULT '',
  contributing_factors TEXT NOT NULL DEFAULT '',
  operational_consequence TEXT NOT NULL DEFAULT '',
  salthira_ref TEXT NOT NULL DEFAULT '',
  corrective_recommendation TEXT NOT NULL DEFAULT '',
  source_refs_json TEXT NOT NULL DEFAULT '[]',
  observed_by TEXT NOT NULL DEFAULT '',
  observed_at TEXT NOT NULL DEFAULT '',
  status TEXT NOT NULL DEFAULT 'Open',
  member_release_status TEXT NOT NULL DEFAULT 'Internal',
  released_by TEXT NOT NULL DEFAULT '',
  released_at TEXT NOT NULL DEFAULT '',
  version INTEGER NOT NULL DEFAULT 1,
  created_by TEXT NOT NULL,
  created_at TEXT NOT NULL,
  updated_by TEXT NOT NULL,
  updated_at TEXT NOT NULL,
  FOREIGN KEY (exercise_id) REFERENCES salops_preparedness_exercises(id) ON DELETE CASCADE
);
CREATE INDEX IF NOT EXISTS idx_salops_prep_observations_scope ON salops_preparedness_observations(tenant_id,exercise_id,status,epistemic_state);

CREATE TABLE IF NOT EXISTS salops_preparedness_corrective_actions (
  id TEXT PRIMARY KEY,
  tenant_id INTEGER NOT NULL,
  observation_id TEXT,
  exercise_id TEXT,
  plan_id TEXT,
  assessment_id INTEGER,
  title TEXT NOT NULL,
  description TEXT NOT NULL,
  owner TEXT NOT NULL DEFAULT '',
  priority TEXT NOT NULL DEFAULT 'Normal',
  due_date TEXT NOT NULL DEFAULT '',
  resources_required TEXT NOT NULL DEFAULT '',
  estimate_reference TEXT NOT NULL DEFAULT '',
  membership_entitlement_ref TEXT NOT NULL DEFAULT '',
  completion_evidence_json TEXT NOT NULL DEFAULT '[]',
  validation_method TEXT NOT NULL DEFAULT '',
  reexercise_required INTEGER NOT NULL DEFAULT 0,
  validation_result TEXT NOT NULL DEFAULT '',
  closure_basis TEXT NOT NULL DEFAULT '',
  status TEXT NOT NULL DEFAULT 'Open',
  member_release_status TEXT NOT NULL DEFAULT 'Internal',
  released_by TEXT NOT NULL DEFAULT '',
  released_at TEXT NOT NULL DEFAULT '',
  version INTEGER NOT NULL DEFAULT 1,
  created_by TEXT NOT NULL,
  created_at TEXT NOT NULL,
  updated_by TEXT NOT NULL,
  updated_at TEXT NOT NULL,
  FOREIGN KEY (observation_id) REFERENCES salops_preparedness_observations(id) ON DELETE SET NULL,
  FOREIGN KEY (exercise_id) REFERENCES salops_preparedness_exercises(id) ON DELETE SET NULL,
  FOREIGN KEY (plan_id) REFERENCES salops_preparedness_plans(id) ON DELETE SET NULL
);
CREATE INDEX IF NOT EXISTS idx_salops_prep_corrective_scope ON salops_preparedness_corrective_actions(tenant_id,status,due_date,assessment_id);

CREATE TABLE IF NOT EXISTS salops_preparedness_aars (
  id TEXT PRIMARY KEY,
  tenant_id INTEGER NOT NULL,
  exercise_id TEXT NOT NULL,
  title TEXT NOT NULL,
  executive_summary TEXT NOT NULL DEFAULT '',
  strengths_json TEXT NOT NULL DEFAULT '[]',
  improvement_areas_json TEXT NOT NULL DEFAULT '[]',
  unresolved_questions_json TEXT NOT NULL DEFAULT '[]',
  corrective_action_ids_json TEXT NOT NULL DEFAULT '[]',
  status TEXT NOT NULL DEFAULT 'Draft',
  version INTEGER NOT NULL DEFAULT 1,
  created_by TEXT NOT NULL,
  created_at TEXT NOT NULL,
  updated_by TEXT NOT NULL,
  updated_at TEXT NOT NULL,
  reviewed_by TEXT NOT NULL DEFAULT '',
  reviewed_at TEXT NOT NULL DEFAULT '',
  approved_by TEXT NOT NULL DEFAULT '',
  approved_at TEXT NOT NULL DEFAULT '',
  released_by TEXT NOT NULL DEFAULT '',
  released_at TEXT NOT NULL DEFAULT '',
  FOREIGN KEY (exercise_id) REFERENCES salops_preparedness_exercises(id) ON DELETE CASCADE
);
CREATE INDEX IF NOT EXISTS idx_salops_prep_aars_scope ON salops_preparedness_aars(tenant_id,exercise_id,status);

CREATE TABLE IF NOT EXISTS salops_preparedness_chat_work (
  id TEXT PRIMARY KEY,
  tenant_id INTEGER NOT NULL,
  linked_entity_type TEXT NOT NULL,
  linked_entity_id TEXT NOT NULL,
  task_type TEXT NOT NULL,
  purpose TEXT NOT NULL,
  authorized_sources_json TEXT NOT NULL DEFAULT '[]',
  source_refs_json TEXT NOT NULL DEFAULT '[]',
  provider TEXT NOT NULL DEFAULT '',
  model TEXT NOT NULL DEFAULT '',
  output_summary TEXT NOT NULL DEFAULT '',
  output_json TEXT NOT NULL DEFAULT '{}',
  status TEXT NOT NULL DEFAULT 'Submitted for Human Review',
  created_by TEXT NOT NULL,
  created_at TEXT NOT NULL,
  reviewed_by TEXT NOT NULL DEFAULT '',
  reviewed_at TEXT NOT NULL DEFAULT '',
  review_reason TEXT NOT NULL DEFAULT ''
);
CREATE INDEX IF NOT EXISTS idx_salops_prep_chat_scope ON salops_preparedness_chat_work(tenant_id,linked_entity_type,linked_entity_id,status);

CREATE TABLE IF NOT EXISTS salops_preparedness_events (
  id TEXT PRIMARY KEY,
  tenant_id INTEGER NOT NULL,
  entity_type TEXT NOT NULL,
  entity_id TEXT NOT NULL,
  event_no INTEGER NOT NULL,
  record_version INTEGER NOT NULL,
  event_type TEXT NOT NULL,
  reason TEXT NOT NULL,
  snapshot_json TEXT NOT NULL,
  changed_by TEXT NOT NULL,
  changed_by_role TEXT NOT NULL,
  created_at TEXT NOT NULL,
  UNIQUE(tenant_id,entity_type,entity_id,event_no)
);
CREATE INDEX IF NOT EXISTS idx_salops_prep_events_scope ON salops_preparedness_events(tenant_id,entity_type,entity_id,event_no);
"""

JSON_COLUMNS = {
    "salops_preparedness_plans": {
        "portfolio_scope_json": "portfolio_scope", "mission_lenses_json": "mission_lenses",
        "evidence_refs_json": "evidence_refs", "salintel_refs_json": "salintel_refs",
        "salthira_refs_json": "salthira_refs", "salops_refs_json": "salops_refs",
    },
    "salops_preparedness_training": {
        "participants_json": "participants", "materials_json": "materials",
        "evidence_refs_json": "evidence_refs", "mission_lenses_json": "mission_lenses",
    },
    "salops_preparedness_exercises": {
        "objectives_json": "objectives", "capabilities_json": "capabilities",
        "portfolio_scope_json": "portfolio_scope", "mission_lenses_json": "mission_lenses",
        "salthira_refs_json": "salthira_refs", "participating_organizations_json": "participating_organizations",
        "control_evaluation_roles_json": "control_evaluation_roles", "scenario_control_json": "scenario_control",
        "expected_actions_json": "expected_actions", "evaluation_criteria_json": "evaluation_criteria",
        "external_partners_json": "external_partners",
    },
    "salops_preparedness_observations": {"source_refs_json": "source_refs"},
    "salops_preparedness_corrective_actions": {"completion_evidence_json": "completion_evidence"},
    "salops_preparedness_aars": {
        "strengths_json": "strengths", "improvement_areas_json": "improvement_areas",
        "unresolved_questions_json": "unresolved_questions", "corrective_action_ids_json": "corrective_action_ids",
    },
    "salops_preparedness_chat_work": {
        "authorized_sources_json": "authorized_sources", "source_refs_json": "source_refs", "output_json": "output",
    },
}
BACKUP_TABLES = [
    "salops_preparedness_plans", "salops_preparedness_training", "salops_preparedness_exercises",
    "salops_preparedness_injects", "salops_preparedness_observations", "salops_preparedness_corrective_actions",
    "salops_preparedness_aars", "salops_preparedness_chat_work", "salops_preparedness_events",
]
RESTORE_ORDER = [
    "salops_preparedness_plans", "salops_preparedness_training", "salops_preparedness_exercises",
    "salops_preparedness_injects", "salops_preparedness_observations", "salops_preparedness_corrective_actions",
    "salops_preparedness_aars", "salops_preparedness_chat_work", "salops_preparedness_events",
]
DELETE_ORDER = list(reversed(RESTORE_ORDER))


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


def _phases(value: list[str]) -> list[str]:
    seen: list[str] = []
    for phase in value:
        if phase not in MISSION_LENSES:
            raise ValueError(f"Unknown mission lens: {phase}")
        if phase not in seen:
            seen.append(phase)
    return seen


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class PlanCreate(StrictModel):
    assessment_id: Optional[int] = None
    title: str = Field(min_length=3, max_length=300)
    plan_type: str = Field(min_length=2, max_length=200)
    purpose: str = ""
    scope_statement: str = Field(min_length=3, max_length=12000)
    portfolio_scope: dict[str, Any] = Field(default_factory=dict)
    mission_lenses: list[str] = Field(default_factory=list)
    authorities_references: str = ""
    assumptions: str = ""
    roles_responsibilities: str = ""
    concept_of_operations: str = ""
    activation_criteria: str = ""
    command_coordination: str = ""
    communications: str = ""
    resource_requirements: str = ""
    dependencies: str = ""
    alternate_capability: str = ""
    checklists_job_aids: str = ""
    annexes_appendices: str = ""
    training_requirements: str = ""
    exercise_validation_requirements: str = ""
    evidence_refs: list[str] = Field(default_factory=list)
    known_unknowns: str = ""
    salintel_refs: list[str] = Field(default_factory=list)
    salthira_refs: list[str] = Field(default_factory=list)
    salops_refs: list[str] = Field(default_factory=list)
    sensitivity: Literal["Standard", "Sensitive", "Highly Sensitive"] = "Standard"
    owner: str = ""
    approver: str = ""
    effective_date: str = ""
    review_date: str = ""
    expiration_date: str = ""
    commercial_treatment: Literal[
        "Not Determined", "Membership Included", "Discounted", "Preferred Rate",
        "Credit Eligible", "Separately Quoted", "Pass-Through", "Custom"
    ] = "Not Determined"
    commercial_reference: str = ""
    membership_entitlement_ref: str = ""

    @field_validator("mission_lenses")
    @classmethod
    def validate_phases(cls, value: list[str]) -> list[str]:
        return _phases(value)


class PlanRevision(StrictModel):
    reason: str = Field(min_length=3, max_length=4000)
    title: Optional[str] = None
    plan_type: Optional[str] = None
    purpose: Optional[str] = None
    scope_statement: Optional[str] = None
    portfolio_scope: Optional[dict[str, Any]] = None
    mission_lenses: Optional[list[str]] = None
    authorities_references: Optional[str] = None
    assumptions: Optional[str] = None
    roles_responsibilities: Optional[str] = None
    concept_of_operations: Optional[str] = None
    activation_criteria: Optional[str] = None
    command_coordination: Optional[str] = None
    communications: Optional[str] = None
    resource_requirements: Optional[str] = None
    dependencies: Optional[str] = None
    alternate_capability: Optional[str] = None
    checklists_job_aids: Optional[str] = None
    annexes_appendices: Optional[str] = None
    training_requirements: Optional[str] = None
    exercise_validation_requirements: Optional[str] = None
    evidence_refs: Optional[list[str]] = None
    known_unknowns: Optional[str] = None
    salintel_refs: Optional[list[str]] = None
    salthira_refs: Optional[list[str]] = None
    salops_refs: Optional[list[str]] = None
    sensitivity: Optional[Literal["Standard", "Sensitive", "Highly Sensitive"]] = None
    owner: Optional[str] = None
    approver: Optional[str] = None
    effective_date: Optional[str] = None
    review_date: Optional[str] = None
    expiration_date: Optional[str] = None
    commercial_treatment: Optional[str] = None
    commercial_reference: Optional[str] = None
    membership_entitlement_ref: Optional[str] = None

    @field_validator("mission_lenses")
    @classmethod
    def validate_phases(cls, value: Optional[list[str]]) -> Optional[list[str]]:
        return None if value is None else _phases(value)


class Transition(StrictModel):
    status: str
    reason: str = Field(min_length=3, max_length=4000)


class MemberAdoption(StrictModel):
    decision: Literal["Adopted", "Rejected", "Superseded"]
    reason: str = Field(min_length=3, max_length=4000)


class TrainingCreate(StrictModel):
    assessment_id: Optional[int] = None
    plan_id: Optional[str] = None
    title: str = Field(min_length=3, max_length=300)
    objective: str = Field(min_length=3, max_length=12000)
    capability_ref: str = ""
    role_addressed: str = ""
    audience: str = ""
    participants: list[str] = Field(default_factory=list)
    prerequisites: str = ""
    delivery_type: str = ""
    materials: list[str] = Field(default_factory=list)
    instructor: str = ""
    scheduled_at: str = ""
    performance_check: str = ""
    follow_up_requirements: str = ""
    recurrence_schedule: str = ""
    mission_lenses: list[str] = Field(default_factory=list)
    commercial_treatment: str = "Not Determined"
    commercial_reference: str = ""
    membership_entitlement_ref: str = ""

    @field_validator("mission_lenses")
    @classmethod
    def validate_phases(cls, value: list[str]) -> list[str]:
        return _phases(value)


class TrainingComplete(StrictModel):
    performance_check: str = ""
    observations: str = ""
    follow_up_requirements: str = ""
    evidence_refs: list[str] = Field(default_factory=list)
    reason: str = Field(min_length=3, max_length=4000)


class ExerciseCreate(StrictModel):
    assessment_id: Optional[int] = None
    plan_id: Optional[str] = None
    title: str = Field(min_length=3, max_length=300)
    exercise_type: str
    purpose: str = ""
    objectives: list[str] = Field(default_factory=list)
    capabilities: list[str] = Field(default_factory=list)
    scope_statement: str = Field(min_length=3, max_length=12000)
    portfolio_scope: dict[str, Any] = Field(default_factory=dict)
    mission_lenses: list[str] = Field(default_factory=list)
    salthira_refs: list[str] = Field(default_factory=list)
    assumptions_artificialities: str = ""
    participating_organizations: list[str] = Field(default_factory=list)
    control_evaluation_roles: list[str] = Field(default_factory=list)
    scenario_summary: str = ""
    scenario_control: dict[str, Any] = Field(default_factory=dict)
    expected_actions: list[str] = Field(default_factory=list)
    evaluation_criteria: list[str] = Field(default_factory=list)
    safety_real_world_controls: str = ""
    logistics_resources: str = ""
    scheduled_at: str = ""
    location: str = ""
    external_partners: list[str] = Field(default_factory=list)
    communications_plan: str = ""
    documentation_requirements: str = ""
    sensitivity: Literal["Standard", "Sensitive", "Highly Sensitive"] = "Standard"
    commercial_treatment: str = "Not Determined"
    commercial_reference: str = ""
    membership_entitlement_ref: str = ""

    @field_validator("mission_lenses")
    @classmethod
    def validate_phases(cls, value: list[str]) -> list[str]:
        return _phases(value)

    @field_validator("exercise_type")
    @classmethod
    def validate_exercise_type(cls, value: str) -> str:
        if value not in EXERCISE_TYPES:
            raise ValueError("Unsupported exercise type")
        return value


class InjectCreate(StrictModel):
    sequence_no: int = Field(ge=1)
    inject_code: str = ""
    scheduled_offset: str = ""
    title: str = Field(min_length=2, max_length=300)
    inject_text: str = Field(min_length=2, max_length=12000)
    intended_recipient: str = ""
    expected_decision: str = ""
    evaluation_link: str = ""
    controller_notes: str = ""


class InjectDelivery(StrictModel):
    status: Literal["Delivered", "Skipped"]
    reason: str = Field(min_length=3, max_length=2000)


class ObservationCreate(StrictModel):
    objective_ref: str = ""
    capability_ref: str = ""
    epistemic_state: str
    title: str = Field(min_length=3, max_length=300)
    observation: str = Field(min_length=3, max_length=12000)
    expected_standard: str = ""
    what_occurred: str = ""
    strength_to_sustain: str = ""
    deficiency_gap: str = ""
    contributing_factors: str = ""
    operational_consequence: str = ""
    salthira_ref: str = ""
    corrective_recommendation: str = ""
    source_refs: list[str] = Field(default_factory=list)
    observed_by: str = ""
    observed_at: str = ""

    @field_validator("epistemic_state")
    @classmethod
    def validate_state(cls, value: str) -> str:
        if value not in EPISTEMIC_STATES:
            raise ValueError("Unsupported epistemic state")
        return value


class ReleaseDecision(StrictModel):
    approved_for_member: bool
    reason: str = Field(min_length=3, max_length=4000)


class CorrectiveCreate(StrictModel):
    observation_id: Optional[str] = None
    exercise_id: Optional[str] = None
    plan_id: Optional[str] = None
    assessment_id: Optional[int] = None
    title: str = Field(min_length=3, max_length=300)
    description: str = Field(min_length=3, max_length=12000)
    owner: str = ""
    priority: Literal["Low", "Normal", "High", "Critical"] = "Normal"
    due_date: str = ""
    resources_required: str = ""
    estimate_reference: str = ""
    membership_entitlement_ref: str = ""
    validation_method: str = ""
    reexercise_required: bool = False


class CorrectiveTransition(StrictModel):
    status: str
    reason: str = Field(min_length=3, max_length=4000)
    completion_evidence: list[str] = Field(default_factory=list)
    validation_result: str = ""
    closure_basis: str = ""


class AarCreate(StrictModel):
    exercise_id: str
    title: str = ""
    executive_summary: str = ""
    unresolved_questions: list[str] = Field(default_factory=list)


class ChatWorkCreate(StrictModel):
    linked_entity_type: Literal["Plan", "Training", "Exercise", "AAR", "Corrective Action"]
    linked_entity_id: str
    task_type: Literal[
        "Planning Research", "Plan Draft", "Training Design", "Exercise Design",
        "Exercise Scenario", "Evaluation Analysis", "AAR Draft", "Corrective Action Analysis"
    ]
    purpose: str = Field(min_length=3, max_length=12000)
    authorized_sources: list[str] = Field(default_factory=list)
    source_refs: list[str] = Field(default_factory=list)
    provider: str = ""
    model: str = ""
    output_summary: str = ""
    output: dict[str, Any] = Field(default_factory=dict)


class ChatWorkReview(StrictModel):
    status: Literal["Human Reviewed", "Qualified", "Rejected"]
    reason: str = Field(min_length=3, max_length=4000)


def register_salops_preparedness(app, core: dict[str, Any]) -> None:
    db = core["db"]
    now = core["now"]
    actor = core["actor"]
    role = core["role"]
    tenant_id = core["tenant_id"]
    require = core["require"]
    require_salus = core["require_salus_component_authority"]
    protected_member_request = core["protected_member_request"]
    require_member_authority = core.get("require_protected_member_authority")
    require_sensitivity = core.get("require_sensitivity")
    assessment_row_for_request = core.get("assessment_row_for_request")
    audit = core["audit"]

    conn = db()
    conn.executescript(SCHEMA)
    conn.commit()
    conn.close()

    def salus_write(request: Request) -> None:
        require(request, "write")
        require_salus(request, "SalOPS preparedness, planning, training and exercises")

    def ensure_assessment(request: Request, assessment_id: Optional[int]) -> None:
        if assessment_id and assessment_row_for_request:
            assessment_row_for_request(request, int(assessment_id))

    def require_row_sensitivity(request: Request, row: dict[str, Any]) -> None:
        if require_sensitivity:
            require_sensitivity(request, str(row.get("sensitivity") or "Standard"))

    def event(conn, entity_type: str, row: dict[str, Any], event_type: str, reason: str, request: Request) -> None:
        tid = int(row["tenant_id"])
        event_no = conn.execute(
            "SELECT COUNT(*) c FROM salops_preparedness_events WHERE tenant_id=? AND entity_type=? AND entity_id=?",
            (tid, entity_type, row["id"]),
        ).fetchone()["c"] + 1
        conn.execute(
            "INSERT INTO salops_preparedness_events(id,tenant_id,entity_type,entity_id,event_no,record_version,event_type,reason,snapshot_json,changed_by,changed_by_role,created_at) VALUES(?,?,?,?,?,?,?,?,?,?,?,?)",
            (_key("pevt"), tid, entity_type, row["id"], event_no, int(row.get("version") or 1), event_type,
             reason, _json(row), actor(request), role(request), now()),
        )
        audit(conn, f"SALOPS_PREP_{event_type.upper().replace(' ', '_')}", f"salops_{entity_type.lower().replace(' ', '_')}", None,
              f"{row['id']}: {reason}"[:1000], actor(request))

    def row_for(conn, table: str, record_id: str, request: Request) -> dict[str, Any]:
        row = conn.execute(f"SELECT * FROM {table} WHERE id=? AND tenant_id=?", (record_id, tenant_id(request))).fetchone()
        if not row:
            raise HTTPException(404, "Preparedness record not found")
        data = dict(row)
        ensure_assessment(request, data.get("assessment_id"))
        require_row_sensitivity(request, data)
        return data

    def decode(table: str, row: dict[str, Any]) -> dict[str, Any]:
        out = dict(row)
        for storage_name, api_name in JSON_COLUMNS.get(table, {}).items():
            default: Any = {} if storage_name.endswith("scope_json") or storage_name.endswith("control_json") or storage_name == "output_json" else []
            out[api_name] = _loads(out.pop(storage_name, None), default)
        if "reexercise_required" in out:
            out["reexercise_required"] = bool(out["reexercise_required"])
        return out

    def member_plan(row: dict[str, Any]) -> dict[str, Any]:
        allowed = {
            "id", "assessment_id", "title", "plan_type", "purpose", "scope_statement", "portfolio_scope",
            "mission_lenses", "roles_responsibilities", "concept_of_operations", "activation_criteria",
            "command_coordination", "communications", "resource_requirements", "dependencies", "alternate_capability",
            "checklists_job_aids", "annexes_appendices", "training_requirements", "exercise_validation_requirements",
            "owner", "approver", "effective_date", "review_date", "expiration_date", "status", "member_adoption_status", "version",
        }
        return {k: v for k, v in row.items() if k in allowed}

    def member_exercise(row: dict[str, Any]) -> dict[str, Any]:
        allowed = {
            "id", "assessment_id", "plan_id", "title", "exercise_type", "purpose", "objectives", "capabilities",
            "scope_statement", "portfolio_scope", "mission_lenses", "participating_organizations", "scheduled_at", "location",
            "communications_plan", "documentation_requirements", "status", "version",
        }
        return {k: v for k, v in row.items() if k in allowed}

    @app.get("/api/salops/preparedness/catalog")
    def preparedness_catalog(request: Request):
        require(request, "read")
        return {
            "service_family": "SalOPS™ Preparedness, Planning & Exercises",
            "lifecycle": ["Plan", "Train", "Exercise", "Observe", "Evaluate", "Improve", "Validate", "Sustain"],
            "mission_lenses": list(MISSION_LENSES),
            "exercise_types": list(EXERCISE_TYPES),
            "epistemic_states": list(EPISTEMIC_STATES),
            "commercial_treatments": list(COMMERCIAL_TREATMENTS),
            "principles": {
                "training_completion_is_readiness_proof": False,
                "corrective_completion_equals_validation": False,
                "automatic_customer_charge": False,
                "intentional_threat_content": "Defensive preparedness only",
            },
        }

    @app.get("/api/salops/preparedness/overview")
    def preparedness_overview(request: Request):
        require(request, "read")
        tid = tenant_id(request)
        conn = db()
        member = protected_member_request(request)
        plan_where = " AND status='Approved'" if member else ""
        exercise_where = " AND status IN ('Approved','In Progress','Completed','Evaluated','Closed')" if member else ""
        counts = {
            "plans": conn.execute(f"SELECT COUNT(*) c FROM salops_preparedness_plans WHERE tenant_id=?{plan_where}", (tid,)).fetchone()["c"],
            "training": conn.execute("SELECT COUNT(*) c FROM salops_preparedness_training WHERE tenant_id=? AND status!='Cancelled'", (tid,)).fetchone()["c"],
            "exercises": conn.execute(f"SELECT COUNT(*) c FROM salops_preparedness_exercises WHERE tenant_id=?{exercise_where}", (tid,)).fetchone()["c"],
            "open_corrective_actions": conn.execute(
                "SELECT COUNT(*) c FROM salops_preparedness_corrective_actions WHERE tenant_id=? AND status NOT IN ('Validated','Closed','Deferred')" + (" AND member_release_status='Released'" if member else ""), (tid,)
            ).fetchone()["c"],
            "released_aars": conn.execute("SELECT COUNT(*) c FROM salops_preparedness_aars WHERE tenant_id=? AND status='Released'", (tid,)).fetchone()["c"],
            "awaiting_validation": conn.execute(
                "SELECT COUNT(*) c FROM salops_preparedness_corrective_actions WHERE tenant_id=? AND status='Awaiting Validation'" + (" AND member_release_status='Released'" if member else ""), (tid,)
            ).fetchone()["c"],
        }
        upcoming = [decode("salops_preparedness_exercises", dict(r)) for r in conn.execute(
            "SELECT * FROM salops_preparedness_exercises WHERE tenant_id=? AND status IN ('Planned','Reviewed','Approved') ORDER BY scheduled_at,id LIMIT 10", (tid,)
        )]
        if member:
            upcoming = [member_exercise(r) for r in upcoming if r["status"] == "Approved"]
        conn.close()
        return {"counts": counts, "upcoming_exercises": upcoming,
                "lifecycle": ["Plan", "Train", "Exercise", "Observe", "Evaluate", "Improve", "Validate", "Sustain"]}

    @app.get("/api/salops/preparedness/plans")
    def list_plans(request: Request, status: str = "", assessment_id: Optional[int] = None):
        require(request, "read")
        tid = tenant_id(request)
        params: list[Any] = [tid]
        clauses = ["tenant_id=?"]
        if protected_member_request(request):
            clauses.append("status='Approved'")
        elif status:
            if status not in PLAN_STATUSES:
                raise HTTPException(422, "Unknown plan status")
            clauses.append("status=?"); params.append(status)
        if assessment_id:
            ensure_assessment(request, assessment_id); clauses.append("assessment_id=?"); params.append(assessment_id)
        conn = db()
        rows = [decode("salops_preparedness_plans", dict(r)) for r in conn.execute(
            "SELECT * FROM salops_preparedness_plans WHERE " + " AND ".join(clauses) + " ORDER BY review_date,title,id", tuple(params)
        )]
        conn.close()
        return [member_plan(r) for r in rows] if protected_member_request(request) else rows

    @app.post("/api/salops/preparedness/plans")
    def create_plan(payload: PlanCreate, request: Request):
        salus_write(request)
        ensure_assessment(request, payload.assessment_id)
        tid, who, ts, rid = tenant_id(request), actor(request), now(), _key("plan")
        d = payload.model_dump()
        conn = db()
        conn.execute(
            """INSERT INTO salops_preparedness_plans(
            id,tenant_id,assessment_id,title,plan_type,purpose,scope_statement,portfolio_scope_json,mission_lenses_json,
            authorities_references,assumptions,roles_responsibilities,concept_of_operations,activation_criteria,command_coordination,
            communications,resource_requirements,dependencies,alternate_capability,checklists_job_aids,annexes_appendices,
            training_requirements,exercise_validation_requirements,evidence_refs_json,known_unknowns,salintel_refs_json,salthira_refs_json,
            salops_refs_json,sensitivity,owner,approver,effective_date,review_date,expiration_date,commercial_treatment,
            commercial_reference,membership_entitlement_ref,version,created_by,created_at,updated_by,updated_at)
            VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (rid,tid,d["assessment_id"],d["title"],d["plan_type"],d["purpose"],d["scope_statement"],_json(d["portfolio_scope"]),_json(d["mission_lenses"]),
             d["authorities_references"],d["assumptions"],d["roles_responsibilities"],d["concept_of_operations"],d["activation_criteria"],d["command_coordination"],
             d["communications"],d["resource_requirements"],d["dependencies"],d["alternate_capability"],d["checklists_job_aids"],d["annexes_appendices"],
             d["training_requirements"],d["exercise_validation_requirements"],_json(d["evidence_refs"]),d["known_unknowns"],_json(d["salintel_refs"]),_json(d["salthira_refs"]),
             _json(d["salops_refs"]),d["sensitivity"],d["owner"],d["approver"],d["effective_date"],d["review_date"],d["expiration_date"],d["commercial_treatment"],
             d["commercial_reference"],d["membership_entitlement_ref"],1,who,ts,who,ts)
        )
        row = dict(conn.execute("SELECT * FROM salops_preparedness_plans WHERE id=?", (rid,)).fetchone())
        event(conn, "Plan", row, "Create", "Governed SalOPS plan created in Draft state.", request)
        conn.commit(); conn.close()
        return decode("salops_preparedness_plans", row)

    @app.get("/api/salops/preparedness/plans/{plan_id}")
    def get_plan(plan_id: str, request: Request):
        require(request, "read")
        conn = db(); row = row_for(conn, "salops_preparedness_plans", plan_id, request)
        decoded = decode("salops_preparedness_plans", row)
        if protected_member_request(request) and decoded["status"] != "Approved":
            conn.close(); raise HTTPException(403, "Plan has not been approved for Protected Member use")
        events = [] if protected_member_request(request) else [dict(r) for r in conn.execute(
            "SELECT event_no,record_version,event_type,reason,changed_by,changed_by_role,created_at FROM salops_preparedness_events WHERE tenant_id=? AND entity_type='Plan' AND entity_id=? ORDER BY event_no",
            (tenant_id(request), plan_id),
        )]
        conn.close()
        if protected_member_request(request):
            return {"plan": member_plan(decoded), "events": []}
        return {"plan": decoded, "events": events}

    @app.post("/api/salops/preparedness/plans/{plan_id}/revise")
    def revise_plan(plan_id: str, payload: PlanRevision, request: Request):
        salus_write(request)
        conn = db(); old = row_for(conn, "salops_preparedness_plans", plan_id, request)
        controlled = conn.execute(
            "SELECT id FROM salops_plan_materializations WHERE tenant_id=? AND draft_plan_id=?",
            (tenant_id(request), plan_id),
        ).fetchone()
        if controlled:
            conn.close(); raise HTTPException(409, "A materialized successor Draft must use its controlled review, approval, and release workflow")
        updates = payload.model_dump(exclude_none=True); reason = updates.pop("reason")
        json_map = {"portfolio_scope":"portfolio_scope_json","mission_lenses":"mission_lenses_json","evidence_refs":"evidence_refs_json",
                    "salintel_refs":"salintel_refs_json","salthira_refs":"salthira_refs_json","salops_refs":"salops_refs_json"}
        stored: dict[str, Any] = {}
        for key, value in updates.items():
            stored[json_map.get(key,key)] = _json(value) if key in json_map else value
        stored["version"] = int(old["version"]) + 1
        stored["status"] = "Draft"
        stored["reviewed_by"] = ""; stored["reviewed_at"] = ""; stored["approved_by"] = ""; stored["approved_at"] = ""
        stored["updated_by"] = actor(request); stored["updated_at"] = now()
        assignments = ",".join(f"{k}=?" for k in stored)
        conn.execute(f"UPDATE salops_preparedness_plans SET {assignments} WHERE id=? AND tenant_id=?", tuple(stored.values())+(plan_id,tenant_id(request)))
        row = dict(conn.execute("SELECT * FROM salops_preparedness_plans WHERE id=?", (plan_id,)).fetchone())
        event(conn, "Plan", row, "Revise", reason, request)
        conn.commit(); conn.close(); return decode("salops_preparedness_plans", row)

    @app.post("/api/salops/preparedness/plans/{plan_id}/transition")
    def transition_plan(plan_id: str, payload: Transition, request: Request):
        salus_write(request)
        conn = db(); row = row_for(conn, "salops_preparedness_plans", plan_id, request)
        controlled = conn.execute(
            "SELECT id FROM salops_plan_materializations WHERE tenant_id=? AND draft_plan_id=?",
            (tenant_id(request), plan_id),
        ).fetchone()
        if controlled:
            conn.close(); raise HTTPException(409, "A materialized successor Draft must use its controlled review, approval, and release workflow")
        target = payload.status
        allowed = {"Draft":"Reviewed", "Reviewed":"Approved", "Approved":"Retired"}
        if allowed.get(row["status"]) != target:
            conn.close(); raise HTTPException(409, f"Plan transition must follow Draft -> Reviewed -> Approved -> Retired; current status is {row['status']}")
        gates = {"Reviewed":{"System Administrator","Assessment Director","Lead Assessor"},
                 "Approved":{"System Administrator","Assessment Director","Program Owner"},
                 "Retired":{"System Administrator","Assessment Director","Program Owner"}}
        if role(request) not in gates[target]:
            conn.close(); raise HTTPException(403, f"{role(request)} cannot record the {target} plan authority gate")
        ts, who = now(), actor(request)
        extra = {}
        if target == "Reviewed": extra = {"reviewed_by":who,"reviewed_at":ts}
        if target == "Approved": extra = {"approved_by":who,"approved_at":ts}
        sets = {"status":target,"updated_by":who,"updated_at":ts,**extra}
        conn.execute("UPDATE salops_preparedness_plans SET "+",".join(f"{k}=?" for k in sets)+" WHERE id=? AND tenant_id=?", tuple(sets.values())+(plan_id,tenant_id(request)))
        updated = dict(conn.execute("SELECT * FROM salops_preparedness_plans WHERE id=?", (plan_id,)).fetchone())
        event(conn,"Plan",updated,f"Transition {target}",payload.reason,request)
        conn.commit(); conn.close(); return decode("salops_preparedness_plans",updated)

    @app.post("/api/salops/preparedness/plans/{plan_id}/member-adoption")
    def adopt_plan(plan_id: str, payload: MemberAdoption, request: Request):
        require(request,"read")
        if not require_member_authority:
            raise HTTPException(503,"Protected Member decision authority helper unavailable")
        require_member_authority(request,"SalOPS plan adoption decision")
        conn=db(); row=row_for(conn,"salops_preparedness_plans",plan_id,request)
        if row["status"] != "Approved":
            conn.close(); raise HTTPException(409,"Only an approved Salus plan may be presented for Protected Member adoption")
        ts=now(); who=actor(request)
        conn.execute("UPDATE salops_preparedness_plans SET member_adoption_status=?,member_adoption_reason=?,member_adopted_by=?,member_adopted_at=?,updated_by=?,updated_at=? WHERE id=? AND tenant_id=?",
                     (payload.decision,payload.reason,who,ts,who,ts,plan_id,tenant_id(request)))
        updated=dict(conn.execute("SELECT * FROM salops_preparedness_plans WHERE id=?",(plan_id,)).fetchone())
        event(conn,"Plan",updated,f"Member {payload.decision}",payload.reason,request)
        conn.commit(); conn.close(); return member_plan(decode("salops_preparedness_plans",updated))

    @app.get("/api/salops/preparedness/training")
    def list_training(request: Request, status: str = ""):
        require(request,"read")
        clauses=["tenant_id=?"]; params: list[Any] = [tenant_id(request)]
        if protected_member_request(request): clauses.append("member_release_status='Released'")
        if status:
            if status not in TRAINING_STATUSES: raise HTTPException(422,"Unknown training status")
            clauses.append("status=?"); params.append(status)
        conn=db(); rows=[decode("salops_preparedness_training",dict(r)) for r in conn.execute("SELECT * FROM salops_preparedness_training WHERE "+" AND ".join(clauses)+" ORDER BY scheduled_at,title,id",tuple(params))]; conn.close()
        if protected_member_request(request):
            keep=("id","plan_id","title","objective","capability_ref","role_addressed","audience","delivery_type","instructor","scheduled_at","completed_at","recurrence_schedule","mission_lenses","status")
            return [{k:r[k] for k in keep if k in r} for r in rows]
        return rows

    @app.post("/api/salops/preparedness/training")
    def create_training(payload: TrainingCreate, request: Request):
        salus_write(request); ensure_assessment(request,payload.assessment_id)
        tid,who,ts,rid=tenant_id(request),actor(request),now(),_key("train")
        if payload.plan_id:
            conn=db(); row_for(conn,"salops_preparedness_plans",payload.plan_id,request); conn.close()
        d=payload.model_dump(); conn=db()
        conn.execute("""INSERT INTO salops_preparedness_training(id,tenant_id,assessment_id,plan_id,title,objective,capability_ref,role_addressed,audience,participants_json,prerequisites,delivery_type,materials_json,instructor,scheduled_at,performance_check,follow_up_requirements,recurrence_schedule,mission_lenses_json,status,commercial_treatment,commercial_reference,membership_entitlement_ref,version,created_by,created_at,updated_by,updated_at) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                     (rid,tid,d["assessment_id"],d["plan_id"],d["title"],d["objective"],d["capability_ref"],d["role_addressed"],d["audience"],_json(d["participants"]),d["prerequisites"],d["delivery_type"],_json(d["materials"]),d["instructor"],d["scheduled_at"],d["performance_check"],d["follow_up_requirements"],d["recurrence_schedule"],_json(d["mission_lenses"]),"Scheduled",d["commercial_treatment"],d["commercial_reference"],d["membership_entitlement_ref"],1,who,ts,who,ts))
        row=dict(conn.execute("SELECT * FROM salops_preparedness_training WHERE id=?",(rid,)).fetchone()); event(conn,"Training",row,"Create","Governed training activity scheduled.",request); conn.commit(); conn.close(); return decode("salops_preparedness_training",row)

    @app.post("/api/salops/preparedness/training/{training_id}/complete")
    def complete_training(training_id:str,payload:TrainingComplete,request:Request):
        salus_write(request); conn=db(); row=row_for(conn,"salops_preparedness_training",training_id,request)
        if row["status"] not in ("Scheduled","In Progress"):
            conn.close(); raise HTTPException(409,"Only scheduled or in-progress training may be completed")
        ts=now(); who=actor(request)
        conn.execute("UPDATE salops_preparedness_training SET status='Completed',completed_at=?,performance_check=?,observations=?,follow_up_requirements=?,evidence_refs_json=?,version=version+1,updated_by=?,updated_at=? WHERE id=? AND tenant_id=?",
                     (ts,payload.performance_check,payload.observations,payload.follow_up_requirements,_json(payload.evidence_refs),who,ts,training_id,tenant_id(request)))
        updated=dict(conn.execute("SELECT * FROM salops_preparedness_training WHERE id=?",(training_id,)).fetchone()); event(conn,"Training",updated,"Complete",payload.reason+" Training completion does not itself prove operational readiness.",request); conn.commit(); conn.close(); return decode("salops_preparedness_training",updated)

    @app.post("/api/salops/preparedness/training/{training_id}/release")
    def release_training(training_id:str,payload:ReleaseDecision,request:Request):
        salus_write(request);conn=db();row=row_for(conn,"salops_preparedness_training",training_id,request);status="Released" if payload.approved_for_member else "Internal";ts=now();who=actor(request)
        conn.execute("UPDATE salops_preparedness_training SET member_release_status=?,released_by=?,released_at=?,version=version+1,updated_by=?,updated_at=? WHERE id=? AND tenant_id=?",(status,who if payload.approved_for_member else "",ts if payload.approved_for_member else "",who,ts,training_id,tenant_id(request)));updated=dict(conn.execute("SELECT * FROM salops_preparedness_training WHERE id=?",(training_id,)).fetchone());event(conn,"Training",updated,"Disclosure",payload.reason,request);conn.commit();conn.close();return decode("salops_preparedness_training",updated)

    @app.get("/api/salops/preparedness/exercises")
    def list_exercises(request:Request,status:str=""):
        require(request,"read"); clauses=["tenant_id=?"]; params: list[Any] = [tenant_id(request)]
        if protected_member_request(request): clauses.append("status IN ('Approved','In Progress','Completed','Evaluated','Closed')")
        elif status:
            if status not in EXERCISE_STATUSES: raise HTTPException(422,"Unknown exercise status")
            clauses.append("status=?"); params.append(status)
        conn=db(); rows=[decode("salops_preparedness_exercises",dict(r)) for r in conn.execute("SELECT * FROM salops_preparedness_exercises WHERE "+" AND ".join(clauses)+" ORDER BY scheduled_at,title,id",tuple(params))]; conn.close()
        return [member_exercise(r) for r in rows] if protected_member_request(request) else rows

    @app.post("/api/salops/preparedness/exercises")
    def create_exercise(payload:ExerciseCreate,request:Request):
        salus_write(request); ensure_assessment(request,payload.assessment_id)
        if payload.plan_id:
            conn=db(); row_for(conn,"salops_preparedness_plans",payload.plan_id,request); conn.close()
        tid,who,ts,rid=tenant_id(request),actor(request),now(),_key("exercise"); d=payload.model_dump(); conn=db()
        conn.execute("""INSERT INTO salops_preparedness_exercises(id,tenant_id,assessment_id,plan_id,title,exercise_type,purpose,objectives_json,capabilities_json,scope_statement,portfolio_scope_json,mission_lenses_json,salthira_refs_json,assumptions_artificialities,participating_organizations_json,control_evaluation_roles_json,scenario_summary,scenario_control_json,expected_actions_json,evaluation_criteria_json,safety_real_world_controls,logistics_resources,scheduled_at,location,external_partners_json,communications_plan,documentation_requirements,sensitivity,status,commercial_treatment,commercial_reference,membership_entitlement_ref,version,created_by,created_at,updated_by,updated_at) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                     (rid,tid,d["assessment_id"],d["plan_id"],d["title"],d["exercise_type"],d["purpose"],_json(d["objectives"]),_json(d["capabilities"]),d["scope_statement"],_json(d["portfolio_scope"]),_json(d["mission_lenses"]),_json(d["salthira_refs"]),d["assumptions_artificialities"],_json(d["participating_organizations"]),_json(d["control_evaluation_roles"]),d["scenario_summary"],_json(d["scenario_control"]),_json(d["expected_actions"]),_json(d["evaluation_criteria"]),d["safety_real_world_controls"],d["logistics_resources"],d["scheduled_at"],d["location"],_json(d["external_partners"]),d["communications_plan"],d["documentation_requirements"],d["sensitivity"],"Planned",d["commercial_treatment"],d["commercial_reference"],d["membership_entitlement_ref"],1,who,ts,who,ts))
        row=dict(conn.execute("SELECT * FROM salops_preparedness_exercises WHERE id=?",(rid,)).fetchone()); event(conn,"Exercise",row,"Create","Governed exercise design created in Planned state.",request); conn.commit(); conn.close(); return decode("salops_preparedness_exercises",row)

    @app.get("/api/salops/preparedness/exercises/{exercise_id}")
    def get_exercise(exercise_id:str,request:Request):
        require(request,"read"); conn=db(); row=row_for(conn,"salops_preparedness_exercises",exercise_id,request); decoded=decode("salops_preparedness_exercises",row)
        member=protected_member_request(request)
        if member and decoded["status"] not in ("Approved","In Progress","Completed","Evaluated","Closed"):
            conn.close(); raise HTTPException(403,"Exercise has not been approved for Protected Member visibility")
        observations=[decode("salops_preparedness_observations",dict(r)) for r in conn.execute("SELECT * FROM salops_preparedness_observations WHERE tenant_id=? AND exercise_id=?"+(" AND member_release_status='Released'" if member else "")+" ORDER BY created_at,id",(tenant_id(request),exercise_id))]
        correctives=[decode("salops_preparedness_corrective_actions",dict(r)) for r in conn.execute("SELECT * FROM salops_preparedness_corrective_actions WHERE tenant_id=? AND exercise_id=?"+(" AND member_release_status='Released'" if member else "")+" ORDER BY due_date,id",(tenant_id(request),exercise_id))]
        aars=[decode("salops_preparedness_aars",dict(r)) for r in conn.execute("SELECT * FROM salops_preparedness_aars WHERE tenant_id=? AND exercise_id=?"+(" AND status='Released'" if member else "")+" ORDER BY created_at,id",(tenant_id(request),exercise_id))]
        injects=[] if member else [dict(r) for r in conn.execute("SELECT * FROM salops_preparedness_injects WHERE tenant_id=? AND exercise_id=? ORDER BY sequence_no,id",(tenant_id(request),exercise_id))]
        conn.close(); return {"exercise":member_exercise(decoded) if member else decoded,"injects":injects,"observations":observations,"corrective_actions":correctives,"aars":aars}

    @app.post("/api/salops/preparedness/exercises/{exercise_id}/transition")
    def transition_exercise(exercise_id:str,payload:Transition,request:Request):
        salus_write(request); conn=db(); row=row_for(conn,"salops_preparedness_exercises",exercise_id,request)
        normal={"Planned":"Reviewed","Reviewed":"Approved","Approved":"In Progress","In Progress":"Completed","Completed":"Evaluated","Evaluated":"Closed"}
        if payload.status=="Cancelled" and row["status"] not in ("Completed","Evaluated","Closed","Cancelled"):
            target="Cancelled"
        else:
            target=payload.status
            if normal.get(row["status"])!=target:
                conn.close(); raise HTTPException(409,f"Exercise transition is not valid from {row['status']} to {target}")
        ts=now();who=actor(request); extra={}
        if target=="Approved": extra={"approved_by":who,"approved_at":ts}
        sets={"status":target,"version":int(row["version"])+1,"updated_by":who,"updated_at":ts,**extra}
        conn.execute("UPDATE salops_preparedness_exercises SET "+",".join(f"{k}=?" for k in sets)+" WHERE id=? AND tenant_id=?",tuple(sets.values())+(exercise_id,tenant_id(request)))
        updated=dict(conn.execute("SELECT * FROM salops_preparedness_exercises WHERE id=?",(exercise_id,)).fetchone());event(conn,"Exercise",updated,f"Transition {target}",payload.reason,request);conn.commit();conn.close();return decode("salops_preparedness_exercises",updated)

    @app.post("/api/salops/preparedness/exercises/{exercise_id}/injects")
    def add_inject(exercise_id:str,payload:InjectCreate,request:Request):
        salus_write(request);conn=db();row_for(conn,"salops_preparedness_exercises",exercise_id,request);rid=_key("inject");ts=now();who=actor(request);d=payload.model_dump()
        conn.execute("INSERT INTO salops_preparedness_injects(id,tenant_id,exercise_id,sequence_no,inject_code,scheduled_offset,title,inject_text,intended_recipient,expected_decision,evaluation_link,controller_notes,status,created_by,created_at) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                     (rid,tenant_id(request),exercise_id,d["sequence_no"],d["inject_code"],d["scheduled_offset"],d["title"],d["inject_text"],d["intended_recipient"],d["expected_decision"],d["evaluation_link"],d["controller_notes"],"Planned",who,ts))
        audit(conn,"SALOPS_PREP_INJECT_CREATE","salops_exercise",None,f"{exercise_id}/{rid}: defensive exercise-control inject created",who);conn.commit();out=dict(conn.execute("SELECT * FROM salops_preparedness_injects WHERE id=?",(rid,)).fetchone());conn.close();return out

    @app.post("/api/salops/preparedness/injects/{inject_id}/delivery")
    def deliver_inject(inject_id:str,payload:InjectDelivery,request:Request):
        salus_write(request);conn=db();row=conn.execute("SELECT * FROM salops_preparedness_injects WHERE id=? AND tenant_id=?",(inject_id,tenant_id(request))).fetchone()
        if not row: conn.close();raise HTTPException(404,"Inject not found")
        ts=now();who=actor(request);conn.execute("UPDATE salops_preparedness_injects SET status=?,delivered_by=?,delivered_at=? WHERE id=? AND tenant_id=?",(payload.status,who,ts,inject_id,tenant_id(request)));audit(conn,"SALOPS_PREP_INJECT_DELIVERY","salops_exercise",None,f"{inject_id}: {payload.status}; {payload.reason}"[:1000],who);conn.commit();out=dict(conn.execute("SELECT * FROM salops_preparedness_injects WHERE id=?",(inject_id,)).fetchone());conn.close();return out

    @app.post("/api/salops/preparedness/exercises/{exercise_id}/observations")
    def add_observation(exercise_id:str,payload:ObservationCreate,request:Request):
        salus_write(request);conn=db();exercise=row_for(conn,"salops_preparedness_exercises",exercise_id,request);rid=_key("obs");ts=now();who=actor(request);d=payload.model_dump()
        conn.execute("""INSERT INTO salops_preparedness_observations(id,tenant_id,exercise_id,objective_ref,capability_ref,epistemic_state,title,observation,expected_standard,what_occurred,strength_to_sustain,deficiency_gap,contributing_factors,operational_consequence,salthira_ref,corrective_recommendation,source_refs_json,observed_by,observed_at,status,member_release_status,version,created_by,created_at,updated_by,updated_at) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                     (rid,tenant_id(request),exercise_id,d["objective_ref"],d["capability_ref"],d["epistemic_state"],d["title"],d["observation"],d["expected_standard"],d["what_occurred"],d["strength_to_sustain"],d["deficiency_gap"],d["contributing_factors"],d["operational_consequence"],d["salthira_ref"],d["corrective_recommendation"],_json(d["source_refs"]),d["observed_by"] or who,d["observed_at"] or ts,"Open","Internal",1,who,ts,who,ts))
        row=dict(conn.execute("SELECT * FROM salops_preparedness_observations WHERE id=?",(rid,)).fetchone());event(conn,"Observation",row,"Create",f"Exercise {exercise['id']} observation preserved separately from analyst conclusions.",request);conn.commit();conn.close();return decode("salops_preparedness_observations",row)

    @app.post("/api/salops/preparedness/observations/{observation_id}/release")
    def release_observation(observation_id:str,payload:ReleaseDecision,request:Request):
        salus_write(request);conn=db();row=row_for(conn,"salops_preparedness_observations",observation_id,request);status="Released" if payload.approved_for_member else "Internal";ts=now();who=actor(request)
        conn.execute("UPDATE salops_preparedness_observations SET member_release_status=?,released_by=?,released_at=?,version=version+1,updated_by=?,updated_at=? WHERE id=? AND tenant_id=?",(status,who if payload.approved_for_member else "",ts if payload.approved_for_member else "",who,ts,observation_id,tenant_id(request)));updated=dict(conn.execute("SELECT * FROM salops_preparedness_observations WHERE id=?",(observation_id,)).fetchone());event(conn,"Observation",updated,"Disclosure",payload.reason,request);conn.commit();conn.close();return decode("salops_preparedness_observations",updated)

    @app.get("/api/salops/preparedness/corrective-actions")
    def list_correctives(request:Request,status:str=""):
        require(request,"read");clauses=["tenant_id=?"];params: list[Any] = [tenant_id(request)]
        if protected_member_request(request): clauses.append("member_release_status='Released'")
        if status:
            if status not in CORRECTIVE_STATUSES: raise HTTPException(422,"Unknown corrective-action status")
            clauses.append("status=?");params.append(status)
        conn=db();rows=[decode("salops_preparedness_corrective_actions",dict(r)) for r in conn.execute("SELECT * FROM salops_preparedness_corrective_actions WHERE "+" AND ".join(clauses)+" ORDER BY due_date,title,id",tuple(params))];conn.close();return rows

    @app.post("/api/salops/preparedness/corrective-actions")
    def create_corrective(payload:CorrectiveCreate,request:Request):
        salus_write(request);ensure_assessment(request,payload.assessment_id);conn=db()
        if payload.observation_id: row_for(conn,"salops_preparedness_observations",payload.observation_id,request)
        if payload.exercise_id: row_for(conn,"salops_preparedness_exercises",payload.exercise_id,request)
        if payload.plan_id: row_for(conn,"salops_preparedness_plans",payload.plan_id,request)
        rid=_key("action");ts=now();who=actor(request);d=payload.model_dump()
        conn.execute("""INSERT INTO salops_preparedness_corrective_actions(id,tenant_id,observation_id,exercise_id,plan_id,assessment_id,title,description,owner,priority,due_date,resources_required,estimate_reference,membership_entitlement_ref,validation_method,reexercise_required,status,member_release_status,version,created_by,created_at,updated_by,updated_at) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                     (rid,tenant_id(request),d["observation_id"],d["exercise_id"],d["plan_id"],d["assessment_id"],d["title"],d["description"],d["owner"],d["priority"],d["due_date"],d["resources_required"],d["estimate_reference"],d["membership_entitlement_ref"],d["validation_method"],1 if d["reexercise_required"] else 0,"Open","Internal",1,who,ts,who,ts))
        row=dict(conn.execute("SELECT * FROM salops_preparedness_corrective_actions WHERE id=?",(rid,)).fetchone());event(conn,"Corrective Action",row,"Create","Corrective action created; implementation and validation remain separate governance states.",request);conn.commit();conn.close();return decode("salops_preparedness_corrective_actions",row)

    @app.post("/api/salops/preparedness/corrective-actions/{action_id}/transition")
    def transition_corrective(action_id:str,payload:CorrectiveTransition,request:Request):
        salus_write(request);conn=db();row=row_for(conn,"salops_preparedness_corrective_actions",action_id,request);target=payload.status
        normal={"Open":"In Progress","In Progress":"Implemented","Implemented":"Awaiting Validation","Awaiting Validation":"Validated","Validated":"Closed"}
        if target=="Deferred" and row["status"] not in ("Validated","Closed"):
            pass
        elif normal.get(row["status"])!=target:
            conn.close();raise HTTPException(409,f"Corrective-action transition is not valid from {row['status']} to {target}. Completion must remain distinct from validation.")
        if target=="Implemented" and not payload.completion_evidence:
            conn.close();raise HTTPException(409,"Implemented status requires completion evidence")
        if target=="Validated" and not payload.validation_result.strip():
            conn.close();raise HTTPException(409,"Validated status requires a validation result")
        if target=="Closed" and not payload.closure_basis.strip():
            conn.close();raise HTTPException(409,"Closed status requires a closure basis")
        ts=now();who=actor(request);sets={"status":target,"version":int(row["version"])+1,"updated_by":who,"updated_at":ts}
        if payload.completion_evidence: sets["completion_evidence_json"]=_json(payload.completion_evidence)
        if payload.validation_result: sets["validation_result"]=payload.validation_result
        if payload.closure_basis: sets["closure_basis"]=payload.closure_basis
        conn.execute("UPDATE salops_preparedness_corrective_actions SET "+",".join(f"{k}=?" for k in sets)+" WHERE id=? AND tenant_id=?",tuple(sets.values())+(action_id,tenant_id(request)));updated=dict(conn.execute("SELECT * FROM salops_preparedness_corrective_actions WHERE id=?",(action_id,)).fetchone());event(conn,"Corrective Action",updated,f"Transition {target}",payload.reason,request);conn.commit();conn.close();return decode("salops_preparedness_corrective_actions",updated)

    @app.post("/api/salops/preparedness/corrective-actions/{action_id}/release")
    def release_corrective(action_id:str,payload:ReleaseDecision,request:Request):
        salus_write(request);conn=db();row_for(conn,"salops_preparedness_corrective_actions",action_id,request);status="Released" if payload.approved_for_member else "Internal";ts=now();who=actor(request)
        conn.execute("UPDATE salops_preparedness_corrective_actions SET member_release_status=?,released_by=?,released_at=?,version=version+1,updated_by=?,updated_at=? WHERE id=? AND tenant_id=?",(status,who if payload.approved_for_member else "",ts if payload.approved_for_member else "",who,ts,action_id,tenant_id(request)));updated=dict(conn.execute("SELECT * FROM salops_preparedness_corrective_actions WHERE id=?",(action_id,)).fetchone());event(conn,"Corrective Action",updated,"Disclosure",payload.reason,request);conn.commit();conn.close();return decode("salops_preparedness_corrective_actions",updated)

    @app.get("/api/salops/preparedness/aars")
    def list_aars(request:Request):
        require(request,"read");where="tenant_id=?"+(" AND status='Released'" if protected_member_request(request) else "");conn=db();rows=[decode("salops_preparedness_aars",dict(r)) for r in conn.execute("SELECT * FROM salops_preparedness_aars WHERE "+where+" ORDER BY created_at DESC,id",(tenant_id(request),))];conn.close();return rows

    @app.post("/api/salops/preparedness/aars")
    def create_aar(payload:AarCreate,request:Request):
        salus_write(request);conn=db();exercise=row_for(conn,"salops_preparedness_exercises",payload.exercise_id,request)
        if exercise["status"] not in ("Completed","Evaluated","Closed"):
            conn.close();raise HTTPException(409,"AAR generation requires a completed exercise")
        observations=[decode("salops_preparedness_observations",dict(r)) for r in conn.execute("SELECT * FROM salops_preparedness_observations WHERE tenant_id=? AND exercise_id=? ORDER BY created_at,id",(tenant_id(request),payload.exercise_id))]
        correctives=[decode("salops_preparedness_corrective_actions",dict(r)) for r in conn.execute("SELECT * FROM salops_preparedness_corrective_actions WHERE tenant_id=? AND exercise_id=? ORDER BY due_date,id",(tenant_id(request),payload.exercise_id))]
        strengths=[o["strength_to_sustain"] for o in observations if o.get("strength_to_sustain")]
        improvements=[{"observation_id":o["id"],"title":o["title"],"gap":o.get("deficiency_gap",""),"recommendation":o.get("corrective_recommendation","")} for o in observations if o.get("deficiency_gap") or o.get("corrective_recommendation")]
        rid=_key("aar");ts=now();who=actor(request);title=payload.title or f"After-Action Report / Improvement Plan — {exercise['title']}"
        conn.execute("INSERT INTO salops_preparedness_aars(id,tenant_id,exercise_id,title,executive_summary,strengths_json,improvement_areas_json,unresolved_questions_json,corrective_action_ids_json,status,version,created_by,created_at,updated_by,updated_at) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                     (rid,tenant_id(request),payload.exercise_id,title,payload.executive_summary,_json(strengths),_json(improvements),_json(payload.unresolved_questions),_json([c["id"] for c in correctives]),"Draft",1,who,ts,who,ts))
        row=dict(conn.execute("SELECT * FROM salops_preparedness_aars WHERE id=?",(rid,)).fetchone());event(conn,"AAR",row,"Create","Draft AAR/IP generated from authoritative exercise observations and corrective actions; source records were not overwritten.",request);conn.commit();conn.close();return decode("salops_preparedness_aars",row)

    @app.post("/api/salops/preparedness/aars/{aar_id}/transition")
    def transition_aar(aar_id:str,payload:Transition,request:Request):
        salus_write(request);conn=db();row=row_for(conn,"salops_preparedness_aars",aar_id,request);allowed={"Draft":"Reviewed","Reviewed":"Approved","Approved":"Released"}
        if allowed.get(row["status"])!=payload.status:
            conn.close();raise HTTPException(409,f"AAR transition must follow Draft -> Reviewed -> Approved -> Released; current status is {row['status']}")
        target=payload.status;ts=now();who=actor(request);extra={}
        if target=="Reviewed":extra={"reviewed_by":who,"reviewed_at":ts}
        if target=="Approved":extra={"approved_by":who,"approved_at":ts}
        if target=="Released":extra={"released_by":who,"released_at":ts}
        sets={"status":target,"version":int(row["version"])+1,"updated_by":who,"updated_at":ts,**extra};conn.execute("UPDATE salops_preparedness_aars SET "+",".join(f"{k}=?" for k in sets)+" WHERE id=? AND tenant_id=?",tuple(sets.values())+(aar_id,tenant_id(request)));updated=dict(conn.execute("SELECT * FROM salops_preparedness_aars WHERE id=?",(aar_id,)).fetchone());event(conn,"AAR",updated,f"Transition {target}",payload.reason,request);conn.commit();conn.close();return decode("salops_preparedness_aars",updated)

    @app.get("/api/salops/preparedness/chat-work")
    def list_chat_work(request:Request,linked_entity_type:str="",linked_entity_id:str=""):
        require(request,"read");require_salus(request,"SalOPS preparedness Chat work products");clauses=["tenant_id=?"];params: list[Any] = [tenant_id(request)]
        if linked_entity_type: clauses.append("linked_entity_type=?");params.append(linked_entity_type)
        if linked_entity_id: clauses.append("linked_entity_id=?");params.append(linked_entity_id)
        conn=db();rows=[decode("salops_preparedness_chat_work",dict(r)) for r in conn.execute("SELECT * FROM salops_preparedness_chat_work WHERE "+" AND ".join(clauses)+" ORDER BY created_at DESC,id",tuple(params))];conn.close();return rows

    @app.post("/api/salops/preparedness/chat-work")
    def create_chat_work(payload:ChatWorkCreate,request:Request):
        salus_write(request);rid=_key("chat");ts=now();who=actor(request);d=payload.model_dump();conn=db()
        conn.execute("INSERT INTO salops_preparedness_chat_work(id,tenant_id,linked_entity_type,linked_entity_id,task_type,purpose,authorized_sources_json,source_refs_json,provider,model,output_summary,output_json,status,created_by,created_at) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                     (rid,tenant_id(request),d["linked_entity_type"],d["linked_entity_id"],d["task_type"],d["purpose"],_json(d["authorized_sources"]),_json(d["source_refs"]),d["provider"],d["model"],d["output_summary"],_json(d["output"]),"Submitted for Human Review",who,ts));audit(conn,"SALOPS_PREP_CHAT_WORK","salops_chat_work",None,f"{rid}: {d['task_type']} submitted for human review",who);conn.commit();row=dict(conn.execute("SELECT * FROM salops_preparedness_chat_work WHERE id=?",(rid,)).fetchone());conn.close();return decode("salops_preparedness_chat_work",row)

    @app.post("/api/salops/preparedness/chat-work/{work_id}/review")
    def review_chat_work(work_id:str,payload:ChatWorkReview,request:Request):
        salus_write(request);conn=db();row=conn.execute("SELECT * FROM salops_preparedness_chat_work WHERE id=? AND tenant_id=?",(work_id,tenant_id(request))).fetchone()
        if not row:conn.close();raise HTTPException(404,"Chat work product not found")
        ts=now();who=actor(request);conn.execute("UPDATE salops_preparedness_chat_work SET status=?,reviewed_by=?,reviewed_at=?,review_reason=? WHERE id=? AND tenant_id=?",(payload.status,who,ts,payload.reason,work_id,tenant_id(request)));audit(conn,"SALOPS_PREP_CHAT_REVIEW","salops_chat_work",None,f"{work_id}: {payload.status}; {payload.reason}"[:1000],who);conn.commit();out=dict(conn.execute("SELECT * FROM salops_preparedness_chat_work WHERE id=?",(work_id,)).fetchone());conn.close();return decode("salops_preparedness_chat_work",out)

    # Extend the core portable-backup hooks at runtime. Existing backup endpoints resolve
    # these globals when called, so this preserves a single tenant backup/restore contract.
    original_collect = core.get("collect_tenant_records")
    original_validate = core.get("validate_records")
    original_replace = core.get("replace_tenant_records")
    if original_collect and original_validate and original_replace:
        def extended_collect(conn, tid: int):
            records = original_collect(conn, tid)
            for table in BACKUP_TABLES:
                records[table] = [dict(r) for r in conn.execute(f"SELECT * FROM {table} WHERE tenant_id=? ORDER BY id", (tid,))]
            return records

        def prep_validate(records: dict, tid: int) -> list[str]:
            errors: list[str] = []
            ids: dict[str, set[str]] = {table:{str(r.get("id")) for r in records.get(table,[]) if r.get("id") is not None} for table in BACKUP_TABLES}
            for table in BACKUP_TABLES:
                for row in records.get(table,[]):
                    if int(row.get("tenant_id",-1)) != int(tid): errors.append(f"{table} record {row.get('id')} crosses the tenant boundary")
            for row in records.get("salops_preparedness_training",[]):
                if row.get("plan_id") and str(row["plan_id"]) not in ids["salops_preparedness_plans"]: errors.append(f"training {row.get('id')} has invalid plan_id")
            for row in records.get("salops_preparedness_exercises",[]):
                if row.get("plan_id") and str(row["plan_id"]) not in ids["salops_preparedness_plans"]: errors.append(f"exercise {row.get('id')} has invalid plan_id")
            for row in records.get("salops_preparedness_injects",[]):
                if str(row.get("exercise_id")) not in ids["salops_preparedness_exercises"]: errors.append(f"inject {row.get('id')} has invalid exercise_id")
            for row in records.get("salops_preparedness_observations",[]):
                if str(row.get("exercise_id")) not in ids["salops_preparedness_exercises"]: errors.append(f"observation {row.get('id')} has invalid exercise_id")
            for row in records.get("salops_preparedness_aars",[]):
                if str(row.get("exercise_id")) not in ids["salops_preparedness_exercises"]: errors.append(f"AAR {row.get('id')} has invalid exercise_id")
            return errors

        def extended_validate(records: dict, tid: Optional[int] = None):
            errors = list(original_validate(records, tid))
            if tid is not None: errors.extend(prep_validate(records, int(tid)))
            return errors

        def insert_row(conn, table: str, row: dict[str, Any]) -> None:
            allowed={r["name"] for r in conn.execute(f"PRAGMA table_info({table})")};data={k:v for k,v in row.items() if k in allowed}
            if not data:return
            conn.execute(f"INSERT INTO {table}({','.join(data)}) VALUES({','.join('?'*len(data))})",tuple(data.values()))

        def extended_replace(conn, tid: int, records: dict):
            errors=list(original_validate(records,tid))+prep_validate(records,tid)
            if errors: raise ValueError("; ".join(errors))
            for table in DELETE_ORDER: conn.execute(f"DELETE FROM {table} WHERE tenant_id=?",(tid,))
            original_replace(conn,tid,records)
            for table in RESTORE_ORDER:
                for row in records.get(table,[]): insert_row(conn,table,row)

        core["collect_tenant_records"] = extended_collect
        core["validate_records"] = extended_validate
        core["replace_tenant_records"] = extended_replace
