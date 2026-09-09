"""Governed SalCAPA commercial planning, membership, actual-cost, and WIP records.

Issue #154 increment.  Salus personnel configure and approve versioned planning
assumptions.  Estimates snapshot every assumption and calculation.  Salus time
and direct-cost records retain source, approval, and correction lineage while
keeping unavailable or estimated amounts distinct from recognized actual cost.
Protected Membership terms retain explicit human approval and release gates;
consumption never creates a charge, invoice, scope expansion, tier change,
renewal, partner action, or customer commitment automatically.
Unbilled/work-in-progress reviews preserve dated source snapshots and human
commercial dispositions without becoming accounting entries or creating bills.
"""
from __future__ import annotations

import csv
import hashlib
import io
import json
import uuid
from datetime import date, datetime
from decimal import Decimal, ROUND_HALF_UP
from typing import Any, Literal, Optional

from fastapi import HTTPException, Request, Response
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


PRODUCT_LINES = (
    "SalINTEL Investigation", "SalINTEL Ongoing Monitoring", "SalTHIRA Assessment",
    "SalOPS Preparedness", "SalOPS Protective Services", "SalOPS Incident Support",
    "Report / Briefing", "Special Project", "Protected Membership", "Other",
)
COMPLEXITIES = ("Low", "Standard", "High", "Very High")
PRICING_METHODS = (
    "Suggested Fixed Fee", "Hourly / Time and Materials", "Membership Included",
    "Bundled", "Pass-Through", "Cost Plus", "Milestone", "Custom",
)
MONITORING_SERVICES = (
    "Not Applicable", "Per Cycle", "Monthly", "Quarterly", "Annual",
    "Retainer / Included", "Custom",
)
RATE_OVERRIDE_LEVELS = (
    "Product Line", "Investigative Domain", "Tier", "Monitoring Service",
    "Protected Member", "Engagement",
)
RATE_OVERRIDE_SELECTORS = {
    "Product Line": "product_line",
    "Investigative Domain": "domain_key",
    "Tier": "investigation_tier",
    "Monitoring Service": "monitoring_service",
    "Protected Member": "protected_member_id",
    "Engagement": "engagement_id",
}
RATE_OVERRIDE_VALUE_FIELDS = {
    "loaded_labor_cost_cents_per_hour", "standard_bill_rate_cents_per_hour",
    "senior_bill_rate_cents_per_hour", "fixed_fee_contingency_basis_points",
    "rounding_increment_cents", "technology_planning_allowance_cents", "human_hours",
}
TIERS = ("Tier 1", "Tier 2", "Tier 3", "Not Applicable")
WORK_CATEGORIES = (
    "Research", "Interview", "Field Work", "Review", "Analysis", "Reporting",
    "Project Management", "Travel", "Administration", "Other",
)
COMMERCIAL_TREATMENTS = ("Billable", "Non-Billable", "Write-Off")
COST_CATEGORIES = (
    "Technology / Data", "Global Partner", "Travel", "Records / Database",
    "Field Expense", "Subcontractor", "Other Direct Cost",
)
COST_BASES = (
    "Metered Actual", "Supplier Invoice", "Receipt",
    "Authorized Estimate", "Planning Allowance", "Unavailable",
)
PARTNER_TREATMENTS = (
    "Included", "Pass-Through", "Cost Plus", "Absorbed",
    "Separately Quoted", "Not Yet Decided",
)
ACTUAL_COST_BASES = {"Metered Actual", "Supplier Invoice", "Receipt"}
REPORT_GROUPS = (
    "Product Line", "Investigative Domain", "Tier", "Engagement", "Pricing Method",
)
MEMBERSHIP_ARRANGEMENTS = ("Transactional", "Subscription Membership", "Hybrid")
MEMBERSHIP_BILLING_CADENCES = ("Monthly", "Quarterly", "Annual", "Custom")
MEMBERSHIP_TREATMENTS = (
    "Included", "Discounted", "Preferred Rate", "Credit Eligible",
    "Separately Quoted", "Pass-Through", "Not Included", "Custom",
)
MEMBERSHIP_CAPACITY_TYPES = ("Direct Quantity", "Service Credits", "Commercial Treatment Only")
MEMBERSHIP_SOURCE_TYPES = (
    "Estimate", "Investigation", "Monitoring Cycle", "Assessment", "Preparedness",
    "Plan", "Training", "Exercise", "Manual Governed Record", "Other",
)
WIP_DISPOSITIONS = (
    "Evidence Needed", "Included in Approved Price", "Membership Included",
    "Ready for Billing Authorization", "Authorized for Billing", "Deferred",
    "Non-Billable", "Write-Off", "Externally Billed",
)
BACKUP_TABLES = (
    "salcapa_rate_cards", "salcapa_commercial_estimates",
    "salcapa_time_entries", "salcapa_cost_entries", "salcapa_commercial_forecasts",
    "salcapa_membership_plans", "salcapa_membership_terms", "salcapa_membership_consumption",
    "salcapa_wip_reviews",
)
DELETE_ORDER = (
    "salcapa_wip_reviews", "salcapa_membership_consumption", "salcapa_membership_terms", "salcapa_membership_plans",
    "salcapa_commercial_forecasts", "salcapa_time_entries", "salcapa_cost_entries",
    "salcapa_commercial_estimates", "salcapa_rate_cards",
)
RESTORE_ORDER = (
    "salcapa_rate_cards", "salcapa_commercial_estimates",
    "salcapa_time_entries", "salcapa_cost_entries", "salcapa_commercial_forecasts",
    "salcapa_membership_plans", "salcapa_membership_terms", "salcapa_membership_consumption",
    "salcapa_wip_reviews",
)


DEFAULT_RULES: dict[str, Any] = {
    "schema_version": "1.0",
    "currency": "USD",
    "loaded_labor_cost_cents_per_hour": 9000,
    "standard_bill_rate_cents_per_hour": 25000,
    "senior_bill_rate_cents_per_hour": 32500,
    "fixed_fee_contingency_basis_points": 1500,
    "rounding_increment_cents": 5000,
    "technology_planning_allowance_cents": {
        "Tier 1": 400, "Tier 2": 1500, "Tier 3": 5000,
        "Monitoring Cycle": 300, "Not Applicable": 0,
    },
    "standard_human_hours": {
        "Tier 1": "1.5", "Tier 2": "4", "Tier 3": "10",
        "Monitoring Cycle": "0.5", "Not Applicable": "0",
    },
    "complexity_basis_points": {
        "Low": 7500, "Standard": 10000, "High": 15000, "Very High": 20000,
    },
    "domain_human_hour_overrides": {
        "personnel-assessment": {"Tier 1": "2", "Tier 2": "6", "Tier 3": "16"},
        "facility-assessment": {"Tier 1": "3", "Tier 2": "10", "Tier 3": "24"},
        "cyber-digital-entities": {"Tier 1": "2", "Tier 2": "6", "Tier 3": "15"},
        "critical-dependencies": {"Tier 1": "2", "Tier 2": "6", "Tier 3": "16"},
        "financial-economic": {"Tier 1": "2", "Tier 2": "6", "Tier 3": "16"},
        "supply-chain-logistics": {"Tier 1": "2", "Tier 2": "6", "Tier 3": "15"},
        "technology-data-cloud-ot-ics": {"Tier 1": "2", "Tier 2": "6", "Tier 3": "15"},
        "geopolitical-international": {"Tier 1": "2", "Tier 2": "6", "Tier 3": "15"},
        "adversarial-criminal-threat-actor": {"Tier 1": "2", "Tier 2": "7", "Tier 3": "18"},
        "emergency-capabilities-readiness": {"Tier 1": "2", "Tier 2": "6", "Tier 3": "14"},
    },
    "rate_overrides": [],
}


SCHEMA = r"""
CREATE TABLE IF NOT EXISTS salcapa_rate_cards (
  id TEXT PRIMARY KEY,
  tenant_id INTEGER NOT NULL,
  version_no INTEGER NOT NULL,
  name TEXT NOT NULL,
  effective_from TEXT NOT NULL DEFAULT '',
  supersedes_id TEXT,
  rules_json TEXT NOT NULL,
  content_sha256 TEXT NOT NULL,
  status TEXT NOT NULL DEFAULT 'Draft',
  created_by TEXT NOT NULL,
  created_at TEXT NOT NULL,
  submitted_by TEXT NOT NULL DEFAULT '',
  submitted_at TEXT NOT NULL DEFAULT '',
  approved_by TEXT NOT NULL DEFAULT '',
  approved_at TEXT NOT NULL DEFAULT '',
  decision_reason TEXT NOT NULL DEFAULT '',
  updated_at TEXT NOT NULL,
  UNIQUE(tenant_id, version_no)
);
CREATE INDEX IF NOT EXISTS idx_salcapa_rate_cards_scope
  ON salcapa_rate_cards(tenant_id,status,version_no);

CREATE TABLE IF NOT EXISTS salcapa_commercial_estimates (
  id TEXT PRIMARY KEY,
  tenant_id INTEGER NOT NULL,
  version_no INTEGER NOT NULL,
  supersedes_estimate_id TEXT,
  engagement_id INTEGER,
  assessment_id INTEGER,
  rate_card_id TEXT NOT NULL,
  rate_card_version INTEGER NOT NULL,
  product_line TEXT NOT NULL,
  domain_key TEXT NOT NULL DEFAULT '',
  investigation_tier TEXT NOT NULL,
  complexity TEXT NOT NULL,
  pricing_method TEXT NOT NULL,
  customer_summary TEXT NOT NULL,
  internal_basis TEXT NOT NULL,
  inputs_json TEXT NOT NULL,
  rate_snapshot_json TEXT NOT NULL,
  calculation_json TEXT NOT NULL,
  content_sha256 TEXT NOT NULL,
  recommended_customer_price_cents INTEGER NOT NULL,
  approved_customer_price_cents INTEGER,
  estimated_internal_cost_cents INTEGER NOT NULL,
  estimated_margin_cents INTEGER NOT NULL,
  estimated_margin_basis_points INTEGER,
  currency TEXT NOT NULL DEFAULT 'USD',
  status TEXT NOT NULL DEFAULT 'Draft',
  creates_charge INTEGER NOT NULL DEFAULT 0,
  creates_invoice INTEGER NOT NULL DEFAULT 0,
  created_by TEXT NOT NULL,
  created_at TEXT NOT NULL,
  submitted_by TEXT NOT NULL DEFAULT '',
  submitted_at TEXT NOT NULL DEFAULT '',
  approved_by TEXT NOT NULL DEFAULT '',
  approved_at TEXT NOT NULL DEFAULT '',
  released_by TEXT NOT NULL DEFAULT '',
  released_at TEXT NOT NULL DEFAULT '',
  decision_reason TEXT NOT NULL DEFAULT '',
  release_reason TEXT NOT NULL DEFAULT '',
  updated_at TEXT NOT NULL,
  FOREIGN KEY (rate_card_id) REFERENCES salcapa_rate_cards(id),
  UNIQUE(tenant_id, version_no)
);
CREATE INDEX IF NOT EXISTS idx_salcapa_commercial_estimates_scope
  ON salcapa_commercial_estimates(tenant_id,status,product_line,domain_key,version_no);

CREATE TABLE IF NOT EXISTS salcapa_time_entries (
  id TEXT PRIMARY KEY,
  tenant_id INTEGER NOT NULL,
  version_no INTEGER NOT NULL,
  estimate_id TEXT NOT NULL,
  supersedes_entry_id TEXT,
  engagement_id INTEGER,
  assessment_id INTEGER,
  person_name TEXT NOT NULL,
  role_name TEXT NOT NULL,
  work_date TEXT NOT NULL,
  minutes INTEGER NOT NULL,
  work_category TEXT NOT NULL,
  commercial_treatment TEXT NOT NULL,
  notes TEXT NOT NULL,
  loaded_rate_cents_per_hour INTEGER NOT NULL,
  calculated_cost_cents INTEGER NOT NULL,
  content_sha256 TEXT NOT NULL,
  status TEXT NOT NULL DEFAULT 'Draft',
  creates_charge INTEGER NOT NULL DEFAULT 0,
  creates_invoice INTEGER NOT NULL DEFAULT 0,
  created_by TEXT NOT NULL,
  created_at TEXT NOT NULL,
  submitted_by TEXT NOT NULL DEFAULT '',
  submitted_at TEXT NOT NULL DEFAULT '',
  approved_by TEXT NOT NULL DEFAULT '',
  approved_at TEXT NOT NULL DEFAULT '',
  decision_reason TEXT NOT NULL DEFAULT '',
  updated_at TEXT NOT NULL,
  FOREIGN KEY (estimate_id) REFERENCES salcapa_commercial_estimates(id),
  UNIQUE(tenant_id, version_no)
);
CREATE INDEX IF NOT EXISTS idx_salcapa_time_entries_scope
  ON salcapa_time_entries(tenant_id,estimate_id,status,work_date,version_no);

CREATE TABLE IF NOT EXISTS salcapa_cost_entries (
  id TEXT PRIMARY KEY,
  tenant_id INTEGER NOT NULL,
  version_no INTEGER NOT NULL,
  estimate_id TEXT NOT NULL,
  supersedes_entry_id TEXT,
  engagement_id INTEGER,
  assessment_id INTEGER,
  cost_category TEXT NOT NULL,
  cost_basis TEXT NOT NULL,
  amount_cents INTEGER NOT NULL,
  recognized_actual_cost_cents INTEGER NOT NULL,
  provider_or_payee TEXT NOT NULL,
  source_reference TEXT NOT NULL,
  usage_units TEXT NOT NULL,
  unit_rate_version TEXT NOT NULL,
  incurred_at TEXT NOT NULL,
  commercial_treatment TEXT NOT NULL,
  notes TEXT NOT NULL,
  content_sha256 TEXT NOT NULL,
  status TEXT NOT NULL DEFAULT 'Draft',
  creates_charge INTEGER NOT NULL DEFAULT 0,
  creates_invoice INTEGER NOT NULL DEFAULT 0,
  created_by TEXT NOT NULL,
  created_at TEXT NOT NULL,
  submitted_by TEXT NOT NULL DEFAULT '',
  submitted_at TEXT NOT NULL DEFAULT '',
  approved_by TEXT NOT NULL DEFAULT '',
  approved_at TEXT NOT NULL DEFAULT '',
  decision_reason TEXT NOT NULL DEFAULT '',
  updated_at TEXT NOT NULL,
  FOREIGN KEY (estimate_id) REFERENCES salcapa_commercial_estimates(id),
  UNIQUE(tenant_id, version_no)
);
CREATE INDEX IF NOT EXISTS idx_salcapa_cost_entries_scope
  ON salcapa_cost_entries(tenant_id,estimate_id,status,cost_category,version_no);

CREATE TABLE IF NOT EXISTS salcapa_commercial_forecasts (
  id TEXT PRIMARY KEY,
  tenant_id INTEGER NOT NULL,
  version_no INTEGER NOT NULL,
  estimate_id TEXT NOT NULL,
  supersedes_forecast_id TEXT,
  engagement_id INTEGER,
  assessment_id INTEGER,
  as_of_date TEXT NOT NULL,
  forecast_through_date TEXT NOT NULL,
  confidence_state TEXT NOT NULL,
  unavailable_cost_handling TEXT NOT NULL,
  remaining_labor_minutes INTEGER NOT NULL,
  loaded_rate_cents_per_hour INTEGER NOT NULL,
  forecast_remaining_labor_cost_cents INTEGER NOT NULL,
  forecast_additional_direct_cost_cents INTEGER NOT NULL,
  actual_snapshot_json TEXT NOT NULL,
  assumptions TEXT NOT NULL,
  known_constraints TEXT NOT NULL,
  content_sha256 TEXT NOT NULL,
  recognized_actual_cost_to_date_cents INTEGER NOT NULL,
  approved_provisional_cost_cents INTEGER NOT NULL,
  forecast_to_complete_cents INTEGER NOT NULL,
  forecast_at_completion_cents INTEGER NOT NULL,
  variance_to_estimated_internal_cost_cents INTEGER NOT NULL,
  projected_contribution_cents INTEGER NOT NULL,
  projected_contribution_basis_points INTEGER,
  completeness_state TEXT NOT NULL,
  status TEXT NOT NULL DEFAULT 'Draft',
  creates_charge INTEGER NOT NULL DEFAULT 0,
  creates_invoice INTEGER NOT NULL DEFAULT 0,
  created_by TEXT NOT NULL,
  created_at TEXT NOT NULL,
  submitted_by TEXT NOT NULL DEFAULT '',
  submitted_at TEXT NOT NULL DEFAULT '',
  approved_by TEXT NOT NULL DEFAULT '',
  approved_at TEXT NOT NULL DEFAULT '',
  decision_reason TEXT NOT NULL DEFAULT '',
  updated_at TEXT NOT NULL,
  FOREIGN KEY (estimate_id) REFERENCES salcapa_commercial_estimates(id),
  UNIQUE(tenant_id, version_no)
);
CREATE INDEX IF NOT EXISTS idx_salcapa_commercial_forecasts_scope
  ON salcapa_commercial_forecasts(tenant_id,estimate_id,status,as_of_date,version_no);

CREATE TABLE IF NOT EXISTS salcapa_membership_plans (
  id TEXT PRIMARY KEY,
  tenant_id INTEGER NOT NULL,
  version_no INTEGER NOT NULL,
  supersedes_plan_id TEXT,
  name TEXT NOT NULL,
  arrangement TEXT NOT NULL,
  effective_from TEXT NOT NULL,
  entitlements_json TEXT NOT NULL,
  portfolio_pricing_json TEXT NOT NULL,
  member_summary TEXT NOT NULL,
  internal_basis TEXT NOT NULL,
  content_sha256 TEXT NOT NULL,
  status TEXT NOT NULL DEFAULT 'Draft',
  created_by TEXT NOT NULL,
  created_at TEXT NOT NULL,
  submitted_by TEXT NOT NULL DEFAULT '',
  submitted_at TEXT NOT NULL DEFAULT '',
  approved_by TEXT NOT NULL DEFAULT '',
  approved_at TEXT NOT NULL DEFAULT '',
  decision_reason TEXT NOT NULL DEFAULT '',
  retired_by TEXT NOT NULL DEFAULT '',
  retired_at TEXT NOT NULL DEFAULT '',
  retirement_reason TEXT NOT NULL DEFAULT '',
  updated_at TEXT NOT NULL,
  UNIQUE(tenant_id,version_no)
);
CREATE INDEX IF NOT EXISTS idx_salcapa_membership_plans_scope
  ON salcapa_membership_plans(tenant_id,status,effective_from,version_no);

CREATE TABLE IF NOT EXISTS salcapa_membership_terms (
  id TEXT PRIMARY KEY,
  tenant_id INTEGER NOT NULL,
  version_no INTEGER NOT NULL,
  supersedes_term_id TEXT,
  plan_id TEXT NOT NULL,
  plan_version INTEGER NOT NULL,
  plan_snapshot_json TEXT NOT NULL,
  contract_reference TEXT NOT NULL,
  start_date TEXT NOT NULL,
  end_date TEXT NOT NULL,
  renewal_review_date TEXT NOT NULL,
  billing_cadence TEXT NOT NULL,
  recurring_fee_cents INTEGER NOT NULL,
  approved_term_value_cents INTEGER NOT NULL,
  portfolio_coverage_json TEXT NOT NULL,
  negotiated_terms TEXT NOT NULL,
  internal_basis TEXT NOT NULL,
  content_sha256 TEXT NOT NULL,
  status TEXT NOT NULL DEFAULT 'Draft',
  creates_charge INTEGER NOT NULL DEFAULT 0,
  creates_invoice INTEGER NOT NULL DEFAULT 0,
  creates_entitlement_automatically INTEGER NOT NULL DEFAULT 0,
  authorizes_scope_automatically INTEGER NOT NULL DEFAULT 0,
  auto_renews INTEGER NOT NULL DEFAULT 0,
  created_by TEXT NOT NULL,
  created_at TEXT NOT NULL,
  submitted_by TEXT NOT NULL DEFAULT '',
  submitted_at TEXT NOT NULL DEFAULT '',
  approved_by TEXT NOT NULL DEFAULT '',
  approved_at TEXT NOT NULL DEFAULT '',
  released_by TEXT NOT NULL DEFAULT '',
  released_at TEXT NOT NULL DEFAULT '',
  decision_reason TEXT NOT NULL DEFAULT '',
  release_reason TEXT NOT NULL DEFAULT '',
  updated_at TEXT NOT NULL,
  FOREIGN KEY (plan_id) REFERENCES salcapa_membership_plans(id),
  UNIQUE(tenant_id,version_no)
);
CREATE INDEX IF NOT EXISTS idx_salcapa_membership_terms_scope
  ON salcapa_membership_terms(tenant_id,status,start_date,end_date,version_no);

CREATE TABLE IF NOT EXISTS salcapa_membership_consumption (
  id TEXT PRIMARY KEY,
  tenant_id INTEGER NOT NULL,
  version_no INTEGER NOT NULL,
  term_id TEXT NOT NULL,
  supersedes_consumption_id TEXT,
  entitlement_key TEXT NOT NULL,
  entitlement_snapshot_json TEXT NOT NULL,
  quantity TEXT NOT NULL,
  occurred_on TEXT NOT NULL,
  source_type TEXT NOT NULL,
  source_record_id TEXT NOT NULL,
  source_reference TEXT NOT NULL,
  estimate_id TEXT,
  notes TEXT NOT NULL,
  content_sha256 TEXT NOT NULL,
  status TEXT NOT NULL DEFAULT 'Draft',
  creates_charge INTEGER NOT NULL DEFAULT 0,
  creates_invoice INTEGER NOT NULL DEFAULT 0,
  creates_scope_authorization INTEGER NOT NULL DEFAULT 0,
  created_by TEXT NOT NULL,
  created_at TEXT NOT NULL,
  submitted_by TEXT NOT NULL DEFAULT '',
  submitted_at TEXT NOT NULL DEFAULT '',
  approved_by TEXT NOT NULL DEFAULT '',
  approved_at TEXT NOT NULL DEFAULT '',
  decision_reason TEXT NOT NULL DEFAULT '',
  updated_at TEXT NOT NULL,
  FOREIGN KEY (term_id) REFERENCES salcapa_membership_terms(id),
  FOREIGN KEY (estimate_id) REFERENCES salcapa_commercial_estimates(id),
  UNIQUE(tenant_id,version_no)
);
CREATE INDEX IF NOT EXISTS idx_salcapa_membership_consumption_scope
  ON salcapa_membership_consumption(tenant_id,term_id,status,entitlement_key,occurred_on,version_no);

CREATE TABLE IF NOT EXISTS salcapa_wip_reviews (
  id TEXT PRIMARY KEY,
  tenant_id INTEGER NOT NULL,
  version_no INTEGER NOT NULL,
  estimate_id TEXT NOT NULL,
  supersedes_wip_review_id TEXT,
  engagement_id INTEGER,
  assessment_id INTEGER,
  as_of_date TEXT NOT NULL,
  work_through_date TEXT NOT NULL,
  commercial_disposition TEXT NOT NULL,
  work_value_cents INTEGER NOT NULL,
  billing_authorized_amount_cents INTEGER NOT NULL DEFAULT 0,
  external_billing_reference TEXT NOT NULL DEFAULT '',
  source_snapshot_json TEXT NOT NULL,
  review_basis TEXT NOT NULL,
  assumptions TEXT NOT NULL,
  known_gaps TEXT NOT NULL,
  content_sha256 TEXT NOT NULL,
  evidence_state TEXT NOT NULL,
  status TEXT NOT NULL DEFAULT 'Draft',
  creates_charge INTEGER NOT NULL DEFAULT 0,
  creates_invoice INTEGER NOT NULL DEFAULT 0,
  recognizes_revenue INTEGER NOT NULL DEFAULT 0,
  transmits_externally INTEGER NOT NULL DEFAULT 0,
  created_by TEXT NOT NULL,
  created_at TEXT NOT NULL,
  submitted_by TEXT NOT NULL DEFAULT '',
  submitted_at TEXT NOT NULL DEFAULT '',
  approved_by TEXT NOT NULL DEFAULT '',
  approved_at TEXT NOT NULL DEFAULT '',
  decision_reason TEXT NOT NULL DEFAULT '',
  updated_at TEXT NOT NULL,
  FOREIGN KEY (estimate_id) REFERENCES salcapa_commercial_estimates(id),
  UNIQUE(tenant_id,version_no)
);
CREATE INDEX IF NOT EXISTS idx_salcapa_wip_reviews_scope
  ON salcapa_wip_reviews(tenant_id,estimate_id,status,work_through_date,version_no);
"""


