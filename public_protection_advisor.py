"""Public, isolated Salus Protection Advisor pilot.

Issue #290. This module intentionally has no Protected Member tenant relationship.
It persists only consented prospect assessment records and preserves versioned,
append-only answer lineage. Recommendations are preliminary and non-binding.
"""
from __future__ import annotations

import hashlib
import hmac
import html
import json
import os
import secrets

import httpx
from azure.identity import ManagedIdentityCredential
from datetime import datetime, timedelta, timezone
from typing import Any

from fastapi import HTTPException, Request
from fastapi.responses import HTMLResponse, JSONResponse
from pydantic import BaseModel, ConfigDict, Field, field_validator

QUESTIONNAIRE_VERSION = "SPA-PUBLIC-QUESTIONNAIRE-2.0.0"
RECOMMENDATION_VERSION = "SPA-PUBLIC-RECOMMENDATION-2.0.0"
CONSENT_NOTICE_VERSION = "SPA-PUBLIC-CONSENT-1.0.0"
RETENTION_POLICY_VERSION = "SPA-SPLIT-RETENTION-1.0.0"
PACKAGE_PROFILE_VERSION = "SPA-SERVICE-PROFILE-2.0.0"
PACKAGE_RECOMMENDATION_VERSION = "SPA-PACKAGE-RECOMMENDATION-2.0.0"
SESSION_HOURS = 24
NOTIFICATION_MODE = os.getenv("SALUS_ADVISOR_NOTIFICATION_MODE", "outbox").strip().lower()
NOTIFICATION_TO = os.getenv("SALUS_ADVISOR_NOTIFICATION_TO", "mduncan@salus.solutions").strip().lower()
NOTIFICATION_FROM = os.getenv("SALUS_ADVISOR_NOTIFICATION_FROM", "protectionadvisor@salus.solutions").strip().lower()
REQUIRE_EMAIL_VERIFICATION = os.getenv("SALUS_ADVISOR_REQUIRE_EMAIL_VERIFICATION", "0").strip() == "1"
ANSWER_STATES = {"Validated", "Documented", "Partially", "No", "Unknown", "Not Applicable", "Declined", "Answered"}
ORGANIZATION_TYPES = {
    "Business", "Faith-Based Organization", "School or Educational Institution",
    "Nonprofit or Community Organization", "Healthcare or Human Services",
    "Government or Public Institution", "Property or Facility Operator",
    "Event Venue or Hospitality", "Other",
}

CORE_CAPABILITIES = {
    "Planning": ("Prevention", "Protection", "Mitigation", "Response", "Recovery"),
    "Public Information and Warning": ("Prevention", "Protection", "Mitigation", "Response", "Recovery"),
    "Operational Coordination": ("Prevention", "Protection", "Mitigation", "Response", "Recovery"),
    "Forensics and Attribution": ("Prevention",),
    "Intelligence and Information Sharing": ("Prevention", "Protection"),
    "Interdiction and Disruption": ("Prevention", "Protection"),
    "Screening, Search, and Detection": ("Prevention", "Protection"),
    "Access Control and Identity Verification": ("Protection",),
    "Cybersecurity": ("Protection",),
    "Physical Protective Measures": ("Protection",),
    "Risk Management for Protection Programs and Activities": ("Protection",),
    "Supply Chain Integrity and Security": ("Protection",),
    "Community Resilience": ("Mitigation",),
    "Long-term Vulnerability Reduction": ("Mitigation",),
    "Risk and Disaster Resilience Assessment": ("Mitigation",),
    "Threats and Hazards Identification": ("Mitigation",),
    "Critical Transportation": ("Response",),
    "Environmental Response/Health and Safety": ("Response",),
    "Fatality Management Services": ("Response",),
    "Fire Management and Suppression": ("Response",),
    "Infrastructure Systems": ("Response", "Recovery"),
    "Logistics and Supply Chain Management": ("Response",),
    "Mass Care Services": ("Response",),
    "Mass Search and Rescue Operations": ("Response",),
    "On-scene Security, Protection, and Law Enforcement": ("Response",),
    "Operational Communications": ("Response",),
    "Public Health, Healthcare, and Emergency Medical Services": ("Response",),
    "Situational Assessment": ("Response",),
    "Economic Recovery": ("Recovery",),
    "Health and Social Services": ("Recovery",),
    "Housing": ("Recovery",),
    "Natural and Cultural Resources": ("Recovery",),
}

SERVICE_CATALOG = (
    ("salthira", "Salus THIRA Assessment", "Identify credible threats and hazards, consequences, capability targets, current capability, gaps, priorities, and defensible improvements."),
    ("facility", "Facility and Physical Security Assessment", "Examine facilities, operations, people, physical and cyber-physical dependencies, surrounding conditions, intentional threats, continuity, and recovery."),
    ("protective_intelligence", "Protective Intelligence and Threat Monitoring", "Establish intelligence requirements, reporting, warning indicators, threat assessment, escalation, monitoring, and decision support."),
    ("planning", "Emergency Planning and Crisis Communications", "Develop usable emergency, notification, accountability, coordination, leadership, and crisis-communications arrangements."),
    ("continuity", "Business Continuity and Recovery", "Define essential functions, dependencies, minimum operations, recovery targets, alternate resources, and restoration priorities."),
    ("cyber_physical", "Cyber-Physical Resilience", "Review the relationship among information systems, operational technology, facilities, security systems, vendors, and continuity requirements."),
    ("training", "Training, Exercises, and Capability Validation", "Prepare personnel, exercise integrated plans and systems, document performance, and turn lessons into governed improvement."),
    ("protection", "Protection and Security Operations", "Design or strengthen protective staffing, procedures, access, incident support, executive protection, and operational coordination."),
    ("incident_support", "Incident, Crisis, and Recovery Support", "Provide planning, coordination, specialist, communications, logistics, response, recovery, and sustainment support when conditions require action."),
    ("implementation", "Implementation and Technical Assistance", "Help leadership assign, sequence, budget, implement, document, and validate approved improvements."),
    ("monitoring", "Ongoing Monitoring and SalCAPA Support", "Maintain awareness, records, responsibilities, reassessment, notifications, and continuing improvement through SalCAPA."),
)

# key, plain-language question, domain, FEMA core capabilities, Salus services, consequence weight
QUESTION_BLUEPRINTS = (
    ("risk_list", "Do you maintain a current list of threats and hazards that could affect your organization?", "risk", ("Threats and Hazards Identification", "Risk and Disaster Resilience Assessment"), ("salthira", "protective_intelligence"), 1.4),
    ("capability_targets", "For priority scenarios, has your organization defined measurable capability targets across prevention, protection, mitigation, response, recovery, and continuity—including who must act, under what conditions, within what time, and to what standard?", "capability", ("Planning", "Risk Management for Protection Programs and Activities"), ("salthira", "planning"), 1.5),
    ("consequence", "Have you assessed how serious the consequences could be for your most credible scenarios?", "risk", ("Risk and Disaster Resilience Assessment", "Community Resilience", "Long-term Vulnerability Reduction"), ("salthira",), 1.5),
    ("vulnerable_people", "Have capability requirements been adjusted for children, older adults, people with disabilities or access and functional needs, people in crisis, and others who may need additional assistance?", "capability", ("Mass Care Services", "Public Health, Healthcare, and Emergency Medical Services", "Health and Social Services", "Housing"), ("planning", "continuity"), 1.4),
    ("reporting", "Are concerns and incident reports collected in one governed place for appropriate review?", "risk", ("Intelligence and Information Sharing", "Forensics and Attribution"), ("protective_intelligence", "monitoring"), 1.2),
    ("warning_thresholds", "Are warning indicators, escalation thresholds, and reporting paths defined so emerging concerns are distinguished from assumptions, combined with related information, and acted on while choices remain?", "intelligence", ("Intelligence and Information Sharing", "Situational Assessment", "Public Information and Warning"), ("protective_intelligence", "planning", "monitoring"), 1.5),
    ("required_actions", "Do personnel understand what they may need to do during likely emergencies or disruptions?", "capability", ("Operational Coordination", "Interdiction and Disruption", "On-scene Security, Protection, and Law Enforcement"), ("planning", "training", "protection"), 1.3),
    ("decision_authority", "If normal leaders are unavailable, are decision authority, succession, delegation limits, and alternate coordination responsibilities documented and understood?", "governance", ("Planning", "Operational Coordination"), ("planning", "implementation"), 1.5),
    ("current_capability", "Has your organization compared what it can reliably do today with what it may need to do?", "capability", ("Risk Management for Protection Programs and Activities", "Long-term Vulnerability Reduction"), ("salthira", "implementation"), 1.3),
    ("dependency_map", "Have essential functions been traced to their critical people, facilities, technology, utilities, suppliers, partners, and transportation dependencies—including shared points of failure?", "continuity", ("Infrastructure Systems", "Critical Transportation", "Supply Chain Integrity and Security", "Cybersecurity"), ("continuity", "cyber_physical", "facility"), 1.6),
    ("integrated_test", "Have plans, communications, facilities, systems, and personnel been tested together?", "evidence", ("Planning", "Operational Coordination", "Operational Communications"), ("training", "planning"), 1.5),
    ("degraded_communications", "Can the organization communicate decisions and protective instructions with personnel, responders, partners, and affected people if internet, cellular service, power, or primary systems fail?", "response", ("Operational Communications", "Public Information and Warning"), ("planning", "cyber_physical", "continuity"), 1.6),
    ("priority_gaps", "Can leadership identify the most important protection or readiness gaps in priority order?", "gap", ("Risk Management for Protection Programs and Activities", "Long-term Vulnerability Reduction"), ("salthira", "implementation"), 1.2),
    ("resource_competition", "Has the organization tested whether critical personnel, responders, vendors, fuel, medical support, equipment, communications, and alternate facilities would remain available during a regional or simultaneous emergency?", "continuity", ("Logistics and Supply Chain Management", "Mass Search and Rescue Operations", "Fatality Management Services", "Environmental Response/Health and Safety"), ("continuity", "planning", "training"), 1.6),
    ("ownership", "Does a specific authorized person own each priority gap, with a plan and review date?", "governance", ("Planning", "Operational Coordination"), ("implementation", "monitoring"), 1.2),
    ("validation_evidence", "Is there recent evidence—not only a written plan—that each critical capability can meet its target under realistic stress, reduced staffing, and degraded conditions?", "evidence", ("Screening, Search, and Detection", "Physical Protective Measures", "Risk Management for Protection Programs and Activities"), ("training", "protection", "facility"), 1.5),
    ("training_test", "Have trained personnel demonstrated that they can perform their assigned actions?", "evidence", ("Operational Coordination", "Fire Management and Suppression", "Public Health, Healthcare, and Emergency Medical Services"), ("training", "planning"), 1.4),
    ("recovery_targets", "Are recovery-time and service-restoration targets defined for every essential function, including minimum acceptable operations, alternate resources, and restoration priority?", "recovery", ("Economic Recovery", "Infrastructure Systems", "Housing"), ("continuity",), 1.6),
    ("leadership_record", "Could leadership explain what was known, what was decided, and what action was underway?", "governance", ("Situational Assessment", "Forensics and Attribution", "Public Information and Warning"), ("protective_intelligence", "planning", "monitoring"), 1.2),
    ("investment_tradeoffs", "When choosing improvements, does leadership compare consequence reduction, cost, feasibility, dependencies, implementation time, and time to protective benefit?", "governance", ("Long-term Vulnerability Reduction", "Community Resilience"), ("implementation", "salthira"), 1.2),
    ("continuity", "Can essential operations continue if facilities, utilities, technology, suppliers, or personnel are disrupted?", "continuity", ("Cybersecurity", "Supply Chain Integrity and Security", "Critical Transportation", "Infrastructure Systems"), ("continuity", "cyber_physical"), 1.7),
    ("recovery", "Are recovery priorities, alternate resources, and restoration responsibilities documented?", "recovery", ("Economic Recovery", "Health and Social Services", "Housing", "Natural and Cultural Resources"), ("continuity", "planning"), 1.5),
    ("protective_controls", "Are access controls, identity verification, physical safeguards, security staffing, and suspicious-activity procedures appropriate for the people, property, and operations being protected?", "protection", ("Access Control and Identity Verification", "Physical Protective Measures", "On-scene Security, Protection, and Law Enforcement"), ("facility", "protection"), 1.6),
    ("cyber_resilience", "Can essential operations continue safely if information systems, operational technology, security systems, cloud services, or communications are compromised or unavailable?", "protection", ("Cybersecurity", "Infrastructure Systems"), ("cyber_physical", "continuity"), 1.7),
    ("life_safety_response", "Are fire, medical, rescue, evacuation, shelter, accountability, and responder-coordination arrangements adequate for your likely conditions and affected population?", "response", ("Fire Management and Suppression", "Mass Search and Rescue Operations", "Public Health, Healthcare, and Emergency Medical Services", "Mass Care Services"), ("planning", "training", "facility"), 1.7),
    ("environmental_hazards", "Can the organization recognize, isolate, report, and coordinate safely around hazardous releases, contaminated areas, unsafe conditions, or environmental consequences?", "response", ("Environmental Response/Health and Safety", "Natural and Cultural Resources"), ("facility", "planning", "incident_support"), 1.5),
    ("supplier_integrity", "Are critical suppliers, contractors, products, transportation routes, and replacement resources evaluated for integrity, availability, concentration, and disruption risk?", "protection", ("Supply Chain Integrity and Security", "Logistics and Supply Chain Management", "Critical Transportation"), ("continuity", "protective_intelligence"), 1.5),
    ("community_recovery", "Do recovery plans address employees and families, customers or members, health and social needs, temporary operations, economic effects, housing or relocation, and community consequences?", "recovery", ("Community Resilience", "Economic Recovery", "Health and Social Services", "Housing"), ("continuity", "planning"), 1.5),
)

