"""Check the approved-font scope receipt source used by M365 conversion."""
from __future__ import annotations

import sys
from pathlib import Path
from tempfile import TemporaryDirectory

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from docx import Document
from protection_advisor_docx_report import render_scope_receipt_docx
from protection_advisor_report_contract import build_report_context
from salus_package_path import draft_level_1_scope_receipt


context = build_report_context(
    client_code_name="Fictional Acceptance Member",
    project_code_name="Fictional scope",
    organization_type="Business",
    government_or_public_service_role="None",
    assessment_authority_or_sponsor="Fictional owner",
    information_handling="Confidential",
    report_reference="SPA-REPORT-FICTIONAL",
)
receipt = draft_level_1_scope_receipt(
    {"covered_operation": "One fictional site", "facility_locations": "Fictional location"},
    {"band": "A", "label": "Level 1A Access"},
)
receipt["receipt_id"] = "SPA-RECEIPT-FICTIONAL"
with TemporaryDirectory() as directory:
    output = render_scope_receipt_docx(
        output_path=Path(directory) / "receipt.docx", context=context, receipt=receipt,
    )
    document = Document(str(output))
    text = "\n".join(p.text for p in document.paragraphs)
    assert "Confidential scope receipt" in text
    assert "This receipt is a preparation aid" in text
    assert "page 1 of 1" in document.sections[0].footer.paragraphs[0].text
    assert len(document.tables) == 3
    if len(sys.argv) > 1:
        Path(sys.argv[1]).write_bytes(output.read_bytes())
print("Fictional scope receipt DOCX source passed")
