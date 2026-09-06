# SalCAPA Pricing & Cost Engine v1.0 Baseline

Status: implementation baseline on `development/salcapa-pricing-engine`.

## Purpose

Connect risk, priority, recommendation, scope, price, authorization, execution,
cost, outcome and residual risk while preserving human commercial authority.

## Core controls

- Internal cost, commercial/list value and contracted price remain separate.
- Currency calculations use decimal arithmetic; monetary values round to cents.
- Rate cards are effective-dated configuration in the persistence phase; historical economics must not be silently rewritten.
- Membership is complexity/capacity based rather than seat based.
- Included professional capacity is finite and monitored at 51%, 76%, 91% and >100% thresholds.
- Assessment work is bounded by Level I, II, III and Critical Infrastructure / Complex Enterprise authorization.
- Unresolved, partially resolved or contradictory findings recommend escalation rather than silently expanding investigation.
- Scope consumption warns at 80%, escalates at 90% and stops at 100% unless an authorized emergency override is recorded.
- Quotes preserve internal cost, commercial value, floor, target and premium prices.
- Margin floors are guardrails, not autonomous commercial decisions.
- AI may calculate, forecast and recommend; it may not change a contract price, approve a discount or expand scope.

## Initial commercial configuration

Membership defaults: Access $2,500/month; Protected Member $6,000/month; Enterprise $15,000/month; Strategic / Critical Infrastructure starting $30,000/month.

Assessment minimums: Level I $7,500; Level II $17,500; Level III $35,000; Critical Infrastructure / Complex Enterprise $75,000.

Default commercial labor rates range from $125/hour for research/investigative support through $500/hour for specialized national-level advisory work. Configuration is represented in the domain module and will become effective-dated persisted rate cards.

## Margin guardrails

- Membership: 55% target, 45% warning floor.
- Assessment: 50% target, 40% warning floor.
- Investigation: 45% target, 35% warning floor.
- Operations: 30% target, 25% warning floor.
- Special project: 50% target, 40% warning floor.

## Domain implementation

`pricing_engine.py` implements:

- employee fully loaded productive-hour cost;
- contractor true hourly cost;
- weighted Protected Member complexity/tier recommendation;
- membership capacity status and projected overage;
- scope-ceiling status;
- assessment escalation;
- assessment minimum pricing;
- labor estimates;
- floor/target/premium quote recommendation;
- contribution margin and margin-required price;
- estimate at completion and projected contribution;
- renewal price recommendation; and
- cost of risk reduction.

`tests/test_pricing_engine.py` defines the initial unit acceptance suite.

## Persistence model (next integration layer)

The database integration will introduce effective-dated, tenant-aware entities for rate cards, labor categories, confidential cost profiles, membership plans, member contract pricing, capacity accounts, service catalog, assessment levels, modifiers, quotes and quote items, estimates, budgets, actual labor/expenses, forecasts, approvals, scope authorizations, change orders, retainers and immutable pricing audit events.

Cost-profile detail must be restricted more tightly than ordinary project economics. Project managers may receive blended cost/margin data without access to salary-derived inputs.

## THIRA integration

The pricing domain must consume, not replace, governed THIRA outputs. A later integration layer will map findings/gaps/improvements to recommended service, professional mix, effort range, price range, authorization state and cost-of-risk-reduction analysis.

## Release sequence

1. Pricing foundation and pure-domain acceptance tests.
2. Tenant-aware persistence and immutable audit history.
3. Estimate/quote API and approval workflow.
4. Engagement budget, actuals, EAC and scope ceilings.
5. Membership capacity, overage and renewal economics.
6. SalTHIRA finding/improvement integration and change-order recommendations.
7. SalOPS operational pricing and mobilization rules.
8. Commercial analytics and estimating feedback loop.
