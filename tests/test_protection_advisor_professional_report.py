from datetime import datetime, timezone
from pathlib import Path

from docx import Document
from pypdf import PdfReader

from protection_advisor_docx_report import _professional_body, render_protection_advisor_pdf
from protection_advisor_report_contract import build_report_context


RESULT = {
    "recommendation": "Comprehensive review recommended",
    "strength_count": 6,
    "attention_count": 16,
    "information_gap_count": 5,
    "core_capabilities_considered": 32,
    "mission_area_scores": {"Prevention": 57, "Protection": 62, "Mitigation": 44, "Response": 52, "Recovery": 41},
    "priority_capabilities": [{"capability": "Operational Coordination", "need_score": 64, "mission_areas": ["Prevention", "Response"], "information_gap": False}],
    "attention_topics": ["Are decision authority and succession documented and understood?"],
    "information_gaps": ["Recovery targets require validation."],
}

PACKAGE = {
    "primary_service": {"title": "Emergency Planning and Crisis Communications", "level": 3, "level_name": "Deep Dive", "summary": "Establish an integrated operating framework.", "why": "The reported conditions span multiple mission areas."},
    "sequence": ["Emergency Planning and Crisis Communications", "Continuity and Recovery"],
    "later_phase_services": [],
    "services": [{"title": "Emergency Planning and Crisis Communications", "level": 3, "why": "Connected gaps require comprehensive validation."}],
    "rationale": "The proposed sequence addresses connected capability needs.",
}


def _context():
    return build_report_context(
        client_code_name="Test Member",
        project_code_name="Test Project",
        organization_type="Private",
        government_or_public_service_role="Not provided",
        assessment_authority_or_sponsor="Not provided",
        information_handling="Confidential",
        report_reference="SPA-REPORT-TEST",
        generated_at=datetime(2026, 9, 22, 14, 28, tzinfo=timezone.utc),
    )


def test_professional_docx_body_contains_approved_sections_without_json(tmp_path: Path):
    document = Document()
    _professional_body(document, _context().as_template_fields(), RESULT, PACKAGE)
    path = tmp_path / "report.docx"
    document.save(path)
    text = "\n".join(paragraph.text for paragraph in Document(path).paragraphs)
    for heading in (
        "Executive Summary", "Mission Area Profile", "Priority Capability Findings",
        "Information Gaps", "Recommended Protection Package",
        "Appendix A Assessment Method", "Appendix B Preliminary Service Rationale",
    ):
        assert heading in text
    assert '"strength_count"' not in text
    assert '"primary_service"' not in text


def test_participant_pdf_uses_professional_report_model(tmp_path: Path):
    path = render_protection_advisor_pdf(
        output_path=tmp_path / "report.pdf",
        context=_context(),
        result=RESULT,
        package=PACKAGE,
    )
    reader = PdfReader(path)
    assert len(reader.pages) >= 8
    text = "\n".join(page.extract_text() or "" for page in reader.pages)
    assert "Executive Summary" in text
    assert "Recommended Protection Package" in text
    assert "Appendix B Preliminary Service Rationale" in text
    assert '"mission_area_scores"' not in text
    assert '"services"' not in text


def test_public_part_two_control_does_not_print_the_webpage():
    source = Path("public_protection_advisor.py").read_text(encoding="utf-8")
    assert 'window.location.assign("/public/protection-advisor/report.pdf")' in source
    assert 'scope==="part2"' in source
