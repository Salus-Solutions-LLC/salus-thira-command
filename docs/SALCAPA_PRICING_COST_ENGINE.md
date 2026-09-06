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

## Planning, Training & Exercise (P/T/E) integration

Planning, training and exercise are first-class SalCAPA service domains, not disconnected consulting tasks. The governed lifecycle is:

**SalTHIRA gap / capability requirement -> plan -> train -> exercise -> evaluate -> corrective action -> validation -> capability reassessment.**

`pte_engine.py` implements the initial P/T/E domain and `tests/test_pte_engine.py` defines its acceptance suite.

### Planning

Supported initial plan classes include strategic plans, emergency operations plans, continuity plans, crisis communications plans, security plans, protective operations plans, incident action/response plans, recovery plans, functional annexes and SOPs/procedures.

A planning work package must identify the linked assessment/capability/gap/improvement where applicable, the authorized budget/hours, objectives and controlled lifecycle state.

### Training

Supported initial training classes include awareness/orientation, role-based training, skills/task training, leadership/decision training, train-the-trainer, refresher/sustainment and remedial/corrective training.

Training completion alone is not assumed to prove capability. Training records may become evidence, but capability credit remains governed by evidence validity and, when appropriate, demonstrated performance.

### Exercises

Supported initial exercise classes are seminar, workshop, tabletop exercise, game, drill, functional exercise and full-scale exercise.

Exercises must be linked to defined objectives and, where available, SalTHIRA capabilities and performance targets. Exercise observations can produce corrective actions. Adverse observations such as Failed, Not Demonstrated, Partial, Unsatisfactory or Needs Improvement trigger corrective-action treatment rather than automatic closure.

Existing THIRA evidence handling already recognizes exercise results; the P/T/E subsystem formalizes the design, conduct, evaluation and corrective-action lifecycle around that evidence.

### Readiness-cycle gate

Capability readiness should distinguish the following dimensions:

1. current approved plan/procedure;
2. required training completed;
3. exercise or other validation event completed;
4. evaluation completed;
5. corrective actions closed or otherwise formally dispositioned; and
6. current valid validation evidence.

Only when the required dimensions are satisfied may P/T/E indicate that a capability is ready for governed capability-credit consideration. P/T/E does not independently change THIRA risk scores.

### Initial P/T/E pricing minimums

Pricing remains configuration-driven and uses the core Pricing & Cost Engine for labor, internal cost, margin floor, target and premium pricing. Initial service minimums are:

- SOP/procedure development: $3,500
- plan annex: $5,000
- emergency operations plan: $12,500
- continuity plan: $12,500
- crisis communications plan: $10,000
- security plan: $12,500
- awareness/orientation training: $2,500
- role-based training: $5,000
- skills/task training: $7,500
- leadership/decision training: $7,500
- train-the-trainer: $7,500
- seminar: $3,500
- workshop: $5,000
- tabletop exercise: $7,500
- drill: $7,500
- functional exercise: $15,000
- full-scale exercise: $30,000

These are minimum starting points, not fixed prices. Complexity, participant count, sites/jurisdictions, scenario design, controllers/evaluators, simulation, travel, logistics, documentation, after-action/improvement planning and required SMEs can raise the recommended price.

### Corrective-action lifecycle

Exercise/training deficiencies create corrective actions with status values Open, In Progress, Pending Validation, Validated, Closed or Accepted Risk. P/T/E cycles cannot be represented as fully closed while required evaluation is incomplete or blocking corrective actions remain unresolved.

Corrective-action validation should create evidence usable by the existing governed evidence lifecycle; stale evidence must not retain permanent readiness credit.

## Persistence model (next integration layer)

The database integration will introduce effective-dated, tenant-aware entities for rate cards, labor categories, confidential cost profiles, membership plans, member contract pricing, capacity accounts, service catalog, assessment levels, modifiers, quotes and quote items, estimates, budgets, actual labor/expenses, forecasts, approvals, scope authorizations, change orders, retainers and immutable pricing audit events.

P/T/E persistence will additionally introduce work packages, capability links, objectives, participants/audiences, plan/training/exercise events, observations, evaluations, corrective actions, after-action/improvement plans, validation events and evidence links.

Cost-profile detail must be restricted more tightly than ordinary project economics. Project managers may receive blended cost/margin data without access to salary-derived inputs.

## THIRA integration

The pricing and P/T/E domains must consume, not replace, governed THIRA outputs. Integration will map findings/gaps/improvements to recommended service, professional mix, effort range, price range, authorization state and cost-of-risk-reduction analysis. P/T/E results then feed validated evidence and corrective-action outcomes back into capability reassessment.

## Release sequence

1. Pricing foundation and pure-domain acceptance tests.
2. Planning, Training & Exercise domain and acceptance tests.
3. Tenant-aware persistence and immutable audit history, including P/T/E records.
4. Estimate/quote API and approval workflow.
5. Engagement budget, actuals, EAC and scope ceilings.
6. Membership capacity, overage and renewal economics.
7. SalTHIRA finding/improvement integration, P/T/E work-package generation and change-order recommendations.
8. SalOPS operational pricing and mobilization rules.
9. P/T/E scheduling, evaluation, corrective-action and evidence-lifecycle UI.
10. Commercial analytics and estimating feedback loop.
