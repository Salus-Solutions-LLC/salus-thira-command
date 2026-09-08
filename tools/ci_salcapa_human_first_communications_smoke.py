#!/usr/bin/env python3
"""Acceptance checks for Issues #204/#205 human-first and human-trust doctrine."""
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
RUNTIME = (ROOT / "salcapa_runtime.py").read_text(encoding="utf-8")
GUIDANCE = (ROOT / "static" / "salcapa-contextual-guidance.js").read_text(encoding="utf-8")
PLANNING_UI = (ROOT / "static" / "salops-plan-assembly.js").read_text(encoding="utf-8")
PLANNING_SERVER = (ROOT / "salops_plan_assembly.py").read_text(encoding="utf-8")


def require(value: str, source: str) -> None:
    if value not in source:
        raise SystemExit(f"Human-first communications acceptance is incomplete: {value}")


require('SALCAPA_RELEASE_VERSION = "3.84"', RUNTIME)

for value in (
    "People lead. Methods guide. Technology supports. Evidence proves.",
    "Salus people use disciplined methods and purpose-built technology",
    "Authorized people remain responsible for judgment, decisions, approval, release, and action.",
    "Technology is described plainly when it materially affects privacy, data handling, provenance, cost, contractual obligations, limitations, or decision authority.",
    "Prepared work is never presented as human-reviewed, approved, released, or validated",
    "Prepare Draft",
    "Recommended Next Step",
    "Ongoing Monitoring",
    "Review and Analyze",
    "Respect expertise. Preserve authority. Explain uncertainty. Protect information. Minimize burden. Avoid blame.",
    "Salus should make people feel more capable and informed—not watched, graded, replaced, or controlled.",
    "Here is what we found, what supports it, what remains uncertain, and what may deserve attention.",
    "Monitoring is not indiscriminate surveillance.",
    "A preliminary signal is not a final judgment about a person.",
    "SalTHIRA works with existing frameworks",
    "Human and manual operating capability remain important when digital tools are unavailable.",
    "Known or verified; Reported but unverified; Reasonably supported",
    "Demonstrated",
    "Partially Demonstrated",
    "Evidence Needed",
    "Improvement Underway",
    "Awaiting Validation",
    "window.salcapaHumanTrustGuidance",
):
    require(value, GUIDANCE)

for value in (
    "Salus emergency-plan research and assembly",
    "Our planning process brings together governed records, authorized research, professional judgment, and purpose-built technology",
    "Our planning process supports",
    "People retain authority",
    "Research technology allowance, including AI",
):
    require(value, PLANNING_UI)

for value in (
    '"capability": "Salus Emergency-Plan Research & Assembly"',
    '"communications_doctrine"',
    '"human_authority"',
    '"truthful_disclosure"',
    "Prepared content is not human-reviewed, approved, released, or validated",
):
    require(value, PLANNING_SERVER)

customer_sources = GUIDANCE + "\n" + PLANNING_UI
for forbidden in (
    "Autonomous emergency-plan",
    "AI-powered",
    "Automated analysis",
    "Synthetic data",
    "machine-generated",
    "algorithm recommends",
    "system detected",
    "automated monitoring",
    "automated reassessment",
    "Generate with AI",
    "Run AI Analysis",
):
    if forbidden.lower() in customer_sources.lower():
        raise SystemExit(f"Customer-facing language violates the human-first doctrine: {forbidden}")

print("SALCAPA_HUMAN_FIRST_COMMUNICATIONS_PASS")
