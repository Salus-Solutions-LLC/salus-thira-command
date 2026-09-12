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
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


POLICY_STATUS = "Released for Fictional Internal Prototype"
DATA_BOUNDARY = "Advisor Prospect — No Protected Member Access"
BUNDLE_KEY = "SPA-INTERNAL-PROTOTYPE-1"
EVALUATION_ADAPTER_VERSION = "SPA-EVALUATION-ADAPTER-1.0.0"
EVALUATION_STATUS = "Prepared — Salus Review Required"
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
