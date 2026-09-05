# SalCAPA v3.11 — Deterministic Azure readiness outcome

## Outcome

Azure connection acceptance now exposes provider readiness through mutually exclusive registered/missing steps. Scheduled governance can read the step state reliably without relying on continue-on-error semantics, failing the overall workflow, or disclosing provider-state details.

## Controls

- A private calculation emits only a boolean job-step output.
- Exactly one visible outcome step runs: required providers registered or required providers missing.
- Missing provider names and Azure resource metadata are not emitted by the readiness outcome.
- Foundation activation remains independently fail-closed and still reports exact missing prerequisites when a governed activation is attempted.
- No provider registration, resource deployment, credential creation, DNS change, or public cutover occurs in this validation path.

## Defect correction

GitHub Actions normalizes a continue-on-error step to success in the jobs API, making the v3.10 signal ambiguous. This release removes that ambiguity.
