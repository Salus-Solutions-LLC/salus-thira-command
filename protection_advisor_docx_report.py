"""Populate the approved Salus Protection Advisor DOCX report template."""

from __future__ import annotations

import os
from copy import deepcopy
from pathlib import Path

from protection_advisor_report_contract import ProtectionAdvisorReportContext

_TEMPLATE_NAME = "Protection Advisor Report Template.docx"
_INSERT_MARKER = "(insert Protective Advisor report part 1 and protective advisor report part 2 here)"


def _replace_text_across_runs(root, old: str, new: str) -> int:
    """Replace split Word text without rebuilding paragraphs or text boxes."""
    replacements = 0
    for paragraph in root.xpath(".//w:p"):
        nodes = paragraph.xpath(".//w:t")
        while nodes:
            combined = "".join(node.text or "" for node in nodes)
            start = combined.find(old)
            if start < 0:
                break
            end = start + len(old)
            offset = 0
            first_index = first_offset = last_index = last_offset = None
            for index, node in enumerate(nodes):
                node_text = node.text or ""
                next_offset = offset + len(node_text)
                if first_index is None and start < next_offset:
                    first_index = index
                    first_offset = start - offset
                if end <= next_offset:
                    last_index = index
                    last_offset = end - offset
                    break
                offset = next_offset
            if first_index is None or last_index is None:
                break
            first = nodes[first_index]
            last = nodes[last_index]
            prefix = (first.text or "")[:first_offset]
            suffix = (last.text or "")[last_offset:]
            first.text = prefix + new + (suffix if first_index == last_index else "")
            for index in range(first_index + 1, last_index):
                nodes[index].text = ""
            if first_index != last_index:
                last.text = suffix
            replacements += 1
    return replacements


def _trim_after_cover_page(document) -> None:
    """Keep the exact first-page cover and remove the template's old report body."""
    body = document.element.body
    page_break_seen = False
    for child in list(body):
        if child.tag.endswith("}sectPr"):
            continue
        if page_break_seen:
            body.remove(child)
            continue
        if child.xpath('.//w:br[@w:type="page"]') or child.xpath('.//w:pPr/w:sectPr'):
            page_break_seen = True
    if not page_break_seen:
        raise ValueError("template cover-page boundary was not found")


def _replace_story(target, source_xml, source_part) -> None:
    target.is_linked_to_previous = False
    element = target._element
    for child in list(element):
        element.remove(child)
    relationship_ids = {}
    for old_id, relationship in source_part.rels.items():
        if relationship.is_external:
            new_id = target.part.relate_to(
                relationship.target_ref,
                relationship.reltype,
                is_external=True,
            )
        else:
            new_id = target.part.relate_to(relationship.target_part, relationship.reltype)
        relationship_ids[old_id] = new_id
    for child in source_xml:
        copied = deepcopy(child)
        for descendant in copied.iter():
            for attribute, value in list(descendant.attrib.items()):
                if value in relationship_ids:
                    descendant.set(attribute, relationship_ids[value])
        element.append(copied)


def _clear_story(target) -> None:
    target.is_linked_to_previous = False
    element = target._element
    for child in list(element):
        element.remove(child)


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
        from docx.enum.section import WD_SECTION
    except ImportError as exc:
        raise RuntimeError("python-docx is required for DOCX Protection Advisor reports") from exc

    document = Document(str(source))
    fields = context.as_template_fields()
    substitutions = {
        "(place client code name here)": fields["ClientCodeName"],
        "(place project code name here)": fields["ProjectCodeName"],
        "(place date and time here)": fields["GeneratedAt"],
        "(day, month, year, time)": fields["GeneratedAt"],
        "(place system-generated immutable reference here)": fields["ReportReference"],
    }
    marker_found = any(_INSERT_MARKER in paragraph.text for paragraph in document.paragraphs)
    replacement_count = sum(
        _replace_text_across_runs(document.element.body, old, new)
        for old, new in substitutions.items()
    )
    if replacement_count < 4:
        raise ValueError("template identity fields were not found")
    if not marker_found:
        raise ValueError("template Part 1/Part 2 insertion marker was not found")

    _trim_after_cover_page(document)

    cover_section = document.sections[0]
    cover_header = deepcopy(cover_section.header._element)
    cover_footer = deepcopy(cover_section.footer._element)

    blank_section = document.add_section(WD_SECTION.CONTINUOUS)
    # The intentionally blank second page retains only the template's light
    # CONFIDENTIAL watermark; it has no visible header text or footer.
    _replace_story(blank_section.header, cover_header, cover_section.header.part)
    _clear_story(blank_section.footer)

    results_section = document.add_section(WD_SECTION.NEW_PAGE)
    _replace_story(results_section.header, cover_header, cover_section.header.part)
    _replace_story(results_section.footer, cover_footer, cover_section.footer.part)

    document.add_heading("Protection Advisor Assessment Results", level=1)
    identity_lines = (
        ("Protected Member Code Name", fields["ClientCodeName"]),
        ("Project Code Name", fields["ProjectCodeName"]),
        ("Report Reference", fields["ReportReference"]),
        ("Date and Time (DTG)", fields["GeneratedAt"]),
        ("Information Classification / Handling", fields["InformationClassificationHandling"]),
    )
    for label, value in identity_lines:
        paragraph = document.add_paragraph()
        paragraph.add_run(f"{label}: ").bold = True
        paragraph.add_run(value)

    document.add_heading("Part 1 — Anonymous Preliminary Summary", level=2)
    document.add_paragraph(part1_text.strip())
    document.add_heading("Part 2 — Detailed Results and Preliminary Package", level=2)
    document.add_paragraph(part2_text.strip())

    destination.parent.mkdir(parents=True, exist_ok=True)
    document.save(str(destination))
    return destination
