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
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse, RedirectResponse, Response
from pydantic import BaseModel, ConfigDict, Field, field_validator
from telemetry import emit as emit_telemetry
from protection_advisor_report_artifact import prepare_review_artifact
from protection_advisor_docx_report import render_protection_advisor_pdf
from protection_advisor_engagements import (
    create_assessment_scope,
    initialize_engagement_schema,
    list_account_assessments,
)
from protection_advisor_report_contract import build_report_context
from salcapa_m365_advisor_reports import publish_advisor_docx

QUESTIONNAIRE_VERSION = "SPA-PUBLIC-QUESTIONNAIRE-2.0.0"
RECOMMENDATION_VERSION = "SPA-PUBLIC-RECOMMENDATION-2.0.0"
CONSENT_NOTICE_VERSION = "SPA-PUBLIC-CONSENT-1.0.0"
RETENTION_POLICY_VERSION = "SPA-PROSPECT-RETENTION-INDEFINITE-1.0.0"
REPORT_TEMPLATE_VERSION = "SPA-REPORT-TEMPLATE-1.0.0"
HANDLING_PROFILES = {
    "Commercial Confidential", "Government Sensitive", "Federal CUI",
    "Government Contractor CUI", "Specialized Regulated Information",
}
HANDLING_REVIEW_REQUIRED = HANDLING_PROFILES - {"Commercial Confidential"}
PACKAGE_PROFILE_VERSION = "SPA-SERVICE-PROFILE-2.0.0"
PACKAGE_RECOMMENDATION_VERSION = "SPA-PACKAGE-RECOMMENDATION-2.0.0"
SESSION_HOURS = 24  # Browser authentication lifetime only; retained records do not expire here.
NOTIFICATION_MODE = os.getenv("SALUS_ADVISOR_NOTIFICATION_MODE", "outbox").strip().lower()
NOTIFICATION_TO = os.getenv("SALUS_ADVISOR_NOTIFICATION_TO", "mduncan@salus.solutions").strip().lower()
NOTIFICATION_FROM = os.getenv("SALUS_ADVISOR_NOTIFICATION_FROM", "protectionadvisor@salus.solutions").strip().lower()
REQUIRE_EMAIL_VERIFICATION = os.getenv("SALUS_ADVISOR_REQUIRE_EMAIL_VERIFICATION", "0").strip() == "1"
ANSWER_STATES = {"Validated", "Documented", "Partially", "No", "Unknown", "Not Applicable", "Declined", "Answered"}
class AdvisorPerformanceEvent(BaseModel):
    model_config = ConfigDict(extra="forbid")
    duration_ms: int = Field(ge=0, le=120000)
    navigation_type: str = Field(default="navigate", pattern=r"^(navigate|reload|back_forward|prerender)$")


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


class NewAccountAssessmentCommand(BaseModel):
    model_config = ConfigDict(extra="forbid")
    organization_type: str

    @field_validator("organization_type")
    @classmethod
    def valid_org_type(cls, value: str) -> str:
        value = value.strip()
        if value not in ORGANIZATION_TYPES:
            raise ValueError("unsupported organization type")
        return value


class SelectAccountAssessmentCommand(BaseModel):
    model_config = ConfigDict(extra="forbid")
    session_key: str = Field(pattern=r"^SPA-SESSION-[A-F0-9]{32}$")


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
            "protected_member_code_name", "project_code_name", "handling_profile",
            "handling_authority", "designating_agency", "contract_reference",
            "dissemination_controls",
        }
        if set(value) - allowed:
            raise ValueError("unsupported draft field")
        if len(_json(value)) > 20000:
            raise ValueError("draft is too large")
        return value


class SubmitCommand(BaseModel):
    model_config = ConfigDict(extra="forbid")
    protected_member_code_name: str = Field(min_length=2, max_length=80)
    project_code_name: str = Field(min_length=2, max_length=80)
    handling_profile: str = Field(min_length=1, max_length=80)
    handling_authority: str = Field(default="", max_length=240)
    designating_agency: str = Field(default="", max_length=160)
    contract_reference: str = Field(default="", max_length=160)
    dissemination_controls: str = Field(default="", max_length=240)
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
        "protected_member_code_name", "project_code_name", "handling_profile",
        "handling_authority", "designating_agency", "contract_reference",
        "dissemination_controls", "organization_name", "contact_name", "contact_email", "facility_scope",
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

    @field_validator("handling_profile")
    @classmethod
    def valid_handling_profile(cls, value: str) -> str:
        if value not in HANDLING_PROFILES:
            raise ValueError("unsupported handling profile")
        return value

    @field_validator("protected_member_code_name", "project_code_name")
    @classmethod
    def valid_code_name(cls, value: str) -> str:
        if "@" in value or any(ch in value for ch in "/\\"):
            raise ValueError("code names must not contain email addresses or path separators")
        return value

    @field_validator("contact_email")
    @classmethod
    def email_shape(cls, value: str) -> str:
        value = value.casefold()
        if value.count("@") != 1 or "." not in value.rsplit("@", 1)[-1]:
            raise ValueError("enter a valid email address")
        return value


class ReportIdentityCommand(BaseModel):
    model_config = ConfigDict(extra="forbid")
    protected_member_code_name: str = Field(min_length=2, max_length=80)
    project_code_name: str = Field(min_length=2, max_length=80)
    handling_profile: str = Field(min_length=1, max_length=80)
    handling_authority: str = Field(default="", max_length=240)
    designating_agency: str = Field(default="", max_length=160)
    contract_reference: str = Field(default="", max_length=160)
    dissemination_controls: str = Field(default="", max_length=240)

    @field_validator(
        "protected_member_code_name", "project_code_name", "handling_profile",
        "handling_authority", "designating_agency", "contract_reference",
        "dissemination_controls",
    )
    @classmethod
    def clean(cls, value: str) -> str:
        value = value.strip()
        if any(ch in value for ch in "\r\n"):
            raise ValueError("line breaks are not permitted")
        return value

    @field_validator("handling_profile")
    @classmethod
    def valid_handling_profile(cls, value: str) -> str:
        if value not in HANDLING_PROFILES:
            raise ValueError("unsupported handling profile")
        return value

    @field_validator("protected_member_code_name", "project_code_name")
    @classmethod
    def valid_code_name(cls, value: str) -> str:
        if "@" in value or any(ch in value for ch in "/\\"):
            raise ValueError("code names must not contain email addresses or path separators")
        return value


class HandlingDecisionCommand(BaseModel):
    model_config = ConfigDict(extra="forbid")
    decision: str = Field(pattern=r"^(Approved|Rejected)$")
    handling_profile: str = Field(min_length=1, max_length=80)
    handling_authority: str = Field(default="", max_length=240)
    designating_agency: str = Field(default="", max_length=160)
    contract_reference: str = Field(default="", max_length=160)
    dissemination_controls: str = Field(default="", max_length=240)
    decision_note: str = Field(default="", max_length=500)

    @field_validator("handling_profile")
    @classmethod
    def valid_handling_profile(cls, value: str) -> str:
        if value not in HANDLING_PROFILES:
            raise ValueError("unsupported handling profile")
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
      last_login_at TEXT NOT NULL DEFAULT '',
      email_verified_at TEXT NOT NULL DEFAULT ''
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
    CREATE TABLE IF NOT EXISTS advisor_public_account_tokens (
      token_sha256 TEXT PRIMARY KEY,
      account_key TEXT NOT NULL,
      purpose TEXT NOT NULL,
      created_at TEXT NOT NULL,
      expires_at TEXT NOT NULL,
      used_at TEXT NOT NULL DEFAULT '',
      FOREIGN KEY (account_key) REFERENCES advisor_public_accounts(account_key) ON DELETE CASCADE
    );
    CREATE INDEX IF NOT EXISTS idx_advisor_account_tokens_account
      ON advisor_public_account_tokens(account_key,purpose,expires_at);
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
    CREATE TABLE IF NOT EXISTS advisor_public_report_identity_revisions (
      revision_key TEXT PRIMARY KEY,
      account_key TEXT NOT NULL,
      session_key TEXT NOT NULL,
      revision_no INTEGER NOT NULL,
      protected_member_code_name TEXT NOT NULL,
      project_code_name TEXT NOT NULL,
      handling_profile TEXT NOT NULL,
      handling_status TEXT NOT NULL,
      handling_authority TEXT NOT NULL DEFAULT '',
      designating_agency TEXT NOT NULL DEFAULT '',
      contract_reference TEXT NOT NULL DEFAULT '',
      dissemination_controls TEXT NOT NULL DEFAULT '',
      created_by TEXT NOT NULL,
      created_at TEXT NOT NULL,
      decision_note TEXT NOT NULL DEFAULT '',
      content_sha256 TEXT NOT NULL,
      FOREIGN KEY (account_key) REFERENCES advisor_public_accounts(account_key) ON DELETE CASCADE,
      FOREIGN KEY (session_key) REFERENCES advisor_public_sessions(session_key) ON DELETE CASCADE,
      UNIQUE(session_key,revision_no)
    );
    CREATE INDEX IF NOT EXISTS idx_advisor_report_identity_session
      ON advisor_public_report_identity_revisions(session_key,revision_no);
    """)
    initialize_engagement_schema(conn)


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
        raise HTTPException(401, "Part 2 account login is required")
    row = conn.execute(
        """SELECT s.*,a.email,a.email_verified_at,a.status account_status
             FROM advisor_public_account_sessions s
             JOIN advisor_public_accounts a ON a.account_key=s.account_key
            WHERE s.token_sha256=?""",
        (_sha(token),),
    ).fetchone()
    if not row or row["revoked_at"] or row["account_status"] != "Active":
        raise HTTPException(401, "Part 2 account session is unavailable")
    if row["expires_at"] <= _utc_text(_utc_now()):
        raise HTTPException(401, "Part 2 account session has expired")
    return row


def _require_account_assessment(conn: Any, account_key: str, session_key: str) -> Any:
    row = conn.execute(
        """SELECT * FROM advisor_public_account_assessments
            WHERE account_key=? AND session_key=?""",
        (account_key, session_key),
    ).fetchone()
    if not row or not row["detailed_assessment_acknowledged"] or not row["identifiable_retention_consent"]:
        raise HTTPException(403, "Part 2 acknowledgement and identifiable-information consent are required")
    return row


def _account_assessment_payload(conn: Any, account: Any, session: Any, csrf: str) -> dict[str, Any]:
    """Return one account-owned assessment without exposing another account's records."""
    _require_account_assessment(conn, account["account_key"], session["session_key"])
    payload: dict[str, Any] = {
        "authenticated": True,
        "email": account["email"],
        "csrf_token": csrf,
        "assessment_status": session["status"],
        "session_key": session["session_key"],
        "assessments": list_account_assessments(conn, account["account_key"]),
    }
    if session["status"] == "Submitted":
        retained = conn.execute(
            """SELECT s.submission_key,s.result_json,s.created_at,p.package_json
                 FROM advisor_public_submissions s
                 JOIN advisor_public_service_profiles p ON p.submission_key=s.submission_key
                WHERE s.session_key=?""",
            (session["session_key"],),
        ).fetchone()
        if not retained:
            raise HTTPException(409, "Submitted assessment results are unavailable")
        payload.update({
            "result": json.loads(retained["result_json"]),
            "package": json.loads(retained["package_json"]),
            "submitted_at": retained["created_at"],
            "result_reference": retained["submission_key"],
            "report_identity": _latest_report_identity(conn, session["session_key"]) or {},
        })
    else:
        draft = conn.execute(
            "SELECT draft_json FROM advisor_public_profile_drafts WHERE session_key=?",
            (session["session_key"],),
        ).fetchone()
        answers = _current_answers(conn, session["session_key"])
        payload.update({
            "questions": _questions(session["organization_type"]),
            "answers": {key: row["answer_state"] for key, row in answers.items()},
            "draft": json.loads(draft["draft_json"]) if draft else {},
        })
    return payload


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


