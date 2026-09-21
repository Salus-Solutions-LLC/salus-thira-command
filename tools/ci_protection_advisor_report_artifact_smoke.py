from datetime import datetime, timezone
from pathlib import Path
from tempfile import TemporaryDirectory
from docx import Document
from protection_advisor_report_artifact import prepare_review_artifact

with TemporaryDirectory() as tmp:
    template = Path(tmp) / "template.docx"
    output = Path(tmp) / "out"
    doc = Document()
    doc.add_paragraph("Client: (place client code name here)")
    doc.add_paragraph("Client Tasking: (place project code name here)")
    doc.add_paragraph("Day Month Year Time (DTG): (place date and time here)")
    doc.add_paragraph("Report Reference: (place system-generated immutable reference here)")
    doc.add_paragraph("Information Classification / Handling: (insert client-designated handling, sensitivity, disclosure, records, or distribution restrictions here; do not place classified or otherwise restricted information in this report unless Salus has expressly authorized and established the required handling environment.)")
    doc.add_paragraph("(insert Protective Advisor report part 1 and protective advisor report part 2 here)")
    doc.save(template)
    result = prepare_review_artifact(
        template_path=str(template),
        output_dir=str(output),
        identity={"protected_member_code_name": "CLIENT-FOX", "project_code_name": "PROJECT-01", "handling_status": "Controlled Information Requested"},
        organization_type="Federal Government",
        public_service_role="Public safety mission",
        assessment_authority="Authorized sponsor",
        part1_text="Part 1 summary",
        part2_text="Part 2 recommendation",
        report_reference="SPA-REPORT-0001",
        generated_at=datetime(2026, 9, 21, 14, 30, tzinfo=timezone.utc),
    )
    assert result["status"] == "Prepared for Salus Review"
    assert (output / "SPA-REPORT-0001.docx").exists()
print("Protection Advisor review artifact smoke passed")
