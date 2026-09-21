from datetime import datetime, timezone

from protection_advisor_report_contract import build_report_context


ctx = build_report_context(
    client_code_name="Northstar",
    project_code_name="Beacon 01",
    organization_type="Business",
    government_or_public_service_role="None",
    assessment_authority_or_sponsor="Authorized program sponsor",
    information_handling="Confidential",
    report_reference="SPA-REPORT-0001",
    generated_at=datetime(2026, 9, 20, 14, 30, tzinfo=timezone.utc),
)
fields = ctx.as_template_fields()
assert fields["ClientCodeName"] == "Northstar"
assert fields["ProjectCodeName"] == "Beacon 01"
assert fields["OrganizationType"] == "Business"
assert fields["InformationClassificationHandling"] == "Confidential"
assert fields["GeneratedAt"] == "20-09-2026 14:30 UTC"
assert fields["RetentionPolicyVersion"] == "SPA-PROSPECT-RETENTION-INDEFINITE-1.0.0"

government = build_report_context(
    client_code_name="Public Sentinel",
    project_code_name="Continuity Review",
    organization_type="Government or Public Institution",
    government_or_public_service_role="Public safety mission",
    assessment_authority_or_sponsor="Authorized agency sponsor",
    information_handling="CUI",
    report_reference="SPA-REPORT-0002",
    generated_at=datetime.now(timezone.utc),
)
assert government.as_template_fields()["OrganizationType"] == "Government or Public Institution"

try:
    build_report_context(
        client_code_name=" ",
        project_code_name="Beacon 01",
        organization_type="Business",
        government_or_public_service_role="None",
        assessment_authority_or_sponsor="Sponsor",
        information_handling="Internal",
        report_reference="SPA-REPORT-0003",
        generated_at=datetime.now(timezone.utc),
    )
except ValueError:
    pass
else:
    raise AssertionError("blank client code name was accepted")

print("Protection Advisor report contract smoke passed")
