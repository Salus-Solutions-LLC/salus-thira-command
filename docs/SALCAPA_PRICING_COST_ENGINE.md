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

`pricing_engine.py` implements employee/contractor cost, complexity/tier recommendation, membership capacity, assessment scope ceilings and escalation, quote recommendations, contribution margin, forecasts, renewal pricing and cost-of-risk-reduction.

`tests/test_pricing_engine.py` defines the initial unit acceptance suite.

## Planning, Training & Exercise (P/T/E) integration

Planning, training and exercise are first-class SalCAPA service domains, not disconnected consulting tasks. The governed lifecycle is:

**SalTHIRA gap / capability requirement -> plan -> train -> exercise -> evaluate -> corrective action -> validation -> capability reassessment.**

`pte_engine.py` implements the P/T/E domain and `tests/test_pte_engine.py` defines its acceptance suite.

Supported plan classes include strategic, emergency operations, continuity, crisis communications, security, protective operations, incident action/response, recovery, functional annexes and SOPs/procedures. Supported training classes include awareness/orientation, role-based, skills/task, leadership/decision, train-the-trainer, refresher/sustainment and remedial/corrective training. Supported exercise classes include seminar, workshop, tabletop, game, drill, functional and full-scale.

Training completion alone does not prove capability. Exercise conduct alone does not improve a THIRA score. Adverse observations generate corrective-action treatment and capability credit remains dependent on current, governed validation evidence.

### Readiness-cycle gate

Capability readiness distinguishes:

1. current approved plan/procedure;
2. required training completed;
3. exercise or other validation event completed;
4. evaluation completed;
5. corrective actions closed or otherwise formally dispositioned; and
6. current valid validation evidence.

Only when required dimensions are satisfied may P/T/E indicate readiness for governed capability-credit consideration.

### Initial P/T/E pricing minimums

Initial minimum starting points include SOP/procedure $3,500; plan annex $5,000; emergency operations plan $12,500; continuity plan $12,500; crisis communications plan $10,000; security plan $12,500; awareness training $2,500; role-based training $5,000; skills/leadership/train-the-trainer $7,500; seminar $3,500; workshop $5,000; tabletop $7,500; drill $7,500; functional exercise $15,000; full-scale exercise $30,000. Complexity and required resources can raise the recommendation.

## Protected Member capability posture matrix

Every Protected Member receives an evidence-based current capability posture across the five mission areas:

- Prevention
- Protection
- Response
- Recovery
- Mitigation

`capability_posture.py` implements this posture model and `tests/test_capability_posture.py` defines its acceptance suite.

### Purpose

The posture matrix must answer: **What can this Protected Member actually do now, with current evidence, under the conditions that matter?** It must not confuse possession of a plan, attendance at training, procurement of equipment or completion of an exercise with demonstrated capability.

### Capability dimensions

Each capability can consider:

- current approved plan/procedure;
- required training completion;
- exercise or real-event testing;
- completed evaluation;
- corrective-action closure;
- current governed validation evidence;
- demonstrated performance against the required standard;
- current material gap severity; and
- consequence/mission importance.

### Fail-closed scoring

The model uses progressive ceilings so missing readiness dimensions limit capability credit. A plan by itself cannot produce a high capability score. Missing training, no exercise/real-world validation, incomplete evaluation, unresolved corrective actions, stale/unverified evidence or failure to meet a performance target each cap the score. Material SalTHIRA gaps further reduce demonstrated capability.

This intentionally prevents a Protected Member from appearing capable merely because documentation exists.

### Capability bands

Initial posture bands are:

- Unknown: insufficient data
- Critical: 0-24.9
- Weak: 25-39.9
- Developing: 40-59.9
- Capable: 60-74.9
- Strong: 75-89.9
- Demonstrated: 90-100

Bands are configurable in later persistence; historical posture snapshots must retain the thresholds in effect when calculated.

### Confidence

Every capability and mission-area posture also receives confidence of Low, Moderate or High. High confidence requires current governed evidence plus exercise/real-event testing and completed evaluation. Stale evidence cannot support High confidence.

### Five-area aggregation

Capabilities are consequence-weighted inside each mission area. Populated mission areas are then equally weighted in the overall Protected Member posture so one area with many capabilities cannot hide weakness in another mission area. Missing mission-area data displays as Unknown, not as falsely good or falsely bad capability.

The dashboard must always show:

- overall capability score and band;
- confidence;
- five mission-area gauges;
- strongest and weakest mission areas;
- material gap count;
- stale/insufficient-evidence indicators;
- capability trends over time;
- next required readiness action; and
- recommended P/T/E or other Salus action needed to improve position.

### No automatic THIRA override

The capability posture is decision support and may feed governed capability review. It does not autonomously overwrite professional risk judgments or the governed THIRA risk formula.

## Persistence model (next integration layer)

Database integration will introduce effective-dated, tenant-aware entities for rate cards, labor categories, confidential cost profiles, membership plans, member contract pricing, capacity accounts, service catalog, assessment levels, modifiers, quotes and quote items, estimates, budgets, actual labor/expenses, forecasts, approvals, scope authorizations, change orders, retainers and immutable pricing audit events.

P/T/E persistence will introduce work packages, capability links, objectives, participants/audiences, plan/training/exercise events, observations, evaluations, corrective actions, after-action/improvement plans, validation events and evidence links.

Capability-posture persistence will add mission-area definitions, capability posture snapshots, scoring-rule versions, evidence/confidence state, material-gap references, trend history and Protected Member overall posture snapshots. Every posture snapshot must be tenant-isolated, timestamped and reproducible from the governed source records used at calculation time.

Cost-profile detail must be restricted more tightly than ordinary project economics. Project managers may receive blended cost/margin data without access to salary-derived inputs.

## THIRA integration

The pricing, P/T/E and capability-posture domains consume, not replace, governed THIRA outputs. Findings/gaps/improvements map to recommended service, professional mix, effort range, price range, authorization state and cost-of-risk-reduction analysis. P/T/E results feed validated evidence and corrective-action outcomes back into capability reassessment. Capability posture then presents the current demonstrated position across Prevention, Protection, Response, Recovery and Mitigation.

## Release sequence

1. Pricing foundation and pure-domain acceptance tests.
2. Planning, Training & Exercise domain and acceptance tests.
3. Protected Member five-area capability posture model and acceptance tests.
4. Tenant-aware persistence and immutable audit history, including P/T/E and posture snapshots.
5. Estimate/quote API and approval workflow.
6. Engagement budget, actuals, EAC and scope ceilings.
7. Membership capacity, overage and renewal economics.
8. SalTHIRA finding/improvement integration, P/T/E work-package generation and change-order recommendations.
9. SalOPS operational pricing and mobilization rules.
10. P/T/E scheduling, evaluation, corrective-action and evidence-lifecycle UI.
11. Protected Member posture dashboard, trend analysis and recommended-next-action UI.
12. Commercial analytics and estimating feedback loop.
