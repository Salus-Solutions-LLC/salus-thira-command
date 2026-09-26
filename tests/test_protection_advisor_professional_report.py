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
    page_count = len(reader.pages)
    assert f"Page 1 of {page_count}" in (reader.pages[0].extract_text() or "")
    assert "Page 2 of" not in (reader.pages[1].extract_text() or "")
    assert all(
        f"Page {number} of {page_count}" in (page.extract_text() or "")
        for number, page in enumerate(reader.pages, 1) if number != 2
    )
    fonts = reader.pages[2]["/Resources"]["/Font"].get_object().values()
    assert any("/FontFile2" in font.get_object()["/FontDescriptor"].get_object() for font in fonts if "/FontDescriptor" in font.get_object())
    text = "\n".join(page.extract_text() or "" for page in reader.pages)
    assert "Executive Summary" in text
    assert "Recommended Protection Package" in text
    assert "Appendix B Preliminary Service Rationale" in text
    assert '"mission_area_scores"' not in text
    assert '"services"' not in text


def test_pdf_total_pages_follow_long_wrapped_report(tmp_path: Path):
    result = dict(RESULT)
    result["priority_capabilities"] = [
        {"capability": f"Capability {index}: " + "Operational coordination and continuity " * 2,
         "need_score": index, "mission_areas": ["Prevention", "Protection", "Mitigation", "Response", "Recovery"],
         "information_gap": index % 2 == 0}
        for index in range(1, 33)
    ]
    result["attention_topics"] = [f"Confirm plans and current evidence {index}" for index in range(25)]
    result["information_gaps"] = [f"Validate authority {index}" for index in range(20)]
    path = render_protection_advisor_pdf(
        output_path=tmp_path / "long-report.pdf", context=_context(), result=result, package=PACKAGE,
    )
    reader = PdfReader(path)
    total = len(reader.pages)
    assert total > 10
    text = "\\n".join(page.extract_text() or "" for page in reader.pages)
    assert "Capability 32" in text
    assert all(
        f"Page {number} of {total}" in (page.extract_text() or "")
        for number, page in enumerate(reader.pages, 1) if number != 2
    )


def test_public_part_two_control_does_not_print_the_webpage():
    source = Path("public_protection_advisor.py").read_text(encoding="utf-8")
    assert 'fetch("/public/protection-advisor/report.pdf"' in source
    assert 'window.location.assign("/public/protection-advisor/report.pdf")' not in source
    assert 'scope==="part2"' in source


def test_requested_cui_is_visible_without_an_approved_marking(tmp_path: Path):
    context = build_report_context(
        client_code_name="Test Member", project_code_name="Test Project",
        organization_type="Private", government_or_public_service_role="Not provided",
        assessment_authority_or_sponsor="Not provided", information_handling="CUI",
        report_reference="SPA-REPORT-CUI-REQUEST", generated_at=datetime(2026, 9, 22, tzinfo=timezone.utc),
    )
    path = render_protection_advisor_pdf(
        output_path=tmp_path / "cui-request.pdf", context=context, result=RESULT, package=PACKAGE,
    )
    text = "\n".join(page.extract_text() or "" for page in PdfReader(path).pages)
    assert "CUI review requested" in text
    assert "Requested handling: CUI review requested" in text
    source = Path("public_protection_advisor.py").read_text(encoding="utf-8")
    assert 'handling = "CUI" if "CUI" in str(identity.get("handling_profile", "")) else "Confidential"' in source
