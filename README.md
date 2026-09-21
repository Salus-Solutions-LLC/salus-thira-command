# SalCAPA

SalCAPA is Salus Solutions' protective capability assessment and action methodology implemented through an integrated operating environment. It turns intelligence, risk findings, responsibilities, decisions, and operational results into coordinated, accountable protective action.

SalCAPA is not defined by a dashboard, portal, or app. Those are interfaces within the environment. SalCAPA is where a Protected Member's continuing protective program lives and where leadership can see risk, assign action, coordinate response, document decisions, verify completion, and strengthen readiness over time.

**Core promise:** We help Protected Members build and operate the capability to see risk early, decide with confidence, act in time, and prove that protective work was done.

## Product structure

- **SalCAPA** provides the governed, role-aware Common Operating Picture and shared operating environment for Protected Members and authorized Salus personnel.
- **SalINTEL** collects, qualifies, validates, analyzes, and monitors intelligence.
- **SalTHIRA** applies a Salus-specific risk-assessment methodology informed by recognized THIRA principles to identify threats and hazards, establish context and capability targets, assess capabilities, identify gaps, and support risk, priority, impact, and reassessment decisions. Salus does not claim ownership of the underlying public THIRA framework.
- **SalOPS** governs approved requests, implementation planning, authorization, assignment, operations, completion evidence, testing or verification, results, and feedback.

Shared platform controls provide tenant isolation, identity and authorization with persisted server-controlled Entra acceptance evidence, a governed See–Coordinate–Act Common Operating Picture, member decision requests, governed observation intake and triage, evidence lifecycle governance, reassessment triggers, professional judgment, Protected Member executive authority, accepted risk, immutable reporting, audit/version history, backup, governed recovery, a versioned SalOPS service catalog, readiness-gated engagement orchestration, governed expert qualification and assignment, tenant-scoped versioned industry profiles, governed estimates and actual expenses, and invoice-ready operational statements.

## Protective Readiness operating model

SalCAPA supports a coherent three-stage relationship:

1. **Diagnostic engagement** — a SalTHIRA-based baseline of protected missions, critical assets, threats, hazards, capability gaps, priorities, and a governed 90-day action plan.
2. **SalCAPA implementation** — configuration of intake, escalation, workflows, owners, reporting cadence, registers, Common Operating Picture views, member communications, and documentation standards.
3. **Ongoing Protective Readiness membership** — recurring SalINTEL monitoring and analysis, periodic reassessment, SalCAPA coordination, executive briefings, exercise and incident support, and SalOPS implementation assistance.

The authoritative protective-action lifecycle is signal or observation -> qualification -> assessment -> capability priority -> decision -> owner -> authorized action -> completion evidence -> testing or verification -> result -> reassessment.

## Development and release controls

GitHub is authoritative. Development occurs on governed development branches. Every release candidate must pass deterministic reconstruction, SQLite, PostgreSQL 16, production-container, dependency audit, Bandit, repository hygiene, and CodeQL gates. Validation pull requests are closed without merge. Frozen release branches are immutable.

Reconstruct and verify this candidate with:

```bash
python tools/reconstruct_v343_source.py
python tools/verify_v343_source.py
```

Run the complete SalCAPA governed-workflow smoke with:

```bash
python tools/ci_v116_smoke.py
python tools/ci_salcapa_smoke.py
python tools/ci_salcapa_v21_smoke.py
python tools/ci_salcapa_v22_smoke.py
python tools/ci_salcapa_v23_smoke.py
python tools/ci_salcapa_v24_smoke.py
python tools/ci_salcapa_v25_smoke.py
python tools/ci_salcapa_v26_smoke.py
python tools/ci_salcapa_v27_smoke.py
python tools/ci_salcapa_v28_smoke.py
python tools/ci_salcapa_v29_smoke.py
python tools/ci_salcapa_operating_model_acceptance.py
python tools/ci_salcapa_v33_identity_smoke.py
```

Production is prepared for Microsoft Azure with passwordless GitHub deployment identity and passwordless Microsoft Entra runtime authentication through the Container App managed identity. No Azure deployment is automatic; billable infrastructure and production activation require explicit approval.
## Protection Advisor report artifact handoff

The authenticated Salus review route can prepare the approved branded DOCX report only after report handling is approved. The artifact remains preliminary and review-gated. Configure these deployment values before enabling Microsoft 365 storage:

- `SALUS_ADVISOR_DOCX_TEMPLATE_PATH`: absolute path to the approved Protection Advisor DOCX template;
- `SALUS_ADVISOR_REPORT_OUTPUT_DIR`: controlled writable staging directory for generated DOCX artifacts;
- `SALUS_M365_ADVISOR_REPORT_FOLDER_ITEM_ID`: separate Microsoft 365 folder item ID for Protection Advisor reports;
- existing `SALUS_OIDC_MANAGED_IDENTITY_CLIENT_ID`, `SALUS_M365_REPORT_DRIVE_ID`, and report size/retry settings.

The Advisor folder must remain separate from Protected Member report storage. The upload path does not release a report, create a contract, create an invoice, or grant Protected Member access. CUI or other controlled handling remains subject to the approved authority and Salus human review.

