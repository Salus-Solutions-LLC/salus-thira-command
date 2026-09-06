"""SalCAPA Pricing & Cost Engine core.

Pure-domain implementation for commercial pricing, internal cost, margin,
membership capacity, assessment scope, premium multipliers and quote guidance.
All currency arithmetic uses Decimal.  This module deliberately contains no
HTTP or persistence dependencies so pricing policy can be validated before UI
or database integration.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal, ROUND_HALF_UP
from enum import Enum
from typing import Iterable, Optional

MONEY = Decimal("0.01")


def D(value) -> Decimal:
    if isinstance(value, Decimal):
        return value
    return Decimal(str(value))


def money(value) -> Decimal:
    return D(value).quantize(MONEY, rounding=ROUND_HALF_UP)


class RevenueClass(str, Enum):
    MEMBERSHIP = "Membership"
    ASSESSMENT = "Assessment"
    INVESTIGATION = "Investigation"
    OPERATIONS = "Operations"
    SPECIAL_PROJECT = "Special Project"


class AssessmentLevel(str, Enum):
    LEVEL_I = "Level I"
    LEVEL_II = "Level II"
    LEVEL_III = "Level III"
    CRITICAL_INFRASTRUCTURE = "Critical Infrastructure / Complex Enterprise"


class InvestigationDisposition(str, Enum):
    RESOLVED = "Resolved"
    SUBSTANTIALLY_RESOLVED = "Substantially Resolved"
    PARTIALLY_RESOLVED = "Partially Resolved"
    UNRESOLVED = "Unresolved"
    CONTRADICTORY = "Contradictory"
    OUTSIDE_SCOPE = "Outside Scope"
    ESCALATION_RECOMMENDED = "Escalation Recommended"


class CapacityStatus(str, Enum):
    NORMAL = "Normal"
    MONITOR = "Monitor"
    ADVISORY = "Advisory"
    WARNING = "Capacity Warning"
    OVERAGE = "Overage"


class ScopeStatus(str, Enum):
    NORMAL = "Normal"
    YELLOW = "Yellow"
    ORANGE = "Orange"
    STOP = "Work Stop / Authorization Required"


@dataclass(frozen=True)
class LaborCategory:
    name: str
    commercial_rate: Decimal

    def __post_init__(self):
        object.__setattr__(self, "commercial_rate", money(self.commercial_rate))


DEFAULT_LABOR_CATEGORIES = {
    "Research / Investigative Support": LaborCategory("Research / Investigative Support", D("125")),
    "Analyst": LaborCategory("Analyst", D("150")),
    "Intelligence Analyst": LaborCategory("Intelligence Analyst", D("175")),
    "Investigator": LaborCategory("Investigator", D("175")),
    "Senior Investigator": LaborCategory("Senior Investigator", D("225")),
    "Protective Intelligence Analyst": LaborCategory("Protective Intelligence Analyst", D("225")),
    "Security / Emergency Management Consultant": LaborCategory("Security / Emergency Management Consultant", D("225")),
    "Senior Consultant": LaborCategory("Senior Consultant", D("275")),
    "Cybersecurity Specialist": LaborCategory("Cybersecurity Specialist", D("275")),
    "Program / Incident Manager": LaborCategory("Program / Incident Manager", D("300")),
    "Subject Matter Expert": LaborCategory("Subject Matter Expert", D("325")),
    "Principal SME": LaborCategory("Principal SME", D("375")),
    "Executive / Strategic Advisor": LaborCategory("Executive / Strategic Advisor", D("425")),
    "Specialized National-Level Advisor": LaborCategory("Specialized National-Level Advisor", D("500")),
}


@dataclass(frozen=True)
class CostProfile:
    annual_compensation: Decimal
    payroll_burden_benefits: Decimal = D("0")
    insurance_training_licensing_equipment: Decimal = D("0")
    allocated_technology_overhead: Decimal = D("0")
    productive_hours: Decimal = D("1300")

    def __post_init__(self):
        for name in (
            "annual_compensation", "payroll_burden_benefits",
            "insurance_training_licensing_equipment", "allocated_technology_overhead",
            "productive_hours",
        ):
            object.__setattr__(self, name, D(getattr(self, name)))
        if self.productive_hours <= 0:
            raise ValueError("productive_hours must be greater than zero")

    @property
    def annual_loaded_cost(self) -> Decimal:
        return money(
            self.annual_compensation
            + self.payroll_burden_benefits
            + self.insurance_training_licensing_equipment
            + self.allocated_technology_overhead
        )

    @property
    def productive_hour_cost(self) -> Decimal:
        return money(self.annual_loaded_cost / self.productive_hours)


@dataclass(frozen=True)
class ContractorCostProfile:
    contractor_rate: Decimal
    burden_percent: Decimal = D("0")
    supervision_per_hour: Decimal = D("0")
    technology_equipment_per_hour: Decimal = D("0")

    def __post_init__(self):
        for name in ("contractor_rate", "burden_percent", "supervision_per_hour", "technology_equipment_per_hour"):
            object.__setattr__(self, name, D(getattr(self, name)))

    @property
    def productive_hour_cost(self) -> Decimal:
        burden = self.contractor_rate * self.burden_percent / D("100")
        return money(self.contractor_rate + burden + self.supervision_per_hour + self.technology_equipment_per_hour)


@dataclass(frozen=True)
class MembershipPlan:
    name: str
    monthly_price: Decimal
    included_capacity_hours: Decimal
    overage_rate: Decimal

    def __post_init__(self):
        for name in ("monthly_price", "included_capacity_hours", "overage_rate"):
            object.__setattr__(self, name, D(getattr(self, name)))

    @property
    def annual_price(self) -> Decimal:
        return money(self.monthly_price * 12)


DEFAULT_MEMBERSHIP_PLANS = {
    "Access": MembershipPlan("SalCAPA Access", D("2500"), D("1"), D("275")),
    "Protected Member": MembershipPlan("SalCAPA Protected Member", D("6000"), D("4"), D("250")),
    "Enterprise": MembershipPlan("SalCAPA Enterprise", D("15000"), D("12"), D("225")),
    "Strategic": MembershipPlan("SalCAPA Strategic / Critical Infrastructure", D("30000"), D("30"), D("225")),
}


DEFAULT_ASSESSMENT_BASE_PRICES = {
    AssessmentLevel.LEVEL_I: D("7500"),
    AssessmentLevel.LEVEL_II: D("17500"),
    AssessmentLevel.LEVEL_III: D("35000"),
    AssessmentLevel.CRITICAL_INFRASTRUCTURE: D("75000"),
}


@dataclass(frozen=True)
class ComplexityFactors:
    facilities: Decimal = D("0")
    principals: Decimal = D("0")
    geography: Decimal = D("0")
    threat_risk: Decimal = D("0")
    intelligence_requirement: Decimal = D("0")
    support_intensity: Decimal = D("0")
    response_requirement: Decimal = D("0")
    regulatory_complexity: Decimal = D("0")

    WEIGHTS = {
        "facilities": D("0.15"),
        "principals": D("0.10"),
        "geography": D("0.10"),
        "threat_risk": D("0.20"),
        "intelligence_requirement": D("0.15"),
        "support_intensity": D("0.15"),
        "response_requirement": D("0.10"),
        "regulatory_complexity": D("0.05"),
    }

    def score(self) -> Decimal:
        total = D("0")
        for name, weight in self.WEIGHTS.items():
            value = D(getattr(self, name))
            if value < 0 or value > 100:
                raise ValueError(f"{name} must be between 0 and 100")
            total += value * weight
        return total.quantize(D("0.1"), rounding=ROUND_HALF_UP)

    def recommended_tier(self) -> str:
        score = self.score()
        if score <= 25:
            return "Access"
        if score <= 50:
            return "Protected Member"
        if score <= 75:
            return "Enterprise"
        return "Strategic"


@dataclass(frozen=True)
class LaborEstimate:
    category: LaborCategory
    hours: Decimal
    internal_hour_cost: Decimal

    def __post_init__(self):
        object.__setattr__(self, "hours", D(self.hours))
        object.__setattr__(self, "internal_hour_cost", D(self.internal_hour_cost))
        if self.hours < 0 or self.internal_hour_cost < 0:
            raise ValueError("hours and internal_hour_cost cannot be negative")

    @property
    def commercial_value(self) -> Decimal:
        return money(self.category.commercial_rate * self.hours)

    @property
    def internal_cost(self) -> Decimal:
        return money(self.internal_hour_cost * self.hours)


@dataclass(frozen=True)
class QuoteInputs:
    labor: tuple[LaborEstimate, ...] = field(default_factory=tuple)
    direct_costs: Decimal = D("0")
    pass_through_costs: Decimal = D("0")
    complexity_allowance: Decimal = D("0")
    capacity_reservation: Decimal = D("0")
    contingency: Decimal = D("0")
    premium_multiplier: Decimal = D("1")

    def __post_init__(self):
        for name in (
            "direct_costs", "pass_through_costs", "complexity_allowance",
            "capacity_reservation", "contingency", "premium_multiplier",
        ):
            object.__setattr__(self, name, D(getattr(self, name)))
        if self.premium_multiplier < 1:
            raise ValueError("premium_multiplier cannot be below 1.0")


@dataclass(frozen=True)
class QuoteRecommendation:
    labor_value: Decimal
    internal_labor_cost: Decimal
    base_commercial_value: Decimal
    internal_expected_cost: Decimal
    floor_price: Decimal
    target_price: Decimal
    premium_price: Decimal
    expected_margin_at_target: Decimal


DEFAULT_TARGET_MARGINS = {
    RevenueClass.MEMBERSHIP: D("0.55"),
    RevenueClass.ASSESSMENT: D("0.50"),
    RevenueClass.INVESTIGATION: D("0.45"),
    RevenueClass.OPERATIONS: D("0.30"),
    RevenueClass.SPECIAL_PROJECT: D("0.50"),
}

DEFAULT_WARNING_FLOORS = {
    RevenueClass.MEMBERSHIP: D("0.45"),
    RevenueClass.ASSESSMENT: D("0.40"),
    RevenueClass.INVESTIGATION: D("0.35"),
    RevenueClass.OPERATIONS: D("0.25"),
    RevenueClass.SPECIAL_PROJECT: D("0.40"),
}


def contribution_margin(revenue, cost) -> Decimal:
    revenue = D(revenue)
    cost = D(cost)
    if revenue <= 0:
        return D("0")
    return ((revenue - cost) / revenue).quantize(D("0.0001"), rounding=ROUND_HALF_UP)


def required_price_for_margin(cost, margin) -> Decimal:
    cost = D(cost)
    margin = D(margin)
    if margin < 0 or margin >= 1:
        raise ValueError("margin must be >= 0 and < 1")
    return money(cost / (D("1") - margin))


def round_commercial_price(value, increment=D("500")) -> Decimal:
    value = D(value)
    increment = D(increment)
    if increment <= 0:
        return money(value)
    units = (value / increment).quantize(D("1"), rounding=ROUND_HALF_UP)
    rounded = units * increment
    if rounded < value:
        rounded += increment
    return money(rounded)


def recommend_quote(inputs: QuoteInputs, revenue_class: RevenueClass) -> QuoteRecommendation:
    labor_value = sum((x.commercial_value for x in inputs.labor), D("0"))
    labor_cost = sum((x.internal_cost for x in inputs.labor), D("0"))
    nonlabor_commercial = (
        inputs.direct_costs + inputs.pass_through_costs + inputs.complexity_allowance
        + inputs.capacity_reservation + inputs.contingency
    )
    base = money((labor_value + nonlabor_commercial) * inputs.premium_multiplier)
    internal_cost = money(labor_cost + inputs.direct_costs + inputs.pass_through_costs)
    warning_margin = DEFAULT_WARNING_FLOORS[revenue_class]
    target_margin = DEFAULT_TARGET_MARGINS[revenue_class]
    floor = round_commercial_price(max(base * D("0.90"), required_price_for_margin(internal_cost, warning_margin)))
    target = round_commercial_price(max(base, required_price_for_margin(internal_cost, target_margin)))
    premium = round_commercial_price(target * D("1.20"))
    return QuoteRecommendation(
        labor_value=money(labor_value),
        internal_labor_cost=money(labor_cost),
        base_commercial_value=base,
        internal_expected_cost=internal_cost,
        floor_price=floor,
        target_price=target,
        premium_price=premium,
        expected_margin_at_target=contribution_margin(target, internal_cost),
    )


def capacity_status(used_hours, included_hours) -> CapacityStatus:
    used = D(used_hours)
    included = D(included_hours)
    if included <= 0:
        return CapacityStatus.OVERAGE if used > 0 else CapacityStatus.NORMAL
    ratio = used / included
    if ratio > 1:
        return CapacityStatus.OVERAGE
    if ratio >= D("0.91"):
        return CapacityStatus.WARNING
    if ratio >= D("0.76"):
        return CapacityStatus.ADVISORY
    if ratio >= D("0.51"):
        return CapacityStatus.MONITOR
    return CapacityStatus.NORMAL


def projected_capacity_overage(used_hours, elapsed_fraction, included_hours) -> Decimal:
    used = D(used_hours)
    elapsed = D(elapsed_fraction)
    included = D(included_hours)
    if elapsed <= 0:
        return D("0")
    forecast = used / elapsed
    return max(D("0"), forecast - included).quantize(D("0.1"), rounding=ROUND_HALF_UP)


def scope_status(consumed, authorized) -> ScopeStatus:
    consumed = D(consumed)
    authorized = D(authorized)
    if authorized <= 0:
        return ScopeStatus.STOP if consumed > 0 else ScopeStatus.NORMAL
    ratio = consumed / authorized
    if ratio >= 1:
        return ScopeStatus.STOP
    if ratio >= D("0.90"):
        return ScopeStatus.ORANGE
    if ratio >= D("0.80"):
        return ScopeStatus.YELLOW
    return ScopeStatus.NORMAL


def assessment_escalation(dispositions: Iterable[InvestigationDisposition]) -> Optional[AssessmentLevel]:
    values = set(dispositions)
    if InvestigationDisposition.ESCALATION_RECOMMENDED in values or InvestigationDisposition.CONTRADICTORY in values:
        return AssessmentLevel.LEVEL_II
    if InvestigationDisposition.UNRESOLVED in values or InvestigationDisposition.PARTIALLY_RESOLVED in values:
        return AssessmentLevel.LEVEL_II
    return None


def minimum_assessment_price(level: AssessmentLevel) -> Decimal:
    return money(DEFAULT_ASSESSMENT_BASE_PRICES[level])


def estimate_at_completion(actual_cost_to_date, estimated_cost_to_complete) -> Decimal:
    return money(D(actual_cost_to_date) + D(estimated_cost_to_complete))


def projected_contribution(expected_revenue, estimate_at_completion_value) -> Decimal:
    return money(D(expected_revenue) - D(estimate_at_completion_value))


def renewal_recommendation(current_annual_price, annual_internal_cost, target_margin=D("0.55"), rounding_increment=D("6000")) -> Decimal:
    current = D(current_annual_price)
    minimum = required_price_for_margin(annual_internal_cost, target_margin)
    recommended = max(current, minimum)
    return round_commercial_price(recommended, increment=rounding_increment)


def cost_of_risk_reduction(current_risk, residual_risk, implementation_cost) -> Optional[Decimal]:
    reduction = D(current_risk) - D(residual_risk)
    if reduction <= 0:
        return None
    return money(D(implementation_cost) / reduction)
