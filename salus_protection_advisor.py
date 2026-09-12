"""Versioned policy models for the isolated Salus Protection Advisor prototype.

Issue #290. This module has no application routes and no Protected Member
tenant relationship. It stores only released fictional-prototype policy
snapshots and supplies fictional acceptance cases. A later, separately
validated adapter may use these snapshots to prepare preliminary,
non-binding recommendations from governed commercial-engine results.
"""

from __future__ import annotations

import copy
import hashlib
import json
import os
import secrets
from datetime import datetime, timedelta, timezone
from typing import Any, Literal, Mapping

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


POLICY_STATUS = "Released for Fictional Internal Prototype"
DATA_BOUNDARY = "Advisor Prospect — No Protected Member Access"
BUNDLE_KEY = "SPA-INTERNAL-PROTOTYPE-1"
EVALUATION_ADAPTER_VERSION = "SPA-EVALUATION-ADAPTER-1.0.0"
EVALUATION_STATUS = "Prepared — Salus Review Required"
SESSION_RETENTION_HOURS = 2
SESSION_RETENTION_POLICY = "SPA-EPHEMERAL-RETENTION-1.0.0"
ANSWER_STATES = ("Answered", "Unknown", "Declined", "Not Applicable")
CONSENT_NOTICE_VERSION = "SPA-CONSENT-NOTICE-1.0.0"
CONSENT_PURPOSE = (
    "Retain the fictional Advisor recommendation and fictional contact details "
    "for an internal Salus review."
)
PROSPECT_RETENTION_DAYS = 30
PROSPECT_RETENTION_POLICY = "SPA-FICTIONAL-PROSPECT-RETENTION-1.0.0"
CONSENTED_FIELDS = (
    "organization_display_name",
    "contact_name",
    "contact_email",
    "evaluation_snapshot",
    "purpose_and_consent_evidence",
)
STAFF_REVIEW_DECISIONS = (
    "Proceed to Fictional Scoping",
    "Questions Required",
    "Decline — No Fit",
    "Close — No Action",
)
SCOPING_HANDOFF_STATUS = (
    "Prepared Draft — Fictional; Separate Scope and Price Approval Required"
)
INTERNAL_REVIEW_PACKET_VERSION = "SPA-INTERNAL-REVIEW-PACKET-1.0.0"
INTERNAL_REVIEW_PACKET_STATUS = "Prepared — Awaiting Salus Review"
INTERNAL_REVIEW_TOPICS = (
    "Question wording and participant burden",
    "Visible evaluation basis, uncertainty, and information gaps",
    "Recommendation fit and investigation depth",
    "Sanitized public price ranges and package inclusions",
    "Consent, retention, correction, withdrawal, and deletion",
    "Staff review, correction, and authority lineage",
    "Scoping handoff assumptions, exclusions, and validation questions",
    "Accessibility, responsive presentation, and Salus visual continuity",
    "Security, privacy, abuse resistance, recovery, and rollback readiness",
)
INTERNAL_REVIEW_INTERFACE_VERSION = "SPA-INTERNAL-REVIEW-INTERFACE-1.0.0"
INTERNAL_REVIEW_INTERFACE_FLAG = "SALUS_PROTECTION_ADVISOR_INTERNAL_REVIEW"
INTERNAL_REVIEW_INTERFACE_STATE = "Enabled for Fictional Internal Acceptance"
POLICY_TABLES = {
    "Questionnaire": "advisor_questionnaire_versions",
    "Recommendation Policy": "advisor_recommendation_policy_versions",
    "Package Catalogue": "advisor_package_catalogue_versions",
    "Public Price Policy": "advisor_public_price_policy_versions",
}
DIMENSIONS = (
    "Exposure",
    "Threat and Hazard Environment",
    "Vulnerability",
    "Consequence",
    "Capability",
    "Complexity",
    "Urgency",
    "Service Intensity",
)
CAPABILITY_AREAS = (
    "Prevention",
    "Protection",
    "Mitigation",
    "Response",
    "Recovery",
)
INVESTIGATION_LEVELS = {
    "Initial Pass": "Tier 1",
    "Intermediate Assessment": "Tier 2",
    "High Deep-Dive": "Tier 3",
}
FORBIDDEN_PUBLIC_FIELDS = frozenset(
    {
        "approved_customer_price_cents",
        "contingency_basis_points",
        "contribution_margin",
        "cost_cents",
        "internal_basis",
        "internal_cost",
        "loaded_labor_cost_cents_per_hour",
        "margin",
        "margin_basis_points",
        "minimum_margin",
        "override_order",
        "partner_rate",
        "proprietary_weight",
        "recommended_customer_price_cents",
        "role_rate",
        "standard_bill_rate_cents_per_hour",
    }
)


class PolicyIntegrityError(RuntimeError):
    """Raised when a released policy snapshot cannot be verified."""


class SessionAccessError(RuntimeError):
    """Generic fail-closed error for invalid, replayed, expired, or deleted sessions."""


