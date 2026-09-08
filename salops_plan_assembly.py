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
CANDIDATE_STATES = ("Draft Candidate", "Candidate Reviewed", "Returned for Revision", "Accepted for Plan Revision", "Rejected")
PLAN_IMPACT_SOURCE_TYPES = (
    "SalINTEL Qualified Investigation", "SalINTEL Qualified Finding",
    "SalINTEL Monitoring Review", "SalTHIRA Reassessment Trigger",
    "SalOPS Exercise", "SalOPS Observation", "SalOPS Corrective Action",
    "PROVE Released Assurance", "Governed Material",
)
PLAN_IMPACT_DECISIONS = ("Material Change", "No Material Change", "More Collection Required")
RESEARCH_COST_CATEGORIES = (
    "Chat / AI", "Salus Human Labor", "External Data", "Approved Partner", "Other Direct",
)
RESEARCH_COST_MEASUREMENTS = ("Actual Metered", "Provider Estimate", "Planning Allowance Applied")
PREPAREDNESS_HANDOFF_TYPES = ("Training", "Exercise", "Validation", "SalTHIRA Reassessment")
PREPAREDNESS_HANDOFF_STATES = ("Pending Human Review", "Accepted", "Rejected", "Materialized")
PLAN_SECTION_FIELDS = {
    "authorities": "authorities_references", "authorities_references": "authorities_references",
    "assumptions": "assumptions", "roles": "roles_responsibilities",
    "roles_responsibilities": "roles_responsibilities", "concept_of_operations": "concept_of_operations",
    "activation": "activation_criteria", "activation_criteria": "activation_criteria",
    "command": "command_coordination", "command_coordination": "command_coordination",
    "communications": "communications", "resources": "resource_requirements",
    "resource_requirements": "resource_requirements", "dependencies": "dependencies",
    "alternate_capability": "alternate_capability", "checklists": "checklists_job_aids",
    "checklists_job_aids": "checklists_job_aids", "annexes": "annexes_appendices",
    "annexes_appendices": "annexes_appendices", "training": "training_requirements",
    "training_requirements": "training_requirements", "exercise_validation": "exercise_validation_requirements",
    "exercise_validation_requirements": "exercise_validation_requirements",
}


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
  proposed_reassessment_actions_json TEXT NOT NULL DEFAULT '[]',
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

CREATE TABLE IF NOT EXISTS salops_plan_version_candidates (
  id TEXT PRIMARY KEY,
  tenant_id INTEGER NOT NULL,
  run_id TEXT NOT NULL,
  revision_recommendation_id TEXT,
  baseline_plan_id TEXT,
  baseline_plan_version INTEGER NOT NULL DEFAULT 0,
  baseline_plan_sha256 TEXT NOT NULL DEFAULT '',
  suggested_plan_version INTEGER NOT NULL,
  candidate_snapshot_json TEXT NOT NULL,
  section_manifest_json TEXT NOT NULL DEFAULT '[]',
  diff_manifest_json TEXT NOT NULL DEFAULT '[]',
  source_manifest_json TEXT NOT NULL DEFAULT '[]',
  unresolved_items_json TEXT NOT NULL DEFAULT '[]',
  candidate_sha256 TEXT NOT NULL,
  status TEXT NOT NULL DEFAULT 'Draft Candidate',
  rationale TEXT NOT NULL,
  immutable_content INTEGER NOT NULL DEFAULT 1,
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
  accepted_by TEXT NOT NULL DEFAULT '',
  accepted_at TEXT NOT NULL DEFAULT '',
  acceptance_reason TEXT NOT NULL DEFAULT '',
  UNIQUE(tenant_id,run_id),
  FOREIGN KEY (run_id) REFERENCES salops_plan_assembly_runs(id) ON DELETE CASCADE,
  FOREIGN KEY (revision_recommendation_id) REFERENCES salops_plan_revision_recommendations(id) ON DELETE RESTRICT,
  FOREIGN KEY (baseline_plan_id) REFERENCES salops_preparedness_plans(id) ON DELETE RESTRICT
);
CREATE INDEX IF NOT EXISTS idx_plan_version_candidates_scope ON salops_plan_version_candidates(tenant_id,status,baseline_plan_id,created_at);

CREATE TABLE IF NOT EXISTS salops_plan_materializations (
  id TEXT PRIMARY KEY,
  tenant_id INTEGER NOT NULL,
  candidate_id TEXT NOT NULL,
  baseline_plan_id TEXT,
  baseline_plan_version INTEGER NOT NULL DEFAULT 0,
  baseline_plan_sha256 TEXT NOT NULL DEFAULT '',
  draft_plan_id TEXT NOT NULL,
  draft_plan_version INTEGER NOT NULL,
  candidate_sha256 TEXT NOT NULL,
  draft_plan_snapshot_json TEXT NOT NULL,
  draft_plan_sha256 TEXT NOT NULL,
  unmapped_sections_json TEXT NOT NULL DEFAULT '[]',
  status TEXT NOT NULL DEFAULT 'Draft Materialized',
  reason TEXT NOT NULL,
  approved_plan_preserved INTEGER NOT NULL DEFAULT 1,
  creates_plan_version INTEGER NOT NULL DEFAULT 1,
  creates_release INTEGER NOT NULL DEFAULT 0,
  creates_authority INTEGER NOT NULL DEFAULT 0,
  creates_charge INTEGER NOT NULL DEFAULT 0,
  created_by TEXT NOT NULL,
  created_at TEXT NOT NULL,
  UNIQUE(tenant_id,candidate_id),
  UNIQUE(tenant_id,draft_plan_id),
  FOREIGN KEY (candidate_id) REFERENCES salops_plan_version_candidates(id) ON DELETE RESTRICT,
  FOREIGN KEY (baseline_plan_id) REFERENCES salops_preparedness_plans(id) ON DELETE RESTRICT,
  FOREIGN KEY (draft_plan_id) REFERENCES salops_preparedness_plans(id) ON DELETE RESTRICT
);
CREATE INDEX IF NOT EXISTS idx_plan_materializations_scope ON salops_plan_materializations(tenant_id,status,baseline_plan_id,draft_plan_id,created_at);

CREATE TABLE IF NOT EXISTS salops_plan_successor_governance (
  id TEXT PRIMARY KEY,
  tenant_id INTEGER NOT NULL,
  materialization_id TEXT NOT NULL,
  baseline_plan_id TEXT,
  baseline_plan_version INTEGER NOT NULL,
  baseline_plan_sha256 TEXT NOT NULL,
  draft_plan_id TEXT NOT NULL,
  draft_plan_version INTEGER NOT NULL,
  candidate_id TEXT NOT NULL,
  candidate_sha256 TEXT NOT NULL,
  status TEXT NOT NULL DEFAULT 'Pending Review',
  review_snapshot_json TEXT NOT NULL DEFAULT '{}',
  review_snapshot_sha256 TEXT NOT NULL DEFAULT '',
  reviewed_by TEXT NOT NULL DEFAULT '',
  reviewed_at TEXT NOT NULL DEFAULT '',
  review_reason TEXT NOT NULL DEFAULT '',
  approval_snapshot_json TEXT NOT NULL DEFAULT '{}',
  approval_snapshot_sha256 TEXT NOT NULL DEFAULT '',
  approved_by TEXT NOT NULL DEFAULT '',
  approved_at TEXT NOT NULL DEFAULT '',
  approval_reason TEXT NOT NULL DEFAULT '',
  released_plan_id TEXT,
  released_plan_snapshot_json TEXT NOT NULL DEFAULT '{}',
  released_plan_sha256 TEXT NOT NULL DEFAULT '',
  released_by TEXT NOT NULL DEFAULT '',
  released_at TEXT NOT NULL DEFAULT '',
  release_reason TEXT NOT NULL DEFAULT '',
  authority_confirmed INTEGER NOT NULL DEFAULT 0,
  disclosure_authorized INTEGER NOT NULL DEFAULT 0,
  unresolved_items_accepted INTEGER NOT NULL DEFAULT 0,
  approved_baseline_preserved INTEGER NOT NULL DEFAULT 1,
  creates_release INTEGER NOT NULL DEFAULT 0,
  creates_authority INTEGER NOT NULL DEFAULT 0,
  creates_charge INTEGER NOT NULL DEFAULT 0,
  created_by TEXT NOT NULL,
  created_at TEXT NOT NULL,
  UNIQUE(tenant_id,materialization_id),
  FOREIGN KEY (materialization_id) REFERENCES salops_plan_materializations(id) ON DELETE RESTRICT,
  FOREIGN KEY (baseline_plan_id) REFERENCES salops_preparedness_plans(id) ON DELETE RESTRICT,
  FOREIGN KEY (draft_plan_id) REFERENCES salops_preparedness_plans(id) ON DELETE RESTRICT,
  FOREIGN KEY (candidate_id) REFERENCES salops_plan_version_candidates(id) ON DELETE RESTRICT
);
CREATE INDEX IF NOT EXISTS idx_plan_successor_governance_scope ON salops_plan_successor_governance(tenant_id,status,baseline_plan_id,draft_plan_id,created_at);

CREATE TABLE IF NOT EXISTS salops_plan_successor_events (
  id TEXT PRIMARY KEY,
  tenant_id INTEGER NOT NULL,
  governance_id TEXT NOT NULL,
  event_no INTEGER NOT NULL,
  event_type TEXT NOT NULL,
  reason TEXT NOT NULL,
  snapshot_json TEXT NOT NULL,
  changed_by TEXT NOT NULL,
  changed_by_role TEXT NOT NULL,
  created_at TEXT NOT NULL,
  UNIQUE(tenant_id,governance_id,event_no),
  FOREIGN KEY (governance_id) REFERENCES salops_plan_successor_governance(id) ON DELETE CASCADE
);
CREATE INDEX IF NOT EXISTS idx_plan_successor_events_scope ON salops_plan_successor_events(tenant_id,governance_id,event_no);

CREATE TABLE IF NOT EXISTS salops_plan_preparedness_handoffs (
  id TEXT PRIMARY KEY,
  tenant_id INTEGER NOT NULL,
  run_id TEXT NOT NULL,
  governance_id TEXT NOT NULL,
  released_plan_id TEXT NOT NULL,
  handoff_type TEXT NOT NULL,
  recommendation TEXT NOT NULL,
  recommendation_sha256 TEXT NOT NULL,
  proposal_snapshot_json TEXT NOT NULL,
  proposal_sha256 TEXT NOT NULL,
  status TEXT NOT NULL DEFAULT 'Pending Human Review',
  target_record_type TEXT NOT NULL DEFAULT '',
  target_record_id TEXT NOT NULL DEFAULT '',
  creates_schedule INTEGER NOT NULL DEFAULT 0,
  creates_release INTEGER NOT NULL DEFAULT 0,
  creates_authority INTEGER NOT NULL DEFAULT 0,
  creates_charge INTEGER NOT NULL DEFAULT 0,
  created_by TEXT NOT NULL,
  created_at TEXT NOT NULL,
  reviewed_by TEXT NOT NULL DEFAULT '',
  reviewed_at TEXT NOT NULL DEFAULT '',
  review_reason TEXT NOT NULL DEFAULT '',
  materialized_by TEXT NOT NULL DEFAULT '',
  materialized_at TEXT NOT NULL DEFAULT '',
  materialization_reason TEXT NOT NULL DEFAULT '',
  UNIQUE(tenant_id,run_id,handoff_type,recommendation_sha256),
  FOREIGN KEY (run_id) REFERENCES salops_plan_assembly_runs(id) ON DELETE RESTRICT,
  FOREIGN KEY (governance_id) REFERENCES salops_plan_successor_governance(id) ON DELETE RESTRICT,
  FOREIGN KEY (released_plan_id) REFERENCES salops_preparedness_plans(id) ON DELETE RESTRICT
);
CREATE INDEX IF NOT EXISTS idx_plan_preparedness_handoffs_scope ON salops_plan_preparedness_handoffs(tenant_id,run_id,status,handoff_type,created_at);

CREATE TABLE IF NOT EXISTS salops_plan_preparedness_handoff_events (
  id TEXT PRIMARY KEY,
  tenant_id INTEGER NOT NULL,
  handoff_id TEXT NOT NULL,
  event_no INTEGER NOT NULL,
  event_type TEXT NOT NULL,
  reason TEXT NOT NULL,
  snapshot_json TEXT NOT NULL,
  changed_by TEXT NOT NULL,
  changed_by_role TEXT NOT NULL,
  created_at TEXT NOT NULL,
  UNIQUE(tenant_id,handoff_id,event_no),
  FOREIGN KEY (handoff_id) REFERENCES salops_plan_preparedness_handoffs(id) ON DELETE CASCADE
);
CREATE INDEX IF NOT EXISTS idx_plan_preparedness_handoff_events_scope ON salops_plan_preparedness_handoff_events(tenant_id,handoff_id,event_no);

CREATE TABLE IF NOT EXISTS salops_plan_research_cost_envelopes (
  id TEXT PRIMARY KEY,
  tenant_id INTEGER NOT NULL,
  run_id TEXT NOT NULL,
  envelope_version INTEGER NOT NULL,
  currency TEXT NOT NULL DEFAULT 'USD',
  estimated_chat_ai_cost_cents INTEGER NOT NULL DEFAULT 0,
  estimated_human_cost_cents INTEGER NOT NULL DEFAULT 0,
  external_data_allowance_cents INTEGER NOT NULL DEFAULT 0,
  partner_allowance_cents INTEGER NOT NULL DEFAULT 0,
  other_direct_allowance_cents INTEGER NOT NULL DEFAULT 0,
  maximum_authorized_cost_cents INTEGER NOT NULL,
  scope_basis TEXT NOT NULL,
  commercial_reference TEXT NOT NULL DEFAULT '',
  status TEXT NOT NULL DEFAULT 'Draft',
  content_sha256 TEXT NOT NULL,
  creates_customer_price INTEGER NOT NULL DEFAULT 0,
  creates_charge INTEGER NOT NULL DEFAULT 0,
  creates_invoice INTEGER NOT NULL DEFAULT 0,
  created_by TEXT NOT NULL,
  created_at TEXT NOT NULL,
  authorized_by TEXT NOT NULL DEFAULT '',
  authorized_at TEXT NOT NULL DEFAULT '',
  authorization_reason TEXT NOT NULL DEFAULT '',
  UNIQUE(tenant_id,run_id,envelope_version),
  FOREIGN KEY (run_id) REFERENCES salops_plan_assembly_runs(id) ON DELETE CASCADE
);
CREATE INDEX IF NOT EXISTS idx_plan_research_cost_envelopes_scope ON salops_plan_research_cost_envelopes(tenant_id,run_id,status,envelope_version);

