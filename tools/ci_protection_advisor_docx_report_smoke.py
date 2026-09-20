from pathlib import Path
from tempfile import TemporaryDirectory
from datetime import datetime, timezone
from docx import Document
from protection_advisor_report_contract import build_report_context
from protection_advisor_docx_report import render_protection_advisor_docx

TEMPLATE = """Client: (place client code name here)
Client Tasking: (place project code name here)
Day Month Year Time (DTG): (place date and time here)
Report Reference: (place system-generated immutable reference here)
Information Classification / Handling: (insert client-designated handling, sensitivity, disclosure, records, or distribution restrictions here; do not place classified or otherwise restricted information in this report unless Salus has expressly authorized and established the required handling environment.)
(insert Protective Advisor report part 1 and protective advisor report part 2 here)
"""

with TemporaryDirectory() as tmp:
    template = Path(tmp) / "template.docx"
    output = Path(tmp) / "rendered.docx"
    doc = Document()
    for line in TEMPLATE.splitlines():
        doc.add_paragraph(line)
    doc.save(template)
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
    text = "\n".join(p.text for p in Document(output).paragraphs)
    assert "CLIENT-FOX" in text
    assert "PROJECT-ADVISOR-01" in text
    assert "20-09-2026 14:30 UTC" in text
    assert "SPA-REPORT-0001" in text
    assert "CUI" in text
    assert "Preliminary Part 2 package recommendation." in text
print("Protection Advisor DOCX renderer smoke passed")