ACTIVITY_OPTIONS = {
    "Precious metals or other high-value materials",
    "Hazardous materials, fuels, chemicals, or regulated waste",
    "Manufacturing, industrial processes, or heavy equipment",
    "Healthcare, medical, behavioral-health, or human services",
    "Children, students, older adults, or people needing assistance",
    "Public events, venues, hospitality, or mass gatherings",
    "Critical infrastructure, utilities, transportation, or logistics",
    "Sensitive information, technology, research, or intellectual property",
    "Distributed, mobile, remote, travel, or international operations",
    "Government, public safety, or essential public services",
}

FAITH_QUESTION = ("volunteer_roles", "Where volunteers have protective or emergency responsibilities, are their roles current, understood, and practiced?", "capability", ("Operational Coordination", "Planning"), ("training", "planning"), 1.3)
SCHOOL_QUESTION = ("reunification", "Have student accountability and family reunification procedures been tested with responsible personnel?", "response", ("Mass Care Services", "Operational Coordination", "Public Information and Warning"), ("planning", "training"), 1.5)
PUBLIC_QUESTION = ("public_access", "Are public access, visitor management, and concerning-behavior reporting handled consistently?", "protection", ("Access Control and Identity Verification", "Screening, Search, and Detection", "Intelligence and Information Sharing"), ("facility", "protection", "protective_intelligence"), 1.5)



class StartCommand(BaseModel):
    model_config = ConfigDict(extra="forbid")
    organization_type: str
    primary_consent: bool
    secondary_deidentified_consent: bool = False

    @field_validator("organization_type")
    @classmethod
    def valid_org_type(cls, value: str) -> str:
        value = value.strip()
        if value not in ORGANIZATION_TYPES:
            raise ValueError("unsupported organization type")
        return value


class AnswerCommand(BaseModel):
    model_config = ConfigDict(extra="forbid")
    question_key: str = Field(pattern=r"^[a-z][a-z0-9_]{0,79}$")
    answer_state: str
    note: str = Field(default="", max_length=500)

    @field_validator("answer_state")
    @classmethod
    def valid_state(cls, value: str) -> str:
        if value not in ANSWER_STATES:
            raise ValueError("unsupported answer state")
        return value

    @field_validator("note")
    @classmethod
    def clean_note(cls, value: str) -> str:
        return value.strip()


class AccountCreateCommand(BaseModel):
    model_config = ConfigDict(extra="forbid")
    email: str = Field(min_length=3, max_length=254)
    password: str = Field(min_length=12, max_length=200)
    detailed_assessment_acknowledged: bool
    identifiable_retention_consent: bool

    @field_validator("email")
    @classmethod
    def email_shape(cls, value: str) -> str:
        value = value.strip().casefold()
        if value.count("@") != 1 or "." not in value.rsplit("@", 1)[-1]:
            raise ValueError("enter a valid email address")
        return value


class AccountLoginCommand(BaseModel):
    model_config = ConfigDict(extra="forbid")
    email: str = Field(min_length=3, max_length=254)
    password: str = Field(min_length=12, max_length=200)

    @field_validator("email")
    @classmethod
    def normalize_email(cls, value: str) -> str:
        return value.strip().casefold()


class PasswordResetRequestCommand(BaseModel):
    model_config = ConfigDict(extra="forbid")
    email: str = Field(min_length=3, max_length=254)

    @field_validator("email")
    @classmethod
    def normalize_email(cls, value: str) -> str:
        return value.strip().casefold()


class PasswordResetCommand(BaseModel):
    model_config = ConfigDict(extra="forbid")
    token: str = Field(min_length=32, max_length=200)
    new_password: str = Field(min_length=12, max_length=200)


class DraftCommand(BaseModel):
    model_config = ConfigDict(extra="forbid")
    fields: dict[str, Any]

    @field_validator("fields")
    @classmethod
    def valid_fields(cls, value: dict[str, Any]) -> dict[str, Any]:
        allowed = {
            "organization_name", "contact_name", "contact_email", "facility_scope",
            "facility_locations", "personnel_range", "affected_population_range",
            "annual_revenue_range", "specific_activities", "essential_functions",
            "maximum_tolerable_downtime", "existing_program_maturity",
            "internal_implementation_capacity", "primary_objective",
            "external_requirements", "recent_concerns", "desired_timing",
            "decision_authority", "investment_range",
        }
        if set(value) - allowed:
            raise ValueError("unsupported draft field")
        if len(_json(value)) > 20000:
            raise ValueError("draft is too large")
        return value


class SubmitCommand(BaseModel):
    model_config = ConfigDict(extra="forbid")
    organization_name: str = Field(min_length=1, max_length=160)
    contact_name: str = Field(min_length=1, max_length=160)
    contact_email: str = Field(min_length=3, max_length=254)
    detailed_assessment_acknowledged: bool
    identifiable_retention_consent: bool
    facility_scope: str = Field(min_length=1, max_length=80)
    facility_locations: str = Field(default="", max_length=1500)
    personnel_range: str = Field(min_length=1, max_length=80)
    affected_population_range: str = Field(min_length=1, max_length=80)
    annual_revenue_range: str = Field(min_length=1, max_length=80)
    specific_activities: list[str] = Field(default_factory=list, max_length=10)
    essential_functions: str = Field(default="", max_length=1200)
    maximum_tolerable_downtime: str = Field(min_length=1, max_length=80)
    existing_program_maturity: str = Field(min_length=1, max_length=100)
    internal_implementation_capacity: str = Field(min_length=1, max_length=100)
    primary_objective: str = Field(min_length=1, max_length=120)
    external_requirements: str = Field(min_length=1, max_length=120)
    recent_concerns: str = Field(default="", max_length=1200)
    desired_timing: str = Field(min_length=1, max_length=80)
    decision_authority: str = Field(min_length=1, max_length=160)
    investment_range: str = Field(min_length=1, max_length=80)

    @field_validator(
        "organization_name", "contact_name", "contact_email", "facility_scope",
        "facility_locations", "personnel_range", "affected_population_range",
        "annual_revenue_range", "essential_functions", "maximum_tolerable_downtime",
        "existing_program_maturity", "internal_implementation_capacity",
        "primary_objective", "external_requirements", "recent_concerns",
        "desired_timing", "decision_authority", "investment_range",
    )
    @classmethod
    def clean(cls, value: str) -> str:
        value = value.strip()
        if any(ch in value for ch in "\r\n"):
            raise ValueError("line breaks are not permitted")
        return value

    @field_validator("specific_activities")
    @classmethod
    def valid_activities(cls, value: list[str]) -> list[str]:
        cleaned = list(dict.fromkeys(item.strip() for item in value if item.strip()))
        if any(item not in ACTIVITY_OPTIONS for item in cleaned):
            raise ValueError("unsupported activity")
        return cleaned

    @field_validator("contact_email")
    @classmethod
    def email_shape(cls, value: str) -> str:
        value = value.casefold()
        if value.count("@") != 1 or "." not in value.rsplit("@", 1)[-1]:
            raise ValueError("enter a valid email address")
        return value


def _utc_now() -> datetime:
    return datetime.now(timezone.utc).replace(microsecond=0)


def _utc_text(value: datetime) -> str:
    return value.isoformat().replace("+00:00", "Z")


