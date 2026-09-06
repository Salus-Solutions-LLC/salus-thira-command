from decimal import Decimal

from pricing_engine import (
    AssessmentLevel, CapacityStatus, ComplexityFactors, ContractorCostProfile,
    CostProfile, DEFAULT_LABOR_CATEGORIES, InvestigationDisposition, LaborEstimate,
    QuoteInputs, RevenueClass, ScopeStatus, assessment_escalation, capacity_status,
    contribution_margin, cost_of_risk_reduction, estimate_at_completion,
    minimum_assessment_price, projected_capacity_overage, projected_contribution,
    recommend_quote, renewal_recommendation, scope_status,
)


def test_employee_loaded_cost_uses_productive_hours_not_2080():
    p = CostProfile(130000, 40000, 15000, 35000, 1300)
    assert p.annual_loaded_cost == Decimal("220000.00")
    assert p.productive_hour_cost == Decimal("169.23")


def test_contractor_true_cost_includes_burden_and_support():
    p = ContractorCostProfile(100, burden_percent=8, supervision_per_hour=6, technology_equipment_per_hour=4)
    assert p.productive_hour_cost == Decimal("118.00")


def test_complexity_recommends_tier_from_weighted_score():
    low = ComplexityFactors(facilities=20, principals=10, geography=10, threat_risk=20,
                            intelligence_requirement=20, support_intensity=20,
                            response_requirement=10, regulatory_complexity=10)
    high = ComplexityFactors(facilities=90, principals=80, geography=90, threat_risk=90,
                             intelligence_requirement=90, support_intensity=90,
                             response_requirement=90, regulatory_complexity=80)
    assert low.recommended_tier() == "Access"
    assert high.recommended_tier() == "Strategic"


def test_capacity_thresholds_and_forecast():
    assert capacity_status(2, 4) == CapacityStatus.NORMAL
    assert capacity_status(2.1, 4) == CapacityStatus.MONITOR
    assert capacity_status(3.1, 4) == CapacityStatus.ADVISORY
    assert capacity_status(3.7, 4) == CapacityStatus.WARNING
    assert capacity_status(4.1, 4) == CapacityStatus.OVERAGE
    assert projected_capacity_overage(3, Decimal("0.5"), 4) == Decimal("2.0")


def test_scope_ceiling_stops_at_authorization():
    assert scope_status(79, 100) == ScopeStatus.NORMAL
    assert scope_status(80, 100) == ScopeStatus.YELLOW
    assert scope_status(90, 100) == ScopeStatus.ORANGE
    assert scope_status(100, 100) == ScopeStatus.STOP


def test_assessment_escalation_stops_unbounded_investigation():
    assert assessment_escalation([InvestigationDisposition.RESOLVED]) is None
    assert assessment_escalation([InvestigationDisposition.UNRESOLVED]) == AssessmentLevel.LEVEL_II
    assert assessment_escalation([InvestigationDisposition.CONTRADICTORY]) == AssessmentLevel.LEVEL_II


def test_assessment_minimums():
    assert minimum_assessment_price(AssessmentLevel.LEVEL_I) == Decimal("7500.00")
    assert minimum_assessment_price(AssessmentLevel.LEVEL_II) == Decimal("17500.00")
    assert minimum_assessment_price(AssessmentLevel.LEVEL_III) == Decimal("35000.00")
    assert minimum_assessment_price(AssessmentLevel.CRITICAL_INFRASTRUCTURE) == Decimal("75000.00")


def test_quote_has_separate_cost_value_and_price():
    senior = LaborEstimate(DEFAULT_LABOR_CATEGORIES["Senior Consultant"], 40, 169.23)
    analyst = LaborEstimate(DEFAULT_LABOR_CATEGORIES["Analyst"], 25, 75)
    q = recommend_quote(
        QuoteInputs(
            labor=(senior, analyst), direct_costs=2500, pass_through_costs=750,
            complexity_allowance=2000, capacity_reservation=0, contingency=0,
        ),
        RevenueClass.ASSESSMENT,
    )
    assert q.labor_value == Decimal("14750.00")
    assert q.internal_expected_cost == Decimal("11894.20")
    assert q.floor_price <= q.target_price < q.premium_price
    assert q.expected_margin_at_target >= Decimal("0.50")


def test_quote_margin_floor_can_raise_price_above_commercial_value():
    labor = LaborEstimate(DEFAULT_LABOR_CATEGORIES["Analyst"], 10, 140)
    q = recommend_quote(QuoteInputs(labor=(labor,)), RevenueClass.SPECIAL_PROJECT)
    assert q.target_price >= Decimal("2800")
    assert contribution_margin(q.target_price, q.internal_expected_cost) >= Decimal("0.50")


def test_forecast_and_contribution():
    assert estimate_at_completion(12100, 6300) == Decimal("18400.00")
    assert projected_contribution(35000, 18400) == Decimal("16600.00")


def test_renewal_never_recommends_below_current_price():
    assert renewal_recommendation(72000, 19500) == Decimal("72000.00")
    assert renewal_recommendation(72000, 46200) == Decimal("108000.00")


def test_cost_of_risk_reduction():
    assert cost_of_risk_reduction(82, 46, 42000) == Decimal("1166.67")
    assert cost_of_risk_reduction(50, 50, 10000) is None
