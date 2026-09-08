"""Governed SalCAPA commercial planning, rate-card, and estimate foundation.

Issue #154 increment.  Salus personnel configure and approve versioned planning
assumptions.  Estimates snapshot every assumption and calculation.  Nothing in
this module creates a charge, invoice, entitlement, scope authorization, or
customer commitment.
"""
from __future__ import annotations

import hashlib
import json
import uuid
from decimal import Decimal, ROUND_HALF_UP
from typing import Any, Literal, Optional

from fastapi import HTTPException, Request
from pydantic import BaseModel, ConfigDict, Field, field_validator


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
TIERS = ("Tier 1", "Tier 2", "Tier 3", "Not Applicable")
BACKUP_TABLES = ("salcapa_rate_cards", "salcapa_commercial_estimates")
DELETE_ORDER = ("salcapa_commercial_estimates", "salcapa_rate_cards")
RESTORE_ORDER = ("salcapa_rate_cards", "salcapa_commercial_estimates")


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


def _validate_rules(rules: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(rules, dict) or rules.get("schema_version") != "1.0" or rules.get("currency") != "USD":
        raise HTTPException(422, "Rate-card rules must use the governed USD schema version 1.0")
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
    return json.loads(_canonical(rules))


def _calculate(payload: EstimateCreate, rules: dict[str, Any]) -> tuple[dict[str, Any], dict[str, Any]]:
    tier = payload.investigation_tier
    multiplier = Decimal(rules["complexity_basis_points"][payload.complexity]) / Decimal(10000)
    overrides = rules["domain_human_hour_overrides"].get(payload.domain_key, {})
    if payload.custom_human_hours is not None:
        base_hours = Decimal(payload.custom_human_hours)
        hour_basis = "Salus-authorized custom estimate"
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
    technology = _money(
        Decimal(rules["technology_planning_allowance_cents"][tier]) * multiplier
        + Decimal(rules["technology_planning_allowance_cents"]["Monitoring Cycle"])
        * multiplier * Decimal(payload.monitoring_cycles)
    )
    loaded_labor = _money(human_hours * Decimal(rules["loaded_labor_cost_cents_per_hour"]))
    bill_rate = rules[
        "senior_bill_rate_cents_per_hour" if payload.senior_specialist
        else "standard_bill_rate_cents_per_hour"
    ]
    customer_labor = _money(human_hours * Decimal(bill_rate))
    internal_cost = loaded_labor + technology + payload.partner_cost_cents + payload.other_direct_cost_cents
    base_price = customer_labor + technology + payload.partner_cost_cents + payload.other_direct_cost_cents
    contingency = 0
    if payload.pricing_method in {"Suggested Fixed Fee", "Bundled", "Milestone", "Custom"}:
        contingency = _money(Decimal(base_price) * Decimal(rules["fixed_fee_contingency_basis_points"]) / Decimal(10000))
    unrounded = max(0, base_price + contingency - payload.discount_cents)
    if payload.pricing_method == "Membership Included":
        recommended = 0
    else:
        increment = int(rules["rounding_increment_cents"])
        recommended = _money(Decimal(unrounded) / Decimal(increment)) * increment
    margin = recommended - internal_cost
    margin_bps = None if recommended <= 0 else _money(Decimal(margin) * Decimal(10000) / Decimal(recommended))
    inputs = payload.model_dump(mode="json")
    calculation = {
        "human_hours": format(human_hours, "f"), "human_hours_basis": hour_basis,
        "technology_planning_allowance_cents": technology,
        "estimated_loaded_labor_cost_cents": loaded_labor,
        "customer_labor_equivalent_cents": customer_labor,
        "partner_cost_cents": payload.partner_cost_cents,
        "other_direct_cost_cents": payload.other_direct_cost_cents,
        "contingency_cents": contingency, "discount_cents": payload.discount_cents,
        "unrounded_recommendation_cents": unrounded,
        "rounding_increment_cents": rules["rounding_increment_cents"],
        "recommended_customer_price_cents": recommended,
        "estimated_internal_cost_cents": internal_cost,
        "estimated_margin_cents": margin,
        "estimated_margin_basis_points": margin_bps,
        "actual_cost_status": "Not Recorded",
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

    @app.get("/api/salcapa/commercial/catalog")
    def commercial_catalog(request: Request):
        salus_read(request)
        return {
            "product_lines": list(PRODUCT_LINES), "investigation_tiers": list(TIERS),
            "complexities": list(COMPLEXITIES), "pricing_methods": list(PRICING_METHODS),
            "initial_planning_defaults": json.loads(_canonical(DEFAULT_RULES)),
            "guidance": {
                "purpose": "Prepare a transparent planning estimate for authorized Salus review.",
                "authority": "Authorized Salus personnel configure assumptions and independently approve customer price.",
                "consequence": "A recommendation is not a charge, invoice, entitlement, scope authorization, or customer commitment.",
                "next_step": "Submit the immutable estimate for independent commercial review, then release approved customer-facing terms separately.",
                "actual_cost_truth": "When actual provider or labor cost is unavailable, the planning allowance remains clearly identified rather than presented as metered actual cost.",
            },
        }

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
        inputs, calculation = _calculate(payload, rules)
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
