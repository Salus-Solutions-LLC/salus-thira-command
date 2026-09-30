"""Prepare a governed Protection Advisor DOCX artifact for Salus review."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

from protection_advisor_docx_report import render_protection_advisor_docx
from protection_advisor_report_contract import build_report_context


def prepare_review_artifact(
    *,
    template_path: str | None,
    output_dir: str | None,
    identity: dict[str, Any],
    organization_type: str,
    public_service_role: str,
    assessment_authority: str,
    part1_text: str,
    part2_text: str,
    report_reference: str,
    generated_at,
) -> dict[str, Any]:
    """Render a review-only DOCX when deployment configuration permits it.

    The function is fail-closed: absent configuration produces no artifact and
    never falls back to an uncontrolled temporary location.
    """
    configured_template = (template_path or os.getenv("SALUS_ADVISOR_DOCX_TEMPLATE_PATH", "")).strip()
    configured_output = (output_dir or os.getenv("SALUS_ADVISOR_REPORT_OUTPUT_DIR", "")).strip()
    if not configured_template or not configured_output:
        return {"status": "Not Configured", "review_required": True}

    context = build_report_context(
        client_code_name=str(identity["protected_member_code_name"]),
        project_code_name=str(identity["project_code_name"]),
        organization_type=organization_type,
        government_or_public_service_role=public_service_role or "Not provided",
        assessment_authority_or_sponsor=assessment_authority or "Not provided",
        information_handling="CUI" if identity.get("handling_status") == "Controlled Information Requested" else "Confidential",
        report_reference=report_reference,
        generated_at=generated_at,
    )
    destination = Path(configured_output) / f"{report_reference}.docx"
    render_protection_advisor_docx(
        template_path=configured_template,
        output_path=destination,
        context=context,
        part1_text=part1_text,
        part2_text=part2_text,
    )
    return {
        "status": "Prepared for Salus Review",
        "review_required": True,
        "report_reference": report_reference,
        "template_version": "SPA-REPORT-TEMPLATE-1.3.0",
        "retention_policy_version": context.retention_policy_version,
    }
