# Current Handoff

## 16 November 2026 10:50 CST — SAL-D140 automatic OSINT-list merge candidate

### Objective

Make routine governed OSINT Sources or Library and Global Endpoint Register maintenance merge automatically after all required repository checks pass, without asking Marc for pull-request or exact-head approval.

### Authority inspected

- `SALUS_PROGRAM_CHARTER.md`
- `SALUS_DECISION_REGISTER.md`
- `CURRENT_HANDOFF.md`
- `APPROVED_ARTIFACTS.md`
- `SALUS_CHAT_STARTUP_PROTOCOL.md`

The current authoritative SAL-D123 rule still requires Marc's exact-head approval and prohibits the weekly automation from merging its own work. Marc directed on 16 November 2026 that automatic list merge become a Charter requirement and that routine approval requests stop.

### Current authoritative and deployed state

- SAL-D123 and SAL-D124 remain authoritative until a superseding governed amendment merges.
- The current authoritative OSINT endpoint tables contain 113 unique addresses.
- Weekly candidate PR #1275 remains open at exact head `59facce9d14a3112f97a62862af9f9e86ab09b26`; all six repository checks passed. It proposes 13 new addresses and one canonical-address change. It is not merged or deployed.
- No connector, credential, paid access, collection service, production system, source qualification, Protected Member record, report or release was changed by this work.

### Candidate work

PR #1278 records SAL-D140 and aligns the Charter, Decision Register, startup protocol and generated authority-coverage register. The proposed standing authorization is narrowly limited to routine OSINT list-maintenance files and stops on failed or missing checks, conflicts, base or scope drift, substantive non-allowlisted changes, or cost, access, rights, privacy, security or legal decisions. Entries remain `Unvetted Candidate` after merge until separately qualified.

### Unfinished or uncertain

- PR #1278 repository checks and mergeability must be verified.
- The active `weekly-salus-osint-source-expansion` prompt must be updated only after SAL-D140 becomes authoritative.
- Because SAL-D140 is not yet authoritative, this governance amendment itself remains subject to the pre-existing exact-head promotion rule.
- PR #1275 remains governed by the current SAL-D123 rule unless SAL-D140 becomes authoritative first.

### Exact next action and authorization boundary

Run and reconcile all required checks for PR #1278. If they pass, report its exact final head for the one-time promotion required under the governance currently in force. After SAL-D140 becomes authoritative, update the weekly automation and permit future allowlisted OSINT list-maintenance pull requests to merge automatically after successful checks without routine approval requests.