CREATE TABLE IF NOT EXISTS salops_plan_research_cost_usage (
  id TEXT PRIMARY KEY,
  tenant_id INTEGER NOT NULL,
  run_id TEXT NOT NULL,
  envelope_id TEXT NOT NULL,
  category TEXT NOT NULL,
  provider_tool TEXT NOT NULL DEFAULT '',
  task_reference TEXT NOT NULL,
  metered_units_json TEXT NOT NULL DEFAULT '{}',
  measurement_status TEXT NOT NULL,
  amount_cents INTEGER NOT NULL,
  occurred_at TEXT NOT NULL,
  recording_basis TEXT NOT NULL,
  creates_customer_price INTEGER NOT NULL DEFAULT 0,
  creates_charge INTEGER NOT NULL DEFAULT 0,
  creates_invoice INTEGER NOT NULL DEFAULT 0,
  recorded_by TEXT NOT NULL,
  recorded_at TEXT NOT NULL,
  FOREIGN KEY (run_id) REFERENCES salops_plan_assembly_runs(id) ON DELETE CASCADE,
  FOREIGN KEY (envelope_id) REFERENCES salops_plan_research_cost_envelopes(id) ON DELETE RESTRICT
);
CREATE INDEX IF NOT EXISTS idx_plan_research_cost_usage_scope ON salops_plan_research_cost_usage(tenant_id,run_id,envelope_id,category,occurred_at);

CREATE TABLE IF NOT EXISTS salops_plan_impact_detections (
  id TEXT PRIMARY KEY,
  tenant_id INTEGER NOT NULL,
  approved_plan_id TEXT NOT NULL,
  approved_plan_version INTEGER NOT NULL,
  approved_plan_sha256 TEXT NOT NULL,
  source_record_type TEXT NOT NULL,
  source_record_id TEXT NOT NULL,
  source_snapshot_json TEXT NOT NULL,
  source_sha256 TEXT NOT NULL,
  source_recorded_at TEXT NOT NULL,
  source_title TEXT NOT NULL,
  temporal_relation TEXT NOT NULL,
  change_summary TEXT NOT NULL,
  suggested_affected_sections_json TEXT NOT NULL DEFAULT '[]',
  detection_reasons_json TEXT NOT NULL DEFAULT '[]',
  research_questions_json TEXT NOT NULL DEFAULT '[]',
  known_unknowns_json TEXT NOT NULL DEFAULT '[]',
  status TEXT NOT NULL DEFAULT 'Potential Impact',
  materiality_decision TEXT NOT NULL DEFAULT 'Not Reviewed',
  confirmed_affected_sections_json TEXT NOT NULL DEFAULT '[]',
  revision_recommended INTEGER NOT NULL DEFAULT 0,
  revision_recommendation TEXT NOT NULL DEFAULT '',
  assembly_run_id TEXT,
  server_detected INTEGER NOT NULL DEFAULT 1,
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
  UNIQUE(tenant_id,approved_plan_id,source_record_type,source_record_id,source_sha256),
  FOREIGN KEY (approved_plan_id) REFERENCES salops_preparedness_plans(id) ON DELETE RESTRICT,
  FOREIGN KEY (assembly_run_id) REFERENCES salops_plan_assembly_runs(id) ON DELETE RESTRICT
);
CREATE INDEX IF NOT EXISTS idx_plan_impact_detections_scope ON salops_plan_impact_detections(tenant_id,status,approved_plan_id,created_at);

