from datetime import datetime, timezone
from pathlib import Path
from tempfile import TemporaryDirectory
from protection_advisor_report_artifact import prepare_review_artifact

with TemporaryDirectory() as tmp:
    template = Path("Protection Advisor Report Template.docx")
    assert template.is_file()
    output = Path(tmp) / "out"
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
    assert result["template_version"] == "SPA-REPORT-TEMPLATE-1.3.0"
    assert (output / "SPA-REPORT-0001.docx").exists()
print("Protection Advisor review artifact smoke passed")
