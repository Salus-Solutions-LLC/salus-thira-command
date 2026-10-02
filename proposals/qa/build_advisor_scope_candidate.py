"""Fictional, local-only layout fixture for Protection Advisor PDF review."""

from datetime import datetime, timezone
from pathlib import Path

from protection_advisor_docx_report import render_protection_advisor_pdf, render_scope_receipt_pdf
from protection_advisor_report_contract import build_report_context
from salus_package_path import draft_level_1_scope_receipt, suggest_provisional_level_1_path

profile = {
    "decision_units": "One", "separate_findings": "No", "group_priorities": "No",
    "covered_operation": "One fictional child-care site",
    "facility_locations": "Example County, Texas", "decision_authority": "Director",
}
path = suggest_provisional_level_1_path(profile)
package = {
    "primary_service": {
        "title": "Level 1 SalCAPA Package", "level": 1, "level_name": "Initial Pass",
        "summary": "Four connected reports for the agreed site.",
        "why": "A qualified Level 1 package is the first paid step.",
    },
    "provisional_path": path,
    "scope_receipt": {**draft_level_1_scope_receipt(profile, path), "receipt_id": "SPA-RECEIPT-FICTIONAL"},
    "sequence": ["Level 1 SalCAPA package — four reports", "Level 2 after Level 1", "Level 3 after Level 2"],
    "services": [], "later_phase_services": [],
    "rationale": "Salus confirms the scope and evidence before making a formal recommendation.",
}
result = {
    "recommendation": "Discuss a bounded Level 1 scope",
    "strength_count": 3, "attention_count": 2, "information_gap_count": 2,
    "core_capabilities_considered": 32,
    "mission_area_scores": {area: None for area in ("Prevention", "Protection", "Mitigation", "Response", "Recovery")},
    "priority_capabilities": [], "attention_topics": ["Clarify emergency communications."],
    "information_gaps": ["Plan and organization chart not yet supplied."],
}
context = build_report_context(
    client_code_name="FICTIONAL MEMBER", project_code_name="ACCESS SCOPE QA",
    organization_type="Business", government_or_public_service_role="Not provided",
    assessment_authority_or_sponsor="Director", information_handling="Confidential",
    report_reference="SPA-REPORT-QA-ONLY", generated_at=datetime(2026, 9, 29, 12, 0, tzinfo=timezone.utc),
)
output = Path(__file__).with_name("advisor_scope_candidate.pdf")
render_protection_advisor_pdf(output_path=output, context=context, result=result, package=package)
print(output)
receipt_output = Path(__file__).with_name("advisor_scope_receipt_candidate.pdf")
render_scope_receipt_pdf(output_path=receipt_output, context=context,
                         receipt=package["scope_receipt"])
print(receipt_output)