CREATE TABLE IF NOT EXISTS salops_plan_impact_events (
  id TEXT PRIMARY KEY,
  tenant_id INTEGER NOT NULL,
  detection_id TEXT NOT NULL,
  event_no INTEGER NOT NULL,
  event_type TEXT NOT NULL,
  reason TEXT NOT NULL,
  snapshot_json TEXT NOT NULL,
  changed_by TEXT NOT NULL,
  changed_by_role TEXT NOT NULL,
  created_at TEXT NOT NULL,
  UNIQUE(tenant_id,detection_id,event_no),
  FOREIGN KEY (detection_id) REFERENCES salops_plan_impact_detections(id) ON DELETE CASCADE
);
CREATE INDEX IF NOT EXISTS idx_plan_impact_events_scope ON salops_plan_impact_events(tenant_id,detection_id,event_no);

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
        "proposed_validation_actions", "proposed_reassessment_actions",
    ),
    "salops_plan_assembly_sources": ("source_derived_statements",),
    "salops_plan_assembly_questions": ("related_section_keys",),
    "salops_plan_assembly_sections": (
        "source_refs", "epistemic_items", "unsupported_assumptions", "known_unknowns",
        "dependencies", "alternate_capabilities", "capability_gaps",
    ),
    "salops_plan_revision_recommendations": ("affected_sections", "supporting_source_refs"),
    "salops_plan_version_candidates": (
        "candidate_snapshot", "section_manifest", "diff_manifest", "source_manifest",
        "unresolved_items",
    ),
    "salops_plan_materializations": ("draft_plan_snapshot", "unmapped_sections"),
    "salops_plan_successor_governance": (
        "review_snapshot", "approval_snapshot", "released_plan_snapshot",
    ),
    "salops_plan_preparedness_handoffs": ("proposal_snapshot",),
    "salops_plan_research_cost_usage": ("metered_units",),
    "salops_plan_impact_detections": (
        "source_snapshot", "suggested_affected_sections", "detection_reasons",
        "research_questions", "known_unknowns", "confirmed_affected_sections",
    ),
}
BACKUP_TABLES = (
    "salops_plan_assembly_runs", "salops_plan_assembly_sources",
    "salops_plan_assembly_questions", "salops_plan_assembly_sections",
    "salops_plan_revision_recommendations", "salops_plan_version_candidates",
    "salops_plan_materializations",
    "salops_plan_successor_governance", "salops_plan_successor_events",
    "salops_plan_preparedness_handoffs", "salops_plan_preparedness_handoff_events",
    "salops_plan_research_cost_envelopes", "salops_plan_research_cost_usage",
    "salops_plan_impact_detections", "salops_plan_impact_events",
    "salops_plan_assembly_events",
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
    proposed_reassessment_actions: list[str] = Field(default_factory=list, max_length=300)
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


class VersionCandidateCreate(StrictModel):
    rationale: str = Field(min_length=3, max_length=12000)
    revision_recommendation_id: Optional[str] = Field(default=None, max_length=200)


class VersionCandidateReview(StrictModel):
    decision: Literal["Candidate Reviewed", "Returned for Revision", "Rejected"]
    reason: str = Field(min_length=3, max_length=8000)


class VersionCandidateAccept(StrictModel):
    reason: str = Field(min_length=3, max_length=8000)


class PlanMaterializeDraft(StrictModel):
    reason: str = Field(min_length=3, max_length=8000)


class PlanSuccessorReview(StrictModel):
    reason: str = Field(min_length=3, max_length=8000)


class PlanSuccessorApprove(StrictModel):
    reason: str = Field(min_length=3, max_length=8000)


class PlanSuccessorRelease(StrictModel):
    reason: str = Field(min_length=3, max_length=8000)
    authority_confirmed: Literal[True]
    disclosure_authorized: Literal[True]
    unresolved_items_accepted: Literal[True]


class PreparednessHandoffReview(StrictModel):
    decision: Literal["Accepted", "Rejected"]
    reason: str = Field(min_length=3, max_length=8000)


class PreparednessHandoffMaterialize(StrictModel):
    reason: str = Field(min_length=3, max_length=8000)


class ResearchCostEnvelopeCreate(StrictModel):
    currency: Literal["USD"] = "USD"
    estimated_chat_ai_cost_cents: int = Field(default=0, ge=0, le=100_000_000)
    estimated_human_cost_cents: int = Field(default=0, ge=0, le=100_000_000)
    external_data_allowance_cents: int = Field(default=0, ge=0, le=100_000_000)
    partner_allowance_cents: int = Field(default=0, ge=0, le=100_000_000)
    other_direct_allowance_cents: int = Field(default=0, ge=0, le=100_000_000)
    maximum_authorized_cost_cents: int = Field(ge=0, le=500_000_000)
    scope_basis: str = Field(min_length=3, max_length=8000)
    commercial_reference: str = Field(default="", max_length=1000)

    @model_validator(mode="after")
    def maximum_covers_planned_components(self):
        planned = (self.estimated_chat_ai_cost_cents + self.estimated_human_cost_cents
                   + self.external_data_allowance_cents + self.partner_allowance_cents
                   + self.other_direct_allowance_cents)
        if planned > self.maximum_authorized_cost_cents:
            raise ValueError("Maximum authorized cost must cover every planned component")
        return self


class ResearchCostEnvelopeAuthorize(StrictModel):
    reason: str = Field(min_length=3, max_length=8000)


class ResearchCostUsageCreate(StrictModel):
    category: Literal["Chat / AI", "Salus Human Labor", "External Data", "Approved Partner", "Other Direct"]
    provider_tool: str = Field(default="", max_length=500)
    task_reference: str = Field(min_length=1, max_length=1000)
    metered_units: dict[str, Any] = Field(default_factory=dict)
    measurement_status: Literal["Actual Metered", "Provider Estimate", "Planning Allowance Applied"]
    amount_cents: int = Field(ge=0, le=100_000_000)
    occurred_at: str = Field(min_length=3, max_length=100)
    recording_basis: str = Field(min_length=3, max_length=4000)


class PlanImpactDetect(StrictModel):
    source_record_type: Literal[
        "SalINTEL Qualified Investigation", "SalINTEL Qualified Finding",
        "SalINTEL Monitoring Review", "SalTHIRA Reassessment Trigger",
        "SalOPS Exercise", "SalOPS Observation", "SalOPS Corrective Action",
        "PROVE Released Assurance", "Governed Material",
    ]
    source_record_id: str = Field(min_length=1, max_length=200)
    change_summary: str = Field(min_length=3, max_length=12000)
    suggested_affected_sections: list[str] = Field(default_factory=list, max_length=100)
    detection_reasons: list[str] = Field(default_factory=list, max_length=100)
    research_questions: list[str] = Field(default_factory=list, max_length=100)
    known_unknowns: list[str] = Field(default_factory=list, max_length=100)

    @field_validator(
        "suggested_affected_sections", "detection_reasons", "research_questions",
        "known_unknowns",
    )
    @classmethod
    def clean_impact_lists(cls, value: list[str]) -> list[str]:
        cleaned = _clean_list(value)
        if any(len(item) > 2000 for item in cleaned):
            raise ValueError("Plan-impact entries may not exceed 2000 characters")
        return cleaned


class PlanImpactReview(StrictModel):
    decision: Literal["Material Change", "No Material Change", "More Collection Required"]
    reason: str = Field(min_length=3, max_length=8000)
    confirmed_affected_sections: list[str] = Field(default_factory=list, max_length=100)
    revision_recommendation: str = Field(default="", max_length=12000)

    @model_validator(mode="after")
    def material_decision_requires_recommendation(self):
        if self.decision == "Material Change" and not self.revision_recommendation.strip():
            raise ValueError("A Material Change decision requires a governed revision recommendation")
        return self


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
    try:
        conn.execute("SELECT proposed_reassessment_actions_json FROM salops_plan_assembly_runs LIMIT 0")
    except Exception:
        # PostgreSQL requires the failed statement transaction to be cleared before migration;
        # SQLite accepts the same rollback and portable ADD COLUMN definition.
        conn.rollback()
        conn.execute(
            "ALTER TABLE salops_plan_assembly_runs ADD COLUMN "
            "proposed_reassessment_actions_json TEXT NOT NULL DEFAULT '[]'"
        )
    legacy_materializations = list(conn.execute(
        """SELECT materialization.* FROM salops_plan_materializations materialization
           LEFT JOIN salops_plan_successor_governance governance
             ON governance.tenant_id=materialization.tenant_id
            AND governance.materialization_id=materialization.id
           WHERE governance.id IS NULL"""
    ))
    for item in legacy_materializations:
        materialization = dict(item)
        conn.execute(
            """INSERT INTO salops_plan_successor_governance(
            id,tenant_id,materialization_id,baseline_plan_id,baseline_plan_version,
            baseline_plan_sha256,draft_plan_id,draft_plan_version,candidate_id,candidate_sha256,
            status,created_by,created_at) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (_key("psg"), materialization["tenant_id"], materialization["id"],
             materialization.get("baseline_plan_id"), int(materialization.get("baseline_plan_version") or 0),
             materialization.get("baseline_plan_sha256") or "", materialization["draft_plan_id"],
             int(materialization["draft_plan_version"]), materialization["candidate_id"],
             materialization["candidate_sha256"], "Pending Review",
             materialization["created_by"], materialization["created_at"]),
        )
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
        for name in ("human_authority_required", "immutable_content", "server_detected",
                     "revision_recommended", "approved_plan_preserved", "creates_plan_version",
                     "approved_baseline_preserved", "authority_confirmed", "disclosure_authorized",
                     "unresolved_items_accepted",
                     "creates_schedule", "creates_release", "creates_authority", "creates_customer_price",
                     "creates_charge", "creates_invoice"):
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

    def latest_sections(conn, run_id: str, request: Request) -> list[dict[str, Any]]:
        rows = conn.execute(
            """SELECT section.* FROM salops_plan_assembly_sections section
               JOIN (SELECT section_key,MAX(section_version) latest_version
                     FROM salops_plan_assembly_sections
                     WHERE tenant_id=? AND run_id=? GROUP BY section_key) latest
                 ON latest.section_key=section.section_key AND latest.latest_version=section.section_version
               WHERE section.tenant_id=? AND section.run_id=? ORDER BY section.section_key""",
            (tenant_id(request), run_id, tenant_id(request), run_id),
        )
        return [decode("salops_plan_assembly_sections", dict(item)) for item in rows]

    def candidate_row(conn, candidate_id: str, request: Request) -> dict[str, Any]:
        row = conn.execute(
            "SELECT * FROM salops_plan_version_candidates WHERE id=? AND tenant_id=?",
            (candidate_id, tenant_id(request)),
        ).fetchone()
        if not row:
            raise HTTPException(404, "Plan-version candidate not found")
        data = dict(row)
        snapshot = _loads(data.get("candidate_snapshot_json"), {})
        if _digest(snapshot) != data.get("candidate_sha256"):
            raise HTTPException(409, "Plan-version candidate integrity verification failed")
        run = run_row(conn, data["run_id"], request)
        if require_sensitivity:
            require_sensitivity(request, str(run.get("sensitivity") or "Standard"))
        return data

    def materialization_row(conn, materialization_id: str, request: Request) -> dict[str, Any]:
        row = conn.execute(
            "SELECT * FROM salops_plan_materializations WHERE id=? AND tenant_id=?",
            (materialization_id, tenant_id(request)),
        ).fetchone()
        if not row:
            raise HTTPException(404, "Plan materialization not found")
        data = dict(row)
        snapshot = _loads(data.get("draft_plan_snapshot_json"), {})
        if not snapshot or _digest(snapshot) != data.get("draft_plan_sha256"):
            raise HTTPException(409, "Materialized Draft plan integrity verification failed")
        candidate = candidate_row(conn, data["candidate_id"], request)
        if candidate["candidate_sha256"] != data["candidate_sha256"]:
            raise HTTPException(409, "Materialized Draft candidate lineage verification failed")
        plan_row(conn, data["draft_plan_id"], request)
        return data

    def plan_proposal_snapshot(row: dict[str, Any]) -> dict[str, Any]:
        """Return plan meaning without mutable lifecycle and adoption fields."""
        excluded = {
            "status", "member_adoption_status", "member_adoption_reason", "member_adopted_by",
            "member_adopted_at", "updated_by", "updated_at", "reviewed_by", "reviewed_at",
            "approved_by", "approved_at",
        }
        return {key: value for key, value in row.items() if key not in excluded}

    def verify_baseline(conn, governance: dict[str, Any], request: Request) -> dict[str, Any]:
        if not governance.get("baseline_plan_id"):
            return {}
        baseline = plan_row(conn, governance["baseline_plan_id"], request)
        if (baseline["status"] != "Approved"
                or int(baseline["version"]) != int(governance["baseline_plan_version"])
                or _digest(baseline) != governance["baseline_plan_sha256"]):
            raise HTTPException(409, "The Approved baseline changed; successor governance is stopped")
        return baseline

    def successor_row(conn, materialization_id: str, request: Request) -> dict[str, Any]:
        materialization = materialization_row(conn, materialization_id, request)
        row = conn.execute(
            "SELECT * FROM salops_plan_successor_governance WHERE tenant_id=? AND materialization_id=?",
            (tenant_id(request), materialization_id),
        ).fetchone()
        if not row:
            raise HTTPException(409, "This materialized Draft has no controlled successor-governance record")
        data = dict(row)
        if (data["draft_plan_id"] != materialization["draft_plan_id"]
                or data["candidate_id"] != materialization["candidate_id"]
                or data["candidate_sha256"] != materialization["candidate_sha256"]):
            raise HTTPException(409, "Successor-plan lineage verification failed")
        for prefix in ("review", "approval", "released_plan"):
            snapshot = _loads(data.get(f"{prefix}_snapshot_json"), {})
            digest = str(data.get(f"{prefix}_snapshot_sha256") or "")
            if digest and (not snapshot or _digest(snapshot) != digest):
                raise HTTPException(409, f"Successor-plan {prefix.replace('_', ' ')} integrity verification failed")
        return data

    def successor_event(conn, governance: dict[str, Any], event_type: str,
                        reason: str, request: Request) -> None:
        number = int(conn.execute(
            "SELECT COUNT(*) c FROM salops_plan_successor_events WHERE tenant_id=? AND governance_id=?",
            (governance["tenant_id"], governance["id"]),
        ).fetchone()["c"]) + 1
        conn.execute(
            """INSERT INTO salops_plan_successor_events(
            id,tenant_id,governance_id,event_no,event_type,reason,snapshot_json,
            changed_by,changed_by_role,created_at) VALUES(?,?,?,?,?,?,?,?,?,?)""",
            (_key("pse"), governance["tenant_id"], governance["id"], number, event_type,
             reason, _json(governance), actor(request), role(request), now()),
        )
        audit(conn, f"SALOPS_PLAN_SUCCESSOR_{event_type.upper().replace(' ', '_')}",
              "salops_plan_successor_governance", None,
              f"{governance['id']}: {reason}"[:1000], actor(request))

    def handoff_row(conn, handoff_id: str, request: Request) -> dict[str, Any]:
        row = conn.execute(
            "SELECT * FROM salops_plan_preparedness_handoffs WHERE id=? AND tenant_id=?",
            (handoff_id, tenant_id(request)),
        ).fetchone()
        if not row:
            raise HTTPException(404, "Preparedness handoff not found")
        data = dict(row)
        proposal = _loads(data.get("proposal_snapshot_json"), {})
        if (_digest(data.get("recommendation") or "") != data.get("recommendation_sha256")
                or not proposal or _digest(proposal) != data.get("proposal_sha256")):
            raise HTTPException(409, "Preparedness handoff integrity verification failed")
        governance = conn.execute(
            "SELECT * FROM salops_plan_successor_governance WHERE id=? AND tenant_id=?",
            (data["governance_id"], tenant_id(request)),
        ).fetchone()
        if not governance or governance["status"] != "Released" or governance["released_plan_id"] != data["released_plan_id"]:
            raise HTTPException(409, "Preparedness handoff is not linked to a released governed successor")
        plan_row(conn, data["released_plan_id"], request)
        return data

    def handoff_event(conn, handoff: dict[str, Any], event_type: str,
                      reason: str, request: Request) -> None:
        number = int(conn.execute(
            "SELECT COUNT(*) c FROM salops_plan_preparedness_handoff_events WHERE tenant_id=? AND handoff_id=?",
            (handoff["tenant_id"], handoff["id"]),
        ).fetchone()["c"]) + 1
        conn.execute(
            """INSERT INTO salops_plan_preparedness_handoff_events(
            id,tenant_id,handoff_id,event_no,event_type,reason,snapshot_json,
            changed_by,changed_by_role,created_at) VALUES(?,?,?,?,?,?,?,?,?,?)""",
            (_key("phe"), handoff["tenant_id"], handoff["id"], number, event_type,
             reason, _json(handoff), actor(request), role(request), now()),
        )
        audit(conn, f"SALOPS_PLAN_HANDOFF_{event_type.upper().replace(' ', '_')}",
              "salops_plan_preparedness_handoffs", None,
              f"{handoff['id']}: {reason}"[:1000], actor(request))

    def create_preparedness_handoffs(conn, governance: dict[str, Any],
                                     released: dict[str, Any], request: Request) -> None:
        """Create inert, immutable proposals from qualified recommendations after plan release."""
        candidate = candidate_row(conn, governance["candidate_id"], request)
        run = run_row(conn, candidate["run_id"], request)
        recommendation_sets = (
            ("Training", _loads(run["proposed_training_actions_json"], [])),
            ("Exercise", _loads(run["proposed_exercise_actions_json"], [])),
            ("Validation", _loads(run["proposed_validation_actions_json"], [])),
            ("SalTHIRA Reassessment", _loads(run["proposed_reassessment_actions_json"], [])),
        )
        stamp, who = now(), actor(request)
        for handoff_type, recommendations in recommendation_sets:
            for recommendation in _clean_list([str(item) for item in recommendations]):
                recommendation_sha = _digest(recommendation)
                title = recommendation[:180].rstrip(" .") or f"{handoff_type} requirement"
                proposal = {
                    "schema": "salops.plan-preparedness-handoff.v1",
                    "handoff_type": handoff_type,
                    "recommendation": recommendation,
                    "title": title,
                    "run_id": run["id"],
                    "released_plan_id": released["id"],
                    "released_plan_version": int(released["version"]),
                    "assessment_id": released.get("assessment_id"),
                    "plan_title": released["title"],
                    "scope_statement": released["scope_statement"],
                    "portfolio_scope": _loads(released.get("portfolio_scope_json"), {}),
                    "mission_lenses": _loads(released.get("mission_lenses_json"), []),
                    "salthira_refs": _loads(released.get("salthira_refs_json"), []),
                    "sensitivity": released.get("sensitivity") or run["sensitivity"],
                    "source_refs": [f"plan-assembly:{run['id']}", f"plan:{released['id']}"],
                    "commercial_treatment": "Not Determined",
                    "creates_schedule": False,
                    "creates_release": False,
                    "creates_authority": False,
                    "creates_charge": False,
                }
                handoff_id = _key("phf")
                conn.execute(
                    """INSERT INTO salops_plan_preparedness_handoffs(
                    id,tenant_id,run_id,governance_id,released_plan_id,handoff_type,
                    recommendation,recommendation_sha256,proposal_snapshot_json,proposal_sha256,
                    status,creates_schedule,creates_release,creates_authority,creates_charge,
                    created_by,created_at) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                    (handoff_id, tenant_id(request), run["id"], governance["id"], released["id"],
                     handoff_type, recommendation, recommendation_sha, _json(proposal), _digest(proposal),
                     "Pending Human Review", 0, 0, 0, 0, who, stamp),
                )
                created = conn.execute(
                    "SELECT * FROM salops_plan_preparedness_handoffs WHERE id=?", (handoff_id,),
                ).fetchone()
                if created:
                    handoff_event(
                        conn, dict(created), "Proposal Created",
                        "Released-plan recommendation recorded for separate human review; no activity, schedule, release, authority, disclosure, or charge was created.",
                        request,
                    )

    def cost_envelope_content(data: dict[str, Any]) -> dict[str, Any]:
        return {name: data.get(name) for name in (
            "id", "tenant_id", "run_id", "envelope_version", "currency",
            "estimated_chat_ai_cost_cents", "estimated_human_cost_cents",
            "external_data_allowance_cents", "partner_allowance_cents",
            "other_direct_allowance_cents", "maximum_authorized_cost_cents",
            "scope_basis", "commercial_reference", "creates_customer_price",
            "creates_charge", "creates_invoice", "created_by", "created_at",
        )}

    def cost_envelope_row(conn, envelope_id: str, request: Request) -> dict[str, Any]:
        row = conn.execute(
            "SELECT * FROM salops_plan_research_cost_envelopes WHERE id=? AND tenant_id=?",
            (envelope_id, tenant_id(request)),
        ).fetchone()
        if not row:
            raise HTTPException(404, "Research-cost envelope not found")
        data = dict(row)
        if _digest(cost_envelope_content(data)) != data.get("content_sha256"):
            raise HTTPException(409, "Research-cost envelope integrity verification failed")
        run_row(conn, data["run_id"], request)
        return data

    def cost_summary(conn, run_id: str, envelope: dict[str, Any]) -> dict[str, Any]:
        usage = [decode("salops_plan_research_cost_usage", dict(item)) for item in conn.execute(
            "SELECT * FROM salops_plan_research_cost_usage WHERE tenant_id=? AND run_id=? AND envelope_id=? ORDER BY occurred_at,id",
            (envelope["tenant_id"], run_id, envelope["id"]),
        )]
        caps = {
            "Chat / AI": int(envelope["estimated_chat_ai_cost_cents"]),
            "Salus Human Labor": int(envelope["estimated_human_cost_cents"]),
            "External Data": int(envelope["external_data_allowance_cents"]),
            "Approved Partner": int(envelope["partner_allowance_cents"]),
            "Other Direct": int(envelope["other_direct_allowance_cents"]),
        }
        by_category = {category: sum(int(item["amount_cents"]) for item in usage if item["category"] == category)
                       for category in RESEARCH_COST_CATEGORIES}
        recognized = sum(by_category.values())
        actual = sum(int(item["amount_cents"]) for item in usage if item["measurement_status"] == "Actual Metered")
        return {
            "envelope": decode("salops_plan_research_cost_envelopes", envelope),
            "usage": usage,
            "category_caps_cents": caps,
            "recognized_cost_cents": recognized,
            "actual_metered_cost_cents": actual,
            "estimated_or_allowance_cost_cents": recognized - actual,
            "remaining_authorized_cost_cents": max(0, int(envelope["maximum_authorized_cost_cents"]) - recognized),
            "category_remaining_cents": {key: max(0, caps[key] - by_category[key]) for key in caps},
            "creates_customer_price": False, "creates_charge": False, "creates_invoice": False,
        }

    def impact_row(conn, detection_id: str, request: Request) -> dict[str, Any]:
        row = conn.execute(
            "SELECT * FROM salops_plan_impact_detections WHERE id=? AND tenant_id=?",
            (detection_id, tenant_id(request)),
        ).fetchone()
        if not row:
            raise HTTPException(404, "Plan-impact detection not found")
        data = dict(row)
        if _digest(_loads(data.get("source_snapshot_json"), {})) != data.get("source_sha256"):
            raise HTTPException(409, "Plan-impact source snapshot integrity verification failed")
        plan_row(conn, data["approved_plan_id"], request)
        return data

    def impact_event(conn, detection: dict[str, Any], event_type: str, reason: str, request: Request) -> None:
        number = int(conn.execute(
            "SELECT COUNT(*) c FROM salops_plan_impact_events WHERE tenant_id=? AND detection_id=?",
            (detection["tenant_id"], detection["id"]),
        ).fetchone()["c"]) + 1
        conn.execute(
            """INSERT INTO salops_plan_impact_events(
            id,tenant_id,detection_id,event_no,event_type,reason,snapshot_json,
            changed_by,changed_by_role,created_at) VALUES(?,?,?,?,?,?,?,?,?,?)""",
            (_key("pie"), detection["tenant_id"], detection["id"], number,
             event_type, reason, _json(detection), actor(request), role(request), now()),
        )
        audit(conn, f"SALOPS_PLAN_IMPACT_{event_type.upper().replace(' ', '_')}",
              "salops_plan_impact", None, f"{detection['id']}: {reason}"[:1000], actor(request))

    def numeric_source_id(value: str) -> int:
        try:
            number = int(value)
        except (TypeError, ValueError):
            raise HTTPException(422, "This governed source type requires a numeric record ID")
        if number <= 0:
            raise HTTPException(422, "Governed source record ID must be positive")
        return number

    def resolve_impact_source(conn, plan: dict[str, Any], source_type: str,
                              source_id: str, request: Request) -> tuple[dict[str, Any], str, str]:
        """Resolve an allowlisted source and derive title/time without trusting client state."""
        tid = tenant_id(request)
        row = None
        title_field, time_field = "title", "updated_at"
        if source_type == "SalINTEL Qualified Investigation":
            number = numeric_source_id(source_id)
            row = conn.execute(
                "SELECT * FROM salintel_investigations WHERE id=? AND tenant_id=?",
                (number, tid),
            ).fetchone()
            if row and row["qualification_status"] != "Qualified":
                raise HTTPException(409, "SalINTEL investigation must be human-qualified before plan-impact detection")
        elif source_type == "SalINTEL Qualified Finding":
            number = numeric_source_id(source_id)
            row = conn.execute("SELECT * FROM intel_findings WHERE id=? AND tenant_id=?", (number, tid)).fetchone()
            if row and row["status"] not in ("Qualified", "Sent to SalTHIRA"):
                raise HTTPException(409, "SalINTEL finding must be qualified before plan-impact detection")
            time_field = "qualified_at"
        elif source_type == "SalINTEL Monitoring Review":
            number = numeric_source_id(source_id)
            row = conn.execute(
                """SELECT item.* FROM salintel_investigation_items item
                   JOIN salintel_investigations investigation ON investigation.id=item.investigation_id
                   WHERE item.id=? AND item.tenant_id=? AND investigation.tenant_id=?""",
                (number, tid, tid),
            ).fetchone()
            if row:
                detail = _loads(row["detail"], {})
                if (detail.get("record_type") != "salintel_monitoring_outcome_review"
                        or detail.get("decision") != "Qualified" or detail.get("human_qualified") is not True):
                    raise HTTPException(409, "Monitoring source must be a separately qualified outcome review")
            time_field = "updated_at"
        elif source_type == "SalTHIRA Reassessment Trigger":
            number = numeric_source_id(source_id)
            row = conn.execute(
                """SELECT trigger.* FROM reassessment_triggers trigger
                   JOIN assessments assessment ON assessment.id=trigger.assessment_id
                   WHERE trigger.id=? AND assessment.tenant_id=?""", (number, tid),
            ).fetchone()
            if row and plan.get("assessment_id") and int(row["assessment_id"]) != int(plan["assessment_id"]):
                raise HTTPException(409, "SalTHIRA trigger is outside the approved plan assessment scope")
            title_field, time_field = "trigger_type", "updated_at"
        elif source_type == "SalOPS Exercise":
            row = conn.execute("SELECT * FROM salops_preparedness_exercises WHERE id=? AND tenant_id=?", (source_id, tid)).fetchone()
            if row and (row["plan_id"] != plan["id"] or row["status"] not in ("Completed", "Evaluated", "Closed")):
                raise HTTPException(409, "Exercise must be completed and explicitly linked to this approved plan")
        elif source_type == "SalOPS Observation":
            row = conn.execute(
                """SELECT observation.* FROM salops_preparedness_observations observation
                   JOIN salops_preparedness_exercises exercise ON exercise.id=observation.exercise_id
                   WHERE observation.id=? AND observation.tenant_id=? AND exercise.tenant_id=? AND exercise.plan_id=?""",
                (source_id, tid, tid, plan["id"]),
            ).fetchone()
            title_field = "title"
        elif source_type == "SalOPS Corrective Action":
            row = conn.execute("SELECT * FROM salops_preparedness_corrective_actions WHERE id=? AND tenant_id=?", (source_id, tid)).fetchone()
            if row and row["plan_id"] != plan["id"]:
                raise HTTPException(409, "Corrective action is not explicitly linked to this approved plan")
        elif source_type == "PROVE Released Assurance":
            number = numeric_source_id(source_id)
            row = conn.execute("SELECT * FROM report_versions WHERE id=? AND tenant_id=?", (number, tid)).fetchone()
            if row and (row["status"] != "Released" or not str(row["report_type"]).startswith("PROVE — ")):
                raise HTTPException(409, "PROVE source must be a released assurance package")
            if row and plan.get("assessment_id") and int(row["assessment_id"]) != int(plan["assessment_id"]):
                raise HTTPException(409, "PROVE package is outside the approved plan assessment scope")
            title_field, time_field = "report_type", "released_at"
        elif source_type == "Governed Material":
            number = numeric_source_id(source_id)
            row = conn.execute("SELECT * FROM materials WHERE id=? AND tenant_id=?", (number, tid)).fetchone()
            if row and row["disposition_status"] != "Active":
                raise HTTPException(409, "Governed material is not active")
            if row and str(row["scan_status"] or "").lower() in ("infected", "rejected", "blocked"):
                raise HTTPException(409, "Unsafe or rejected material cannot create a plan-impact detection")
            time_field = "updated_at"
        if not row:
            raise HTTPException(404, "Governed source record not found within this tenant and plan scope")
        data = dict(row)
        return data, str(data.get(title_field) or f"{source_type} {source_id}"), str(data.get(time_field) or data.get("created_at") or now())

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
        candidates = [decode("salops_plan_version_candidates", dict(item)) for item in conn.execute(
            "SELECT * FROM salops_plan_version_candidates WHERE tenant_id=? AND run_id=? ORDER BY created_at,id",
            (tenant_id(request), run_id),
        )]
        materializations = [decode("salops_plan_materializations", dict(item)) for item in conn.execute(
            """SELECT materialization.* FROM salops_plan_materializations materialization
               JOIN salops_plan_version_candidates candidate ON candidate.id=materialization.candidate_id
               WHERE materialization.tenant_id=? AND candidate.tenant_id=? AND candidate.run_id=?
               ORDER BY materialization.created_at,materialization.id""",
            (tenant_id(request), tenant_id(request), run_id),
        )]
        successor_governance = [decode("salops_plan_successor_governance", dict(item)) for item in conn.execute(
            """SELECT governance.* FROM salops_plan_successor_governance governance
               JOIN salops_plan_materializations materialization ON materialization.id=governance.materialization_id
               JOIN salops_plan_version_candidates candidate ON candidate.id=materialization.candidate_id
               WHERE governance.tenant_id=? AND candidate.tenant_id=? AND candidate.run_id=?
               ORDER BY governance.created_at,governance.id""",
            (tenant_id(request), tenant_id(request), run_id),
        )]
        preparedness_handoffs = [decode("salops_plan_preparedness_handoffs", handoff_row(conn, item["id"], request)) for item in conn.execute(
            "SELECT id FROM salops_plan_preparedness_handoffs WHERE tenant_id=? AND run_id=? ORDER BY created_at,id",
            (tenant_id(request), run_id),
        )]
        impacts = [decode("salops_plan_impact_detections", dict(item)) for item in conn.execute(
            "SELECT * FROM salops_plan_impact_detections WHERE tenant_id=? AND assembly_run_id=? ORDER BY created_at,id",
            (tenant_id(request), run_id),
        )]
        events = [dict(item) for item in conn.execute(
            "SELECT event_no,event_type,reason,changed_by,changed_by_role,created_at FROM salops_plan_assembly_events WHERE tenant_id=? AND run_id=? ORDER BY event_no",
            (tenant_id(request), run_id),
        )]
        cost_envelopes = [cost_summary(conn, run_id, dict(item)) for item in conn.execute(
            "SELECT * FROM salops_plan_research_cost_envelopes WHERE tenant_id=? AND run_id=? ORDER BY envelope_version",
            (tenant_id(request), run_id),
        )]
        return {"run": decode("salops_plan_assembly_runs", row), "sources": sources,
                "questions": questions, "sections": sections,
                "revision_recommendations": recommendations,
                "version_candidates": candidates, "plan_materializations": materializations,
                "plan_successor_governance": successor_governance,
                "preparedness_handoffs": preparedness_handoffs,
                "plan_impact_detections": impacts,
                "research_cost_envelopes": cost_envelopes,
                "events": events}

    @app.get("/api/salops/preparedness/plan-assembly/catalog")
    def catalog(request: Request):
        salus_access(request)
        return {
            "capability": "Autonomous Emergency-Plan Research & Assembly",
            "source_kinds": list(SOURCE_KINDS), "access_states": list(ACCESS_STATES),
            "epistemic_states": list(EPISTEMIC_STATES), "question_targets": list(QUESTION_TARGETS),
            "automated_draft_epistemic_states": [state for state in EPISTEMIC_STATES if state != "Verified Fact"],
            "workflow": list(RUN_STATES),
            "candidate_workflow": list(CANDIDATE_STATES),
            "plan_impact_source_types": list(PLAN_IMPACT_SOURCE_TYPES),
            "plan_impact_review_decisions": list(PLAN_IMPACT_DECISIONS),
            "research_cost_categories": list(RESEARCH_COST_CATEGORIES),
            "research_cost_measurements": list(RESEARCH_COST_MEASUREMENTS),
            "preparedness_handoff_types": list(PREPAREDNESS_HANDOFF_TYPES),
            "preparedness_handoff_workflow": list(PREPAREDNESS_HANDOFF_STATES),
            "research_cost_doctrine": {
                "default_paid_research_authorized": False,
                "new_scope_requires_new_envelope": True,
                "customer_price_separate": True,
                "automatic_charge": False,
            },
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

    @app.post("/api/salops/preparedness/plan-assembly/{run_id}/research-cost-envelopes")
    def create_research_cost_envelope(run_id: str, payload: ResearchCostEnvelopeCreate, request: Request):
        salus_access(request, "write")
        conn = db()
        try:
            run = run_row(conn, run_id, request)
            if run["status"] == "Rejected":
                raise HTTPException(409, "A rejected assembly run cannot receive a research-cost envelope")
            version = int(conn.execute(
                "SELECT COUNT(*) c FROM salops_plan_research_cost_envelopes WHERE tenant_id=? AND run_id=?",
                (tenant_id(request), run_id),
            ).fetchone()["c"]) + 1
            stamp, who, envelope_id = now(), actor(request), _key("parce")
            data = payload.model_dump()
            content = {
                "id": envelope_id, "tenant_id": tenant_id(request), "run_id": run_id,
                "envelope_version": version, **data,
                "creates_customer_price": 0, "creates_charge": 0, "creates_invoice": 0,
                "created_by": who, "created_at": stamp,
            }
            conn.execute(
                """INSERT INTO salops_plan_research_cost_envelopes(
                id,tenant_id,run_id,envelope_version,currency,estimated_chat_ai_cost_cents,
                estimated_human_cost_cents,external_data_allowance_cents,partner_allowance_cents,
                other_direct_allowance_cents,maximum_authorized_cost_cents,scope_basis,
                commercial_reference,status,content_sha256,creates_customer_price,creates_charge,
                creates_invoice,created_by,created_at) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                (envelope_id, tenant_id(request), run_id, version, data["currency"],
                 data["estimated_chat_ai_cost_cents"], data["estimated_human_cost_cents"],
                 data["external_data_allowance_cents"], data["partner_allowance_cents"],
                 data["other_direct_allowance_cents"], data["maximum_authorized_cost_cents"],
                 data["scope_basis"], data["commercial_reference"], "Draft", _digest(content),
                 0, 0, 0, who, stamp),
            )
            created = dict(conn.execute(
                "SELECT * FROM salops_plan_research_cost_envelopes WHERE id=?", (envelope_id,),
            ).fetchone())
            event(conn, run, "Research Cost Envelope Drafted",
                  f"{envelope_id} v{version}: internal delivery-cost proposal only; no paid activity, customer price, charge, or invoice authorized.", request)
            conn.commit()
            return cost_summary(conn, run_id, created)
        finally:
            conn.close()

    @app.post("/api/salops/preparedness/plan-assembly/research-cost-envelopes/{envelope_id}/authorize")
    def authorize_research_cost_envelope(envelope_id: str, payload: ResearchCostEnvelopeAuthorize, request: Request):
        salus_access(request, "write")
        if role(request) not in ("System Administrator", "Assessment Director", "Program Owner"):
            raise HTTPException(403, "This role cannot authorize a research-cost envelope")
        conn = db()
        try:
            envelope = cost_envelope_row(conn, envelope_id, request)
            if envelope["status"] != "Draft":
                raise HTTPException(409, "Only a Draft research-cost envelope can be authorized")
            stamp = now()
            conn.execute(
                "UPDATE salops_plan_research_cost_envelopes SET status='Superseded' WHERE tenant_id=? AND run_id=? AND status='Authorized'",
                (tenant_id(request), envelope["run_id"]),
            )
            conn.execute(
                """UPDATE salops_plan_research_cost_envelopes
                   SET status='Authorized',authorized_by=?,authorized_at=?,authorization_reason=?
                   WHERE id=? AND tenant_id=?""",
                (actor(request), stamp, payload.reason, envelope_id, tenant_id(request)),
            )
            updated = dict(conn.execute(
                "SELECT * FROM salops_plan_research_cost_envelopes WHERE id=?", (envelope_id,),
            ).fetchone())
            run = run_row(conn, envelope["run_id"], request)
            event(conn, run, "Research Cost Envelope Authorized",
                  f"{envelope_id} v{envelope['envelope_version']}: maximum internal delivery cost {envelope['currency']} {int(envelope['maximum_authorized_cost_cents']) / 100:.2f}; exceeding a component or total requires a new governed envelope; no customer price, charge, or invoice created.", request)
            conn.commit()
            return cost_summary(conn, envelope["run_id"], updated)
        finally:
            conn.close()

    @app.post("/api/salops/preparedness/plan-assembly/research-cost-envelopes/{envelope_id}/usage")
    def record_research_cost_usage(envelope_id: str, payload: ResearchCostUsageCreate, request: Request):
        salus_access(request, "write")
        conn = db()
        try:
            envelope = cost_envelope_row(conn, envelope_id, request)
            if envelope["status"] != "Authorized":
                raise HTTPException(409, "Paid or metered research requires the current Authorized cost envelope")
            summary = cost_summary(conn, envelope["run_id"], envelope)
            cap = int(summary["category_caps_cents"][payload.category])
            remaining_category = int(summary["category_remaining_cents"][payload.category])
            remaining_total = int(summary["remaining_authorized_cost_cents"])
            if payload.amount_cents > remaining_category or payload.amount_cents > remaining_total:
                raise HTTPException(
                    409,
                    f"Research cost exceeds the authorized {payload.category} or total ceiling; create and separately authorize a new governed envelope before incurring more cost",
                )
            data, usage_id, stamp = payload.model_dump(), _key("parcu"), now()
            conn.execute(
                """INSERT INTO salops_plan_research_cost_usage(
                id,tenant_id,run_id,envelope_id,category,provider_tool,task_reference,
                metered_units_json,measurement_status,amount_cents,occurred_at,recording_basis,
                creates_customer_price,creates_charge,creates_invoice,recorded_by,recorded_at)
                VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                (usage_id, tenant_id(request), envelope["run_id"], envelope_id,
                 data["category"], data["provider_tool"], data["task_reference"],
                 _json(data["metered_units"]), data["measurement_status"], data["amount_cents"],
                 data["occurred_at"], data["recording_basis"], 0, 0, 0, actor(request), stamp),
            )
            run = run_row(conn, envelope["run_id"], request)
            event(conn, run, "Research Cost Usage Recorded",
                  f"{usage_id}: {data['category']} {envelope['currency']} {data['amount_cents'] / 100:.2f} recorded as {data['measurement_status']} against envelope v{envelope['envelope_version']}; no customer price, charge, or invoice created.", request)
            conn.commit()
            refreshed = cost_envelope_row(conn, envelope_id, request)
            return cost_summary(conn, envelope["run_id"], refreshed)
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
                "proposed_reassessment_actions_json": _json(data["proposed_reassessment_actions"]),
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

    @app.post("/api/salops/preparedness/plan-assembly/{run_id}/version-candidates")
    def create_version_candidate(run_id: str, payload: VersionCandidateCreate, request: Request):
        """Freeze server-derived proposed content without creating or replacing a plan."""
        salus_access(request, "write")
        if role(request) not in ("System Administrator", "Assessment Director", "Program Owner"):
            raise HTTPException(403, "This role cannot create a governed plan-version candidate")
        conn = db()
        try:
            run = run_row(conn, run_id, request)
            if run["status"] != "Qualified":
                raise HTTPException(409, "A plan-version candidate requires a human-reviewed, qualified assembly run")
            duplicate = conn.execute(
                "SELECT id FROM salops_plan_version_candidates WHERE tenant_id=? AND run_id=?",
                (tenant_id(request), run_id),
            ).fetchone()
            if duplicate:
                raise HTTPException(409, "This qualified run already has an immutable plan-version candidate")

            recommendation: Optional[dict[str, Any]] = None
            baseline: dict[str, Any] = {}
            if run.get("base_plan_id"):
                baseline = plan_row(conn, run["base_plan_id"], request)
                if (run["base_plan_status"] != "Approved" or baseline["status"] != "Approved"
                        or int(baseline["version"]) != int(run["base_plan_version"])
                        or _digest(baseline) != run["base_plan_sha256"]):
                    raise HTTPException(409, "The approved baseline changed; start a new assembly run before preparing a candidate")
                if not payload.revision_recommendation_id:
                    raise HTTPException(409, "A revision candidate requires an accepted material-change recommendation")
                rec_row = conn.execute(
                    "SELECT * FROM salops_plan_revision_recommendations WHERE id=? AND tenant_id=? AND run_id=?",
                    (payload.revision_recommendation_id, tenant_id(request), run_id),
                ).fetchone()
                if not rec_row or rec_row["status"] != "Accepted for Drafting":
                    raise HTTPException(409, "The linked revision recommendation must be accepted for drafting")
                recommendation = dict(rec_row)
            elif payload.revision_recommendation_id:
                raise HTTPException(422, "A new-plan candidate cannot claim a revision recommendation")

            sections = latest_sections(conn, run_id, request)
            if not sections:
                raise HTTPException(409, "A plan-version candidate requires at least one structured draft section")
            source_rows = [decode("salops_plan_assembly_sources", dict(item)) for item in conn.execute(
                "SELECT * FROM salops_plan_assembly_sources WHERE tenant_id=? AND run_id=? ORDER BY created_at,id",
                (tenant_id(request), run_id),
            )]
            diff_manifest = []
            for section in sections:
                plan_field = PLAN_SECTION_FIELDS.get(section["section_key"], "")
                before = str(baseline.get(plan_field) or "") if plan_field else ""
                after = str(section["content"])
                diff_manifest.append({
                    "section_key": section["section_key"], "plan_field": plan_field,
                    "change": "Unchanged" if before == after else ("Changed" if before else "Added"),
                    "baseline_content": before, "proposed_content": after,
                    "source_refs": section["source_refs"],
                    "human_authority_required": bool(section["human_authority_required"]),
                })
            source_manifest = [{
                "id": item["id"], "source_kind": item["source_kind"],
                "access_status": item["access_status"], "locator": item["locator"],
                "citation": item["citation"], "governed_material_id": item["governed_material_id"],
                "accessed_at": item["accessed_at"], "unavailable_reason": item["unavailable_reason"],
            } for item in source_rows]
            unresolved = _clean_list(
                _loads(run["known_unknowns_json"], []) + _loads(run["assumptions_to_validate_json"], [])
                + _loads(run["contradictions_json"], []) + _loads(run["missing_authorities_json"], [])
                + _loads(run["unresolved_dependencies_json"], [])
                + [item for section in sections for item in (
                    section["unsupported_assumptions"] + section["known_unknowns"] + section["capability_gaps"]
                )]
            )
            snapshot = {
                "schema": "salops.plan-version-candidate.v1", "run_id": run_id,
                "assembly_content_sha256": run["content_sha256"],
                "mode": run["assembly_mode"], "title": run["plan_title"], "plan_type": run["plan_type"],
                "purpose": run["purpose"], "scope_statement": run["scope_statement"],
                "portfolio_scope": _loads(run["portfolio_scope_json"], {}),
                "sensitivity": run["sensitivity"],
                "baseline": {"plan_id": run.get("base_plan_id") or "", "version": int(run["base_plan_version"]),
                             "sha256": run["base_plan_sha256"], "status": run["base_plan_status"]},
                "suggested_plan_version": int(run["base_plan_version"]) + 1 if baseline else 1,
                "sections": sections, "sources": source_manifest, "diff": diff_manifest,
                "unresolved_items": unresolved, "completion_statement": run["completion_statement"],
                "change_rationale": run["change_rationale"],
                "training_recommendations": _loads(run["proposed_training_actions_json"], []),
                "exercise_recommendations": _loads(run["proposed_exercise_actions_json"], []),
                "validation_recommendations": _loads(run["proposed_validation_actions_json"], []),
                "reassessment_recommendations": _loads(run["proposed_reassessment_actions_json"], []),
                "authority_effect": {"creates_plan_version": False, "creates_release": False,
                                     "creates_authority": False, "creates_charge": False},
            }
            candidate_id = _key("pvc")
            stamp = now()
            candidate_sha256 = _digest(snapshot)
            conn.execute(
                """INSERT INTO salops_plan_version_candidates(
                id,tenant_id,run_id,revision_recommendation_id,baseline_plan_id,baseline_plan_version,
                baseline_plan_sha256,suggested_plan_version,candidate_snapshot_json,section_manifest_json,
                diff_manifest_json,source_manifest_json,unresolved_items_json,candidate_sha256,status,rationale,
                immutable_content,approved_plan_preserved,creates_plan_version,creates_release,creates_authority,
                creates_charge,created_by,created_at)
                VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                (candidate_id, tenant_id(request), run_id,
                 recommendation["id"] if recommendation else None, run.get("base_plan_id"),
                 int(run["base_plan_version"]), run["base_plan_sha256"], snapshot["suggested_plan_version"],
                 _json(snapshot), _json(sections), _json(diff_manifest), _json(source_manifest),
                 _json(unresolved), candidate_sha256, "Draft Candidate", payload.rationale,
                 1, 1, 0, 0, 0, 0, actor(request), stamp),
            )
            created = candidate_row(conn, candidate_id, request)
            event(conn, run, "Version Candidate Created",
                  f"{candidate_id}: immutable proposed v{snapshot['suggested_plan_version']} candidate; approved baseline preserved and no plan version, authority, release, disclosure, or charge created.", request)
            conn.commit()
            return decode("salops_plan_version_candidates", created)
        finally:
            conn.close()

    @app.post("/api/salops/preparedness/plan-assembly/version-candidates/{candidate_id}/review")
    def review_version_candidate(candidate_id: str, payload: VersionCandidateReview, request: Request):
        salus_access(request, "write")
        if role(request) not in ("System Administrator", "Assessment Director", "Program Owner", "Lead Assessor"):
            raise HTTPException(403, "This role cannot review plan-version candidates")
        conn = db()
        try:
            candidate = candidate_row(conn, candidate_id, request)
            if candidate["status"] != "Draft Candidate":
                raise HTTPException(409, "Candidate review requires an immutable Draft Candidate")
            stamp = now()
            conn.execute(
                "UPDATE salops_plan_version_candidates SET status=?,reviewed_by=?,reviewed_at=?,review_reason=? WHERE id=? AND tenant_id=?",
                (payload.decision, actor(request), stamp, payload.reason, candidate_id, tenant_id(request)),
            )
            updated = candidate_row(conn, candidate_id, request)
            run = run_row(conn, updated["run_id"], request)
            event(conn, run, f"Version Candidate {payload.decision}",
                  f"{candidate_id}: {payload.reason}; immutable candidate content and approved plan remain unchanged.", request)
            conn.commit()
            return decode("salops_plan_version_candidates", updated)
        finally:
            conn.close()

    @app.post("/api/salops/preparedness/plan-assembly/version-candidates/{candidate_id}/accept")
    def accept_version_candidate(candidate_id: str, payload: VersionCandidateAccept, request: Request):
        salus_access(request, "write")
        if role(request) not in ("System Administrator", "Assessment Director", "Program Owner"):
            raise HTTPException(403, "This role cannot accept a candidate for governed plan revision")
        conn = db()
        try:
            candidate = candidate_row(conn, candidate_id, request)
            if candidate["status"] != "Candidate Reviewed":
                raise HTTPException(409, "Acceptance requires a separately reviewed plan-version candidate")
            if candidate.get("baseline_plan_id"):
                baseline = plan_row(conn, candidate["baseline_plan_id"], request)
                if (baseline["status"] != "Approved"
                        or int(baseline["version"]) != int(candidate["baseline_plan_version"])
                        or _digest(baseline) != candidate["baseline_plan_sha256"]):
                    raise HTTPException(409, "The approved baseline changed; this candidate cannot be accepted")
            stamp = now()
            conn.execute(
                """UPDATE salops_plan_version_candidates SET status='Accepted for Plan Revision',
                accepted_by=?,accepted_at=?,acceptance_reason=? WHERE id=? AND tenant_id=?""",
                (actor(request), stamp, payload.reason, candidate_id, tenant_id(request)),
            )
            updated = candidate_row(conn, candidate_id, request)
            run = run_row(conn, updated["run_id"], request)
            event(conn, run, "Version Candidate Accepted",
                  f"{candidate_id}: accepted only as governed revision input; approved plan remains unchanged and no plan version or release was created.", request)
            conn.commit()
            return decode("salops_plan_version_candidates", updated)
        finally:
            conn.close()

    @app.get("/api/salops/preparedness/plan-materializations")
    def list_plan_materializations(request: Request):
        salus_access(request)
        conn = db()
        try:
            rows = []
            for item in conn.execute(
                "SELECT id FROM salops_plan_materializations WHERE tenant_id=? ORDER BY created_at DESC,id",
                (tenant_id(request),),
            ):
                rows.append(decode("salops_plan_materializations", materialization_row(conn, item["id"], request)))
            return rows
        finally:
            conn.close()

    @app.post("/api/salops/preparedness/plan-assembly/version-candidates/{candidate_id}/materialize-draft")
    def materialize_plan_candidate(candidate_id: str, payload: PlanMaterializeDraft, request: Request):
        """Create a separate Draft plan record without changing the approved baseline."""
        salus_access(request, "write")
        if role(request) not in ("System Administrator", "Assessment Director", "Program Owner"):
            raise HTTPException(403, "This role cannot materialize a governed Draft plan version")
        conn = db()
        try:
            candidate = candidate_row(conn, candidate_id, request)
            if candidate["status"] != "Accepted for Plan Revision":
                raise HTTPException(409, "Draft materialization requires a separately reviewed and accepted candidate")
            duplicate = conn.execute(
                "SELECT id FROM salops_plan_materializations WHERE tenant_id=? AND candidate_id=?",
                (tenant_id(request), candidate_id),
            ).fetchone()
            if duplicate:
                raise HTTPException(409, "This immutable candidate has already been materialized")
            run = run_row(conn, candidate["run_id"], request)
            baseline: dict[str, Any] = {}
            if candidate.get("baseline_plan_id"):
                baseline = plan_row(conn, candidate["baseline_plan_id"], request)
                if (baseline["status"] != "Approved"
                        or int(baseline["version"]) != int(candidate["baseline_plan_version"])
                        or _digest(baseline) != candidate["baseline_plan_sha256"]):
                    raise HTTPException(409, "The Approved plan baseline changed; the candidate cannot be materialized")
            snapshot = _loads(candidate["candidate_snapshot_json"], {})
            diff = _loads(candidate["diff_manifest_json"], [])
            unmapped_sections = []
            plan_text = {
                field: str(baseline.get(field) or "")
                for field in set(PLAN_SECTION_FIELDS.values())
            }
            for item in diff:
                field = str(item.get("plan_field") or "")
                if field in plan_text:
                    plan_text[field] = str(item.get("proposed_content") or "")
                else:
                    unmapped_sections.append({
                        "section_key": str(item.get("section_key") or ""),
                        "reason": "Structured candidate section has no direct governed plan-record field and remains in the immutable candidate.",
                    })
            unresolved = _loads(candidate["unresolved_items_json"], [])
            existing_unknowns = str(baseline.get("known_unknowns") or "").strip()
            known_unknowns = "\n".join(_clean_list(
                ([existing_unknowns] if existing_unknowns else []) + [str(item) for item in unresolved]
            ))
            stamp, who = now(), actor(request)
            draft_id = _key("plan")
            draft_version = int(candidate["suggested_plan_version"])
            plan_columns = (
                "id", "tenant_id", "assessment_id", "title", "plan_type", "purpose", "scope_statement",
                "portfolio_scope_json", "mission_lenses_json", "authorities_references", "assumptions",
                "roles_responsibilities", "concept_of_operations", "activation_criteria", "command_coordination",
                "communications", "resource_requirements", "dependencies", "alternate_capability",
                "checklists_job_aids", "annexes_appendices", "training_requirements",
                "exercise_validation_requirements", "evidence_refs_json", "known_unknowns", "salintel_refs_json",
                "salthira_refs_json", "salops_refs_json", "sensitivity", "owner", "approver", "effective_date",
                "review_date", "expiration_date", "status", "commercial_treatment", "commercial_reference",
                "membership_entitlement_ref", "version", "created_by", "created_at", "updated_by", "updated_at",
            )
            plan_values = (
                draft_id, tenant_id(request), baseline.get("assessment_id"),
                str(snapshot.get("title") or run["plan_title"]),
                str(snapshot.get("plan_type") or run["plan_type"]),
                str(snapshot.get("purpose") or run["purpose"]),
                str(snapshot.get("scope_statement") or run["scope_statement"]),
                _json(snapshot.get("portfolio_scope") or _loads(baseline.get("portfolio_scope_json"), {})),
                baseline.get("mission_lenses_json") or "[]",
                plan_text["authorities_references"], plan_text["assumptions"],
                plan_text["roles_responsibilities"], plan_text["concept_of_operations"],
                plan_text["activation_criteria"], plan_text["command_coordination"],
                plan_text["communications"], plan_text["resource_requirements"], plan_text["dependencies"],
                plan_text["alternate_capability"], plan_text["checklists_job_aids"],
                plan_text["annexes_appendices"], plan_text["training_requirements"],
                plan_text["exercise_validation_requirements"], baseline.get("evidence_refs_json") or "[]",
                known_unknowns, baseline.get("salintel_refs_json") or "[]",
                baseline.get("salthira_refs_json") or "[]", baseline.get("salops_refs_json") or "[]",
                str(snapshot.get("sensitivity") or run["sensitivity"]),
                str(baseline.get("owner") or who), "", "", "", "", "Draft", "Not Determined", "", "",
                draft_version, who, stamp, who, stamp,
            )
            conn.execute(
                f"INSERT INTO salops_preparedness_plans({','.join(plan_columns)}) VALUES({','.join('?' * len(plan_columns))})",
                plan_values,
            )
            draft = plan_row(conn, draft_id, request)
            materialization_id = _key("pvm")
            conn.execute(
                """INSERT INTO salops_plan_materializations(
                id,tenant_id,candidate_id,baseline_plan_id,baseline_plan_version,baseline_plan_sha256,
                draft_plan_id,draft_plan_version,candidate_sha256,draft_plan_snapshot_json,draft_plan_sha256,
                unmapped_sections_json,status,reason,approved_plan_preserved,creates_plan_version,
                creates_release,creates_authority,creates_charge,created_by,created_at)
                VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                (materialization_id, tenant_id(request), candidate_id, candidate.get("baseline_plan_id"),
                 int(candidate["baseline_plan_version"]), candidate["baseline_plan_sha256"], draft_id,
                 draft_version, candidate["candidate_sha256"], _json(draft), _digest(draft),
                 _json(unmapped_sections), "Draft Materialized", payload.reason, 1, 1, 0, 0, 0, who, stamp),
            )
            governance_id = _key("psg")
            conn.execute(
                """INSERT INTO salops_plan_successor_governance(
                id,tenant_id,materialization_id,baseline_plan_id,baseline_plan_version,
                baseline_plan_sha256,draft_plan_id,draft_plan_version,candidate_id,candidate_sha256,
                status,created_by,created_at) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                (governance_id, tenant_id(request), materialization_id, candidate["baseline_plan_id"],
                 int(candidate["baseline_plan_version"]), candidate["baseline_plan_sha256"], draft_id,
                 draft_version, candidate_id, candidate["candidate_sha256"], "Pending Review", who, stamp),
            )
            governance = successor_row(conn, materialization_id, request)
            successor_event(conn, governance, "Controlled Draft Created",
                            f"Separate Draft {draft_id} requires controlled review, approval, and release; Approved baseline preserved.", request)
            created = materialization_row(conn, materialization_id, request)
            event(conn, run, "Draft Plan Materialized",
                  f"{candidate_id}: separate Draft plan {draft_id} v{draft_version} created for governed review; Approved baseline unchanged and no authority, release, disclosure, or charge created.", request)
            conn.execute(
                """INSERT INTO salops_preparedness_events(
                id,tenant_id,entity_type,entity_id,event_no,record_version,event_type,reason,
                snapshot_json,changed_by,changed_by_role,created_at) VALUES(?,?,?,?,?,?,?,?,?,?,?,?)""",
                (_key("pevt"), tenant_id(request), "Plan", draft_id, 1, draft_version,
                 "Materialize Separate Draft",
                 f"Created from accepted immutable candidate {candidate_id}; Approved baseline preserved; normal plan review and approval remain required.",
                 _json(draft), who, role(request), stamp),
            )
            audit(conn, "SALOPS_PREPAREDNESS_PLAN_DRAFT_MATERIALIZED", "salops_preparedness_plans", None,
                  f"{draft_id}: candidate {candidate_id}; separate Draft only; Approved baseline preserved."[:1000], who)
            conn.commit()
            return decode("salops_plan_materializations", created)
        finally:
            conn.close()

    @app.post("/api/salops/preparedness/plan-materializations/{materialization_id}/review")
    def review_plan_successor(materialization_id: str, payload: PlanSuccessorReview, request: Request):
        salus_access(request, "write")
        if role(request) not in ("System Administrator", "Assessment Director", "Lead Assessor"):
            raise HTTPException(403, "This role cannot review a controlled successor plan")
        conn = db()
        try:
            governance = successor_row(conn, materialization_id, request)
            if governance["status"] != "Pending Review":
                raise HTTPException(409, "Successor review requires a materialized Draft pending review")
            verify_baseline(conn, governance, request)
            draft = plan_row(conn, governance["draft_plan_id"], request)
            materialization = materialization_row(conn, materialization_id, request)
            original = _loads(materialization["draft_plan_snapshot_json"], {})
            if _digest(plan_proposal_snapshot(draft)) != _digest(plan_proposal_snapshot(original)):
                raise HTTPException(409, "The materialized Draft changed outside its governed candidate lineage")
            stamp, who = now(), actor(request)
            snapshot = dict(draft)
            conn.execute(
                """UPDATE salops_plan_successor_governance SET status='Human Reviewed',
                review_snapshot_json=?,review_snapshot_sha256=?,reviewed_by=?,reviewed_at=?,review_reason=?
                WHERE id=? AND tenant_id=?""",
                (_json(snapshot), _digest(snapshot), who, stamp, payload.reason,
                 governance["id"], tenant_id(request)),
            )
            updated = successor_row(conn, materialization_id, request)
            successor_event(conn, updated, "Human Review Recorded",
                            f"{payload.reason}; no approval, release, disclosure, authority, or charge created.", request)
            conn.commit()
            return decode("salops_plan_successor_governance", updated)
        finally:
            conn.close()

    @app.post("/api/salops/preparedness/plan-materializations/{materialization_id}/approve")
    def approve_plan_successor(materialization_id: str, payload: PlanSuccessorApprove, request: Request):
        salus_access(request, "write")
        if role(request) not in ("System Administrator", "Assessment Director", "Program Owner"):
            raise HTTPException(403, "This role cannot approve a controlled successor proposal")
        conn = db()
        try:
            governance = successor_row(conn, materialization_id, request)
            if governance["status"] != "Human Reviewed":
                raise HTTPException(409, "Successor approval requires the separate human-review gate")
            verify_baseline(conn, governance, request)
            draft = plan_row(conn, governance["draft_plan_id"], request)
            reviewed = _loads(governance["review_snapshot_json"], {})
            if _digest(draft) != governance["review_snapshot_sha256"] or draft != reviewed:
                raise HTTPException(409, "The reviewed successor content changed; approval is stopped")
            stamp, who = now(), actor(request)
            conn.execute(
                """UPDATE salops_plan_successor_governance SET status='Approved for Release',
                approval_snapshot_json=?,approval_snapshot_sha256=?,approved_by=?,approved_at=?,approval_reason=?
                WHERE id=? AND tenant_id=?""",
                (_json(draft), _digest(draft), who, stamp, payload.reason,
                 governance["id"], tenant_id(request)),
            )
            updated = successor_row(conn, materialization_id, request)
            successor_event(conn, updated, "Successor Proposal Approved",
                            f"{payload.reason}; approval does not release or disclose the plan and creates no authority or charge.", request)
            conn.commit()
            return decode("salops_plan_successor_governance", updated)
        finally:
            conn.close()

    @app.post("/api/salops/preparedness/plan-materializations/{materialization_id}/release")
    def release_plan_successor(materialization_id: str, payload: PlanSuccessorRelease, request: Request):
        salus_access(request, "write")
        if role(request) not in ("System Administrator", "Program Owner"):
            raise HTTPException(403, "This role cannot release a controlled successor plan")
        conn = db()
        try:
            governance = successor_row(conn, materialization_id, request)
            if governance["status"] != "Approved for Release":
                raise HTTPException(409, "Release requires separate review and successor-approval gates")
            verify_baseline(conn, governance, request)
            draft = plan_row(conn, governance["draft_plan_id"], request)
            if _digest(draft) != governance["approval_snapshot_sha256"]:
                raise HTTPException(409, "The approved successor proposal changed; release is stopped")
            stamp, who, released_id = now(), actor(request), _key("plan")
            released = dict(draft)
            released.update({
                "id": released_id, "status": "Approved", "member_adoption_status": "Not Recorded",
                "member_adoption_reason": "", "member_adopted_by": "", "member_adopted_at": "",
                "commercial_treatment": "Not Determined", "commercial_reference": "",
                "membership_entitlement_ref": "", "created_by": who, "created_at": stamp,
                "updated_by": who, "updated_at": stamp, "reviewed_by": governance["reviewed_by"],
                "reviewed_at": governance["reviewed_at"], "approved_by": governance["approved_by"],
                "approved_at": governance["approved_at"],
            })
            columns = [item["name"] for item in conn.execute("PRAGMA table_info(salops_preparedness_plans)")]
            conn.execute(
                f"INSERT INTO salops_preparedness_plans({','.join(columns)}) VALUES({','.join('?' * len(columns))})",
                tuple(released.get(column) for column in columns),
            )
            released = plan_row(conn, released_id, request)
            conn.execute(
                """UPDATE salops_plan_successor_governance SET status='Released',released_plan_id=?,
                released_plan_snapshot_json=?,released_plan_sha256=?,released_by=?,released_at=?,release_reason=?,
                authority_confirmed=1,disclosure_authorized=1,unresolved_items_accepted=1,creates_release=1
                WHERE id=? AND tenant_id=?""",
                (released_id, _json(released), _digest(released), who, stamp, payload.reason,
                 governance["id"], tenant_id(request)),
            )
            conn.execute(
                """INSERT INTO salops_preparedness_events(
                id,tenant_id,entity_type,entity_id,event_no,record_version,event_type,reason,
                snapshot_json,changed_by,changed_by_role,created_at) VALUES(?,?,?,?,?,?,?,?,?,?,?,?)""",
                (_key("pevt"), tenant_id(request), "Plan", released_id, 1, int(released["version"]),
                 "Controlled Successor Released",
                 f"Released from governed materialization {materialization_id}; predecessor {governance['baseline_plan_id']} remains immutable.",
                 _json(released), who, role(request), stamp),
            )
            updated = successor_row(conn, materialization_id, request)
            successor_event(conn, updated, "Successor Plan Released",
                            f"{payload.reason}; authorized disclosure created plan {released_id}; predecessor preserved; no authority or charge created.", request)
            create_preparedness_handoffs(conn, updated, released, request)
            audit(conn, "SALOPS_PLAN_SUCCESSOR_RELEASED", "salops_preparedness_plans", None,
                  f"{released_id}: released from {materialization_id}; baseline {governance['baseline_plan_id']} preserved."[:1000], who)
            conn.commit()
            return decode("salops_plan_successor_governance", updated)
        finally:
            conn.close()

    @app.get("/api/salops/preparedness/plan-handoffs")
    def list_preparedness_handoffs(request: Request, status: str = ""):
        salus_access(request)
        if status and status not in PREPAREDNESS_HANDOFF_STATES:
            raise HTTPException(422, "Unknown preparedness-handoff status")
        clauses, params = ["tenant_id=?"], [tenant_id(request)]
        if status:
            clauses.append("status=?")
            params.append(status)
        conn = db()
        try:
            return [decode("salops_plan_preparedness_handoffs", handoff_row(conn, item["id"], request))
                    for item in conn.execute(
                        "SELECT id FROM salops_plan_preparedness_handoffs WHERE "
                        + " AND ".join(clauses) + " ORDER BY created_at,id", tuple(params))]
        finally:
            conn.close()

    @app.post("/api/salops/preparedness/plan-handoffs/{handoff_id}/review")
    def review_preparedness_handoff(handoff_id: str, payload: PreparednessHandoffReview,
                                    request: Request):
        salus_access(request, "write")
        if role(request) not in ("System Administrator", "Assessment Director", "Lead Assessor", "Program Owner"):
            raise HTTPException(403, "This role cannot review a released-plan preparedness handoff")
        conn = db()
        try:
            handoff = handoff_row(conn, handoff_id, request)
            if handoff["status"] != "Pending Human Review":
                raise HTTPException(409, "Preparedness handoff review is available only from Pending Human Review")
            stamp, who = now(), actor(request)
            conn.execute(
                """UPDATE salops_plan_preparedness_handoffs SET status=?,reviewed_by=?,reviewed_at=?,review_reason=?
                   WHERE id=? AND tenant_id=?""",
                (payload.decision, who, stamp, payload.reason, handoff_id, tenant_id(request)),
            )
            updated = handoff_row(conn, handoff_id, request)
            handoff_event(
                conn, updated, f"Human Review {payload.decision}",
                f"{payload.reason}; review did not schedule, perform, release, disclose, authorize, or charge for work.",
                request,
            )
            conn.commit()
            return decode("salops_plan_preparedness_handoffs", updated)
        finally:
            conn.close()

    @app.post("/api/salops/preparedness/plan-handoffs/{handoff_id}/materialize")
    def materialize_preparedness_handoff(handoff_id: str, payload: PreparednessHandoffMaterialize,
                                         request: Request):
        """Create one governed internal activity from an accepted immutable proposal."""
        salus_access(request, "write")
        if role(request) not in ("System Administrator", "Assessment Director", "Program Owner"):
            raise HTTPException(403, "This role cannot create a preparedness activity from a plan handoff")
        conn = db()
        try:
            handoff = handoff_row(conn, handoff_id, request)
            if handoff["status"] != "Accepted":
                raise HTTPException(409, "Materialization requires a separately accepted preparedness handoff")
            proposal = _loads(handoff["proposal_snapshot_json"], {})
            plan = plan_row(conn, handoff["released_plan_id"], request)
            stamp, who = now(), actor(request)
            target_id, target_type = "", ""
            if handoff["handoff_type"] == "Training":
                target_id, target_type = _key("train"), "Training"
                conn.execute(
                    """INSERT INTO salops_preparedness_training(
                    id,tenant_id,assessment_id,plan_id,title,objective,capability_ref,role_addressed,
                    audience,participants_json,prerequisites,delivery_type,materials_json,instructor,
                    scheduled_at,performance_check,follow_up_requirements,recurrence_schedule,
                    mission_lenses_json,status,commercial_treatment,commercial_reference,
                    membership_entitlement_ref,version,created_by,created_at,updated_by,updated_at)
                    VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                    (target_id, tenant_id(request), plan.get("assessment_id"), plan["id"],
                     proposal["title"], proposal["recommendation"], "", "", "", "[]", "", "",
                     "[]", "", "", "", "", "", plan.get("mission_lenses_json") or "[]", "Draft",
                     "Not Determined", "", "", 1, who, stamp, who, stamp),
                )
                target = dict(conn.execute("SELECT * FROM salops_preparedness_training WHERE id=?", (target_id,)).fetchone())
            elif handoff["handoff_type"] == "Exercise":
                target_id, target_type = _key("exercise"), "Exercise"
                conn.execute(
                    """INSERT INTO salops_preparedness_exercises(
                    id,tenant_id,assessment_id,plan_id,title,exercise_type,purpose,objectives_json,
                    capabilities_json,scope_statement,portfolio_scope_json,mission_lenses_json,
                    salthira_refs_json,assumptions_artificialities,participating_organizations_json,
                    control_evaluation_roles_json,scenario_summary,scenario_control_json,
                    expected_actions_json,evaluation_criteria_json,safety_real_world_controls,
                    logistics_resources,scheduled_at,location,external_partners_json,communications_plan,
                    documentation_requirements,sensitivity,status,commercial_treatment,commercial_reference,
                    membership_entitlement_ref,version,created_by,created_at,updated_by,updated_at)
                    VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                    (target_id, tenant_id(request), plan.get("assessment_id"), plan["id"], proposal["title"],
                     "Tabletop Exercise", proposal["recommendation"], _json([proposal["recommendation"]]),
                     "[]", plan["scope_statement"], plan.get("portfolio_scope_json") or "{}",
                     plan.get("mission_lenses_json") or "[]", plan.get("salthira_refs_json") or "[]",
                     "Requires separate human exercise design and approval.", "[]", "[]", "", "{}", "[]",
                     _json(["Evaluate the released-plan recommendation against documented capability evidence."]),
                     "No execution is authorized by this Planned record.", "", "", "", "[]", "",
                     "Capture observations, source references, decisions, and validation evidence.",
                     plan.get("sensitivity") or "Standard", "Planned", "Not Determined", "", "", 1,
                     who, stamp, who, stamp),
                )
                target = dict(conn.execute("SELECT * FROM salops_preparedness_exercises WHERE id=?", (target_id,)).fetchone())
            elif handoff["handoff_type"] == "Validation":
                target_id, target_type = _key("action"), "Corrective Action"
                conn.execute(
                    """INSERT INTO salops_preparedness_corrective_actions(
                    id,tenant_id,observation_id,exercise_id,plan_id,assessment_id,title,description,
                    owner,priority,due_date,resources_required,estimate_reference,membership_entitlement_ref,
                    validation_method,reexercise_required,status,member_release_status,version,
                    created_by,created_at,updated_by,updated_at) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                    (target_id, tenant_id(request), None, None, plan["id"], plan.get("assessment_id"),
                     proposal["title"], proposal["recommendation"], "", "Normal", "", "", "", "",
                     proposal["recommendation"], 1, "Open", "Internal", 1, who, stamp, who, stamp),
                )
                target = dict(conn.execute("SELECT * FROM salops_preparedness_corrective_actions WHERE id=?", (target_id,)).fetchone())
            elif handoff["handoff_type"] == "SalTHIRA Reassessment":
                if not plan.get("assessment_id"):
                    raise HTTPException(409, "SalTHIRA reassessment materialization requires an assessment-linked released plan")
                target_type = "Reassessment Trigger"
                description = (
                    f"Released preparedness plan {plan['title']} ({plan['id']}): "
                    f"{proposal['recommendation']}"
                )
                cursor = conn.execute(
                    """INSERT INTO reassessment_triggers(
                    assessment_id,source,trigger_type,description,severity,affected_record_type,
                    affected_record_id,status,assigned_to,due_date,resolution,created_at,updated_at)
                    VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                    (int(plan["assessment_id"]), "SalOPS Preparedness",
                     "Preparedness Plan Reassessment Recommendation", description, "Moderate",
                     "assessment", int(plan["assessment_id"]), "Open", "", "", "", stamp, stamp),
                )
                target_id = int(cursor.lastrowid)
                target = dict(conn.execute(
                    "SELECT * FROM reassessment_triggers WHERE id=?", (target_id,)
                ).fetchone())
                audit(
                    conn, "SALOPS_PREP_TO_SALTHIRA", "reassessment_trigger", target_id,
                    f"Created from separately accepted immutable handoff {handoff_id}; assessment state unchanged.",
                    who,
                )
            else:
                raise HTTPException(409, "Unsupported preparedness handoff type")
            conn.execute(
                """UPDATE salops_plan_preparedness_handoffs SET status='Materialized',target_record_type=?,
                target_record_id=?,materialized_by=?,materialized_at=?,materialization_reason=?
                WHERE id=? AND tenant_id=?""",
                (target_type, target_id, who, stamp, payload.reason, handoff_id, tenant_id(request)),
            )
            if target_type != "Reassessment Trigger":
                conn.execute(
                    """INSERT INTO salops_preparedness_events(
                    id,tenant_id,entity_type,entity_id,event_no,record_version,event_type,reason,
                    snapshot_json,changed_by,changed_by_role,created_at) VALUES(?,?,?,?,?,?,?,?,?,?,?,?)""",
                    (_key("pevt"), tenant_id(request), target_type, target_id, 1, 1,
                     "Materialize Released-Plan Handoff",
                     f"Created from separately accepted immutable handoff {handoff_id}. No release, disclosure, execution authority, or charge was created.",
                     _json(target), who, role(request), stamp),
                )
            updated = handoff_row(conn, handoff_id, request)
            handoff_event(
                conn, updated, "Governed Activity Materialized",
                f"{payload.reason}; created internal {target_type} {target_id}. Scheduling/execution, disclosure, commercial treatment, and completion/validation remain separate.",
                request,
            )
            run = run_row(conn, handoff["run_id"], request)
            event(conn, run, "Preparedness Handoff Materialized",
                  f"{handoff_id}: created internal {target_type} {target_id}; no automatic release, authority, or charge.", request)
            conn.commit()
            return decode("salops_plan_preparedness_handoffs", updated)
        finally:
            conn.close()

    @app.get("/api/salops/preparedness/plan-impact-detections")
    def list_plan_impact_detections(request: Request, status: str = ""):
        salus_access(request)
        clauses = ["tenant_id=?"]
        params: list[Any] = [tenant_id(request)]
        if status:
            clauses.append("status=?")
            params.append(status)
        conn = db()
        try:
            rows = []
            for item in conn.execute(
                "SELECT * FROM salops_plan_impact_detections WHERE " + " AND ".join(clauses)
                + " ORDER BY created_at DESC,id", tuple(params),
            ):
                data = impact_row(conn, item["id"], request)
                rows.append(decode("salops_plan_impact_detections", data))
            return rows
        finally:
            conn.close()

    @app.post("/api/salops/preparedness/plans/{plan_id}/impact-detections")
    def detect_plan_impact(plan_id: str, payload: PlanImpactDetect, request: Request):
        salus_access(request, "write")
        conn = db()
        try:
            plan = plan_row(conn, plan_id, request)
            if plan["status"] != "Approved":
                raise HTTPException(409, "Plan-impact detection requires the current Approved plan baseline")
            source, source_title, source_recorded_at = resolve_impact_source(
                conn, plan, payload.source_record_type, payload.source_record_id, request,
            )
            source_sha256 = _digest(source)
            existing = conn.execute(
                """SELECT id FROM salops_plan_impact_detections
                   WHERE tenant_id=? AND approved_plan_id=? AND source_record_type=?
                   AND source_record_id=? AND source_sha256=?""",
                (tenant_id(request), plan_id, payload.source_record_type,
                 payload.source_record_id, source_sha256),
            ).fetchone()
            if existing:
                raise HTTPException(409, "This exact governed source version has already been evaluated for plan impact")
            defaults = {
                "SalINTEL Qualified Investigation": ["assumptions", "concept_of_operations", "dependencies"],
                "SalINTEL Qualified Finding": ["assumptions", "activation_criteria", "concept_of_operations"],
                "SalINTEL Monitoring Review": ["assumptions", "dependencies", "activation_criteria"],
                "SalTHIRA Reassessment Trigger": ["assumptions", "concept_of_operations", "exercise_validation_requirements"],
                "SalOPS Exercise": ["concept_of_operations", "training_requirements", "exercise_validation_requirements"],
                "SalOPS Observation": ["concept_of_operations", "checklists_job_aids", "training_requirements"],
                "SalOPS Corrective Action": ["checklists_job_aids", "training_requirements", "exercise_validation_requirements"],
                "PROVE Released Assurance": ["evidence_refs", "exercise_validation_requirements"],
                "Governed Material": ["authorities_references", "assumptions", "dependencies"],
            }
            affected = payload.suggested_affected_sections or defaults[payload.source_record_type]
            reasons = _clean_list([
                "The source is an actual tenant-scoped governed record resolved by an allowlisted adapter.",
                f"The current Approved plan v{plan['version']} was integrity-snapshotted before impact review.",
                *payload.detection_reasons,
            ])
            research_questions = payload.research_questions or [
                f"How does {source_title} affect the current approved plan and its documented assumptions?",
                "Which proposed changes require legal, policy, command, evacuation, contractual, or other human authority?",
            ]
            unknowns = payload.known_unknowns or [
                "Materiality and exact plan impact remain subject to Salus human review."
            ]
            temporal = ("Recorded after plan approval" if source_recorded_at > str(plan.get("approved_at") or "")
                        else "Recorded on or before plan approval — review possible omission or later qualification")
            detection_id = _key("pid")
            stamp = now()
            conn.execute(
                """INSERT INTO salops_plan_impact_detections(
                id,tenant_id,approved_plan_id,approved_plan_version,approved_plan_sha256,
                source_record_type,source_record_id,source_snapshot_json,source_sha256,
                source_recorded_at,source_title,temporal_relation,change_summary,
                suggested_affected_sections_json,detection_reasons_json,research_questions_json,
                known_unknowns_json,status,materiality_decision,revision_recommended,
                server_detected,approved_plan_preserved,creates_plan_version,creates_release,
                creates_authority,creates_charge,created_by,created_at)
                VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                (detection_id, tenant_id(request), plan_id, int(plan["version"]), _digest(plan),
                 payload.source_record_type, payload.source_record_id, _json(source), source_sha256,
                 source_recorded_at, source_title, temporal, payload.change_summary,
                 _json(affected), _json(reasons), _json(research_questions), _json(unknowns),
                 "Potential Impact", "Not Reviewed", 0, 1, 1, 0, 0, 0, 0,
                 actor(request), stamp),
            )
            created = impact_row(conn, detection_id, request)
            impact_event(conn, created, "Potential Impact Detected",
                         "Actual governed source resolved and compared to the Approved baseline; materiality, revision, authority, release, disclosure, and cost remain undecided.", request)
            conn.commit()
            return decode("salops_plan_impact_detections", created)
        finally:
            conn.close()

    @app.post("/api/salops/preparedness/plan-impact-detections/{detection_id}/review")
    def review_plan_impact(detection_id: str, payload: PlanImpactReview, request: Request):
        salus_access(request, "write")
        if role(request) not in ("System Administrator", "Assessment Director", "Program Owner"):
            raise HTTPException(403, "This role cannot determine plan-impact materiality")
        conn = db()
        try:
            detection = impact_row(conn, detection_id, request)
            if detection["status"] != "Potential Impact" or detection["materiality_decision"] != "Not Reviewed":
                raise HTTPException(409, "This potential plan impact already has a materiality decision")
            plan = plan_row(conn, detection["approved_plan_id"], request)
            if (plan["status"] != "Approved" or int(plan["version"]) != int(detection["approved_plan_version"])
                    or _digest(plan) != detection["approved_plan_sha256"]):
                raise HTTPException(409, "The Approved plan baseline changed; create a new impact detection")
            confirmed = _clean_list(payload.confirmed_affected_sections) or _loads(
                detection["suggested_affected_sections_json"], []
            )
            status = {
                "Material Change": "Revision Recommended",
                "No Material Change": "Closed — No Material Change",
                "More Collection Required": "Collection Required",
            }[payload.decision]
            run_id: Optional[str] = None
            stamp, who = now(), actor(request)
            if payload.decision == "Material Change":
                if not confirmed:
                    raise HTTPException(409, "A Material Change decision requires at least one affected plan section")
                run_id = _key("par")
                research_questions = _loads(detection["research_questions_json"], []) or [
                    "What exact source-grounded changes are required in the approved plan?"
                ]
                known_unknowns = _loads(detection["known_unknowns_json"], [])
                conn.execute(
                    """INSERT INTO salops_plan_assembly_runs(
                    id,tenant_id,base_plan_id,base_plan_version,base_plan_status,base_plan_snapshot_json,
                    base_plan_sha256,assembly_mode,plan_title,plan_type,purpose,scope_statement,
                    portfolio_scope_json,internal_record_refs_json,library_refs_json,
                    authorized_external_sources_json,source_exclusions_json,research_questions_json,
                    known_unknowns_json,assumptions_to_validate_json,affected_sections_json,sensitivity,
                    status,current_iteration,created_by,created_at,updated_by,updated_at)
                    VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                    (run_id, tenant_id(request), plan["id"], int(plan["version"]), plan["status"],
                     _json(plan), _digest(plan), "Revision", f"{plan['title']} — proposed revision",
                     plan["plan_type"], f"Research and draft the human-confirmed material plan impact {detection_id}.",
                     plan["scope_statement"], plan["portfolio_scope_json"],
                     _json([f"plan-impact:{detection_id}", f"{detection['source_record_type']}:{detection['source_record_id']}"]),
                     "[]", "[]", "[]", _json(research_questions), _json(known_unknowns),
                     _json(known_unknowns), _json(confirmed), plan["sensitivity"], "Research Planning", 1,
                     who, stamp, who, stamp),
                )
                run = dict(conn.execute("SELECT * FROM salops_plan_assembly_runs WHERE id=?", (run_id,)).fetchone())
                event(conn, run, "Create from Material Plan Impact",
                      f"{detection_id}: separate bounded revision research started; Approved plan v{plan['version']} remains unchanged.", request)
            conn.execute(
                """UPDATE salops_plan_impact_detections SET status=?,materiality_decision=?,
                confirmed_affected_sections_json=?,revision_recommended=?,revision_recommendation=?,
                assembly_run_id=?,reviewed_by=?,reviewed_at=?,review_reason=?
                WHERE id=? AND tenant_id=?""",
                (status, payload.decision, _json(confirmed),
                 1 if payload.decision == "Material Change" else 0,
                 payload.revision_recommendation if payload.decision == "Material Change" else "",
                 run_id, who, stamp, payload.reason, detection_id, tenant_id(request)),
            )
            updated = impact_row(conn, detection_id, request)
            impact_event(conn, updated, f"Materiality Review — {payload.decision}",
                         f"{payload.reason}; Approved plan preserved and no plan version, authority, release, disclosure, or charge created.", request)
            conn.commit()
            return decode("salops_plan_impact_detections", updated)
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
            recommendation_ids = ids["salops_plan_revision_recommendations"]
            candidate_ids = ids["salops_plan_version_candidates"]
            materialization_ids = ids["salops_plan_materializations"]
            governance_ids = ids["salops_plan_successor_governance"]
            handoff_ids = ids["salops_plan_preparedness_handoffs"]
            preparedness_target_ids = {
                "Training": {str(row.get("id")) for row in records.get("salops_preparedness_training", []) if row.get("id")},
                "Exercise": {str(row.get("id")) for row in records.get("salops_preparedness_exercises", []) if row.get("id")},
                "Corrective Action": {str(row.get("id")) for row in records.get("salops_preparedness_corrective_actions", []) if row.get("id")},
                "Reassessment Trigger": {str(row.get("id")) for row in records.get("reassessment_triggers", []) if row.get("id")},
            }
            envelope_ids = ids["salops_plan_research_cost_envelopes"]
            envelope_records = {str(row.get("id")): row for row in records.get("salops_plan_research_cost_envelopes", []) if row.get("id")}
            candidate_hashes = {
                str(row.get("id")): str(row.get("candidate_sha256") or "")
                for row in records.get("salops_plan_version_candidates", []) if row.get("id")
            }
            impact_ids = ids["salops_plan_impact_detections"]
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
            for row in records.get("salops_plan_version_candidates", []):
                if row.get("baseline_plan_id") and str(row["baseline_plan_id"]) not in plan_ids:
                    errors.append(f"plan-version candidate {row.get('id')} has invalid baseline_plan_id")
                if row.get("revision_recommendation_id") and str(row["revision_recommendation_id"]) not in recommendation_ids:
                    errors.append(f"plan-version candidate {row.get('id')} has invalid revision_recommendation_id")
                snapshot = _loads(row.get("candidate_snapshot_json"), {})
                if not snapshot or _digest(snapshot) != row.get("candidate_sha256"):
                    errors.append(f"plan-version candidate {row.get('id')} failed integrity verification")
            for row in records.get("salops_plan_materializations", []):
                if str(row.get("candidate_id")) not in candidate_ids:
                    errors.append(f"plan materialization {row.get('id')} has invalid candidate_id")
                elif candidate_hashes.get(str(row.get("candidate_id"))) != str(row.get("candidate_sha256") or ""):
                    errors.append(f"plan materialization {row.get('id')} failed candidate lineage verification")
                if row.get("baseline_plan_id") and str(row["baseline_plan_id"]) not in plan_ids:
                    errors.append(f"plan materialization {row.get('id')} has invalid baseline_plan_id")
                if str(row.get("draft_plan_id")) not in plan_ids:
                    errors.append(f"plan materialization {row.get('id')} has invalid draft_plan_id")
                snapshot = _loads(row.get("draft_plan_snapshot_json"), {})
                if not snapshot or _digest(snapshot) != row.get("draft_plan_sha256"):
                    errors.append(f"plan materialization {row.get('id')} failed Draft plan integrity verification")
            for row in records.get("salops_plan_successor_governance", []):
                if str(row.get("materialization_id")) not in materialization_ids:
                    errors.append(f"plan successor governance {row.get('id')} has invalid materialization_id")
                if row.get("baseline_plan_id") and str(row.get("baseline_plan_id")) not in plan_ids:
                    errors.append(f"plan successor governance {row.get('id')} has invalid baseline_plan_id")
                if str(row.get("draft_plan_id")) not in plan_ids:
                    errors.append(f"plan successor governance {row.get('id')} has invalid draft_plan_id")
                if str(row.get("candidate_id")) not in candidate_ids:
                    errors.append(f"plan successor governance {row.get('id')} has invalid candidate lineage")
                if row.get("released_plan_id") and str(row.get("released_plan_id")) not in plan_ids:
                    errors.append(f"plan successor governance {row.get('id')} has invalid released_plan_id")
                if row.get("status") not in ("Pending Review", "Human Reviewed", "Approved for Release", "Released"):
                    errors.append(f"plan successor governance {row.get('id')} has invalid status")
                for prefix in ("review", "approval", "released_plan"):
                    digest = str(row.get(f"{prefix}_snapshot_sha256") or "")
                    snapshot = _loads(row.get(f"{prefix}_snapshot_json"), {})
                    if digest and (not snapshot or _digest(snapshot) != digest):
                        errors.append(f"plan successor governance {row.get('id')} failed {prefix} integrity verification")
                if int(row.get("creates_authority") or 0) or int(row.get("creates_charge") or 0):
                    errors.append(f"plan successor governance {row.get('id')} forges authority or charge")
                if row.get("status") == "Released" and not all(int(row.get(name) or 0) == 1 for name in (
                    "authority_confirmed", "disclosure_authorized", "unresolved_items_accepted", "creates_release",
                )):
                    errors.append(f"released plan successor governance {row.get('id')} lacks explicit release confirmations")
            for row in records.get("salops_plan_successor_events", []):
                if str(row.get("governance_id")) not in governance_ids:
                    errors.append(f"plan successor event {row.get('id')} has invalid governance_id")
            for row in records.get("salops_plan_preparedness_handoffs", []):
                if str(row.get("governance_id")) not in governance_ids:
                    errors.append(f"preparedness handoff {row.get('id')} has invalid governance_id")
                if str(row.get("released_plan_id")) not in plan_ids:
                    errors.append(f"preparedness handoff {row.get('id')} has invalid released_plan_id")
                if row.get("handoff_type") not in PREPAREDNESS_HANDOFF_TYPES:
                    errors.append(f"preparedness handoff {row.get('id')} has invalid type")
                if row.get("status") not in PREPAREDNESS_HANDOFF_STATES:
                    errors.append(f"preparedness handoff {row.get('id')} has invalid status")
                proposal = _loads(row.get("proposal_snapshot_json"), {})
                if (_digest(row.get("recommendation") or "") != row.get("recommendation_sha256")
                        or not proposal or _digest(proposal) != row.get("proposal_sha256")):
                    errors.append(f"preparedness handoff {row.get('id')} failed integrity verification")
                if any(int(row.get(name) or 0) != 0 for name in
                       ("creates_schedule", "creates_release", "creates_authority", "creates_charge")):
                    errors.append(f"preparedness handoff {row.get('id')} forges schedule, release, authority, or charge")
                target_id = str(row.get("target_record_id") or "")
                target_type = str(row.get("target_record_type") or "")
                if row.get("status") == "Materialized":
                    if target_type not in preparedness_target_ids or target_id not in preparedness_target_ids[target_type]:
                        errors.append(f"materialized preparedness handoff {row.get('id')} has invalid target lineage")
                elif target_id or target_type:
                    errors.append(f"unmaterialized preparedness handoff {row.get('id')} forges a target record")
            for row in records.get("salops_plan_preparedness_handoff_events", []):
                if str(row.get("handoff_id")) not in handoff_ids:
                    errors.append(f"preparedness handoff event {row.get('id')} has invalid handoff_id")
            for row in records.get("salops_plan_research_cost_envelopes", []):
                if row.get("status") not in ("Draft", "Authorized", "Superseded", "Closed"):
                    errors.append(f"research-cost envelope {row.get('id')} has invalid status")
                if any(int(row.get(name) or 0) != 0 for name in
                       ("creates_customer_price", "creates_charge", "creates_invoice")):
                    errors.append(f"research-cost envelope {row.get('id')} forges a customer commercial effect")
                if _digest(cost_envelope_content(row)) != row.get("content_sha256"):
                    errors.append(f"research-cost envelope {row.get('id')} failed integrity verification")
                planned = sum(int(row.get(name) or 0) for name in (
                    "estimated_chat_ai_cost_cents", "estimated_human_cost_cents",
                    "external_data_allowance_cents", "partner_allowance_cents",
                    "other_direct_allowance_cents",
                ))
                if planned > int(row.get("maximum_authorized_cost_cents") or 0):
                    errors.append(f"research-cost envelope {row.get('id')} exceeds its maximum")
            for row in records.get("salops_plan_research_cost_usage", []):
                if str(row.get("envelope_id")) not in envelope_ids:
                    errors.append(f"research-cost usage {row.get('id')} has invalid envelope_id")
                elif str(row.get("run_id")) != str(envelope_records[str(row.get("envelope_id"))].get("run_id")):
                    errors.append(f"research-cost usage {row.get('id')} crosses its envelope run boundary")
                if row.get("category") not in RESEARCH_COST_CATEGORIES:
                    errors.append(f"research-cost usage {row.get('id')} has invalid category")
                if row.get("measurement_status") not in RESEARCH_COST_MEASUREMENTS:
                    errors.append(f"research-cost usage {row.get('id')} has invalid measurement status")
                if int(row.get("amount_cents") or 0) < 0:
                    errors.append(f"research-cost usage {row.get('id')} has a negative amount")
                if any(int(row.get(name) or 0) != 0 for name in
                       ("creates_customer_price", "creates_charge", "creates_invoice")):
                    errors.append(f"research-cost usage {row.get('id')} forges a customer commercial effect")
            usage_by_envelope: dict[str, dict[str, int]] = {}
            for row in records.get("salops_plan_research_cost_usage", []):
                totals = usage_by_envelope.setdefault(str(row.get("envelope_id")), {})
                category = str(row.get("category") or "")
                totals[category] = totals.get(category, 0) + int(row.get("amount_cents") or 0)
            cap_fields = {
                "Chat / AI": "estimated_chat_ai_cost_cents",
                "Salus Human Labor": "estimated_human_cost_cents",
                "External Data": "external_data_allowance_cents",
                "Approved Partner": "partner_allowance_cents",
                "Other Direct": "other_direct_allowance_cents",
            }
            for envelope_id, totals in usage_by_envelope.items():
                envelope = envelope_records.get(envelope_id)
                if not envelope:
                    continue
                if sum(totals.values()) > int(envelope.get("maximum_authorized_cost_cents") or 0):
                    errors.append(f"research-cost envelope {envelope_id} restored usage exceeds its maximum")
                for category, amount in totals.items():
                    if category in cap_fields and amount > int(envelope.get(cap_fields[category]) or 0):
                        errors.append(f"research-cost envelope {envelope_id} restored {category} usage exceeds its component allowance")
            active_by_run: dict[str, int] = {}
            for row in records.get("salops_plan_research_cost_envelopes", []):
                if row.get("status") == "Authorized":
                    key = str(row.get("run_id"))
                    active_by_run[key] = active_by_run.get(key, 0) + 1
            if any(count > 1 for count in active_by_run.values()):
                errors.append("research-cost backup contains multiple Authorized envelopes for one assembly run")
            for row in records.get("salops_plan_impact_detections", []):
                if str(row.get("approved_plan_id")) not in plan_ids:
                    errors.append(f"plan-impact detection {row.get('id')} has invalid approved_plan_id")
                if row.get("assembly_run_id") and str(row["assembly_run_id"]) not in run_ids:
                    errors.append(f"plan-impact detection {row.get('id')} has invalid assembly_run_id")
                snapshot = _loads(row.get("source_snapshot_json"), {})
                if not snapshot or _digest(snapshot) != row.get("source_sha256"):
                    errors.append(f"plan-impact detection {row.get('id')} failed source snapshot integrity verification")
            for row in records.get("salops_plan_impact_events", []):
                if str(row.get("detection_id")) not in impact_ids:
                    errors.append(f"plan-impact event {row.get('id')} has invalid detection_id")
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
