"""Governed Protection Advisor report context contract.

This module is the application-side contract for populating the approved
Salus-branded report template. It deliberately produces data, not a binding
scope, price, Protected Member record, or customer commitment.
"""

from __future__ import annotations

from dataclasses import dataclass, asdict
from datetime import datetime, timezone
from typing import Any

ORGANIZATION_TYPES = frozenset({
    "Federal Government", "State Government", "Local Government",
    "Quasi-Governmental", "Private", "NGO", "Other",
})
HANDLING_LEVELS = frozenset({
    "Public", "Internal", "Confidential", "CUI", "Restricted",
})
INDEFINITE_RETENTION_POLICY = "SPA-PROSPECT-RETENTION-INDEFINITE-1.0.0"


@dataclass(frozen=True)
class ProtectionAdvisorReportContext:
    """Validated values used to populate a Protection Advisor report."""

    client_code_name: str
    project_code_name: str
    organization_type: str
    government_or_public_service_role: str
    assessment_authority_or_sponsor: str
    information_handling: str
    report_reference: str
    generated_at: str
    retention_policy_version: str = INDEFINITE_RETENTION_POLICY

    def __post_init__(self) -> None:
        values = {
            "client_code_name": self.client_code_name,
            "project_code_name": self.project_code_name,
            "organization_type": self.organization_type,
            "government_or_public_service_role": self.government_or_public_service_role,
            "assessment_authority_or_sponsor": self.assessment_authority_or_sponsor,
            "information_handling": self.information_handling,
            "report_reference": self.report_reference,
        }
        for name, value in values.items():
            if not isinstance(value, str) or not value.strip():
                raise ValueError(f"{name} is required")
            if len(value.strip()) > 500:
                raise ValueError(f"{name} exceeds the report field limit")
        if self.organization_type not in ORGANIZATION_TYPES:
            raise ValueError("organization_type is not an approved value")
        if self.information_handling not in HANDLING_LEVELS:
            raise ValueError("information_handling is not an approved value")
        if not self.client_code_name.startswith("CLIENT-"):
            raise ValueError("client_code_name must use the CLIENT- code-name format")
        if not self.project_code_name.startswith("PROJECT-"):
            raise ValueError("project_code_name must use the PROJECT- code-name format")
        if not self.report_reference.startswith("SPA-REPORT-"):
            raise ValueError("report_reference must use the SPA-REPORT- format")

    def as_template_fields(self) -> dict[str, Any]:
        """Return stable field names for the approved Word report template."""
        return {
            "ClientCodeName": self.client_code_name,
            "ProjectCodeName": self.project_code_name,
            "OrganizationType": self.organization_type,
            "GovernmentOrPublicServiceRole": self.government_or_public_service_role,
            "AssessmentAuthorityOrSponsor": self.assessment_authority_or_sponsor,
            "InformationClassificationHandling": self.information_handling,
            "ReportReference": self.report_reference,
            "GeneratedAt": self.generated_at,
            "RetentionPolicyVersion": self.retention_policy_version,
        }


def build_report_context(
    *,
    client_code_name: str,
    project_code_name: str,
    organization_type: str,
    government_or_public_service_role: str,
    assessment_authority_or_sponsor: str,
    information_handling: str,
    report_reference: str,
    generated_at: datetime | None = None,
) -> ProtectionAdvisorReportContext:
    """Build a day-month-year, 24-hour UTC report context."""
    stamp = generated_at or datetime.now(timezone.utc)
    if stamp.tzinfo is None:
        raise ValueError("generated_at must include timezone information")
    return ProtectionAdvisorReportContext(
        client_code_name=client_code_name.strip(),
        project_code_name=project_code_name.strip(),
        organization_type=organization_type.strip(),
        government_or_public_service_role=government_or_public_service_role.strip(),
        assessment_authority_or_sponsor=assessment_authority_or_sponsor.strip(),
        information_handling=information_handling.strip(),
        report_reference=report_reference.strip(),
        generated_at=stamp.astimezone(timezone.utc).strftime("%d-%m-%Y %H:%M UTC"),
    )
