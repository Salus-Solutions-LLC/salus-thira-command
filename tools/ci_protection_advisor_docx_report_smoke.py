from datetime import datetime, timezone
from pathlib import Path
from tempfile import TemporaryDirectory

from docx import Document
from docx.enum.section import WD_SECTION

from protection_advisor_docx_report import render_protection_advisor_docx
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
    text = "\n".join(p.text for p in rendered.paragraphs)
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
        assert "CONFIDENTIAL" in header_xml
        assert "#bfbfbf" in header_xml.lower(), "watermark must remain light gray"
        assert "z-index:-251658240" in header_xml, "watermark must remain behind readable content"
    assert not any(p.text.strip() for p in rendered.sections[1].footer.paragraphs)

print("Protection Advisor DOCX three-page renderer smoke passed")
