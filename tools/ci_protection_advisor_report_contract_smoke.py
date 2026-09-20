from datetime import datetime, timezone
from protection_advisor_report_contract import build_report_context

ctx = build_report_context(
    client_code_name="CLIENT-FOX",
    project_code_name="PROJECT-ADVISOR-01",
    organization_type="Federal Government",
    government_or_public_service_role="Public safety mission",
    assessment_authority_or_sponsor="Authorized program sponsor",
    information_handling="CUI",
    report_reference="SPA-REPORT-0001",
    generated_at=datetime(2026, 9, 20, 14, 30, tzinfo=timezone.utc),
)
fields = ctx.as_template_fields()
assert fields["ClientCodeName"] == "CLIENT-FOX"
assert fields["ProjectCodeName"] == "PROJECT-ADVISOR-01"
assert fields["OrganizationType"] == "Federal Government"
assert fields["InformationClassificationHandling"] == "CUI"
assert fields["GeneratedAt"] == "20-09-2026 14:30 UTC"
assert fields["RetentionPolicyVersion"] == "SPA-PROSPECT-RETENTION-INDEFINITE-1.0.0"

try:
    build_report_context(
        client_code_name="FOX",
        project_code_name="PROJECT-ADVISOR-01",
        organization_type="Private",
        government_or_public_service_role="None",
        assessment_authority_or_sponsor="Sponsor",
        information_handling="Internal",
        report_reference="SPA-REPORT-0001",
        generated_at=datetime.now(timezone.utc),
    )
except ValueError:
    pass
else:
    raise AssertionError("invalid client code name was accepted")

print("Protection Advisor report contract smoke passed")
