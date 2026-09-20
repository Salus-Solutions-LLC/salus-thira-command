"""Populate the approved Salus Protection Advisor DOCX report template."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Iterable

from protection_advisor_report_contract import ProtectionAdvisorReportContext

_TEMPLATE_NAME = "Protection Advisor Report Template.docx"
_INSERT_MARKER = "(insert Protective Advisor report part 1 and protective advisor report part 2 here)"


def _replace_paragraph(paragraph, text: str) -> None:
    paragraph.text = text


def _iter_paragraphs(document):
    for paragraph in document.paragraphs:
        yield paragraph
    for table in document.tables:
        for row in table.rows:
            for cell in row.cells:
                yield from _iter_paragraphs(cell)


def render_protection_advisor_docx(
    *,
    template_path: str | os.PathLike[str],
    output_path: str | os.PathLike[str],
    context: ProtectionAdvisorReportContext,
    part1_text: str,
    part2_text: str,
) -> Path:
    """Render a nonbinding, review-gated Protection Advisor report.

    The renderer writes a new DOCX and never overwrites the source template.
    It does not release a report, create a contract, or approve a CUI marking.
    """
    if not part1_text.strip() or not part2_text.strip():
        raise ValueError("both Part 1 and Part 2 report content are required")
    source = Path(template_path)
    destination = Path(output_path)
    if not source.is_file():
        raise FileNotFoundError(f"Protection Advisor template not found: {source}")
    if source.resolve() == destination.resolve():
        raise ValueError("output must not overwrite the report template")

    try:
        from docx import Document
    except ImportError as exc:
        raise RuntimeError("python-docx is required for DOCX Protection Advisor reports") from exc

    document = Document(str(source))
    fields = context.as_template_fields()
    substitutions = {
        "(place client code name here)": fields["ClientCodeName"],
        "(place project code name here)": fields["ProjectCodeName"],
        "(place date and time here)": fields["GeneratedAt"],
        "(place system-generated immutable reference here)": fields["ReportReference"],
        "(insert client-designated handling, sensitivity, disclosure, records, or distribution restrictions here; do not place classified or otherwise restricted information in this report unless Salus has expressly authorized and established the required handling environment.)": (
            fields["InformationClassificationHandling"]
        ),
    }
    found_identity = False
    found_marker = False
    for paragraph in _iter_paragraphs(document):
        text = paragraph.text
        if not text:
            continue
        for old, new in substitutions.items():
            if old in text:
                text = text.replace(old, new)
                found_identity = True
        if _INSERT_MARKER in text:
            text = text.replace(
                _INSERT_MARKER,
                f"Part 1 — Anonymous Preliminary Summary\\n{part1_text.strip()}\\n\\n"
                f"Part 2 — Detailed Results and Preliminary Package\\n{part2_text.strip()}",
            )
            found_marker = True
        _replace_paragraph(paragraph, text)
    if not found_identity:
        raise ValueError("template identity fields were not found")
    if not found_marker:
        raise ValueError("template Part 1/Part 2 insertion marker was not found")

    destination.parent.mkdir(parents=True, exist_ok=True)
    document.save(str(destination))
    return destination