def _handling_status(profile: str) -> str:
    return "Pending Salus Review" if profile in HANDLING_REVIEW_REQUIRED else "Approved by Default Policy"


def _latest_report_identity(conn: Any, session_key: str) -> dict[str, Any] | None:
    row = conn.execute(
        """SELECT * FROM advisor_public_report_identity_revisions
            WHERE session_key=? ORDER BY revision_no DESC LIMIT 1""",
        (session_key,),
    ).fetchone()
    return dict(row) if row else None


def _insert_report_identity(
    conn: Any,
    *,
    account_key: str,
    session_key: str,
    values: dict[str, Any],
    created_by: str,
    handling_status: str | None = None,
    decision_note: str = "",
) -> dict[str, Any]:
    latest = _latest_report_identity(conn, session_key)
    revision_no = int(latest["revision_no"]) + 1 if latest else 1
    payload = {
        "protected_member_code_name": values["protected_member_code_name"],
        "project_code_name": values["project_code_name"],
        "handling_profile": values["handling_profile"],
        "handling_status": handling_status or _handling_status(values["handling_profile"]),
        "handling_authority": values.get("handling_authority", ""),
        "designating_agency": values.get("designating_agency", ""),
        "contract_reference": values.get("contract_reference", ""),
        "dissemination_controls": values.get("dissemination_controls", ""),
        "revision_no": revision_no,
        "created_by": created_by,
        "created_at": _utc_text(_utc_now()),
        "decision_note": decision_note,
        "report_template_version": REPORT_TEMPLATE_VERSION,
    }
    conn.execute(
        """INSERT INTO advisor_public_report_identity_revisions
           (revision_key,account_key,session_key,revision_no,protected_member_code_name,
            project_code_name,handling_profile,handling_status,handling_authority,
            designating_agency,contract_reference,dissemination_controls,created_by,
            created_at,decision_note,content_sha256)
           VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
        (
            "SPA-IDENTITY-" + secrets.token_hex(16).upper(), account_key, session_key,
            revision_no, payload["protected_member_code_name"], payload["project_code_name"],
            payload["handling_profile"], payload["handling_status"],
            payload["handling_authority"], payload["designating_agency"],
            payload["contract_reference"], payload["dissemination_controls"],
            created_by, payload["created_at"], decision_note, _sha(_json(payload)),
        ),
    )
    return payload


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


def _salus_theme_css() -> str:
    """Shared Salus website heading, masthead, and action-link convention."""
    return """
:root{--blue:#427799;--ink:#1e242e;--orange:#cf5626;--line:#d8e0e6;--soft:#f7f9fa}*{box-sizing:border-box}
body{margin:0;background:#fff;color:var(--ink);font:18px/1.55 Georgia,"Times New Roman",serif}
main{max-width:1080px;margin:auto;padding:48px 32px 80px}
.salus-header{margin-bottom:62px}.salus-brand{display:flex;align-items:center;gap:16px;color:#000;text-decoration:none;font:400 30px/1.35 Arial,Helvetica,sans-serif;letter-spacing:.3px}
.salus-brand img{width:70px;height:70px;object-fit:contain}.salus-nav{display:flex;flex-wrap:wrap;gap:14px 26px;margin:28px 0 0}
.salus-nav a{color:var(--orange);text-decoration:none;font:400 18px/1.4 Arial,Helvetica,sans-serif;letter-spacing:.08em}.salus-nav a[aria-current=page]{color:var(--ink)}
h1,h2,h3{font-family:Arial,Helvetica,sans-serif;font-weight:300;color:var(--ink)}
h1{font-size:56px;line-height:1;color:var(--blue);margin:0 0 26px}h2{font-size:32px;line-height:1.4;margin:36px 0 20px}h3{font-size:28px;line-height:1.4;margin:28px 0 14px}
a{color:var(--orange)}a:hover,a:focus-visible{text-decoration:underline;text-underline-offset:4px}
@media(max-width:700px){main{padding:30px 20px 64px}.salus-header{margin-bottom:42px}.salus-brand{font-size:27px}.salus-brand img{width:60px;height:60px}.salus-nav{gap:12px 18px;margin-top:22px}.salus-nav a{font-size:16px}h1{font-size:42px;line-height:1.08}h2{font-size:29px}h3{font-size:25px}}
"""


def _salus_header() -> str:
    return """<header class="salus-header">
<a class="salus-brand" href="https://www.salus.solutions/"><img src="/static/salus-reticle.svg" alt="Salus Solutions reticle"><span>Salus Solutions</span></a>
<nav class="salus-nav" aria-label="Salus Solutions">
<a href="https://www.salus.solutions/">Home</a>
<a href="https://www.salus.solutions/how-salus-works">How Salus Works</a>
<a href="https://www.salus.solutions/protection-advisor" aria-current="page">Protection Advisor &gt;</a>
<a href="https://www.salus.solutions/salcapa">SalCAPA &gt;</a>
<a href="https://www.salus.solutions/salintel">SalINTEL &gt;</a>
<a href="https://www.salus.solutions/salthira">SalTHIRA &gt;</a>
<a href="https://www.salus.solutions/salops">SalOPS &gt;</a>
<a href="https://www.salus.solutions/about">About Salus</a>
<a href="https://www.salus.solutions/industries">Industries</a>
<a href="https://www.salus.solutions/insights">Insights and Library</a>
<a href="https://www.salus.solutions/payments">Payments</a>
<a href="https://www.salus.solutions/contact">Contact</a>
<a href="https://salcapa.salus.solutions/">Protected Member Login &gt;</a>
</nav></header>"""


def _verification_page() -> str:
    return f"""<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Email Verified | Protection Advisor</title><style>{_salus_theme_css()}</style></head><body><main>{_salus_header()}
<p class="eyebrow">Protection Advisor Account</p><h1>Email verified</h1>
<h2>Your Part 2 account is ready</h2><p>Your assessment and submitted results remain associated with your account under the consented retention policy. Security links and browser sessions expire; your retained assessment result does not expire with them.</p>
<p><a href="/protection-advisor">Return to Protection Advisor &gt;</a></p></main></body></html>"""


def _page(include_shell: bool = True) -> str:
    page_intro = ('<h1>Protection Advisor™</h1><p class="muted">Find Your Salus Package</p>' if include_shell else '<h1 class="visually-hidden">Protection Advisor</h1>')
    embed_css = "" if include_shell else "html,body{min-height:100%}main{padding-top:8px;padding-bottom:18px}#assessment h2{margin:10px 0 4px}#assessment>p{margin:4px 0}.question-progress{margin:8px 0 4px}.question{padding:9px 0}.choices{gap:8px 14px;margin-top:8px}.question-nav{position:sticky;bottom:0;z-index:10;background:#fff;border-top:1px solid var(--line);padding:8px 0;margin-top:8px}.assessment-important{font-size:.86rem;line-height:1.35;margin:7px 0;padding:7px 10px;border-left:3px solid var(--orange);background:var(--soft)}"
    options = "".join(f'<option value="{html.escape(item)}">{html.escape(item)}</option>' for item in sorted(ORGANIZATION_TYPES))
    activities = "".join(
        f'<label class="choice"><input type="checkbox" name="activity" value="{html.escape(item)}"> {html.escape(item)}</label>'
        for item in sorted(ACTIVITY_OPTIONS)
    )
    return """<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Protection Advisor | Salus Solutions</title>
<style>__SALUS_THEME__
button,label,select,input,textarea{font-family:Arial,Helvetica,sans-serif}.muted{color:#536675}.panel{border-top:1px solid var(--line);padding-top:24px;margin-top:28px}
label{display:block;font-weight:600;margin:18px 0 7px}label[hidden]{display:none!important}select,input[type=text],input[type=email],input[type=password],textarea{width:100%;font-size:1rem;padding:13px;border:1px solid #8d9aa3;border-radius:7px;min-height:48px}select{padding-right:38px;background-color:#fff}select:focus-visible,input:focus-visible,textarea:focus-visible{outline:3px solid var(--orange);outline-offset:2px}
textarea{min-height:100px}.check,.choice{display:flex;gap:12px;align-items:flex-start;font-family:Georgia,"Times New Roman",serif;font-weight:400}.check input,.choice input{margin-top:7px}
button,.action{border:0;background:none;color:var(--orange);font:1.05rem Arial,Helvetica,sans-serif;padding:14px 0;cursor:pointer;text-align:left;text-decoration:none;display:inline-block;margin-right:26px}
button:disabled{color:#888;cursor:not-allowed}.question{display:block;width:100%;min-width:0;margin:0;padding:20px 0;border:0;border-bottom:1px solid var(--line)}.question legend{font:700 1.12rem/1.45 Arial,Helvetica,sans-serif;color:var(--blue);padding:0}.choices{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:10px;margin-top:14px}
.choices label{display:flex;align-items:flex-start;gap:11px;font:400 1rem/1.4 Arial,Helvetica,sans-serif;margin:0;padding:13px 14px;border:1px solid #b9c7cf;border-radius:8px;background:#fff;cursor:pointer;min-height:52px}.choices label:hover{border-color:var(--blue);background:#f5f9fb}.choices label:has(input:checked){border-color:var(--blue);background:#edf5f9;box-shadow:inset 4px 0 var(--orange)}.choices input{width:18px;height:18px;margin:2px 0 0;flex:none;accent-color:var(--blue)}.choices label:focus-within{outline:3px solid var(--orange);outline-offset:2px}.profile-section{margin:30px 0 12px;padding-top:18px;border-top:1px solid var(--line);color:var(--blue)}.profile-choice-field{border:0;border-top:1px solid var(--line);margin:22px 0;padding:14px 0 0;min-width:0}.profile-choice-field legend{font:700 1rem/1.4 Arial,Helvetica,sans-serif;color:var(--blue);padding-right:8px}.profile-choice-field .choices{grid-template-columns:repeat(2,minmax(0,1fr))}.profile-choice-field .choices label{min-height:50px}@media(max-width:700px){.profile-choice-field .choices{grid-template-columns:1fr}}#profile>label{max-width:760px}#profile>label:has(textarea){max-width:920px}.question-progress{font:700 .8rem Arial,Helvetica,sans-serif;letter-spacing:.06em;text-transform:uppercase;color:var(--blue);margin:18px 0 8px}.question-nav{display:flex;gap:28px;align-items:center;flex-wrap:wrap;margin-top:18px}.question-nav button{margin:0}.hidden{display:none}.error{color:#a12612}.result{background:var(--soft);padding:24px;margin-top:24px}.route{border-left:3px solid var(--blue);padding:4px 20px;margin:28px 0}
.package-item{padding:16px 0;border-bottom:1px solid var(--line)}.eyebrow{font:700 .78rem Arial,Helvetica,sans-serif;letter-spacing:.08em;text-transform:uppercase;color:var(--blue)}
.visually-hidden{position:absolute!important;width:1px!important;height:1px!important;padding:0!important;margin:-1px!important;overflow:hidden!important;clip:rect(0,0,0,0)!important;white-space:nowrap!important;border:0!important}.handling-fields{border-left:3px solid var(--blue);padding-left:18px;margin:20px 0}.print-actions{margin-top:18px;border-top:1px solid var(--line);padding-top:12px}.print-meta{font:400 .82rem Arial,Helvetica,sans-serif;color:#536675;border-bottom:1px solid var(--line);padding-bottom:12px;margin-bottom:18px}.print-brand{display:flex;align-items:center;gap:12px;margin-bottom:18px;color:#000;font:400 24px Arial,Helvetica,sans-serif}.print-brand img{width:52px;height:52px}.print-report-title{font:300 28px Arial,Helvetica,sans-serif;color:var(--blue);margin:10px 0}.print-identifiers{font:400 14px/1.45 Arial,Helvetica,sans-serif}.print-classification{font-weight:700;color:#7b2d20}.print-watermark{display:none}.print-footer{font:400 11px Arial,Helvetica,sans-serif;border-top:1px solid #777;margin-top:28px;padding-top:8px;display:flex;justify-content:space-between;gap:12px}.print-confidential{font-weight:700;color:#7b2d20}@media(max-width:700px){.question-nav{gap:12px}.question-nav button{flex:1 1 150px}.choices{grid-template-columns:1fr}.choices label{min-height:48px}.print-actions button{width:100%;margin-right:0}}@media print{@page{size:letter;margin:.65in}.salus-header,.print-actions,.route,.action,body.print-part1 main>*:not(#result),body.print-part2 main>*:not(#package){display:none!important}body.print-part1 #result,body.print-part2 #package{display:block!important;background:#fff!important;padding:0!important;margin:0!important;color:#111!important}.print-watermark{display:block;position:fixed;top:38%;left:12%;transform:rotate(-48deg);font:700 76px Arial,Helvetica,sans-serif;color:rgba(90,90,90,.12);z-index:-1}.print-brand,.print-identifiers,.print-footer{break-inside:avoid}.package-item{break-inside:avoid}a{color:#111!important;text-decoration:none!important}}__EMBED_CSS__
</style></head><body><main>
__SALUS_HEADER__
__PAGE_INTRO__\n<p><a class="action" href="#accountAccess" onclick="openAccountLogin(event)">Return to Your Part 2 Assessment &gt;</a></p>
<h2>Part 1 — Anonymous Protection Readiness Review</h2>
<p>Learn what may deserve attention without providing your name, email address, or organization name. Your anonymous answers produce an immediate preliminary summary.</p>
<section id="start" class="panel">
<label for="orgType">Organization type</label><select id="orgType"><option value="">Select your organization type</option>__OPTIONS__</select>
<label class="check"><input id="primary" type="checkbox"> <span>I consent to Salus retaining my anonymous assessment answers to prepare this preliminary result. I understand I may delete this record from this session.</span></label>
<label class="check"><input id="secondary" type="checkbox"> <span>Optional: I permit Salus to derive separately reviewed, appropriately deidentified knowledge for protective research and service improvement.</span></label>
<button onclick="startAssessment()">Begin Your Anonymous Review &gt;</button><p id="startError" class="error"></p></section>
<section id="assessment" class="hidden"><h2>Your anonymous assessment</h2><p>You may choose Not Sure, Not Applicable, or Prefer Not to Answer.</p><aside class="assessment-important"><strong>Important notice:</strong> Protection Advisor provides preliminary educational and decision-support information. It is not an emergency reporting service, completed THIRA, professional security assessment, legal or insurance advice, or guarantee against loss. Salus professionals review information and evidence before issuing formal findings or proposals.</aside><p id="questionProgress" class="question-progress"></p><div id="questions"></div>
<div class="question-nav"><button id="previousQuestion" type="button" onclick="moveQuestion(-1)">Previous Question</button><button id="nextQuestion" type="button" onclick="moveQuestion(1)">Next Question</button><button id="reviewResults" class="hidden" type="button" onclick="preliminaryResult()">Review My Preliminary Results &gt;</button></div><p id="assessmentError" class="error"></p></section>
<section id="result" class="hidden result"></section>
<section id="paths" class="hidden panel"><h2>Choose what happens next</h2>
<p>Your anonymous review is complete. Continue for a tailored preliminary package or browse individual Salus services without identifying yourself.</p>
<div class="route"><a class="action" href="#profileAgreement" onclick="showProfileAgreement(event)">Continue to Your Tailored Salus Package &gt;</a><br>
<a class="action" href="https://salcapa.salus.solutions/protection-advisor/services" target="_blank" rel="noopener noreferrer">Explore Individual Salus Services &gt;</a></div></section>
<section id="profileAgreement" class="hidden panel"><p class="eyebrow">Before Part 2</p>
<h2>Understand the detailed assessment</h2>
<p>Part 2 asks more detailed and sometimes difficult questions about your organization, operations, capabilities, concerns, and priorities. Accurate answers are necessary for a useful preliminary package recommendation.</p>
<p>You do not need to conduct research or obtain new records before continuing. Answer truthfully from your current knowledge. When you do not know, select <strong>Not sure</strong> or <strong>Prefer to discuss with Salus</strong> where available rather than guessing.</p>
<label class="check"><input id="detailAck" type="checkbox"> <span>I understand that Part 2 is a detailed assessment and agree to answer truthfully from my current knowledge without guessing or overstating the organization’s capabilities.</span></label>
<label class="check"><input id="identifiableConsent" type="checkbox"> <span>I consent to Salus retaining the identifiable organization and contact information I provide in Part 2 with my assessment record for package preparation, professional review, and possible follow-up.</span></label>
<button onclick="confirmProfile()">I Understand — Continue to Part 2 &gt;</button><p id="profileAgreementError" class="error"></p></section>
<section id="accountAccess" class="hidden panel"><p class="eyebrow">Part 2 Account</p>
<h2>Create an account or sign in</h2>
<p>Your Part 2 account protects the confidential organization profile and lets you save your work, sign out, and return later. Submitted results remain available through your account while the record is retained. A 24-hour verification link or browser session is only a security credential; it does not delete or expire your assessment results.</p>
<div id="createAccountPanel"><h3>Create your account</h3>
<label>Email address<input id="accountEmail" type="email" maxlength="254" autocomplete="email"></label>
<label>Password<input id="accountPassword" type="password" minlength="12" maxlength="200" autocomplete="new-password"></label>
<label>Confirm password<input id="accountPasswordConfirm" type="password" minlength="12" maxlength="200" autocomplete="new-password"></label>
<p class="muted">Use at least 12 characters. Email verification and password recovery require the authorized Salus mail service.</p>
<button onclick="createAccount()">Create Account and Continue &gt;</button></div>
<div id="loginAccountPanel"><h3>Already have a Part 2 account?</h3>
<label>Email address<input id="loginEmail" type="email" maxlength="254" autocomplete="email"></label>
<label>Password<input id="loginPassword" type="password" minlength="12" maxlength="200" autocomplete="current-password"></label>
<button onclick="loginAccount()">Sign In and Resume &gt;</button>
<button onclick="requestPasswordReset()">Email Password-Reset Link &gt;</button></div>
<div id="resetPanel" class="hidden"><h3>Set a new password</h3>
<label>New password<input id="resetPassword" type="password" minlength="12" maxlength="200" autocomplete="new-password"></label>
<button onclick="resetAccountPassword()">Reset Password &gt;</button></div>
<p id="accountError" class="error"></p></section>
<section id="relationshipWorkspace" class="hidden panel"><p class="eyebrow">Protected Member Relationship</p>
<h2>Your assessments and engagements</h2>
<p>Manage separate assessments for different organizations, locations, projects, and functional areas under one Salus relationship. Each submitted assessment receives its own governed engagement and scope.</p>
<div id="assessmentList"></div>
<h3>Start another assessment</h3>
<label>Organization type<select id="additionalOrganizationType"><option value="">Select your organization type</option>__OPTIONS__</select></label>
<button type="button" onclick="startAdditionalAssessment()">Start New Assessment &gt;</button>
<p id="workspaceStatus" class="muted"></p></section>
<section id="profile" class="hidden panel"><p class="eyebrow">Part 2 — Confidential Organization and Service Profile</p>
<h2>Help us prepare your tailored preliminary package</h2>
<p>These candid questions help Salus understand scale, complexity, priorities, timing, and likely services. Identifying information is requested only because you elected to continue.</p>
<div class="handling-fields"><h3>Protected Member and project code names</h3>
<p>Create code names that do not disclose the Protected Member’s legal identity, a person’s name, an email address, or sensitive operational details. These names will appear on Part 2 results and remain in effect until an authorized account user changes them. The immutable report reference will not change.</p>
<label>Protected Member Code Name<input id="protectedMemberCodeName" type="text" minlength="2" maxlength="80" autocomplete="off"></label>
<label>Project Code Name<input id="projectCodeName" type="text" minlength="2" maxlength="80" autocomplete="off"></label>
<label>Requested report-handling profile<select id="handlingProfile"><option value="">Choose an option</option><option>Commercial Confidential</option><option>Government Sensitive</option><option>Federal CUI</option><option>Government Contractor CUI</option><option>Specialized Regulated Information</option></select></label>
<p class="muted">Selecting a government or regulated profile does not itself designate the report as CUI or another controlled category. Salus must review the stated authority before controlled markings are applied.</p>
<label>Handling authority or requirement<input id="handlingAuthority" type="text" maxlength="240" placeholder="Law, regulation, policy, contract clause, or other stated basis"></label>
<label>Designating or information-owning agency<input id="designatingAgency" type="text" maxlength="160"></label>
<label>Contract or task-order reference<input id="contractReference" type="text" maxlength="160"></label>
<label>Requested dissemination controls<input id="disseminationControls" type="text" maxlength="240" placeholder="Enter only authorized handling instructions"></label></div>
<h3 class="profile-section">1. Your organization</h3><label>Organization name<input id="organizationName" type="text" maxlength="160"></label>
<label>Your name<input id="contactName" type="text" maxlength="160"></label>
<label>Email address<input id="contactEmail" type="email" maxlength="254"></label>
<label>Facility scope<select id="facilityScope"><option value="">Choose an option</option><option>One facility</option><option>Several facilities</option><option>Organization-wide</option><option>Distributed, mobile, or remote operations</option><option>Not sure</option></select></label>
<label>Facility locations or general service area<textarea id="facilityLocations" maxlength="1500" placeholder="Provide addresses or general locations appropriate for this preliminary review. Do not provide access codes, floor plans, or sensitive security details."></textarea></label>
<label>Personnel and population range<select id="personnelRange"><option value="">Choose an option</option><option>1–25</option><option>26–100</option><option>101–500</option><option>501–2,500</option><option>2,501–10,000</option><option>More than 10,000</option><option>Varies significantly</option><option>Prefer to discuss with Salus</option></select></label>
<label>People who may be affected, served, present, or dependent on operations<select id="affectedPopulationRange"><option value="">Choose an option</option><option>1–25</option><option>26–100</option><option>101–500</option><option>501–2,500</option><option>2,501–10,000</option><option>More than 10,000</option><option>Varies significantly</option><option>Not sure</option><option>Prefer to discuss with Salus</option></select></label>
<label>Annual revenue or operating-budget range<select id="revenueRange"><option value="">Choose an option</option><option>Under $1 million</option><option>$1 million–$5 million</option><option>$5 million–$25 million</option><option>$25 million–$100 million</option><option>$100 million–$500 million</option><option>Over $500 million</option><option>Government or nonprofit operating budget</option><option>Prefer to discuss with Salus</option></select></label>
<h3 class="profile-section">2. Operations and continuity</h3><label>Activities and operating conditions that apply</label><div id="activities">__ACTIVITIES__</div>
<label>Essential products, services, or functions<textarea id="essentialFunctions" maxlength="1200"></textarea></label>
<label>Maximum tolerable interruption for the most essential function<select id="maximumTolerableDowntime"><option value="">Choose an option</option><option>Less than 4 hours</option><option>4–24 hours</option><option>1–3 days</option><option>4–7 days</option><option>More than 7 days</option><option>Not established</option><option>Not sure</option><option>Prefer to discuss with Salus</option></select></label>
<label>Current protection and preparedness program<select id="existingProgramMaturity"><option value="">Choose an option</option><option>Recently assessed, documented, and validated</option><option>Documented but not recently tested</option><option>Partially documented or inconsistently applied</option><option>Mostly informal</option><option>Little or no current program</option><option>Not sure</option><option>Prefer to discuss with Salus</option></select></label>
<label>Internal capacity to implement improvements<select id="internalImplementationCapacity"><option value="">Choose an option</option><option>Dedicated qualified team</option><option>Shared or part-time personnel</option><option>Limited internal capacity</option><option>Need Salus implementation support</option><option>Not sure</option><option>Prefer to discuss with Salus</option></select></label>
<h3 class="profile-section">3. What you need from Salus</h3><label>Primary outcome sought<select id="primaryObjective"><option value="">Choose an option</option><option>Independent assessment and priorities</option><option>Plans, procedures, and decision support</option><option>Facility or operational protection improvements</option><option>Training and exercises</option><option>Continuity and recovery capability</option><option>Protective intelligence and monitoring</option><option>Implementation assistance</option><option>Immediate incident or crisis support</option><option>Comprehensive protection program</option><option>Not sure</option></select></label>
<label>External requirement or decision driver<select id="externalRequirements"><option value="">Choose an option</option><option>Regulatory or statutory requirement</option><option>Contract or customer requirement</option><option>Insurance or underwriting concern</option><option>Board, executive, or governance requirement</option><option>Recent incident or credible concern</option><option>Future planning or budget decision</option><option>No known external requirement</option><option>Not sure</option><option>Prefer to discuss with Salus</option></select></label>
<label>Recent incidents, concerns, deadlines, or reasons for seeking assistance<textarea id="recentConcerns" maxlength="1200"></textarea></label>
<label>Desired timing<select id="desiredTiming"><option value="">Choose an option</option><option>Immediate concern</option><option>Within 30 days</option><option>Within 90 days</option><option>Within 6 months</option><option>Planning for a future budget cycle</option><option>Not sure</option></select></label>
<label>Who can authorize the next step?<input id="decisionAuthority" type="text" maxlength="160" placeholder="Role or decision group; a personal name is not required"></label>
<label>Potential investment range<select id="investmentRange"><option value="">Choose an option</option><option>Under $10,000</option><option>$10,000–$25,000</option><option>$25,000–$75,000</option><option>$75,000–$250,000</option><option>Over $250,000</option><option>Need phased options</option><option>Not established</option><option>Prefer to discuss with Salus</option></select></label>
<p class="muted">Do not enter passwords, financial account information, medical records, government identifiers, classified information, detailed hazardous-material inventories, access-control details, or information whose disclosure could create an immediate security risk.</p>
<p id="draftStatus" class="muted">Changes will be saved to your Part 2 account.</p><button onclick="saveDraft()">Save Progress &gt;</button><button onclick="logoutAccount()">Sign Out &gt;</button><br><button onclick="submitProfile()">Prepare My Tailored Preliminary Package &gt;</button><p id="submitError" class="error"></p></section>
<section id="package" class="hidden result"></section>
<section class="panel"><h2>Important notice</h2><p>Protection Advisor provides preliminary educational and decision-support information. It is not an emergency reporting service, completed THIRA, professional security assessment, legal or insurance advice, or guarantee against loss. Salus professionals review information, evidence, context, scope, recommendations, and pricing before issuing formal findings or proposals.</p></section>
</main><script>
let csrf="",questions=[],questionIndex=0,answerStates={},advisorResultReference="",reportIdentity={},accountEmailCurrent="";
async function call(path,opts={}){opts.headers={"Content-Type":"application/json",...(csrf?{"X-CSRF-Token":csrf}:{}),...(opts.headers||{})};const r=await fetch(path,opts);const data=await r.json().catch(()=>({detail:"Request failed"}));if(!r.ok){const detail=data.detail;const message=Array.isArray(detail)?detail.map(item=>item.msg||"Invalid value").join(" "):(typeof detail==="string"?detail:"Request failed");throw new Error(message)}return data}
async function startAssessment(){startError.textContent="";try{const data=await call("/public/protection-advisor/session",{method:"POST",body:JSON.stringify({organization_type:orgType.value,primary_consent:primary.checked,secondary_deidentified_consent:secondary.checked})});csrf=data.csrf_token;questions=data.questions;questionIndex=0;answerStates={};start.classList.add("hidden");assessment.classList.remove("hidden");renderQuestions();requestAnimationFrame(()=>window.scrollTo(0,0))}catch(x){startError.textContent=x.message}}
function answerLabel(s){return s==="Validated"?"Yes — recently tested":s==="Documented"?"Yes — documented, not recently tested":s==="Partially"?"Some parts are in place":s==="No"?"No — not in place":s==="Unknown"?"Not sure":s==="Not Applicable"?"Does not apply":s==="Declined"?"Prefer not to answer":s}
function renderQuestions(){if(!questions.length)return;const q=questions[questionIndex];questionProgress.textContent="Question "+(questionIndex+1)+" of "+questions.length;document.getElementById("questions").innerHTML='<fieldset class="question"><legend>'+(questionIndex+1)+'. '+escapeAdvisorHtml(q.text)+'</legend><div class="choices">'+["Validated","Documented","Partially","No","Unknown","Not Applicable","Declined"].map(s=>'<label><input type="radio" name="'+q.key+'" value="'+s+'" '+(answerStates[q.key]===s?"checked":"")+' onchange="saveAnswer(this.name,this.value)"> '+answerLabel(s)+'</label>').join("")+'</div></fieldset>';previousQuestion.disabled=questionIndex===0;nextQuestion.classList.toggle("hidden",questionIndex===questions.length-1);reviewResults.classList.toggle("hidden",questionIndex!==questions.length-1)}
function moveQuestion(delta){questionIndex=Math.max(0,Math.min(questions.length-1,questionIndex+delta));renderQuestions();requestAnimationFrame(()=>document.getElementById("assessment").scrollIntoView({block:"start",behavior:"smooth"}))}
async function saveAnswer(key,state){assessmentError.textContent="";answerStates[key]=state;try{await call("/public/protection-advisor/answer",{method:"POST",body:JSON.stringify({question_key:key,answer_state:state,note:""})})}catch(x){assessmentError.textContent=x.message}}
function escapeAdvisorHtml(value){return String(value||"").replace(/[&<>"']/g,ch=>({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"}[ch]))}
function handlingPresentation(identity){if(!identity||!identity.handling_profile)return {banner:"CONFIDENTIAL — SALUS PROTECTED INFORMATION",watermark:"CONFIDENTIAL",note:""};if(identity.handling_status==="Approved"||identity.handling_status==="Approved by Default Policy"){const cui=identity.handling_profile.includes("CUI");return {banner:cui?"CONTROLLED UNCLASSIFIED INFORMATION (CUI)":identity.handling_profile.toUpperCase(),watermark:cui?"CUI":"CONFIDENTIAL",note:""};}return {banner:"CONFIDENTIAL — SALUS PROTECTED INFORMATION",watermark:"CONFIDENTIAL",note:"Requested handling profile: "+identity.handling_profile+" — awaiting authorized Salus review."}}
function advisorPrintMeta(part,reference,confidential,identity={}){const handling=handlingPresentation(identity);const prepared=new Date().toLocaleString();const identifiers=confidential?'<div class="print-identifiers"><strong>Protected Member:</strong> '+escapeAdvisorHtml(identity.protected_member_code_name)+'<br><strong>Project:</strong> '+escapeAdvisorHtml(identity.project_code_name)+'<br><strong>Report Reference:</strong> '+escapeAdvisorHtml(reference)+'<br><strong>Prepared:</strong> '+escapeAdvisorHtml(prepared)+'<br><strong>Report Template:</strong> SPA-REPORT-TEMPLATE-1.1.0<br><span class="print-classification">'+escapeAdvisorHtml(handling.banner)+'</span>'+(handling.note?'<br>'+escapeAdvisorHtml(handling.note):'')+'</div>':'<div class="print-identifiers"><strong>Anonymous Report Reference:</strong> '+escapeAdvisorHtml(reference)+'<br><strong>Prepared:</strong> '+escapeAdvisorHtml(prepared)+'<br><strong>ANONYMOUS PRELIMINARY SUMMARY</strong></div>';return '<div class="print-meta"><div class="print-watermark">'+escapeAdvisorHtml(confidential?handling.watermark:"ANONYMOUS")+'</div><div class="print-brand"><img src="/static/salus-reticle.svg" alt=""><span>Salus Solutions</span></div><div class="print-report-title">Protection Advisor™ Assessment</div><strong>'+escapeAdvisorHtml(part)+'</strong>'+identifiers+'<p>This preliminary educational and decision-support output is not an emergency report, completed SalTHIRA™, professional certification, legal or insurance advice, or guarantee of safety.</p></div>'}
async function downloadAdvisorReport(){const status=document.getElementById("detailedReportStatus");if(status)status.textContent="Preparing your professional PDF…";try{const response=await fetch("/public/protection-advisor/report.pdf",{method:"GET",credentials:"same-origin",headers:{"X-CSRF-Token":csrf}});if(!response.ok){let message="Professional report download failed";try{const error=await response.json();if(error.detail)message=error.detail}catch(_){}throw new Error(message)}const blob=await response.blob();if(blob.type&&blob.type!=="application/pdf")throw new Error("The report service did not return a PDF");const disposition=response.headers.get("content-disposition")||"";const match=disposition.match(/filename="?([^";]+)"?/i);const filename=match?match[1]:"Salus-Protection-Advisor-Report.pdf";const url=URL.createObjectURL(blob);const link=document.createElement("a");link.href=url;link.download=filename;document.body.appendChild(link);link.click();link.remove();setTimeout(()=>URL.revokeObjectURL(url),1000);if(status)status.textContent="Professional PDF downloaded."}catch(error){if(status)status.textContent=error.message||"Professional report download failed"}}
function printAdvisor(scope){if(scope==="part2"){downloadAdvisorReport();return}document.body.classList.remove("print-part1","print-part2");document.body.classList.add("print-part1");window.print();setTimeout(()=>document.body.classList.remove("print-part1"),0)}
async function preliminaryResult(){assessmentError.textContent="";try{const data=await call("/public/protection-advisor/preliminary",{method:"POST",body:"{}"});const r=data.result;advisorResultReference=data.result_reference;assessment.classList.add("hidden");result.classList.remove("hidden");paths.classList.toggle("hidden",Boolean(accountEmailCurrent));result.innerHTML=advisorPrintMeta("Part 1 — Anonymous Preliminary Summary",advisorResultReference,false)+'<p class="eyebrow">Your Anonymous Preliminary Summary</p><h2>'+r.recommendation+'</h2><p>'+r.notice+'</p><p><strong>Potential attention areas:</strong> '+r.attention_count+'. <strong>Indicated strengths:</strong> '+r.strength_count+'. <strong>Information gaps:</strong> '+r.information_gap_count+'.</p><p>'+r.manual_next_step+'</p><div class="print-actions"><button type="button" onclick="printAdvisor(&quot;part1&quot;)">Print or Save Preliminary Summary &gt;</button></div><div class="print-footer">Salus Solutions · www.salus.solutions · '+escapeAdvisorHtml(advisorResultReference)+'</div>';if(accountEmailCurrent){showProfileForAccount(accountEmailCurrent,{})}else{result.scrollIntoView({behavior:"smooth"})}reportProtectionAdvisorHeight()}catch(x){assessmentError.textContent=x.message}}
function showProfileAgreement(event){event.preventDefault();profileAgreement.classList.remove("hidden");profileAgreement.scrollIntoView({behavior:"smooth"})}
function openAccountLogin(event){event.preventDefault();accountAccess.classList.remove("hidden");accountAccess.scrollIntoView({behavior:"smooth"})}
function confirmProfile(){profileAgreementError.textContent="";if(!detailAck.checked||!identifiableConsent.checked){profileAgreementError.textContent="Both acknowledgements are required before Part 2.";return}profileAgreement.classList.add("hidden");accountAccess.classList.remove("hidden");accountAccess.scrollIntoView({behavior:"smooth"})}
function showProfileForAccount(email,draft){accountEmailCurrent=email;detailAck.checked=true;identifiableConsent.checked=true;accountAccess.classList.add("hidden");contactEmail.value=email;contactEmail.readOnly=true;hydrateDraft(draft||{});profile.classList.remove("hidden");profile.scrollIntoView({behavior:"smooth"});enableAutosave()}
async function createAccount(){accountError.textContent="";try{if(accountPassword.value!==accountPasswordConfirm.value)throw new Error("Passwords do not match");const data=await call("/public/protection-advisor/account",{method:"POST",body:JSON.stringify({email:accountEmail.value,password:accountPassword.value,detailed_assessment_acknowledged:detailAck.checked,identifiable_retention_consent:identifiableConsent.checked})});showProfileForAccount(data.email,data.draft)}catch(x){accountError.textContent=x.message}}
function packageMarkup(p){return '<h2>'+p.title+'</h2><p>'+p.rationale+'</p>'+p.services.map(s=>'<div class="package-item"><h3>'+s.title+' — Level '+s.level+'</h3><p>'+s.summary+'</p><p><strong>Why this level:</strong> '+s.why+'</p><p><strong>Core capabilities addressed:</strong> '+s.capabilities.join(", ")+'</p></div>').join("")+(p.later_phase_services.length?'<h3>Possible later-phase services</h3><p>'+p.later_phase_services.map(s=>s.title+' — Level '+s.level).join("; ")+'</p>':'')+'<p><strong>Suggested sequence:</strong> '+p.sequence.join(" → ")+'</p><p>'+p.notice+'</p><a class="action" href="https://www.salus.solutions/contact">Discuss This Package With Salus &gt;</a>'}
function identityEditorMarkup(i){return '<details class="notice"><summary><strong>Update report code names or requested handling</strong></summary><p class="muted">Changes create a new immutable revision. A controlled-information request remains Confidential unless an authorized Salus reviewer approves the marking.</p><label>Protected Member Code Name<input id="retainedMemberCode" value="'+escapeAdvisorHtml(i.protected_member_code_name||"")+'" maxlength="80"></label><label>Project Code Name<input id="retainedProjectCode" value="'+escapeAdvisorHtml(i.project_code_name||"")+'" maxlength="80"></label><label>Requested report-handling profile<select id="retainedHandlingProfile">'+["Commercial Confidential","Government Sensitive","Federal CUI","Government Contractor CUI","Specialized Regulated Information"].map(v=>'<option'+(v===i.handling_profile?' selected':'')+'>'+v+'</option>').join("")+'</select></label><label>Handling authority<input id="retainedHandlingAuthority" value="'+escapeAdvisorHtml(i.handling_authority||"")+'" maxlength="240"></label><label>Designating agency<input id="retainedDesignatingAgency" value="'+escapeAdvisorHtml(i.designating_agency||"")+'" maxlength="160"></label><label>Contract or task-order reference<input id="retainedContractReference" value="'+escapeAdvisorHtml(i.contract_reference||"")+'" maxlength="160"></label><label>Dissemination controls<input id="retainedDisseminationControls" value="'+escapeAdvisorHtml(i.dissemination_controls||"")+'" maxlength="240"></label><button type="button" onclick="updateReportIdentity()">Save New Revision &gt;</button><p id="identityUpdateStatus" class="muted"></p></details>'}
async function updateReportIdentity(){const status=document.getElementById("identityUpdateStatus");status.textContent="Saving…";try{const data=await call("/public/protection-advisor/report-identity",{method:"POST",body:JSON.stringify({protected_member_code_name:retainedMemberCode.value,project_code_name:retainedProjectCode.value,handling_profile:retainedHandlingProfile.value,handling_authority:retainedHandlingAuthority.value,designating_agency:retainedDesignatingAgency.value,contract_reference:retainedContractReference.value,dissemination_controls:retainedDisseminationControls.value})});reportIdentity=data.report_identity;status.textContent="Revision "+reportIdentity.revision_no+" saved. Reloading the protected report.";setTimeout(()=>location.reload(),500)}catch(x){status.textContent=x.message}}
function showRetainedResults(data){accountAccess.classList.add("hidden");profile.classList.add("hidden");const r=data.result,p=data.package;advisorResultReference=data.result_reference;reportIdentity=data.report_identity||{};package.classList.remove("hidden");package.innerHTML=advisorPrintMeta("Part 2 — Detailed Results and Preliminary Package",advisorResultReference,true,reportIdentity)+'<p class="eyebrow">Your Retained Protection Advisor Results</p><p class="muted">Submitted '+new Date(data.submitted_at).toLocaleString()+'. Sign in whenever you need to review this retained record.</p><p><strong>'+escapeAdvisorHtml(r.recommendation)+'</strong></p><p>Potential attention areas: '+r.attention_count+'. Indicated strengths: '+r.strength_count+'. Information gaps: '+r.information_gap_count+'.</p>'+identityEditorMarkup(reportIdentity)+packageMarkup(p)+'<div class="print-actions"><button type="button" onclick="printAdvisor(&quot;part2&quot;)">Download Professional Detailed Report &gt;</button><p id="detailedReportStatus" class="muted" role="status" aria-live="polite"></p></div><div class="print-footer">Salus Solutions · www.salus.solutions · '+escapeAdvisorHtml(advisorResultReference)+'</div>';package.scrollIntoView({behavior:"smooth"});reportProtectionAdvisorHeight()}
function renderRelationshipWorkspace(data){accountEmailCurrent=data.email||accountEmailCurrent;relationshipWorkspace.classList.remove("hidden");const rows=data.assessments||[];assessmentList.innerHTML=rows.length?rows.map(a=>'<div class="package-item"><strong>'+escapeAdvisorHtml(a.engagement_name)+'</strong><br>'+escapeAdvisorHtml(a.organization_name)+' · '+escapeAdvisorHtml(a.functional_area)+'<br><span class="muted">'+escapeAdvisorHtml(a.organization_type)+' · '+escapeAdvisorHtml(a.status)+'</span><br><button type="button" data-session="'+escapeAdvisorHtml(a.session_key)+'" onclick="selectAccountAssessment(this.dataset.session)">Open This Assessment &gt;</button></div>').join(""):'<p>No assessments are available.</p>';reportProtectionAdvisorHeight()}
function showSelectedAssessment(data){csrf=data.csrf_token;questions=data.questions||[];answerStates=data.answers||{};questionIndex=0;detailAck.checked=true;identifiableConsent.checked=true;profile.classList.add("hidden");package.classList.add("hidden");assessment.classList.add("hidden");if(data.assessment_status==="Submitted"){showRetainedResults(data)}else if(questions.length){assessment.classList.remove("hidden");renderQuestions();assessment.scrollIntoView({behavior:"smooth"})}}
async function selectAccountAssessment(sessionKey){workspaceStatus.textContent="Opening assessment…";try{const data=await call("/public/protection-advisor/assessments/select",{method:"POST",body:JSON.stringify({session_key:sessionKey})});renderRelationshipWorkspace(data);showSelectedAssessment(data);workspaceStatus.textContent=""}catch(x){workspaceStatus.textContent=x.message}}
async function startAdditionalAssessment(){workspaceStatus.textContent="";if(!additionalOrganizationType.value){workspaceStatus.textContent="Select an organization type.";return}try{const data=await call("/public/protection-advisor/assessments",{method:"POST",body:JSON.stringify({organization_type:additionalOrganizationType.value})});renderRelationshipWorkspace(data);showSelectedAssessment(data);workspaceStatus.textContent="New assessment started. Its organization, locations, functional area, and engagement will be confirmed before submission."}catch(x){workspaceStatus.textContent=x.message}}
async function loginAccount(){accountError.textContent="";try{const data=await call("/public/protection-advisor/login",{method:"POST",body:JSON.stringify({email:loginEmail.value,password:loginPassword.value})});accountAccess.classList.add("hidden");accountEmailCurrent=data.email;renderRelationshipWorkspace(data);showSelectedAssessment(data)}catch(x){accountError.textContent=x.message}}
async function requestPasswordReset(){accountError.textContent="";try{await call("/public/protection-advisor/password-reset-request",{method:"POST",body:JSON.stringify({email:loginEmail.value})});accountError.textContent="If the account exists, a password-reset message has been requested."}catch(x){accountError.textContent=x.message}}
async function resetAccountPassword(){accountError.textContent="";try{const token=new URLSearchParams(location.search).get("reset_token")||"";await call("/public/protection-advisor/password-reset",{method:"POST",body:JSON.stringify({token:token,new_password:resetPassword.value})});accountError.textContent="Password reset. Sign in with the new password.";resetPanel.classList.add("hidden")}catch(x){accountError.textContent=x.message}}
function draftFields(){return {protected_member_code_name:protectedMemberCode.value,project_code_name:projectCode.value,handling_profile:handlingProfile.value,handling_authority:handlingAuthority.value,designating_agency:designatingAgency.value,contract_reference:contractReference.value,dissemination_controls:disseminationControls.value,organization_name:organizationName.value,contact_name:contactName.value,contact_email:contactEmail.value,facility_scope:facilityScope.value,facility_locations:facilityLocations.value,personnel_range:personnelRange.value,affected_population_range:affectedPopulationRange.value,annual_revenue_range:revenueRange.value,specific_activities:[...document.querySelectorAll('input[name="activity"]:checked')].map(x=>x.value),essential_functions:essentialFunctions.value,maximum_tolerable_downtime:maximumTolerableDowntime.value,existing_program_maturity:existingProgramMaturity.value,internal_implementation_capacity:internalImplementationCapacity.value,primary_objective:primaryObjective.value,external_requirements:externalRequirements.value,recent_concerns:recentConcerns.value,desired_timing:desiredTiming.value,decision_authority:decisionAuthority.value,investment_range:investmentRange.value}}
function hydrateDraft(d){const ids={protected_member_code_name:"protectedMemberCode",project_code_name:"projectCode",handling_profile:"handlingProfile",handling_authority:"handlingAuthority",designating_agency:"designatingAgency",contract_reference:"contractReference",dissemination_controls:"disseminationControls",organization_name:"organizationName",contact_name:"contactName",facility_scope:"facilityScope",facility_locations:"facilityLocations",personnel_range:"personnelRange",affected_population_range:"affectedPopulationRange",annual_revenue_range:"revenueRange",essential_functions:"essentialFunctions",maximum_tolerable_downtime:"maximumTolerableDowntime",existing_program_maturity:"existingProgramMaturity",internal_implementation_capacity:"internalImplementationCapacity",primary_objective:"primaryObjective",external_requirements:"externalRequirements",recent_concerns:"recentConcerns",desired_timing:"desiredTiming",decision_authority:"decisionAuthority",investment_range:"investmentRange"};Object.entries(ids).forEach(([k,id])=>{if(d[k]!==undefined)document.getElementById(id).value=d[k]});(d.specific_activities||[]).forEach(v=>{const el=[...document.querySelectorAll('input[name="activity"]')].find(x=>x.value===v);if(el)el.checked=true});syncAdvisorCardChoices()}
const advisorCardFieldIds=["facilityScope","existingProgramMaturity","internalImplementationCapacity","desiredTiming"];
function syncAdvisorCardChoices(){
  advisorCardFieldIds.forEach(id=>{
    const select=document.getElementById(id),group=document.getElementById(id+"Choices");
    if(!select||!group)return;
    group.querySelectorAll('input[type="radio"]').forEach(input=>{input.checked=input.value===select.value});
  });
}
function initAdvisorCardChoices(){
  advisorCardFieldIds.forEach(id=>{
    const select=document.getElementById(id);
    if(!select||document.getElementById(id+"Choices"))return;
    const sourceLabel=select.closest("label");
    const fieldset=document.createElement("fieldset");
    fieldset.id=id+"Choices";fieldset.className="profile-choice-field";
    const legend=document.createElement("legend");
    legend.textContent=sourceLabel.firstChild.textContent.trim();
    fieldset.appendChild(legend);
    const choices=document.createElement("div");choices.className="choices";
    [...select.options].filter(option=>option.value).forEach(option=>{
      const label=document.createElement("label"),radio=document.createElement("input");
      radio.type="radio";radio.name=id+"Choice";radio.value=option.value;
      radio.checked=option.value===select.value;
      radio.addEventListener("change",()=>{
        select.value=radio.value;
        select.dispatchEvent(new Event("change",{bubbles:true}));
      });
      label.append(radio,document.createTextNode(option.textContent));
      choices.appendChild(label);
    });
    fieldset.appendChild(choices);
    sourceLabel.after(fieldset);
    sourceLabel.hidden=true;
  });
  syncAdvisorCardChoices();
}
initAdvisorCardChoices();
let draftTimer=null;
function enableAutosave(){profile.querySelectorAll("input,select,textarea").forEach(el=>el.addEventListener("change",()=>{clearTimeout(draftTimer);draftTimer=setTimeout(saveDraft,500)}))}
async function saveDraft(){draftStatus.textContent="Saving…";try{const data=await call("/public/protection-advisor/draft",{method:"POST",body:JSON.stringify({fields:draftFields()})});draftStatus.textContent="Saved "+new Date(data.updated_at).toLocaleString()}catch(x){draftStatus.textContent="Draft not saved: "+x.message}}
async function logoutAccount(){try{await call("/public/protection-advisor/logout",{method:"POST",body:"{}"})}finally{location.reload()}}
async function submitProfile(){submitError.textContent="";try{const selected=[...document.querySelectorAll('input[name="activity"]:checked')].map(x=>x.value);const data=await call("/public/protection-advisor/submit",{method:"POST",body:JSON.stringify({protected_member_code_name:protectedMemberCode.value,project_code_name:projectCode.value,handling_profile:handlingProfile.value,handling_authority:handlingAuthority.value,designating_agency:designatingAgency.value,contract_reference:contractReference.value,dissemination_controls:disseminationControls.value,organization_name:organizationName.value,contact_name:contactName.value,contact_email:contactEmail.value,detailed_assessment_acknowledged:detailAck.checked,identifiable_retention_consent:identifiableConsent.checked,facility_scope:facilityScope.value,facility_locations:facilityLocations.value,personnel_range:personnelRange.value,affected_population_range:affectedPopulationRange.value,annual_revenue_range:revenueRange.value,specific_activities:selected,essential_functions:essentialFunctions.value,maximum_tolerable_downtime:maximumTolerableDowntime.value,existing_program_maturity:existingProgramMaturity.value,internal_implementation_capacity:internalImplementationCapacity.value,primary_objective:primaryObjective.value,external_requirements:externalRequirements.value,recent_concerns:recentConcerns.value,desired_timing:desiredTiming.value,decision_authority:decisionAuthority.value,investment_range:investmentRange.value})});profile.classList.add("hidden");const p=data.package;advisorResultReference=data.result_reference;reportIdentity=data.report_identity||{};package.classList.remove("hidden");package.innerHTML=advisorPrintMeta("Part 2 — Detailed Results and Preliminary Package",advisorResultReference,true,reportIdentity)+'<p class="eyebrow">Tailored Preliminary Salus Package</p>'+packageMarkup(p)+'<div class="print-actions"><button type="button" onclick="printAdvisor(&quot;part2&quot;)">Download Professional Detailed Report &gt;</button><p id="detailedReportStatus" class="muted" role="status" aria-live="polite"></p></div><div class="print-footer">Salus Solutions · www.salus.solutions · '+escapeAdvisorHtml(advisorResultReference)+'</div>';package.scrollIntoView({behavior:"smooth"});reportProtectionAdvisorHeight()}catch(x){submitError.textContent=x.message}}
const resetToken=new URLSearchParams(location.search).get("reset_token");if(resetToken){accountAccess.classList.remove("hidden");resetPanel.classList.remove("hidden");}
</script><script>
const reportProtectionAdvisorHeight=()=>{const height=Math.max(900,document.documentElement.scrollHeight,document.body.scrollHeight);window.parent.postMessage({type:"salus-protection-advisor-height",height:height,preferred_min_height:900,source:"protection-advisor"},"https://www.salus.solutions")};
const reportProtectionAdvisorLoad=()=>setTimeout(()=>{
  const nav=performance.getEntriesByType("navigation")[0];
  const payload=JSON.stringify({duration_ms:Math.max(0,Math.round((nav&&nav.loadEventEnd)||performance.now())),navigation_type:(nav&&nav.type)||"navigate"});
  const blob=new Blob([payload],{type:"application/json"});
  if(!navigator.sendBeacon("/public/protection-advisor/performance",blob)){
    fetch("/public/protection-advisor/performance",{method:"POST",headers:{"Content-Type":"application/json"},body:payload,keepalive:true}).catch(()=>{});
  }
},0);
new ResizeObserver(reportProtectionAdvisorHeight).observe(document.documentElement);
window.addEventListener("load",()=>{reportProtectionAdvisorHeight();reportProtectionAdvisorLoad()});
</script></body></html>""".replace("__OPTIONS__", options).replace("__ACTIVITIES__", activities).replace("__SALUS_THEME__", _salus_theme_css()).replace("__SALUS_HEADER__", _salus_header() if include_shell else "").replace("__PAGE_INTRO__", page_intro).replace("__EMBED_CSS__", embed_css)


def _service_catalog_page() -> str:
    items = "".join(
        f'<article class="service"><h2>{html.escape(title)}</h2><p>{html.escape(summary)}</p>'
        f'<a href="https://www.salus.solutions/contact">Discuss This Service With Salus &gt;</a></article>'
        for _, title, summary in SERVICE_CATALOG
    )
    return f"""<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Individual Salus Services | Protection Advisor</title><style>{_salus_theme_css()}
.service{{padding:20px 0;border-bottom:1px solid var(--line)}}.service h2{{margin-bottom:8px}}
</style></head><body><main>{_salus_header()}
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
        "rationale": "This preliminary package connects the capability conditions identified in Part 1 with the scale, consequences, activities, dependencies, maturity, timing, and implementation context supplied in Part 2.",
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
<title>Protection Advisor Review | Salus Solutions</title><style>{_salus_theme_css()}
main{{max-width:1180px}}table{{width:100%;border-collapse:collapse}}th,td{{padding:14px 12px;border-bottom:1px solid var(--line);text-align:left;vertical-align:top}}
th{{font:600 .85rem Arial,Helvetica,sans-serif;text-transform:uppercase}}.notice{{background:#f6f8fa;padding:14px 18px;border-left:3px solid var(--blue)}} .review-form label{{display:block;margin:12px 0;font-weight:600}} .review-form input,.review-form select,.review-form textarea{{display:block;width:100%;max-width:720px;margin-top:5px;padding:10px;border:1px solid var(--line);font:inherit}} .review-form span{{font-weight:400;color:#555}}
@media(max-width:760px){{table,thead,tbody,tr,th,td{{display:block}}thead{{display:none}}tr{{margin:18px 0;border:1px solid var(--line)}}}}
</style></head><body><main>{_salus_header()}
<h1>Protection Advisor Review</h1><p class="notice">Authorized Salus review workspace. Prospect records remain separate from Protected Member tenant records until an authorized person completes the governed intake decision.</p>
<table><thead><tr><th>Submitted</th><th>Organization</th><th>Contact</th><th>Recommendation</th><th>Status</th><th>Notification</th></tr></thead><tbody>{rows_html}</tbody></table>
<p><a href="/">&lt; SalCAPA Command Center</a></p></main></body></html>"""


def _review_detail(row: dict[str, Any], identity: dict[str, Any] | None = None) -> str:
    result = json.loads(row["result_json"])
    identity = identity or {}
    identity_html = (
        "<h2>Report identity and handling</h2><p class='notice'>"
        f"<strong>Protected Member:</strong> {html.escape(identity.get('protected_member_code_name','Not assigned'))}<br>"
        f"<strong>Project:</strong> {html.escape(identity.get('project_code_name','Not assigned'))}<br>"
        f"<strong>Requested profile:</strong> {html.escape(identity.get('handling_profile','Not assigned'))}<br>"
        f"<strong>Review status:</strong> {html.escape(identity.get('handling_status','Not assigned'))}<br>"
        f"<strong>Revision:</strong> {int(identity.get('revision_no',0))}</p>"
    )
    profile_options = "".join(
        f"<option value='{html.escape(profile)}' "
        + ("selected" if profile == identity.get("handling_profile") else "")
        + f">{html.escape(profile)}</option>"
        for profile in sorted(HANDLING_PROFILES)
    )
    handling_action_html = ""
    if identity.get("handling_status") != "Approved":
        handling_action_html = f"""
        <h2>Approve report handling</h2>
        <form id="handling-form" class="review-form">
          <label>Handling profile<select name="handling_profile">{profile_options}</select></label>
          <label>Handling authority <span>(required for CUI)</span><input name="handling_authority" value="{html.escape(str(identity.get('handling_authority') or ''))}"></label>
          <label>Designating agency <span>(required for CUI)</span><input name="designating_agency" value="{html.escape(str(identity.get('designating_agency') or ''))}"></label>
          <label>Contract reference<input name="contract_reference" value="{html.escape(str(identity.get('contract_reference') or ''))}"></label>
          <label>Dissemination controls<input name="dissemination_controls" value="{html.escape(str(identity.get('dissemination_controls') or ''))}"></label>
          <label>Decision note<textarea name="decision_note"></textarea></label>
          <input type="hidden" name="decision" value="Approved">
          <button type="submit">Approve report handling</button>
        </form>
        <p id="handling-status" role="status"></p>
        <script>
        document.getElementById("handling-form").addEventListener("submit", async (event) => {{
          event.preventDefault();
          const form = event.currentTarget;
          const status = document.getElementById("handling-status");
          status.textContent = "Saving approval...";
          const response = await fetch("/api/protection-advisor/review/{html.escape(str(row['submission_key']))}/handling", {{
            method: "POST",
            headers: {{"Content-Type": "application/json"}},
            body: JSON.stringify(Object.fromEntries(new FormData(form))),
          }});
          if (!response.ok) {{
            status.textContent = "Approval failed: " + await response.text();
            return;
          }}
          location.reload();
        }});
        </script>
        """

    report_action_html = (
        "<h2>Governed report artifact</h2>"
        "<form method='post' action='/api/protection-advisor/review/"
        + html.escape(str(row["submission_key"]))
        + "/report'><button type='submit'>Generate governed DOCX and PDF in SharePoint</button></form>"
        if identity.get("handling_status") == "Approved"
        else "<h2>Governed report artifact</h2><p class='notice'>Approve report handling before generating the governed DOCX and PDF.</p>"
    )
    answers = json.loads(row["answer_snapshot_json"])
    answer_rows = "".join(
        f"<tr><td>{html.escape(key.replace('_',' ').title())}</td><td>{html.escape(str(value.get('answer_state','')))}</td></tr>"
        for key, value in answers.items()
    )
    return f"""<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Protection Advisor Submission | Salus Solutions</title><style>{_salus_theme_css()}
main{{max-width:960px}}table{{width:100%;border-collapse:collapse}}td{{padding:11px;border-bottom:1px solid var(--line);vertical-align:top}}
.notice{{background:#f6f8fa;padding:14px 18px;border-left:3px solid var(--blue)}}</style></head><body><main>
{_salus_header()}
<p><a href="/protection-advisor/review">&lt; All submissions</a></p><h1>{html.escape(row['organization_name'])}</h1>
<p><strong>Contact:</strong> {html.escape(row['contact_name'])} · <a href="mailto:{html.escape(row['contact_email'])}">{html.escape(row['contact_email'])}</a><br>
<strong>Submitted:</strong> {html.escape(row['created_at'])}<br><strong>Status:</strong> {html.escape(row['status'])}</p>
{identity_html}
{handling_action_html}
{report_action_html}
<h2>Preliminary result</h2><p class="notice"><strong>{html.escape(result.get('recommendation',''))}</strong><br>{html.escape(result.get('notice',''))}</p>
<p>Potential attention areas: {int(result.get('attention_count',0))}. Information gaps: {int(result.get('information_gap_count',0))}.</p>
<h2>Assessment answers</h2><table>{answer_rows}</table></main></body></html>"""


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

    @app.post("/public/protection-advisor/performance", status_code=204)
    def protection_advisor_performance(request: Request, event: AdvisorPerformanceEvent) -> Response:
        limited(request)
        emit_telemetry(
            "protection_advisor_page_load",
            duration_ms=event.duration_ms,
            navigation_type=event.navigation_type,
            embedded=True,
        )
        return Response(status_code=204)

    @app.get("/protection-advisor/services", response_class=HTMLResponse)
    def protection_advisor_services() -> HTMLResponse:
        return HTMLResponse(_service_catalog_page(), headers={"Cache-Control": "no-store", "X-Frame-Options": "DENY", "Referrer-Policy": "no-referrer"})

    @app.get("/protection-advisor/embed", response_class=HTMLResponse)
    def protection_advisor_embed() -> HTMLResponse:
        return HTMLResponse(_page(include_shell=False), headers={"Cache-Control": "no-store", "Referrer-Policy": "no-referrer", "Content-Security-Policy": "default-src 'self'; style-src 'unsafe-inline'; script-src 'unsafe-inline'; connect-src 'self'; frame-ancestors https://www.salus.solutions https://salus.solutions; base-uri 'none'; form-action 'self'"})

    @app.get("/protection-advisor")
    def protection_advisor_page() -> RedirectResponse:
        return RedirectResponse(
            "https://www.salus.solutions/protection-advisor",
            status_code=307,
            headers={"Cache-Control": "no-store"},
        )

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
            identity = _latest_report_identity(conn, row["session_key"])
            return HTMLResponse(_review_detail(dict(row), identity), headers={"Cache-Control": "no-store", "X-Frame-Options": "DENY"})
        finally:
            conn.close()

    @app.post("/api/protection-advisor/review/{submission_key}/handling")
    def decide_protection_advisor_handling(
        submission_key: str, command: HandlingDecisionCommand, request: Request
    ) -> dict[str, Any]:
        ctx["require"](request, "admin")
        conn = ctx["db"]()
        try:
            submission = conn.execute(
                "SELECT session_key FROM advisor_public_submissions WHERE submission_key=?",
                (submission_key,),
            ).fetchone()
            if not submission:
                raise HTTPException(404, "Submission not found")
            latest = _latest_report_identity(conn, submission["session_key"])
            if not latest:
                raise HTTPException(409, "Report identity is unavailable")
            if (
                command.decision == "Approved"
                and command.handling_profile in {"Federal CUI", "Government Contractor CUI"}
                and (not command.handling_authority or not command.designating_agency)
            ):
                raise HTTPException(400, "Approved CUI handling requires an authority and designating agency")
            values = dict(latest)
            values.update(command.model_dump())
            status = "Approved" if command.decision == "Approved" else "Rejected"
            report_identity = _insert_report_identity(
                conn,
                account_key=latest["account_key"],
                session_key=submission["session_key"],
                values=values,
                created_by="Salus Reviewer",
                handling_status=status,
                decision_note=command.decision_note,
            )
            conn.execute(
                "INSERT INTO advisor_public_lifecycle_events VALUES(?,?,?,?,?)",
                ("SPA-EVENT-"+secrets.token_hex(16).upper(), submission["session_key"],
                 "Report Handling "+status, report_identity["created_at"],
                 _sha(_json({"revision_no": report_identity["revision_no"], "profile": report_identity["handling_profile"]}))),
            )
            conn.commit()
            return {"report_identity": report_identity}
        finally:
            conn.close()

    @app.post("/api/protection-advisor/review/{submission_key}/report")
    def prepare_protection_advisor_review_report(submission_key: str, request: Request) -> dict[str, Any]:
        """Prepare the branded DOCX only for an authenticated Salus reviewer."""
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
            identity = _latest_report_identity(conn, row["session_key"])
            if not identity or identity.get("handling_status") != "Approved":
                raise HTTPException(409, "Report handling must be approved before DOCX preparation")
            session = conn.execute(
                "SELECT organization_type FROM advisor_public_sessions WHERE session_key=?",
                (row["session_key"],),
            ).fetchone()
            profile_row = conn.execute(
                "SELECT profile_json, package_json FROM advisor_public_service_profiles WHERE submission_key=?",
                (submission_key,),
            ).fetchone()
            if not session or not profile_row:
                raise HTTPException(409, "Assessment profile is unavailable")
            profile = json.loads(profile_row["profile_json"])
            package = json.loads(profile_row["package_json"])
            result = json.loads(row["result_json"])
            artifact = prepare_review_artifact(
                template_path=None,
                output_dir=None,
                identity=dict(identity),
                organization_type=session["organization_type"],
                public_service_role=str(profile.get("external_requirements") or "Not provided"),
                assessment_authority=str(profile.get("decision_authority") or "Not provided"),
                part1_text=json.dumps(result, sort_keys=True, indent=2),
                part2_text=json.dumps(package, sort_keys=True, indent=2),
                report_reference="SPA-REPORT-" + submission_key.removeprefix("SPA-SUBMISSION-"),
                generated_at=_utc_now(),
            )
            storage = {"status": "Not Configured", "review_required": True}
            if artifact.get("status") == "Prepared for Salus Review":
                artifact_path = os.path.join(
                    os.getenv("SALUS_ADVISOR_REPORT_OUTPUT_DIR", ""),
                    "SPA-REPORT-" + submission_key.removeprefix("SPA-SUBMISSION-") + ".docx",
                )
                storage = publish_advisor_docx(
                    artifact_path,
                    "SPA-REPORT-" + submission_key.removeprefix("SPA-SUBMISSION-"),
                )
            return {"submission_key": submission_key, "artifact": artifact, "storage": storage}
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
            verification_token = secrets.token_urlsafe(32)
            conn.execute(
                """INSERT INTO advisor_public_account_tokens
                   (token_sha256,account_key,purpose,created_at,expires_at,used_at)
                   VALUES(?,?,?,?,?,?)""",
                (_sha(verification_token), account_key, "Verify Email", _utc_text(now),
                 _utc_text(now + timedelta(hours=24)), ""),
            )
            conn.execute(
                "INSERT INTO advisor_public_lifecycle_events VALUES(?,?,?,?,?)",
                ("SPA-EVENT-" + secrets.token_hex(16).upper(), session["session_key"],
                 "Part 2 Account Created", _utc_text(now),
                 _sha(_json({"account_key": account_key, "email": command.email}))),
            )
            conn.commit()
            verification_url = (
                str(request.base_url).rstrip("/")
                + "/protection-advisor/verify-email?token="
                + verification_token
            )
            delivered, delivery_error = await _send_graph_email(
                command.email,
                "Verify your Salus Protection Advisor account",
                "Verify your Protection Advisor Part 2 account within 24 hours:\n\n"
                + verification_url
                + "\n\nIf you did not create this account, do not use this link.",
            )
            response = JSONResponse({
                "authenticated": True,
                "email": command.email,
                "draft": {},
                "email_verification": "Delivered" if delivered else "Pending",
                "email_verification_error": delivery_error,
            })
            response.set_cookie(
                "salus_advisor_account", account_token, httponly=True,
                secure=ctx.get("COOKIE_SECURE", True), samesite="strict",
                max_age=30 * 24 * 3600, path="/",
            )
            return response
        finally:
            conn.close()

    @app.get("/protection-advisor/verify-email", response_class=HTMLResponse)
    async def verify_protection_advisor_email(token: str, request: Request) -> HTMLResponse:
        conn = ctx["db"]()
        try:
            _initialize(conn)
            row = conn.execute(
                """SELECT t.*,a.email FROM advisor_public_account_tokens t
                   JOIN advisor_public_accounts a ON a.account_key=t.account_key
                  WHERE t.token_sha256=? AND t.purpose='Verify Email'""",
                (_sha(token),),
            ).fetchone()
            now = _utc_text(_utc_now())
            if not row or row["used_at"] or row["expires_at"] <= now:
                raise HTTPException(400, "Verification link is invalid or expired")
            conn.execute(
                "UPDATE advisor_public_accounts SET email_verified_at=? WHERE account_key=?",
                (now, row["account_key"]),
            )
            conn.execute(
                "UPDATE advisor_public_account_tokens SET used_at=? WHERE token_sha256=?",
                (now, _sha(token)),
            )
            conn.commit()
            return HTMLResponse(
                _verification_page(),
                headers={"Cache-Control": "no-store", "Referrer-Policy": "no-referrer"},
            )
        finally:
            conn.close()

    @app.post("/public/protection-advisor/password-reset-request")
    async def request_protection_advisor_password_reset(
        command: PasswordResetRequestCommand, request: Request
    ) -> dict[str, Any]:
        limited(request, command.email)
        conn = ctx["db"]()
        try:
            _initialize(conn)
            account = conn.execute(
                "SELECT * FROM advisor_public_accounts WHERE email=? AND status='Active'",
                (command.email,),
            ).fetchone()
            if account:
                now = _utc_now()
                token = secrets.token_urlsafe(32)
                conn.execute(
                    """INSERT INTO advisor_public_account_tokens
                       (token_sha256,account_key,purpose,created_at,expires_at,used_at)
                       VALUES(?,?,?,?,?,?)""",
                    (_sha(token), account["account_key"], "Reset Password", _utc_text(now),
                     _utc_text(now + timedelta(hours=1)), ""),
                )
                conn.commit()
                reset_url = (
                    str(request.base_url).rstrip("/")
                    + "/protection-advisor?reset_token="
                    + token
                )
                await _send_graph_email(
                    command.email,
                    "Reset your Salus Protection Advisor password",
                    "Use this link within one hour to reset your Protection Advisor password:\n\n"
                    + reset_url
                    + "\n\nIf you did not request this, no action is required.",
                )
            return {"accepted": True}
        finally:
            conn.close()

    @app.post("/public/protection-advisor/password-reset")
    async def reset_protection_advisor_password(
        command: PasswordResetCommand, request: Request
    ) -> dict[str, Any]:
        limited(request, command.token)
        conn = ctx["db"]()
        try:
            now = _utc_text(_utc_now())
            row = conn.execute(
                """SELECT * FROM advisor_public_account_tokens
                    WHERE token_sha256=? AND purpose='Reset Password'""",
                (_sha(command.token),),
            ).fetchone()
            if not row or row["used_at"] or row["expires_at"] <= now:
                raise HTTPException(400, "Password-reset link is invalid or expired")
            salt = secrets.token_hex(16)
            conn.execute(
                """UPDATE advisor_public_accounts
                      SET password_salt=?,password_hash=? WHERE account_key=?""",
                (salt, _password_hash(command.new_password, salt), row["account_key"]),
            )
            conn.execute(
                "UPDATE advisor_public_account_tokens SET used_at=? WHERE token_sha256=?",
                (now, _sha(command.token)),
            )
            conn.execute(
                "UPDATE advisor_public_account_sessions SET revoked_at=? WHERE account_key=? AND revoked_at=''",
                (now, row["account_key"]),
            )
            conn.commit()
            return {"reset": True}
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
                  WHERE aa.account_key=? AND s.status IN ('Active','Submitted') AND s.deleted_at=''
                  ORDER BY aa.acknowledged_at DESC LIMIT 1""",
                (account["account_key"],),
            ).fetchone()
            if not linked:
                raise HTTPException(404, "No resumable Part 2 assessment is available")
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
            retained = None
            if linked["status"] == "Submitted":
                retained = conn.execute(
                    """SELECT s.submission_key,s.result_json,s.created_at,p.package_json
                         FROM advisor_public_submissions s
                         JOIN advisor_public_service_profiles p ON p.submission_key=s.submission_key
                        WHERE s.session_key=?""",
                    (linked["session_key"],),
                ).fetchone()
                if not retained:
                    raise HTTPException(409, "Submitted assessment results are unavailable")
            conn.commit()
            payload: dict[str, Any] = {
                "authenticated": True,
                "email": account["email"],
                "csrf_token": csrf,
                "assessment_status": linked["status"],
                "assessments": list_account_assessments(conn, account["account_key"]),
            }
            if retained:
                payload.update({
                    "result": json.loads(retained["result_json"]),
                    "package": json.loads(retained["package_json"]),
                    "submitted_at": retained["created_at"],
                    "result_reference": retained["submission_key"],
                    "report_identity": _latest_report_identity(conn, linked["session_key"]) or {},
                })
            else:
                payload.update({
                    "questions": _questions(linked["organization_type"]),
                    "answers": {key: row["answer_state"] for key, row in answers.items()},
                    "draft": json.loads(draft["draft_json"]) if draft else {},
                })
            response = JSONResponse(payload)
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

    @app.get("/public/protection-advisor/assessments")
    async def list_protection_advisor_assessments(request: Request) -> dict[str, Any]:
        limited(request, request.cookies.get("salus_advisor_account", ""))
        conn = ctx["db"]()
        try:
            _initialize(conn)
            account = _account_session(conn, request)
            return {"assessments": list_account_assessments(conn, account["account_key"])}
        finally:
            conn.close()

    @app.post("/public/protection-advisor/assessments")
    async def create_protection_advisor_assessment(
        command: NewAccountAssessmentCommand, request: Request
    ) -> JSONResponse:
        """Start another assessment under the signed-in prospective relationship."""
        limited(request, request.cookies.get("salus_advisor_account", ""))
        conn = ctx["db"]()
        try:
            _initialize(conn)
            account = _account_session(conn, request)
            current_session, _ = _session(conn, request)
            _require_account_assessment(
                conn, account["account_key"], current_session["session_key"]
            )
            now = _utc_now()
            session_key = "SPA-SESSION-" + secrets.token_hex(16).upper()
            advisor_token = secrets.token_urlsafe(32)
            csrf = secrets.token_urlsafe(24)
            conn.execute(
                """INSERT INTO advisor_public_sessions
                (session_key,token_sha256,csrf_sha256,organization_type,primary_consent,
                 secondary_deidentified_consent,consent_notice_version,retention_policy_version,
                 questionnaire_version,status,created_at,expires_at)
                 VALUES(?,?,?,?,?,?,?,?,?,?,?,?)""",
                (session_key, _sha(advisor_token), _sha(csrf), command.organization_type, 1, 0,
                 CONSENT_NOTICE_VERSION, RETENTION_POLICY_VERSION, QUESTIONNAIRE_VERSION,
                 "Active", _utc_text(now), _utc_text(now + timedelta(hours=SESSION_HOURS))),
            )
            conn.execute(
                """INSERT INTO advisor_public_account_assessments
                   (account_key,session_key,detailed_assessment_acknowledged,
                    identifiable_retention_consent,acknowledged_at)
                   VALUES(?,?,?,?,?)""",
                (account["account_key"], session_key, 1, 1, _utc_text(now)),
            )
            conn.execute(
                "INSERT INTO advisor_public_lifecycle_events VALUES(?,?,?,?,?)",
                ("SPA-EVENT-" + secrets.token_hex(16).upper(), session_key,
                 "Additional Assessment Started", _utc_text(now),
                 _sha(_json({"organization_type": command.organization_type}))),
            )
            session = conn.execute(
                "SELECT * FROM advisor_public_sessions WHERE session_key=?", (session_key,)
            ).fetchone()
            conn.commit()
            response = JSONResponse(_account_assessment_payload(conn, account, session, csrf))
            response.set_cookie(
                "salus_advisor_session", advisor_token, httponly=True,
                secure=ctx.get("COOKIE_SECURE", True), samesite="strict",
                max_age=SESSION_HOURS * 3600, path="/",
            )
            return response
        finally:
            conn.close()

    @app.post("/public/protection-advisor/assessments/select")
    async def select_protection_advisor_assessment(
        command: SelectAccountAssessmentCommand, request: Request
    ) -> JSONResponse:
        """Select one account-owned assessment and rotate its browser credentials."""
        limited(request, request.cookies.get("salus_advisor_account", ""))
        conn = ctx["db"]()
        try:
            _initialize(conn)
            account = _account_session(conn, request)
            current_session, _ = _session(conn, request)
            _require_account_assessment(
                conn, account["account_key"], current_session["session_key"]
            )
            _require_account_assessment(conn, account["account_key"], command.session_key)
            session = conn.execute(
                """SELECT * FROM advisor_public_sessions
                    WHERE session_key=? AND status IN ('Active','Submitted') AND deleted_at=''""",
                (command.session_key,),
            ).fetchone()
            if not session:
                raise HTTPException(404, "Assessment is unavailable")
            now = _utc_now()
            advisor_token = secrets.token_urlsafe(32)
            csrf = secrets.token_urlsafe(24)
            conn.execute(
                """UPDATE advisor_public_sessions SET token_sha256=?,csrf_sha256=?,expires_at=?
                    WHERE session_key=?""",
                (_sha(advisor_token), _sha(csrf), _utc_text(now + timedelta(hours=SESSION_HOURS)),
                 command.session_key),
            )
            conn.commit()
            response = JSONResponse(_account_assessment_payload(conn, account, session, csrf))
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
            return {"anonymous": True, "result_reference": "SPA-ANON-" + _sha(session["session_key"])[:12].upper(), "result": _result(questions, answers)}
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
                raise HTTPException(400, "Part 2 acknowledgement and retention consent are required")
            if REQUIRE_EMAIL_VERIFICATION and not account["email_verified_at"]:
                raise HTTPException(403, "Verify the Part 2 account email before submitting")
            if command.contact_email != account["email"]:
                raise HTTPException(400, "Contact email must match the signed-in Part 2 account")
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
                "protected_member_code_name": command.protected_member_code_name,
                "project_code_name": command.project_code_name,
                "handling_profile": command.handling_profile,
                "handling_authority": command.handling_authority,
                "designating_agency": command.designating_agency,
                "contract_reference": command.contract_reference,
                "dissemination_controls": command.dissemination_controls,
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
            report_identity = _insert_report_identity(
                conn,
                account_key=account["account_key"],
                session_key=session["session_key"],
                values=command.model_dump(),
                created_by="Protected Member Account",
            )
            engagement_scope = create_assessment_scope(
                conn,
                account_key=account["account_key"],
                session_key=session["session_key"],
                organization_name=command.organization_name,
                organization_type=session["organization_type"],
                project_name=command.project_code_name,
                location_description=command.facility_locations or command.facility_scope,
                functional_area=command.primary_objective,
                objective=command.primary_objective,
                created_at=created,
            )
            profile["organization_name"] = command.organization_name
            profile["engagement_scope"] = engagement_scope
            conn.execute(
                """UPDATE advisor_public_service_profiles
                      SET profile_json=?,profile_sha256=? WHERE submission_key=?""",
                (_json(profile), _sha(_json(profile)), submission_key),
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
                f"Protected Member code: {command.protected_member_code_name}\n"
                f"Project code: {command.project_code_name}\n"
                f"Engagement: {engagement_scope['engagement_key']}\n"
                f"Requested handling: {command.handling_profile} ({report_identity['handling_status']})\n"
                f"Preliminary recommendation: {result['recommendation']}\n"
                f"Attention areas: {result['attention_count']}\n"
                f"Information gaps: {result['information_gap_count']}\n\n"
                f"Review securely in SalCAPA: {review_url}\n\n"
                "Assessment answers are intentionally not included in email."
            )
            participant_body = (
                f"Hello {command.contact_name},\n\n"
                "Salus Solutions received your Protection Advisor assessment.\n\n"
                f"Project code: {command.project_code_name}\n"
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
                 f"Protection Advisor submission: {command.project_code_name}",internal_body,
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
                "result_reference": submission_key,
                "result": result,
                "package": package,
                "report_identity": report_identity,
                "engagement_scope": engagement_scope,
                "notifications": [dict(row) for row in notification_rows],
            }
        finally:
            conn.close()

    @app.post("/public/protection-advisor/report-identity")
    async def revise_public_report_identity(command: ReportIdentityCommand, request: Request) -> dict[str, Any]:
        limited(request, request.cookies.get("salus_advisor_session", ""))
        conn = ctx["db"]()
        try:
            session, _ = _session(conn, request)
            account = _account_session(conn, request)
            _require_account_assessment(conn, account["account_key"], session["session_key"])
            if session["status"] != "Submitted":
                raise HTTPException(409, "Report identity can be revised after submission")
            report_identity = _insert_report_identity(
                conn,
                account_key=account["account_key"],
                session_key=session["session_key"],
                values=command.model_dump(),
                created_by="Protected Member Account",
            )
            conn.execute(
                "INSERT INTO advisor_public_lifecycle_events VALUES(?,?,?,?,?)",
                ("SPA-EVENT-"+secrets.token_hex(16).upper(), session["session_key"],
                 "Report Identity Revised", report_identity["created_at"],
                 _sha(_json({"revision_no": report_identity["revision_no"]}))),
            )
            conn.commit()
            return {"report_identity": report_identity}
        finally:
            conn.close()

    @app.get("/public/protection-advisor/report.pdf")
    def download_public_protection_advisor_report(request: Request) -> FileResponse:
        """Return the professional preliminary report only to its linked Part 2 account."""
        limited(request, request.cookies.get("salus_advisor_account", ""))
        conn = ctx["db"]()
        try:
            session, _ = _session(conn, request)
            account = _account_session(conn, request)
            _require_account_assessment(conn, account["account_key"], session["session_key"])
            if session["status"] != "Submitted":
                raise HTTPException(409, "Submit Part 2 before downloading the detailed report")
            row = conn.execute(
                """SELECT s.submission_key,s.result_json,p.profile_json,p.package_json
                     FROM advisor_public_submissions s
                     JOIN advisor_public_service_profiles p ON p.submission_key=s.submission_key
                    WHERE s.session_key=?""",
                (session["session_key"],),
            ).fetchone()
            identity = _latest_report_identity(conn, session["session_key"])
            if not row or not identity:
                raise HTTPException(409, "Submitted assessment report is unavailable")
            output_dir = os.getenv("SALUS_ADVISOR_REPORT_OUTPUT_DIR", "").strip()
            if not output_dir:
                raise HTTPException(503, "Report delivery is temporarily unavailable")
            result = json.loads(row["result_json"])
            profile = json.loads(row["profile_json"])
            package = json.loads(row["package_json"])
            report_reference = "SPA-REPORT-" + row["submission_key"].removeprefix("SPA-SUBMISSION-")
            handling = "CUI" if (
                identity.get("handling_status") == "Approved"
                and "CUI" in str(identity.get("handling_profile", ""))
            ) else "Confidential"
            context = build_report_context(
                client_code_name=str(identity["protected_member_code_name"]),
                project_code_name=str(identity["project_code_name"]),
                organization_type=session["organization_type"],
                government_or_public_service_role=str(profile.get("external_requirements") or "Not provided"),
                assessment_authority_or_sponsor=str(profile.get("decision_authority") or "Not provided"),
                information_handling=handling,
                report_reference=report_reference,
                generated_at=_utc_now(),
            )
            path = os.path.join(output_dir, report_reference + "-participant.pdf")
            render_protection_advisor_pdf(
                output_path=path,
                context=context,
                result=result,
                package=package,
            )
            created = _utc_text(_utc_now())
            conn.execute(
                "INSERT INTO advisor_public_lifecycle_events VALUES(?,?,?,?,?)",
                ("SPA-EVENT-" + secrets.token_hex(16).upper(), session["session_key"],
                 "Participant Report Downloaded", created,
                 _sha(_json({"report_reference": report_reference, "format": "PDF"}))),
            )
            conn.commit()
            return FileResponse(
                path,
                media_type="application/pdf",
                filename=f"Salus-Protection-Advisor-{report_reference}.pdf",
                headers={"Cache-Control": "no-store", "X-Content-Type-Options": "nosniff"},
            )
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
