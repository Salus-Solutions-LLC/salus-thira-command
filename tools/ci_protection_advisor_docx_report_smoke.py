from datetime import datetime, timezone
from pathlib import Path
from tempfile import TemporaryDirectory

from docx import Document
from docx.enum.section import WD_SECTION

from protection_advisor_docx_report import _professional_body, render_protection_advisor_docx, render_protection_advisor_pdf, render_scope_receipt_pdf
from protection_advisor_report_contract import build_report_context
from salus_package_path import draft_level_1_scope_receipt, suggest_provisional_level_1_path


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
    assert "CUI REVIEW REQUESTED" not in rendered.sections[1].header._element.xml
    for section in (rendered.sections[0], rendered.sections[2]):
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
            "provisional_path": {"label": "Possible Level 1B", "reason": "Two distinct operations need comparison.", "next_step": "Salus will provide a written quote."},
            "scope_receipt": {"receipt_id": "SPA-RECEIPT-TEST", "version": "SPA-SCOPE-RECEIPT-0.3.0", "lead_sentence": "Possible Level 1B is a starting point; written price pending.", "requested_boundary": "Two fictional facilities", "requested_location": "Example County", "outside_boundary": "Other operations are excluded.", "member_prepares": ["A simple organization chart."], "price_state": "Written quote pending.", "schedule_state": "Start and delivery dates are set in the written scope.", "decision_owner": "Executive team", "next_step": "Review the boundary.", "status": "Draft for Salus review", "milestones": [{"step": "Confirm scope", "owner": "Salus and decision owner", "complete_when": "Boundary agreed."}], "choices": [{"choice": "Request a fixed quote", "effect": "Salus sends a written proposal."}]},
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
    assert rendered_pdf.metadata.title == "Protection Advisor Scope and Readiness Report"
    assert rendered_pdf.trailer["/Root"].get("/Lang") == "en-US"
    extracted = "\n".join(page.extract_text() for page in rendered_pdf.pages)
    assert "CUI review requested" in extracted
    assert "Possible Level 1B" in extracted
    assert "Two fictional facilities" in extracted
    assert "SPA-RECEIPT-TEST" in extracted
    assert "Request a fixed quote" in extracted
    assert "CONFIDENTIALITY NOTICE - AUTHORIZED USE ONLY" not in extracted

    body = Document()
    _professional_body(body, context.as_template_fields(), {"recommendation": "Preliminary review"}, {
        "provisional_path": {"label": "Possible Level 1B", "reason": "Two distinct operations need comparison.", "next_step": "Salus will provide a written quote."},
        "primary_service": {"title": "Level 1 SalCAPA Package", "level": 1, "level_name": "Initial Pass", "summary": "Four reports.", "why": "First step."},
        "sequence": [], "services": [], "later_phase_services": [],
    })
    assert "Possible Level 1B" in "\n".join(p.text for p in body.paragraphs)

print("Protection Advisor PDF table-layout smoke passed")

with TemporaryDirectory() as tmp:
    profile = {
        "decision_units": "One", "separate_findings": "No", "group_priorities": "No",
        "covered_operation": "One fictional child-care site",
        "facility_locations": "Example County, Texas", "decision_authority": "Director",
    }
    path = suggest_provisional_level_1_path(profile)
    receipt = draft_level_1_scope_receipt(profile, path)
    receipt["receipt_id"] = "SPA-RECEIPT-TEST"
    output = Path(tmp) / "receipt.pdf"
    render_scope_receipt_pdf(output_path=output, context=context, receipt=receipt)
    one_page = PdfReader(output)
    assert len(one_page.pages) == 1
    text = one_page.pages[0].extract_text()
    for required in ("SPA-RECEIPT-TEST", "page 1 of 1", "$1,500",
                     "organization chart", "Five steps", "Your choices", "Decline for now"):
        assert required in text, required
    receipt["member_prepares"] = ["A large packet " * 500]
    try:
        render_scope_receipt_pdf(output_path=output, context=context, receipt=receipt)
    except RuntimeError as exc:
        assert "exceeds one page" in str(exc)
    else:
        raise AssertionError("Overlong receipt must fail closed")
    assert not output.exists()

print("Protection Advisor one-page scope receipt smoke passed")