class AdvisorPolicyDefinition(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    policy_kind: Literal[
        "Questionnaire",
        "Recommendation Policy",
        "Package Catalogue",
        "Public Price Policy",
    ]
    version_key: str = Field(pattern=r"^SPA-[A-Z-]+-[0-9]+\.[0-9]+\.[0-9]+$")
    status: Literal["Released for Fictional Internal Prototype"] = POLICY_STATUS
    data_boundary: Literal["Advisor Prospect — No Protected Member Access"] = DATA_BOUNDARY
    fictional_only: Literal[True] = True
    effective_date: str = Field(min_length=1, max_length=80)
    authority: str = Field(min_length=1, max_length=240)
    payload: dict[str, Any]

    @field_validator("effective_date", "authority")
    @classmethod
    def clean_text(cls, value: str) -> str:
        return value.strip()


class FictionalAdvisorCase(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    case_key: str = Field(pattern=r"^SPA-FICTIONAL-[A-Z-]+$")
    display_name: str = Field(min_length=1, max_length=160)
    organization_context: str = Field(min_length=1, max_length=1200)
    answers: dict[str, Any]
    acceptance_focus: tuple[str, ...]

    @field_validator("display_name")
    @classmethod
    def require_fictional_label(cls, value: str) -> str:
        clean = value.strip()
        if "Fictional" not in clean:
            raise ValueError("fictional cases must be visibly labelled")
        return clean


class FictionalCommercialCandidate(BaseModel):
    """Hash-bound commercial input available only to the fictional adapter."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    package_key: str = Field(pattern=r"^SPA-PKG-[A-Z-]+$")
    fictional_only: Literal[True] = True
    commercial_estimate_snapshot_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    rate_card_snapshot_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    currency: Literal["USD"] = "USD"
    one_time_range_minimum: int = Field(ge=0)
    one_time_range_maximum: int = Field(ge=0)
    recurring_range_minimum: int = Field(ge=0)
    recurring_range_maximum: int = Field(ge=0)
    recurring_cadence: Literal["Monthly", "Quarterly", "Annual"]
    implementation_period: str = Field(min_length=1, max_length=160)
    assumptions: tuple[str, ...]

    @model_validator(mode="after")
    def validate_ranges(self) -> "FictionalCommercialCandidate":
        if self.one_time_range_maximum < self.one_time_range_minimum:
            raise ValueError("one-time maximum must not be below minimum")
        if self.recurring_range_maximum < self.recurring_range_minimum:
            raise ValueError("recurring maximum must not be below minimum")
        return self


class FictionalAnswerSubmission(BaseModel):
    """Strict answer command accepted only by the internal fictional service."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    question_key: str = Field(pattern=r"^[a-z][a-z0-9_]{0,79}$")
    answer_state: Literal["Answered", "Unknown", "Declined", "Not Applicable"]
    value: str | int | list[str] | None = None

    @model_validator(mode="after")
    def validate_state_and_value(self) -> "FictionalAnswerSubmission":
        if self.answer_state == "Answered":
            if self.value in (None, "", []):
                raise ValueError("answered submissions require a value")
        elif self.value is not None:
            raise ValueError("non-answered states must not carry a value")
        if isinstance(self.value, str) and len(self.value.strip()) > 1200:
            raise ValueError("answer text exceeds the prototype limit")
        if isinstance(self.value, int) and not 0 <= self.value <= 10000:
            raise ValueError("answer count exceeds the prototype limit")
        if isinstance(self.value, list):
            if len(self.value) > 25 or any(not item.strip() or len(item.strip()) > 160 for item in self.value):
                raise ValueError("answer collection exceeds the prototype limit")
        return self



class FictionalProspectSubmission(BaseModel):
    """Strict fictional contact-and-consent command for the disabled prototype."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    action: Literal["Save for Later", "Submit for Salus Review"]
    affirmative_consent: Literal[True]
    notice_version: Literal["SPA-CONSENT-NOTICE-1.0.0"]
    organization_display_name: str = Field(min_length=1, max_length=160)
    contact_name: str = Field(min_length=1, max_length=160)
    contact_email: str = Field(min_length=3, max_length=254)
    authorized_fields: tuple[str, ...]

    @field_validator("organization_display_name", "contact_name")
    @classmethod
    def validate_fictional_identity(cls, value: str) -> str:
        normalized = value.strip()
        if "fictional" not in normalized.casefold():
            raise ValueError("only explicitly fictional prospect identities are accepted")
        return normalized

    @field_validator("contact_email")
    @classmethod
    def validate_fictional_email(cls, value: str) -> str:
        normalized = value.strip().casefold()
        if "@" not in normalized or not (
            normalized.endswith("@example.com") or normalized.endswith(".example")
        ):
            raise ValueError("only reserved fictional email addresses are accepted")
        return normalized

    @field_validator("authorized_fields")
    @classmethod
    def validate_authorized_fields(cls, value: tuple[str, ...]) -> tuple[str, ...]:
        if len(value) != len(set(value)) or set(value) != set(CONSENTED_FIELDS):
            raise ValueError("consent must name the exact authorized field set")
        return value



class FictionalStaffReviewCommand(BaseModel):
    """Strict fictional Salus staff-review command with correction lineage."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    decision: Literal[
        "Proceed to Fictional Scoping",
        "Questions Required",
        "Decline — No Fit",
        "Close — No Action",
    ]
    reviewer_key: str = Field(pattern=r"^SPA-REVIEWER-FICTIONAL-[A-Z0-9-]{1,80}$")
    reviewer_role: Literal[
        "Qualified Salus Commercial Reviewer",
        "Senior Salus Commercial Reviewer",
    ]
    qualifications_confirmed: Literal[True]
    fictional_acceptance_simulation: Literal[True]
    rationale: str = Field(min_length=10, max_length=2000)
    assumptions: tuple[str, ...] = ()
    information_needed: tuple[str, ...] = ()
    supersedes_review_key: str | None = Field(
        default=None, pattern=r"^SPA-REVIEW-[A-F0-9]{64}$"
    )
    correction_reason: str | None = Field(default=None, min_length=10, max_length=1000)

    @field_validator("rationale")
    @classmethod
    def normalize_rationale(cls, value: str) -> str:
        return value.strip()

    @field_validator("assumptions", "information_needed")
    @classmethod
    def validate_bounded_statements(cls, value: tuple[str, ...]) -> tuple[str, ...]:
        if len(value) > 20 or any(not item.strip() or len(item.strip()) > 500 for item in value):
            raise ValueError("review statement collection exceeds the prototype limit")
        return tuple(item.strip() for item in value)

    @model_validator(mode="after")
    def validate_review_lineage(self) -> "FictionalStaffReviewCommand":
        if self.decision == "Questions Required" and not self.information_needed:
            raise ValueError("questions-required decisions must identify information needed")
        if self.decision != "Questions Required" and self.information_needed:
            raise ValueError("information-needed entries require a questions-required decision")
        if bool(self.supersedes_review_key) != bool(self.correction_reason):
            raise ValueError("supersession and correction reason must be supplied together")
        return self



class FictionalScopingHandoffCommand(BaseModel):
    """Strict command for a nonbinding fictional scope-draft handoff."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    authorizing_review_key: str = Field(pattern=r"^SPA-REVIEW-[A-F0-9]{64}$")
    prepared_by_reviewer_key: str = Field(
        pattern=r"^SPA-REVIEWER-FICTIONAL-[A-Z0-9-]{1,80}$"
    )
    prepared_by_reviewer_role: Literal[
        "Qualified Salus Commercial Reviewer",
        "Senior Salus Commercial Reviewer",
    ]
    preparation_purpose: Literal["Prepare Fictional Scope Draft"]
    fictional_acceptance_simulation: Literal[True]
    assumptions: tuple[str, ...] = ()
    exclusions: tuple[str, ...] = ()
    validation_questions: tuple[str, ...] = ()

    @field_validator("assumptions", "exclusions", "validation_questions")
    @classmethod
    def validate_handoff_statements(cls, value: tuple[str, ...]) -> tuple[str, ...]:
        if len(value) > 20 or any(not item.strip() or len(item.strip()) > 500 for item in value):
            raise ValueError("scope-draft statement collection exceeds the prototype limit")
        return tuple(item.strip() for item in value)


class FictionalInternalReviewPacketCommand(BaseModel):
    """Strict command that prepares evidence for an actual Salus human review."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    handoff_key: str = Field(pattern=r"^SPA-HANDOFF-[A-F0-9]{64}$")
    prepared_by_reviewer_key: str = Field(
        pattern=r"^SPA-REVIEWER-FICTIONAL-[A-Z0-9-]{1,80}$"
    )
    prepared_by_reviewer_role: Literal[
        "Qualified Salus Commercial Reviewer",
        "Senior Salus Commercial Reviewer",
    ]
    fictional_acceptance_simulation: Literal[True]
    requested_review_topics: tuple[str, ...]

    @field_validator("requested_review_topics")
    @classmethod
    def require_complete_review_scope(cls, value: tuple[str, ...]) -> tuple[str, ...]:
        cleaned = tuple(item.strip() for item in value)
        if cleaned != INTERNAL_REVIEW_TOPICS:
            raise ValueError("internal review packet must retain the complete governed review scope")
        return cleaned


class FictionalInternalReviewInterfaceContext(BaseModel):
    """Server-side fictional reviewer context; no public request model uses it."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    reviewer_key: str = Field(
        pattern=r"^SPA-REVIEWER-FICTIONAL-[A-Z0-9-]{1,80}$"
    )
    reviewer_role: Literal[
        "Qualified Salus Commercial Reviewer",
        "Senior Salus Commercial Reviewer",
    ]
    access_purpose: Literal["Review Fictional Protection Advisor Evidence"]
    fictional_acceptance_simulation: Literal[True]


SCHEMA = """
CREATE TABLE IF NOT EXISTS advisor_questionnaire_versions (
 version_key TEXT PRIMARY KEY, status TEXT NOT NULL, data_boundary TEXT NOT NULL,
 fictional_only INTEGER NOT NULL, effective_date TEXT NOT NULL, authority TEXT NOT NULL,
 snapshot_json TEXT NOT NULL, content_sha256 TEXT NOT NULL UNIQUE,
 released_by TEXT NOT NULL, released_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS advisor_recommendation_policy_versions (
 version_key TEXT PRIMARY KEY, status TEXT NOT NULL, data_boundary TEXT NOT NULL,
 fictional_only INTEGER NOT NULL, effective_date TEXT NOT NULL, authority TEXT NOT NULL,
 snapshot_json TEXT NOT NULL, content_sha256 TEXT NOT NULL UNIQUE,
 released_by TEXT NOT NULL, released_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS advisor_package_catalogue_versions (
 version_key TEXT PRIMARY KEY, status TEXT NOT NULL, data_boundary TEXT NOT NULL,
 fictional_only INTEGER NOT NULL, effective_date TEXT NOT NULL, authority TEXT NOT NULL,
 snapshot_json TEXT NOT NULL, content_sha256 TEXT NOT NULL UNIQUE,
 released_by TEXT NOT NULL, released_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS advisor_public_price_policy_versions (
 version_key TEXT PRIMARY KEY, status TEXT NOT NULL, data_boundary TEXT NOT NULL,
 fictional_only INTEGER NOT NULL, effective_date TEXT NOT NULL, authority TEXT NOT NULL,
 snapshot_json TEXT NOT NULL, content_sha256 TEXT NOT NULL UNIQUE,
 released_by TEXT NOT NULL, released_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS advisor_policy_bundles (
 bundle_key TEXT PRIMARY KEY, status TEXT NOT NULL, data_boundary TEXT NOT NULL,
 fictional_only INTEGER NOT NULL, snapshot_json TEXT NOT NULL,
 content_sha256 TEXT NOT NULL UNIQUE, released_by TEXT NOT NULL, released_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS advisor_fictional_evaluation_snapshots (
 evaluation_key TEXT PRIMARY KEY, case_key TEXT NOT NULL,
 status TEXT NOT NULL, data_boundary TEXT NOT NULL, fictional_only INTEGER NOT NULL,
 adapter_version TEXT NOT NULL, policy_bundle_sha256 TEXT NOT NULL,
 commercial_estimate_snapshot_sha256 TEXT NOT NULL,
 rate_card_snapshot_sha256 TEXT NOT NULL, input_sha256 TEXT NOT NULL,
 snapshot_json TEXT NOT NULL, content_sha256 TEXT NOT NULL UNIQUE,
 created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS advisor_sessions (
 session_key TEXT PRIMARY KEY, case_key TEXT NOT NULL,
 status TEXT NOT NULL, data_boundary TEXT NOT NULL, fictional_only INTEGER NOT NULL,
 policy_bundle_sha256 TEXT NOT NULL, questionnaire_version_key TEXT NOT NULL,
 retention_policy_version TEXT NOT NULL, latest_answer_revision INTEGER NOT NULL,
 current_token_sha256 TEXT, created_at TEXT NOT NULL, expires_at TEXT NOT NULL,
 deleted_at TEXT
);
CREATE TABLE IF NOT EXISTS advisor_session_tokens (
 token_sha256 TEXT PRIMARY KEY, session_key TEXT NOT NULL,
 token_status TEXT NOT NULL, issued_at TEXT NOT NULL, superseded_at TEXT
);
CREATE TABLE IF NOT EXISTS advisor_answer_revisions (
 revision_key TEXT PRIMARY KEY, session_key TEXT NOT NULL,
 revision_number INTEGER NOT NULL, question_key TEXT NOT NULL,
 questionnaire_version_key TEXT NOT NULL, answer_state TEXT NOT NULL,
 answer_json TEXT NOT NULL, content_sha256 TEXT NOT NULL UNIQUE,
 created_at TEXT NOT NULL, UNIQUE(session_key, revision_number)
);
CREATE TABLE IF NOT EXISTS advisor_audit_events (
 event_key TEXT PRIMARY KEY, session_key TEXT NOT NULL,
 event_sequence INTEGER NOT NULL, event_type TEXT NOT NULL,
 event_at TEXT NOT NULL, event_json TEXT NOT NULL,
 content_sha256 TEXT NOT NULL UNIQUE, UNIQUE(session_key, event_sequence)
);
CREATE TABLE IF NOT EXISTS advisor_session_evaluation_snapshots (
 evaluation_key TEXT PRIMARY KEY, session_key TEXT NOT NULL,
 answer_revision INTEGER NOT NULL, answer_state_sha256 TEXT NOT NULL,
 status TEXT NOT NULL, data_boundary TEXT NOT NULL, fictional_only INTEGER NOT NULL,
 adapter_version TEXT NOT NULL, policy_bundle_sha256 TEXT NOT NULL,
 commercial_estimate_snapshot_sha256 TEXT NOT NULL,
 rate_card_snapshot_sha256 TEXT NOT NULL, snapshot_json TEXT NOT NULL,
 content_sha256 TEXT NOT NULL UNIQUE, created_at TEXT NOT NULL,
 UNIQUE(session_key, answer_revision)
);
CREATE TABLE IF NOT EXISTS advisor_consent_notice_versions (
 notice_version TEXT PRIMARY KEY, status TEXT NOT NULL,
 data_boundary TEXT NOT NULL, fictional_only INTEGER NOT NULL,
 notice_json TEXT NOT NULL, content_sha256 TEXT NOT NULL UNIQUE,
 released_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS advisor_consents (
 consent_key TEXT PRIMARY KEY, session_key TEXT NOT NULL,
 evaluation_key TEXT NOT NULL, notice_version TEXT NOT NULL,
 notice_sha256 TEXT NOT NULL, status TEXT NOT NULL, action TEXT NOT NULL,
 purpose TEXT NOT NULL, authorized_fields_json TEXT NOT NULL,
 affirmative_action INTEGER NOT NULL, consented_at TEXT NOT NULL,
 consented_display TEXT NOT NULL, expires_at TEXT NOT NULL,
 retention_policy_version TEXT NOT NULL, lifecycle_state TEXT NOT NULL,
 withdrawn_at TEXT, deleted_at TEXT, snapshot_json TEXT NOT NULL,
 content_sha256 TEXT NOT NULL UNIQUE
);
CREATE TABLE IF NOT EXISTS advisor_prospects (
 prospect_key TEXT PRIMARY KEY, session_key TEXT NOT NULL,
 evaluation_key TEXT NOT NULL, consent_key TEXT NOT NULL,
 status TEXT NOT NULL, data_boundary TEXT NOT NULL,
 fictional_only INTEGER NOT NULL, payload_json TEXT NOT NULL,
 content_sha256 TEXT NOT NULL UNIQUE, created_at TEXT NOT NULL,
 expires_at TEXT NOT NULL, retention_policy_version TEXT NOT NULL,
 correction_state TEXT NOT NULL, withdrawal_state TEXT NOT NULL,
 deletion_state TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS advisor_prospect_review_decisions (
 review_key TEXT PRIMARY KEY, prospect_key TEXT NOT NULL,
 review_sequence INTEGER NOT NULL, status TEXT NOT NULL,
 decision TEXT NOT NULL, reviewer_key TEXT NOT NULL,
 reviewer_role TEXT NOT NULL, data_boundary TEXT NOT NULL,
 fictional_only INTEGER NOT NULL, basis_sha256 TEXT NOT NULL,
 supersedes_review_key TEXT, correction_reason TEXT,
 snapshot_json TEXT NOT NULL, content_sha256 TEXT NOT NULL UNIQUE,
 created_at TEXT NOT NULL, UNIQUE(prospect_key, review_sequence)
);
CREATE TABLE IF NOT EXISTS advisor_prospect_review_state (
 prospect_key TEXT PRIMARY KEY, current_review_key TEXT NOT NULL,
 review_sequence INTEGER NOT NULL, status TEXT NOT NULL,
 updated_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS advisor_fictional_scoping_handoffs (
 handoff_key TEXT PRIMARY KEY, prospect_key TEXT NOT NULL,
 authorizing_review_key TEXT NOT NULL UNIQUE, status TEXT NOT NULL,
 data_boundary TEXT NOT NULL, fictional_only INTEGER NOT NULL,
 prepared_by_reviewer_key TEXT NOT NULL,
 prepared_by_reviewer_role TEXT NOT NULL, basis_sha256 TEXT NOT NULL,
 snapshot_json TEXT NOT NULL, content_sha256 TEXT NOT NULL UNIQUE,
 created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS advisor_fictional_internal_review_packets (
 packet_key TEXT PRIMARY KEY, packet_version TEXT NOT NULL,
 handoff_key TEXT NOT NULL UNIQUE, prospect_key TEXT NOT NULL,
 status TEXT NOT NULL, data_boundary TEXT NOT NULL,
 fictional_only INTEGER NOT NULL, prepared_by_reviewer_key TEXT NOT NULL,
 prepared_by_reviewer_role TEXT NOT NULL, evidence_sha256 TEXT NOT NULL,
 snapshot_json TEXT NOT NULL, content_sha256 TEXT NOT NULL UNIQUE,
 created_at TEXT NOT NULL
);
"""


def canonical_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def content_sha256(value: Any) -> str:
    encoded = value if isinstance(value, str) else canonical_json(value)
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()


def _question(
    key: str,
    prompt: str,
    why: str,
    answer_kind: str,
    dimensions: list[str],
    *,
    required: bool = False,
    choices: list[str] | None = None,
    shown_when: dict[str, Any] | None = None,
) -> dict[str, Any]:
    return {
        "question_key": key,
        "prompt": prompt,
        "why_this_matters": why,
        "answer_kind": answer_kind,
        "required": required,
        "choices": choices or [],
        "shown_when": shown_when or {},
        "dimension_links": dimensions,
        "unknown_allowed": True,
        "declined_allowed": not required,
        "not_applicable_allowed": not required,
        "retained_before_submission": False,
    }


def policy_definitions() -> tuple[AdvisorPolicyDefinition, ...]:
    questionnaire = AdvisorPolicyDefinition(
        policy_kind="Questionnaire",
        version_key="SPA-QUESTIONNAIRE-1.0.0",
        effective_date="12 September 2026",
        authority="Issue #290 internal prototype; Salus review required before pilot.",
        payload={
            "title": "Find Your Salus Package",
            "result_title": "Your Salus Recommendation",
            "one_topic_at_a_time": True,
            "contact_requested_only_for_save_or_submit": True,
            "questions": [
                _question(
                    "organization_type", "Which description best fits your organization?",
                    "Organization type helps Salus apply the right operating and public-service context.",
                    "Single Choice", ["Complexity", "Service Intensity"], required=True,
                    choices=["Small Business", "Multi-location Business", "Corporation", "Critical Infrastructure", "Public Agency", "Nonprofit or Community Organization", "Other"],
                ),
                _question(
                    "mission", "What work or public purpose must continue?",
                    "The protected mission gives later answers a practical frame.",
                    "Short Narrative", ["Consequence", "Capability"], required=True,
                ),
                _question(
                    "locations", "How many operating locations are in scope?",
                    "Location count and type can change coordination, travel, and continuity needs.",
                    "Bounded Count", ["Exposure", "Complexity", "Service Intensity"], required=True,
                ),
                _question(
                    "jurisdictions", "How many legal or operating jurisdictions are in scope?",
                    "Different jurisdictions can add authorities, requirements, and coordination needs.",
                    "Bounded Count", ["Complexity", "Service Intensity"], required=True,
                ),
                _question(
                    "people_exposed", "Approximately how many personnel or people depend on these operations?",
                    "This helps describe exposure without treating size as a substitute for need.",
                    "Bounded Range", ["Exposure", "Consequence"], required=True,
                ),
                _question(
                    "critical_assets", "Which people, places, assets, information, or services are most important?",
                    "Priorities should follow the mission and consequences, not a generic checklist.",
                    "Multi Select", ["Exposure", "Consequence"],
                ),
                _question(
                    "dependencies", "Which outside services or suppliers are essential?",
                    "Dependencies can create shared failure points and restoration constraints.",
                    "Multi Select", ["Vulnerability", "Consequence", "Complexity"],
                ),
                _question(
                    "capability_posture", "How would you describe current prevention, protection, mitigation, response, and recovery arrangements?",
                    "Existing capability helps Salus identify the appropriate starting depth and support.",
                    "Five-area Capability", ["Capability", "Service Intensity"], required=True,
                ),
                _question(
                    "reported_concerns", "Which threats, hazards, risks, or vulnerabilities concern you?",
                    "Reported concerns guide follow-up; they are not findings or threat judgments.",
                    "Multi Select", ["Threat and Hazard Environment", "Vulnerability"],
                ),
                _question(
                    "recent_change", "Has a material change made existing plans or assumptions less reliable?",
                    "Recent change can increase urgency or create a need for validation.",
                    "Single Choice", ["Urgency", "Vulnerability"],
                    choices=["Yes", "No", "Unknown"],
                ),
                _question(
                    "desired_support", "What kind of Salus support would be most useful?",
                    "Desired outcomes help distinguish an assessment from implementation or ongoing support.",
                    "Multi Select", ["Service Intensity", "Capability"],
                ),
                _question(
                    "investigation_depth", "How much initial investigation depth are you considering?",
                    "Clear levels keep the proposed work bounded while allowing deeper inquiry when justified.",
                    "Single Choice", ["Complexity", "Service Intensity"],
                    choices=list(INVESTIGATION_LEVELS),
                ),
                _question(
                    "urgency_window", "When do you need a useful first result?",
                    "Timing affects staffing, sequencing, and what can be responsibly demonstrated.",
                    "Single Choice", ["Urgency", "Service Intensity"],
                    choices=["Within 14 days", "Within 30 days", "Within 90 days", "Planning ahead", "Unknown"],
                ),
                _question(
                    "budget_context", "Would you like the preliminary options shaped around a budget range?",
                    "Budget context can help identify a practical entry point without understating real cost.",
                    "Optional Range", ["Service Intensity"], required=False,
                ),
            ],
            "answer_states": ["Answered", "Unknown", "Declined", "Not Applicable"],
            "branching_rule": "Only explicitly displayed and answered questions may contribute to evaluation.",
        },
    )

    recommendation = AdvisorPolicyDefinition(
        policy_kind="Recommendation Policy",
        version_key="SPA-RECOMMENDATION-POLICY-1.0.0",
        effective_date="12 September 2026",
        authority="Issue #290 internal prototype; qualified Salus review retains decision authority.",
        payload={
            "dimensions": [
                {
                    "name": name,
                    "output_states": ["Limited Indication", "Developing Indication", "Material Indication", "Evidence Needed"],
                    "requires_answer_lineage": True,
                    "requires_uncertainty_explanation": True,
                }
                for name in DIMENSIONS
            ],
            "capability_areas": list(CAPABILITY_AREAS),
            "investigation_level_mapping": INVESTIGATION_LEVELS,
            "size_only_decision_prohibited": True,
            "hidden_answer_scoring_prohibited": True,
            "required_result_distinctions": [
                "Reported Information", "Assumption", "Information Gap",
                "Contradiction", "Preliminary Inference", "Salus-reviewed Recommendation",
            ],
            "recommendation_authority": "Preliminary until a qualified Salus reviewer approves final scope, package, and price.",
            "binding_effect": False,
            "creates_charge": False,
            "creates_contract": False,
            "creates_membership": False,
            "creates_protected_member": False,
        },
    )

    packages = AdvisorPolicyDefinition(
        policy_kind="Package Catalogue",
        version_key="SPA-PACKAGE-CATALOGUE-1.0.0",
        effective_date="12 September 2026",
        authority="Prototype names and mappings require Salus review before any customer use.",
        payload={
            "catalogue_state": "Internal Fictional Prototype",
            "selection_principles": [
                "Need, mission, exposure, consequence, capability, complexity, urgency, and service intensity are considered independently.",
                "Organization size alone never selects a package.",
                "Scope and professional attention scale; user-seat count is not the governing proxy.",
                "Every option states inclusions, exclusions, capacity ceiling, and change-control boundary.",
            ],
            "packages": [
                {
                    "package_key": "SPA-PKG-FOUNDATION",
                    "prototype_name": "Essential Protection Foundation",
                    "purpose": "A bounded diagnostic starting point and prioritized improvement path.",
                    "eligible_depths": ["Initial Pass"],
                    "commercial_product_lines": ["SalTHIRA Assessment", "Report / Briefing"],
                    "includes": ["Protected mission context", "Initial assessment", "Priority briefing", "Governed 90-day action outline"],
                    "excludes": ["Ongoing monitoring", "Operational implementation", "Deep-dive investigation"],
                    "capacity_ceiling": "One bounded organization context and an approved location allowance.",
                },
                {
                    "package_key": "SPA-PKG-READINESS",
                    "prototype_name": "Protective Readiness",
                    "purpose": "Assessment plus a bounded implementation and review cadence.",
                    "eligible_depths": ["Initial Pass", "Intermediate Assessment"],
                    "commercial_product_lines": ["SalTHIRA Assessment", "SalOPS Preparedness", "Protected Membership"],
                    "includes": ["Assessment", "Implementation priorities", "Planning support", "Scheduled review"],
                    "excludes": ["Unscheduled incident operations", "High Deep-Dive investigation unless separately scoped"],
                    "capacity_ceiling": "Versioned location, professional-capacity, and review-cadence allowance.",
                },
                {
                    "package_key": "SPA-PKG-INTEGRATED",
                    "prototype_name": "Integrated Protective Program",
                    "purpose": "Coordinated intelligence, assessment, implementation, and continuing improvement.",
                    "eligible_depths": ["Intermediate Assessment", "High Deep-Dive"],
                    "commercial_product_lines": ["SalINTEL Ongoing Monitoring", "SalTHIRA Assessment", "SalOPS Preparedness", "Protected Membership"],
                    "includes": ["Ongoing monitoring", "Assessment and reassessment", "Preparedness support", "Executive review"],
                    "excludes": ["Unlimited investigations", "Unapproved travel, specialists, equipment, or Global Partner work"],
                    "capacity_ceiling": "Approved monitoring, assessment, location, and professional-capacity allowances.",
                },
                {
                    "package_key": "SPA-PKG-COMPLEX-MISSION",
                    "prototype_name": "Complex Mission Partnership",
                    "purpose": "A governed multi-jurisdiction program with separately scoped specialist support.",
                    "eligible_depths": ["Intermediate Assessment", "High Deep-Dive"],
                    "commercial_product_lines": ["SalINTEL Investigation", "SalINTEL Ongoing Monitoring", "SalTHIRA Assessment", "SalOPS Preparedness", "SalOPS Incident Support", "Protected Membership"],
                    "includes": ["Multi-jurisdiction coordination design", "Deep-dive options", "Continuing review", "Specialist-resource planning"],
                    "excludes": ["Automatic partner activation", "Automatic incident deployment", "Open-ended professional capacity"],
                    "capacity_ceiling": "Explicit jurisdiction, location, workstream, specialist, travel, and professional-capacity ceilings.",
                },
            ],
        },
    )

    public_price = AdvisorPolicyDefinition(
        policy_kind="Public Price Policy",
        version_key="SPA-PUBLIC-PRICE-POLICY-1.0.0",
        effective_date="12 September 2026",
        authority="Issue #290 public-output boundary; no customer release is authorized.",
        payload={
            "currency": "USD",
            "output_shape": {
                "one_time_range": ["minimum", "maximum", "cadence"],
                "recurring_range": ["minimum", "maximum", "cadence"],
                "required_context": ["assumptions", "inclusions", "exclusions", "estimate_snapshot_reference"],
            },
            "allowed_public_fields": [
                "currency", "range_minimum", "range_maximum", "cadence",
                "assumptions", "inclusions", "exclusions", "implementation_period",
                "optional_services", "preliminary_notice",
            ],
            "forbidden_public_fields": sorted(FORBIDDEN_PUBLIC_FIELDS),
            "range_rules": {
                "rounded_values_only": True,
                "single_exact_price_prohibited": True,
                "minimum_less_than_or_equal_to_maximum": True,
                "internal_estimate_snapshot_required": True,
                "sanitized_projection_required": True,
            },
            "commercial_events_created": [],
            "qualified_salus_review_required": True,
        },
    )
    return questionnaire, recommendation, packages, public_price


FICTIONAL_CASES = (
    FictionalAdvisorCase(
        case_key="SPA-FICTIONAL-JUNIPER-TABLE",
        display_name="Fictional Juniper Table Restaurant",
        organization_context="A single-location restaurant with public occupancy, perishable inventory, utility dependencies, and a small leadership team.",
        answers={
            "organization_type": "Small Business", "locations": 1, "jurisdictions": 1,
            "people_exposed": "Under 100", "capability_posture": "Mixed and partly documented",
            "reported_concerns": ["Severe weather", "Utility interruption", "Workplace violence"],
            "recent_change": "No", "investigation_depth": "Initial Pass",
        },
        acceptance_focus=("small-organization entry point", "real cost preserved", "size alone does not select scope"),
    ),
    FictionalAdvisorCase(
        case_key="SPA-FICTIONAL-MERIDIAN-REGIONAL",
        display_name="Fictional Meridian Regional Services",
        organization_context="A multi-location commercial service organization operating across two states with shared technology and vendor dependencies.",
        answers={
            "organization_type": "Multi-location Business", "locations": 12, "jurisdictions": 2,
            "people_exposed": "500–999", "capability_posture": "Documented but inconsistently exercised",
            "reported_concerns": ["Cyber-physical disruption", "Supply-chain interruption"],
            "recent_change": "Yes", "investigation_depth": "Intermediate Assessment",
        },
        acceptance_focus=("multi-location coordination", "dependency complexity", "material-change validation"),
    ),
    FictionalAdvisorCase(
        case_key="SPA-FICTIONAL-HARBORLIGHT-UTILITY",
        display_name="Fictional Harborlight Utility Cooperative",
        organization_context="A regional utility operator with public-service obligations, operational technology, field crews, mutual aid, and restoration priorities.",
        answers={
            "organization_type": "Critical Infrastructure", "locations": 7, "jurisdictions": 4,
            "people_exposed": "100,000 or more", "capability_posture": "Mature plans with specific evidence gaps",
            "reported_concerns": ["Severe weather", "Cyber-physical disruption", "Competing restoration resources"],
            "recent_change": "Yes", "investigation_depth": "High Deep-Dive",
        },
        acceptance_focus=("critical-infrastructure context", "capability evidence gap", "specialist controls"),
    ),
    FictionalAdvisorCase(
        case_key="SPA-FICTIONAL-SUMMIT-METRO",
        display_name="Fictional Summit Metro Administration",
        organization_context="A major multi-jurisdiction public entity with diverse departments, essential services, dense populations, regulated authorities, and regional partners.",
        answers={
            "organization_type": "Public Agency", "locations": 140, "jurisdictions": 18,
            "people_exposed": "100,000 or more", "capability_posture": "Varies materially by department and mission area",
            "reported_concerns": ["Concurrent emergencies", "Public-safety saturation", "Critical dependency failure"],
            "recent_change": "Unknown", "investigation_depth": "High Deep-Dive",
        },
        acceptance_focus=("major multi-jurisdiction complexity", "authority distinctions", "bounded professional capacity"),
    ),
)


FICTIONAL_PROSPECT_CONTACTS = {
    "SPA-FICTIONAL-JUNIPER-TABLE": {
        "organization_display_name": "Fictional Juniper Table Restaurant",
        "contact_name": "Fictional Jordan Example",
        "contact_email": "jordan.juniper@example.com",
    },
    "SPA-FICTIONAL-MERIDIAN-REGIONAL": {
        "organization_display_name": "Fictional Meridian Regional Services",
        "contact_name": "Fictional Morgan Example",
        "contact_email": "morgan.meridian@example.com",
    },
    "SPA-FICTIONAL-HARBORLIGHT-UTILITY": {
        "organization_display_name": "Fictional Harborlight Utility Cooperative",
        "contact_name": "Fictional Casey Example",
        "contact_email": "casey.harborlight@example.com",
    },
    "SPA-FICTIONAL-SUMMIT-METRO": {
        "organization_display_name": "Fictional Summit Metro Administration",
        "contact_name": "Fictional Taylor Example",
        "contact_email": "taylor.summit@example.com",
    },
}


def fictional_prospect_contacts() -> dict[str, dict[str, str]]:
    """Return repository-owned fictional contacts for internal acceptance only."""

    return copy.deepcopy(FICTIONAL_PROSPECT_CONTACTS)


FICTIONAL_STAFF_REVIEWERS = {
    "SPA-REVIEWER-FICTIONAL-COMMERCIAL-1": {
        "reviewer_key": "SPA-REVIEWER-FICTIONAL-COMMERCIAL-1",
        "display_name": "Fictional Commercial Reviewer",
        "reviewer_role": "Qualified Salus Commercial Reviewer",
        "fictional_only": True,
        "authority": (
            "May record a fictional preliminary review decision; may not establish "
            "scope, price, contract, membership, or customer release."
        ),
    },
    "SPA-REVIEWER-FICTIONAL-SENIOR-1": {
        "reviewer_key": "SPA-REVIEWER-FICTIONAL-SENIOR-1",
        "display_name": "Fictional Senior Commercial Reviewer",
        "reviewer_role": "Senior Salus Commercial Reviewer",
        "fictional_only": True,
        "authority": (
            "May record or correct a fictional preliminary review decision; may not "
            "establish scope, price, contract, membership, or customer release."
        ),
    },
}


def fictional_staff_reviewers() -> dict[str, dict[str, Any]]:
    """Return repository-owned fictional reviewer fixtures."""

    return copy.deepcopy(FICTIONAL_STAFF_REVIEWERS)


def _snapshot(definition: AdvisorPolicyDefinition) -> tuple[str, str]:
    payload = definition.model_dump(mode="json")
    snapshot_json = canonical_json(payload)
    return snapshot_json, content_sha256(snapshot_json)


def build_policy_bundle_snapshot() -> dict[str, Any]:
    components: dict[str, dict[str, str]] = {}
    for definition in policy_definitions():
        _, digest = _snapshot(definition)
        components[definition.policy_kind] = {
            "version_key": definition.version_key,
            "content_sha256": digest,
        }
    fixture_hashes = {
        case.case_key: content_sha256(case.model_dump(mode="json"))
        for case in FICTIONAL_CASES
    }
    return {
        "bundle_key": BUNDLE_KEY,
        "status": POLICY_STATUS,
        "data_boundary": DATA_BOUNDARY,
        "fictional_only": True,
        "components": components,
        "fictional_fixture_hashes": fixture_hashes,
        "has_routes": False,
        "has_contact_fields": False,
        "has_protected_member_access": False,
        "creates_binding_event": False,
        "design_authority": "docs/salus-protection-advisor-internal-prototype-design.md",
    }


def initialize_policy_store(conn: Any) -> None:
    conn.executescript(SCHEMA)


def _insert_immutable_snapshot(
    conn: Any,
    definition: AdvisorPolicyDefinition,
    released_by: str,
    released_at: str,
) -> None:
    table = POLICY_TABLES[definition.policy_kind]
    snapshot_json, digest = _snapshot(definition)
    existing = conn.execute(
        f"SELECT snapshot_json, content_sha256 FROM {table} WHERE version_key=?",
        (definition.version_key,),
    ).fetchone()
    if existing:
        if existing["snapshot_json"] != snapshot_json or existing["content_sha256"] != digest:
            raise PolicyIntegrityError(f"{definition.policy_kind} version collision")
        return
    conn.execute(
        f"INSERT INTO {table}(version_key,status,data_boundary,fictional_only,effective_date,authority,snapshot_json,content_sha256,released_by,released_at) VALUES(?,?,?,?,?,?,?,?,?,?)",
        (
            definition.version_key, definition.status, definition.data_boundary, 1,
            definition.effective_date, definition.authority, snapshot_json, digest,
            released_by.strip(), released_at.strip(),
        ),
    )


def install_fictional_policy_bundle(
    conn: Any,
    *,
    released_by: str,
    released_at: str,
) -> dict[str, Any]:
    """Install the exact fictional prototype policy bundle idempotently."""

    if not released_by.strip() or not released_at.strip():
        raise ValueError("release identity and time are required")
    initialize_policy_store(conn)
    try:
        for definition in policy_definitions():
            _insert_immutable_snapshot(conn, definition, released_by, released_at)
        bundle = build_policy_bundle_snapshot()
        snapshot_json = canonical_json(bundle)
        digest = content_sha256(snapshot_json)
        existing = conn.execute(
            "SELECT snapshot_json, content_sha256 FROM advisor_policy_bundles WHERE bundle_key=?",
            (BUNDLE_KEY,),
        ).fetchone()
        if existing:
            if existing["snapshot_json"] != snapshot_json or existing["content_sha256"] != digest:
                raise PolicyIntegrityError("policy bundle version collision")
        else:
            conn.execute(
                "INSERT INTO advisor_policy_bundles(bundle_key,status,data_boundary,fictional_only,snapshot_json,content_sha256,released_by,released_at) VALUES(?,?,?,?,?,?,?,?)",
                (BUNDLE_KEY, POLICY_STATUS, DATA_BOUNDARY, 1, snapshot_json, digest, released_by.strip(), released_at.strip()),
            )
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    return {**bundle, "content_sha256": digest}


def load_fictional_policy_bundle(conn: Any) -> dict[str, Any]:
    """Load and verify every immutable snapshot in the active fictional bundle."""

    row = conn.execute(
        "SELECT * FROM advisor_policy_bundles WHERE bundle_key=?", (BUNDLE_KEY,)
    ).fetchone()
    if not row:
        raise PolicyIntegrityError("fictional prototype policy bundle is not installed")
    if row["status"] != POLICY_STATUS or row["data_boundary"] != DATA_BOUNDARY or int(row["fictional_only"]) != 1:
        raise PolicyIntegrityError("policy bundle boundary is invalid")
    if content_sha256(row["snapshot_json"]) != row["content_sha256"]:
        raise PolicyIntegrityError("policy bundle integrity check failed")
    bundle = json.loads(row["snapshot_json"])
    for kind, reference in bundle["components"].items():
        table = POLICY_TABLES.get(kind)
        if not table:
            raise PolicyIntegrityError("policy bundle contains an unsupported component")
        component = conn.execute(
            f"SELECT * FROM {table} WHERE version_key=?", (reference["version_key"],)
        ).fetchone()
        if not component:
            raise PolicyIntegrityError(f"{kind} snapshot is missing")
        if (
            content_sha256(component["snapshot_json"]) != component["content_sha256"]
            or component["content_sha256"] != reference["content_sha256"]
            or component["status"] != POLICY_STATUS
            or component["data_boundary"] != DATA_BOUNDARY
            or int(component["fictional_only"]) != 1
        ):
            raise PolicyIntegrityError(f"{kind} snapshot integrity check failed")
    return {**bundle, "content_sha256": row["content_sha256"]}


def fictional_cases() -> list[dict[str, Any]]:
    return [copy.deepcopy(case.model_dump(mode="json")) for case in FICTIONAL_CASES]


def public_projection_violations(value: Any) -> list[str]:
    """Return internal field names that must never appear in a public projection."""

    found: set[str] = set()

    def walk(item: Any) -> None:
        if isinstance(item, dict):
            for key, nested in item.items():
                normalized = str(key).strip().casefold()
                if normalized in FORBIDDEN_PUBLIC_FIELDS:
                    found.add(normalized)
                walk(nested)
        elif isinstance(item, (list, tuple)):
            for nested in item:
                walk(nested)

    walk(value)
    return sorted(found)


def assert_safe_public_projection(value: Any) -> None:
    violations = public_projection_violations(value)
    if violations:
        raise ValueError("public projection contains Salus-internal commercial fields")


def fictional_commercial_candidates() -> dict[str, FictionalCommercialCandidate]:
    """Return isolated fictional commercial-engine references for adapter acceptance."""

    estimate_reference = content_sha256(
        {"source": "fictional-commercial-engine", "version": "SPA-COMMERCIAL-ESTIMATE-1.0.0"}
    )
    rate_reference = content_sha256(
        {"source": "fictional-governed-rate-card", "version": "SPA-RATE-CARD-1.0.0"}
    )
    definitions = (
        ("SPA-PKG-FOUNDATION", 7500, 15000, 0, 0, "Annual", "Four to six weeks"),
        ("SPA-PKG-READINESS", 18000, 35000, 2500, 5000, "Monthly", "Six to twelve weeks"),
        ("SPA-PKG-INTEGRATED", 40000, 85000, 6500, 12500, "Monthly", "Three to six months"),
        ("SPA-PKG-COMPLEX-MISSION", 90000, 225000, 15000, 35000, "Monthly", "Six to twelve months"),
    )
    return {
        package_key: FictionalCommercialCandidate(
            package_key=package_key,
            commercial_estimate_snapshot_sha256=estimate_reference,
            rate_card_snapshot_sha256=rate_reference,
            one_time_range_minimum=one_min,
            one_time_range_maximum=one_max,
            recurring_range_minimum=recurring_min,
            recurring_range_maximum=recurring_max,
            recurring_cadence=cadence,
            implementation_period=period,
            assumptions=(
                "Fictional internal prototype only.",
                "Final scope and price require qualified Salus review.",
                "Travel, specialists, equipment, partner work, and incident operations require separate scope.",
            ),
        )
        for package_key, one_min, one_max, recurring_min, recurring_max, cadence, period in definitions
    }


def _policy_payload(conn: Any, bundle: dict[str, Any], kind: str) -> dict[str, Any]:
    reference = bundle["components"][kind]
    row = conn.execute(
        f"SELECT snapshot_json FROM {POLICY_TABLES[kind]} WHERE version_key=?",
        (reference["version_key"],),
    ).fetchone()
    if not row:
        raise PolicyIntegrityError(f"{kind} snapshot is missing")
    definition = json.loads(row["snapshot_json"])
    return definition["payload"]


def _reported_answer(answer: Any) -> bool:
    return answer not in (None, "", [], "Unknown", "Declined", "Not Applicable")


def _level_label(level: int) -> str:
    return {
        0: "Evidence Needed",
        1: "Limited Indication",
        2: "Developing Indication",
        3: "Material Indication",
    }[max(0, min(3, int(level)))]


def _dimension_review(
    answers: dict[str, Any],
    questionnaire: dict[str, Any],
) -> tuple[dict[str, dict[str, Any]], dict[str, int]]:
    """Apply visible deterministic rules only to explicitly answered questions."""

    permitted = {item["question_key"]: item for item in questionnaire["questions"]}
    used = {key: value for key, value in answers.items() if key in permitted and _reported_answer(value)}
    locations = int(used.get("locations", 0) or 0)
    jurisdictions = int(used.get("jurisdictions", 0) or 0)
    concerns = used.get("reported_concerns", [])
    concerns = concerns if isinstance(concerns, list) else [concerns]
    people = str(used.get("people_exposed", ""))
    posture = str(used.get("capability_posture", ""))
    change = str(used.get("recent_change", ""))
    depth = str(used.get("investigation_depth", "Initial Pass"))
    org_type = str(used.get("organization_type", ""))

    exposure = 3 if ("100,000" in people or locations >= 50) else 2 if (locations >= 10 or "500" in people) else 1 if (locations or people) else 0
    threat = 3 if len(concerns) >= 3 else 2 if len(concerns) == 2 else 1 if concerns else 0
    vulnerability = 3 if change == "Yes" and len(concerns) >= 2 else 2 if len(concerns) >= 2 else 1 if concerns else 0
    consequence = 3 if ("100,000" in people or org_type in {"Critical Infrastructure", "Public Agency"}) else 2 if "500" in people else 1 if people else 0
    capability = 2 if ("inconsistently" in posture.casefold() or "varies materially" in posture.casefold()) else 1 if posture else 0
    complexity = 3 if jurisdictions >= 4 or locations >= 50 else 2 if jurisdictions >= 2 or locations >= 10 else 1 if locations or jurisdictions else 0
    urgency = 2 if change == "Yes" else 1 if change == "No" else 0
    service = {"Initial Pass": 1, "Intermediate Assessment": 2, "High Deep-Dive": 3}.get(depth, 0)
    levels = {
        "Exposure": exposure,
        "Threat and Hazard Environment": threat,
        "Vulnerability": vulnerability,
        "Consequence": consequence,
        "Capability": capability,
        "Complexity": complexity,
        "Urgency": urgency,
        "Service Intensity": service,
    }

    reviews: dict[str, dict[str, Any]] = {}
    for dimension in DIMENSIONS:
        linked = [
            item["question_key"]
            for item in questionnaire["questions"]
            if dimension in item["dimension_links"]
        ]
        basis = [key for key in linked if key in used]
        missing = [key for key in linked if key not in used]
        reviews[dimension] = {
            "state": _level_label(levels[dimension]),
            "classification": "Preliminary Inference",
            "basis_question_keys": basis,
            "reported_information": {key: used[key] for key in basis},
            "information_gaps": missing,
            "assumptions": [],
            "contradictions": [],
            "uncertainty": (
                "Evidence remains incomplete; a qualified Salus reviewer must validate the context."
                if missing else
                "Based only on the displayed fictional answers; independent Salus review remains required."
            ),
        }
    return reviews, levels


def _select_package(levels: dict[str, int], investigation_depth: str) -> str:
    """Select by transparent multi-factor gates; exposure alone never governs."""

    non_exposure = [
        levels[name] for name in DIMENSIONS if name != "Exposure"
    ]
    material_or_developing = sum(value >= 2 for value in non_exposure)
    depth = INVESTIGATION_LEVELS.get(investigation_depth, "Tier 1")
    depth_number = int(depth.rsplit(" ", 1)[-1])
    if depth_number >= 3 and material_or_developing >= 2:
        return "SPA-PKG-COMPLEX-MISSION"
    if depth_number >= 2 and (
        levels["Complexity"] >= 2 or levels["Service Intensity"] >= 2
    ):
        return "SPA-PKG-INTEGRATED"
    if (
        depth_number >= 2
        or levels["Capability"] >= 2
        or levels["Urgency"] >= 2
    ):
        return "SPA-PKG-READINESS"
    return "SPA-PKG-FOUNDATION"


def _load_package(catalogue: dict[str, Any], package_key: str) -> dict[str, Any]:
    matches = [item for item in catalogue["packages"] if item["package_key"] == package_key]
    if len(matches) != 1:
        raise PolicyIntegrityError("selected package is absent or duplicated")
    return matches[0]


def prepare_fictional_evaluation(
    conn: Any,
    case_key: str,
    *,
    created_at: str,
) -> dict[str, Any]:
    """Prepare and persist a non-binding evaluation for one repository-owned fixture."""

    if not created_at.strip():
        raise ValueError("creation time is required")
    initialize_policy_store(conn)
    bundle = load_fictional_policy_bundle(conn)
    cases = {case.case_key: case for case in FICTIONAL_CASES}
    if case_key not in cases:
        raise ValueError("only repository-owned fictional cases may be evaluated")
    case = cases[case_key]
    case_payload = case.model_dump(mode="json")
    expected_fixture_hash = bundle["fictional_fixture_hashes"].get(case_key)
    if content_sha256(case_payload) != expected_fixture_hash:
        raise PolicyIntegrityError("fictional case does not match the released bundle")

    questionnaire = _policy_payload(conn, bundle, "Questionnaire")
    catalogue = _policy_payload(conn, bundle, "Package Catalogue")
    price_policy = _policy_payload(conn, bundle, "Public Price Policy")
    reviews, levels = _dimension_review(case_payload["answers"], questionnaire)
    package_key = _select_package(levels, str(case_payload["answers"].get("investigation_depth", "")))
    package = _load_package(catalogue, package_key)
    candidates = fictional_commercial_candidates()
    if set(candidates) != {item["package_key"] for item in catalogue["packages"]}:
        raise PolicyIntegrityError("fictional commercial references do not match the package catalogue")
    commercial = candidates[package_key]

    public_price = {
        "currency": commercial.currency,
        "one_time_range_minimum": commercial.one_time_range_minimum,
        "one_time_range_maximum": commercial.one_time_range_maximum,
        "one_time_cadence": "One-time",
        "recurring_range_minimum": commercial.recurring_range_minimum,
        "recurring_range_maximum": commercial.recurring_range_maximum,
        "recurring_cadence": commercial.recurring_cadence,
        "implementation_period": commercial.implementation_period,
        "assumptions": list(commercial.assumptions),
        "inclusions": package["includes"],
        "exclusions": package["excludes"],
        "preliminary_notice": "Qualified Salus review is required before scope, price, or customer use.",
    }
    assert_safe_public_projection(public_price)
    if price_policy["qualified_salus_review_required"] is not True:
        raise PolicyIntegrityError("public price policy does not preserve Salus review")

    input_sha = content_sha256(case_payload)
    key_material = {
        "adapter_version": EVALUATION_ADAPTER_VERSION,
        "case_key": case_key,
        "input_sha256": input_sha,
        "policy_bundle_sha256": bundle["content_sha256"],
        "commercial_estimate_snapshot_sha256": commercial.commercial_estimate_snapshot_sha256,
        "rate_card_snapshot_sha256": commercial.rate_card_snapshot_sha256,
    }
    evaluation_key = "SPA-EVAL-" + content_sha256(key_material).upper()
    result = {
        "evaluation_key": evaluation_key,
        "status": EVALUATION_STATUS,
        "data_boundary": DATA_BOUNDARY,
        "fictional_only": True,
        "preliminary": True,
        "adapter_version": EVALUATION_ADAPTER_VERSION,
        "case": {
            "case_key": case.case_key,
            "display_name": case.display_name,
            "organization_context": case.organization_context,
            "input_sha256": input_sha,
        },
        "policy_bundle_sha256": bundle["content_sha256"],
        "commercial_estimate_snapshot_sha256": commercial.commercial_estimate_snapshot_sha256,
        "rate_card_snapshot_sha256": commercial.rate_card_snapshot_sha256,
        "dimensions": reviews,
        "recommended_package": {
            "package_key": package["package_key"],
            "prototype_name": package["prototype_name"],
            "purpose": package["purpose"],
            "capacity_ceiling": package["capacity_ceiling"],
            "classification": "Preliminary Inference",
        },
        "public_price": public_price,
        "information_gaps": sorted({
            gap for review in reviews.values() for gap in review["information_gaps"]
        }),
        "assumptions": list(commercial.assumptions),
        "contradictions": [],
        "authority": "A qualified Salus reviewer retains scope, package, price, release, and commercial authority.",
        "creates_charge": False,
        "creates_contract": False,
        "creates_membership": False,
        "creates_protected_member": False,
        "creates_disclosure": False,
        "has_routes": False,
    }
    snapshot_json = canonical_json(result)
    digest = content_sha256(snapshot_json)
    existing = conn.execute(
        "SELECT snapshot_json, content_sha256 FROM advisor_fictional_evaluation_snapshots WHERE evaluation_key=?",
        (evaluation_key,),
    ).fetchone()
    if existing:
        if existing["snapshot_json"] != snapshot_json or existing["content_sha256"] != digest:
            raise PolicyIntegrityError("fictional evaluation key collision")
    else:
        conn.execute(
            "INSERT INTO advisor_fictional_evaluation_snapshots(evaluation_key,case_key,status,data_boundary,fictional_only,adapter_version,policy_bundle_sha256,commercial_estimate_snapshot_sha256,rate_card_snapshot_sha256,input_sha256,snapshot_json,content_sha256,created_at) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (
                evaluation_key, case_key, EVALUATION_STATUS, DATA_BOUNDARY, 1,
                EVALUATION_ADAPTER_VERSION, bundle["content_sha256"],
                commercial.commercial_estimate_snapshot_sha256,
                commercial.rate_card_snapshot_sha256, input_sha,
                snapshot_json, digest, created_at.strip(),
            ),
        )
        conn.commit()
    return {**copy.deepcopy(result), "content_sha256": digest}


def load_fictional_evaluation(conn: Any, evaluation_key: str) -> dict[str, Any]:
    """Load an immutable fictional evaluation and fail closed on any mismatch."""

    row = conn.execute(
        "SELECT * FROM advisor_fictional_evaluation_snapshots WHERE evaluation_key=?",
        (evaluation_key,),
    ).fetchone()
    if not row:
        raise PolicyIntegrityError("fictional evaluation is missing")
    if (
        row["status"] != EVALUATION_STATUS
        or row["data_boundary"] != DATA_BOUNDARY
        or int(row["fictional_only"]) != 1
        or row["adapter_version"] != EVALUATION_ADAPTER_VERSION
        or content_sha256(row["snapshot_json"]) != row["content_sha256"]
    ):
        raise PolicyIntegrityError("fictional evaluation integrity check failed")
    result = json.loads(row["snapshot_json"])
    checks = {
        "evaluation_key": row["evaluation_key"],
        "status": row["status"],
        "data_boundary": row["data_boundary"],
        "adapter_version": row["adapter_version"],
        "policy_bundle_sha256": row["policy_bundle_sha256"],
        "commercial_estimate_snapshot_sha256": row["commercial_estimate_snapshot_sha256"],
        "rate_card_snapshot_sha256": row["rate_card_snapshot_sha256"],
    }
    if any(result.get(key) != value for key, value in checks.items()):
        raise PolicyIntegrityError("fictional evaluation reference check failed")
    if result["case"]["input_sha256"] != row["input_sha256"]:
        raise PolicyIntegrityError("fictional evaluation input reference check failed")
    if any(result.get(flag) is not False for flag in (
        "creates_charge", "creates_contract", "creates_membership",
        "creates_protected_member", "creates_disclosure", "has_routes",
    )):
        raise PolicyIntegrityError("fictional evaluation authority boundary failed")
    assert_safe_public_projection(result["public_price"])
    return {**result, "content_sha256": row["content_sha256"]}


def prepare_all_fictional_evaluations(conn: Any, *, created_at: str) -> list[dict[str, Any]]:
    return [
        prepare_fictional_evaluation(conn, case.case_key, created_at=created_at)
        for case in FICTIONAL_CASES
    ]


def _parse_utc(value: str) -> datetime:
    try:
        parsed = datetime.fromisoformat(value.strip().replace("Z", "+00:00"))
    except (TypeError, ValueError) as exc:
        raise ValueError("a valid timezone-aware time is required") from exc
    if parsed.tzinfo is None:
        raise ValueError("a timezone-aware time is required")
    return parsed.astimezone(timezone.utc)


def _utc_text(value: datetime) -> str:
    return value.astimezone(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _record_session_event(
    conn: Any,
    session_key: str,
    event_type: str,
    event_at: str,
    details: dict[str, Any],
) -> None:
    row = conn.execute(
        "SELECT MAX(event_sequence) AS latest FROM advisor_audit_events WHERE session_key=?",
        (session_key,),
    ).fetchone()
    sequence = int(row["latest"] or 0) + 1
    event = {
        "session_key": session_key,
        "event_sequence": sequence,
        "event_type": event_type,
        "event_at": event_at,
        "details": details,
        "contains_answer_content": False,
        "contains_contact_information": False,
        "creates_protected_member": False,
    }
    event_json = canonical_json(event)
    digest = content_sha256(event_json)
    conn.execute(
        "INSERT INTO advisor_audit_events(event_key,session_key,event_sequence,event_type,event_at,event_json,content_sha256) VALUES(?,?,?,?,?,?,?)",
        ("SPA-AUDIT-" + digest.upper(), session_key, sequence, event_type, event_at, event_json, digest),
    )


def start_fictional_session(
    conn: Any,
    case_key: str,
    *,
    created_at: str,
) -> dict[str, Any]:
    """Issue a new opaque token for one repository-owned fictional case."""

    initialize_policy_store(conn)
    created = _parse_utc(created_at)
    bundle = load_fictional_policy_bundle(conn)
    cases = {case.case_key: case for case in FICTIONAL_CASES}
    case = cases.get(case_key)
    if not case or content_sha256(case.model_dump(mode="json")) != bundle["fictional_fixture_hashes"].get(case_key):
        raise ValueError("only repository-owned fictional cases may start a session")
    token = secrets.token_urlsafe(32)
    token_digest = content_sha256(token)
    session_key = "SPA-SESSION-" + secrets.token_hex(16).upper()
    expires_at = _utc_text(created + timedelta(hours=SESSION_RETENTION_HOURS))
    questionnaire_version = bundle["components"]["Questionnaire"]["version_key"]
    try:
        conn.execute(
            "INSERT INTO advisor_sessions(session_key,case_key,status,data_boundary,fictional_only,policy_bundle_sha256,questionnaire_version_key,retention_policy_version,latest_answer_revision,current_token_sha256,created_at,expires_at,deleted_at) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (
                session_key, case_key, "Active", DATA_BOUNDARY, 1,
                bundle["content_sha256"], questionnaire_version,
                SESSION_RETENTION_POLICY, 0, token_digest,
                _utc_text(created), expires_at, None,
            ),
        )
        conn.execute(
            "INSERT INTO advisor_session_tokens(token_sha256,session_key,token_status,issued_at,superseded_at) VALUES(?,?,?,?,?)",
            (token_digest, session_key, "Active", _utc_text(created), None),
        )
        _record_session_event(
            conn, session_key, "Session Started", _utc_text(created),
            {"case_key": case_key, "expires_at": expires_at, "retention_policy_version": SESSION_RETENTION_POLICY},
        )
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    return {
        "session_token": token,
        "session_key": session_key,
        "case_key": case_key,
        "status": "Active",
        "fictional_only": True,
        "data_boundary": DATA_BOUNDARY,
        "created_at": _utc_text(created),
        "expires_at": expires_at,
        "retention_policy_version": SESSION_RETENTION_POLICY,
        "contact_information_required": False,
        "has_protected_member_access": False,
    }


def expire_fictional_sessions(conn: Any, *, as_of: str) -> list[str]:
    """Enforce server-side expiry and disable every active token."""

    now = _parse_utc(as_of)
    expired: list[str] = []
    rows = list(conn.execute("SELECT * FROM advisor_sessions WHERE status='Active'"))
    try:
        for row in rows:
            if _parse_utc(row["expires_at"]) <= now:
                conn.execute(
                    "DELETE FROM advisor_answer_revisions WHERE session_key=?",
                    (row["session_key"],),
                )
                conn.execute(
                    "UPDATE advisor_sessions SET status='Expired', current_token_sha256=NULL, latest_answer_revision=0 WHERE session_key=?",
                    (row["session_key"],),
                )
                conn.execute(
                    "UPDATE advisor_session_tokens SET token_status='Expired', superseded_at=? WHERE session_key=? AND token_status='Active'",
                    (_utc_text(now), row["session_key"]),
                )
                _record_session_event(
                    conn, row["session_key"], "Session Expired", _utc_text(now),
                    {
                        "retention_policy_version": row["retention_policy_version"],
                        "answer_content_deleted": True,
                    },
                )
                expired.append(row["session_key"])
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    return expired


def _active_session(conn: Any, token: str, *, as_of: str) -> Any:
    if not isinstance(token, str) or len(token) < 32:
        raise SessionAccessError("session is unavailable")
    token_digest = content_sha256(token)
    token_row = conn.execute(
        "SELECT * FROM advisor_session_tokens WHERE token_sha256=?",
        (token_digest,),
    ).fetchone()
    if not token_row or token_row["token_status"] != "Active":
        raise SessionAccessError("session is unavailable")
    session = conn.execute(
        "SELECT * FROM advisor_sessions WHERE session_key=?",
        (token_row["session_key"],),
    ).fetchone()
    if not session or session["status"] != "Active" or session["current_token_sha256"] != token_digest:
        raise SessionAccessError("session is unavailable")
    if _parse_utc(session["expires_at"]) <= _parse_utc(as_of):
        expire_fictional_sessions(conn, as_of=as_of)
        raise SessionAccessError("session is unavailable")
    if session["data_boundary"] != DATA_BOUNDARY or int(session["fictional_only"]) != 1:
        raise SessionAccessError("session is unavailable")
    return session


def load_fictional_session(conn: Any, token: str, *, as_of: str) -> dict[str, Any]:
    session = _active_session(conn, token, as_of=as_of)
    return {
        "session_key": session["session_key"],
        "case_key": session["case_key"],
        "status": session["status"],
        "data_boundary": session["data_boundary"],
        "fictional_only": True,
        "policy_bundle_sha256": session["policy_bundle_sha256"],
        "questionnaire_version_key": session["questionnaire_version_key"],
        "retention_policy_version": session["retention_policy_version"],
        "latest_answer_revision": int(session["latest_answer_revision"]),
        "created_at": session["created_at"],
        "expires_at": session["expires_at"],
        "contact_information_required": False,
        "has_protected_member_access": False,
    }


def rotate_fictional_session(
    conn: Any,
    token: str,
    *,
    rotated_at: str,
) -> dict[str, Any]:
    """Rotate an active token; the old token becomes unusable immediately."""

    session = _active_session(conn, token, as_of=rotated_at)
    new_token = secrets.token_urlsafe(32)
    new_digest = content_sha256(new_token)
    old_digest = content_sha256(token)
    at = _utc_text(_parse_utc(rotated_at))
    try:
        conn.execute(
            "UPDATE advisor_session_tokens SET token_status='Superseded', superseded_at=? WHERE token_sha256=?",
            (at, old_digest),
        )
        conn.execute(
            "INSERT INTO advisor_session_tokens(token_sha256,session_key,token_status,issued_at,superseded_at) VALUES(?,?,?,?,?)",
            (new_digest, session["session_key"], "Active", at, None),
        )
        conn.execute(
            "UPDATE advisor_sessions SET current_token_sha256=? WHERE session_key=?",
            (new_digest, session["session_key"]),
        )
        _record_session_event(conn, session["session_key"], "Session Token Rotated", at, {"old_token_replay_denied": True})
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    return {"session_token": new_token, **load_fictional_session(conn, new_token, as_of=rotated_at)}


def _question_by_key(conn: Any, bundle: dict[str, Any], question_key: str) -> dict[str, Any]:
    questionnaire = _policy_payload(conn, bundle, "Questionnaire")
    matches = [item for item in questionnaire["questions"] if item["question_key"] == question_key]
    if len(matches) != 1:
        raise ValueError("question is not in the released questionnaire")
    question = matches[0]
    if question.get("shown_when"):
        raise ValueError("conditional question is not available without its released display condition")
    return question


def append_fictional_answer_revision(
    conn: Any,
    token: str,
    submission: FictionalAnswerSubmission,
    *,
    created_at: str,
) -> dict[str, Any]:
    """Append one governed answer state without overwriting prior revisions."""

    session = _active_session(conn, token, as_of=created_at)
    bundle = load_fictional_policy_bundle(conn)
    if bundle["content_sha256"] != session["policy_bundle_sha256"]:
        raise PolicyIntegrityError("session policy reference is unavailable")
    question = _question_by_key(conn, bundle, submission.question_key)
    if submission.answer_state == "Answered":
        case = next(item for item in FICTIONAL_CASES if item.case_key == session["case_key"])
        if (
            submission.question_key not in case.answers
            or submission.value != case.answers[submission.question_key]
        ):
            raise ValueError("only the released fictional fixture value may be recorded")
        if question["choices"] and (
            not isinstance(submission.value, str)
            or submission.value not in question["choices"]
        ):
            raise ValueError("answer is outside the released choices")
    revision_number = int(session["latest_answer_revision"]) + 1
    answer_json = canonical_json(submission.value)
    at = _utc_text(_parse_utc(created_at))
    snapshot = {
        "session_key": session["session_key"],
        "revision_number": revision_number,
        "question_key": submission.question_key,
        "questionnaire_version_key": session["questionnaire_version_key"],
        "answer_state": submission.answer_state,
        "answer": submission.value,
        "created_at": at,
        "classification": "Prospect-Reported Fictional Information",
    }
    snapshot_json = canonical_json(snapshot)
    digest = content_sha256(snapshot_json)
    revision_key = "SPA-ANSWER-" + digest.upper()
    try:
        conn.execute(
            "INSERT INTO advisor_answer_revisions(revision_key,session_key,revision_number,question_key,questionnaire_version_key,answer_state,answer_json,content_sha256,created_at) VALUES(?,?,?,?,?,?,?,?,?)",
            (
                revision_key, session["session_key"], revision_number,
                submission.question_key, session["questionnaire_version_key"],
                submission.answer_state, answer_json, digest, at,
            ),
        )
        conn.execute(
            "UPDATE advisor_sessions SET latest_answer_revision=? WHERE session_key=?",
            (revision_number, session["session_key"]),
        )
        _record_session_event(
            conn, session["session_key"], "Answer Revision Appended", at,
            {"question_key": submission.question_key, "revision_number": revision_number, "answer_state": submission.answer_state},
        )
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    return {**snapshot, "revision_key": revision_key, "content_sha256": digest}


def current_fictional_answers(conn: Any, token: str, *, as_of: str) -> dict[str, dict[str, Any]]:
    """Resolve only the latest append-only revision for each answered question."""

    session = _active_session(conn, token, as_of=as_of)
    rows = list(conn.execute(
        "SELECT * FROM advisor_answer_revisions WHERE session_key=? ORDER BY revision_number",
        (session["session_key"],),
    ))
    current: dict[str, dict[str, Any]] = {}
    for row in rows:
        expected = {
            "session_key": session["session_key"],
            "revision_number": int(row["revision_number"]),
            "question_key": row["question_key"],
            "questionnaire_version_key": row["questionnaire_version_key"],
            "answer_state": row["answer_state"],
            "answer": json.loads(row["answer_json"]),
            "created_at": row["created_at"],
            "classification": "Prospect-Reported Fictional Information",
        }
        if content_sha256(canonical_json(expected)) != row["content_sha256"]:
            raise PolicyIntegrityError("answer revision integrity check failed")
        current[row["question_key"]] = {
            "revision_key": row["revision_key"],
            "revision_number": int(row["revision_number"]),
            "answer_state": row["answer_state"],
            "value": json.loads(row["answer_json"]),
            "questionnaire_version_key": row["questionnaire_version_key"],
            "classification": "Prospect-Reported Fictional Information",
        }
    return current


def delete_fictional_session(conn: Any, token: str, *, deleted_at: str) -> dict[str, Any]:
    """Delete fictional answer content while retaining content-free lifecycle evidence."""

    session = _active_session(conn, token, as_of=deleted_at)
    at = _utc_text(_parse_utc(deleted_at))
    try:
        conn.execute(
            "DELETE FROM advisor_answer_revisions WHERE session_key=?",
            (session["session_key"],),
        )
        conn.execute(
            "UPDATE advisor_session_tokens SET token_status='Deleted', superseded_at=? WHERE session_key=? AND token_status='Active'",
            (at, session["session_key"]),
        )
        conn.execute(
            "UPDATE advisor_sessions SET status='Deleted', current_token_sha256=NULL, latest_answer_revision=0, deleted_at=? WHERE session_key=?",
            (at, session["session_key"]),
        )
        _record_session_event(
            conn, session["session_key"], "Session Deleted", at,
            {"answer_content_deleted": True, "retention_policy_version": session["retention_policy_version"]},
        )
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    return {
        "session_key": session["session_key"],
        "status": "Deleted",
        "deleted_at": at,
        "answer_content_deleted": True,
        "contact_information_retained": False,
        "protected_member_record_created": False,
    }


def verify_fictional_session_audit(conn: Any, session_key: str) -> list[dict[str, Any]]:
    rows = list(conn.execute(
        "SELECT * FROM advisor_audit_events WHERE session_key=? ORDER BY event_sequence",
        (session_key,),
    ))
    verified: list[dict[str, Any]] = []
    for expected_sequence, row in enumerate(rows, start=1):
        if int(row["event_sequence"]) != expected_sequence:
            raise PolicyIntegrityError("session audit sequence is invalid")
        if content_sha256(row["event_json"]) != row["content_sha256"]:
            raise PolicyIntegrityError("session audit integrity check failed")
        event = json.loads(row["event_json"])
        if event["event_sequence"] != expected_sequence or event["session_key"] != session_key:
            raise PolicyIntegrityError("session audit reference check failed")
        if event["contains_answer_content"] or event["contains_contact_information"] or event["creates_protected_member"]:
            raise PolicyIntegrityError("session audit information boundary failed")
        verified.append(event)
    return verified


def prepare_session_fictional_evaluation(
    conn: Any,
    token: str,
    *,
    created_at: str,
) -> dict[str, Any]:
    """Prepare an immutable evaluation from the session's latest explicit revisions."""

    session = _active_session(conn, token, as_of=created_at)
    bundle = load_fictional_policy_bundle(conn)
    if bundle["content_sha256"] != session["policy_bundle_sha256"]:
        raise PolicyIntegrityError("session policy reference is unavailable")
    questionnaire = _policy_payload(conn, bundle, "Questionnaire")
    catalogue = _policy_payload(conn, bundle, "Package Catalogue")
    price_policy = _policy_payload(conn, bundle, "Public Price Policy")
    current = current_fictional_answers(conn, token, as_of=created_at)
    required_keys = {
        item["question_key"] for item in questionnaire["questions"] if item["required"]
    }
    missing_required = sorted(required_keys - set(current))
    if missing_required:
        raise ValueError("every required displayed question needs an explicit answer state")

    answered = {
        key: item["value"]
        for key, item in current.items()
        if item["answer_state"] == "Answered"
    }
    reviews, levels = _dimension_review(answered, questionnaire)
    for review in reviews.values():
        review["basis_answer_revision_keys"] = [
            current[key]["revision_key"]
            for key in review["basis_question_keys"]
        ]
        review["explicit_non_answer_states"] = {
            key: current[key]["answer_state"]
            for key in review["information_gaps"]
            if key in current
        }

    investigation_depth = str(answered.get("investigation_depth", "Initial Pass"))
    package_key = _select_package(levels, investigation_depth)
    package = _load_package(catalogue, package_key)
    candidates = fictional_commercial_candidates()
    if set(candidates) != {item["package_key"] for item in catalogue["packages"]}:
        raise PolicyIntegrityError("fictional commercial references do not match the package catalogue")
    commercial = candidates[package_key]
    if price_policy["qualified_salus_review_required"] is not True:
        raise PolicyIntegrityError("public price policy does not preserve Salus review")

    public_price = {
        "currency": commercial.currency,
        "one_time_range_minimum": commercial.one_time_range_minimum,
        "one_time_range_maximum": commercial.one_time_range_maximum,
        "one_time_cadence": "One-time",
        "recurring_range_minimum": commercial.recurring_range_minimum,
        "recurring_range_maximum": commercial.recurring_range_maximum,
        "recurring_cadence": commercial.recurring_cadence,
        "implementation_period": commercial.implementation_period,
        "assumptions": list(commercial.assumptions),
        "inclusions": package["includes"],
        "exclusions": package["excludes"],
        "preliminary_notice": "Qualified Salus review is required before scope, price, or customer use.",
    }
    assert_safe_public_projection(public_price)
    answer_state_sha = content_sha256(current)
    key_material = {
        "session_key": session["session_key"],
        "answer_revision": int(session["latest_answer_revision"]),
        "answer_state_sha256": answer_state_sha,
        "adapter_version": EVALUATION_ADAPTER_VERSION,
        "policy_bundle_sha256": bundle["content_sha256"],
        "commercial_estimate_snapshot_sha256": commercial.commercial_estimate_snapshot_sha256,
        "rate_card_snapshot_sha256": commercial.rate_card_snapshot_sha256,
    }
    evaluation_key = "SPA-SESSION-EVAL-" + content_sha256(key_material).upper()
    case = next(item for item in FICTIONAL_CASES if item.case_key == session["case_key"])
    result = {
        "evaluation_key": evaluation_key,
        "session_key": session["session_key"],
        "answer_revision": int(session["latest_answer_revision"]),
        "answer_state_sha256": answer_state_sha,
        "status": EVALUATION_STATUS,
        "data_boundary": DATA_BOUNDARY,
        "fictional_only": True,
        "preliminary": True,
        "adapter_version": EVALUATION_ADAPTER_VERSION,
        "case": {
            "case_key": case.case_key,
            "display_name": case.display_name,
            "organization_context": case.organization_context,
        },
        "answer_states": {
            key: {
                "answer_state": item["answer_state"],
                "revision_key": item["revision_key"],
            }
            for key, item in current.items()
        },
        "policy_bundle_sha256": bundle["content_sha256"],
        "governing_versions": {
            kind: reference["version_key"]
            for kind, reference in bundle["components"].items()
        },
        "commercial_estimate_snapshot_sha256": commercial.commercial_estimate_snapshot_sha256,
        "rate_card_snapshot_sha256": commercial.rate_card_snapshot_sha256,
        "dimensions": reviews,
        "recommended_investigation_depth": investigation_depth,
        "recommended_package": {
            "package_key": package["package_key"],
            "prototype_name": package["prototype_name"],
            "purpose": package["purpose"],
            "capacity_ceiling": package["capacity_ceiling"],
            "classification": "Preliminary Inference",
        },
        "public_price": public_price,
        "information_gaps": sorted({
            gap for review in reviews.values() for gap in review["information_gaps"]
        }),
        "assumptions": list(commercial.assumptions),
        "contradictions": [],
        "authority": "A qualified Salus reviewer retains scope, package, price, release, and commercial authority.",
        "creates_charge": False,
        "creates_contract": False,
        "creates_membership": False,
        "creates_protected_member": False,
        "creates_disclosure": False,
        "has_routes": False,
    }
    snapshot_json = canonical_json(result)
    digest = content_sha256(snapshot_json)
    existing = conn.execute(
        "SELECT snapshot_json, content_sha256 FROM advisor_session_evaluation_snapshots WHERE evaluation_key=?",
        (evaluation_key,),
    ).fetchone()
    try:
        if existing:
            if existing["snapshot_json"] != snapshot_json or existing["content_sha256"] != digest:
                raise PolicyIntegrityError("session evaluation key collision")
        else:
            conn.execute(
                "INSERT INTO advisor_session_evaluation_snapshots(evaluation_key,session_key,answer_revision,answer_state_sha256,status,data_boundary,fictional_only,adapter_version,policy_bundle_sha256,commercial_estimate_snapshot_sha256,rate_card_snapshot_sha256,snapshot_json,content_sha256,created_at) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                (
                    evaluation_key, session["session_key"],
                    int(session["latest_answer_revision"]), answer_state_sha,
                    EVALUATION_STATUS, DATA_BOUNDARY, 1,
                    EVALUATION_ADAPTER_VERSION, bundle["content_sha256"],
                    commercial.commercial_estimate_snapshot_sha256,
                    commercial.rate_card_snapshot_sha256,
                    snapshot_json, digest, _utc_text(_parse_utc(created_at)),
                ),
            )
            _record_session_event(
                conn, session["session_key"], "Session Evaluated",
                _utc_text(_parse_utc(created_at)),
                {
                    "evaluation_key": evaluation_key,
                    "answer_revision": int(session["latest_answer_revision"]),
                    "answer_content_recorded": False,
                },
            )
            conn.commit()
    except Exception:
        conn.rollback()
        raise
    return {**copy.deepcopy(result), "content_sha256": digest}


def load_session_fictional_evaluation(conn: Any, evaluation_key: str) -> dict[str, Any]:
    """Verify an immutable session evaluation without requiring an active token."""

    row = conn.execute(
        "SELECT * FROM advisor_session_evaluation_snapshots WHERE evaluation_key=?",
        (evaluation_key,),
    ).fetchone()
    if not row:
        raise PolicyIntegrityError("session evaluation is missing")
    if (
        row["status"] != EVALUATION_STATUS
        or row["data_boundary"] != DATA_BOUNDARY
        or int(row["fictional_only"]) != 1
        or row["adapter_version"] != EVALUATION_ADAPTER_VERSION
        or content_sha256(row["snapshot_json"]) != row["content_sha256"]
    ):
        raise PolicyIntegrityError("session evaluation integrity check failed")
    result = json.loads(row["snapshot_json"])
    checks = {
        "evaluation_key": row["evaluation_key"],
        "session_key": row["session_key"],
        "answer_revision": int(row["answer_revision"]),
        "answer_state_sha256": row["answer_state_sha256"],
        "status": row["status"],
        "data_boundary": row["data_boundary"],
        "adapter_version": row["adapter_version"],
        "policy_bundle_sha256": row["policy_bundle_sha256"],
        "commercial_estimate_snapshot_sha256": row["commercial_estimate_snapshot_sha256"],
        "rate_card_snapshot_sha256": row["rate_card_snapshot_sha256"],
    }
    if any(result.get(key) != value for key, value in checks.items()):
        raise PolicyIntegrityError("session evaluation reference check failed")
    if any(result.get(flag) is not False for flag in (
        "creates_charge", "creates_contract", "creates_membership",
        "creates_protected_member", "creates_disclosure", "has_routes",
    )):
        raise PolicyIntegrityError("session evaluation authority boundary failed")
    assert_safe_public_projection(result["public_price"])
    return {**result, "content_sha256": row["content_sha256"]}


def retrieve_session_fictional_recommendation(
    conn: Any,
    token: str,
    evaluation_key: str,
    *,
    as_of: str,
) -> dict[str, Any]:
    """Return a sanitized recommendation only for the active, unchanged session."""

    session = _active_session(conn, token, as_of=as_of)
    evaluation = load_session_fictional_evaluation(conn, evaluation_key)
    if evaluation["session_key"] != session["session_key"]:
        raise SessionAccessError("session is unavailable")
    current = current_fictional_answers(conn, token, as_of=as_of)
    if (
        evaluation["answer_revision"] != int(session["latest_answer_revision"])
        or evaluation["answer_state_sha256"] != content_sha256(current)
    ):
        raise PolicyIntegrityError("session answers changed; prepare a new evaluation")
    result = {
        "result_heading": "Your Salus Recommendation",
        "evaluation_key": evaluation["evaluation_key"],
        "status": evaluation["status"],
        "fictional_only": True,
        "demonstration_notice": "Internal fictional demonstration; no customer release is authorized.",
        "preliminary": True,
        "organization_profile": evaluation["case"],
        "dimensions": {
            name: {
                "state": review["state"],
                "classification": review["classification"],
                "basis_question_keys": review["basis_question_keys"],
                "information_gaps": review["information_gaps"],
                "explicit_non_answer_states": review["explicit_non_answer_states"],
                "uncertainty": review["uncertainty"],
            }
            for name, review in evaluation["dimensions"].items()
        },
        "recommended_investigation_depth": evaluation["recommended_investigation_depth"],
        "primary_package": evaluation["recommended_package"],
        "price_ranges": evaluation["public_price"],
        "assumptions": evaluation["assumptions"],
        "contradictions": evaluation["contradictions"],
        "information_gaps": evaluation["information_gaps"],
        "governing_versions": evaluation["governing_versions"],
        "estimate_snapshot_reference": evaluation["commercial_estimate_snapshot_sha256"],
        "authority": evaluation["authority"],
        "what_happens_next": [
            "Review or revise the fictional answers.",
            "A qualified Salus reviewer evaluates scope, package, and price.",
            "No charge, contract, membership, or Protected Member record is created.",
        ],
        "may_stop": True,
        "may_revise": True,
        "may_save_or_submit": True,
        "save_or_submit_notice": (
            "Fictional contact details are requested only after an explicit "
            "choice and affirmative consent."
        ),
        "creates_charge": False,
        "creates_contract": False,
        "creates_membership": False,
        "creates_protected_member": False,
        "creates_disclosure": False,
        "has_routes": False,
    }
    assert_safe_public_projection(result)
    return result



def _display_utc(value: datetime) -> str:
    return value.astimezone(timezone.utc).strftime("%d %B %Y %H:%M UTC")


def build_fictional_consent_notice() -> dict[str, Any]:
    """Build the exact notice shown before fictional contact retention."""

    return {
        "notice_version": CONSENT_NOTICE_VERSION,
        "status": POLICY_STATUS,
        "data_boundary": DATA_BOUNDARY,
        "fictional_only": True,
        "purpose": CONSENT_PURPOSE,
        "recipient": "Qualified Salus reviewers in the internal fictional prototype",
        "authorized_fields": list(CONSENTED_FIELDS),
        "retention_days": PROSPECT_RETENTION_DAYS,
        "retention_policy_version": PROSPECT_RETENTION_POLICY,
        "what_happens_next": [
            "The fictional recommendation and fictional contact details are retained for the selected purpose.",
            "A qualified Salus reviewer may review the fictional submission.",
            "Correction, withdrawal, and deletion remain available within the governed lifecycle.",
        ],
        "creates_charge": False,
        "creates_contract": False,
        "creates_membership": False,
        "creates_protected_member": False,
        "creates_disclosure": False,
        "authorizes_customer_release": False,
        "has_routes": False,
    }


def install_fictional_consent_notice(conn: Any, *, released_at: str) -> dict[str, Any]:
    """Install the immutable fictional notice idempotently."""

    initialize_policy_store(conn)
    released = _utc_text(_parse_utc(released_at))
    notice = build_fictional_consent_notice()
    notice_json = canonical_json(notice)
    digest = content_sha256(notice_json)
    existing = conn.execute(
        "SELECT * FROM advisor_consent_notice_versions WHERE notice_version=?",
        (CONSENT_NOTICE_VERSION,),
    ).fetchone()
    try:
        if existing:
            if (
                existing["notice_json"] != notice_json
                or existing["content_sha256"] != digest
                or existing["status"] != POLICY_STATUS
                or existing["data_boundary"] != DATA_BOUNDARY
                or int(existing["fictional_only"]) != 1
            ):
                raise PolicyIntegrityError("consent notice version collision")
        else:
            conn.execute(
                "INSERT INTO advisor_consent_notice_versions(notice_version,status,data_boundary,fictional_only,notice_json,content_sha256,released_at) VALUES(?,?,?,?,?,?,?)",
                (
                    CONSENT_NOTICE_VERSION, POLICY_STATUS, DATA_BOUNDARY, 1,
                    notice_json, digest, released,
                ),
            )
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    return {**notice, "content_sha256": digest, "released_at": released}


def load_fictional_consent_notice(conn: Any) -> dict[str, Any]:
    """Load and verify the released fictional consent notice."""

    row = conn.execute(
        "SELECT * FROM advisor_consent_notice_versions WHERE notice_version=?",
        (CONSENT_NOTICE_VERSION,),
    ).fetchone()
    if not row:
        raise PolicyIntegrityError("fictional consent notice is missing")
    if (
        row["status"] != POLICY_STATUS
        or row["data_boundary"] != DATA_BOUNDARY
        or int(row["fictional_only"]) != 1
        or content_sha256(row["notice_json"]) != row["content_sha256"]
    ):
        raise PolicyIntegrityError("fictional consent notice integrity check failed")
    notice = json.loads(row["notice_json"])
    if (
        notice.get("notice_version") != row["notice_version"]
        or notice.get("authorized_fields") != list(CONSENTED_FIELDS)
        or notice.get("purpose") != CONSENT_PURPOSE
        or any(notice.get(flag) is not False for flag in (
            "creates_charge", "creates_contract", "creates_membership",
            "creates_protected_member", "creates_disclosure",
            "authorizes_customer_release", "has_routes",
        ))
    ):
        raise PolicyIntegrityError("fictional consent notice boundary failed")
    return {**notice, "content_sha256": row["content_sha256"], "released_at": row["released_at"]}


def load_fictional_consent(conn: Any, consent_key: str) -> dict[str, Any]:
    """Load and verify immutable consent evidence without contact values."""

    row = conn.execute(
        "SELECT * FROM advisor_consents WHERE consent_key=?", (consent_key,)
    ).fetchone()
    if not row or content_sha256(row["snapshot_json"]) != row["content_sha256"]:
        raise PolicyIntegrityError("fictional consent integrity check failed")
    result = json.loads(row["snapshot_json"])
    checks = {
        "consent_key": row["consent_key"],
        "session_key": row["session_key"],
        "evaluation_key": row["evaluation_key"],
        "notice_version": row["notice_version"],
        "notice_sha256": row["notice_sha256"],
        "status": row["status"],
        "action": row["action"],
        "purpose": row["purpose"],
        "authorized_fields": json.loads(row["authorized_fields_json"]),
        "consented_at": row["consented_at"],
        "consented_display": row["consented_display"],
        "expires_at": row["expires_at"],
        "retention_policy_version": row["retention_policy_version"],
        "lifecycle_state": row["lifecycle_state"],
    }
    if (
        any(result.get(key) != value for key, value in checks.items())
        or int(row["affirmative_action"]) != 1
        or result.get("affirmative_consent") is not True
        or set(result.get("authorized_fields", [])) != set(CONSENTED_FIELDS)
        or any(result.get(flag) is not False for flag in (
            "creates_charge", "creates_contract", "creates_membership",
            "creates_protected_member", "creates_disclosure",
            "authorizes_customer_release",
        ))
    ):
        raise PolicyIntegrityError("fictional consent boundary failed")
    serialized = canonical_json(result).casefold()
    if "contact_email" in serialized and "@example.com" in serialized:
        raise PolicyIntegrityError("consent evidence contains contact values")
    return {**result, "content_sha256": row["content_sha256"]}


def load_fictional_prospect(conn: Any, prospect_key: str) -> dict[str, Any]:
    """Load and verify a fictional prospect retained under exact consent."""

    row = conn.execute(
        "SELECT * FROM advisor_prospects WHERE prospect_key=?", (prospect_key,)
    ).fetchone()
    if not row or content_sha256(row["payload_json"]) != row["content_sha256"]:
        raise PolicyIntegrityError("fictional prospect integrity check failed")
    result = json.loads(row["payload_json"])
    checks = {
        "prospect_key": row["prospect_key"],
        "session_key": row["session_key"],
        "evaluation_key": row["evaluation_key"],
        "consent_key": row["consent_key"],
        "status": row["status"],
        "data_boundary": row["data_boundary"],
        "created_at": row["created_at"],
        "expires_at": row["expires_at"],
        "retention_policy_version": row["retention_policy_version"],
        "correction_state": row["correction_state"],
        "withdrawal_state": row["withdrawal_state"],
        "deletion_state": row["deletion_state"],
    }
    if (
        any(result.get(key) != value for key, value in checks.items())
        or int(row["fictional_only"]) != 1
        or result.get("fictional_only") is not True
        or any(result.get(flag) is not False for flag in (
            "creates_charge", "creates_contract", "creates_membership",
            "creates_protected_member", "creates_disclosure",
            "authorizes_customer_release",
        ))
    ):
        raise PolicyIntegrityError("fictional prospect boundary failed")
    assert_safe_public_projection(result["recommendation"])
    return {**result, "content_sha256": row["content_sha256"]}


def record_fictional_consent_and_prospect(
    conn: Any,
    token: str,
    evaluation_key: str,
    submission: FictionalProspectSubmission,
    *,
    consented_at: str,
) -> dict[str, Any]:
    """Retain one exact fictional prospect only after explicit informed consent."""

    at = _parse_utc(consented_at)
    session = _active_session(conn, token, as_of=consented_at)
    recommendation = retrieve_session_fictional_recommendation(
        conn, token, evaluation_key, as_of=consented_at
    )
    evaluation = load_session_fictional_evaluation(conn, evaluation_key)
    expected = FICTIONAL_PROSPECT_CONTACTS.get(session["case_key"])
    supplied = {
        "organization_display_name": submission.organization_display_name,
        "contact_name": submission.contact_name,
        "contact_email": submission.contact_email,
    }
    if expected is None or supplied != expected:
        raise ValueError("only the released fictional contact fixture may be retained")
    notice = install_fictional_consent_notice(conn, released_at=consented_at)
    if (
        submission.notice_version != notice["notice_version"]
        or set(submission.authorized_fields) != set(notice["authorized_fields"])
        or evaluation["session_key"] != session["session_key"]
    ):
        raise PolicyIntegrityError("consent does not cover the current fictional evaluation")

    at_text = _utc_text(at)
    expires_at = _utc_text(at + timedelta(days=PROSPECT_RETENTION_DAYS))
    status = (
        "Saved — Fictional"
        if submission.action == "Save for Later"
        else "Submitted — Fictional; Awaiting Salus Review"
    )
    lifecycle_state = "Retained under affirmative fictional consent"
    consent_seed = {
        "session_key": session["session_key"],
        "evaluation_key": evaluation_key,
        "notice_version": notice["notice_version"],
        "notice_sha256": notice["content_sha256"],
        "status": "Affirmative Consent Recorded — Fictional",
        "action": submission.action,
        "purpose": CONSENT_PURPOSE,
        "authorized_fields": list(submission.authorized_fields),
        "affirmative_consent": True,
        "consented_at": at_text,
        "consented_display": _display_utc(at),
        "expires_at": expires_at,
        "retention_policy_version": PROSPECT_RETENTION_POLICY,
        "lifecycle_state": lifecycle_state,
        "withdrawal_available": True,
        "correction_available": True,
        "deletion_available": True,
        "creates_charge": False,
        "creates_contract": False,
        "creates_membership": False,
        "creates_protected_member": False,
        "creates_disclosure": False,
        "authorizes_customer_release": False,
    }
    consent_key = "SPA-CONSENT-" + content_sha256(consent_seed).upper()
    consent = {"consent_key": consent_key, **consent_seed}
    consent_json = canonical_json(consent)
    consent_digest = content_sha256(consent_json)

    prospect_seed = {
        "session_key": session["session_key"],
        "evaluation_key": evaluation_key,
        "consent_key": consent_key,
        "status": status,
        "data_boundary": DATA_BOUNDARY,
        "fictional_only": True,
        "classification": "Fictional Prospect-Reported Information",
        "organization_display_name": submission.organization_display_name,
        "contact_name": submission.contact_name,
        "contact_email": submission.contact_email,
        "recommendation": recommendation,
        "created_at": at_text,
        "created_display": _display_utc(at),
        "expires_at": expires_at,
        "retention_policy_version": PROSPECT_RETENTION_POLICY,
        "correction_state": "Available through governed Salus review",
        "withdrawal_state": "Available before any separately authorized next step",
        "deletion_state": "Available under the governed retention lifecycle",
        "what_happens_next": (
            "A qualified Salus reviewer may review this fictional submission; "
            "no scope, price, customer relationship, or service commitment is established."
        ),
        "creates_charge": False,
        "creates_contract": False,
        "creates_membership": False,
        "creates_protected_member": False,
        "creates_disclosure": False,
        "authorizes_customer_release": False,
    }
    prospect_key = "SPA-PROSPECT-" + content_sha256(prospect_seed).upper()
    prospect = {"prospect_key": prospect_key, **prospect_seed}
    prospect_json = canonical_json(prospect)
    prospect_digest = content_sha256(prospect_json)
    token_digest = content_sha256(token)
    try:
        conn.execute(
            "INSERT INTO advisor_consents(consent_key,session_key,evaluation_key,notice_version,notice_sha256,status,action,purpose,authorized_fields_json,affirmative_action,consented_at,consented_display,expires_at,retention_policy_version,lifecycle_state,withdrawn_at,deleted_at,snapshot_json,content_sha256) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (
                consent_key, session["session_key"], evaluation_key,
                notice["notice_version"], notice["content_sha256"],
                consent["status"], submission.action, CONSENT_PURPOSE,
                canonical_json(list(submission.authorized_fields)), 1, at_text,
                consent["consented_display"], expires_at, PROSPECT_RETENTION_POLICY,
                lifecycle_state, None, None, consent_json, consent_digest,
            ),
        )
        conn.execute(
            "INSERT INTO advisor_prospects(prospect_key,session_key,evaluation_key,consent_key,status,data_boundary,fictional_only,payload_json,content_sha256,created_at,expires_at,retention_policy_version,correction_state,withdrawal_state,deletion_state) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (
                prospect_key, session["session_key"], evaluation_key, consent_key,
                status, DATA_BOUNDARY, 1, prospect_json, prospect_digest,
                at_text, expires_at, PROSPECT_RETENTION_POLICY,
                prospect["correction_state"], prospect["withdrawal_state"],
                prospect["deletion_state"],
            ),
        )
        conn.execute(
            "DELETE FROM advisor_answer_revisions WHERE session_key=?",
            (session["session_key"],),
        )
        conn.execute(
            "UPDATE advisor_sessions SET status=?, current_token_sha256=NULL WHERE session_key=?",
            ("Saved" if submission.action == "Save for Later" else "Submitted", session["session_key"]),
        )
        conn.execute(
            "UPDATE advisor_session_tokens SET token_status=?, superseded_at=? WHERE token_sha256=?",
            ("Saved" if submission.action == "Save for Later" else "Submitted", at_text, token_digest),
        )
        _record_session_event(
            conn,
            session["session_key"],
            "Prospect Saved" if submission.action == "Save for Later" else "Prospect Submitted",
            at_text,
            {
                "prospect_key": prospect_key,
                "consent_key": consent_key,
                "evaluation_key": evaluation_key,
                "status": status,
                "retention_policy_version": PROSPECT_RETENTION_POLICY,
                "answer_content_deleted": True,
            },
        )
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    return {
        "prospect_key": prospect_key,
        "consent_key": consent_key,
        "evaluation_key": evaluation_key,
        "status": status,
        "fictional_only": True,
        "data_boundary": DATA_BOUNDARY,
        "created_at": at_text,
        "created_display": _display_utc(at),
        "expires_at": expires_at,
        "retention_policy_version": PROSPECT_RETENTION_POLICY,
        "awaiting_salus_review": submission.action == "Submit for Salus Review",
        "creates_charge": False,
        "creates_contract": False,
        "creates_membership": False,
        "creates_protected_member": False,
        "creates_disclosure": False,
        "authorizes_customer_release": False,
    }



def _fictional_review_status(decision: str) -> str:
    return {
        "Proceed to Fictional Scoping": (
            "Accepted for Fictional Scoping — Separate Salus Approval Required"
        ),
        "Questions Required": "Awaiting Fictional Prospect Information",
        "Decline — No Fit": "Declined — Fictional; No Commitment Created",
        "Close — No Action": "Closed — Fictional; No Action Authorized",
    }[decision]


def load_fictional_staff_review(conn: Any, review_key: str) -> dict[str, Any]:
    """Load and verify one immutable fictional staff-review decision."""

    row = conn.execute(
        "SELECT * FROM advisor_prospect_review_decisions WHERE review_key=?",
        (review_key,),
    ).fetchone()
    if not row or content_sha256(row["snapshot_json"]) != row["content_sha256"]:
        raise PolicyIntegrityError("fictional staff review integrity check failed")
    result = json.loads(row["snapshot_json"])
    checks = {
        "review_key": row["review_key"],
        "prospect_key": row["prospect_key"],
        "review_sequence": int(row["review_sequence"]),
        "status": row["status"],
        "decision": row["decision"],
        "reviewer_key": row["reviewer_key"],
        "reviewer_role": row["reviewer_role"],
        "data_boundary": row["data_boundary"],
        "basis_sha256": row["basis_sha256"],
        "supersedes_review_key": row["supersedes_review_key"],
        "correction_reason": row["correction_reason"],
        "created_at": row["created_at"],
    }
    reviewer = FICTIONAL_STAFF_REVIEWERS.get(row["reviewer_key"])
    if (
        any(result.get(key) != value for key, value in checks.items())
        or int(row["fictional_only"]) != 1
        or result.get("fictional_only") is not True
        or result.get("fictional_acceptance_simulation") is not True
        or reviewer is None
        or reviewer["reviewer_role"] != row["reviewer_role"]
        or result.get("reviewer_fixture_sha256") != content_sha256(reviewer)
        or result.get("basis_sha256") != content_sha256(result.get("basis", {}))
        or any(result.get(flag) is not False for flag in (
            "establishes_scope", "changes_package", "changes_price",
            "creates_charge", "creates_contract", "creates_membership",
            "creates_protected_member", "creates_disclosure",
            "authorizes_customer_release", "authorizes_onboarding",
        ))
    ):
        raise PolicyIntegrityError("fictional staff review boundary failed")
    review_text = canonical_json(result).casefold()
    if "@example.com" in review_text or "contact_email" in review_text:
        raise PolicyIntegrityError("fictional staff review contains contact information")
    return {**result, "content_sha256": row["content_sha256"]}


def fictional_staff_review_history(
    conn: Any, prospect_key: str
) -> list[dict[str, Any]]:
    """Return hash-verified review history in immutable sequence order."""

    rows = list(conn.execute(
        "SELECT review_key FROM advisor_prospect_review_decisions "
        "WHERE prospect_key=? ORDER BY review_sequence",
        (prospect_key,),
    ))
    history = [load_fictional_staff_review(conn, row["review_key"]) for row in rows]
    for expected, review in enumerate(history, start=1):
        if review["review_sequence"] != expected:
            raise PolicyIntegrityError("fictional staff review sequence is incomplete")
        if expected == 1 and review["supersedes_review_key"] is not None:
            raise PolicyIntegrityError("first fictional staff review cannot supersede another")
        if expected > 1 and review["supersedes_review_key"] != history[expected - 2]["review_key"]:
            raise PolicyIntegrityError("fictional staff review supersession lineage failed")
    return history


def load_current_fictional_staff_review(
    conn: Any, prospect_key: str
) -> dict[str, Any]:
    """Load the server-controlled current review pointer and immutable decision."""

    state = conn.execute(
        "SELECT * FROM advisor_prospect_review_state WHERE prospect_key=?",
        (prospect_key,),
    ).fetchone()
    if not state:
        raise PolicyIntegrityError("fictional prospect has no staff review")
    review = load_fictional_staff_review(conn, state["current_review_key"])
    if (
        review["prospect_key"] != prospect_key
        or review["review_sequence"] != int(state["review_sequence"])
        or review["status"] != state["status"]
    ):
        raise PolicyIntegrityError("fictional staff review current state failed")
    return review


def record_fictional_staff_review(
    conn: Any,
    prospect_key: str,
    command: FictionalStaffReviewCommand,
    *,
    reviewed_at: str,
) -> dict[str, Any]:
    """Record a fictional staff decision without creating commercial authority."""

    initialize_policy_store(conn)
    at = _parse_utc(reviewed_at)
    prospect = load_fictional_prospect(conn, prospect_key)
    consent = load_fictional_consent(conn, prospect["consent_key"])
    if prospect["status"] != "Submitted — Fictional; Awaiting Salus Review":
        raise PolicyIntegrityError("only a submitted fictional prospect may be reviewed")
    if consent["lifecycle_state"] != "Retained under affirmative fictional consent":
        raise PolicyIntegrityError("fictional prospect consent is not active")
    if _parse_utc(prospect["expires_at"]) <= at or _parse_utc(consent["expires_at"]) <= at:
        raise PolicyIntegrityError("fictional prospect consent has expired")
    reviewer = FICTIONAL_STAFF_REVIEWERS.get(command.reviewer_key)
    if (
        reviewer is None
        or reviewer["fictional_only"] is not True
        or reviewer["reviewer_role"] != command.reviewer_role
    ):
        raise PolicyIntegrityError("fictional reviewer role is not authorized")

    state = conn.execute(
        "SELECT * FROM advisor_prospect_review_state WHERE prospect_key=?",
        (prospect_key,),
    ).fetchone()
    if state:
        if command.supersedes_review_key != state["current_review_key"]:
            raise PolicyIntegrityError("review correction must supersede the current decision")
        sequence = int(state["review_sequence"]) + 1
    else:
        if command.supersedes_review_key is not None:
            raise PolicyIntegrityError("first review cannot supersede another decision")
        sequence = 1

    evaluation = load_session_fictional_evaluation(conn, prospect["evaluation_key"])
    basis = {
        "prospect_key": prospect_key,
        "prospect_snapshot_sha256": prospect["content_sha256"],
        "consent_key": consent["consent_key"],
        "consent_snapshot_sha256": consent["content_sha256"],
        "evaluation_key": evaluation["evaluation_key"],
        "evaluation_snapshot_sha256": evaluation["content_sha256"],
        "policy_bundle_sha256": evaluation["policy_bundle_sha256"],
        "governing_versions": evaluation["governing_versions"],
        "commercial_estimate_snapshot_sha256": (
            evaluation["commercial_estimate_snapshot_sha256"]
        ),
    }
    basis_sha256 = content_sha256(basis)
    at_text = _utc_text(at)
    status = _fictional_review_status(command.decision)
    seed = {
        "prospect_key": prospect_key,
        "review_sequence": sequence,
        "status": status,
        "decision": command.decision,
        "reviewer_key": command.reviewer_key,
        "reviewer_role": command.reviewer_role,
        "reviewer_fixture_sha256": content_sha256(reviewer),
        "qualifications_confirmed": True,
        "fictional_only": True,
        "fictional_acceptance_simulation": True,
        "data_boundary": DATA_BOUNDARY,
        "basis": basis,
        "basis_sha256": basis_sha256,
        "rationale": command.rationale,
        "assumptions": list(command.assumptions),
        "information_needed": list(command.information_needed),
        "supersedes_review_key": command.supersedes_review_key,
        "correction_reason": command.correction_reason,
        "created_at": at_text,
        "created_display": _display_utc(at),
        "authority": (
            "This fictional acceptance simulation records a preliminary Salus review "
            "decision only. Separate qualified approval is required for scope, package, "
            "price, customer release, onboarding, or commitment."
        ),
        "recommended_next_step": {
            "Proceed to Fictional Scoping": "Prepare a separate fictional scope for review.",
            "Questions Required": "Request only the identified fictional information.",
            "Decline — No Fit": "Record the non-binding fictional disposition.",
            "Close — No Action": "Retain the fictional closure evidence through expiry.",
        }[command.decision],
        "establishes_scope": False,
        "changes_package": False,
        "changes_price": False,
        "creates_charge": False,
        "creates_contract": False,
        "creates_membership": False,
        "creates_protected_member": False,
        "creates_disclosure": False,
        "authorizes_customer_release": False,
        "authorizes_onboarding": False,
    }
    review_key = "SPA-REVIEW-" + content_sha256(seed).upper()
    review = {"review_key": review_key, **seed}
    snapshot_json = canonical_json(review)
    digest = content_sha256(snapshot_json)
    try:
        conn.execute(
            "INSERT INTO advisor_prospect_review_decisions(review_key,prospect_key,review_sequence,status,decision,reviewer_key,reviewer_role,data_boundary,fictional_only,basis_sha256,supersedes_review_key,correction_reason,snapshot_json,content_sha256,created_at) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (
                review_key, prospect_key, sequence, status, command.decision,
                command.reviewer_key, command.reviewer_role, DATA_BOUNDARY, 1,
                basis_sha256, command.supersedes_review_key,
                command.correction_reason, snapshot_json, digest, at_text,
            ),
        )
        if state:
            conn.execute(
                "UPDATE advisor_prospect_review_state SET current_review_key=?,review_sequence=?,status=?,updated_at=? WHERE prospect_key=?",
                (review_key, sequence, status, at_text, prospect_key),
            )
        else:
            conn.execute(
                "INSERT INTO advisor_prospect_review_state(prospect_key,current_review_key,review_sequence,status,updated_at) VALUES(?,?,?,?,?)",
                (prospect_key, review_key, sequence, status, at_text),
            )
        _record_session_event(
            conn,
            prospect["session_key"],
            "Fictional Staff Review Recorded",
            at_text,
            {
                "prospect_key": prospect_key,
                "review_key": review_key,
                "review_sequence": sequence,
                "decision": command.decision,
                "status": status,
                "reviewer_key": command.reviewer_key,
                "fictional_acceptance_simulation": True,
            },
        )
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    return {**review, "content_sha256": digest}



def load_fictional_scoping_handoff(conn: Any, handoff_key: str) -> dict[str, Any]:
    """Load and verify one immutable nonbinding fictional scope-draft handoff."""

    row = conn.execute(
        "SELECT * FROM advisor_fictional_scoping_handoffs WHERE handoff_key=?",
        (handoff_key,),
    ).fetchone()
    if not row or content_sha256(row["snapshot_json"]) != row["content_sha256"]:
        raise PolicyIntegrityError("fictional scoping handoff integrity check failed")
    result = json.loads(row["snapshot_json"])
    checks = {
        "handoff_key": row["handoff_key"],
        "prospect_key": row["prospect_key"],
        "authorizing_review_key": row["authorizing_review_key"],
        "status": row["status"],
        "data_boundary": row["data_boundary"],
        "prepared_by_reviewer_key": row["prepared_by_reviewer_key"],
        "prepared_by_reviewer_role": row["prepared_by_reviewer_role"],
        "basis_sha256": row["basis_sha256"],
        "created_at": row["created_at"],
    }
    reviewer = FICTIONAL_STAFF_REVIEWERS.get(row["prepared_by_reviewer_key"])
    if (
        any(result.get(key) != value for key, value in checks.items())
        or int(row["fictional_only"]) != 1
        or result.get("fictional_only") is not True
        or result.get("fictional_acceptance_simulation") is not True
        or result.get("basis_sha256") != content_sha256(result.get("basis", {}))
        or reviewer is None
        or reviewer["reviewer_role"] != row["prepared_by_reviewer_role"]
        or result.get("prepared_by_reviewer_fixture_sha256") != content_sha256(reviewer)
        or result.get("contact_information_included") is not False
        or any(result.get(flag) is not False for flag in (
            "establishes_scope", "authorizes_package", "authorizes_price",
            "creates_charge", "creates_contract", "creates_membership",
            "creates_protected_member", "creates_disclosure",
            "authorizes_customer_release", "authorizes_onboarding",
        ))
    ):
        raise PolicyIntegrityError("fictional scoping handoff boundary failed")
    serialized = canonical_json(result).casefold()
    if "@example.com" in serialized or "contact_email" in serialized or "contact_name" in serialized:
        raise PolicyIntegrityError("fictional scoping handoff contains contact information")
    assert_safe_public_projection(result["public_price_ranges"])
    return {**result, "content_sha256": row["content_sha256"]}


def prepare_fictional_scoping_handoff(
    conn: Any,
    prospect_key: str,
    command: FictionalScopingHandoffCommand,
    *,
    prepared_at: str,
) -> dict[str, Any]:
    """Prepare a source-grounded fictional scope draft without commercial authority."""

    initialize_policy_store(conn)
    at = _parse_utc(prepared_at)
    prospect = load_fictional_prospect(conn, prospect_key)
    consent = load_fictional_consent(conn, prospect["consent_key"])
    current_review = load_current_fictional_staff_review(conn, prospect_key)
    if (
        current_review["review_key"] != command.authorizing_review_key
        or current_review["decision"] != "Proceed to Fictional Scoping"
    ):
        raise PolicyIntegrityError(
            "current fictional review does not authorize scope-draft preparation"
        )
    if _parse_utc(prospect["expires_at"]) <= at or _parse_utc(consent["expires_at"]) <= at:
        raise PolicyIntegrityError("fictional prospect consent has expired")
    reviewer = FICTIONAL_STAFF_REVIEWERS.get(command.prepared_by_reviewer_key)
    if (
        reviewer is None
        or reviewer["fictional_only"] is not True
        or reviewer["reviewer_role"] != command.prepared_by_reviewer_role
    ):
        raise PolicyIntegrityError("fictional scope-draft preparer is not authorized")
    if conn.execute(
        "SELECT handoff_key FROM advisor_fictional_scoping_handoffs "
        "WHERE authorizing_review_key=?",
        (command.authorizing_review_key,),
    ).fetchone():
        raise PolicyIntegrityError("fictional review already has a scoping handoff")

    evaluation = load_session_fictional_evaluation(conn, prospect["evaluation_key"])
    recommendation = prospect["recommendation"]
    if recommendation["evaluation_key"] != evaluation["evaluation_key"]:
        raise PolicyIntegrityError("fictional recommendation reference failed")
    assert_safe_public_projection(recommendation["price_ranges"])
    basis = {
        "prospect_key": prospect_key,
        "prospect_snapshot_sha256": prospect["content_sha256"],
        "consent_key": consent["consent_key"],
        "consent_snapshot_sha256": consent["content_sha256"],
        "evaluation_key": evaluation["evaluation_key"],
        "evaluation_snapshot_sha256": evaluation["content_sha256"],
        "authorizing_review_key": current_review["review_key"],
        "authorizing_review_snapshot_sha256": current_review["content_sha256"],
        "policy_bundle_sha256": evaluation["policy_bundle_sha256"],
        "governing_versions": evaluation["governing_versions"],
        "commercial_estimate_snapshot_sha256": (
            evaluation["commercial_estimate_snapshot_sha256"]
        ),
    }
    basis_sha256 = content_sha256(basis)
    at_text = _utc_text(at)
    seed = {
        "prospect_key": prospect_key,
        "authorizing_review_key": current_review["review_key"],
        "status": SCOPING_HANDOFF_STATUS,
        "scope_state": "Proposed — Not Authorized",
        "data_boundary": DATA_BOUNDARY,
        "fictional_only": True,
        "fictional_acceptance_simulation": True,
        "preparation_purpose": command.preparation_purpose,
        "prepared_by_reviewer_key": command.prepared_by_reviewer_key,
        "prepared_by_reviewer_role": command.prepared_by_reviewer_role,
        "prepared_by_reviewer_fixture_sha256": content_sha256(reviewer),
        "basis": basis,
        "basis_sha256": basis_sha256,
        "organization_profile": recommendation["organization_profile"],
        "proposed_package": recommendation["primary_package"],
        "recommended_investigation_depth": (
            recommendation["recommended_investigation_depth"]
        ),
        "public_price_ranges": recommendation["price_ranges"],
        "implementation_period": recommendation["price_ranges"]["implementation_period"],
        "recommendation_assumptions": recommendation["assumptions"],
        "recommendation_contradictions": recommendation["contradictions"],
        "recommendation_information_gaps": recommendation["information_gaps"],
        "preparer_assumptions": list(command.assumptions),
        "preparer_exclusions": list(command.exclusions),
        "validation_questions": list(command.validation_questions),
        "required_separate_approvals": [
            "Final scope",
            "Final package",
            "Final price",
            "Customer release or commitment",
            "Protected Member onboarding",
        ],
        "contact_information_included": False,
        "created_at": at_text,
        "created_display": _display_utc(at),
        "what_happens_next": (
            "Qualified Salus personnel review and revise this fictional scope draft. "
            "No customer-facing release or commitment occurs without separate authority."
        ),
        "establishes_scope": False,
        "authorizes_package": False,
        "authorizes_price": False,
        "creates_charge": False,
        "creates_contract": False,
        "creates_membership": False,
        "creates_protected_member": False,
        "creates_disclosure": False,
        "authorizes_customer_release": False,
        "authorizes_onboarding": False,
    }
    handoff_key = "SPA-HANDOFF-" + content_sha256(seed).upper()
    handoff = {"handoff_key": handoff_key, **seed}
    snapshot_json = canonical_json(handoff)
    digest = content_sha256(snapshot_json)
    try:
        conn.execute(
            "INSERT INTO advisor_fictional_scoping_handoffs(handoff_key,prospect_key,authorizing_review_key,status,data_boundary,fictional_only,prepared_by_reviewer_key,prepared_by_reviewer_role,basis_sha256,snapshot_json,content_sha256,created_at) VALUES(?,?,?,?,?,?,?,?,?,?,?,?)",
            (
                handoff_key, prospect_key, current_review["review_key"],
                SCOPING_HANDOFF_STATUS, DATA_BOUNDARY, 1,
                command.prepared_by_reviewer_key, command.prepared_by_reviewer_role,
                basis_sha256, snapshot_json, digest, at_text,
            ),
        )
        _record_session_event(
            conn,
            prospect["session_key"],
            "Fictional Scoping Handoff Prepared",
            at_text,
            {
                "prospect_key": prospect_key,
                "handoff_key": handoff_key,
                "authorizing_review_key": current_review["review_key"],
                "status": SCOPING_HANDOFF_STATUS,
                "fictional_acceptance_simulation": True,
            },
        )
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    return {**handoff, "content_sha256": digest}


def load_fictional_internal_review_packet(
    conn: Any, packet_key: str
) -> dict[str, Any]:
    """Load and verify one immutable, content-safe internal review packet."""

    row = conn.execute(
        "SELECT * FROM advisor_fictional_internal_review_packets WHERE packet_key=?",
        (packet_key,),
    ).fetchone()
    if not row or content_sha256(row["snapshot_json"]) != row["content_sha256"]:
        raise PolicyIntegrityError("fictional internal review packet integrity check failed")
    result = json.loads(row["snapshot_json"])
    checks = {
        "packet_key": row["packet_key"],
        "packet_version": row["packet_version"],
        "handoff_key": row["handoff_key"],
        "prospect_key": row["prospect_key"],
        "status": row["status"],
        "data_boundary": row["data_boundary"],
        "prepared_by_reviewer_key": row["prepared_by_reviewer_key"],
        "prepared_by_reviewer_role": row["prepared_by_reviewer_role"],
        "evidence_sha256": row["evidence_sha256"],
        "created_at": row["created_at"],
    }
    reviewer = FICTIONAL_STAFF_REVIEWERS.get(row["prepared_by_reviewer_key"])
    handoff = load_fictional_scoping_handoff(conn, row["handoff_key"])
    if (
        any(result.get(key) != value for key, value in checks.items())
        or row["packet_version"] != INTERNAL_REVIEW_PACKET_VERSION
        or row["status"] != INTERNAL_REVIEW_PACKET_STATUS
        or int(row["fictional_only"]) != 1
        or result.get("fictional_only") is not True
        or result.get("fictional_acceptance_simulation") is not True
        or result.get("human_review_completed") is not False
        or result.get("contact_information_included") is not False
        or tuple(result.get("requested_review_topics", [])) != INTERNAL_REVIEW_TOPICS
        or result.get("evidence_sha256") != content_sha256(result.get("evidence", {}))
        or reviewer is None
        or reviewer["reviewer_role"] != row["prepared_by_reviewer_role"]
        or result.get("prepared_by_reviewer_fixture_sha256") != content_sha256(reviewer)
        or result["evidence"].get("handoff_snapshot_sha256") != handoff["content_sha256"]
        or any(result.get(flag) is not False for flag in (
            "approves_prototype", "authorizes_public_route", "authorizes_dns",
            "authorizes_pilot", "establishes_scope", "authorizes_package",
            "authorizes_price", "creates_charge", "creates_contract",
            "creates_membership", "creates_protected_member", "creates_disclosure",
            "authorizes_customer_release", "authorizes_onboarding",
        ))
    ):
        raise PolicyIntegrityError("fictional internal review packet boundary failed")
    serialized = canonical_json(result).casefold()
    for forbidden in (
        "@example.com", "contact_email", "contact_name", "session_token",
        "internal_cost", "role_rate", "margin_basis_points", "tenant_id",
        "protected_member_id", "approved_customer_price_cents",
    ):
        if forbidden in serialized:
            raise PolicyIntegrityError("fictional internal review packet contains restricted data")
    assert_safe_public_projection(result["evidence"]["public_price_ranges"])
    return {**result, "content_sha256": row["content_sha256"]}


def prepare_fictional_internal_review_packet(
    conn: Any,
    command: FictionalInternalReviewPacketCommand,
    *,
    prepared_at: str,
) -> dict[str, Any]:
    """Prepare evidence for human review without claiming that review occurred."""

    initialize_policy_store(conn)
    at = _parse_utc(prepared_at)
    handoff = load_fictional_scoping_handoff(conn, command.handoff_key)
    prospect = load_fictional_prospect(conn, handoff["prospect_key"])
    consent = load_fictional_consent(conn, prospect["consent_key"])
    current_review = load_current_fictional_staff_review(conn, prospect["prospect_key"])
    if (
        current_review["review_key"] != handoff["authorizing_review_key"]
        or current_review["decision"] != "Proceed to Fictional Scoping"
    ):
        raise PolicyIntegrityError("internal review packet requires the current scoping handoff")
    if _parse_utc(prospect["expires_at"]) <= at or _parse_utc(consent["expires_at"]) <= at:
        raise PolicyIntegrityError("fictional prospect consent has expired")
    reviewer = FICTIONAL_STAFF_REVIEWERS.get(command.prepared_by_reviewer_key)
    if (
        reviewer is None
        or reviewer["fictional_only"] is not True
        or reviewer["reviewer_role"] != command.prepared_by_reviewer_role
    ):
        raise PolicyIntegrityError("fictional review packet preparer is not authorized")
    if conn.execute(
        "SELECT packet_key FROM advisor_fictional_internal_review_packets WHERE handoff_key=?",
        (command.handoff_key,),
    ).fetchone():
        raise PolicyIntegrityError("fictional scoping handoff already has a review packet")

    review_history = fictional_staff_review_history(conn, prospect["prospect_key"])
    evidence = {
        "handoff_key": handoff["handoff_key"],
        "handoff_snapshot_sha256": handoff["content_sha256"],
        "prospect_key": prospect["prospect_key"],
        "prospect_snapshot_sha256": prospect["content_sha256"],
        "consent_key": consent["consent_key"],
        "consent_snapshot_sha256": consent["content_sha256"],
        "evaluation_key": handoff["basis"]["evaluation_key"],
        "evaluation_snapshot_sha256": handoff["basis"]["evaluation_snapshot_sha256"],
        "policy_bundle_sha256": handoff["basis"]["policy_bundle_sha256"],
        "governing_versions": handoff["basis"]["governing_versions"],
        "commercial_estimate_snapshot_sha256": (
            handoff["basis"]["commercial_estimate_snapshot_sha256"]
        ),
        "authorizing_review_key": current_review["review_key"],
        "authorizing_review_snapshot_sha256": current_review["content_sha256"],
        "review_history": [
            {
                "review_key": review["review_key"],
                "review_sequence": review["review_sequence"],
                "decision": review["decision"],
                "status": review["status"],
                "content_sha256": review["content_sha256"],
            }
            for review in review_history
        ],
        "organization_profile": handoff["organization_profile"],
        "proposed_package": handoff["proposed_package"],
        "recommended_investigation_depth": handoff["recommended_investigation_depth"],
        "public_price_ranges": handoff["public_price_ranges"],
        "recommendation_assumptions": handoff["recommendation_assumptions"],
        "recommendation_contradictions": handoff["recommendation_contradictions"],
        "recommendation_information_gaps": handoff["recommendation_information_gaps"],
        "scoping_assumptions": handoff["preparer_assumptions"],
        "scoping_exclusions": handoff["preparer_exclusions"],
        "validation_questions": handoff["validation_questions"],
        "fictional_case_coverage": [
            {
                "case_key": case.case_key,
                "display_name": case.display_name,
                "acceptance_focus": list(case.acceptance_focus),
                "case_fixture_sha256": content_sha256(case.model_dump(mode="json")),
            }
            for case in FICTIONAL_CASES
        ],
    }
    evidence_sha256 = content_sha256(evidence)
    topic_evidence = [
        {
            "topic": topic,
            "state": (
                "Evidence Needed"
                if topic in INTERNAL_REVIEW_TOPICS[-2:]
                else "Evidence Prepared — Human Review Required"
            ),
        }
        for topic in INTERNAL_REVIEW_TOPICS
    ]
    at_text = _utc_text(at)
    seed = {
        "packet_version": INTERNAL_REVIEW_PACKET_VERSION,
        "handoff_key": handoff["handoff_key"],
        "prospect_key": prospect["prospect_key"],
        "status": INTERNAL_REVIEW_PACKET_STATUS,
        "data_boundary": DATA_BOUNDARY,
        "fictional_only": True,
        "fictional_acceptance_simulation": True,
        "prepared_by_reviewer_key": command.prepared_by_reviewer_key,
        "prepared_by_reviewer_role": command.prepared_by_reviewer_role,
        "prepared_by_reviewer_fixture_sha256": content_sha256(reviewer),
        "requested_review_topics": list(command.requested_review_topics),
        "topic_evidence": topic_evidence,
        "evidence": evidence,
        "evidence_sha256": evidence_sha256,
        "open_decisions": [
            "Qualified Salus personnel must review and may accept, reject, or request changes.",
            "Question wording, evaluation basis, recommendation fit, package details, and public price ranges remain subject to Salus judgment.",
            "Accessibility, responsive presentation, privacy, security, abuse resistance, recovery, and rollback require separate validation.",
            "No public route, DNS change, pilot, customer release, or Protected Member onboarding is authorized.",
            "The Salus Protection Advisor name remains provisional pending trademark clearance.",
        ],
        "human_review_completed": False,
        "contact_information_included": False,
        "created_at": at_text,
        "created_display": _display_utc(at),
        "what_happens_next": (
            "Qualified Salus personnel review this evidence, record questions or changes, "
            "and separately decide whether the internal prototype is ready for further validation."
        ),
        "approves_prototype": False,
        "authorizes_public_route": False,
        "authorizes_dns": False,
        "authorizes_pilot": False,
        "establishes_scope": False,
        "authorizes_package": False,
        "authorizes_price": False,
        "creates_charge": False,
        "creates_contract": False,
        "creates_membership": False,
        "creates_protected_member": False,
        "creates_disclosure": False,
        "authorizes_customer_release": False,
        "authorizes_onboarding": False,
    }
    packet_key = "SPA-REVIEW-PACKET-" + content_sha256(seed).upper()
    packet = {"packet_key": packet_key, **seed}
    snapshot_json = canonical_json(packet)
    digest = content_sha256(snapshot_json)
    try:
        conn.execute(
            "INSERT INTO advisor_fictional_internal_review_packets(packet_key,packet_version,handoff_key,prospect_key,status,data_boundary,fictional_only,prepared_by_reviewer_key,prepared_by_reviewer_role,evidence_sha256,snapshot_json,content_sha256,created_at) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (
                packet_key, INTERNAL_REVIEW_PACKET_VERSION, handoff["handoff_key"],
                prospect["prospect_key"], INTERNAL_REVIEW_PACKET_STATUS,
                DATA_BOUNDARY, 1, command.prepared_by_reviewer_key,
                command.prepared_by_reviewer_role, evidence_sha256,
                snapshot_json, digest, at_text,
            ),
        )
        _record_session_event(
            conn,
            prospect["session_key"],
            "Fictional Internal Review Packet Prepared",
            at_text,
            {
                "prospect_key": prospect["prospect_key"],
                "handoff_key": handoff["handoff_key"],
                "packet_key": packet_key,
                "status": INTERNAL_REVIEW_PACKET_STATUS,
                "human_review_completed": False,
                "fictional_acceptance_simulation": True,
            },
        )
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    return {**packet, "content_sha256": digest}


def _require_fictional_internal_review_interface(
    server_settings: Mapping[str, str] | None,
) -> dict[str, str]:
    """Fail closed unless the internal fictional-review boundary is explicitly enabled."""

    settings = dict(os.environ if server_settings is None else server_settings)
    environment = str(settings.get("SALUS_ENV", "")).strip().lower()
    auth_mode = str(settings.get("SALUS_AUTH_MODE", "")).strip().lower()
    interface_state = str(settings.get(INTERNAL_REVIEW_INTERFACE_FLAG, "")).strip()
    if (
        environment not in {"development", "test"}
        or auth_mode not in {"prototype", "session", "oidc"}
        or interface_state != INTERNAL_REVIEW_INTERFACE_STATE
    ):
        raise SessionAccessError("fictional internal review interface is unavailable")
    return {
        "environment": environment,
        "auth_mode": auth_mode,
        "interface_state": interface_state,
    }


def open_fictional_internal_review_interface(
    conn: Any,
    packet_key: str,
    context: FictionalInternalReviewInterfaceContext,
    *,
    viewed_at: str,
    server_settings: Mapping[str, str] | None = None,
) -> dict[str, Any]:
    """Open a read-only internal view without claiming review or approval."""

    gate = _require_fictional_internal_review_interface(server_settings)
    at = _parse_utc(viewed_at)
    packet = load_fictional_internal_review_packet(conn, packet_key)
    reviewer = FICTIONAL_STAFF_REVIEWERS.get(context.reviewer_key)
    if (
        reviewer is None
        or reviewer["fictional_only"] is not True
        or reviewer["reviewer_role"] != context.reviewer_role
    ):
        raise SessionAccessError("fictional internal review viewer is not authorized")

    prospect = load_fictional_prospect(conn, packet["prospect_key"])
    current_review = load_current_fictional_staff_review(conn, prospect["prospect_key"])
    basis_is_current = (
        current_review["review_key"]
        == packet["evidence"]["authorizing_review_key"]
    )
    lifecycle_state = (
        "Current Fictional Review Evidence"
        if basis_is_current
        else "Superseded — Historical Fictional Evidence"
    )
    interface = {
        "interface_version": INTERNAL_REVIEW_INTERFACE_VERSION,
        "page_title": "Salus Protection Advisor™",
        "navigation_label": "Service Recommendation & Pricing",
        "page_purpose": "Internal Fictional Review",
        "visibility": "Internal Salus Review Only — No Public Route",
        "left_margin_release_version": "Internal prototype — not deployed",
        "salus_workflow": ["See", "Decide", "Coordinate", "Act", "Prove"],
        "status": packet["status"],
        "lifecycle_state": lifecycle_state,
        "data_boundary": packet["data_boundary"],
        "fictional_only": True,
        "fictional_acceptance_simulation": True,
        "packet_key": packet["packet_key"],
        "packet_content_sha256": packet["content_sha256"],
        "viewer_key": context.reviewer_key,
        "viewer_role": context.reviewer_role,
        "access_purpose": context.access_purpose,
        "viewed_at": _utc_text(at),
        "viewed_display": _display_utc(at),
        "guidance": (
            "Review the evidence, uncertainty, assumptions, and unresolved validation "
            "needs. Salus personnel retain judgment and decide what happens next."
        ),
        "review_topics": packet["topic_evidence"],
        "evidence_summary": {
            "fictional_case_coverage": packet["evidence"]["fictional_case_coverage"],
            "organization_profile": packet["evidence"]["organization_profile"],
            "proposed_package": packet["evidence"]["proposed_package"],
            "recommended_investigation_depth": (
                packet["evidence"]["recommended_investigation_depth"]
            ),
            "public_price_ranges": packet["evidence"]["public_price_ranges"],
            "recommendation_assumptions": (
                packet["evidence"]["recommendation_assumptions"]
            ),
            "recommendation_contradictions": (
                packet["evidence"]["recommendation_contradictions"]
            ),
            "recommendation_information_gaps": (
                packet["evidence"]["recommendation_information_gaps"]
            ),
            "scoping_assumptions": packet["evidence"]["scoping_assumptions"],
            "scoping_exclusions": packet["evidence"]["scoping_exclusions"],
            "validation_questions": packet["evidence"]["validation_questions"],
        },
        "source_lineage": {
            key: packet["evidence"][key]
            for key in (
                "handoff_key", "handoff_snapshot_sha256", "prospect_key",
                "prospect_snapshot_sha256", "consent_key",
                "consent_snapshot_sha256", "evaluation_key",
                "evaluation_snapshot_sha256", "policy_bundle_sha256",
                "governing_versions", "commercial_estimate_snapshot_sha256",
                "authorizing_review_key",
                "authorizing_review_snapshot_sha256", "review_history",
            )
        },
        "open_decisions": packet["open_decisions"],
        "what_happens_next": packet["what_happens_next"],
        "human_authority": (
            "Qualified Salus personnel may accept, reject, request changes, pause, or "
            "end this work through a separately governed decision record."
        ),
        "available_controls": {
            "inspect_evidence": True,
            "compare_source_lineage": True,
            "prepare_review_notes": True,
            "record_human_review": False,
            "approve_prototype": False,
            "authorize_public_release": False,
        },
        "accessibility_contract": {
            "reading_order": [
                "Identity and purpose", "Status and authority", "Review topics",
                "Evidence summary", "Source lineage", "Open decisions", "Next step",
            ],
            "keyboard_operable": True,
            "visible_focus_required": True,
            "color_is_not_the_only_signal": True,
            "supports_text_resize": True,
            "mobile_reflow_required": True,
        },
        "human_review_completed": False,
        "approves_prototype": False,
        "authorizes_public_route": False,
        "authorizes_dns": False,
        "authorizes_pilot": False,
        "creates_protected_member": False,
        "creates_disclosure": False,
        "authorizes_customer_release": False,
        "authorizes_onboarding": False,
    }
    interface_text = canonical_json(interface).casefold()
    for forbidden in (
        "@example.com", "contact_email", "contact_name", "session_token",
        "internal_cost", "role_rate", "margin_basis_points", "tenant_id",
        "protected_member_id", "approved_customer_price_cents",
    ):
        if forbidden in interface_text:
            raise PolicyIntegrityError("fictional internal review interface contains restricted data")
    assert_safe_public_projection(interface["evidence_summary"]["public_price_ranges"])
    view_sha256 = content_sha256(interface)
    _record_session_event(
        conn,
        prospect["session_key"],
        "Fictional Internal Review Interface Opened",
        interface["viewed_at"],
        {
            "packet_key": packet["packet_key"],
            "view_sha256": view_sha256,
            "viewer_key": context.reviewer_key,
            "lifecycle_state": lifecycle_state,
            "human_review_completed": False,
            "fictional_acceptance_simulation": True,
        },
    )
    conn.commit()
    return {
        **interface,
        "view_sha256": view_sha256,
        "server_gate": {
            "interface_state": gate["interface_state"],
            "environment_class": "Non-production",
            "authentication_boundary": "Server controlled",
        },
    }