def _sha(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def _password_hash(password: str, salt_hex: str) -> str:
    return hashlib.scrypt(
        password.encode("utf-8"),
        salt=bytes.fromhex(salt_hex),
        n=2 ** 14,
        r=8,
        p=1,
        dklen=32,
    ).hex()


def _password_matches(password: str, salt_hex: str, expected: str) -> bool:
    return hmac.compare_digest(_password_hash(password, salt_hex), expected)


STATE_NEED = {
    "Validated": 0.0,
    "Answered": 0.0,
    "Documented": 0.7,
    "Partially": 1.8,
    "No": 3.0,
    "Unknown": 0.8,
    "Declined": 0.5,
    "Not Applicable": 0.0,
}


def _question_row(row: tuple[Any, ...]) -> dict[str, Any]:
    key, text, domain, capabilities, services, weight = row
    return {
        "key": key,
        "text": text,
        "domain": domain,
        "capabilities": list(capabilities),
        "mission_areas": sorted({area for capability in capabilities for area in CORE_CAPABILITIES[capability]}),
        "services": list(services),
        "weight": float(weight),
    }


def _questions(org_type: str) -> list[dict[str, Any]]:
    rows = [_question_row(row) for row in QUESTION_BLUEPRINTS]
    if org_type == "Faith-Based Organization":
        rows.append(_question_row(FAITH_QUESTION))
    if org_type == "School or Educational Institution":
        rows.append(_question_row(SCHOOL_QUESTION))
    if org_type in {"Faith-Based Organization", "School or Educational Institution", "Government or Public Institution", "Event Venue or Hospitality"}:
        rows.append(_question_row(PUBLIC_QUESTION))
    return rows


_COVERED_CORE_CAPABILITIES = {
    capability
    for row in QUESTION_BLUEPRINTS
    for capability in row[3]
}
if set(CORE_CAPABILITIES) != _COVERED_CORE_CAPABILITIES:
    missing = sorted(set(CORE_CAPABILITIES) - _COVERED_CORE_CAPABILITIES)
    extra = sorted(_COVERED_CORE_CAPABILITIES - set(CORE_CAPABILITIES))
    raise RuntimeError(f"Protection Advisor capability coverage mismatch; missing={missing}; extra={extra}")


def _capability_results(
    questions: list[dict[str, Any]], answers: dict[str, dict[str, Any]]
) -> tuple[list[dict[str, Any]], dict[str, int]]:
    totals = {name: {"need": 0.0, "possible": 0.0, "unknown": 0} for name in CORE_CAPABILITIES}
    for question in questions:
        state = answers.get(question["key"], {}).get("answer_state", "Unknown")
        if state == "Not Applicable":
            continue
        need = STATE_NEED.get(state, 0.8)
        for capability in question["capabilities"]:
            totals[capability]["need"] += need * question["weight"]
            totals[capability]["possible"] += 3.0 * question["weight"]
            if state in {"Unknown", "Declined"}:
                totals[capability]["unknown"] += 1
    capability_rows = []
    for name, values in totals.items():
        score = round(100 * values["need"] / values["possible"]) if values["possible"] else 0
        capability_rows.append({
            "capability": name,
            "mission_areas": list(CORE_CAPABILITIES[name]),
            "need_score": score,
            "information_gap": values["unknown"] > 0,
        })
    capability_rows.sort(key=lambda row: (-row["need_score"], row["capability"]))
    mission_scores: dict[str, int] = {}
    for area in ("Prevention", "Protection", "Mitigation", "Response", "Recovery"):
        relevant = [row["need_score"] for row in capability_rows if area in row["mission_areas"]]
        mission_scores[area] = round(sum(relevant) / len(relevant)) if relevant else 0
    return capability_rows, mission_scores

def _initialize(conn: Any) -> None:
    conn.executescript("""
    CREATE TABLE IF NOT EXISTS advisor_public_sessions (
      session_key TEXT PRIMARY KEY,
      token_sha256 TEXT NOT NULL UNIQUE,
      csrf_sha256 TEXT NOT NULL,
      organization_type TEXT NOT NULL,
      primary_consent INTEGER NOT NULL,
      secondary_deidentified_consent INTEGER NOT NULL,
      consent_notice_version TEXT NOT NULL,
      retention_policy_version TEXT NOT NULL,
      questionnaire_version TEXT NOT NULL,
      status TEXT NOT NULL,
      created_at TEXT NOT NULL,
      expires_at TEXT NOT NULL,
      submitted_at TEXT NOT NULL DEFAULT '',
      deleted_at TEXT NOT NULL DEFAULT ''
    );
    CREATE TABLE IF NOT EXISTS advisor_public_answer_revisions (
      revision_key TEXT PRIMARY KEY,
      session_key TEXT NOT NULL,
      question_key TEXT NOT NULL,
      revision_no INTEGER NOT NULL,
      answer_state TEXT NOT NULL,
      note TEXT NOT NULL DEFAULT '',
      created_at TEXT NOT NULL,
      content_sha256 TEXT NOT NULL,
      FOREIGN KEY (session_key) REFERENCES advisor_public_sessions(session_key) ON DELETE CASCADE,
      UNIQUE(session_key,question_key,revision_no)
    );
    CREATE INDEX IF NOT EXISTS idx_advisor_answers_session ON advisor_public_answer_revisions(session_key,question_key,revision_no);
    CREATE TABLE IF NOT EXISTS advisor_public_submissions (
      submission_key TEXT PRIMARY KEY,
      session_key TEXT NOT NULL UNIQUE,
      organization_name TEXT NOT NULL,
      contact_name TEXT NOT NULL,
      contact_email TEXT NOT NULL,
      answer_snapshot_json TEXT NOT NULL,
      answer_snapshot_sha256 TEXT NOT NULL,
      questionnaire_version TEXT NOT NULL,
      recommendation_version TEXT NOT NULL,
      consent_notice_version TEXT NOT NULL,
      retention_policy_version TEXT NOT NULL,
      secondary_deidentified_consent INTEGER NOT NULL,
      result_json TEXT NOT NULL,
      status TEXT NOT NULL,
      created_at TEXT NOT NULL,
      FOREIGN KEY (session_key) REFERENCES advisor_public_sessions(session_key) ON DELETE RESTRICT
    );
    CREATE TABLE IF NOT EXISTS advisor_public_lifecycle_events (
      event_key TEXT PRIMARY KEY,
      session_key TEXT NOT NULL,
      event_type TEXT NOT NULL,
      event_at TEXT NOT NULL,
      detail_sha256 TEXT NOT NULL,
      FOREIGN KEY (session_key) REFERENCES advisor_public_sessions(session_key) ON DELETE CASCADE
    );
    CREATE TABLE IF NOT EXISTS advisor_public_notification_outbox (
      notification_key TEXT PRIMARY KEY,
      submission_key TEXT NOT NULL,
      audience TEXT NOT NULL,
      recipient_email TEXT NOT NULL,
      subject TEXT NOT NULL,
      body_text TEXT NOT NULL,
      state TEXT NOT NULL,
      attempts INTEGER NOT NULL DEFAULT 0,
      last_attempt_at TEXT NOT NULL DEFAULT '',
      delivered_at TEXT NOT NULL DEFAULT '',
      error_code TEXT NOT NULL DEFAULT '',
      created_at TEXT NOT NULL,
      FOREIGN KEY (submission_key) REFERENCES advisor_public_submissions(submission_key) ON DELETE CASCADE
    );
    CREATE INDEX IF NOT EXISTS idx_advisor_notification_state
      ON advisor_public_notification_outbox(state,created_at);
    CREATE TABLE IF NOT EXISTS advisor_public_service_profiles (
      profile_key TEXT PRIMARY KEY,
      submission_key TEXT NOT NULL UNIQUE,
      profile_version TEXT NOT NULL,
      profile_json TEXT NOT NULL,
      profile_sha256 TEXT NOT NULL,
      package_recommendation_version TEXT NOT NULL,
      package_json TEXT NOT NULL,
      created_at TEXT NOT NULL,
      FOREIGN KEY (submission_key) REFERENCES advisor_public_submissions(submission_key) ON DELETE CASCADE
    );
    CREATE TABLE IF NOT EXISTS advisor_public_accounts (
      account_key TEXT PRIMARY KEY,
      email TEXT NOT NULL UNIQUE,
      password_salt TEXT NOT NULL,
      password_hash TEXT NOT NULL,
      status TEXT NOT NULL,
      created_at TEXT NOT NULL,
      last_login_at TEXT NOT NULL DEFAULT ''
    );
    CREATE TABLE IF NOT EXISTS advisor_public_account_sessions (
      token_sha256 TEXT PRIMARY KEY,
      account_key TEXT NOT NULL,
      created_at TEXT NOT NULL,
      expires_at TEXT NOT NULL,
      revoked_at TEXT NOT NULL DEFAULT '',
      FOREIGN KEY (account_key) REFERENCES advisor_public_accounts(account_key) ON DELETE CASCADE
    );
    CREATE INDEX IF NOT EXISTS idx_advisor_account_sessions_account
      ON advisor_public_account_sessions(account_key,expires_at);
    CREATE TABLE IF NOT EXISTS advisor_public_account_assessments (
      account_key TEXT NOT NULL,
      session_key TEXT NOT NULL UNIQUE,
      detailed_assessment_acknowledged INTEGER NOT NULL,
      identifiable_retention_consent INTEGER NOT NULL,
      acknowledged_at TEXT NOT NULL,
      PRIMARY KEY (account_key,session_key),
      FOREIGN KEY (account_key) REFERENCES advisor_public_accounts(account_key) ON DELETE CASCADE,
      FOREIGN KEY (session_key) REFERENCES advisor_public_sessions(session_key) ON DELETE CASCADE
    );
    CREATE TABLE IF NOT EXISTS advisor_public_profile_drafts (
      session_key TEXT PRIMARY KEY,
      account_key TEXT NOT NULL,
      draft_json TEXT NOT NULL,
      updated_at TEXT NOT NULL,
      FOREIGN KEY (session_key) REFERENCES advisor_public_sessions(session_key) ON DELETE CASCADE,
      FOREIGN KEY (account_key) REFERENCES advisor_public_accounts(account_key) ON DELETE CASCADE
    );
    """)


def _session(conn: Any, request: Request) -> tuple[Any, str]:
    token = request.cookies.get("salus_advisor_session", "")
    csrf = request.headers.get("x-csrf-token", "")
    if not token or not csrf:
        raise HTTPException(401, "Advisor session is required")
    row = conn.execute(
        "SELECT * FROM advisor_public_sessions WHERE token_sha256=?",
        (_sha(token),),
    ).fetchone()
    if not row or row["status"] not in ("Active", "Submitted") or row["deleted_at"]:
        raise HTTPException(401, "Advisor session is unavailable")
    if row["csrf_sha256"] != _sha(csrf):
        raise HTTPException(403, "Request verification failed")
    if row["expires_at"] <= _utc_text(_utc_now()) and row["status"] == "Active":
        raise HTTPException(401, "Advisor session has expired")
    return row, token


def _account_session(conn: Any, request: Request) -> Any:
    token = request.cookies.get("salus_advisor_account", "")
    if not token:
        raise HTTPException(401, "Part Two account login is required")
    row = conn.execute(
        """SELECT s.*,a.email,a.status account_status
             FROM advisor_public_account_sessions s
             JOIN advisor_public_accounts a ON a.account_key=s.account_key
            WHERE s.token_sha256=?""",
        (_sha(token),),
    ).fetchone()
    if not row or row["revoked_at"] or row["account_status"] != "Active":
        raise HTTPException(401, "Part Two account session is unavailable")
    if row["expires_at"] <= _utc_text(_utc_now()):
        raise HTTPException(401, "Part Two account session has expired")
    return row


def _require_account_assessment(conn: Any, account_key: str, session_key: str) -> Any:
    row = conn.execute(
        """SELECT * FROM advisor_public_account_assessments
            WHERE account_key=? AND session_key=?""",
        (account_key, session_key),
    ).fetchone()
    if not row or not row["detailed_assessment_acknowledged"] or not row["identifiable_retention_consent"]:
        raise HTTPException(403, "Part Two acknowledgement and identifiable-information consent are required")
    return row


def _current_answers(conn: Any, session_key: str) -> dict[str, dict[str, Any]]:
    rows = conn.execute(
        """SELECT a.* FROM advisor_public_answer_revisions a
           JOIN (SELECT question_key,MAX(revision_no) revision_no
                 FROM advisor_public_answer_revisions WHERE session_key=? GROUP BY question_key) latest
             ON latest.question_key=a.question_key AND latest.revision_no=a.revision_no
          WHERE a.session_key=? ORDER BY a.question_key""",
        (session_key, session_key),
    ).fetchall()
    return {row["question_key"]: dict(row) for row in rows}


def _result(questions: list[dict[str, Any]], answers: dict[str, dict[str, Any]]) -> dict[str, Any]:
    attention = []
    strengths = []
    unknowns = []
    for question in questions:
        state = answers.get(question["key"], {}).get("answer_state", "Unknown")
        if state in {"No", "Partially"}:
            attention.append(question["text"])
        elif state in {"Validated", "Documented", "Answered"}:
            strengths.append(question["text"])
        elif state in {"Unknown", "Declined"}:
            unknowns.append(question["text"])
    capability_rows, mission_scores = _capability_results(questions, answers)
    highest_need = capability_rows[0]["need_score"] if capability_rows else 0
    if highest_need >= 65 or len(attention) >= 10:
        level = "Comprehensive review recommended"
    elif highest_need >= 35 or len(attention) >= 4:
        level = "Focused review recommended"
    elif unknowns:
        level = "Foundation discovery recommended"
    else:
        level = "Foundation review recommended"
    return {
        "status": "Preliminary — Salus Review Required",
        "recommendation": level,
        "attention_count": len(attention),
        "strength_count": len(strengths),
        "information_gap_count": len(unknowns),
        "attention_topics": attention[:6],
        "information_gaps": unknowns[:6],
        "priority_capabilities": [row for row in capability_rows if row["need_score"] > 0][:8],
        "mission_area_scores": mission_scores,
        "core_capabilities_considered": len(CORE_CAPABILITIES),
        "notice": "This result is preliminary and non-binding. A qualified Salus professional must review scope, recommendations, service levels, and any price.",
        "manual_next_step": "Qualification, scoping, proposal, onboarding, and service delivery remain human-controlled.",
    }


def _page() -> str:
    options = "".join(f'<option value="{html.escape(item)}">{html.escape(item)}</option>' for item in sorted(ORGANIZATION_TYPES))
    activities = "".join(
        f'<label class="choice"><input type="checkbox" name="activity" value="{html.escape(item)}"> {html.escape(item)}</label>'
        for item in sorted(ACTIVITY_OPTIONS)
    )
    return """<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Protection Advisor | Salus Solutions</title>
<style>
:root{--blue:#477d9f;--ink:#14283a;--orange:#d9571e;--line:#d8e0e6;--soft:#f7f9fa}*{box-sizing:border-box}
body{margin:0;background:#fff;color:var(--ink);font:18px/1.55 Georgia,serif}main{max-width:980px;margin:auto;padding:48px 28px 80px}
h1,h2,h3,button,label,select,input,textarea{font-family:Arial,sans-serif}h1{font-size:3rem;font-weight:300;color:var(--blue);margin:.2rem 0}
h2{font-weight:400;font-size:1.9rem;margin-top:2rem}.brand{font:28px Arial,sans-serif;color:#111;margin-bottom:44px;display:flex;align-items:center;gap:14px}
.brand img{width:58px;height:58px;object-fit:contain}.muted{color:#536675}.panel{border-top:1px solid var(--line);padding-top:24px;margin-top:28px}
label{display:block;font-weight:600;margin:18px 0 7px}select,input[type=text],input[type=email],textarea{width:100%;font-size:1rem;padding:13px;border:1px solid #8d9aa3;border-radius:2px}
textarea{min-height:100px}.check,.choice{display:flex;gap:12px;align-items:flex-start;font-family:Georgia,serif;font-weight:400}.check input,.choice input{margin-top:7px}
button,.action{border:0;background:none;color:var(--orange);font:1.05rem Arial,sans-serif;padding:14px 0;cursor:pointer;text-align:left;text-decoration:none;display:inline-block;margin-right:26px}
button:disabled{color:#888;cursor:not-allowed}.question{padding:20px 0;border-bottom:1px solid var(--line)}.choices{display:flex;flex-wrap:wrap;gap:14px;margin-top:12px}
.choices label{font-weight:400;margin:0}.hidden{display:none}.error{color:#a12612}.result{background:var(--soft);padding:24px;margin-top:24px}.route{border-left:3px solid var(--blue);padding:4px 20px;margin:28px 0}
.package-item{padding:16px 0;border-bottom:1px solid var(--line)}.eyebrow{font:700 .78rem Arial,sans-serif;letter-spacing:.08em;text-transform:uppercase;color:var(--blue)}
@media(max-width:600px){body{font-size:17px}main{padding:28px 20px}h1{font-size:2.4rem}}
</style></head><body><main>
<div class="brand"><img src="/static/salus-reticle.svg" alt="Salus Solutions reticle"> Salus Solutions</div>
<h1>Protection Advisor™</h1><p class="muted">Find Your Salus Package</p>\n<p><a class="action" href="#accountAccess" onclick="openAccountLogin(event)">Return to Your Part Two Assessment &gt;</a></p>
<h2>Part One — Anonymous Protection Readiness Review</h2>
<p>Learn what may deserve attention without providing your name, email address, or organization name. Your anonymous answers produce an immediate preliminary summary.</p>
<section id="start" class="panel">
<label for="orgType">Organization type</label><select id="orgType"><option value="">Select your organization type</option>__OPTIONS__</select>
<label class="check"><input id="primary" type="checkbox"> <span>I consent to Salus retaining my anonymous assessment answers to prepare this preliminary result. I understand I may delete this record from this session.</span></label>
<label class="check"><input id="secondary" type="checkbox"> <span>Optional: I permit Salus to derive separately reviewed, appropriately deidentified knowledge for protective research and service improvement.</span></label>
<button onclick="startAssessment()">Begin Your Anonymous Review &gt;</button><p id="startError" class="error"></p></section>
<section id="assessment" class="hidden"><h2>Your anonymous assessment</h2><p>You may choose Not Sure, Not Applicable, or Prefer Not to Answer.</p><div id="questions"></div>
<button onclick="preliminaryResult()">Review My Preliminary Results &gt;</button><p id="assessmentError" class="error"></p></section>
<section id="result" class="hidden result"></section>
<section id="paths" class="hidden panel"><h2>Choose what happens next</h2>
<p>Your anonymous review is complete. Continue for a tailored preliminary package or browse individual Salus services without identifying yourself.</p>
<div class="route"><a class="action" href="#profileAgreement" onclick="showProfileAgreement(event)">Continue to Your Tailored Salus Package &gt;</a><br>
<a class="action" href="/protection-advisor/services">Explore Individual Salus Services &gt;</a></div></section>
<section id="profileAgreement" class="hidden panel"><p class="eyebrow">Before Part Two</p>
<h2>Understand the detailed assessment</h2>
<p>Part Two asks more detailed and sometimes difficult questions about your organization, operations, capabilities, concerns, and priorities. Accurate answers are necessary for a useful preliminary package recommendation.</p>
<p>You do not need to conduct research or obtain new records before continuing. Answer truthfully from your current knowledge. When you do not know, select <strong>Not sure</strong> or <strong>Prefer to discuss with Salus</strong> where available rather than guessing.</p>
<label class="check"><input id="detailAck" type="checkbox"> <span>I understand that Part Two is a detailed assessment and agree to answer truthfully from my current knowledge without guessing or overstating the organization’s capabilities.</span></label>
<label class="check"><input id="identifiableConsent" type="checkbox"> <span>I consent to Salus retaining the identifiable organization and contact information I provide in Part Two with my assessment record for package preparation, professional review, and possible follow-up.</span></label>
<button onclick="confirmProfile()">I Understand — Continue to Part Two &gt;</button><p id="profileAgreementError" class="error"></p></section>
<section id="accountAccess" class="hidden panel"><p class="eyebrow">Part Two Account</p>
<h2>Create an account or sign in</h2>
<p>Your Part Two account protects the confidential organization profile and lets you save your work, sign out, and return later.</p>
<div id="createAccountPanel"><h3>Create your account</h3>
<label>Email address<input id="accountEmail" type="email" maxlength="254" autocomplete="email"></label>
<label>Password<input id="accountPassword" type="password" minlength="12" maxlength="200" autocomplete="new-password"></label>
<label>Confirm password<input id="accountPasswordConfirm" type="password" minlength="12" maxlength="200" autocomplete="new-password"></label>
<p class="muted">Use at least 12 characters. Email verification and password recovery require the authorized Salus mail service.</p>
<button onclick="createAccount()">Create Account and Continue &gt;</button></div>
<div id="loginAccountPanel"><h3>Already have a Part Two account?</h3>
<label>Email address<input id="loginEmail" type="email" maxlength="254" autocomplete="email"></label>
<label>Password<input id="loginPassword" type="password" minlength="12" maxlength="200" autocomplete="current-password"></label>
<button onclick="loginAccount()">Sign In and Resume &gt;</button></div>
<p id="accountError" class="error"></p></section>
<section id="profile" class="hidden panel"><p class="eyebrow">Part Two — Confidential Organization and Service Profile</p>
<h2>Help us prepare your tailored preliminary package</h2>
<p>These candid questions help Salus understand scale, complexity, priorities, timing, and likely services. Identifying information is requested only because you elected to continue.</p>
<label>Organization name<input id="organizationName" type="text" maxlength="160"></label>
<label>Your name<input id="contactName" type="text" maxlength="160"></label>
<label>Email address<input id="contactEmail" type="email" maxlength="254"></label>
<label>Facility scope<select id="facilityScope"><option value="">Select</option><option>One facility</option><option>Several facilities</option><option>Organization-wide</option><option>Distributed, mobile, or remote operations</option><option>Not sure</option></select></label>
<label>Facility locations or general service area<textarea id="facilityLocations" maxlength="1500" placeholder="Provide addresses or general locations appropriate for this preliminary review. Do not provide access codes, floor plans, or sensitive security details."></textarea></label>
<label>Personnel and population range<select id="personnelRange"><option value="">Select</option><option>1–25</option><option>26–100</option><option>101–500</option><option>501–2,500</option><option>2,501–10,000</option><option>More than 10,000</option><option>Varies significantly</option><option>Prefer to discuss with Salus</option></select></label>
<label>People who may be affected, served, present, or dependent on operations<select id="affectedPopulationRange"><option value="">Select</option><option>1–25</option><option>26–100</option><option>101–500</option><option>501–2,500</option><option>2,501–10,000</option><option>More than 10,000</option><option>Varies significantly</option><option>Not sure</option><option>Prefer to discuss with Salus</option></select></label>
<label>Annual revenue or operating-budget range<select id="revenueRange"><option value="">Select</option><option>Under $1 million</option><option>$1 million–$5 million</option><option>$5 million–$25 million</option><option>$25 million–$100 million</option><option>$100 million–$500 million</option><option>Over $500 million</option><option>Government or nonprofit operating budget</option><option>Prefer to discuss with Salus</option></select></label>
<label>Activities and operating conditions that apply</label><div id="activities">__ACTIVITIES__</div>
<label>Essential products, services, or functions<textarea id="essentialFunctions" maxlength="1200"></textarea></label>
<label>Maximum tolerable interruption for the most essential function<select id="maximumTolerableDowntime"><option value="">Select</option><option>Less than 4 hours</option><option>4–24 hours</option><option>1–3 days</option><option>4–7 days</option><option>More than 7 days</option><option>Not established</option><option>Not sure</option><option>Prefer to discuss with Salus</option></select></label>
<label>Current protection and preparedness program<select id="existingProgramMaturity"><option value="">Select</option><option>Recently assessed, documented, and validated</option><option>Documented but not recently tested</option><option>Partially documented or inconsistently applied</option><option>Mostly informal</option><option>Little or no current program</option><option>Not sure</option><option>Prefer to discuss with Salus</option></select></label>
<label>Internal capacity to implement improvements<select id="internalImplementationCapacity"><option value="">Select</option><option>Dedicated qualified team</option><option>Shared or part-time personnel</option><option>Limited internal capacity</option><option>Need Salus implementation support</option><option>Not sure</option><option>Prefer to discuss with Salus</option></select></label>
<label>Primary outcome sought<select id="primaryObjective"><option value="">Select</option><option>Independent assessment and priorities</option><option>Plans, procedures, and decision support</option><option>Facility or operational protection improvements</option><option>Training and exercises</option><option>Continuity and recovery capability</option><option>Protective intelligence and monitoring</option><option>Implementation assistance</option><option>Immediate incident or crisis support</option><option>Comprehensive protection program</option><option>Not sure</option></select></label>
<label>External requirement or decision driver<select id="externalRequirements"><option value="">Select</option><option>Regulatory or statutory requirement</option><option>Contract or customer requirement</option><option>Insurance or underwriting concern</option><option>Board, executive, or governance requirement</option><option>Recent incident or credible concern</option><option>Future planning or budget decision</option><option>No known external requirement</option><option>Not sure</option><option>Prefer to discuss with Salus</option></select></label>
<label>Recent incidents, concerns, deadlines, or reasons for seeking assistance<textarea id="recentConcerns" maxlength="1200"></textarea></label>
<label>Desired timing<select id="desiredTiming"><option value="">Select</option><option>Immediate concern</option><option>Within 30 days</option><option>Within 90 days</option><option>Within 6 months</option><option>Planning for a future budget cycle</option><option>Not sure</option></select></label>
<label>Who can authorize the next step?<input id="decisionAuthority" type="text" maxlength="160" placeholder="Role or decision group; a personal name is not required"></label>
<label>Potential investment range<select id="investmentRange"><option value="">Select</option><option>Under $10,000</option><option>$10,000–$25,000</option><option>$25,000–$75,000</option><option>$75,000–$250,000</option><option>Over $250,000</option><option>Need phased options</option><option>Not established</option><option>Prefer to discuss with Salus</option></select></label>
<p class="muted">Do not enter passwords, financial account information, medical records, government identifiers, classified information, detailed hazardous-material inventories, access-control details, or information whose disclosure could create an immediate security risk.</p>
<p id="draftStatus" class="muted">Changes will be saved to your Part Two account.</p><button onclick="saveDraft()">Save Progress &gt;</button><button onclick="logoutAccount()">Sign Out &gt;</button><br><button onclick="submitProfile()">Prepare My Tailored Preliminary Package &gt;</button><p id="submitError" class="error"></p></section>
<section id="package" class="hidden result"></section>
<section class="panel"><h2>Important notice</h2><p>Protection Advisor provides preliminary educational and decision-support information. It is not an emergency reporting service, completed THIRA, professional security assessment, legal or insurance advice, or guarantee against loss. Salus professionals review information, evidence, context, scope, recommendations, and pricing before issuing formal findings or proposals.</p></section>
</main><script>
let csrf="",questions=[];
async function call(path,opts={}){opts.headers={"Content-Type":"application/json",...(csrf?{"X-CSRF-Token":csrf}:{}),...(opts.headers||{})};const r=await fetch(path,opts);const data=await r.json().catch(()=>({detail:"Request failed"}));if(!r.ok)throw new Error(data.detail||"Request failed");return data}
async function startAssessment(){startError.textContent="";try{const data=await call("/public/protection-advisor/session",{method:"POST",body:JSON.stringify({organization_type:orgType.value,primary_consent:primary.checked,secondary_deidentified_consent:secondary.checked})});csrf=data.csrf_token;questions=data.questions;start.classList.add("hidden");assessment.classList.remove("hidden");renderQuestions()}catch(x){startError.textContent=x.message}}
function renderQuestions(){document.getElementById("questions").innerHTML=questions.map((q,i)=>'<div class="question"><strong>'+(i+1)+'. '+q.text+'</strong><div class="choices">'+["Validated","Documented","Partially","No","Unknown","Not Applicable","Declined"].map(s=>'<label><input type="radio" name="'+q.key+'" value="'+s+'" onchange="saveAnswer(this.name,this.value)"> '+(s==="Validated"?"Yes — documented and recently validated":s==="Documented"?"Yes — documented but not recently tested":s==="Unknown"?"Not Sure":s==="Declined"?"Prefer Not to Answer":s)+'</label>').join("")+'</div></div>').join("")}
async function saveAnswer(key,state){await call("/public/protection-advisor/answer",{method:"POST",body:JSON.stringify({question_key:key,answer_state:state,note:""})})}
async function preliminaryResult(){assessmentError.textContent="";try{const data=await call("/public/protection-advisor/preliminary",{method:"POST",body:"{}"});const r=data.result;assessment.classList.add("hidden");result.classList.remove("hidden");paths.classList.remove("hidden");result.innerHTML='<p class="eyebrow">Your Anonymous Preliminary Summary</p><h2>'+r.recommendation+'</h2><p>'+r.notice+'</p><p><strong>Potential attention areas:</strong> '+r.attention_count+'. <strong>Indicated strengths:</strong> '+r.strength_count+'. <strong>Information gaps:</strong> '+r.information_gap_count+'.</p><p>'+r.manual_next_step+'</p>';result.scrollIntoView({behavior:"smooth"})}catch(x){assessmentError.textContent=x.message}}
function showProfileAgreement(event){event.preventDefault();profileAgreement.classList.remove("hidden");profileAgreement.scrollIntoView({behavior:"smooth"})}
function openAccountLogin(event){event.preventDefault();accountAccess.classList.remove("hidden");accountAccess.scrollIntoView({behavior:"smooth"})}
function confirmProfile(){profileAgreementError.textContent="";if(!detailAck.checked||!identifiableConsent.checked){profileAgreementError.textContent="Both acknowledgements are required before Part Two.";return}profileAgreement.classList.add("hidden");accountAccess.classList.remove("hidden");accountAccess.scrollIntoView({behavior:"smooth"})}
function showProfileForAccount(email,draft){accountAccess.classList.add("hidden");contactEmail.value=email;contactEmail.readOnly=true;hydrateDraft(draft||{});profile.classList.remove("hidden");profile.scrollIntoView({behavior:"smooth"});enableAutosave()}
async function createAccount(){accountError.textContent="";try{if(accountPassword.value!==accountPasswordConfirm.value)throw new Error("Passwords do not match");const data=await call("/public/protection-advisor/account",{method:"POST",body:JSON.stringify({email:accountEmail.value,password:accountPassword.value,detailed_assessment_acknowledged:detailAck.checked,identifiable_retention_consent:identifiableConsent.checked})});showProfileForAccount(data.email,data.draft)}catch(x){accountError.textContent=x.message}}
async function loginAccount(){accountError.textContent="";try{const data=await call("/public/protection-advisor/login",{method:"POST",body:JSON.stringify({email:loginEmail.value,password:loginPassword.value})});csrf=data.csrf_token;questions=data.questions||[];showProfileForAccount(data.email,data.draft)}catch(x){accountError.textContent=x.message}}
function draftFields(){return {organization_name:organizationName.value,contact_name:contactName.value,contact_email:contactEmail.value,facility_scope:facilityScope.value,facility_locations:facilityLocations.value,personnel_range:personnelRange.value,affected_population_range:affectedPopulationRange.value,annual_revenue_range:revenueRange.value,specific_activities:[...document.querySelectorAll('input[name="activity"]:checked')].map(x=>x.value),essential_functions:essentialFunctions.value,maximum_tolerable_downtime:maximumTolerableDowntime.value,existing_program_maturity:existingProgramMaturity.value,internal_implementation_capacity:internalImplementationCapacity.value,primary_objective:primaryObjective.value,external_requirements:externalRequirements.value,recent_concerns:recentConcerns.value,desired_timing:desiredTiming.value,decision_authority:decisionAuthority.value,investment_range:investmentRange.value}}
function hydrateDraft(d){const ids={organization_name:"organizationName",contact_name:"contactName",facility_scope:"facilityScope",facility_locations:"facilityLocations",personnel_range:"personnelRange",affected_population_range:"affectedPopulationRange",annual_revenue_range:"revenueRange",essential_functions:"essentialFunctions",maximum_tolerable_downtime:"maximumTolerableDowntime",existing_program_maturity:"existingProgramMaturity",internal_implementation_capacity:"internalImplementationCapacity",primary_objective:"primaryObjective",external_requirements:"externalRequirements",recent_concerns:"recentConcerns",desired_timing:"desiredTiming",decision_authority:"decisionAuthority",investment_range:"investmentRange"};Object.entries(ids).forEach(([k,id])=>{if(d[k]!==undefined)document.getElementById(id).value=d[k]});(d.specific_activities||[]).forEach(v=>{const el=[...document.querySelectorAll('input[name="activity"]')].find(x=>x.value===v);if(el)el.checked=true})}
let draftTimer=null;
function enableAutosave(){profile.querySelectorAll("input,select,textarea").forEach(el=>el.addEventListener("change",()=>{clearTimeout(draftTimer);draftTimer=setTimeout(saveDraft,500)}))}
async function saveDraft(){draftStatus.textContent="Saving…";try{const data=await call("/public/protection-advisor/draft",{method:"POST",body:JSON.stringify({fields:draftFields()})});draftStatus.textContent="Saved "+new Date(data.updated_at).toLocaleString()}catch(x){draftStatus.textContent="Draft not saved: "+x.message}}
async function logoutAccount(){try{await call("/public/protection-advisor/logout",{method:"POST",body:"{}"})}finally{location.reload()}}
async function submitProfile(){submitError.textContent="";try{const selected=[...document.querySelectorAll('input[name="activity"]:checked')].map(x=>x.value);const data=await call("/public/protection-advisor/submit",{method:"POST",body:JSON.stringify({organization_name:organizationName.value,contact_name:contactName.value,contact_email:contactEmail.value,detailed_assessment_acknowledged:detailAck.checked,identifiable_retention_consent:identifiableConsent.checked,facility_scope:facilityScope.value,facility_locations:facilityLocations.value,personnel_range:personnelRange.value,affected_population_range:affectedPopulationRange.value,annual_revenue_range:revenueRange.value,specific_activities:selected,essential_functions:essentialFunctions.value,maximum_tolerable_downtime:maximumTolerableDowntime.value,existing_program_maturity:existingProgramMaturity.value,internal_implementation_capacity:internalImplementationCapacity.value,primary_objective:primaryObjective.value,external_requirements:externalRequirements.value,recent_concerns:recentConcerns.value,desired_timing:desiredTiming.value,decision_authority:decisionAuthority.value,investment_range:investmentRange.value})});profile.classList.add("hidden");const p=data.package;package.classList.remove("hidden");package.innerHTML='<p class="eyebrow">Tailored Preliminary Salus Package</p><h2>'+p.title+'</h2><p>'+p.rationale+'</p>'+p.services.map(s=>'<div class="package-item"><h3>'+s.title+' — Level '+s.level+'</h3><p>'+s.summary+'</p><p><strong>Why this level:</strong> '+s.why+'</p><p><strong>Core capabilities addressed:</strong> '+s.capabilities.join(", ")+'</p></div>').join("")+(p.later_phase_services.length?'<h3>Possible later-phase services</h3><p>'+p.later_phase_services.map(s=>s.title+' — Level '+s.level).join("; ")+'</p>':'')+'<p><strong>Suggested sequence:</strong> '+p.sequence.join(" → ")+'</p><p>'+p.notice+'</p><a class="action" href="https://www.salus.solutions/contact">Discuss This Package With Salus &gt;</a>';package.scrollIntoView({behavior:"smooth"})}catch(x){submitError.textContent=x.message}}
</script></body></html>""".replace("__OPTIONS__", options).replace("__ACTIVITIES__", activities)


def _service_catalog_page() -> str:
    items = "".join(
        f'<article class="service"><h2>{html.escape(title)}</h2><p>{html.escape(summary)}</p>'
        f'<a href="https://www.salus.solutions/contact">Discuss This Service With Salus &gt;</a></article>'
        for _, title, summary in SERVICE_CATALOG
    )
    return f"""<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Individual Salus Services | Protection Advisor</title><style>
:root{{--blue:#477d9f;--orange:#d9571e;--ink:#14283a;--line:#d8e0e6}}*{{box-sizing:border-box}}body{{margin:0;color:var(--ink);font:18px/1.55 Georgia,serif}}
main{{max-width:980px;margin:auto;padding:48px 28px 80px}}header{{display:flex;align-items:center;gap:14px;font:28px Arial,sans-serif;margin-bottom:42px}}header img{{width:58px;height:58px}}
h1,h2,a{{font-family:Arial,sans-serif}}h1{{font-size:3rem;font-weight:300;color:var(--blue)}}h2{{font-weight:400}}a{{color:var(--orange);text-decoration:none}}.service{{padding:20px 0;border-bottom:1px solid var(--line)}}
</style></head><body><main><header><img src="/static/salus-reticle.svg" alt="Salus Solutions reticle">Salus Solutions</header>
<p><a href="/protection-advisor">&lt; Protection Advisor</a></p><h1>Individual Salus Services</h1>
<p>Explore services directly without completing the confidential Organization and Service Profile. A Salus professional will confirm scope, deliverables, schedule, and pricing before any engagement.</p>
{items}</main></body></html>"""


SERVICE_LEVEL_NAMES = {1: "Foundation", 2: "Enhanced", 3: "Comprehensive"}
SERVICE_DEFAULT_CAPABILITIES = {
    "salthira": ("Threats and Hazards Identification", "Risk and Disaster Resilience Assessment"),
    "facility": ("Physical Protective Measures", "Access Control and Identity Verification"),
    "protective_intelligence": ("Intelligence and Information Sharing", "Situational Assessment"),
    "planning": ("Planning", "Public Information and Warning", "Operational Coordination"),
    "continuity": ("Infrastructure Systems", "Economic Recovery"),
    "cyber_physical": ("Cybersecurity", "Infrastructure Systems"),
    "training": ("Operational Coordination", "Risk Management for Protection Programs and Activities"),
    "protection": ("Physical Protective Measures", "On-scene Security, Protection, and Law Enforcement"),
    "incident_support": ("Operational Coordination", "Situational Assessment"),
    "implementation": ("Planning", "Long-term Vulnerability Reduction"),
    "monitoring": ("Intelligence and Information Sharing", "Risk Management for Protection Programs and Activities"),
}


def _package_recommendation(
    questions: list[dict[str, Any]],
    answers: dict[str, dict[str, Any]],
    profile: dict[str, Any],
) -> dict[str, Any]:
    catalog = {key: {"key": key, "title": title, "summary": summary} for key, title, summary in SERVICE_CATALOG}
    scores = {key: 0.0 for key in catalog}
    capabilities = {key: set() for key in catalog}
    evidence = {key: [] for key in catalog}
    information_gap_count = 0

    for question in questions:
        state = answers.get(question["key"], {}).get("answer_state", "Unknown")
        need = STATE_NEED.get(state, 0.8)
        if state in {"Unknown", "Declined"}:
            information_gap_count += 1
        if need <= 0:
            continue
        contribution = need * question["weight"]
        for service in question["services"]:
            scores[service] += contribution
            capabilities[service].update(question["capabilities"])
            evidence[service].append((contribution, state, question["domain"]))

    def add(service: str, points: float, reason: str, related: tuple[str, ...] = ()) -> None:
        scores[service] += points
        capabilities[service].update(related)
        evidence[service].append((points, "Profile", reason))

    activities = set(profile.get("specific_activities", []))
    activity_rules = {
        "Precious metals or other high-value materials": (
            ("facility", 3.0), ("protection", 3.0), ("protective_intelligence", 2.0)
        ),
        "Hazardous materials, fuels, chemicals, or regulated waste": (
            ("facility", 3.0), ("planning", 2.0), ("incident_support", 2.0)
        ),
        "Manufacturing, industrial processes, or heavy equipment": (
            ("facility", 2.5), ("cyber_physical", 2.5), ("continuity", 2.0)
        ),
        "Healthcare, medical, behavioral-health, or human services": (
            ("planning", 2.5), ("continuity", 2.0), ("training", 1.5)
        ),
        "Children, students, older adults, or people needing assistance": (
            ("planning", 2.5), ("training", 2.0), ("continuity", 1.5)
        ),
        "Public events, venues, hospitality, or mass gatherings": (
            ("protection", 3.0), ("planning", 2.5), ("protective_intelligence", 2.0)
        ),
        "Critical infrastructure, utilities, transportation, or logistics": (
            ("continuity", 3.0), ("cyber_physical", 2.5), ("facility", 2.0)
        ),
        "Sensitive information, technology, research, or intellectual property": (
            ("cyber_physical", 3.0), ("protective_intelligence", 2.0), ("continuity", 1.5)
        ),
        "Distributed, mobile, remote, travel, or international operations": (
            ("protective_intelligence", 2.5), ("continuity", 2.5), ("monitoring", 2.0)
        ),
        "Government, public safety, or essential public services": (
            ("planning", 2.5), ("continuity", 2.5), ("implementation", 1.5)
        ),
    }
    for activity in activities:
        for service, points in activity_rules.get(activity, ()):
            add(service, points, activity)

    scope = profile.get("facility_scope", "")
    if scope in {"Several facilities", "Organization-wide", "Distributed, mobile, or remote operations"}:
        add("implementation", 2.0, "multi-site or organization-wide scope")
        add("monitoring", 2.0, "multi-site or organization-wide scope")
        add("facility", 1.5, "multi-site or organization-wide scope")

    personnel = profile.get("personnel_range", "")
    affected = profile.get("affected_population_range", "")
    large_ranges = {"501–2,500", "2,501–10,000", "More than 10,000", "Varies significantly"}
    if personnel in large_ranges or affected in large_ranges:
        add("planning", 2.0, "large or variable affected population")
        add("training", 1.5, "large or variable affected population")
        add("implementation", 1.0, "large or variable affected population")

    downtime = profile.get("maximum_tolerable_downtime", "")
    if downtime == "Less than 4 hours":
        add("continuity", 4.0, "essential function tolerates less than four hours of interruption")
        add("cyber_physical", 2.0, "essential function tolerates less than four hours of interruption")
    elif downtime == "4–24 hours":
        add("continuity", 2.5, "essential function has a short interruption tolerance")
    elif downtime in {"Not established", "Not sure"}:
        add("continuity", 1.5, "recovery tolerance requires validation")
        add("salthira", 1.0, "recovery tolerance requires validation")

    maturity = profile.get("existing_program_maturity", "")
    if maturity == "Recently assessed, documented, and validated":
        add("monitoring", 3.0, "a mature program needs sustainment and reassessment")
    elif maturity == "Documented but not recently tested":
        add("training", 3.0, "documented capabilities require validation")
    elif maturity == "Partially documented or inconsistently applied":
        add("planning", 2.0, "program elements are incomplete or inconsistent")
        add("implementation", 2.0, "program elements are incomplete or inconsistent")
    elif maturity == "Mostly informal":
        add("salthira", 2.5, "the current program is mostly informal")
        add("planning", 2.5, "the current program is mostly informal")
        add("implementation", 2.0, "the current program is mostly informal")
    elif maturity == "Little or no current program":
        add("salthira", 4.0, "little or no current program was identified")
        add("planning", 3.0, "little or no current program was identified")
        add("implementation", 3.0, "little or no current program was identified")

    capacity = profile.get("internal_implementation_capacity", "")
    if capacity == "Limited internal capacity":
        add("implementation", 2.5, "internal implementation capacity is limited")
    elif capacity == "Need Salus implementation support":
        add("implementation", 4.0, "Salus implementation support is requested")
        add("monitoring", 2.0, "continuing support may be needed")

    objective_rules = {
        "Independent assessment and priorities": "salthira",
        "Plans, procedures, and decision support": "planning",
        "Facility or operational protection improvements": "facility",
        "Training and exercises": "training",
        "Continuity and recovery capability": "continuity",
        "Protective intelligence and monitoring": "protective_intelligence",
        "Implementation assistance": "implementation",
        "Immediate incident or crisis support": "incident_support",
        "Comprehensive protection program": "implementation",
    }
    objective = profile.get("primary_objective", "")
    if objective in objective_rules:
        add(objective_rules[objective], 4.0, f"stated primary objective: {objective}")
    if objective == "Comprehensive protection program":
        add("salthira", 2.0, "comprehensive program requested")
        add("monitoring", 2.0, "comprehensive program requested")

    timing = profile.get("desired_timing", "")
    if timing == "Immediate concern":
        add("incident_support", 6.0, "immediate concern")
        add("protective_intelligence", 2.0, "immediate concern")
    elif timing == "Within 30 days":
        add("implementation", 2.0, "near-term delivery requirement")

    external = profile.get("external_requirements", "")
    if external in {
        "Regulatory or statutory requirement",
        "Contract or customer requirement",
        "Insurance or underwriting concern",
        "Board, executive, or governance requirement",
    }:
        add("salthira", 1.5, external)
        add("implementation", 1.5, external)
    elif external == "Recent incident or credible concern":
        add("protective_intelligence", 2.5, external)
        add("incident_support", 2.0, external)

    if profile.get("decision_authority", "").casefold() in {"unknown", "not sure"}:
        add("implementation", 1.0, "decision authority requires clarification")
    if information_gap_count >= max(5, len(questions) // 4):
        add("salthira", 3.0, "material information gaps require structured discovery")

    ranked = sorted(scores, key=lambda key: (-scores[key], key))
    qualified = [key for key in ranked if scores[key] >= 3.0]
    if not qualified:
        qualified = ["monitoring"] if maturity == "Recently assessed, documented, and validated" else ["salthira"]
        add(qualified[0], 1.0, "focused professional confirmation is appropriate")
    primary_keys = qualified[:4]
    later_keys = qualified[4:7]

    def service_row(key: str) -> dict[str, Any]:
        score = scores[key]
        level = 3 if score >= 12.0 else 2 if score >= 6.0 else 1
        level_name = SERVICE_LEVEL_NAMES[level]
        relevant_capabilities = sorted(capabilities[key] or SERVICE_DEFAULT_CAPABILITIES[key])[:6]
        if relevant_capabilities:
            why = (
                f"{level_name} service is indicated by needs involving "
                + ", ".join(relevant_capabilities[:3])
                + "."
            )
        else:
            why = f"{level_name} service is indicated by the organization and service profile."
        return {
            **catalog[key],
            "level": level,
            "level_name": level_name,
            "capabilities": relevant_capabilities,
            "why": why,
            "basis": [
                {"weight": round(item[0], 2), "state": item[1], "factor": item[2]}
                for item in sorted(evidence[key], key=lambda item: -item[0])[:5]
            ],
        }

    services = [service_row(key) for key in primary_keys]
    later_services = [service_row(key) for key in later_keys]
    capability_rows, mission_scores = _capability_results(questions, answers)
    return {
        "title": f"{services[0]['title']}-led protection package",
        "primary_service": services[0],
        "services": services,
        "later_phase_services": later_services,
        "sequence": [f"{item['title']} — Level {item['level']}" for item in services],
        "priority_capabilities": [row for row in capability_rows if row["need_score"] > 0][:8],
        "mission_area_scores": mission_scores,
        "core_capabilities_considered": len(CORE_CAPABILITIES),
        "rationale": "This preliminary package connects the capability conditions identified in Part One with the scale, consequences, activities, dependencies, maturity, timing, and implementation context supplied in Part Two.",
        "notice": "Preliminary — Subject to Salus Professional Review. A Salus professional must validate the answers, capability interpretation, service selection, level, scope, evidence, specialists, deliverables, schedule, pricing, contract terms, and Protected Member eligibility.",
        "version": PACKAGE_RECOMMENDATION_VERSION,
    }


async def _send_graph_email(recipient: str, subject: str, body_text: str) -> tuple[bool, str]:
    if NOTIFICATION_MODE != "graph":
        return False, "delivery_not_configured"
    if not NOTIFICATION_FROM:
        return False, "sender_not_configured"
    try:
        credential = ManagedIdentityCredential(client_id=os.getenv("AZURE_CLIENT_ID") or None)
        token = credential.get_token("https://graph.microsoft.com/.default").token
        sender = NOTIFICATION_FROM.replace("'", "").replace("/", "")
        payload = {
            "message": {
                "subject": subject,
                "body": {"contentType": "Text", "content": body_text},
                "toRecipients": [{"emailAddress": {"address": recipient}}],
            },
            "saveToSentItems": True,
        }
        async with httpx.AsyncClient(timeout=15.0) as client:
            response = await client.post(
                f"https://graph.microsoft.com/v1.0/users/{sender}/sendMail",
                headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
                json=payload,
            )
        if response.status_code == 202:
            return True, ""
        return False, f"graph_http_{response.status_code}"
    except Exception as exc:
        return False, type(exc).__name__[:80]


async def _deliver_outbox(conn: Any, notification_key: str) -> None:
    row = conn.execute(
        "SELECT * FROM advisor_public_notification_outbox WHERE notification_key=?",
        (notification_key,),
    ).fetchone()
    if not row or row["state"] == "Delivered":
        return
    attempted = _utc_text(_utc_now())
    delivered, error_code = await _send_graph_email(
        row["recipient_email"], row["subject"], row["body_text"]
    )
    conn.execute(
        """UPDATE advisor_public_notification_outbox
           SET state=?,attempts=attempts+1,last_attempt_at=?,delivered_at=?,error_code=?
         WHERE notification_key=?""",
        (
            "Delivered" if delivered else "Pending",
            attempted,
            attempted if delivered else "",
            error_code,
            notification_key,
        ),
    )
    conn.commit()


def _review_page(rows: list[dict[str, Any]]) -> str:
    body_rows = []
    for row in rows:
        result = json.loads(row["result_json"])
        body_rows.append(
            "<tr>"
            f"<td>{html.escape(row['created_at'])}</td>"
            f"<td><a href='/protection-advisor/review/{html.escape(row['submission_key'])}'>"
            f"{html.escape(row['organization_name'])} &gt;</a></td>"
            f"<td>{html.escape(row['contact_name'])}<br>{html.escape(row['contact_email'])}</td>"
            f"<td>{html.escape(result.get('recommendation',''))}</td>"
            f"<td>{html.escape(row['status'])}</td>"
            f"<td>{html.escape(row['notification_state'])}</td>"
            "</tr>"
        )
    rows_html = "".join(body_rows) or "<tr><td colspan='6'>No Protection Advisor submissions yet.</td></tr>"
    return f"""<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Protection Advisor Review | Salus Solutions</title><style>
:root{{--orange:#dc4f17;--blue:#477fa4;--ink:#172938;--line:#dce3e8}}*{{box-sizing:border-box}}body{{margin:0;background:#fff;color:var(--ink);font:17px/1.55 Georgia,serif}}
main{{max-width:1180px;margin:auto;padding:44px 28px 80px}}header{{display:flex;align-items:center;gap:18px;margin-bottom:42px}}header img{{width:66px;height:66px;object-fit:contain}}
.brand{{font:30px Arial,sans-serif;color:#111}}h1{{font:300 2.7rem Arial,sans-serif;color:var(--blue)}}table{{width:100%;border-collapse:collapse}}th,td{{padding:14px 12px;border-bottom:1px solid var(--line);text-align:left;vertical-align:top}}
th{{font:600 .85rem Arial,sans-serif;text-transform:uppercase}}a{{color:var(--orange);text-decoration:none}}.notice{{background:#f6f8fa;padding:14px 18px;border-left:3px solid var(--blue)}}
@media(max-width:760px){{table,thead,tbody,tr,th,td{{display:block}}thead{{display:none}}tr{{margin:18px 0;border:1px solid var(--line)}}}}
</style></head><body><main><header><img src="/static/salus-reticle.svg" alt="Salus Solutions reticle"><div class="brand">Salus Solutions</div></header>
<h1>Protection Advisor Review</h1><p class="notice">Authorized Salus review workspace. Prospect records remain separate from Protected Member tenant records until an authorized person completes the governed intake decision.</p>
<table><thead><tr><th>Submitted</th><th>Organization</th><th>Contact</th><th>Recommendation</th><th>Status</th><th>Notification</th></tr></thead><tbody>{rows_html}</tbody></table>
<p><a href="/">&lt; SalCAPA Command Center</a></p></main></body></html>"""


def _review_detail(row: dict[str, Any]) -> str:
    result = json.loads(row["result_json"])
    answers = json.loads(row["answer_snapshot_json"])
    answer_rows = "".join(
        f"<tr><td>{html.escape(key.replace('_',' ').title())}</td><td>{html.escape(str(value.get('answer_state','')))}</td></tr>"
        for key, value in answers.items()
    )
    return f"""<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Protection Advisor Submission | Salus Solutions</title><style>
body{{max-width:900px;margin:auto;padding:42px 26px 80px;color:#172938;font:17px/1.55 Georgia,serif}}header{{display:flex;align-items:center;gap:16px}}header img{{width:62px;height:62px;object-fit:contain}}h1{{font:300 2.5rem Arial,sans-serif;color:#477fa4}}h2{{font:400 1.55rem Arial,sans-serif}}a,button{{color:#dc4f17}}table{{width:100%;border-collapse:collapse}}td{{padding:11px;border-bottom:1px solid #dce3e8;vertical-align:top}}
.notice{{background:#f6f8fa;padding:14px 18px;border-left:3px solid #477fa4}}</style></head><body>
<header><img src="/static/salus-reticle.svg" alt="Salus Solutions reticle"><strong>Salus Solutions</strong></header>
<p><a href="/protection-advisor/review">&lt; All submissions</a></p><h1>{html.escape(row['organization_name'])}</h1>
<p><strong>Contact:</strong> {html.escape(row['contact_name'])} · <a href="mailto:{html.escape(row['contact_email'])}">{html.escape(row['contact_email'])}</a><br>
<strong>Submitted:</strong> {html.escape(row['created_at'])}<br><strong>Status:</strong> {html.escape(row['status'])}</p>
<h2>Preliminary result</h2><p class="notice"><strong>{html.escape(result.get('recommendation',''))}</strong><br>{html.escape(result.get('notice',''))}</p>
<p>Potential attention areas: {int(result.get('attention_count',0))}. Information gaps: {int(result.get('information_gap_count',0))}.</p>
<h2>Assessment answers</h2><table>{answer_rows}</table></body></html>"""


def register_public_protection_advisor(app: Any, ctx: dict[str, Any]) -> None:
    conn = ctx["db"]()
    try:
        _initialize(conn)
        conn.commit()
    finally:
        conn.close()

    def limited(request: Request, token: str = "") -> None:
        limiter = ctx["RATE_LIMITER"]
        source = request.client.host if request.client else ""
        key = "advisor:" + limiter.key(source, token)
        allowed, _, retry = limiter.allow(key)
        if not allowed:
            raise HTTPException(429, f"Please wait {retry} seconds before trying again")

    @app.get("/protection-advisor/services", response_class=HTMLResponse)
    def protection_advisor_services() -> HTMLResponse:
        return HTMLResponse(_service_catalog_page(), headers={"Cache-Control": "no-store", "X-Frame-Options": "DENY", "Referrer-Policy": "no-referrer"})

    @app.get("/protection-advisor", response_class=HTMLResponse)
    def protection_advisor_page() -> HTMLResponse:
        return HTMLResponse(_page(), headers={"Cache-Control": "no-store", "X-Frame-Options": "DENY", "Referrer-Policy": "no-referrer", "Content-Security-Policy": "default-src 'self'; style-src 'unsafe-inline'; script-src 'unsafe-inline'; connect-src 'self'; frame-ancestors 'none'; base-uri 'none'; form-action 'self'"})

    @app.get("/protection-advisor/review", response_class=HTMLResponse)
    def protection_advisor_review(request: Request) -> HTMLResponse:
        ctx["require"](request, "admin")
        conn = ctx["db"]()
        try:
            _initialize(conn)
            rows = [dict(row) for row in conn.execute(
                """SELECT s.*,
                   COALESCE((SELECT CASE WHEN SUM(CASE WHEN state='Delivered' THEN 1 ELSE 0 END)=COUNT(*)
                                        THEN 'Delivered' ELSE 'Pending' END
                               FROM advisor_public_notification_outbox n
                              WHERE n.submission_key=s.submission_key),'Not queued') notification_state
                     FROM advisor_public_submissions s
                    ORDER BY s.created_at DESC"""
            ).fetchall()]
            return HTMLResponse(_review_page(rows), headers={"Cache-Control": "no-store", "X-Frame-Options": "DENY"})
        finally:
            conn.close()

    @app.get("/protection-advisor/review/{submission_key}", response_class=HTMLResponse)
    def protection_advisor_review_detail(submission_key: str, request: Request) -> HTMLResponse:
        ctx["require"](request, "admin")
        if not submission_key.startswith("SPA-SUBMISSION-"):
            raise HTTPException(404, "Submission not found")
        conn = ctx["db"]()
        try:
            row = conn.execute(
                "SELECT * FROM advisor_public_submissions WHERE submission_key=?",
                (submission_key,),
            ).fetchone()
            if not row:
                raise HTTPException(404, "Submission not found")
            return HTMLResponse(_review_detail(dict(row)), headers={"Cache-Control": "no-store", "X-Frame-Options": "DENY"})
        finally:
            conn.close()

    @app.post("/api/protection-advisor/review/notifications/{notification_key}/retry")
    async def retry_protection_advisor_notification(notification_key: str, request: Request) -> dict[str, Any]:
        ctx["require"](request, "admin")
        conn = ctx["db"]()
        try:
            _initialize(conn)
            await _deliver_outbox(conn, notification_key)
            row = conn.execute(
                "SELECT state,attempts,last_attempt_at,delivered_at,error_code FROM advisor_public_notification_outbox WHERE notification_key=?",
                (notification_key,),
            ).fetchone()
            if not row:
                raise HTTPException(404, "Notification not found")
            return dict(row)
        finally:
            conn.close()

    @app.post("/public/protection-advisor/account")
    async def create_protection_advisor_account(command: AccountCreateCommand, request: Request) -> JSONResponse:
        limited(request, request.cookies.get("salus_advisor_session", ""))
        if not command.detailed_assessment_acknowledged:
            raise HTTPException(400, "Detailed-assessment acknowledgement is required")
        if not command.identifiable_retention_consent:
            raise HTTPException(400, "Identifiable-information retention consent is required")
        conn = ctx["db"]()
        try:
            session, _ = _session(conn, request)
            existing = conn.execute(
                "SELECT account_key FROM advisor_public_accounts WHERE email=?",
                (command.email,),
            ).fetchone()
            if existing:
                raise HTTPException(409, "An account already exists for this email; sign in instead")
            now = _utc_now()
            account_key = "SPA-ACCOUNT-" + secrets.token_hex(16).upper()
            salt = secrets.token_hex(16)
            account_token = secrets.token_urlsafe(32)
            conn.execute(
                """INSERT INTO advisor_public_accounts
                   (account_key,email,password_salt,password_hash,status,created_at,last_login_at)
                   VALUES(?,?,?,?,?,?,?)""",
                (account_key, command.email, salt, _password_hash(command.password, salt),
                 "Active", _utc_text(now), _utc_text(now)),
            )
            conn.execute(
                """INSERT INTO advisor_public_account_sessions
                   (token_sha256,account_key,created_at,expires_at,revoked_at)
                   VALUES(?,?,?,?,?)""",
                (_sha(account_token), account_key, _utc_text(now),
                 _utc_text(now + timedelta(days=30)), ""),
            )
            conn.execute(
                """INSERT INTO advisor_public_account_assessments
                   (account_key,session_key,detailed_assessment_acknowledged,
                    identifiable_retention_consent,acknowledged_at)
                   VALUES(?,?,?,?,?)""",
                (account_key, session["session_key"], 1, 1, _utc_text(now)),
            )
            conn.execute(
                "INSERT INTO advisor_public_lifecycle_events VALUES(?,?,?,?,?)",
                ("SPA-EVENT-" + secrets.token_hex(16).upper(), session["session_key"],
                 "Part Two Account Created", _utc_text(now),
                 _sha(_json({"account_key": account_key, "email": command.email}))),
            )
            conn.commit()
            response = JSONResponse({"authenticated": True, "email": command.email, "draft": {}})
            response.set_cookie(
                "salus_advisor_account", account_token, httponly=True,
                secure=ctx.get("COOKIE_SECURE", True), samesite="strict",
                max_age=30 * 24 * 3600, path="/",
            )
            return response
        finally:
            conn.close()

    @app.post("/public/protection-advisor/login")
    async def login_protection_advisor_account(command: AccountLoginCommand, request: Request) -> JSONResponse:
        limited(request, command.email)
        conn = ctx["db"]()
        try:
            _initialize(conn)
            account = conn.execute(
                "SELECT * FROM advisor_public_accounts WHERE email=?",
                (command.email,),
            ).fetchone()
            if (
                not account
                or account["status"] != "Active"
                or not _password_matches(command.password, account["password_salt"], account["password_hash"])
            ):
                raise HTTPException(401, "Email or password is incorrect")
            linked = conn.execute(
                """SELECT s.* FROM advisor_public_account_assessments aa
                   JOIN advisor_public_sessions s ON s.session_key=aa.session_key
                  WHERE aa.account_key=? AND s.status='Active' AND s.deleted_at=''
                  ORDER BY aa.acknowledged_at DESC LIMIT 1""",
                (account["account_key"],),
            ).fetchone()
            if not linked:
                raise HTTPException(404, "No resumable Part Two assessment is available")
            now = _utc_now()
            account_token = secrets.token_urlsafe(32)
            advisor_token = secrets.token_urlsafe(32)
            csrf = secrets.token_urlsafe(24)
            conn.execute(
                "UPDATE advisor_public_account_sessions SET revoked_at=? WHERE account_key=? AND revoked_at=''",
                (_utc_text(now), account["account_key"]),
            )
            conn.execute(
                """INSERT INTO advisor_public_account_sessions
                   (token_sha256,account_key,created_at,expires_at,revoked_at)
                   VALUES(?,?,?,?,?)""",
                (_sha(account_token), account["account_key"], _utc_text(now),
                 _utc_text(now + timedelta(days=30)), ""),
            )
            conn.execute(
                """UPDATE advisor_public_sessions
                      SET token_sha256=?,csrf_sha256=?,expires_at=?
                    WHERE session_key=?""",
                (_sha(advisor_token), _sha(csrf), _utc_text(now + timedelta(hours=SESSION_HOURS)),
                 linked["session_key"]),
            )
            conn.execute(
                "UPDATE advisor_public_accounts SET last_login_at=? WHERE account_key=?",
                (_utc_text(now), account["account_key"]),
            )
            draft = conn.execute(
                "SELECT draft_json FROM advisor_public_profile_drafts WHERE session_key=?",
                (linked["session_key"],),
            ).fetchone()
            answers = _current_answers(conn, linked["session_key"])
            conn.commit()
            response = JSONResponse({
                "authenticated": True,
                "email": account["email"],
                "csrf_token": csrf,
                "questions": _questions(linked["organization_type"]),
                "answers": {key: row["answer_state"] for key, row in answers.items()},
                "draft": json.loads(draft["draft_json"]) if draft else {},
            })
            response.set_cookie(
                "salus_advisor_account", account_token, httponly=True,
                secure=ctx.get("COOKIE_SECURE", True), samesite="strict",
                max_age=30 * 24 * 3600, path="/",
            )
            response.set_cookie(
                "salus_advisor_session", advisor_token, httponly=True,
                secure=ctx.get("COOKIE_SECURE", True), samesite="strict",
                max_age=SESSION_HOURS * 3600, path="/",
            )
            return response
        finally:
            conn.close()

    @app.post("/public/protection-advisor/draft")
    async def save_protection_advisor_draft(command: DraftCommand, request: Request) -> dict[str, Any]:
        limited(request, request.cookies.get("salus_advisor_account", ""))
        conn = ctx["db"]()
        try:
            account = _account_session(conn, request)
            session, _ = _session(conn, request)
            _require_account_assessment(conn, account["account_key"], session["session_key"])
            now = _utc_text(_utc_now())
            payload = _json(command.fields)
            existing = conn.execute(
                "SELECT session_key FROM advisor_public_profile_drafts WHERE session_key=?",
                (session["session_key"],),
            ).fetchone()
            if existing:
                conn.execute(
                    """UPDATE advisor_public_profile_drafts
                          SET draft_json=?,updated_at=? WHERE session_key=?""",
                    (payload, now, session["session_key"]),
                )
            else:
                conn.execute(
                    """INSERT INTO advisor_public_profile_drafts
                       (session_key,account_key,draft_json,updated_at) VALUES(?,?,?,?)""",
                    (session["session_key"], account["account_key"], payload, now),
                )
            conn.commit()
            return {"saved": True, "updated_at": now}
        finally:
            conn.close()

    @app.post("/public/protection-advisor/logout")
    async def logout_protection_advisor_account(request: Request) -> JSONResponse:
        conn = ctx["db"]()
        try:
            token = request.cookies.get("salus_advisor_account", "")
            if token:
                conn.execute(
                    "UPDATE advisor_public_account_sessions SET revoked_at=? WHERE token_sha256=?",
                    (_utc_text(_utc_now()), _sha(token)),
                )
                conn.commit()
            response = JSONResponse({"authenticated": False})
            response.delete_cookie("salus_advisor_account", path="/")
            response.delete_cookie("salus_advisor_session", path="/")
            return response
        finally:
            conn.close()

    @app.post("/public/protection-advisor/session")
    async def start_public_session(command: StartCommand, request: Request) -> JSONResponse:
        limited(request)
        if not command.primary_consent:
            raise HTTPException(400, "Consent is required before assessment information can be retained")
        token, csrf = secrets.token_urlsafe(32), secrets.token_urlsafe(24)
        session_key = "SPA-SESSION-" + secrets.token_hex(16).upper()
        created = _utc_now()
        conn = ctx["db"]()
        try:
            _initialize(conn)
            conn.execute(
                """INSERT INTO advisor_public_sessions
                (session_key,token_sha256,csrf_sha256,organization_type,primary_consent,
                 secondary_deidentified_consent,consent_notice_version,retention_policy_version,
                 questionnaire_version,status,created_at,expires_at)
                 VALUES(?,?,?,?,?,?,?,?,?,?,?,?)""",
                (session_key,_sha(token),_sha(csrf),command.organization_type,1,
                 1 if command.secondary_deidentified_consent else 0,CONSENT_NOTICE_VERSION,
                 RETENTION_POLICY_VERSION,QUESTIONNAIRE_VERSION,"Active",_utc_text(created),
                 _utc_text(created+timedelta(hours=SESSION_HOURS))),
            )
            conn.execute("INSERT INTO advisor_public_lifecycle_events VALUES(?,?,?,?,?)",
                ("SPA-EVENT-"+secrets.token_hex(16).upper(),session_key,"Consent Recorded",
                 _utc_text(created),_sha(_json(command.model_dump()))))
            conn.commit()
        finally:
            conn.close()
        response = JSONResponse({"csrf_token": csrf, "questions": _questions(command.organization_type), "questionnaire_version": QUESTIONNAIRE_VERSION})
        response.set_cookie("salus_advisor_session", token, httponly=True, secure=ctx.get("COOKIE_SECURE", True), samesite="strict", max_age=SESSION_HOURS*3600, path="/")
        return response

    @app.post("/public/protection-advisor/answer")
    async def answer_public_question(command: AnswerCommand, request: Request) -> dict[str, Any]:
        limited(request, request.cookies.get("salus_advisor_session", ""))
        conn = ctx["db"]()
        try:
            session, _ = _session(conn, request)
            allowed = {q["key"] for q in _questions(session["organization_type"])}
            if command.question_key not in allowed:
                raise HTTPException(400, "Question is not part of this assessment")
            row = conn.execute("SELECT COALESCE(MAX(revision_no),0) n FROM advisor_public_answer_revisions WHERE session_key=? AND question_key=?",(session["session_key"],command.question_key)).fetchone()
            revision_no = int(row["n"])+1
            payload = {"question_key":command.question_key,"revision_no":revision_no,"answer_state":command.answer_state,"note":command.note}
            conn.execute("INSERT INTO advisor_public_answer_revisions VALUES(?,?,?,?,?,?,?,?)",
                ("SPA-ANSWER-"+secrets.token_hex(16).upper(),session["session_key"],command.question_key,
                 revision_no,command.answer_state,command.note,_utc_text(_utc_now()),_sha(_json(payload))))
            conn.commit()
            return {"saved": True, "revision_no": revision_no}
        finally:
            conn.close()

    @app.post("/public/protection-advisor/preliminary")
    async def preliminary_public_assessment(request: Request) -> dict[str, Any]:
        limited(request, request.cookies.get("salus_advisor_session", ""))
        conn = ctx["db"]()
        try:
            session, _ = _session(conn, request)
            if session["status"] != "Active":
                raise HTTPException(409, "Assessment has already been submitted")
            questions = _questions(session["organization_type"])
            answers = _current_answers(conn, session["session_key"])
            missing = [q["key"] for q in questions if q["key"] not in answers]
            if missing:
                raise HTTPException(400, "Answer every question before reviewing results")
            return {"anonymous": True, "result": _result(questions, answers)}
        finally:
            conn.close()

    @app.post("/public/protection-advisor/submit")
    async def submit_public_assessment(command: SubmitCommand, request: Request) -> dict[str, Any]:
        limited(request, request.cookies.get("salus_advisor_session", ""))
        conn = ctx["db"]()
        try:
            session, _ = _session(conn, request)
            account = _account_session(conn, request)
            _require_account_assessment(conn, account["account_key"], session["session_key"])
            if not command.detailed_assessment_acknowledged or not command.identifiable_retention_consent:
                raise HTTPException(400, "Part Two acknowledgement and retention consent are required")
            if command.contact_email != account["email"]:
                raise HTTPException(400, "Contact email must match the signed-in Part Two account")
            if session["status"] != "Active":
                raise HTTPException(409, "Assessment has already been submitted")
            questions = _questions(session["organization_type"])
            answers = _current_answers(conn, session["session_key"])
            missing = [q["key"] for q in questions if q["key"] not in answers]
            if missing:
                raise HTTPException(400, "Answer every question before submitting")
            snapshot = {key:{"answer_state":value["answer_state"],"note":value["note"],"revision_no":value["revision_no"],"content_sha256":value["content_sha256"]} for key,value in sorted(answers.items())}
            result = _result(questions, answers)
            profile = {
                "facility_scope": command.facility_scope,
                "facility_locations": command.facility_locations,
                "personnel_range": command.personnel_range,
                "affected_population_range": command.affected_population_range,
                "annual_revenue_range": command.annual_revenue_range,
                "specific_activities": command.specific_activities,
                "essential_functions": command.essential_functions,
                "maximum_tolerable_downtime": command.maximum_tolerable_downtime,
                "existing_program_maturity": command.existing_program_maturity,
                "internal_implementation_capacity": command.internal_implementation_capacity,
                "primary_objective": command.primary_objective,
                "external_requirements": command.external_requirements,
                "recent_concerns": command.recent_concerns,
                "desired_timing": command.desired_timing,
                "decision_authority": command.decision_authority,
                "investment_range": command.investment_range,
            }
            package = _package_recommendation(questions, answers, profile)
            created = _utc_text(_utc_now())
            submission_key = "SPA-SUBMISSION-" + secrets.token_hex(16).upper()
            conn.execute(
                """INSERT INTO advisor_public_submissions
                (submission_key,session_key,organization_name,contact_name,contact_email,
                 answer_snapshot_json,answer_snapshot_sha256,questionnaire_version,
                 recommendation_version,consent_notice_version,retention_policy_version,
                 secondary_deidentified_consent,result_json,status,created_at)
                 VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                (submission_key,session["session_key"],
                 command.organization_name,command.contact_name,command.contact_email,
                 _json(snapshot),_sha(_json(snapshot)),QUESTIONNAIRE_VERSION,RECOMMENDATION_VERSION,
                 CONSENT_NOTICE_VERSION,RETENTION_POLICY_VERSION,
                 session["secondary_deidentified_consent"],_json(result),
                 "Awaiting Salus Review",created),
            )
            conn.execute(
                """INSERT INTO advisor_public_service_profiles
                (profile_key,submission_key,profile_version,profile_json,profile_sha256,
                 package_recommendation_version,package_json,created_at)
                 VALUES(?,?,?,?,?,?,?,?)""",
                ("SPA-PROFILE-"+secrets.token_hex(16).upper(),submission_key,PACKAGE_PROFILE_VERSION,
                 _json(profile),_sha(_json(profile)),PACKAGE_RECOMMENDATION_VERSION,_json(package),created),
            )
            conn.execute("UPDATE advisor_public_sessions SET status='Submitted',submitted_at=? WHERE session_key=?",(created,session["session_key"]))
            conn.execute("DELETE FROM advisor_public_profile_drafts WHERE session_key=?", (session["session_key"],))
            conn.execute("INSERT INTO advisor_public_lifecycle_events VALUES(?,?,?,?,?)",
                ("SPA-EVENT-"+secrets.token_hex(16).upper(),session["session_key"],"Submitted for Salus Review",created,_sha(_json({"snapshot_sha256":_sha(_json(snapshot))}))))
            conn.commit()

            review_url = str(request.base_url).rstrip("/") + "/protection-advisor/review/" + submission_key
            internal_key = "SPA-NOTIFY-" + secrets.token_hex(16).upper()
            participant_key = "SPA-NOTIFY-" + secrets.token_hex(16).upper()
            internal_body = (
                "A new Protection Advisor assessment is awaiting Salus review.\n\n"
                f"Organization: {command.organization_name}\n"
                f"Contact: {command.contact_name}\n"
                f"Email: {command.contact_email}\n"
                f"Preliminary recommendation: {result['recommendation']}\n"
                f"Attention areas: {result['attention_count']}\n"
                f"Information gaps: {result['information_gap_count']}\n\n"
                f"Review securely in SalCAPA: {review_url}\n\n"
                "Assessment answers are intentionally not included in email."
            )
            participant_body = (
                f"Hello {command.contact_name},\n\n"
                "Salus Solutions received your Protection Advisor assessment.\n\n"
                f"Preliminary recommendation: {result['recommendation']}\n"
                f"Potential attention areas: {result['attention_count']}\n"
                f"Information gaps: {result['information_gap_count']}\n\n"
                f"{result['notice']}\n\n"
                "A Salus professional may contact you to discuss appropriate next steps. "
                "Do not reply with passwords, financial information, medical records, government identifiers, "
                "classified information, or operational details whose disclosure could create an immediate security risk."
            )
            outbox_created = _utc_text(_utc_now())
            conn.execute(
                "INSERT INTO advisor_public_notification_outbox VALUES(?,?,?,?,?,?,?,?,?,?,?,?)",
                (internal_key,submission_key,"Salus Reviewer",NOTIFICATION_TO,
                 f"Protection Advisor submission: {command.organization_name}",internal_body,
                 "Pending",0,"","","",outbox_created),
            )
            conn.execute(
                "INSERT INTO advisor_public_notification_outbox VALUES(?,?,?,?,?,?,?,?,?,?,?,?)",
                (participant_key,submission_key,"Participant",command.contact_email,
                 "Your Salus Protection Advisor assessment",participant_body,
                 "Pending",0,"","","",outbox_created),
            )
            conn.commit()
            await _deliver_outbox(conn, internal_key)
            await _deliver_outbox(conn, participant_key)
            notification_rows = conn.execute(
                "SELECT audience,state,error_code FROM advisor_public_notification_outbox WHERE submission_key=? ORDER BY audience",
                (submission_key,),
            ).fetchall()
            return {
                "submitted": True,
                "result": result,
                "package": package,
                "notifications": [dict(row) for row in notification_rows],
            }
        finally:
            conn.close()

    @app.post("/public/protection-advisor/delete")
    async def delete_public_assessment(request: Request) -> dict[str, Any]:
        limited(request, request.cookies.get("salus_advisor_session", ""))
        conn = ctx["db"]()
        try:
            session, _ = _session(conn, request)
            deleted = _utc_text(_utc_now())
            conn.execute("DELETE FROM advisor_public_submissions WHERE session_key=?",(session["session_key"],))
            conn.execute("DELETE FROM advisor_public_answer_revisions WHERE session_key=?",(session["session_key"],))
            conn.execute("UPDATE advisor_public_sessions SET status='Deleted',deleted_at=? WHERE session_key=?",(deleted,session["session_key"]))
            conn.execute("INSERT INTO advisor_public_lifecycle_events VALUES(?,?,?,?,?)",
                ("SPA-EVENT-"+secrets.token_hex(16).upper(),session["session_key"],"Content Deleted",deleted,_sha("content deleted at prospect request")))
            conn.commit()
            return {"deleted": True}
        finally:
            conn.close()
