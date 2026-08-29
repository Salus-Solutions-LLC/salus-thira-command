# Salus THIRA Command Prototype v0.4

A local, database-backed working prototype of **Salus THIRA Command**. This build operationalizes the Salus THIRA assessment and decision workflow while preserving traceability, governance, revision history, and evidence integrity.

## v0.4 capabilities

- Command Center portfolio dashboard
- **Active assessment selector** for multi-client / multi-assessment operation; analytical and operational views are scoped to the selected assessment
- New records automatically inherit the active assessment context rather than requiring repeated assessment selection
- Assessment workspaces with locked scope and formal version numbers
- Threat / Hazard Register
- Scenario Builder with multidimensional consequences
- Transparent inherent, current, and estimated residual risk analytics
- Capability targets and demonstrated-performance gaps
- Controlled Evidence Register
- **Evidence file attachments** with 25 MB prototype limit, SHA-256 integrity hash, uploader, timestamp, and audited download
- Gap Register
- Improvement Portfolio
- Transparent prioritization scoring across consequence reduction, mission benefit, feasibility, sustainability, compliance, staffing, cost, and time
- Immutable executive decision records
- Implementation Tracker
- Event-driven reassessment triggers, including automatic validation triggers when an improvement is completed
- **Controlled workflow transitions** through the defined THIRA lifecycle
- **Formal scope-change requests and executive approval/rejection**
- Approved scope/mission changes automatically increment the assessment version instead of overwriting the original
- **Automatic revision snapshots** for material assessment, threat, scenario, capability, evidence, gap, improvement, and reassessment-trigger changes
- Governance view showing workflow history, scope-change history, and revision history
- Audit log with actor identity supplied by the prototype role selector
- Executive report view with print / Save PDF support through the browser
- **Portable JSON assessment package export** containing the assessment, risk analytics, priorities, decisions, reassessment triggers, scope/workflow history, and revision index
- Prototype role permissions for System Administrator, Assessment Director, Lead Assessor, SME Assessor, Client Executive, Program Owner, Contributor, and Auditor

## Risk model

The prototype keeps the calculation transparent rather than presenting an unexplained score.

1. Scenario consequences are combined using configurable assessment consequence weights.
2. Inherent risk is modeled from likelihood × vulnerability/exposure × consequence and normalized to 0–100.
3. Demonstrated capability effectiveness is calculated from current performance versus the required standard.
4. Current risk credits demonstrated capability effectiveness while maintaining a floor so capability does not mathematically erase the underlying threat.
5. Estimated residual risk additionally reflects approved improvements.
6. The underlying likelihood, vulnerability/exposure, consequence, capability effectiveness, confidence, and trend remain visible.

These calculations are decision-support estimates and do not replace documented professional judgment.

## Prioritization model

The default v0.4 improvement priority score is visible in the UI:

- 22% consequence reduction
- 18% mission benefit
- 12% feasibility
- 10% sustainability
- 10% compliance impact
- 8% staffing impact
- 10% cost efficiency
- 10% time to benefit

Every underlying factor remains visible and editable.

## Run on Windows

1. Install Python 3.11 or later.
2. Extract the ZIP to a local folder.
3. Open Command Prompt or PowerShell in that folder.
4. Install requirements:

   `pip install -r requirements.txt`

5. Run:

   `run_windows.bat`

6. Open `http://127.0.0.1:8000` in a browser.

## Run on macOS / Linux

1. Install Python 3.11 or later.
2. From the extracted folder run:

   `pip install -r requirements.txt`

3. Then run:

   `./run_mac_linux.sh`

4. Open `http://127.0.0.1:8000`.

## Data and files

- Application database: `thira.db`
- Evidence attachments: `attachments/` (created automatically)
- Front end: `static/`
- FastAPI application: `app.py`

The GitHub repository intentionally excludes `thira.db`, attachments, uploads, logs, secrets, and other runtime/client data. On first run, the application creates a local database and seeds fictional demonstration records. The v0.4 migration preserves existing local v0.2 records and establishes baseline revision snapshots for existing versioned records.

## Security / production status

This is a **functional local prototype**, not a hardened production deployment. The role selector is intentionally a prototype mechanism: the server enforces the selected role through request headers, but there is not yet an authenticated identity provider behind those headers.

Before handling real sensitive client data, production work still needs authenticated SSO / identity, server-issued authorization claims, tenant isolation, record-level sensitivity enforcement, encrypted managed storage, secrets management, database hardening, backup/restore, malware scanning for uploaded documents, retention/legal-hold controls, production observability, and security review.

## v0.4 regression validation

The build was tested on a disposable database copy for:

- evidence upload, SHA-256 registration, and byte-for-byte download
- Auditor write denial
- rejection of direct assessment-status overwrite
- controlled workflow transition
- scope-change request and executive approval
- assessment version increment after approved scope change
- revision-history creation
- portable assessment-package export

The test copy was discarded; the working demonstration database was not modified by regression testing.
