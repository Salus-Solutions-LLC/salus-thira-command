from datetime import datetime, timezone
from pathlib import Path
from tempfile import TemporaryDirectory

from docx import Document
from docx.enum.section import WD_SECTION

from protection_advisor_docx_report import render_protection_advisor_docx, render_protection_advisor_pdf
from protection_advisor_report_contract import build_report_context


template = Path("Protection Advisor Report Template.docx")
assert template.is_file(), "approved Protection Advisor DOCX template is missing"

with TemporaryDirectory() as tmp:
    output = Path(tmp) / "rendered.docx"
    context = build_report_context(
        client_code_name="CLIENT-FOX",
        project_code_name="PROJECT-ADVISOR-01",
        organization_type="Federal Government",
        government_or_public_service_role="Public safety mission",
        assessment_authority_or_sponsor="Authorized sponsor",
        information_handling="CUI",
        report_reference="SPA-REPORT-0001",
        generated_at=datetime(2026, 9, 20, 14, 30, tzinfo=timezone.utc),
    )
    render_protection_advisor_docx(
        template_path=template,
        output_path=output,
        context=context,
        part1_text="Preliminary Part 1 summary.",
        part2_text="Preliminary Part 2 package recommendation.",
    )

    rendered = Document(output)
    text = "\n".join(
        [p.text for p in rendered.paragraphs]
        + [cell.text for table in rendered.tables for row in table.rows for cell in row.cells]
    )
    assert "CLIENT-FOX" in text
    assert "PROJECT-ADVISOR-01" in text
    assert "20-09-2026 14:30 UTC" in text
    assert "SPA-REPORT-0001" in text
    assert "CUI" in text
    assert "Preliminary Part 1 summary." in text
    assert "Preliminary Part 2 package recommendation." in text
    assert "This report has been prepared to assess" not in text
    assert len(rendered.sections) == 3
    assert rendered.sections[1].start_type == WD_SECTION.CONTINUOUS
    assert rendered.sections[2].start_type == WD_SECTION.NEW_PAGE
    for section in rendered.sections:
        header_xml = section.header._element.xml
        assert "CUI REVIEW REQUESTED" in header_xml
        assert 'string="REVIEW"' in header_xml
        assert "Controlled Unclassified Information (CUI)" not in header_xml
        assert "#bfbfbf" in header_xml.lower(), "watermark must remain light gray"
        assert "z-index:-251658240" in header_xml, "watermark must remain behind readable content"
    assert not any(p.text.strip() for p in rendered.sections[1].footer.paragraphs)

    confidential = build_report_context(
        client_code_name="EXAMPLE-MEMBER", project_code_name="EXAMPLE-PROJECT",
        organization_type="Business", government_or_public_service_role="None",
        assessment_authority_or_sponsor="Authorized representative",
        information_handling="Confidential", report_reference="SPA-REPORT-0002",
        generated_at=datetime(2026, 9, 20, 14, 30, tzinfo=timezone.utc),
    )
    confidential_output = Path(tmp) / "confidential.docx"
    render_protection_advisor_docx(
        template_path=template, output_path=confidential_output,
        context=confidential, part1_text="Preliminary summary.",
        part2_text="Preliminary package.",
    )
    confidential_doc = Document(confidential_output)
    assert "CUI" not in confidential_doc.element.xml
    assert "CUI" not in confidential_doc.sections[0].header._element.xml
    assert "CONFIDENTIAL" in confidential_doc.sections[0].header._element.xml

print("Protection Advisor DOCX three-page renderer smoke passed")

with TemporaryDirectory() as tmp:
    output = Path(tmp) / "rendered.pdf"
    context = build_report_context(
        client_code_name="CLIENT-FOX",
        project_code_name="PROJECT-ADVISOR-01",
        organization_type="Federal Government",
        government_or_public_service_role="Public safety mission",
        assessment_authority_or_sponsor="Authorized sponsor",
        information_handling="CUI",
        report_reference="SPA-REPORT-0001",
        generated_at=datetime(2026, 9, 20, 14, 30, tzinfo=timezone.utc),
    )
    render_protection_advisor_pdf(
        output_path=output,
        context=context,
        result={
            "recommendation": "Comprehensive review recommended",
            "strength_count": 6,
            "attention_count": 16,
            "information_gap_count": 5,
            "core_capabilities_considered": 32,
            "mission_area_scores": {area: 50 for area in ("Prevention", "Protection", "Mitigation", "Response", "Recovery")},
            "priority_capabilities": [{
                "capability": "Operational Communications and Coordination",
                "need_score": 92,
                "mission_areas": ["Protection", "Response"],
                "information_gap": True,
            }],
            "attention_topics": ["Validate communications."],
            "information_gaps": ["Current evidence unavailable."],
        },
        package={
            "primary_service": {"title": "Emergency Planning", "level": 2, "level_name": "Focused Review", "summary": "Validate priority capabilities.", "why": "Connected planning needs."},
            "sequence": ["Emergency Planning", "Continuity Program"],
            "later_phase_services": [],
            "services": [{"title": "Emergency Planning", "level": 2, "why": "Validate communications."}],
            "rationale": "Services are sequenced by assessed need.",
        },
    )
    pdf = output.read_bytes()
    assert pdf.startswith(b"%PDF-")
    assert len(pdf) > 10_000
    from pypdf import PdfReader
    rendered_pdf = PdfReader(output)
    assert rendered_pdf.metadata.title == "Protection Advisor Assessment Report"
    assert rendered_pdf.trailer["/Root"].get("/Lang") == "en-US"
    extracted = "\n".join(page.extract_text() for page in rendered_pdf.pages)
    assert "CUI review requested" in extracted
    assert "CONFIDENTIALITY NOTICE - AUTHORIZED USE ONLY" not in extracted

print("Protection Advisor PDF table-layout smoke passed")