def _canonical(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def _digest(value: Any) -> str:
    return hashlib.sha256(_canonical(value).encode("utf-8")).hexdigest()


def _money(value: Decimal) -> int:
    return int(value.quantize(Decimal("1"), rounding=ROUND_HALF_UP))


def _key(prefix: str) -> str:
    return f"{prefix}-{uuid.uuid4().hex}"


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class RateCardCreate(StrictModel):
    name: str = Field(min_length=3, max_length=200)
    effective_from: str = Field(default="", max_length=40)
    supersedes_id: Optional[str] = Field(default=None, max_length=80)
    rules: dict[str, Any] = Field(default_factory=lambda: json.loads(_canonical(DEFAULT_RULES)))


class RateCardTransition(StrictModel):
    status: Literal["Submitted", "Approved", "Rejected"]
    reason: str = Field(min_length=3, max_length=4000)


class EstimateCreate(StrictModel):
    supersedes_estimate_id: Optional[str] = Field(default=None, max_length=80)
    engagement_id: Optional[int] = Field(default=None, gt=0)
    assessment_id: Optional[int] = Field(default=None, gt=0)
    rate_card_id: Optional[str] = Field(default=None, max_length=80)
    product_line: Literal[
        "SalINTEL Investigation", "SalINTEL Ongoing Monitoring", "SalTHIRA Assessment",
        "SalOPS Preparedness", "SalOPS Protective Services", "SalOPS Incident Support",
        "Report / Briefing", "Special Project", "Protected Membership", "Other",
    ]
    domain_key: str = Field(default="", max_length=160)
    investigation_tier: Literal["Tier 1", "Tier 2", "Tier 3", "Not Applicable"] = "Not Applicable"
    complexity: Literal["Low", "Standard", "High", "Very High"] = "Standard"
    pricing_method: Literal[
        "Suggested Fixed Fee", "Hourly / Time and Materials", "Membership Included",
        "Bundled", "Pass-Through", "Cost Plus", "Milestone", "Custom",
    ] = "Suggested Fixed Fee"
    monitoring_service: Literal[
        "Not Applicable", "Per Cycle", "Monthly", "Quarterly", "Annual",
        "Retainer / Included", "Custom",
    ] = "Not Applicable"
    monitoring_cycles: int = Field(default=0, ge=0, le=10000)
    senior_specialist: bool = False
    custom_human_hours: Optional[Decimal] = Field(default=None, ge=0, le=100000, decimal_places=3)
    partner_cost_cents: int = Field(default=0, ge=0, le=1_000_000_000)
    other_direct_cost_cents: int = Field(default=0, ge=0, le=1_000_000_000)
    discount_cents: int = Field(default=0, ge=0, le=1_000_000_000)
    customer_summary: str = Field(min_length=3, max_length=3000)
    internal_basis: str = Field(min_length=3, max_length=8000)

    @field_validator("domain_key")
    @classmethod
    def normalize_domain(cls, value: str) -> str:
        return value.strip().lower()


class EstimateTransition(StrictModel):
    status: Literal["Submitted", "Approved", "Rejected", "Released"]
    reason: str = Field(min_length=3, max_length=4000)
    approved_customer_price_cents: Optional[int] = Field(default=None, ge=0, le=2_000_000_000)


class TimeEntryCreate(StrictModel):
    estimate_id: str = Field(min_length=3, max_length=80)
    supersedes_entry_id: Optional[str] = Field(default=None, max_length=80)
    person_name: str = Field(min_length=2, max_length=160)
    role_name: str = Field(min_length=2, max_length=160)
    work_date: str = Field(min_length=10, max_length=10)
    minutes: int = Field(gt=0, le=1440)
    work_category: Literal[
        "Research", "Interview", "Field Work", "Review", "Analysis", "Reporting",
        "Project Management", "Travel", "Administration", "Other",
    ]
    commercial_treatment: Literal["Billable", "Non-Billable", "Write-Off"]
    notes: str = Field(min_length=3, max_length=4000)

    @field_validator("work_date")
    @classmethod
    def valid_work_date(cls, value: str) -> str:
        try:
            date.fromisoformat(value)
        except ValueError as exc:
            raise ValueError("work_date must be a valid ISO date") from exc
        return value


class CostEntryCreate(StrictModel):
    estimate_id: str = Field(min_length=3, max_length=80)
    supersedes_entry_id: Optional[str] = Field(default=None, max_length=80)
    cost_category: Literal[
        "Technology / Data", "Global Partner", "Travel", "Records / Database",
        "Field Expense", "Subcontractor", "Other Direct Cost",
    ]
    cost_basis: Literal[
        "Metered Actual", "Supplier Invoice", "Receipt",
        "Authorized Estimate", "Planning Allowance", "Unavailable",
    ]
    amount_cents: int = Field(default=0, ge=0, le=1_000_000_000)
    provider_or_payee: str = Field(default="", max_length=240)
    source_reference: str = Field(default="", max_length=500)
    usage_units: str = Field(default="", max_length=500)
    unit_rate_version: str = Field(default="", max_length=240)
    incurred_at: str = Field(min_length=3, max_length=40)
    commercial_treatment: Literal[
        "Included", "Pass-Through", "Cost Plus", "Absorbed",
        "Separately Quoted", "Not Yet Decided",
    ] = "Not Yet Decided"
    notes: str = Field(min_length=3, max_length=4000)

    @field_validator("amount_cents")
    @classmethod
    def valid_amount(cls, value: int, info) -> int:
        basis = info.data.get("cost_basis")
        if basis == "Unavailable" and value != 0:
            raise ValueError("Unavailable cost must not fabricate an amount")
        if basis and basis != "Unavailable" and value <= 0:
            raise ValueError("Recorded cost amount must be positive")
        return value

    @field_validator("incurred_at")
    @classmethod
    def valid_incurred_at(cls, value: str) -> str:
        try:
            datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError as exc:
            raise ValueError("incurred_at must be a valid ISO date or timestamp") from exc
        return value

    @model_validator(mode="after")
    def actual_cost_requires_source(self):
        if self.cost_basis in ACTUAL_COST_BASES:
            if not self.provider_or_payee.strip() or not self.source_reference.strip():
                raise ValueError("Recognized actual cost requires a provider/payee and source reference")
            if self.cost_basis == "Metered Actual" and (
                not self.usage_units.strip() or not self.unit_rate_version.strip()
            ):
                raise ValueError("Metered actual cost requires usage units and the applicable unit-rate version")
        return self


class ActualEntryTransition(StrictModel):
    status: Literal["Submitted", "Approved", "Rejected"]
    reason: str = Field(min_length=3, max_length=4000)


class ForecastCreate(StrictModel):
    estimate_id: str = Field(min_length=3, max_length=80)
    supersedes_forecast_id: Optional[str] = Field(default=None, max_length=80)
    as_of_date: str = Field(min_length=10, max_length=10)
    forecast_through_date: str = Field(min_length=10, max_length=10)
    confidence_state: Literal[
        "Reasonably Supported", "Evidence Needed", "Awaiting Validation",
    ] = "Awaiting Validation"
    unavailable_cost_handling: Literal[
        "Included in remaining estimate", "Excluded pending evidence",
    ] = "Excluded pending evidence"
    remaining_labor_minutes: int = Field(default=0, ge=0, le=10_000_000)
    additional_remaining_direct_cost_cents: int = Field(default=0, ge=0, le=2_000_000_000)
    assumptions: str = Field(min_length=3, max_length=8000)
    known_constraints: str = Field(min_length=3, max_length=8000)

    @model_validator(mode="after")
    def valid_forecast_dates(self):
        try:
            as_of = date.fromisoformat(self.as_of_date)
            through = date.fromisoformat(self.forecast_through_date)
        except ValueError as exc:
            raise ValueError("Forecast dates must be valid ISO dates") from exc
        if through < as_of:
            raise ValueError("forecast_through_date cannot precede as_of_date")
        return self


class ForecastTransition(StrictModel):
    status: Literal["Submitted", "Approved", "Rejected"]
    reason: str = Field(min_length=3, max_length=4000)


class MembershipEntitlement(StrictModel):
    key: str = Field(pattern=r"^[a-z0-9][a-z0-9-]{1,79}$")
    label: str = Field(min_length=2, max_length=160)
    product_line: str = Field(min_length=2, max_length=160)
    service_scope: str = Field(min_length=3, max_length=1000)
    treatment: Literal[
        "Included", "Discounted", "Preferred Rate", "Credit Eligible",
        "Separately Quoted", "Pass-Through", "Not Included", "Custom",
    ]
    capacity_type: Literal["Direct Quantity", "Service Credits", "Commercial Treatment Only"]
    included_quantity: Optional[Decimal] = Field(default=None, gt=0, le=1_000_000, decimal_places=3)
    unit: str = Field(min_length=2, max_length=80)
    rollover: bool = False
    rollover_limit: Optional[Decimal] = Field(default=None, ge=0, le=1_000_000, decimal_places=3)
    member_description: str = Field(min_length=3, max_length=1000)

    @model_validator(mode="after")
    def valid_entitlement(self):
        if self.product_line not in PRODUCT_LINES:
            raise ValueError("Membership entitlement product line is invalid")
        if self.capacity_type in {"Direct Quantity", "Service Credits"}:
            if self.included_quantity is None:
                raise ValueError("A quantity or credit capacity must have an explicit limit")
        elif self.included_quantity is not None or self.rollover or self.rollover_limit is not None:
            raise ValueError("Commercial-treatment-only entitlements cannot imply quantity capacity")
        if self.capacity_type != "Service Credits" and (self.rollover or self.rollover_limit is not None):
            raise ValueError("Rollover applies only to service credits")
        if self.rollover_limit is not None and not self.rollover:
            raise ValueError("A rollover limit requires rollover to be enabled")
        return self


class MembershipPortfolioPricingRule(StrictModel):
    driver_key: str = Field(pattern=r"^[a-z0-9][a-z0-9-]{1,79}$")
    label: str = Field(min_length=2, max_length=160)
    unit: str = Field(min_length=2, max_length=80)
    included_quantity: Decimal = Field(ge=0, le=1_000_000, decimal_places=3)
    adjustment_method: Literal["Negotiated", "Per Additional Unit", "Separate Quote"]
    planning_amount_cents: int = Field(default=0, ge=0, le=1_000_000_000)
    efficiency_basis: str = Field(min_length=3, max_length=1000)

    @model_validator(mode="after")
    def valid_portfolio_rule(self):
        if self.adjustment_method == "Per Additional Unit" and self.planning_amount_cents <= 0:
            raise ValueError("A per-unit planning rule requires a positive planning amount")
        if self.adjustment_method != "Per Additional Unit" and self.planning_amount_cents != 0:
            raise ValueError("Negotiated or separately quoted drivers cannot imply a unit charge")
        return self


class MembershipPlanCreate(StrictModel):
    supersedes_plan_id: Optional[str] = Field(default=None, max_length=80)
    name: str = Field(min_length=3, max_length=200)
    arrangement: Literal["Transactional", "Subscription Membership", "Hybrid"]
    effective_from: str = Field(min_length=10, max_length=10)
    entitlements: list[MembershipEntitlement] = Field(min_length=1, max_length=200)
    portfolio_pricing: list[MembershipPortfolioPricingRule] = Field(default_factory=list, max_length=100)
    member_summary: str = Field(min_length=3, max_length=3000)
    internal_basis: str = Field(min_length=3, max_length=8000)

    @field_validator("name")
    @classmethod
    def membership_name_is_not_investigation_tier(cls, value: str) -> str:
        folded = " ".join(value.casefold().replace("-", " ").split())
        if any(f"tier {number}" in folded for number in (1, 2, 3)):
            raise ValueError("Membership plan names must not be represented as investigation tiers")
        return value.strip()

    @field_validator("effective_from")
    @classmethod
    def valid_effective_from(cls, value: str) -> str:
        try:
            date.fromisoformat(value)
        except ValueError as exc:
            raise ValueError("effective_from must be a valid ISO date") from exc
        return value

    @model_validator(mode="after")
    def unique_membership_keys(self):
        entitlement_keys = [item.key for item in self.entitlements]
        if len(entitlement_keys) != len(set(entitlement_keys)):
            raise ValueError("Membership entitlement keys must be unique")
        driver_keys = [item.driver_key for item in self.portfolio_pricing]
        if len(driver_keys) != len(set(driver_keys)):
            raise ValueError("Portfolio pricing driver keys must be unique")
        return self


class MembershipPlanTransition(StrictModel):
    status: Literal["Submitted", "Approved", "Rejected", "Retired"]
    reason: str = Field(min_length=3, max_length=4000)


class MembershipPortfolioCoverage(StrictModel):
    entity_type: str = Field(min_length=2, max_length=120)
    covered_quantity: Decimal = Field(ge=0, le=1_000_000, decimal_places=3)
    scope_reference: str = Field(min_length=3, max_length=500)
    member_description: str = Field(min_length=3, max_length=1000)


class MembershipTermCreate(StrictModel):
    supersedes_term_id: Optional[str] = Field(default=None, max_length=80)
    plan_id: str = Field(min_length=3, max_length=80)
    contract_reference: str = Field(min_length=3, max_length=500)
    start_date: str = Field(min_length=10, max_length=10)
    end_date: str = Field(min_length=10, max_length=10)
    renewal_review_date: str = Field(min_length=10, max_length=10)
    billing_cadence: Literal["Monthly", "Quarterly", "Annual", "Custom"]
    recurring_fee_cents: int = Field(ge=0, le=2_000_000_000)
    approved_term_value_cents: int = Field(ge=0, le=2_000_000_000)
    portfolio_coverage: list[MembershipPortfolioCoverage] = Field(default_factory=list, max_length=200)
    negotiated_terms: str = Field(min_length=3, max_length=8000)
    internal_basis: str = Field(min_length=3, max_length=8000)

    @model_validator(mode="after")
    def valid_term(self):
        try:
            start = date.fromisoformat(self.start_date)
            end = date.fromisoformat(self.end_date)
            review = date.fromisoformat(self.renewal_review_date)
        except ValueError as exc:
            raise ValueError("Membership term dates must be valid ISO dates") from exc
        if end < start:
            raise ValueError("Membership end_date cannot precede start_date")
        if review > end:
            raise ValueError("renewal_review_date cannot follow end_date")
        coverage_types = [item.entity_type.casefold() for item in self.portfolio_coverage]
        if len(coverage_types) != len(set(coverage_types)):
            raise ValueError("Portfolio coverage entity types must be unique within a term")
        return self


class MembershipTermTransition(StrictModel):
    status: Literal["Submitted", "Approved", "Rejected", "Released"]
    reason: str = Field(min_length=3, max_length=4000)


class MembershipConsumptionCreate(StrictModel):
    term_id: str = Field(min_length=3, max_length=80)
    supersedes_consumption_id: Optional[str] = Field(default=None, max_length=80)
    entitlement_key: str = Field(pattern=r"^[a-z0-9][a-z0-9-]{1,79}$")
    quantity: Decimal = Field(gt=0, le=1_000_000, decimal_places=3)
    occurred_on: str = Field(min_length=10, max_length=10)
    source_type: Literal[
        "Estimate", "Investigation", "Monitoring Cycle", "Assessment", "Preparedness",
        "Plan", "Training", "Exercise", "Manual Governed Record", "Other",
    ]
    source_record_id: str = Field(min_length=1, max_length=160)
    source_reference: str = Field(min_length=3, max_length=1000)
    estimate_id: Optional[str] = Field(default=None, max_length=80)
    notes: str = Field(min_length=3, max_length=4000)

    @field_validator("occurred_on")
    @classmethod
    def valid_occurred_on(cls, value: str) -> str:
        try:
            date.fromisoformat(value)
        except ValueError as exc:
            raise ValueError("occurred_on must be a valid ISO date") from exc
        return value

    @model_validator(mode="after")
    def valid_source(self):
        if self.source_type == "Estimate" and not self.estimate_id:
            raise ValueError("Estimate consumption requires estimate_id")
        return self


class MembershipConsumptionTransition(StrictModel):
    status: Literal["Submitted", "Approved", "Rejected"]
    reason: str = Field(min_length=3, max_length=4000)


class WipReviewCreate(StrictModel):
    estimate_id: str = Field(min_length=3, max_length=80)
    supersedes_wip_review_id: Optional[str] = Field(default=None, max_length=80)
    as_of_date: str = Field(min_length=10, max_length=10)
    work_through_date: str = Field(min_length=10, max_length=10)
    commercial_disposition: Literal[
        "Evidence Needed", "Included in Approved Price", "Membership Included",
        "Ready for Billing Authorization", "Authorized for Billing", "Deferred",
        "Non-Billable", "Write-Off", "Externally Billed",
    ]
    work_value_cents: int = Field(ge=0, le=2_000_000_000)
    billing_authorized_amount_cents: int = Field(default=0, ge=0, le=2_000_000_000)
    external_billing_reference: str = Field(default="", max_length=500)
    review_basis: str = Field(min_length=3, max_length=8000)
    assumptions: str = Field(min_length=3, max_length=8000)
    known_gaps: str = Field(min_length=3, max_length=8000)

    @model_validator(mode="after")
    def valid_wip_review(self):
        try:
            as_of = date.fromisoformat(self.as_of_date)
            through = date.fromisoformat(self.work_through_date)
        except ValueError as exc:
            raise ValueError("WIP review dates must be valid ISO dates") from exc
        if through > as_of:
            raise ValueError("work_through_date cannot follow as_of_date")
        if self.commercial_disposition == "Authorized for Billing":
            if self.billing_authorized_amount_cents <= 0:
                raise ValueError("Authorized-for-billing treatment requires a positive reviewed amount")
            if self.billing_authorized_amount_cents > self.work_value_cents:
                raise ValueError("Billing-authorized amount cannot exceed reviewed work value")
        elif self.billing_authorized_amount_cents:
            raise ValueError("Only Authorized for Billing may carry a billing-authorized amount")
        if self.commercial_disposition == "Externally Billed":
            if not self.external_billing_reference.strip():
                raise ValueError("Externally billed treatment requires an evidence reference")
        elif self.external_billing_reference.strip():
            raise ValueError("External billing reference applies only to Externally Billed evidence")
        if self.commercial_disposition not in {"Evidence Needed", "Non-Billable"} and self.work_value_cents <= 0:
            raise ValueError("This WIP treatment requires a positive reviewed work value")
        return self


class WipReviewTransition(StrictModel):
    status: Literal["Submitted", "Approved", "Rejected"]
    reason: str = Field(min_length=3, max_length=4000)


def _validate_rules(rules: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(rules, dict) or rules.get("schema_version") != "1.0" or rules.get("currency") != "USD":
        raise HTTPException(422, "Rate-card rules must use the governed USD schema version 1.0")
    rules = json.loads(_canonical(rules))
    integer_fields = (
        "loaded_labor_cost_cents_per_hour", "standard_bill_rate_cents_per_hour",
        "senior_bill_rate_cents_per_hour", "fixed_fee_contingency_basis_points",
        "rounding_increment_cents",
    )
    for field in integer_fields:
        value = rules.get(field)
        if not isinstance(value, int) or value < 0 or value > 100_000_000:
            raise HTTPException(422, f"Rate-card field {field} is invalid")
    if not 0 <= rules["fixed_fee_contingency_basis_points"] <= 10000:
        raise HTTPException(422, "Contingency must be between zero and 100 percent")
    if rules["rounding_increment_cents"] < 1:
        raise HTTPException(422, "Rounding increment must be positive")
    for key in TIERS[:3] + ("Monitoring Cycle", "Not Applicable"):
        value = rules.get("technology_planning_allowance_cents", {}).get(key)
        if not isinstance(value, int) or not 0 <= value <= 100_000_000:
            raise HTTPException(422, f"Technology planning allowance for {key} is invalid")
        try:
            hours = Decimal(str(rules.get("standard_human_hours", {}).get(key)))
        except Exception as exc:
            raise HTTPException(422, f"Standard human hours for {key} are invalid") from exc
        if hours < 0 or hours > 100000:
            raise HTTPException(422, f"Standard human hours for {key} are invalid")
    for key in COMPLEXITIES:
        multiplier = rules.get("complexity_basis_points", {}).get(key)
        if not isinstance(multiplier, int) or not 1000 <= multiplier <= 100000:
            raise HTTPException(422, f"Complexity multiplier for {key} is invalid")
    overrides = rules.get("domain_human_hour_overrides", {})
    if not isinstance(overrides, dict) or len(overrides) > 500:
        raise HTTPException(422, "Domain human-hour overrides are invalid")
    for domain, profile in overrides.items():
        if not isinstance(domain, str) or not domain.strip() or not isinstance(profile, dict):
            raise HTTPException(422, "Domain human-hour override is invalid")
        for tier, raw in profile.items():
            if tier not in TIERS[:3] or Decimal(str(raw)) < 0 or Decimal(str(raw)) > 100000:
                raise HTTPException(422, f"Domain human-hour override for {domain} is invalid")
    rate_overrides = rules.get("rate_overrides", [])
    if not isinstance(rate_overrides, list) or len(rate_overrides) > 1000:
        raise HTTPException(422, "Rate overrides must be a bounded list")
    seen_scopes: set[str] = set()
    cleaned_overrides: list[dict[str, Any]] = []
    for override in rate_overrides:
        if not isinstance(override, dict) or set(override) != {
            "name", "scope_level", "selector", "values", "reason",
        }:
            raise HTTPException(422, "Each rate override must use the governed override schema")
        name, level, selector, values, reason = (
            override["name"], override["scope_level"], override["selector"],
            override["values"], override["reason"],
        )
        if not isinstance(name, str) or not 3 <= len(name.strip()) <= 200:
            raise HTTPException(422, "Rate override name is invalid")
        if level not in RATE_OVERRIDE_LEVELS or not isinstance(selector, dict):
            raise HTTPException(422, "Rate override scope is invalid")
        selector_key = RATE_OVERRIDE_SELECTORS[level]
        if set(selector) != {selector_key}:
            raise HTTPException(422, f"{level} override must use only {selector_key}")
        selector_value = selector[selector_key]
        if selector_key in {"protected_member_id", "engagement_id"}:
            if not isinstance(selector_value, int) or selector_value <= 0:
                raise HTTPException(422, f"Rate override selector {selector_key} is invalid")
        elif not isinstance(selector_value, str) or not selector_value.strip():
            raise HTTPException(422, f"Rate override selector {selector_key} is invalid")
        if selector_key == "product_line" and selector_value not in PRODUCT_LINES:
            raise HTTPException(422, "Rate override product line is invalid")
        if selector_key == "investigation_tier" and selector_value not in TIERS:
            raise HTTPException(422, "Rate override tier is invalid")
        if selector_key == "monitoring_service" and selector_value not in MONITORING_SERVICES:
            raise HTTPException(422, "Rate override monitoring service is invalid")
        if selector_key == "domain_key":
            selector_value = selector_value.strip().lower()
        elif isinstance(selector_value, str):
            selector_value = selector_value.strip()
        normalized_selector = {selector_key: selector_value}
        scope_key = f"{level}:{_canonical(normalized_selector)}"
        if scope_key in seen_scopes:
            raise HTTPException(422, "Rate card contains competing overrides for the same scope")
        seen_scopes.add(scope_key)
        if not isinstance(values, dict) or not values or not set(values).issubset(RATE_OVERRIDE_VALUE_FIELDS):
            raise HTTPException(422, "Rate override values contain an unsupported or empty field set")
        cleaned_values: dict[str, Any] = {}
        for field, value in values.items():
            if field == "human_hours":
                try:
                    hours = Decimal(str(value))
                except Exception as exc:
                    raise HTTPException(422, "Rate override human hours are invalid") from exc
                if hours < 0 or hours > 100000:
                    raise HTTPException(422, "Rate override human hours are invalid")
                cleaned_values[field] = format(hours, "f")
            else:
                if not isinstance(value, int) or value < 0 or value > 100_000_000:
                    raise HTTPException(422, f"Rate override field {field} is invalid")
                if field == "fixed_fee_contingency_basis_points" and value > 10000:
                    raise HTTPException(422, "Rate override contingency cannot exceed 100 percent")
                if field == "rounding_increment_cents" and value < 1:
                    raise HTTPException(422, "Rate override rounding increment must be positive")
                cleaned_values[field] = value
        if not isinstance(reason, str) or not 3 <= len(reason.strip()) <= 2000:
            raise HTTPException(422, "Rate override reason is invalid")
        cleaned_overrides.append({
            "name": name.strip(), "scope_level": level, "selector": normalized_selector,
            "values": cleaned_values, "reason": reason.strip(),
        })
    rules["rate_overrides"] = cleaned_overrides
    return json.loads(_canonical(rules))


def _resolve_rate_overrides(payload: EstimateCreate, rules: dict[str, Any], tid: int) -> tuple[dict[str, Any], list[dict[str, Any]], dict[str, str]]:
    effective = {
        "loaded_labor_cost_cents_per_hour": rules["loaded_labor_cost_cents_per_hour"],
        "standard_bill_rate_cents_per_hour": rules["standard_bill_rate_cents_per_hour"],
        "senior_bill_rate_cents_per_hour": rules["senior_bill_rate_cents_per_hour"],
        "fixed_fee_contingency_basis_points": rules["fixed_fee_contingency_basis_points"],
        "rounding_increment_cents": rules["rounding_increment_cents"],
    }
    actual_selectors = {
        "product_line": payload.product_line, "domain_key": payload.domain_key,
        "investigation_tier": payload.investigation_tier,
        "monitoring_service": payload.monitoring_service,
        "protected_member_id": tid, "engagement_id": payload.engagement_id,
    }
    applied: list[dict[str, Any]] = []
    field_sources: dict[str, str] = {}
    ranked = sorted(
        rules.get("rate_overrides", []),
        key=lambda item: RATE_OVERRIDE_LEVELS.index(item["scope_level"]),
    )
    for override in ranked:
        selector_key = RATE_OVERRIDE_SELECTORS[override["scope_level"]]
        selector_value = override["selector"][selector_key]
        if actual_selectors.get(selector_key) != selector_value:
            continue
        effective.update(override["values"])
        for field in override["values"]:
            field_sources[field] = override["name"]
        applied.append(json.loads(_canonical(override)))
    return effective, applied, field_sources


def _calculate(payload: EstimateCreate, rules: dict[str, Any], tid: int) -> tuple[dict[str, Any], dict[str, Any]]:
    effective, applied_overrides, field_sources = _resolve_rate_overrides(payload, rules, tid)
    tier = payload.investigation_tier
    multiplier = Decimal(rules["complexity_basis_points"][payload.complexity]) / Decimal(10000)
    overrides = rules["domain_human_hour_overrides"].get(payload.domain_key, {})
    if payload.custom_human_hours is not None:
        base_hours = Decimal(payload.custom_human_hours)
        hour_basis = "Salus-authorized custom estimate"
    elif "human_hours" in effective:
        base_hours = Decimal(str(effective["human_hours"]))
        hour_basis = f"Authorized rate-card override: {field_sources['human_hours']}"
    elif tier in overrides:
        base_hours = Decimal(str(overrides[tier]))
        hour_basis = "Authorized domain override"
    else:
        base_hours = Decimal(str(rules["standard_human_hours"][tier])) * multiplier
        hour_basis = "Standard profile with complexity multiplier"
    monitoring_hours = (
        Decimal(str(rules["standard_human_hours"]["Monitoring Cycle"]))
        * multiplier * Decimal(payload.monitoring_cycles)
    )
    human_hours = (base_hours + monitoring_hours).quantize(Decimal("0.001"), rounding=ROUND_HALF_UP)
    if "technology_planning_allowance_cents" in effective:
        technology = int(effective["technology_planning_allowance_cents"])
        technology_basis = f"Authorized rate-card override: {field_sources['technology_planning_allowance_cents']}"
    else:
        technology = _money(
            Decimal(rules["technology_planning_allowance_cents"][tier]) * multiplier
            + Decimal(rules["technology_planning_allowance_cents"]["Monitoring Cycle"])
            * multiplier * Decimal(payload.monitoring_cycles)
        )
        technology_basis = "Tier, monitoring-cycle, and complexity planning rules"
    loaded_labor = _money(human_hours * Decimal(effective["loaded_labor_cost_cents_per_hour"]))
    bill_rate = effective[
        "senior_bill_rate_cents_per_hour" if payload.senior_specialist
        else "standard_bill_rate_cents_per_hour"
    ]
    customer_labor = _money(human_hours * Decimal(bill_rate))
    internal_cost = loaded_labor + technology + payload.partner_cost_cents + payload.other_direct_cost_cents
    base_price = customer_labor + technology + payload.partner_cost_cents + payload.other_direct_cost_cents
    contingency = 0
    if payload.pricing_method in {"Suggested Fixed Fee", "Bundled", "Milestone", "Custom"}:
        contingency = _money(Decimal(base_price) * Decimal(effective["fixed_fee_contingency_basis_points"]) / Decimal(10000))
    unrounded = max(0, base_price + contingency - payload.discount_cents)
    if payload.pricing_method == "Membership Included":
        recommended = 0
    else:
        increment = int(effective["rounding_increment_cents"])
        recommended = _money(Decimal(unrounded) / Decimal(increment)) * increment
    margin = recommended - internal_cost
    margin_bps = None if recommended <= 0 else _money(Decimal(margin) * Decimal(10000) / Decimal(recommended))
    inputs = payload.model_dump(mode="json")
    calculation = {
        "human_hours": format(human_hours, "f"), "human_hours_basis": hour_basis,
        "technology_planning_allowance_cents": technology,
        "technology_planning_allowance_basis": technology_basis,
        "estimated_loaded_labor_cost_cents": loaded_labor,
        "customer_labor_equivalent_cents": customer_labor,
        "partner_cost_cents": payload.partner_cost_cents,
        "other_direct_cost_cents": payload.other_direct_cost_cents,
        "contingency_cents": contingency, "discount_cents": payload.discount_cents,
        "unrounded_recommendation_cents": unrounded,
        "rounding_increment_cents": effective["rounding_increment_cents"],
        "recommended_customer_price_cents": recommended,
        "estimated_internal_cost_cents": internal_cost,
        "estimated_margin_cents": margin,
        "estimated_margin_basis_points": margin_bps,
        "actual_cost_status": "Not Recorded",
        "rate_resolution": {
            "precedence": list(RATE_OVERRIDE_LEVELS),
            "applied_overrides": applied_overrides,
            "effective_values": effective,
            "human_authority_required": True,
        },
        "creates_charge": False, "creates_invoice": False,
    }
    return inputs, calculation


def register_salcapa_commercial(app, core: dict[str, Any]) -> None:
    db = core["db"]
    require = core["require"]
    require_salus = core["require_salus_component_authority"]
    tenant_id = core["tenant_id"]
    actor = core["actor"]
    role = core["role"]
    now = core["now"]
    audit = core["audit"]
    protected_member = core["protected_member_request"]
    assessment_for_request = core.get("assessment_row_for_request")
    accessible_assessment_ids = core.get("accessible_assessment_ids")

    conn = db()
    conn.executescript(SCHEMA)
    conn.commit()
    conn.close()

    def salus_read(request: Request) -> None:
        require(request, "read")
        require_salus(request, "SalCAPA commercial planning")

    def salus_write(request: Request) -> None:
        require(request, "write")
        require_salus(request, "SalCAPA commercial planning")

    def commercial_authority(request: Request) -> None:
        require(request, "decide")
        if role(request) not in {"Assessment Director", "System Administrator"}:
            raise HTTPException(403, f"{role(request)} cannot approve commercial terms")

    def card_content(row: dict[str, Any]) -> dict[str, Any]:
        return {
            "id": row["id"], "tenant_id": int(row["tenant_id"]),
            "version_no": int(row["version_no"]), "name": row["name"],
            "effective_from": row["effective_from"], "supersedes_id": row["supersedes_id"],
            "rules": json.loads(row["rules_json"]),
        }

    def verify_card(row: dict[str, Any]) -> None:
        if _digest(card_content(row)) != row["content_sha256"]:
            raise HTTPException(409, "Rate-card integrity verification failed")

    def estimate_content(row: dict[str, Any]) -> dict[str, Any]:
        return {
            "id": row["id"], "tenant_id": int(row["tenant_id"]),
            "version_no": int(row["version_no"]),
            "supersedes_estimate_id": row["supersedes_estimate_id"],
            "engagement_id": row["engagement_id"], "assessment_id": row["assessment_id"],
            "rate_card_id": row["rate_card_id"], "rate_card_version": int(row["rate_card_version"]),
            "inputs": json.loads(row["inputs_json"]),
            "rate_snapshot": json.loads(row["rate_snapshot_json"]),
            "calculation": json.loads(row["calculation_json"]),
        }

    def verify_estimate(row: dict[str, Any]) -> None:
        if _digest(estimate_content(row)) != row["content_sha256"]:
            raise HTTPException(409, "Commercial estimate integrity verification failed")
        if int(row["creates_charge"]) or int(row["creates_invoice"]):
            raise HTTPException(409, "Commercial estimate contains a prohibited billing effect")
        calculation = json.loads(row["calculation_json"])
        summary_fields = {
            "recommended_customer_price_cents": "recommended_customer_price_cents",
            "estimated_internal_cost_cents": "estimated_internal_cost_cents",
            "estimated_margin_cents": "estimated_margin_cents",
            "estimated_margin_basis_points": "estimated_margin_basis_points",
        }
        for column, key in summary_fields.items():
            if row.get(column) != calculation.get(key):
                raise HTTPException(409, "Commercial estimate summary failed integrity verification")

    def time_content(row: dict[str, Any]) -> dict[str, Any]:
        return {
            "id": row["id"], "tenant_id": int(row["tenant_id"]),
            "version_no": int(row["version_no"]), "estimate_id": row["estimate_id"],
            "supersedes_entry_id": row["supersedes_entry_id"],
            "engagement_id": row["engagement_id"], "assessment_id": row["assessment_id"],
            "person_name": row["person_name"], "role_name": row["role_name"],
            "work_date": row["work_date"], "minutes": int(row["minutes"]),
            "work_category": row["work_category"],
            "commercial_treatment": row["commercial_treatment"], "notes": row["notes"],
            "loaded_rate_cents_per_hour": int(row["loaded_rate_cents_per_hour"]),
            "calculated_cost_cents": int(row["calculated_cost_cents"]),
        }

    def cost_content(row: dict[str, Any]) -> dict[str, Any]:
        return {
            "id": row["id"], "tenant_id": int(row["tenant_id"]),
            "version_no": int(row["version_no"]), "estimate_id": row["estimate_id"],
            "supersedes_entry_id": row["supersedes_entry_id"],
            "engagement_id": row["engagement_id"], "assessment_id": row["assessment_id"],
            "cost_category": row["cost_category"], "cost_basis": row["cost_basis"],
            "amount_cents": int(row["amount_cents"]),
            "recognized_actual_cost_cents": int(row["recognized_actual_cost_cents"]),
            "provider_or_payee": row["provider_or_payee"],
            "source_reference": row["source_reference"], "usage_units": row["usage_units"],
            "unit_rate_version": row["unit_rate_version"], "incurred_at": row["incurred_at"],
            "commercial_treatment": row["commercial_treatment"], "notes": row["notes"],
        }

    def verify_actual_entry(row: dict[str, Any], kind: str) -> None:
        content = time_content(row) if kind == "time" else cost_content(row)
        if _digest(content) != row["content_sha256"]:
            raise HTTPException(409, f"Commercial {kind} entry integrity verification failed")
        if int(row["creates_charge"]) or int(row["creates_invoice"]):
            raise HTTPException(409, f"Commercial {kind} entry contains a prohibited billing effect")
        if kind == "cost":
            expected = int(row["amount_cents"]) if row["cost_basis"] in ACTUAL_COST_BASES else 0
            if int(row["recognized_actual_cost_cents"]) != expected:
                raise HTTPException(409, "Cost basis and recognized actual cost do not agree")

    def active_actual_summary(conn, tid: int, estimate_id: str) -> dict[str, Any]:
        time_rows = [dict(r) for r in conn.execute(
            "SELECT * FROM salcapa_time_entries WHERE tenant_id=? AND estimate_id=? ORDER BY version_no",
            (tid, estimate_id),
        )]
        cost_rows = [dict(r) for r in conn.execute(
            "SELECT * FROM salcapa_cost_entries WHERE tenant_id=? AND estimate_id=? ORDER BY version_no",
            (tid, estimate_id),
        )]
        for row in time_rows:
            verify_actual_entry(row, "time")
        for row in cost_rows:
            verify_actual_entry(row, "cost")
        approved_time = [row for row in time_rows if row["status"] == "Approved"]
        approved_cost = [row for row in cost_rows if row["status"] == "Approved"]
        superseded_time = {row["supersedes_entry_id"] for row in approved_time if row["supersedes_entry_id"]}
        superseded_cost = {row["supersedes_entry_id"] for row in approved_cost if row["supersedes_entry_id"]}
        active_time = [row for row in approved_time if row["id"] not in superseded_time]
        active_cost = [row for row in approved_cost if row["id"] not in superseded_cost]
        time_cost = sum(int(row["calculated_cost_cents"]) for row in active_time)
        recognized_direct = sum(int(row["recognized_actual_cost_cents"]) for row in active_cost)
        provisional = sum(
            int(row["amount_cents"]) for row in active_cost
            if row["cost_basis"] in {"Authorized Estimate", "Planning Allowance"}
        )
        unavailable_count = sum(1 for row in active_cost if row["cost_basis"] == "Unavailable")
        return {
            "time_rows": time_rows, "cost_rows": cost_rows,
            "active_time": active_time, "active_cost": active_cost,
            "superseded_time": superseded_time, "superseded_cost": superseded_cost,
            "approved_time_cost_cents": time_cost,
            "approved_direct_actual_cost_cents": recognized_direct,
            "recognized_actual_cost_to_date_cents": time_cost + recognized_direct,
            "approved_provisional_cost_cents": provisional,
            "approved_unavailable_cost_record_count": unavailable_count,
        }

    def actual_snapshot(summary: dict[str, Any]) -> dict[str, Any]:
        return {
            "recognized_actual_cost_to_date_cents": summary["recognized_actual_cost_to_date_cents"],
            "approved_provisional_cost_cents": summary["approved_provisional_cost_cents"],
            "approved_unavailable_cost_record_count": summary["approved_unavailable_cost_record_count"],
            "active_time_entries": [
                {"id": row["id"], "content_sha256": row["content_sha256"]}
                for row in summary["active_time"]
            ],
            "active_cost_entries": [
                {"id": row["id"], "content_sha256": row["content_sha256"]}
                for row in summary["active_cost"]
            ],
        }

    def forecast_content(row: dict[str, Any]) -> dict[str, Any]:
        return {
            "id": row["id"], "tenant_id": int(row["tenant_id"]),
            "version_no": int(row["version_no"]), "estimate_id": row["estimate_id"],
            "supersedes_forecast_id": row["supersedes_forecast_id"],
            "engagement_id": row["engagement_id"], "assessment_id": row["assessment_id"],
            "as_of_date": row["as_of_date"], "forecast_through_date": row["forecast_through_date"],
            "confidence_state": row["confidence_state"],
            "unavailable_cost_handling": row["unavailable_cost_handling"],
            "remaining_labor_minutes": int(row["remaining_labor_minutes"]),
            "loaded_rate_cents_per_hour": int(row["loaded_rate_cents_per_hour"]),
            "forecast_remaining_labor_cost_cents": int(row["forecast_remaining_labor_cost_cents"]),
            "forecast_additional_direct_cost_cents": int(row["forecast_additional_direct_cost_cents"]),
            "actual_snapshot": json.loads(row["actual_snapshot_json"]),
            "assumptions": row["assumptions"], "known_constraints": row["known_constraints"],
            "recognized_actual_cost_to_date_cents": int(row["recognized_actual_cost_to_date_cents"]),
            "approved_provisional_cost_cents": int(row["approved_provisional_cost_cents"]),
            "forecast_to_complete_cents": int(row["forecast_to_complete_cents"]),
            "forecast_at_completion_cents": int(row["forecast_at_completion_cents"]),
            "variance_to_estimated_internal_cost_cents": int(row["variance_to_estimated_internal_cost_cents"]),
            "projected_contribution_cents": int(row["projected_contribution_cents"]),
            "projected_contribution_basis_points": row["projected_contribution_basis_points"],
            "completeness_state": row["completeness_state"],
        }

    def verify_forecast(row: dict[str, Any]) -> None:
        if _digest(forecast_content(row)) != row["content_sha256"]:
            raise HTTPException(409, "Commercial forecast integrity verification failed")
        if int(row["creates_charge"]) or int(row["creates_invoice"]):
            raise HTTPException(409, "Commercial forecast contains a prohibited billing effect")
        snapshot = json.loads(row["actual_snapshot_json"])
        if int(row["recognized_actual_cost_to_date_cents"]) != int(
            snapshot["recognized_actual_cost_to_date_cents"]
        ) or int(row["approved_provisional_cost_cents"]) != int(
            snapshot["approved_provisional_cost_cents"]
        ):
            raise HTTPException(409, "Commercial forecast summary failed integrity verification")

    def forecast_view(row: dict[str, Any]) -> dict[str, Any]:
        out = dict(row)
        out["actual_snapshot"] = json.loads(out.pop("actual_snapshot_json"))
        out["creates_charge"] = bool(out["creates_charge"])
        out["creates_invoice"] = bool(out["creates_invoice"])
        return out

    def actual_view(row: dict[str, Any], kind: str) -> dict[str, Any]:
        out = dict(row)
        out["entry_type"] = kind
        out["creates_charge"] = bool(out["creates_charge"])
        out["creates_invoice"] = bool(out["creates_invoice"])
        return out

    def estimate_for_actuals(conn, request: Request, estimate_id: str) -> dict[str, Any]:
        found = conn.execute(
            "SELECT * FROM salcapa_commercial_estimates WHERE id=? AND tenant_id=?",
            (estimate_id, tenant_id(request)),
        ).fetchone()
        if not found:
            raise HTTPException(404, "Commercial estimate not found")
        estimate = dict(found)
        verify_estimate(estimate)
        if estimate["status"] not in {"Approved", "Released"}:
            raise HTTPException(409, "Actual cost may be recorded only against an Approved or Released estimate")
        return estimate

    def active_approved_forecast(conn, tid: int, estimate_id: str) -> Optional[dict[str, Any]]:
        found = conn.execute(
            """SELECT f.* FROM salcapa_commercial_forecasts f
               WHERE f.tenant_id=? AND f.estimate_id=? AND f.status='Approved'
                 AND NOT EXISTS (
                   SELECT 1 FROM salcapa_commercial_forecasts successor
                   WHERE successor.tenant_id=f.tenant_id
                     AND successor.supersedes_forecast_id=f.id
                     AND successor.status='Approved'
                 )
               ORDER BY f.version_no DESC LIMIT 1""",
            (tid, estimate_id),
        ).fetchone()
        return dict(found) if found else None

    def member_view(row: dict[str, Any]) -> dict[str, Any]:
        return {
            "id": row["id"], "version_no": int(row["version_no"]),
            "engagement_id": row["engagement_id"], "assessment_id": row["assessment_id"],
            "product_line": row["product_line"], "domain_key": row["domain_key"],
            "investigation_tier": row["investigation_tier"],
            "pricing_method": row["pricing_method"], "customer_summary": row["customer_summary"],
            "approved_customer_price_cents": row["approved_customer_price_cents"],
            "currency": row["currency"], "status": row["status"], "released_at": row["released_at"],
            "creates_charge": False, "creates_invoice": False,
        }

    def full_view(row: dict[str, Any]) -> dict[str, Any]:
        out = dict(row)
        out["inputs"] = json.loads(out.pop("inputs_json"))
        out["rate_snapshot"] = json.loads(out.pop("rate_snapshot_json"))
        out["calculation"] = json.loads(out.pop("calculation_json"))
        out["creates_charge"] = bool(out["creates_charge"])
        out["creates_invoice"] = bool(out["creates_invoice"])
        return out

    def plan_content(row: dict[str, Any]) -> dict[str, Any]:
        return {
            "id": row["id"], "tenant_id": int(row["tenant_id"]),
            "version_no": int(row["version_no"]),
            "supersedes_plan_id": row["supersedes_plan_id"],
            "name": row["name"], "arrangement": row["arrangement"],
            "effective_from": row["effective_from"],
            "entitlements": json.loads(row["entitlements_json"]),
            "portfolio_pricing": json.loads(row["portfolio_pricing_json"]),
            "member_summary": row["member_summary"], "internal_basis": row["internal_basis"],
        }

    def verify_membership_plan(row: dict[str, Any]) -> None:
        if _digest(plan_content(row)) != row["content_sha256"]:
            raise HTTPException(409, "Protected Membership plan integrity verification failed")

    def membership_plan_view(row: dict[str, Any]) -> dict[str, Any]:
        out = dict(row)
        out["entitlements"] = json.loads(out.pop("entitlements_json"))
        out["portfolio_pricing"] = json.loads(out.pop("portfolio_pricing_json"))
        return out

    def term_content(row: dict[str, Any]) -> dict[str, Any]:
        return {
            "id": row["id"], "tenant_id": int(row["tenant_id"]),
            "version_no": int(row["version_no"]),
            "supersedes_term_id": row["supersedes_term_id"],
            "plan_id": row["plan_id"], "plan_version": int(row["plan_version"]),
            "plan_snapshot": json.loads(row["plan_snapshot_json"]),
            "contract_reference": row["contract_reference"],
            "start_date": row["start_date"], "end_date": row["end_date"],
            "renewal_review_date": row["renewal_review_date"],
            "billing_cadence": row["billing_cadence"],
            "recurring_fee_cents": int(row["recurring_fee_cents"]),
            "approved_term_value_cents": int(row["approved_term_value_cents"]),
            "portfolio_coverage": json.loads(row["portfolio_coverage_json"]),
            "negotiated_terms": row["negotiated_terms"], "internal_basis": row["internal_basis"],
        }

    def verify_membership_term(row: dict[str, Any]) -> None:
        if _digest(term_content(row)) != row["content_sha256"]:
            raise HTTPException(409, "Protected Membership term integrity verification failed")
        prohibited = (
            "creates_charge", "creates_invoice", "creates_entitlement_automatically",
            "authorizes_scope_automatically", "auto_renews",
        )
        if any(int(row[field]) for field in prohibited):
            raise HTTPException(409, "Protected Membership term contains a prohibited automatic effect")

    def consumption_content(row: dict[str, Any]) -> dict[str, Any]:
        return {
            "id": row["id"], "tenant_id": int(row["tenant_id"]),
            "version_no": int(row["version_no"]), "term_id": row["term_id"],
            "supersedes_consumption_id": row["supersedes_consumption_id"],
            "entitlement_key": row["entitlement_key"],
            "entitlement_snapshot": json.loads(row["entitlement_snapshot_json"]),
            "quantity": row["quantity"], "occurred_on": row["occurred_on"],
            "source_type": row["source_type"], "source_record_id": row["source_record_id"],
            "source_reference": row["source_reference"], "estimate_id": row["estimate_id"],
            "notes": row["notes"],
        }

    def verify_membership_consumption(row: dict[str, Any]) -> None:
        if _digest(consumption_content(row)) != row["content_sha256"]:
            raise HTTPException(409, "Protected Membership consumption integrity verification failed")
        if any(int(row[field]) for field in (
            "creates_charge", "creates_invoice", "creates_scope_authorization",
        )):
            raise HTTPException(409, "Protected Membership consumption contains a prohibited automatic effect")

    def active_membership_consumption(conn, tid: int, term_id: str) -> list[dict[str, Any]]:
        rows = [dict(row) for row in conn.execute(
            "SELECT * FROM salcapa_membership_consumption WHERE tenant_id=? AND term_id=? ORDER BY version_no",
            (tid, term_id),
        )]
        for row in rows:
            verify_membership_consumption(row)
        approved = [row for row in rows if row["status"] == "Approved"]
        superseded = {
            row["supersedes_consumption_id"] for row in approved if row["supersedes_consumption_id"]
        }
        return [row for row in approved if row["id"] not in superseded]

    def membership_capacity(conn, row: dict[str, Any],
                            proposed: Optional[tuple[str, Decimal]] = None) -> list[dict[str, Any]]:
        entitlements = json.loads(row["plan_snapshot_json"])["entitlements"]
        consumption = active_membership_consumption(conn, int(row["tenant_id"]), row["id"])
        used: dict[str, Decimal] = {}
        for item in consumption:
            used[item["entitlement_key"]] = used.get(item["entitlement_key"], Decimal("0")) + Decimal(
                item["quantity"]
            )
        if proposed:
            key, quantity = proposed
            used[key] = used.get(key, Decimal("0")) + quantity
        capacity: list[dict[str, Any]] = []
        for entitlement in entitlements:
            quantity = used.get(entitlement["key"], Decimal("0"))
            limit_value = entitlement.get("included_quantity")
            limit = Decimal(str(limit_value)) if limit_value is not None else None
            remaining = max(limit - quantity, Decimal("0")) if limit is not None else None
            excess = max(quantity - limit, Decimal("0")) if limit is not None else Decimal("0")
            requires_separate = (
                excess > 0
                or entitlement["treatment"] in {"Separately Quoted", "Pass-Through", "Not Included"}
            )
            capacity.append({
                "entitlement_key": entitlement["key"], "label": entitlement["label"],
                "product_line": entitlement["product_line"],
                "service_scope": entitlement["service_scope"],
                "commercial_treatment": entitlement["treatment"],
                "capacity_type": entitlement["capacity_type"], "unit": entitlement["unit"],
                "included_quantity": None if limit is None else format(limit, "f"),
                "approved_consumption": format(quantity, "f"),
                "remaining_quantity": None if remaining is None else format(remaining, "f"),
                "quantity_requiring_separate_authorization": format(excess, "f"),
                "authorization_state": (
                    "Separate Authorization Required" if requires_separate
                    else "Within Approved Entitlement"
                ),
                "next_step": (
                    "Prepare a governed add-on, estimate, or membership amendment for authorized review."
                    if requires_separate else
                    "Continue within the released term and record supported consumption for review."
                ),
                "member_description": entitlement["member_description"],
            })
        return capacity

    def recurring_values(row: dict[str, Any]) -> tuple[Optional[int], Optional[int]]:
        fee = int(row["recurring_fee_cents"])
        cadence = row["billing_cadence"]
        if cadence == "Monthly":
            return fee, fee * 12
        if cadence == "Quarterly":
            return _money(Decimal(fee) / Decimal(3)), fee * 4
        if cadence == "Annual":
            return _money(Decimal(fee) / Decimal(12)), fee
        return None, None

    def membership_economics(conn, row: dict[str, Any]) -> dict[str, Any]:
        consumption = active_membership_consumption(conn, int(row["tenant_id"]), row["id"])
        estimate_ids = sorted({item["estimate_id"] for item in consumption if item["estimate_id"]})
        recognized_cost = 0
        forecast_cost = 0
        unavailable_count = 0
        forecasts_used = 0
        for estimate_id in estimate_ids:
            found = conn.execute(
                "SELECT * FROM salcapa_commercial_estimates WHERE id=? AND tenant_id=?",
                (estimate_id, row["tenant_id"]),
            ).fetchone()
            if not found:
                raise HTTPException(409, "Membership consumption references a missing estimate")
            estimate = dict(found)
            verify_estimate(estimate)
            actuals = active_actual_summary(conn, int(row["tenant_id"]), estimate_id)
            actual_cost = int(actuals["recognized_actual_cost_to_date_cents"])
            recognized_cost += actual_cost
            unavailable_count += int(actuals["approved_unavailable_cost_record_count"])
            forecast = active_approved_forecast(conn, int(row["tenant_id"]), estimate_id)
            if forecast:
                verify_forecast(forecast)
                forecast_cost += int(forecast["forecast_at_completion_cents"])
                forecasts_used += 1
            else:
                forecast_cost += actual_cost
        monthly, annual = recurring_values(row)
        term_value = int(row["approved_term_value_cents"])
        planning_contribution = term_value - forecast_cost
        contribution_bps = None if term_value <= 0 else _money(
            Decimal(planning_contribution) * Decimal(10000) / Decimal(term_value)
        )
        if not estimate_ids:
            evidence_state = "Awaiting Validation"
        elif unavailable_count or forecasts_used < len(estimate_ids):
            evidence_state = "Evidence Needed"
        else:
            evidence_state = "Reasonably Supported"
        return {
            "monthly_recurring_value_cents": monthly,
            "annualized_recurring_value_cents": annual,
            "approved_term_value_cents": term_value,
            "linked_estimate_count": len(estimate_ids),
            "recognized_cost_to_serve_cents": recognized_cost,
            "forecast_cost_to_serve_cents": forecast_cost,
            "planning_contribution_cents": planning_contribution,
            "planning_contribution_basis_points": contribution_bps,
            "evidence_state": evidence_state,
            "unavailable_cost_record_count": unavailable_count,
            "interpretation": (
                "Salus-only planning economics based on approved term values and governed cost records. "
                "They are not financial statements, recognized revenue or margin, a customer charge, or an invoice."
            ),
        }

    def membership_term_view(conn, row: dict[str, Any], member: bool) -> dict[str, Any]:
        capacity = membership_capacity(conn, row)
        plan = json.loads(row["plan_snapshot_json"])
        common = {
            "id": row["id"], "version_no": int(row["version_no"]),
            "plan_name": plan["name"], "plan_version": int(row["plan_version"]),
            "arrangement": plan["arrangement"], "contract_reference": row["contract_reference"],
            "start_date": row["start_date"], "end_date": row["end_date"],
            "renewal_review_date": row["renewal_review_date"],
            "billing_cadence": row["billing_cadence"],
            "recurring_fee_cents": int(row["recurring_fee_cents"]),
            "approved_term_value_cents": int(row["approved_term_value_cents"]),
            "portfolio_coverage": json.loads(row["portfolio_coverage_json"]),
            "member_summary": plan["member_summary"], "status": row["status"],
            "released_at": row["released_at"], "capacity": capacity,
            "creates_charge": False, "creates_invoice": False,
            "creates_entitlement_automatically": False,
            "authorizes_scope_automatically": False, "auto_renews": False,
            "next_step": (
                "Review remaining capacity and ask Salus to prepare an authorized change when needs exceed the released term."
            ),
        }
        if member:
            common["visibility"] = (
                "Released information for this Protected Member only. Internal rates, costs, calculations, "
                "partner economics, margin, and profitability are withheld."
            )
            return common
        common.update({
            "tenant_id": int(row["tenant_id"]), "supersedes_term_id": row["supersedes_term_id"],
            "plan_id": row["plan_id"], "plan_snapshot": plan,
            "negotiated_terms": row["negotiated_terms"], "internal_basis": row["internal_basis"],
            "content_sha256": row["content_sha256"], "created_by": row["created_by"],
            "created_at": row["created_at"], "submitted_by": row["submitted_by"],
            "submitted_at": row["submitted_at"], "approved_by": row["approved_by"],
            "approved_at": row["approved_at"], "released_by": row["released_by"],
            "decision_reason": row["decision_reason"], "release_reason": row["release_reason"],
            "updated_at": row["updated_at"], "economics": membership_economics(conn, row),
        })
        return common

    def membership_consumption_view(conn, row: dict[str, Any]) -> dict[str, Any]:
        term = conn.execute(
            "SELECT * FROM salcapa_membership_terms WHERE id=? AND tenant_id=?",
            (row["term_id"], row["tenant_id"]),
        ).fetchone()
        if not term:
            raise HTTPException(409, "Protected Membership consumption term is missing")
        out = dict(row)
        out["entitlement_snapshot"] = json.loads(out.pop("entitlement_snapshot_json"))
        out["creates_charge"] = False
        out["creates_invoice"] = False
        out["creates_scope_authorization"] = False
        projected = membership_capacity(
            conn, dict(term),
            None if row["status"] == "Approved" else (row["entitlement_key"], Decimal(row["quantity"])),
        )
        out["capacity_analysis"] = next(
            item for item in projected if item["entitlement_key"] == row["entitlement_key"]
        )
        return out

    def wip_source_snapshot(conn, tid: int, estimate_id: str,
                            through: str) -> dict[str, Any]:
        found = conn.execute(
            "SELECT * FROM salcapa_commercial_estimates WHERE id=? AND tenant_id=?",
            (estimate_id, tid),
        ).fetchone()
        if not found:
            raise HTTPException(404, "Commercial estimate not found")
        estimate = dict(found)
        verify_estimate(estimate)
        if estimate["status"] not in {"Approved", "Released"}:
            raise HTTPException(409, "WIP review requires an Approved or Released estimate")
        actuals = active_actual_summary(conn, tid, estimate_id)
        time_rows = [row for row in actuals["active_time"] if row["work_date"] <= through]
        cost_rows = [row for row in actuals["active_cost"] if row["incurred_at"][:10] <= through]
        membership_rows = [dict(row) for row in conn.execute(
            """SELECT * FROM salcapa_membership_consumption
               WHERE tenant_id=? AND estimate_id=? AND status='Approved' AND occurred_on<=?
               ORDER BY version_no""",
            (tid, estimate_id, through),
        )]
        for row in membership_rows:
            verify_membership_consumption(row)
        superseded_membership = {
            row["supersedes_consumption_id"] for row in membership_rows
            if row["supersedes_consumption_id"]
        }
        membership_rows = [row for row in membership_rows if row["id"] not in superseded_membership]
        time_cost = sum(int(row["calculated_cost_cents"]) for row in time_rows)
        direct_actual = sum(int(row["recognized_actual_cost_cents"]) for row in cost_rows)
        provisional = sum(
            int(row["amount_cents"]) for row in cost_rows
            if row["cost_basis"] in {"Authorized Estimate", "Planning Allowance"}
        )
        unavailable = sum(1 for row in cost_rows if row["cost_basis"] == "Unavailable")
        return {
            "estimate": {
                "id": estimate["id"], "version_no": int(estimate["version_no"]),
                "content_sha256": estimate["content_sha256"], "status": estimate["status"],
                "approved_customer_price_cents": int(estimate["approved_customer_price_cents"] or 0),
                "currency": estimate["currency"],
            },
            "work_through_date": through,
            "active_time_entries": [
                {"id": row["id"], "content_sha256": row["content_sha256"],
                 "work_date": row["work_date"], "minutes": int(row["minutes"]),
                 "commercial_treatment": row["commercial_treatment"]}
                for row in time_rows
            ],
            "active_cost_entries": [
                {"id": row["id"], "content_sha256": row["content_sha256"],
                 "incurred_at": row["incurred_at"], "cost_basis": row["cost_basis"],
                 "commercial_treatment": row["commercial_treatment"]}
                for row in cost_rows
            ],
            "active_membership_consumption": [
                {"id": row["id"], "content_sha256": row["content_sha256"],
                 "term_id": row["term_id"], "entitlement_key": row["entitlement_key"],
                 "quantity": row["quantity"], "occurred_on": row["occurred_on"]}
                for row in membership_rows
            ],
            "approved_time_minutes": sum(int(row["minutes"]) for row in time_rows),
            "recognized_time_cost_cents": time_cost,
            "recognized_direct_actual_cost_cents": direct_actual,
            "recognized_actual_cost_cents": time_cost + direct_actual,
            "approved_provisional_cost_cents": provisional,
            "unavailable_cost_record_count": unavailable,
            "work_evidence_record_count": len(time_rows) + len(cost_rows) + len(membership_rows),
        }

    def wip_content(row: dict[str, Any]) -> dict[str, Any]:
        return {
            "id": row["id"], "tenant_id": int(row["tenant_id"]),
            "version_no": int(row["version_no"]), "estimate_id": row["estimate_id"],
            "supersedes_wip_review_id": row["supersedes_wip_review_id"],
            "engagement_id": row["engagement_id"], "assessment_id": row["assessment_id"],
            "as_of_date": row["as_of_date"], "work_through_date": row["work_through_date"],
            "commercial_disposition": row["commercial_disposition"],
            "work_value_cents": int(row["work_value_cents"]),
            "billing_authorized_amount_cents": int(row["billing_authorized_amount_cents"]),
            "external_billing_reference": row["external_billing_reference"],
            "source_snapshot": json.loads(row["source_snapshot_json"]),
            "review_basis": row["review_basis"], "assumptions": row["assumptions"],
            "known_gaps": row["known_gaps"], "evidence_state": row["evidence_state"],
        }

    def verify_wip_review(row: dict[str, Any]) -> None:
        if _digest(wip_content(row)) != row["content_sha256"]:
            raise HTTPException(409, "Unbilled/work-in-progress review integrity verification failed")
        if any(int(row[field]) for field in (
            "creates_charge", "creates_invoice", "recognizes_revenue", "transmits_externally",
        )):
            raise HTTPException(409, "Unbilled/work-in-progress review contains a prohibited effect")
        snapshot = json.loads(row["source_snapshot_json"])
        if int(snapshot["work_evidence_record_count"]) <= 0:
            raise HTTPException(409, "Unbilled/work-in-progress review lacks governed work evidence")

    def wip_view(row: dict[str, Any]) -> dict[str, Any]:
        out = dict(row)
        out["source_snapshot"] = json.loads(out.pop("source_snapshot_json"))
        out["creates_charge"] = False
        out["creates_invoice"] = False
        out["recognizes_revenue"] = False
        out["transmits_externally"] = False
        out["authority_note"] = (
            "The approved disposition is a Salus commercial review record. Authorized-for-billing means "
            "the recorded amount may proceed to a separate billing process; this record does not create a charge or invoice."
        )
        out["accounting_note"] = (
            "Work value and WIP status are management information, not recognized revenue, a financial statement, "
            "a customer balance, or evidence that an invoice was sent or paid."
        )
        out["next_step"] = (
            "Complete the separate authorized billing process and record its evidence by governed reference."
            if row["status"] == "Approved" and row["commercial_disposition"] == "Authorized for Billing"
            else "Review source completeness and revise the dated disposition when work or commercial facts change."
        )
        return out

    def active_wip_review(conn, tid: int, estimate_id: str) -> Optional[dict[str, Any]]:
        found = conn.execute(
            """SELECT w.* FROM salcapa_wip_reviews w
               WHERE w.tenant_id=? AND w.estimate_id=? AND w.status='Approved'
                 AND NOT EXISTS (
                   SELECT 1 FROM salcapa_wip_reviews successor
                   WHERE successor.tenant_id=w.tenant_id
                     AND successor.supersedes_wip_review_id=w.id
                     AND successor.status='Approved'
                 )
               ORDER BY w.version_no DESC LIMIT 1""",
            (tid, estimate_id),
        ).fetchone()
        return dict(found) if found else None

    def wip_management_summary(conn, tid: int, as_of: date) -> dict[str, Any]:
        rows = [dict(row) for row in conn.execute(
            """SELECT * FROM salcapa_wip_reviews
               WHERE tenant_id=? AND status='Approved' AND as_of_date<=?
               ORDER BY version_no""",
            (tid, as_of.isoformat()),
        )]
        for row in rows:
            verify_wip_review(row)
        superseded = {
            row["supersedes_wip_review_id"] for row in rows if row["supersedes_wip_review_id"]
        }
        active = [row for row in rows if row["id"] not in superseded]
        groups: dict[str, dict[str, Any]] = {}
        for row in active:
            group = groups.setdefault(row["commercial_disposition"], {
                "commercial_disposition": row["commercial_disposition"],
                "current_review_count": 0, "work_value_cents": 0,
                "billing_authorized_amount_cents": 0,
                "recognized_actual_cost_cents": 0,
                "evidence_needed_count": 0,
            })
            snapshot = json.loads(row["source_snapshot_json"])
            group["current_review_count"] += 1
            group["work_value_cents"] += int(row["work_value_cents"])
            group["billing_authorized_amount_cents"] += int(row["billing_authorized_amount_cents"])
            group["recognized_actual_cost_cents"] += int(snapshot["recognized_actual_cost_cents"])
            if row["evidence_state"] != "Reasonably Supported":
                group["evidence_needed_count"] += 1
        ordered = [groups[key] for key in sorted(groups, key=str.casefold)]
        totals = {
            "current_review_count": len(active),
            "work_value_cents": sum(int(row["work_value_cents"]) for row in active),
            "billing_authorized_amount_cents": sum(
                int(row["billing_authorized_amount_cents"]) for row in active
            ),
            "recognized_actual_cost_cents": sum(
                int(json.loads(row["source_snapshot_json"])["recognized_actual_cost_cents"])
                for row in active
            ),
            "evidence_needed_count": sum(
                1 for row in active if row["evidence_state"] != "Reasonably Supported"
            ),
        }
        return {
            "scope": {"protected_member_id": tid, "as_of_date": as_of.isoformat()},
            "purpose": "Review current approved unbilled/work-in-progress dispositions within one governed Protected Member scope.",
            "basis": "Each current record is a dated human-approved snapshot of governed work evidence and commercial treatment.",
            "confidentiality": "Salus-only commercial management information; no cross-member aggregation or Protected Member disclosure is permitted.",
            "interpretation": "These values are not recognized revenue, financial statements, customer balances, charges, invoices, or proof of payment.",
            "totals": totals, "groups": ordered,
            "creates_charge": False, "creates_invoice": False,
            "recognizes_revenue": False, "transmits_externally": False,
        }

    def report_date(value: str, field_name: str) -> date:
        try:
            return date.fromisoformat(value)
        except ValueError as exc:
            raise HTTPException(422, f"{field_name} must be a valid ISO date") from exc

    def report_group_label(row: dict[str, Any], group_by: str) -> str:
        if group_by == "Product Line":
            return row["product_line"]
        if group_by == "Investigative Domain":
            return row["domain_key"] or "Not Specified"
        if group_by == "Tier":
            return row["investigation_tier"]
        if group_by == "Engagement":
            return f"Engagement {row['engagement_id']}" if row["engagement_id"] else "Not Assigned"
        return row["pricing_method"]

    def management_report(conn, tid: int, start: date, end: date,
                          group_by: str) -> dict[str, Any]:
        rows = [dict(r) for r in conn.execute(
            "SELECT * FROM salcapa_commercial_estimates WHERE tenant_id=? ORDER BY version_no",
            (tid,),
        )]
        for row in rows:
            verify_estimate(row)
        governed = [row for row in rows if row["status"] in {"Approved", "Released"}]
        superseded = {
            row["supersedes_estimate_id"] for row in governed if row["supersedes_estimate_id"]
        }
        active = [
            row for row in governed
            if row["id"] not in superseded and date.fromisoformat(row["created_at"][:10]) <= end
        ]
        groups: dict[str, dict[str, Any]] = {}
        for estimate in active:
            label = report_group_label(estimate, group_by)
            group = groups.setdefault(label, {
                "group": label,
                "active_estimate_count": 0,
                "new_estimate_count": 0,
                "released_estimate_count": 0,
                "approved_customer_price_cents": 0,
                "estimated_internal_cost_cents": 0,
                "approved_estimated_contribution_cents": 0,
                "period_time_minutes": 0,
                "period_time_cost_cents": 0,
                "period_direct_actual_cost_cents": 0,
                "period_recognized_actual_cost_cents": 0,
                "period_provisional_cost_cents": 0,
                "period_unavailable_cost_record_count": 0,
                "current_approved_forecast_count": 0,
                "current_forecast_at_completion_cents": 0,
                "current_projected_contribution_cents": 0,
                "support_state": "Reasonably Supported",
            })
            group["active_estimate_count"] += 1
            created_date = date.fromisoformat(estimate["created_at"][:10])
            if start <= created_date <= end:
                group["new_estimate_count"] += 1
            if estimate["status"] == "Released":
                group["released_estimate_count"] += 1
            approved_price = int(estimate["approved_customer_price_cents"] or 0)
            estimated_internal = int(estimate["estimated_internal_cost_cents"])
            group["approved_customer_price_cents"] += approved_price
            group["estimated_internal_cost_cents"] += estimated_internal
            group["approved_estimated_contribution_cents"] += approved_price - estimated_internal

            actuals = active_actual_summary(conn, tid, estimate["id"])
            period_time = [
                row for row in actuals["active_time"]
                if start <= date.fromisoformat(row["work_date"]) <= end
            ]
            period_cost = [
                row for row in actuals["active_cost"]
                if start <= date.fromisoformat(row["incurred_at"][:10]) <= end
            ]
            time_minutes = sum(int(row["minutes"]) for row in period_time)
            time_cost = sum(int(row["calculated_cost_cents"]) for row in period_time)
            direct_actual = sum(int(row["recognized_actual_cost_cents"]) for row in period_cost)
            provisional = sum(
                int(row["amount_cents"]) for row in period_cost
                if row["cost_basis"] in {"Authorized Estimate", "Planning Allowance"}
            )
            unavailable = sum(1 for row in period_cost if row["cost_basis"] == "Unavailable")
            group["period_time_minutes"] += time_minutes
            group["period_time_cost_cents"] += time_cost
            group["period_direct_actual_cost_cents"] += direct_actual
            group["period_recognized_actual_cost_cents"] += time_cost + direct_actual
            group["period_provisional_cost_cents"] += provisional
            group["period_unavailable_cost_record_count"] += unavailable

            forecast_rows = [dict(r) for r in conn.execute(
                """SELECT * FROM salcapa_commercial_forecasts
                   WHERE tenant_id=? AND estimate_id=? AND status='Approved' AND as_of_date<=?
                   ORDER BY version_no""",
                (tid, estimate["id"], end.isoformat()),
            )]
            for forecast in forecast_rows:
                verify_forecast(forecast)
            superseded_forecasts = {
                row["supersedes_forecast_id"] for row in forecast_rows
                if row["supersedes_forecast_id"]
            }
            current_forecasts = [
                row for row in forecast_rows if row["id"] not in superseded_forecasts
            ]
            current = current_forecasts[-1] if current_forecasts else None
            if current:
                group["current_approved_forecast_count"] += 1
                group["current_forecast_at_completion_cents"] += int(
                    current["forecast_at_completion_cents"]
                )
                group["current_projected_contribution_cents"] += int(
                    current["projected_contribution_cents"]
                )
                if current["completeness_state"] == "Evidence Needed":
                    group["support_state"] = "Evidence Needed"
                elif (current["completeness_state"] == "Awaiting Validation"
                      and group["support_state"] != "Evidence Needed"):
                    group["support_state"] = "Awaiting Validation"
            elif group["support_state"] == "Reasonably Supported":
                group["support_state"] = "Awaiting Validation"
            if unavailable:
                group["support_state"] = "Evidence Needed"

        ordered = [groups[key] for key in sorted(groups, key=lambda value: value.lower())]
        numeric_fields = [
            key for key in next(iter(groups.values()), {})
            if key != "group" and key != "support_state"
        ]
        totals = {field: sum(int(row[field]) for row in ordered) for field in numeric_fields}
        support_states = {row["support_state"] for row in ordered}
        if "Evidence Needed" in support_states:
            overall_support = "Evidence Needed"
        elif "Awaiting Validation" in support_states or not ordered:
            overall_support = "Awaiting Validation"
        else:
            overall_support = "Reasonably Supported"
        totals["support_state"] = overall_support
        return {
            "scope": {
                "protected_member_id": tid,
                "start_date": start.isoformat(),
                "end_date": end.isoformat(),
                "group_by": group_by,
            },
            "record_state_basis": (
                "Current Approved or Released estimate versions created on or before the period end; "
                "dated work and cost figures include only active Approved records within the period."
            ),
            "forecast_basis": (
                "Latest active Approved forecast with an as-of date on or before the period end. "
                "A forecast remains a planning judgment and may require further evidence."
            ),
            "confidentiality": (
                "Salus-only commercial management information for the active Protected Member scope. "
                "It is not available in Protected Member views or across member boundaries."
            ),
            "interpretation": (
                "This management view is not a financial statement, recognized revenue or margin, "
                "customer charge, invoice, scope authorization, entitlement, or commitment."
            ),
            "support_state": overall_support,
            "totals": totals,
            "groups": ordered,
            "creates_charge": False,
            "creates_invoice": False,
            "authorizes_scope": False,
        }

    def management_report_csv(report: dict[str, Any]) -> str:
        def safe(value: Any) -> Any:
            if isinstance(value, str) and value[:1] in {"=", "+", "-", "@", "\t", "\r"}:
                return "'" + value
            return value

        fields = [
            "group", "support_state", "active_estimate_count", "new_estimate_count",
            "released_estimate_count", "approved_customer_price_cents",
            "estimated_internal_cost_cents", "approved_estimated_contribution_cents",
            "period_time_minutes", "period_time_cost_cents",
            "period_direct_actual_cost_cents", "period_recognized_actual_cost_cents",
            "period_provisional_cost_cents", "period_unavailable_cost_record_count",
            "current_approved_forecast_count", "current_forecast_at_completion_cents",
            "current_projected_contribution_cents",
        ]
        stream = io.StringIO(newline="")
        writer = csv.DictWriter(stream, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        for row in report["groups"]:
            writer.writerow({key: safe(value) for key, value in row.items()})
        return stream.getvalue()

    @app.get("/api/salcapa/commercial/catalog")
    def commercial_catalog(request: Request):
        salus_read(request)
        return {
            "product_lines": list(PRODUCT_LINES), "investigation_tiers": list(TIERS),
            "complexities": list(COMPLEXITIES), "pricing_methods": list(PRICING_METHODS),
            "monitoring_services": list(MONITORING_SERVICES),
            "rate_override_precedence": list(RATE_OVERRIDE_LEVELS),
            "management_report_groups": list(REPORT_GROUPS),
            "work_categories": list(WORK_CATEGORIES),
            "time_commercial_treatments": list(COMMERCIAL_TREATMENTS),
            "cost_categories": list(COST_CATEGORIES), "cost_bases": list(COST_BASES),
            "cost_commercial_treatments": list(PARTNER_TREATMENTS),
            "membership_arrangements": list(MEMBERSHIP_ARRANGEMENTS),
            "membership_billing_cadences": list(MEMBERSHIP_BILLING_CADENCES),
            "membership_commercial_treatments": list(MEMBERSHIP_TREATMENTS),
            "membership_capacity_types": list(MEMBERSHIP_CAPACITY_TYPES),
            "membership_source_types": list(MEMBERSHIP_SOURCE_TYPES),
            "wip_dispositions": list(WIP_DISPOSITIONS),
            "initial_planning_defaults": json.loads(_canonical(DEFAULT_RULES)),
            "guidance": {
                "purpose": "Prepare a transparent planning estimate for authorized Salus review.",
                "authority": "Authorized Salus personnel configure assumptions and independently approve customer price.",
                "consequence": "A recommendation is not a charge, invoice, entitlement, scope authorization, or customer commitment.",
                "next_step": "Submit the immutable estimate for independent commercial review, then release approved customer-facing terms separately.",
                "actual_cost_truth": "When actual provider or labor cost is unavailable, the planning allowance remains clearly identified rather than presented as metered actual cost.",
                "actuals_authority": "Salus personnel record work and cost evidence; a different authorized person approves what becomes recognized actual cost.",
                "actuals_consequence": "An approved actual-cost record updates internal cost visibility only. It does not charge a Protected Member or create an invoice.",
                "forecast_purpose": "Prepare a dated internal view of recorded cost, supported remaining work, unresolved cost, and expected cost at completion.",
                "forecast_uncertainty": "A forecast is a planning judgment, not a final cost. It shows its evidence state, assumptions, constraints, unavailable-cost handling, and source-record snapshot.",
                "forecast_authority": "A different authorized Salus person must approve the forecast, and changed source records require a new forecast rather than a silent update.",
                "forecast_consequence": "An approved forecast informs Salus planning only. It does not alter scope, customer price, margin recognition, charges, invoices, or commitments.",
                "report_purpose": "Review current approved commercial positions and dated cost activity within one governed Protected Member scope.",
                "report_uncertainty": "Management totals distinguish recognized actual cost, provisional amounts, unavailable cost records, and approved forecasts; they are not financial statements or final margin recognition.",
                "report_confidentiality": "Commercial management reports are Salus-only and do not expose internal rates, costs, calculations, or margins to Protected Members.",
                "membership_distinction": "Protected Membership defines a recurring commercial relationship and explicit capacity. Investigation Tier 1, Tier 2, and Tier 3 define authorized investigative depth only.",
                "membership_authority": "Authorized Salus personnel independently approve plan versions, member terms, consumption records, and any add-on or amendment.",
                "membership_consequence": "Recording use or reaching a capacity limit does not create a charge, invoice, scope expansion, tier change, partner action, renewal, or customer commitment.",
                "membership_next_step": "When a released entitlement does not cover requested work, prepare a governed add-on, estimate, or membership amendment for human review.",
                "membership_confidentiality": "Protected Members see only their released term, covered scope, approved consumption, and remaining capacity. Salus rates, costs, partner economics, calculations, margin, and profitability remain Salus-only.",
                "wip_purpose": "Prepare a dated Salus review of supported work value and its current commercial treatment.",
                "wip_authority": "Authorized Salus personnel independently approve each disposition. Authorized for Billing permits a separate billing process to begin; it does not create a charge or invoice.",
                "wip_consequence": "A WIP review does not recognize revenue, change scope or price, transmit information, charge a Protected Member, or create an invoice.",
                "wip_uncertainty": "The review identifies its source snapshot, assumptions, known gaps, and evidence state. Changed work or cost records require a new governed revision.",
                "wip_confidentiality": "Unbilled/work-in-progress reviews and summaries are Salus-only commercial management information within one Protected Member scope.",
                "wip_next_step": "Resolve evidence gaps or complete the separately authorized billing process, then record later billing evidence by governed reference without rewriting this review.",
            },
        }

    @app.get("/api/salcapa/commercial/management-report")
    def commercial_management_report(request: Request, start_date: str, end_date: str,
                                     group_by: Literal[
                                         "Product Line", "Investigative Domain", "Tier",
                                         "Engagement", "Pricing Method",
                                     ] = "Product Line",
                                     export: Literal["json", "csv"] = "json"):
        salus_read(request)
        start = report_date(start_date, "start_date")
        end = report_date(end_date, "end_date")
        if end < start:
            raise HTTPException(422, "end_date cannot precede start_date")
        if (end - start).days > 366:
            raise HTTPException(422, "Commercial reporting periods are limited to 367 days")
        conn = db()
        try:
            report = management_report(conn, tenant_id(request), start, end, group_by)
        finally:
            conn.close()
        if export == "csv":
            filename = f"salcapa-commercial-{start.isoformat()}-{end.isoformat()}.csv"
            return Response(
                content=management_report_csv(report),
                media_type="text/csv",
                headers={"Content-Disposition": f'attachment; filename="{filename}"'},
            )
        return report

    @app.get("/api/salcapa/commercial/rate-cards")
    def list_rate_cards(request: Request):
        salus_read(request)
        conn = db()
        rows = [dict(r) for r in conn.execute(
            "SELECT * FROM salcapa_rate_cards WHERE tenant_id=? ORDER BY version_no DESC", (tenant_id(request),)
        )]
        conn.close()
        for row in rows:
            verify_card(row)
            row["rules"] = json.loads(row.pop("rules_json"))
        return rows

    @app.post("/api/salcapa/commercial/rate-cards")
    def create_rate_card(payload: RateCardCreate, request: Request):
        salus_write(request)
        rules = _validate_rules(payload.rules)
        tid, who, stamp = tenant_id(request), actor(request), now()
        conn = db()
        for override in rules.get("rate_overrides", []):
            selector = override["selector"]
            if override["scope_level"] == "Protected Member" and int(
                selector["protected_member_id"]
            ) != tid:
                conn.close()
                raise HTTPException(422, "Protected Member override must remain within this tenant")
            if override["scope_level"] == "Engagement":
                engagement = conn.execute(
                    "SELECT id FROM ops_engagements WHERE id=? AND tenant_id=?",
                    (int(selector["engagement_id"]), tid),
                ).fetchone()
                if not engagement:
                    conn.close()
                    raise HTTPException(422, "Engagement override must reference this tenant's engagement")
        if payload.supersedes_id:
            prior = conn.execute(
                "SELECT * FROM salcapa_rate_cards WHERE id=? AND tenant_id=? AND status='Approved'",
                (payload.supersedes_id, tid),
            ).fetchone()
            if not prior:
                conn.close()
                raise HTTPException(422, "A successor must reference an Approved rate card in this tenant")
            verify_card(dict(prior))
        version = int(conn.execute(
            "SELECT COALESCE(MAX(version_no),0)+1 v FROM salcapa_rate_cards WHERE tenant_id=?", (tid,)
        ).fetchone()["v"])
        card_id = _key("rate")
        content = {
            "id": card_id, "tenant_id": tid, "version_no": version, "name": payload.name.strip(),
            "effective_from": payload.effective_from.strip(), "supersedes_id": payload.supersedes_id,
            "rules": rules,
        }
        conn.execute(
            "INSERT INTO salcapa_rate_cards(id,tenant_id,version_no,name,effective_from,supersedes_id,rules_json,content_sha256,status,created_by,created_at,updated_at) VALUES(?,?,?,?,?,?,?,?,?,?,?,?)",
            (card_id, tid, version, content["name"], content["effective_from"], payload.supersedes_id,
             _canonical(rules), _digest(content), "Draft", who, stamp, stamp),
        )
        audit(conn, "SALCAPA_RATE_CARD_CREATE", "salcapa_rate_card", None,
              f"{card_id} v{version}: Draft planning assumptions created; no customer price, charge, invoice, or entitlement created.", who)
        conn.commit()
        row = dict(conn.execute("SELECT * FROM salcapa_rate_cards WHERE id=?", (card_id,)).fetchone())
        conn.close()
        verify_card(row)
        row["rules"] = json.loads(row.pop("rules_json"))
        return row

    @app.post("/api/salcapa/commercial/rate-cards/{card_id}/transition")
    def transition_rate_card(card_id: str, payload: RateCardTransition, request: Request):
        salus_write(request)
        tid, who, stamp = tenant_id(request), actor(request), now()
        conn = db()
        found = conn.execute("SELECT * FROM salcapa_rate_cards WHERE id=? AND tenant_id=?", (card_id, tid)).fetchone()
        if not found:
            conn.close()
            raise HTTPException(404, "Rate card not found")
        row = dict(found)
        verify_card(row)
        expected = {"Draft": {"Submitted"}, "Submitted": {"Approved", "Rejected"}}
        if payload.status not in expected.get(row["status"], set()):
            conn.close()
            raise HTTPException(409, f"Rate card cannot transition from {row['status']} to {payload.status}")
        if payload.status in {"Approved", "Rejected"}:
            commercial_authority(request)
            if row["created_by"] == who:
                conn.close()
                raise HTTPException(409, "Rate-card decision requires an actor other than the creator")
        submitted_by = who if payload.status == "Submitted" else row["submitted_by"]
        submitted_at = stamp if payload.status == "Submitted" else row["submitted_at"]
        approved = payload.status == "Approved"
        conn.execute(
            "UPDATE salcapa_rate_cards SET status=?,submitted_by=?,submitted_at=?,approved_by=?,approved_at=?,decision_reason=?,updated_at=? WHERE id=? AND tenant_id=?",
            (payload.status, submitted_by, submitted_at, who if approved else "", stamp if approved else "",
             payload.reason if payload.status in {"Approved", "Rejected"} else "", stamp, card_id, tid),
        )
        audit(conn, "SALCAPA_RATE_CARD_TRANSITION", "salcapa_rate_card", None,
              f"{card_id}: {row['status']} -> {payload.status}; {payload.reason}"[:1000], who)
        conn.commit()
        result = dict(conn.execute("SELECT * FROM salcapa_rate_cards WHERE id=?", (card_id,)).fetchone())
        conn.close()
        verify_card(result)
        result["rules"] = json.loads(result.pop("rules_json"))
        return result

    @app.get("/api/salcapa/commercial/estimates")
    def list_estimates(request: Request):
        require(request, "read")
        tid = tenant_id(request)
        conn = db()
        if protected_member(request):
            rows = [dict(r) for r in conn.execute(
                "SELECT * FROM salcapa_commercial_estimates WHERE tenant_id=? AND status='Released' ORDER BY version_no DESC",
                (tid,),
            )]
            conn.close()
            if accessible_assessment_ids:
                allowed = set(accessible_assessment_ids(request))
                rows = [row for row in rows if row.get("assessment_id") is None or int(row["assessment_id"]) in allowed]
            for row in rows:
                verify_estimate(row)
            return [member_view(row) for row in rows]
        require_salus(request, "SalCAPA commercial planning")
        rows = [dict(r) for r in conn.execute(
            "SELECT * FROM salcapa_commercial_estimates WHERE tenant_id=? ORDER BY version_no DESC", (tid,)
        )]
        conn.close()
        for row in rows:
            verify_estimate(row)
        return [full_view(row) for row in rows]

    @app.post("/api/salcapa/commercial/estimates")
    def create_estimate(payload: EstimateCreate, request: Request):
        salus_write(request)
        tid, who, stamp = tenant_id(request), actor(request), now()
        if payload.assessment_id and assessment_for_request:
            assessment_for_request(request, payload.assessment_id)
        conn = db()
        if payload.engagement_id:
            engagement = conn.execute(
                "SELECT id,assessment_id FROM ops_engagements WHERE id=? AND tenant_id=?",
                (payload.engagement_id, tid),
            ).fetchone()
            if not engagement:
                conn.close()
                raise HTTPException(422, "Engagement must belong to this Protected Member")
            if payload.assessment_id and int(engagement["assessment_id"]) != payload.assessment_id:
                conn.close()
                raise HTTPException(422, "Engagement and assessment must share the same governed scope")
        if payload.supersedes_estimate_id:
            prior = conn.execute(
                "SELECT * FROM salcapa_commercial_estimates WHERE id=? AND tenant_id=? AND status IN ('Approved','Released')",
                (payload.supersedes_estimate_id, tid),
            ).fetchone()
            if not prior:
                conn.close()
                raise HTTPException(422, "A change estimate must reference an Approved or Released estimate in this tenant")
            verify_estimate(dict(prior))
        if payload.rate_card_id:
            selected = conn.execute(
                "SELECT * FROM salcapa_rate_cards WHERE id=? AND tenant_id=? AND status='Approved'",
                (payload.rate_card_id, tid),
            ).fetchone()
        else:
            selected = conn.execute(
                "SELECT * FROM salcapa_rate_cards WHERE tenant_id=? AND status='Approved' ORDER BY version_no DESC LIMIT 1",
                (tid,),
            ).fetchone()
        if not selected:
            conn.close()
            raise HTTPException(409, "An Approved rate card is required before preparing an estimate")
        card = dict(selected)
        verify_card(card)
        rules = json.loads(card["rules_json"])
        inputs, calculation = _calculate(payload, rules, tid)
        version = int(conn.execute(
            "SELECT COALESCE(MAX(version_no),0)+1 v FROM salcapa_commercial_estimates WHERE tenant_id=?", (tid,)
        ).fetchone()["v"])
        estimate_id = _key("estimate")
        rate_snapshot = card_content(card)
        content = {
            "id": estimate_id, "tenant_id": tid, "version_no": version,
            "supersedes_estimate_id": payload.supersedes_estimate_id,
            "engagement_id": payload.engagement_id, "assessment_id": payload.assessment_id,
            "rate_card_id": card["id"], "rate_card_version": int(card["version_no"]),
            "inputs": inputs, "rate_snapshot": rate_snapshot, "calculation": calculation,
        }
        conn.execute(
            """INSERT INTO salcapa_commercial_estimates(
              id,tenant_id,version_no,supersedes_estimate_id,engagement_id,assessment_id,
              rate_card_id,rate_card_version,product_line,domain_key,investigation_tier,complexity,
              pricing_method,customer_summary,internal_basis,inputs_json,rate_snapshot_json,
              calculation_json,content_sha256,recommended_customer_price_cents,
              estimated_internal_cost_cents,estimated_margin_cents,estimated_margin_basis_points,
              currency,status,creates_charge,creates_invoice,created_by,created_at,updated_at)
              VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (estimate_id, tid, version, payload.supersedes_estimate_id, payload.engagement_id,
             payload.assessment_id, card["id"], card["version_no"], payload.product_line,
             payload.domain_key, payload.investigation_tier, payload.complexity, payload.pricing_method,
             payload.customer_summary, payload.internal_basis, _canonical(inputs), _canonical(rate_snapshot),
             _canonical(calculation), _digest(content), calculation["recommended_customer_price_cents"],
             calculation["estimated_internal_cost_cents"], calculation["estimated_margin_cents"],
             calculation["estimated_margin_basis_points"], "USD", "Draft", 0, 0, who, stamp, stamp),
        )
        audit(conn, "SALCAPA_COMMERCIAL_ESTIMATE_CREATE", "salcapa_commercial_estimate", None,
              f"{estimate_id} v{version}: immutable planning estimate prepared from rate card v{card['version_no']}; no scope, charge, invoice, entitlement, or customer commitment created.", who)
        conn.commit()
        row = dict(conn.execute("SELECT * FROM salcapa_commercial_estimates WHERE id=?", (estimate_id,)).fetchone())
        conn.close()
        verify_estimate(row)
        return full_view(row)

    @app.post("/api/salcapa/commercial/estimates/{estimate_id}/transition")
    def transition_estimate(estimate_id: str, payload: EstimateTransition, request: Request):
        salus_write(request)
        tid, who, stamp = tenant_id(request), actor(request), now()
        conn = db()
        found = conn.execute(
            "SELECT * FROM salcapa_commercial_estimates WHERE id=? AND tenant_id=?", (estimate_id, tid)
        ).fetchone()
        if not found:
            conn.close()
            raise HTTPException(404, "Commercial estimate not found")
        row = dict(found)
        verify_estimate(row)
        expected = {"Draft": {"Submitted"}, "Submitted": {"Approved", "Rejected"}, "Approved": {"Released"}}
        if payload.status not in expected.get(row["status"], set()):
            conn.close()
            raise HTTPException(409, f"Commercial estimate cannot transition from {row['status']} to {payload.status}")
        approved_price = row["approved_customer_price_cents"]
        approved_by, approved_at = row["approved_by"], row["approved_at"]
        released_by, released_at = row["released_by"], row["released_at"]
        decision_reason, release_reason = row["decision_reason"], row["release_reason"]
        submitted_by, submitted_at = row["submitted_by"], row["submitted_at"]
        if payload.status == "Submitted":
            if payload.approved_customer_price_cents is not None:
                conn.close()
                raise HTTPException(422, "Price approval is not accepted during submission")
            submitted_by, submitted_at = who, stamp
        elif payload.status in {"Approved", "Rejected"}:
            commercial_authority(request)
            if row["created_by"] == who:
                conn.close()
                raise HTTPException(409, "Estimate decision requires an actor other than the creator")
            if payload.status == "Approved":
                if payload.approved_customer_price_cents is None:
                    conn.close()
                    raise HTTPException(422, "Approved customer price is required")
                approved_price = payload.approved_customer_price_cents
                approved_by, approved_at = who, stamp
            elif payload.approved_customer_price_cents is not None:
                conn.close()
                raise HTTPException(422, "A rejected estimate cannot approve a customer price")
            decision_reason = payload.reason
        else:
            commercial_authority(request)
            if who != row["approved_by"]:
                conn.close()
                raise HTTPException(409, "The recorded price approver must authorize member release")
            if payload.approved_customer_price_cents is not None:
                conn.close()
                raise HTTPException(422, "Release cannot alter the approved customer price")
            released_by, released_at, release_reason = who, stamp, payload.reason
        conn.execute(
            """UPDATE salcapa_commercial_estimates SET status=?,approved_customer_price_cents=?,
               submitted_by=?,submitted_at=?,approved_by=?,approved_at=?,released_by=?,released_at=?,
               decision_reason=?,release_reason=?,updated_at=? WHERE id=? AND tenant_id=?""",
            (payload.status, approved_price, submitted_by, submitted_at, approved_by, approved_at,
             released_by, released_at, decision_reason, release_reason, stamp, estimate_id, tid),
        )
        audit(conn, "SALCAPA_COMMERCIAL_ESTIMATE_TRANSITION", "salcapa_commercial_estimate", None,
              f"{estimate_id}: {row['status']} -> {payload.status}; no charge or invoice created; {payload.reason}"[:1000], who)
        conn.commit()
        result = dict(conn.execute(
            "SELECT * FROM salcapa_commercial_estimates WHERE id=?", (estimate_id,)
        ).fetchone())
        conn.close()
        verify_estimate(result)
        return full_view(result)

    @app.post("/api/salcapa/commercial/time-entries")
    def create_time_entry(payload: TimeEntryCreate, request: Request):
        salus_write(request)
        tid, who, stamp = tenant_id(request), actor(request), now()
        conn = db()
        try:
            estimate = estimate_for_actuals(conn, request, payload.estimate_id)
            if payload.supersedes_entry_id:
                prior = conn.execute(
                    "SELECT * FROM salcapa_time_entries WHERE id=? AND tenant_id=? AND estimate_id=? AND status='Approved'",
                    (payload.supersedes_entry_id, tid, payload.estimate_id),
                ).fetchone()
                if not prior:
                    raise HTTPException(422, "A corrected time entry must replace an Approved entry for this estimate")
                verify_actual_entry(dict(prior), "time")
                duplicate = conn.execute(
                    "SELECT id FROM salcapa_time_entries WHERE supersedes_entry_id=? AND tenant_id=? AND status<>'Rejected'",
                    (payload.supersedes_entry_id, tid),
                ).fetchone()
                if duplicate:
                    raise HTTPException(409, "This time entry already has an active correction")
            rate_snapshot = json.loads(estimate["rate_snapshot_json"])
            loaded_rate = int(rate_snapshot["rules"]["loaded_labor_cost_cents_per_hour"])
            calculated_cost = _money(Decimal(payload.minutes) * Decimal(loaded_rate) / Decimal(60))
            version = int(conn.execute(
                "SELECT COALESCE(MAX(version_no),0)+1 v FROM salcapa_time_entries WHERE tenant_id=?", (tid,)
            ).fetchone()["v"])
            entry_id = _key("time")
            content = {
                "id": entry_id, "tenant_id": tid, "version_no": version,
                "estimate_id": payload.estimate_id, "supersedes_entry_id": payload.supersedes_entry_id,
                "engagement_id": estimate["engagement_id"], "assessment_id": estimate["assessment_id"],
                "person_name": payload.person_name.strip(), "role_name": payload.role_name.strip(),
                "work_date": payload.work_date, "minutes": payload.minutes,
                "work_category": payload.work_category,
                "commercial_treatment": payload.commercial_treatment, "notes": payload.notes.strip(),
                "loaded_rate_cents_per_hour": loaded_rate, "calculated_cost_cents": calculated_cost,
            }
            conn.execute(
                """INSERT INTO salcapa_time_entries(
                  id,tenant_id,version_no,estimate_id,supersedes_entry_id,engagement_id,assessment_id,
                  person_name,role_name,work_date,minutes,work_category,commercial_treatment,notes,
                  loaded_rate_cents_per_hour,calculated_cost_cents,content_sha256,status,
                  creates_charge,creates_invoice,created_by,created_at,updated_at)
                  VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                (entry_id, tid, version, payload.estimate_id, payload.supersedes_entry_id,
                 estimate["engagement_id"], estimate["assessment_id"], content["person_name"],
                 content["role_name"], payload.work_date, payload.minutes, payload.work_category,
                 payload.commercial_treatment, content["notes"], loaded_rate, calculated_cost,
                 _digest(content), "Draft", 0, 0, who, stamp, stamp),
            )
            audit(conn, "SALCAPA_TIME_ENTRY_CREATE", "salcapa_time_entry", estimate["assessment_id"],
                  f"{entry_id} v{version}: Draft work record prepared for independent review; no price, charge, or invoice created.", who)
            conn.commit()
            row = dict(conn.execute("SELECT * FROM salcapa_time_entries WHERE id=?", (entry_id,)).fetchone())
        finally:
            conn.close()
        verify_actual_entry(row, "time")
        return actual_view(row, "time")

    @app.post("/api/salcapa/commercial/cost-entries")
    def create_cost_entry(payload: CostEntryCreate, request: Request):
        salus_write(request)
        tid, who, stamp = tenant_id(request), actor(request), now()
        conn = db()
        try:
            estimate = estimate_for_actuals(conn, request, payload.estimate_id)
            if payload.supersedes_entry_id:
                prior = conn.execute(
                    "SELECT * FROM salcapa_cost_entries WHERE id=? AND tenant_id=? AND estimate_id=? AND status='Approved'",
                    (payload.supersedes_entry_id, tid, payload.estimate_id),
                ).fetchone()
                if not prior:
                    raise HTTPException(422, "A corrected cost entry must replace an Approved entry for this estimate")
                verify_actual_entry(dict(prior), "cost")
                duplicate = conn.execute(
                    "SELECT id FROM salcapa_cost_entries WHERE supersedes_entry_id=? AND tenant_id=? AND status<>'Rejected'",
                    (payload.supersedes_entry_id, tid),
                ).fetchone()
                if duplicate:
                    raise HTTPException(409, "This cost entry already has an active correction")
            version = int(conn.execute(
                "SELECT COALESCE(MAX(version_no),0)+1 v FROM salcapa_cost_entries WHERE tenant_id=?", (tid,)
            ).fetchone()["v"])
            entry_id = _key("cost")
            recognized = payload.amount_cents if payload.cost_basis in ACTUAL_COST_BASES else 0
            content = {
                "id": entry_id, "tenant_id": tid, "version_no": version,
                "estimate_id": payload.estimate_id, "supersedes_entry_id": payload.supersedes_entry_id,
                "engagement_id": estimate["engagement_id"], "assessment_id": estimate["assessment_id"],
                "cost_category": payload.cost_category, "cost_basis": payload.cost_basis,
                "amount_cents": payload.amount_cents, "recognized_actual_cost_cents": recognized,
                "provider_or_payee": payload.provider_or_payee.strip(),
                "source_reference": payload.source_reference.strip(),
                "usage_units": payload.usage_units.strip(),
                "unit_rate_version": payload.unit_rate_version.strip(),
                "incurred_at": payload.incurred_at.strip(),
                "commercial_treatment": payload.commercial_treatment, "notes": payload.notes.strip(),
            }
            conn.execute(
                """INSERT INTO salcapa_cost_entries(
                  id,tenant_id,version_no,estimate_id,supersedes_entry_id,engagement_id,assessment_id,
                  cost_category,cost_basis,amount_cents,recognized_actual_cost_cents,provider_or_payee,
                  source_reference,usage_units,unit_rate_version,incurred_at,commercial_treatment,notes,
                  content_sha256,status,creates_charge,creates_invoice,created_by,created_at,updated_at)
                  VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                (entry_id, tid, version, payload.estimate_id, payload.supersedes_entry_id,
                 estimate["engagement_id"], estimate["assessment_id"], payload.cost_category,
                 payload.cost_basis, payload.amount_cents, recognized, content["provider_or_payee"],
                 content["source_reference"], content["usage_units"], content["unit_rate_version"],
                 content["incurred_at"], payload.commercial_treatment, content["notes"],
                 _digest(content), "Draft", 0, 0, who, stamp, stamp),
            )
            audit(conn, "SALCAPA_COST_ENTRY_CREATE", "salcapa_cost_entry", estimate["assessment_id"],
                  f"{entry_id} v{version}: Draft {payload.cost_basis} record prepared for independent review; no price, charge, or invoice created.", who)
            conn.commit()
            row = dict(conn.execute("SELECT * FROM salcapa_cost_entries WHERE id=?", (entry_id,)).fetchone())
        finally:
            conn.close()
        verify_actual_entry(row, "cost")
        return actual_view(row, "cost")

    def transition_actual_entry(table: str, kind: str, entry_id: str,
                                payload: ActualEntryTransition, request: Request) -> dict[str, Any]:
        salus_write(request)
        tid, who, stamp = tenant_id(request), actor(request), now()
        conn = db()
        try:
            found = conn.execute(f"SELECT * FROM {table} WHERE id=? AND tenant_id=?", (entry_id, tid)).fetchone()
            if not found:
                raise HTTPException(404, f"Commercial {kind} entry not found")
            row = dict(found)
            verify_actual_entry(row, kind)
            expected = {"Draft": {"Submitted"}, "Submitted": {"Approved", "Rejected"}}
            if payload.status not in expected.get(row["status"], set()):
                raise HTTPException(409, f"Commercial {kind} entry cannot transition from {row['status']} to {payload.status}")
            submitted_by, submitted_at = row["submitted_by"], row["submitted_at"]
            approved_by, approved_at = row["approved_by"], row["approved_at"]
            decision_reason = row["decision_reason"]
            if payload.status == "Submitted":
                submitted_by, submitted_at = who, stamp
            else:
                commercial_authority(request)
                if row["created_by"] == who:
                    raise HTTPException(409, f"Commercial {kind} entry decision requires an actor other than the creator")
                if payload.status == "Approved":
                    approved_by, approved_at = who, stamp
                decision_reason = payload.reason
            conn.execute(
                f"UPDATE {table} SET status=?,submitted_by=?,submitted_at=?,approved_by=?,approved_at=?,decision_reason=?,updated_at=? WHERE id=? AND tenant_id=?",
                (payload.status, submitted_by, submitted_at, approved_by, approved_at,
                 decision_reason, stamp, entry_id, tid),
            )
            audit(conn, f"SALCAPA_{kind.upper()}_ENTRY_TRANSITION", f"salcapa_{kind}_entry", row["assessment_id"],
                  f"{entry_id}: {row['status']} -> {payload.status}; internal cost visibility only; no price, charge, or invoice created; {payload.reason}"[:1000], who)
            conn.commit()
            result = dict(conn.execute(f"SELECT * FROM {table} WHERE id=?", (entry_id,)).fetchone())
        finally:
            conn.close()
        verify_actual_entry(result, kind)
        return actual_view(result, kind)

    @app.post("/api/salcapa/commercial/time-entries/{entry_id}/transition")
    def transition_time_entry(entry_id: str, payload: ActualEntryTransition, request: Request):
        return transition_actual_entry("salcapa_time_entries", "time", entry_id, payload, request)

    @app.post("/api/salcapa/commercial/cost-entries/{entry_id}/transition")
    def transition_cost_entry(entry_id: str, payload: ActualEntryTransition, request: Request):
        return transition_actual_entry("salcapa_cost_entries", "cost", entry_id, payload, request)

    @app.get("/api/salcapa/commercial/estimates/{estimate_id}/actuals")
    def estimate_actuals(estimate_id: str, request: Request):
        salus_read(request)
        tid = tenant_id(request)
        conn = db()
        try:
            estimate = estimate_for_actuals(conn, request, estimate_id)
            summary = active_actual_summary(conn, tid, estimate_id)
        finally:
            conn.close()
        time_rows, cost_rows = summary["time_rows"], summary["cost_rows"]
        superseded_time = summary["superseded_time"]
        superseded_cost = summary["superseded_cost"]
        time_cost = summary["approved_time_cost_cents"]
        recognized_direct = summary["approved_direct_actual_cost_cents"]
        provisional = summary["approved_provisional_cost_cents"]
        unavailable_count = summary["approved_unavailable_cost_record_count"]
        recognized_total = summary["recognized_actual_cost_to_date_cents"]
        estimated_internal = int(estimate["estimated_internal_cost_cents"])
        if not summary["active_time"] and not summary["active_cost"]:
            actual_status = "Not Recorded"
        elif provisional or unavailable_count:
            actual_status = "Partial Actuals"
        else:
            actual_status = "Actuals Recorded to Date"
        time_views = [actual_view(row, "time") for row in time_rows]
        cost_views = [actual_view(row, "cost") for row in cost_rows]
        for item in time_views:
            item["active_approved_record"] = item["status"] == "Approved" and item["id"] not in superseded_time
        for item in cost_views:
            item["active_approved_record"] = item["status"] == "Approved" and item["id"] not in superseded_cost
        return {
            "estimate_id": estimate_id, "estimate_version_no": int(estimate["version_no"]),
            "currency": estimate["currency"], "actual_cost_status": actual_status,
            "estimated_internal_cost_cents": estimated_internal,
            "approved_time_cost_cents": time_cost,
            "approved_direct_actual_cost_cents": recognized_direct,
            "recognized_actual_cost_to_date_cents": recognized_total,
            "approved_estimated_or_allowance_cost_cents": provisional,
            "approved_unavailable_cost_record_count": unavailable_count,
            "variance_to_estimated_internal_cost_cents": recognized_total - estimated_internal,
            "variance_interpretation": "To-date comparison only; it is not a final savings, overrun, margin, price, charge, or invoice.",
            "completeness": "Salus review is required to determine whether all work and costs have been recorded.",
            "creates_charge": False, "creates_invoice": False,
            "time_entries": time_views, "cost_entries": cost_views,
        }

    @app.post("/api/salcapa/commercial/forecasts")
    def create_forecast(payload: ForecastCreate, request: Request):
        salus_write(request)
        tid, who, stamp = tenant_id(request), actor(request), now()
        conn = db()
        try:
            estimate = estimate_for_actuals(conn, request, payload.estimate_id)
            if payload.supersedes_forecast_id:
                prior = conn.execute(
                    "SELECT * FROM salcapa_commercial_forecasts WHERE id=? AND tenant_id=? AND estimate_id=? AND status='Approved'",
                    (payload.supersedes_forecast_id, tid, payload.estimate_id),
                ).fetchone()
                if not prior:
                    raise HTTPException(422, "A revised forecast must replace an Approved forecast for this estimate")
                verify_forecast(dict(prior))
                duplicate = conn.execute(
                    "SELECT id FROM salcapa_commercial_forecasts WHERE supersedes_forecast_id=? AND tenant_id=? AND status<>'Rejected'",
                    (payload.supersedes_forecast_id, tid),
                ).fetchone()
                if duplicate:
                    raise HTTPException(409, "This forecast already has an active revision")
            active_prior = active_approved_forecast(conn, tid, payload.estimate_id)
            if active_prior and payload.supersedes_forecast_id != active_prior["id"]:
                raise HTTPException(
                    409, "A new forecast must explicitly revise the current Approved forecast"
                )
            summary = active_actual_summary(conn, tid, payload.estimate_id)
            snapshot = actual_snapshot(summary)
            rate_snapshot = json.loads(estimate["rate_snapshot_json"])
            loaded_rate = int(rate_snapshot["rules"]["loaded_labor_cost_cents_per_hour"])
            remaining_labor_cost = _money(
                Decimal(payload.remaining_labor_minutes) * Decimal(loaded_rate) / Decimal(60)
            )
            provisional = int(summary["approved_provisional_cost_cents"])
            recognized = int(summary["recognized_actual_cost_to_date_cents"])
            forecast_to_complete = (
                remaining_labor_cost + provisional + payload.additional_remaining_direct_cost_cents
            )
            forecast_at_completion = recognized + forecast_to_complete
            estimated_internal = int(estimate["estimated_internal_cost_cents"])
            approved_price = int(estimate["approved_customer_price_cents"] or 0)
            contribution = approved_price - forecast_at_completion
            contribution_bps = None if approved_price <= 0 else _money(
                Decimal(contribution) * Decimal(10000) / Decimal(approved_price)
            )
            unavailable_count = int(summary["approved_unavailable_cost_record_count"])
            incomplete_unavailable = (
                unavailable_count > 0
                and payload.unavailable_cost_handling == "Excluded pending evidence"
            )
            completeness = "Evidence Needed" if incomplete_unavailable else payload.confidence_state
            version = int(conn.execute(
                "SELECT COALESCE(MAX(version_no),0)+1 v FROM salcapa_commercial_forecasts WHERE tenant_id=?",
                (tid,),
            ).fetchone()["v"])
            forecast_id = _key("forecast")
            content = {
                "id": forecast_id, "tenant_id": tid, "version_no": version,
                "estimate_id": payload.estimate_id,
                "supersedes_forecast_id": payload.supersedes_forecast_id,
                "engagement_id": estimate["engagement_id"], "assessment_id": estimate["assessment_id"],
                "as_of_date": payload.as_of_date,
                "forecast_through_date": payload.forecast_through_date,
                "confidence_state": payload.confidence_state,
                "unavailable_cost_handling": payload.unavailable_cost_handling,
                "remaining_labor_minutes": payload.remaining_labor_minutes,
                "loaded_rate_cents_per_hour": loaded_rate,
                "forecast_remaining_labor_cost_cents": remaining_labor_cost,
                "forecast_additional_direct_cost_cents": payload.additional_remaining_direct_cost_cents,
                "actual_snapshot": snapshot,
                "assumptions": payload.assumptions.strip(),
                "known_constraints": payload.known_constraints.strip(),
                "recognized_actual_cost_to_date_cents": recognized,
                "approved_provisional_cost_cents": provisional,
                "forecast_to_complete_cents": forecast_to_complete,
                "forecast_at_completion_cents": forecast_at_completion,
                "variance_to_estimated_internal_cost_cents": forecast_at_completion - estimated_internal,
                "projected_contribution_cents": contribution,
                "projected_contribution_basis_points": contribution_bps,
                "completeness_state": completeness,
            }
            conn.execute(
                """INSERT INTO salcapa_commercial_forecasts(
                  id,tenant_id,version_no,estimate_id,supersedes_forecast_id,engagement_id,assessment_id,
                  as_of_date,forecast_through_date,confidence_state,unavailable_cost_handling,
                  remaining_labor_minutes,loaded_rate_cents_per_hour,forecast_remaining_labor_cost_cents,
                  forecast_additional_direct_cost_cents,actual_snapshot_json,assumptions,known_constraints,
                  content_sha256,recognized_actual_cost_to_date_cents,approved_provisional_cost_cents,
                  forecast_to_complete_cents,forecast_at_completion_cents,
                  variance_to_estimated_internal_cost_cents,projected_contribution_cents,
                  projected_contribution_basis_points,completeness_state,status,creates_charge,creates_invoice,
                  created_by,created_at,updated_at)
                  VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                (forecast_id, tid, version, payload.estimate_id, payload.supersedes_forecast_id,
                 estimate["engagement_id"], estimate["assessment_id"], payload.as_of_date,
                 payload.forecast_through_date, payload.confidence_state,
                 payload.unavailable_cost_handling, payload.remaining_labor_minutes, loaded_rate,
                 remaining_labor_cost, payload.additional_remaining_direct_cost_cents,
                 _canonical(snapshot), content["assumptions"], content["known_constraints"],
                 _digest(content), recognized, provisional, forecast_to_complete, forecast_at_completion,
                 content["variance_to_estimated_internal_cost_cents"], contribution, contribution_bps,
                 completeness, "Draft", 0, 0, who, stamp, stamp),
            )
            audit(conn, "SALCAPA_COMMERCIAL_FORECAST_CREATE", "salcapa_commercial_forecast",
                  estimate["assessment_id"],
                  f"{forecast_id} v{version}: dated internal forecast prepared from approved source records; no scope, price, charge, invoice, or commitment changed.", who)
            conn.commit()
            row = dict(conn.execute(
                "SELECT * FROM salcapa_commercial_forecasts WHERE id=?", (forecast_id,)
            ).fetchone())
        finally:
            conn.close()
        verify_forecast(row)
        return forecast_view(row)

    @app.get("/api/salcapa/commercial/estimates/{estimate_id}/forecasts")
    def list_forecasts(estimate_id: str, request: Request):
        salus_read(request)
        tid = tenant_id(request)
        conn = db()
        try:
            estimate_for_actuals(conn, request, estimate_id)
            rows = [dict(r) for r in conn.execute(
                "SELECT * FROM salcapa_commercial_forecasts WHERE tenant_id=? AND estimate_id=? ORDER BY version_no",
                (tid, estimate_id),
            )]
        finally:
            conn.close()
        for row in rows:
            verify_forecast(row)
        approved = [row for row in rows if row["status"] == "Approved"]
        superseded = {row["supersedes_forecast_id"] for row in approved if row["supersedes_forecast_id"]}
        views = [forecast_view(row) for row in rows]
        for item in views:
            item["active_approved_forecast"] = item["status"] == "Approved" and item["id"] not in superseded
            item["interpretation"] = (
                "Internal planning view as of the recorded date; not a final cost, savings, overrun, "
                "recognized margin, customer price, charge, invoice, or commitment."
            )
        return views

    @app.post("/api/salcapa/commercial/forecasts/{forecast_id}/transition")
    def transition_forecast(forecast_id: str, payload: ForecastTransition, request: Request):
        salus_write(request)
        tid, who, stamp = tenant_id(request), actor(request), now()
        conn = db()
        try:
            found = conn.execute(
                "SELECT * FROM salcapa_commercial_forecasts WHERE id=? AND tenant_id=?",
                (forecast_id, tid),
            ).fetchone()
            if not found:
                raise HTTPException(404, "Commercial forecast not found")
            row = dict(found)
            verify_forecast(row)
            expected = {"Draft": {"Submitted"}, "Submitted": {"Approved", "Rejected"}}
            if payload.status not in expected.get(row["status"], set()):
                raise HTTPException(409, f"Commercial forecast cannot transition from {row['status']} to {payload.status}")
            submitted_by, submitted_at = row["submitted_by"], row["submitted_at"]
            approved_by, approved_at = row["approved_by"], row["approved_at"]
            decision_reason = row["decision_reason"]
            if payload.status == "Submitted":
                submitted_by, submitted_at = who, stamp
            else:
                commercial_authority(request)
                if row["created_by"] == who:
                    raise HTTPException(409, "Commercial forecast decision requires an actor other than the creator")
                if payload.status == "Approved":
                    active_prior = active_approved_forecast(conn, tid, row["estimate_id"])
                    if active_prior and row["supersedes_forecast_id"] != active_prior["id"]:
                        raise HTTPException(
                            409, "Another Approved forecast is current; prepare an explicit revision"
                        )
                    current = actual_snapshot(active_actual_summary(conn, tid, row["estimate_id"]))
                    if _canonical(current) != _canonical(json.loads(row["actual_snapshot_json"])):
                        raise HTTPException(
                            409, "Approved source records changed; prepare a current forecast rather than approving a stale snapshot"
                        )
                    approved_by, approved_at = who, stamp
                decision_reason = payload.reason
            conn.execute(
                """UPDATE salcapa_commercial_forecasts SET status=?,submitted_by=?,submitted_at=?,
                   approved_by=?,approved_at=?,decision_reason=?,updated_at=? WHERE id=? AND tenant_id=?""",
                (payload.status, submitted_by, submitted_at, approved_by, approved_at,
                 decision_reason, stamp, forecast_id, tid),
            )
            audit(conn, "SALCAPA_COMMERCIAL_FORECAST_TRANSITION", "salcapa_commercial_forecast",
                  row["assessment_id"],
                  f"{forecast_id}: {row['status']} -> {payload.status}; internal planning only; no scope, price, charge, invoice, or commitment changed; {payload.reason}"[:1000], who)
            conn.commit()
            result = dict(conn.execute(
                "SELECT * FROM salcapa_commercial_forecasts WHERE id=?", (forecast_id,)
            ).fetchone())
        finally:
            conn.close()
        verify_forecast(result)
        return forecast_view(result)

    @app.get("/api/salcapa/commercial/wip-reviews")
    def list_wip_reviews(request: Request, estimate_id: Optional[str] = None):
        salus_read(request)
        tid = tenant_id(request)
        conn = db()
        try:
            if estimate_id:
                estimate_for_actuals(conn, request, estimate_id)
                rows = [dict(row) for row in conn.execute(
                    """SELECT * FROM salcapa_wip_reviews
                       WHERE tenant_id=? AND estimate_id=? ORDER BY version_no""",
                    (tid, estimate_id),
                )]
            else:
                rows = [dict(row) for row in conn.execute(
                    "SELECT * FROM salcapa_wip_reviews WHERE tenant_id=? ORDER BY version_no",
                    (tid,),
                )]
        finally:
            conn.close()
        for row in rows:
            verify_wip_review(row)
        approved = [row for row in rows if row["status"] == "Approved"]
        superseded = {
            row["supersedes_wip_review_id"] for row in approved
            if row["supersedes_wip_review_id"]
        }
        views = [wip_view(row) for row in rows]
        for item in views:
            item["current_approved_review"] = (
                item["status"] == "Approved" and item["id"] not in superseded
            )
        return views

    @app.get("/api/salcapa/commercial/wip-summary")
    def get_wip_summary(request: Request, as_of_date: str):
        salus_read(request)
        as_of = report_date(as_of_date, "as_of_date")
        conn = db()
        try:
            return wip_management_summary(conn, tenant_id(request), as_of)
        finally:
            conn.close()

    @app.post("/api/salcapa/commercial/wip-reviews")
    def create_wip_review(payload: WipReviewCreate, request: Request):
        salus_write(request)
        tid, who, stamp = tenant_id(request), actor(request), now()
        conn = db()
        try:
            estimate = estimate_for_actuals(conn, request, payload.estimate_id)
            if payload.supersedes_wip_review_id:
                prior = conn.execute(
                    """SELECT * FROM salcapa_wip_reviews
                       WHERE id=? AND tenant_id=? AND estimate_id=? AND status='Approved'""",
                    (payload.supersedes_wip_review_id, tid, payload.estimate_id),
                ).fetchone()
                if not prior:
                    raise HTTPException(
                        422, "A revised WIP review must replace an Approved review for this estimate"
                    )
                verify_wip_review(dict(prior))
                duplicate = conn.execute(
                    """SELECT id FROM salcapa_wip_reviews
                       WHERE supersedes_wip_review_id=? AND tenant_id=? AND status<>'Rejected'""",
                    (payload.supersedes_wip_review_id, tid),
                ).fetchone()
                if duplicate:
                    raise HTTPException(409, "This WIP review already has an active revision")
            active_prior = active_wip_review(conn, tid, payload.estimate_id)
            if active_prior and payload.supersedes_wip_review_id != active_prior["id"]:
                raise HTTPException(
                    409, "A new WIP review must explicitly revise the current Approved review"
                )
            snapshot = wip_source_snapshot(
                conn, tid, payload.estimate_id, payload.work_through_date
            )
            if int(snapshot["work_evidence_record_count"]) <= 0:
                raise HTTPException(
                    409, "WIP review requires approved time, cost, or membership-consumption evidence"
                )
            if (payload.commercial_disposition == "Membership Included"
                    and not snapshot["active_membership_consumption"]):
                raise HTTPException(
                    409, "Membership Included requires approved linked membership consumption"
                )
            evidence_state = (
                "Evidence Needed" if int(snapshot["unavailable_cost_record_count"]) > 0
                else "Reasonably Supported"
            )
            if (payload.commercial_disposition == "Authorized for Billing"
                    and evidence_state != "Reasonably Supported"):
                raise HTTPException(
                    409, "Billing authorization requires supported cost evidence; resolve unavailable cost records first"
                )
            version = int(conn.execute(
                "SELECT COALESCE(MAX(version_no),0)+1 v FROM salcapa_wip_reviews WHERE tenant_id=?",
                (tid,),
            ).fetchone()["v"])
            review_id = _key("wip-review")
            content = {
                "id": review_id, "tenant_id": tid, "version_no": version,
                "estimate_id": payload.estimate_id,
                "supersedes_wip_review_id": payload.supersedes_wip_review_id,
                "engagement_id": estimate["engagement_id"],
                "assessment_id": estimate["assessment_id"],
                "as_of_date": payload.as_of_date,
                "work_through_date": payload.work_through_date,
                "commercial_disposition": payload.commercial_disposition,
                "work_value_cents": payload.work_value_cents,
                "billing_authorized_amount_cents": payload.billing_authorized_amount_cents,
                "external_billing_reference": payload.external_billing_reference.strip(),
                "source_snapshot": snapshot,
                "review_basis": payload.review_basis.strip(),
                "assumptions": payload.assumptions.strip(),
                "known_gaps": payload.known_gaps.strip(),
                "evidence_state": evidence_state,
            }
            conn.execute(
                """INSERT INTO salcapa_wip_reviews(
                   id,tenant_id,version_no,estimate_id,supersedes_wip_review_id,
                   engagement_id,assessment_id,as_of_date,work_through_date,
                   commercial_disposition,work_value_cents,billing_authorized_amount_cents,
                   external_billing_reference,source_snapshot_json,review_basis,assumptions,
                   known_gaps,content_sha256,evidence_state,status,creates_charge,creates_invoice,
                   recognizes_revenue,transmits_externally,created_by,created_at,updated_at)
                   VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                (review_id, tid, version, payload.estimate_id,
                 payload.supersedes_wip_review_id, estimate["engagement_id"],
                 estimate["assessment_id"], payload.as_of_date, payload.work_through_date,
                 payload.commercial_disposition, payload.work_value_cents,
                 payload.billing_authorized_amount_cents,
                 content["external_billing_reference"], _canonical(snapshot),
                 content["review_basis"], content["assumptions"], content["known_gaps"],
                 _digest(content), evidence_state, "Draft", 0, 0, 0, 0, who, stamp, stamp),
            )
            audit(
                conn, "SALCAPA_COMMERCIAL_WIP_CREATE", "salcapa_wip_review",
                estimate["assessment_id"],
                f"{review_id} v{version}: dated Salus WIP disposition prepared from governed work evidence; no revenue, charge, invoice, scope change, or external transmission occurred.",
                who,
            )
            conn.commit()
            row = dict(conn.execute(
                "SELECT * FROM salcapa_wip_reviews WHERE id=?", (review_id,)
            ).fetchone())
        finally:
            conn.close()
        verify_wip_review(row)
        return wip_view(row)

    @app.post("/api/salcapa/commercial/wip-reviews/{review_id}/transition")
    def transition_wip_review(review_id: str, payload: WipReviewTransition,
                              request: Request):
        salus_write(request)
        tid, who, stamp = tenant_id(request), actor(request), now()
        conn = db()
        try:
            found = conn.execute(
                "SELECT * FROM salcapa_wip_reviews WHERE id=? AND tenant_id=?",
                (review_id, tid),
            ).fetchone()
            if not found:
                raise HTTPException(404, "Unbilled/work-in-progress review not found")
            row = dict(found)
            verify_wip_review(row)
            expected = {"Draft": {"Submitted"}, "Submitted": {"Approved", "Rejected"}}
            if payload.status not in expected.get(row["status"], set()):
                raise HTTPException(
                    409, f"WIP review cannot transition from {row['status']} to {payload.status}"
                )
            submitted_by, submitted_at = row["submitted_by"], row["submitted_at"]
            approved_by, approved_at = row["approved_by"], row["approved_at"]
            decision_reason = row["decision_reason"]
            if payload.status == "Submitted":
                submitted_by, submitted_at = who, stamp
            else:
                commercial_authority(request)
                if row["created_by"] == who:
                    raise HTTPException(
                        409, "WIP review decision requires an actor other than the creator"
                    )
                if payload.status == "Approved":
                    active_prior = active_wip_review(conn, tid, row["estimate_id"])
                    if active_prior and row["supersedes_wip_review_id"] != active_prior["id"]:
                        raise HTTPException(
                            409, "Another Approved WIP review is current; prepare an explicit revision"
                        )
                    current = wip_source_snapshot(
                        conn, tid, row["estimate_id"], row["work_through_date"]
                    )
                    if _canonical(current) != _canonical(json.loads(row["source_snapshot_json"])):
                        raise HTTPException(
                            409, "Approved source records changed; prepare a current WIP review rather than approving a stale snapshot"
                        )
                    if (row["commercial_disposition"] == "Authorized for Billing"
                            and row["evidence_state"] != "Reasonably Supported"):
                        raise HTTPException(
                            409, "Billing authorization requires reasonably supported evidence"
                        )
                    approved_by, approved_at = who, stamp
                decision_reason = payload.reason
            conn.execute(
                """UPDATE salcapa_wip_reviews SET status=?,submitted_by=?,submitted_at=?,
                   approved_by=?,approved_at=?,decision_reason=?,updated_at=?
                   WHERE id=? AND tenant_id=?""",
                (payload.status, submitted_by, submitted_at, approved_by, approved_at,
                 decision_reason, stamp, review_id, tid),
            )
            audit(
                conn, "SALCAPA_COMMERCIAL_WIP_TRANSITION", "salcapa_wip_review",
                row["assessment_id"],
                f"{review_id}: {row['status']} -> {payload.status}; separate human commercial review only; no revenue, charge, invoice, scope change, or external transmission occurred; {payload.reason}"[:1000],
                who,
            )
            conn.commit()
            result = dict(conn.execute(
                "SELECT * FROM salcapa_wip_reviews WHERE id=?", (review_id,)
            ).fetchone())
        finally:
            conn.close()
        verify_wip_review(result)
        return wip_view(result)

    @app.get("/api/salcapa/commercial/membership/plans")
    def list_membership_plans(request: Request):
        salus_read(request)
        conn = db()
        try:
            rows = [dict(row) for row in conn.execute(
                "SELECT * FROM salcapa_membership_plans WHERE tenant_id=? ORDER BY version_no DESC",
                (tenant_id(request),),
            )]
        finally:
            conn.close()
        for row in rows:
            verify_membership_plan(row)
        return [membership_plan_view(row) for row in rows]

    @app.post("/api/salcapa/commercial/membership/plans")
    def create_membership_plan(payload: MembershipPlanCreate, request: Request):
        salus_write(request)
        tid, who, stamp = tenant_id(request), actor(request), now()
        entitlements = [item.model_dump(mode="json") for item in payload.entitlements]
        portfolio_pricing = [item.model_dump(mode="json") for item in payload.portfolio_pricing]
        conn = db()
        try:
            if payload.supersedes_plan_id:
                prior = conn.execute(
                    "SELECT * FROM salcapa_membership_plans WHERE id=? AND tenant_id=? AND status IN ('Approved','Retired')",
                    (payload.supersedes_plan_id, tid),
                ).fetchone()
                if not prior:
                    raise HTTPException(422, "A successor must reference an Approved or Retired plan in this tenant")
                verify_membership_plan(dict(prior))
                duplicate = conn.execute(
                    "SELECT id FROM salcapa_membership_plans WHERE supersedes_plan_id=? AND tenant_id=? AND status<>'Rejected'",
                    (payload.supersedes_plan_id, tid),
                ).fetchone()
                if duplicate:
                    raise HTTPException(409, "This membership plan already has an active successor")
            version = int(conn.execute(
                "SELECT COALESCE(MAX(version_no),0)+1 v FROM salcapa_membership_plans WHERE tenant_id=?",
                (tid,),
            ).fetchone()["v"])
            plan_id = _key("membership-plan")
            content = {
                "id": plan_id, "tenant_id": tid, "version_no": version,
                "supersedes_plan_id": payload.supersedes_plan_id,
                "name": payload.name.strip(), "arrangement": payload.arrangement,
                "effective_from": payload.effective_from, "entitlements": entitlements,
                "portfolio_pricing": portfolio_pricing,
                "member_summary": payload.member_summary.strip(),
                "internal_basis": payload.internal_basis.strip(),
            }
            conn.execute(
                """INSERT INTO salcapa_membership_plans(
                   id,tenant_id,version_no,supersedes_plan_id,name,arrangement,effective_from,
                   entitlements_json,portfolio_pricing_json,member_summary,internal_basis,
                   content_sha256,status,created_by,created_at,updated_at)
                   VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                (plan_id, tid, version, payload.supersedes_plan_id, content["name"],
                 payload.arrangement, payload.effective_from, _canonical(entitlements),
                 _canonical(portfolio_pricing), content["member_summary"], content["internal_basis"],
                 _digest(content), "Draft", who, stamp, stamp),
            )
            audit(
                conn, "SALCAPA_MEMBERSHIP_PLAN_CREATE", "salcapa_membership_plan", None,
                f"{plan_id} v{version}: Draft Protected Membership plan prepared; no customer entitlement, scope, charge, invoice, or commitment created.",
                who,
            )
            conn.commit()
            row = dict(conn.execute(
                "SELECT * FROM salcapa_membership_plans WHERE id=?", (plan_id,)
            ).fetchone())
        finally:
            conn.close()
        verify_membership_plan(row)
        return membership_plan_view(row)

    @app.post("/api/salcapa/commercial/membership/plans/{plan_id}/transition")
    def transition_membership_plan(plan_id: str, payload: MembershipPlanTransition, request: Request):
        salus_write(request)
        tid, who, stamp = tenant_id(request), actor(request), now()
        conn = db()
        try:
            found = conn.execute(
                "SELECT * FROM salcapa_membership_plans WHERE id=? AND tenant_id=?", (plan_id, tid)
            ).fetchone()
            if not found:
                raise HTTPException(404, "Protected Membership plan not found")
            row = dict(found)
            verify_membership_plan(row)
            expected = {
                "Draft": {"Submitted"}, "Submitted": {"Approved", "Rejected"},
                "Approved": {"Retired"},
            }
            if payload.status not in expected.get(row["status"], set()):
                raise HTTPException(
                    409, f"Protected Membership plan cannot transition from {row['status']} to {payload.status}"
                )
            submitted_by, submitted_at = row["submitted_by"], row["submitted_at"]
            approved_by, approved_at = row["approved_by"], row["approved_at"]
            decision_reason = row["decision_reason"]
            retired_by, retired_at, retirement_reason = (
                row["retired_by"], row["retired_at"], row["retirement_reason"]
            )
            if payload.status == "Submitted":
                submitted_by, submitted_at = who, stamp
            elif payload.status in {"Approved", "Rejected"}:
                commercial_authority(request)
                if row["created_by"] == who:
                    raise HTTPException(409, "Membership plan decision requires an actor other than the creator")
                if payload.status == "Approved":
                    approved_by, approved_at = who, stamp
                decision_reason = payload.reason
            else:
                commercial_authority(request)
                retired_by, retired_at, retirement_reason = who, stamp, payload.reason
            conn.execute(
                """UPDATE salcapa_membership_plans SET status=?,submitted_by=?,submitted_at=?,
                   approved_by=?,approved_at=?,decision_reason=?,retired_by=?,retired_at=?,
                   retirement_reason=?,updated_at=? WHERE id=? AND tenant_id=?""",
                (payload.status, submitted_by, submitted_at, approved_by, approved_at,
                 decision_reason, retired_by, retired_at, retirement_reason, stamp, plan_id, tid),
            )
            audit(
                conn, "SALCAPA_MEMBERSHIP_PLAN_TRANSITION", "salcapa_membership_plan", None,
                f"{plan_id}: {row['status']} -> {payload.status}; no automatic customer entitlement, scope, charge, invoice, renewal, or commitment; {payload.reason}"[:1000],
                who,
            )
            conn.commit()
            result = dict(conn.execute(
                "SELECT * FROM salcapa_membership_plans WHERE id=?", (plan_id,)
            ).fetchone())
        finally:
            conn.close()
        verify_membership_plan(result)
        return membership_plan_view(result)

    @app.get("/api/salcapa/commercial/membership/terms")
    def list_membership_terms(request: Request):
        require(request, "read")
        tid = tenant_id(request)
        member = protected_member(request)
        if not member:
            require_salus(request, "SalCAPA Protected Membership")
        conn = db()
        try:
            sql = "SELECT * FROM salcapa_membership_terms WHERE tenant_id=?"
            if member:
                sql += " AND status='Released'"
            sql += " ORDER BY version_no DESC"
            rows = [dict(row) for row in conn.execute(sql, (tid,))]
            for row in rows:
                verify_membership_term(row)
            return [membership_term_view(conn, row, member) for row in rows]
        finally:
            conn.close()

    @app.post("/api/salcapa/commercial/membership/terms")
    def create_membership_term(payload: MembershipTermCreate, request: Request):
        salus_write(request)
        tid, who, stamp = tenant_id(request), actor(request), now()
        coverage = [item.model_dump(mode="json") for item in payload.portfolio_coverage]
        conn = db()
        try:
            found_plan = conn.execute(
                "SELECT * FROM salcapa_membership_plans WHERE id=? AND tenant_id=? AND status='Approved'",
                (payload.plan_id, tid),
            ).fetchone()
            if not found_plan:
                raise HTTPException(422, "A term requires an Approved, active membership plan in this tenant")
            plan = dict(found_plan)
            verify_membership_plan(plan)
            if payload.supersedes_term_id:
                prior = conn.execute(
                    "SELECT * FROM salcapa_membership_terms WHERE id=? AND tenant_id=? AND status IN ('Approved','Released')",
                    (payload.supersedes_term_id, tid),
                ).fetchone()
                if not prior:
                    raise HTTPException(422, "A successor term must reference an Approved or Released term in this tenant")
                verify_membership_term(dict(prior))
                duplicate = conn.execute(
                    "SELECT id FROM salcapa_membership_terms WHERE supersedes_term_id=? AND tenant_id=? AND status<>'Rejected'",
                    (payload.supersedes_term_id, tid),
                ).fetchone()
                if duplicate:
                    raise HTTPException(409, "This membership term already has an active successor")
            version = int(conn.execute(
                "SELECT COALESCE(MAX(version_no),0)+1 v FROM salcapa_membership_terms WHERE tenant_id=?",
                (tid,),
            ).fetchone()["v"])
            term_id = _key("membership-term")
            plan_snapshot = plan_content(plan)
            content = {
                "id": term_id, "tenant_id": tid, "version_no": version,
                "supersedes_term_id": payload.supersedes_term_id,
                "plan_id": plan["id"], "plan_version": int(plan["version_no"]),
                "plan_snapshot": plan_snapshot, "contract_reference": payload.contract_reference.strip(),
                "start_date": payload.start_date, "end_date": payload.end_date,
                "renewal_review_date": payload.renewal_review_date,
                "billing_cadence": payload.billing_cadence,
                "recurring_fee_cents": payload.recurring_fee_cents,
                "approved_term_value_cents": payload.approved_term_value_cents,
                "portfolio_coverage": coverage,
                "negotiated_terms": payload.negotiated_terms.strip(),
                "internal_basis": payload.internal_basis.strip(),
            }
            conn.execute(
                """INSERT INTO salcapa_membership_terms(
                   id,tenant_id,version_no,supersedes_term_id,plan_id,plan_version,plan_snapshot_json,
                   contract_reference,start_date,end_date,renewal_review_date,billing_cadence,
                   recurring_fee_cents,approved_term_value_cents,portfolio_coverage_json,
                   negotiated_terms,internal_basis,content_sha256,status,creates_charge,creates_invoice,
                   creates_entitlement_automatically,authorizes_scope_automatically,auto_renews,
                   created_by,created_at,updated_at)
                   VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                (term_id, tid, version, payload.supersedes_term_id, plan["id"], plan["version_no"],
                 _canonical(plan_snapshot), content["contract_reference"], payload.start_date,
                 payload.end_date, payload.renewal_review_date, payload.billing_cadence,
                 payload.recurring_fee_cents, payload.approved_term_value_cents, _canonical(coverage),
                 content["negotiated_terms"], content["internal_basis"], _digest(content), "Draft",
                 0, 0, 0, 0, 0, who, stamp, stamp),
            )
            audit(
                conn, "SALCAPA_MEMBERSHIP_TERM_CREATE", "salcapa_membership_term", None,
                f"{term_id} v{version}: Draft term snapshots plan v{plan['version_no']}; no entitlement, scope, charge, invoice, renewal, or commitment is active.",
                who,
            )
            conn.commit()
            row = dict(conn.execute(
                "SELECT * FROM salcapa_membership_terms WHERE id=?", (term_id,)
            ).fetchone())
            verify_membership_term(row)
            return membership_term_view(conn, row, False)
        finally:
            conn.close()

    @app.post("/api/salcapa/commercial/membership/terms/{term_id}/transition")
    def transition_membership_term(term_id: str, payload: MembershipTermTransition, request: Request):
        salus_write(request)
        tid, who, stamp = tenant_id(request), actor(request), now()
        conn = db()
        try:
            found = conn.execute(
                "SELECT * FROM salcapa_membership_terms WHERE id=? AND tenant_id=?", (term_id, tid)
            ).fetchone()
            if not found:
                raise HTTPException(404, "Protected Membership term not found")
            row = dict(found)
            verify_membership_term(row)
            expected = {"Draft": {"Submitted"}, "Submitted": {"Approved", "Rejected"}, "Approved": {"Released"}}
            if payload.status not in expected.get(row["status"], set()):
                raise HTTPException(
                    409, f"Protected Membership term cannot transition from {row['status']} to {payload.status}"
                )
            submitted_by, submitted_at = row["submitted_by"], row["submitted_at"]
            approved_by, approved_at = row["approved_by"], row["approved_at"]
            released_by, released_at = row["released_by"], row["released_at"]
            decision_reason, release_reason = row["decision_reason"], row["release_reason"]
            if payload.status == "Submitted":
                submitted_by, submitted_at = who, stamp
            elif payload.status in {"Approved", "Rejected"}:
                commercial_authority(request)
                if row["created_by"] == who:
                    raise HTTPException(409, "Membership term decision requires an actor other than the creator")
                if payload.status == "Approved":
                    approved_by, approved_at = who, stamp
                decision_reason = payload.reason
            else:
                commercial_authority(request)
                if who != row["approved_by"]:
                    raise HTTPException(409, "The recorded term approver must authorize member release")
                released_by, released_at, release_reason = who, stamp, payload.reason
            conn.execute(
                """UPDATE salcapa_membership_terms SET status=?,submitted_by=?,submitted_at=?,
                   approved_by=?,approved_at=?,released_by=?,released_at=?,decision_reason=?,
                   release_reason=?,updated_at=? WHERE id=? AND tenant_id=?""",
                (payload.status, submitted_by, submitted_at, approved_by, approved_at,
                 released_by, released_at, decision_reason, release_reason, stamp, term_id, tid),
            )
            audit(
                conn, "SALCAPA_MEMBERSHIP_TERM_TRANSITION", "salcapa_membership_term", None,
                f"{term_id}: {row['status']} -> {payload.status}; human authority retained; no automatic charge, invoice, renewal, tier change, partner action, or scope expansion; {payload.reason}"[:1000],
                who,
            )
            conn.commit()
            result = dict(conn.execute(
                "SELECT * FROM salcapa_membership_terms WHERE id=?", (term_id,)
            ).fetchone())
            verify_membership_term(result)
            return membership_term_view(conn, result, False)
        finally:
            conn.close()

    @app.get("/api/salcapa/commercial/membership/consumption")
    def list_membership_consumption(request: Request, term_id: Optional[str] = None):
        salus_read(request)
        tid = tenant_id(request)
        conn = db()
        try:
            if term_id:
                term = conn.execute(
                    "SELECT id FROM salcapa_membership_terms WHERE id=? AND tenant_id=?", (term_id, tid)
                ).fetchone()
                if not term:
                    raise HTTPException(404, "Protected Membership term not found")
                rows = [dict(row) for row in conn.execute(
                    "SELECT * FROM salcapa_membership_consumption WHERE tenant_id=? AND term_id=? ORDER BY version_no",
                    (tid, term_id),
                )]
            else:
                rows = [dict(row) for row in conn.execute(
                    "SELECT * FROM salcapa_membership_consumption WHERE tenant_id=? ORDER BY version_no", (tid,)
                )]
            for row in rows:
                verify_membership_consumption(row)
            return [membership_consumption_view(conn, row) for row in rows]
        finally:
            conn.close()

    @app.post("/api/salcapa/commercial/membership/consumption")
    def create_membership_consumption(payload: MembershipConsumptionCreate, request: Request):
        salus_write(request)
        tid, who, stamp = tenant_id(request), actor(request), now()
        conn = db()
        try:
            found_term = conn.execute(
                "SELECT * FROM salcapa_membership_terms WHERE id=? AND tenant_id=? AND status IN ('Approved','Released')",
                (payload.term_id, tid),
            ).fetchone()
            if not found_term:
                raise HTTPException(422, "Consumption requires an Approved or Released term in this tenant")
            term = dict(found_term)
            verify_membership_term(term)
            occurred = date.fromisoformat(payload.occurred_on)
            if not date.fromisoformat(term["start_date"]) <= occurred <= date.fromisoformat(term["end_date"]):
                raise HTTPException(422, "Consumption date must fall within the governed membership term")
            entitlements = json.loads(term["plan_snapshot_json"])["entitlements"]
            entitlement = next((item for item in entitlements if item["key"] == payload.entitlement_key), None)
            if not entitlement:
                raise HTTPException(422, "Consumption must reference an entitlement in the term snapshot")
            if entitlement["capacity_type"] == "Commercial Treatment Only":
                raise HTTPException(422, "Commercial-treatment-only services require a separate governed estimate or add-on")
            if payload.estimate_id:
                estimate = conn.execute(
                    "SELECT * FROM salcapa_commercial_estimates WHERE id=? AND tenant_id=? AND status IN ('Approved','Released')",
                    (payload.estimate_id, tid),
                ).fetchone()
                if not estimate:
                    raise HTTPException(422, "Linked estimate must be Approved or Released within this tenant")
                verify_estimate(dict(estimate))
                if payload.source_type == "Estimate" and payload.source_record_id != payload.estimate_id:
                    raise HTTPException(422, "Estimate source_record_id must match estimate_id")
            if payload.supersedes_consumption_id:
                prior = conn.execute(
                    """SELECT * FROM salcapa_membership_consumption
                       WHERE id=? AND tenant_id=? AND term_id=? AND entitlement_key=? AND status='Approved'""",
                    (payload.supersedes_consumption_id, tid, payload.term_id, payload.entitlement_key),
                ).fetchone()
                if not prior:
                    raise HTTPException(422, "A correction must replace an Approved record in the same entitlement")
                verify_membership_consumption(dict(prior))
                duplicate = conn.execute(
                    "SELECT id FROM salcapa_membership_consumption WHERE supersedes_consumption_id=? AND tenant_id=? AND status<>'Rejected'",
                    (payload.supersedes_consumption_id, tid),
                ).fetchone()
                if duplicate:
                    raise HTTPException(409, "This consumption record already has an active correction")
            version = int(conn.execute(
                "SELECT COALESCE(MAX(version_no),0)+1 v FROM salcapa_membership_consumption WHERE tenant_id=?",
                (tid,),
            ).fetchone()["v"])
            consumption_id = _key("membership-use")
            quantity = format(payload.quantity, "f")
            content = {
                "id": consumption_id, "tenant_id": tid, "version_no": version,
                "term_id": payload.term_id,
                "supersedes_consumption_id": payload.supersedes_consumption_id,
                "entitlement_key": payload.entitlement_key,
                "entitlement_snapshot": entitlement, "quantity": quantity,
                "occurred_on": payload.occurred_on, "source_type": payload.source_type,
                "source_record_id": payload.source_record_id.strip(),
                "source_reference": payload.source_reference.strip(),
                "estimate_id": payload.estimate_id, "notes": payload.notes.strip(),
            }
            conn.execute(
                """INSERT INTO salcapa_membership_consumption(
                   id,tenant_id,version_no,term_id,supersedes_consumption_id,entitlement_key,
                   entitlement_snapshot_json,quantity,occurred_on,source_type,source_record_id,
                   source_reference,estimate_id,notes,content_sha256,status,creates_charge,
                   creates_invoice,creates_scope_authorization,created_by,created_at,updated_at)
                   VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                (consumption_id, tid, version, payload.term_id, payload.supersedes_consumption_id,
                 payload.entitlement_key, _canonical(entitlement), quantity, payload.occurred_on,
                 payload.source_type, content["source_record_id"], content["source_reference"],
                 payload.estimate_id, content["notes"], _digest(content), "Draft", 0, 0, 0,
                 who, stamp, stamp),
            )
            audit(
                conn, "SALCAPA_MEMBERSHIP_CONSUMPTION_CREATE", "salcapa_membership_consumption", None,
                f"{consumption_id} v{version}: Draft supported consumption prepared for independent review; excess capacity requires a separate decision and never creates a charge or scope change automatically.",
                who,
            )
            conn.commit()
            row = dict(conn.execute(
                "SELECT * FROM salcapa_membership_consumption WHERE id=?", (consumption_id,)
            ).fetchone())
            verify_membership_consumption(row)
            return membership_consumption_view(conn, row)
        finally:
            conn.close()

    @app.post("/api/salcapa/commercial/membership/consumption/{consumption_id}/transition")
    def transition_membership_consumption(consumption_id: str, payload: MembershipConsumptionTransition,
                                          request: Request):
        salus_write(request)
        tid, who, stamp = tenant_id(request), actor(request), now()
        conn = db()
        try:
            found = conn.execute(
                "SELECT * FROM salcapa_membership_consumption WHERE id=? AND tenant_id=?",
                (consumption_id, tid),
            ).fetchone()
            if not found:
                raise HTTPException(404, "Protected Membership consumption record not found")
            row = dict(found)
            verify_membership_consumption(row)
            expected = {"Draft": {"Submitted"}, "Submitted": {"Approved", "Rejected"}}
            if payload.status not in expected.get(row["status"], set()):
                raise HTTPException(
                    409, f"Protected Membership consumption cannot transition from {row['status']} to {payload.status}"
                )
            submitted_by, submitted_at = row["submitted_by"], row["submitted_at"]
            approved_by, approved_at = row["approved_by"], row["approved_at"]
            decision_reason = row["decision_reason"]
            if payload.status == "Submitted":
                submitted_by, submitted_at = who, stamp
            else:
                commercial_authority(request)
                if row["created_by"] == who:
                    raise HTTPException(409, "Consumption decision requires an actor other than the creator")
                if payload.status == "Approved":
                    approved_by, approved_at = who, stamp
                decision_reason = payload.reason
            conn.execute(
                """UPDATE salcapa_membership_consumption SET status=?,submitted_by=?,submitted_at=?,
                   approved_by=?,approved_at=?,decision_reason=?,updated_at=? WHERE id=? AND tenant_id=?""",
                (payload.status, submitted_by, submitted_at, approved_by, approved_at,
                 decision_reason, stamp, consumption_id, tid),
            )
            audit(
                conn, "SALCAPA_MEMBERSHIP_CONSUMPTION_TRANSITION", "salcapa_membership_consumption", None,
                f"{consumption_id}: {row['status']} -> {payload.status}; consumption evidence only; no automatic charge, invoice, add-on, tier change, partner action, or scope expansion; {payload.reason}"[:1000],
                who,
            )
            conn.commit()
            result = dict(conn.execute(
                "SELECT * FROM salcapa_membership_consumption WHERE id=?", (consumption_id,)
            ).fetchone())
            verify_membership_consumption(result)
            return membership_consumption_view(conn, result)
        finally:
            conn.close()

    original_collect = core.get("collect_tenant_records")
    original_validate = core.get("validate_records")
    original_replace = core.get("replace_tenant_records")
    if original_collect and original_validate and original_replace:
        def extended_collect(conn, tid: int):
            records = original_collect(conn, tid)
            for table in BACKUP_TABLES:
                records[table] = [dict(r) for r in conn.execute(
                    f"SELECT * FROM {table} WHERE tenant_id=? ORDER BY version_no,id", (tid,)
                )]
            return records

        def commercial_validate(records: dict, tid: int) -> list[str]:
            errors: list[str] = []
            cards = {str(r.get("id")): r for r in records.get("salcapa_rate_cards", [])}
            estimates = {str(r.get("id")): r for r in records.get("salcapa_commercial_estimates", [])}
            time_entries = {str(r.get("id")): r for r in records.get("salcapa_time_entries", [])}
            cost_entries = {str(r.get("id")): r for r in records.get("salcapa_cost_entries", [])}
            forecasts = {str(r.get("id")): r for r in records.get("salcapa_commercial_forecasts", [])}
            wip_reviews = {
                str(r.get("id")): r for r in records.get("salcapa_wip_reviews", [])
            }
            membership_plans = {
                str(r.get("id")): r for r in records.get("salcapa_membership_plans", [])
            }
            membership_terms = {
                str(r.get("id")): r for r in records.get("salcapa_membership_terms", [])
            }
            membership_consumption = {
                str(r.get("id")): r for r in records.get("salcapa_membership_consumption", [])
            }
            for row in cards.values():
                if int(row.get("tenant_id", -1)) != int(tid):
                    errors.append(f"rate card {row.get('id')} crosses the tenant boundary")
                    continue
                try:
                    verify_card(dict(row))
                except (HTTPException, ValueError, TypeError):
                    errors.append(f"rate card {row.get('id')} failed integrity verification")
                prior = row.get("supersedes_id")
                if prior and str(prior) not in cards:
                    errors.append(f"rate card {row.get('id')} has invalid supersedes_id")
            for row in estimates.values():
                if int(row.get("tenant_id", -1)) != int(tid):
                    errors.append(f"commercial estimate {row.get('id')} crosses the tenant boundary")
                    continue
                if str(row.get("rate_card_id")) not in cards:
                    errors.append(f"commercial estimate {row.get('id')} has invalid rate_card_id")
                prior = row.get("supersedes_estimate_id")
                if prior and str(prior) not in estimates:
                    errors.append(f"commercial estimate {row.get('id')} has invalid supersedes_estimate_id")
                try:
                    verify_estimate(dict(row))
                except (HTTPException, ValueError, TypeError):
                    errors.append(f"commercial estimate {row.get('id')} failed integrity verification")
            for kind, entries in (("time", time_entries), ("cost", cost_entries)):
                for row in entries.values():
                    if int(row.get("tenant_id", -1)) != int(tid):
                        errors.append(f"commercial {kind} entry {row.get('id')} crosses the tenant boundary")
                        continue
                    estimate = estimates.get(str(row.get("estimate_id")))
                    if not estimate:
                        errors.append(f"commercial {kind} entry {row.get('id')} has invalid estimate_id")
                    elif (row.get("engagement_id") != estimate.get("engagement_id") or
                          row.get("assessment_id") != estimate.get("assessment_id")):
                        errors.append(f"commercial {kind} entry {row.get('id')} crosses its estimate scope")
                    prior_id = row.get("supersedes_entry_id")
                    if prior_id:
                        prior = entries.get(str(prior_id))
                        if not prior or prior.get("estimate_id") != row.get("estimate_id"):
                            errors.append(f"commercial {kind} entry {row.get('id')} has invalid correction lineage")
                    try:
                        verify_actual_entry(dict(row), kind)
                    except (HTTPException, ValueError, TypeError, KeyError):
                        errors.append(f"commercial {kind} entry {row.get('id')} failed integrity verification")
            for row in forecasts.values():
                if int(row.get("tenant_id", -1)) != int(tid):
                    errors.append(f"commercial forecast {row.get('id')} crosses the tenant boundary")
                    continue
                estimate = estimates.get(str(row.get("estimate_id")))
                if not estimate:
                    errors.append(f"commercial forecast {row.get('id')} has invalid estimate_id")
                elif (row.get("engagement_id") != estimate.get("engagement_id") or
                      row.get("assessment_id") != estimate.get("assessment_id")):
                    errors.append(f"commercial forecast {row.get('id')} crosses its estimate scope")
                prior_id = row.get("supersedes_forecast_id")
                if prior_id:
                    prior = forecasts.get(str(prior_id))
                    if not prior or prior.get("estimate_id") != row.get("estimate_id"):
                        errors.append(f"commercial forecast {row.get('id')} has invalid revision lineage")
                try:
                    verify_forecast(dict(row))
                except (HTTPException, ValueError, TypeError, KeyError):
                    errors.append(f"commercial forecast {row.get('id')} failed integrity verification")
            for row in wip_reviews.values():
                if int(row.get("tenant_id", -1)) != int(tid):
                    errors.append(f"WIP review {row.get('id')} crosses the tenant boundary")
                    continue
                estimate = estimates.get(str(row.get("estimate_id")))
                if not estimate:
                    errors.append(f"WIP review {row.get('id')} has invalid estimate_id")
                elif (row.get("engagement_id") != estimate.get("engagement_id") or
                      row.get("assessment_id") != estimate.get("assessment_id")):
                    errors.append(f"WIP review {row.get('id')} crosses its estimate scope")
                prior_id = row.get("supersedes_wip_review_id")
                if prior_id:
                    prior = wip_reviews.get(str(prior_id))
                    if not prior or prior.get("estimate_id") != row.get("estimate_id"):
                        errors.append(f"WIP review {row.get('id')} has invalid revision lineage")
                try:
                    snapshot = json.loads(row.get("source_snapshot_json", "{}"))
                    estimate_snapshot = snapshot.get("estimate", {})
                    if estimate and (
                        estimate_snapshot.get("id") != estimate.get("id")
                        or int(estimate_snapshot.get("version_no", -1))
                        != int(estimate.get("version_no", -2))
                        or estimate_snapshot.get("content_sha256")
                        != estimate.get("content_sha256")
                    ):
                        errors.append(f"WIP review {row.get('id')} estimate snapshot does not match")
                    verify_wip_review(dict(row))
                except (HTTPException, ValueError, TypeError, KeyError):
                    errors.append(f"WIP review {row.get('id')} failed integrity verification")
            for row in membership_plans.values():
                if int(row.get("tenant_id", -1)) != int(tid):
                    errors.append(f"membership plan {row.get('id')} crosses the tenant boundary")
                    continue
                prior_id = row.get("supersedes_plan_id")
                if prior_id and str(prior_id) not in membership_plans:
                    errors.append(f"membership plan {row.get('id')} has invalid revision lineage")
                try:
                    verify_membership_plan(dict(row))
                except (HTTPException, ValueError, TypeError, KeyError):
                    errors.append(f"membership plan {row.get('id')} failed integrity verification")
            for row in membership_terms.values():
                if int(row.get("tenant_id", -1)) != int(tid):
                    errors.append(f"membership term {row.get('id')} crosses the tenant boundary")
                    continue
                plan = membership_plans.get(str(row.get("plan_id")))
                if not plan:
                    errors.append(f"membership term {row.get('id')} has invalid plan_id")
                else:
                    try:
                        if int(row.get("plan_version", -1)) != int(plan.get("version_no", -2)):
                            errors.append(f"membership term {row.get('id')} has invalid plan version")
                        if _canonical(json.loads(row.get("plan_snapshot_json", "{}"))) != _canonical(
                            plan_content(dict(plan))
                        ):
                            errors.append(f"membership term {row.get('id')} plan snapshot does not match")
                    except (ValueError, TypeError, KeyError):
                        errors.append(f"membership term {row.get('id')} plan snapshot is invalid")
                prior_id = row.get("supersedes_term_id")
                if prior_id and str(prior_id) not in membership_terms:
                    errors.append(f"membership term {row.get('id')} has invalid revision lineage")
                try:
                    verify_membership_term(dict(row))
                except (HTTPException, ValueError, TypeError, KeyError):
                    errors.append(f"membership term {row.get('id')} failed integrity verification")
            for row in membership_consumption.values():
                if int(row.get("tenant_id", -1)) != int(tid):
                    errors.append(f"membership consumption {row.get('id')} crosses the tenant boundary")
                    continue
                term = membership_terms.get(str(row.get("term_id")))
                if not term:
                    errors.append(f"membership consumption {row.get('id')} has invalid term_id")
                else:
                    try:
                        entitlements = json.loads(term.get("plan_snapshot_json", "{}"))["entitlements"]
                        expected_entitlement = next(
                            item for item in entitlements if item["key"] == row.get("entitlement_key")
                        )
                        if _canonical(json.loads(row.get("entitlement_snapshot_json", "{}"))) != _canonical(
                            expected_entitlement
                        ):
                            errors.append(
                                f"membership consumption {row.get('id')} entitlement snapshot does not match"
                            )
                    except (ValueError, TypeError, KeyError, StopIteration):
                        errors.append(f"membership consumption {row.get('id')} entitlement is invalid")
                estimate_id = row.get("estimate_id")
                if estimate_id and str(estimate_id) not in estimates:
                    errors.append(f"membership consumption {row.get('id')} has invalid estimate_id")
                if row.get("source_type") == "Estimate" and row.get("source_record_id") != estimate_id:
                    errors.append(f"membership consumption {row.get('id')} has inconsistent estimate source")
                prior_id = row.get("supersedes_consumption_id")
                if prior_id:
                    prior = membership_consumption.get(str(prior_id))
                    if not prior or prior.get("term_id") != row.get("term_id") or prior.get(
                        "entitlement_key"
                    ) != row.get("entitlement_key"):
                        errors.append(f"membership consumption {row.get('id')} has invalid correction lineage")
                try:
                    verify_membership_consumption(dict(row))
                    if Decimal(str(row.get("quantity", "0"))) <= 0:
                        errors.append(f"membership consumption {row.get('id')} quantity is invalid")
                except (HTTPException, ValueError, TypeError, KeyError):
                    errors.append(f"membership consumption {row.get('id')} failed integrity verification")
            return errors

        def extended_validate(records: dict, tid: Optional[int] = None):
            errors = list(original_validate(records, tid))
            if tid is not None:
                errors.extend(commercial_validate(records, int(tid)))
            return errors

        def insert_row(conn, table: str, row: dict[str, Any]) -> None:
            allowed = {r["name"] for r in conn.execute(f"PRAGMA table_info({table})")}
            data = {k: v for k, v in row.items() if k in allowed}
            if data:
                conn.execute(
                    f"INSERT INTO {table}({','.join(data)}) VALUES({','.join('?' * len(data))})",
                    tuple(data.values()),
                )

        def extended_replace(conn, tid: int, records: dict):
            errors = list(original_validate(records, tid)) + commercial_validate(records, tid)
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
