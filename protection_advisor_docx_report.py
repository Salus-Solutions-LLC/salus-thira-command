"""Populate the approved Salus Protection Advisor DOCX report template."""

from __future__ import annotations

import os
import json
import io
import zipfile
from copy import deepcopy
from pathlib import Path

from protection_advisor_report_contract import ProtectionAdvisorReportContext

_TEMPLATE_NAME = "Protection Advisor Report Template.docx"
_INSERT_MARKER = "(insert Protective Advisor report part 1 and protective advisor report part 2 here)"


def _add_bullets(document, items) -> None:
    for item in items:
        # The approved production template may not define Word's built-in
        # "List Bullet" style. Use a plain paragraph with an explicit bullet so
        # rendering remains deterministic across approved and smoke templates.
        paragraph = document.add_paragraph()
        paragraph.add_run("\u2022 " + str(item))


def _sequence_rows(package):
    """Use the recommended service's own purpose in both report formats."""
    services = [package.get("primary_service") or {}, *(package.get("services") or [])]
    summaries = {str(service.get("title", "")).strip(): str(service.get("summary", "")).strip()
                 for service in services if service.get("title") and service.get("summary")}
    rows = []
    for index, label in enumerate(package.get("sequence") or [], 1):
        name = str(label).split(" — Level", 1)[0].split(" - Level", 1)[0].strip()
        rows.append((index, label, summaries.get(name) or
                     "Validate the scope, implement approved work, and document the result."))
    return rows


def _add_table(document, headers, rows, widths=None):
    from docx.enum.table import WD_CELL_VERTICAL_ALIGNMENT, WD_TABLE_ALIGNMENT
    from docx.enum.text import WD_ALIGN_PARAGRAPH
    from docx.oxml import OxmlElement
    from docx.oxml.ns import qn
    from docx.shared import Inches, Pt, RGBColor

    table = document.add_table(rows=1, cols=len(headers))
    table.alignment = WD_TABLE_ALIGNMENT.CENTER
    table.autofit = False
    if widths:
        for index, width in enumerate(widths):
            table.columns[index].width = Inches(width)
    header = table.rows[0]
    header_properties = header._tr.get_or_add_trPr()
    repeat = OxmlElement("w:tblHeader")
    repeat.set(qn("w:val"), "true")
    header_properties.append(repeat)
    for index, title in enumerate(headers):
        cell = header.cells[index]
        if widths:
            cell.width = Inches(widths[index])
        cell.vertical_alignment = WD_CELL_VERTICAL_ALIGNMENT.CENTER
        shading = OxmlElement("w:shd")
        shading.set(qn("w:fill"), "17365D")
        cell._tc.get_or_add_tcPr().append(shading)
        paragraph = cell.paragraphs[0]
        paragraph.alignment = WD_ALIGN_PARAGRAPH.CENTER
        paragraph.paragraph_format.space_after = Pt(0)
        run = paragraph.add_run(str(title))
        run.bold = True
        run.font.size = Pt(9)
        run.font.color.rgb = RGBColor(255, 255, 255)
    for row_index, values in enumerate(rows):
        cells = table.add_row().cells
        for index, value in enumerate(values):
            cell = cells[index]
            if widths:
                cell.width = Inches(widths[index])
            cell.vertical_alignment = WD_CELL_VERTICAL_ALIGNMENT.CENTER
            if row_index % 2:
                shading = OxmlElement("w:shd")
                shading.set(qn("w:fill"), "F5F8FA")
                cell._tc.get_or_add_tcPr().append(shading)
            paragraph = cell.paragraphs[0]
            paragraph.paragraph_format.space_after = Pt(0)
            run = paragraph.add_run(str(value))
            run.font.size = Pt(9.5)
    return table


def _professional_body(document, fields, result, package) -> None:
    """Write the approved client-report architecture from governed model data."""
    scores = result.get("mission_area_scores") or {}
    capabilities = result.get("priority_capabilities") or []
    gaps = result.get("information_gaps") or []
    attention = result.get("attention_topics") or []
    primary = package.get("primary_service") or {}

    document.add_heading("Protection Advisor Assessment Report", level=1)
    document.add_paragraph("Preliminary results and recommended protection package")
    _add_table(document, ("Report detail", "Value"), (
        ("Protected Member code name", fields["ClientCodeName"]),
        ("Project code name", fields["ProjectCodeName"]),
        ("Report reference", fields["ReportReference"]),
        ("Prepared", fields["GeneratedAt"]),
        ("Handling", "CUI review requested" if fields["InformationClassificationHandling"] == "CUI" else fields["InformationClassificationHandling"]),
        ("Status", "Preliminary - Salus professional review required"),
    ), widths=(2.05, 4.35))

    document.add_heading("Executive Summary", level=1)
    document.add_paragraph(
        f"The assessment recorded {result.get('strength_count', 0)} positive indicators, "
        f"{result.get('attention_count', 0)} conditions requiring attention, and "
        f"{result.get('information_gap_count', 0)} material information gaps. "
        "These results support a connected review of protection, preparedness, continuity, "
        "response, and recovery rather than isolated corrective projects."
    )
    if capabilities:
        names = ", ".join(str(item.get("capability", "")).strip() for item in capabilities[:3])
        document.add_paragraph(
            f"The highest preliminary capability priorities are {names}. These priorities "
            "identify where validation should begin; they do not establish that a particular "
            "threat, deficiency, or compliance failure exists."
        )
    if primary:
        document.add_paragraph(
            f"Salus recommends beginning with {primary.get('title', 'a qualification and validation review')} "
            f"at Level {primary.get('level', '')} {primary.get('level_name', '')}. "
            f"{primary.get('summary', '')}"
        )

    document.add_page_break()
    document.add_heading("Assessment Snapshot", level=1)
    _add_table(document, ("Measure", "Result", "Interpretation"), (
        ("Overall result", result.get("recommendation", "Professional review recommended"), "Preliminary decision-support result"),
        ("Positive indicators", result.get("strength_count", 0), "Reported practices that may support improvement"),
        ("Conditions requiring attention", result.get("attention_count", 0), "Potential gaps, weaknesses, or unvalidated capability"),
        ("Information gaps", result.get("information_gap_count", 0), "Unknowns that could materially change conclusions"),
        ("Core capabilities considered", result.get("core_capabilities_considered", 32), "Capabilities evaluated across five mission areas"),
    ), widths=(2.1, 1.35, 2.95))

    document.add_heading("Mission Area Profile", level=1)
    document.add_paragraph(
        "These scores are screening indicators, not audit grades. Lower values identify areas "
        "requiring validation, investigation, or improvement planning."
    )
    score_rows = []
    for area in ("Prevention", "Protection", "Mitigation", "Response", "Recovery"):
        score = int(scores.get(area, 0))
        interpretation = "Relative strength" if score >= 60 else "Moderate concern" if score >= 50 else "Priority concern"
        score_rows.append((area, f"{score} / 100", interpretation))
    _add_table(document, ("Mission area", "Screening score", "Preliminary interpretation"), score_rows, widths=(2.0, 1.5, 2.9))
    document.add_heading("Primary Conclusions", level=1)
    _add_bullets(document, (
        "Leadership should treat protection, emergency planning, continuity, and capability validation as one integrated program.",
        "Reported capability should be tested against current plans, records, interviews, demonstrations, exercises, and site conditions.",
        "Decision authority, succession, escalation, dependencies, and alternate arrangements require explicit validation.",
        "Final findings, scope, price, and assurance statements require authorized Salus professional review.",
    ))

    document.add_page_break()
    document.add_heading("Priority Capability Findings", level=1)
    cap_rows = []
    for index, item in enumerate(capabilities, 1):
        cap_rows.append((
            index,
            item.get("capability", "Not stated"),
            item.get("need_score", ""),
            ", ".join(item.get("mission_areas") or []),
            "Information incomplete" if item.get("information_gap") else "Reported need",
        ))
    _add_table(document, ("Priority", "Capability", "Need", "Mission areas", "Basis"), cap_rows, widths=(.8, 2.0, .65, 1.6, 1.35))
    document.add_paragraph(
        "Need scores rank the relative urgency of review within this submission. They are not "
        "probability estimates, compliance findings, or final measures of readiness."
    )
    document.add_heading("Conditions Requiring Attention", level=1)
    _add_bullets(document, attention or ("No specific attention topics were preserved in this preliminary record.",))

    document.add_page_break()
    document.add_heading("Information Gaps", level=1)
    document.add_paragraph(
        "These unanswered or insufficiently supported issues could materially change the "
        "assessment and should be resolved before Salus issues a final opinion, scope, or price."
    )
    _add_bullets(document, gaps or ("No explicit information gap was recorded; professional validation is still required.",))
    document.add_heading("Evidence Needed", level=1)
    _add_bullets(document, (
        "Current emergency, continuity, communications, security, and recovery plans.",
        "Authority, succession, delegation, notification, and escalation records.",
        "Essential-function, dependency, vendor, utility, and restoration-priority information.",
        "Training, exercise, incident, corrective-action, maintenance, and inspection records.",
        "Relevant interviews, demonstrations, site observations, and current performance evidence.",
    ))
    document.add_heading("Validation Standard", level=2)
    document.add_paragraph(
        "Salus should keep verified facts separate from reported conditions, reasonable "
        "inferences, and unresolved unknowns. A written plan is not sufficient evidence by itself."
    )
    hypothesis = result.get("preliminary_hypothesis") or {}
    if hypothesis:
        document.add_heading("Preliminary Working Hypothesis and Level 1 Action", level=2)
        for key in ("reported_basis", "working_assumption", "level_1_action"):
            if hypothesis.get(key):
                document.add_paragraph(str(hypothesis[key]))
        _add_bullets(document, hypothesis.get("checklist") or ())

    document.add_page_break()
    document.add_heading("Recommended Protection Package", level=1)
    if primary:
        document.add_paragraph(
            f"The preliminary lead engagement is {primary.get('title', 'Professional Review')} - "
            f"Level {primary.get('level', '')} {primary.get('level_name', '')}. {primary.get('summary', '')}"
        )
        document.add_paragraph(f"Why this leads the package. {primary.get('why', '')}")
    sequence = package.get("sequence") or []
    document.add_heading("Recommended Sequence", level=1)
    sequence_rows = _sequence_rows(package)
    _add_table(document, ("Phase", "Service", "Purpose"), sequence_rows, widths=(.6, 2.85, 2.95))
    document.add_heading("Additional Later Phase Services", level=1)
    for service in package.get("later_phase_services") or []:
        document.add_paragraph(
            f"{service.get('title', 'Service')} - Level {service.get('level', '')} "
            f"{service.get('level_name', '')}. {service.get('summary', '')}"
        )

    document.add_page_break()
    document.add_heading("Preliminary Scope for Salus Review", level=1)
    document.add_paragraph(
        "A Salus professional should confirm the Protected Member's objectives, operating "
        "environment, authority, evidence, facilities, dependencies, handling requirements, "
        "desired outcomes, schedule, and resource constraints before finalizing an engagement."
    )
    _add_bullets(document, (
        "Validate questionnaire responses and resolve material information gaps.",
        "Map essential functions to people, facilities, technology, utilities, suppliers, partners, and public services.",
        "Establish measurable capability targets and compare them with demonstrated current capability.",
        "Prioritize practical corrective actions, owners, dependencies, costs, and validation measures.",
        "Define training, exercise, assurance, reassessment, and continuing-improvement requirements.",
    ))
    document.add_heading("Proposed Deliverables", level=1)
    _add_table(document, ("Deliverable", "Purpose"), (
        ("Validated assessment record", "Separates verified facts, reported conditions, inferences, and unknowns"),
        ("Capability and dependency map", "Shows essential functions, supporting resources, failure points, and alternates"),
        ("Prioritized improvement plan", "Identifies actions, owners, sequence, dependencies, and completion measures"),
        ("Exercise and validation plan", "Tests priority capabilities and creates defensible performance evidence"),
        ("Executive briefing", "Presents decisions, risks, resource implications, and recommended next steps"),
    ), widths=(2.35, 4.05))

    document.add_heading("Human Review and Decision Points", level=1)
    document.add_paragraph(
        "No automated recommendation becomes a final scope, assurance statement, price, contract commitment, "
        "or protective decision without authorized Salus review. The reviewer confirms service selection, "
        "level, specialists, deliverables, schedule, pricing basis, handling controls, and eligibility."
    )
    document.add_heading("Recommended Immediate Actions", level=1)
    _add_table(document, ("Timing", "Action", "Responsible party"), (
        ("Now", "Assign an authorized Salus reviewer and confirm secure handling.", "Salus"),
        ("Within 5 business days", "Conduct a qualification and validation interview.", "Salus and Protected Member"),
        ("After interview", "Request only the evidence needed to resolve priority findings and gaps.", "Salus"),
        ("After evidence review", "Confirm or revise service sequence, scope, level, schedule, and specialists.", "Authorized Salus reviewer"),
        ("Before engagement", "Approve scope, commercial terms, information handling, and points of contact.", "Salus and Protected Member"),
    ), widths=(1.45, 3.35, 1.6))

    document.add_heading("Decision Required", level=1)
    document.add_paragraph(
        "The next decision is whether to authorize a Salus qualification and validation review. "
        "That review determines the appropriate package and evidence needed before work is proposed."
    )

    document.add_heading("Important Notice", level=1)
    document.add_paragraph(
        "This preliminary report is based on self-reported information and automated screening. "
        "It is not a certification or a legal, insurance, regulatory, engineering, medical, "
        "cybersecurity, or safety determination. Final conclusions require qualified Salus review."
    )

    document.add_page_break()
    document.add_heading("Appendix A Assessment Method", level=1)
    document.add_paragraph(
        "Protection Advisor screens reported conditions against 32 core capabilities across "
        "Prevention, Protection, Mitigation, Response, and Recovery. Scores and rankings organize "
        "professional review; they do not independently establish risk, compliance, or readiness."
    )
    document.add_heading("Interpretation Rules", level=2)
    _add_table(document, ("Element", "How it should be interpreted"), (
        ("Mission area score", "A screening indicator derived from reported conditions; not an audit grade"),
        ("Need score", "A relative priority within this submission; not probability or consequence"),
        ("Reported need", "A condition that may require improvement or validation"),
        ("Information gap", "An unknown that could alter findings, priorities, scope, or recommendations"),
        ("Service level", "A preliminary indication of engagement depth; subject to human review"),
    ), widths=(1.75, 4.65))
    document.add_heading("Quality and Evidence Principles", level=2)
    _add_bullets(document, (
        "Use current, relevant, traceable evidence and record its source, date, owner, and limitations.",
        "Test plans and controls under realistic stress, reduced staffing, degraded systems, and competing-resource conditions.",
        "Reassess when conditions, threats, facilities, leadership, dependencies, or evidence materially change.",
    ))

    document.add_page_break()
    document.add_heading("Appendix B Preliminary Service Rationale", level=1)
    document.add_paragraph(str(package.get("rationale") or "Service recommendations require Salus professional validation."))
    service_rows = []
    for service in package.get("services") or []:
        service_rows.append((service.get("title", "Service"), f"Level {service.get('level', '')}", service.get("why", "")))
    _add_table(document, ("Recommended service", "Level", "Preliminary rationale"), service_rows, widths=(2.25, .8, 3.35))
    document.add_heading("Limitations", level=2)
    document.add_paragraph(
        "This report does not contain enough validated evidence to support final findings about "
        "specific facilities, personnel, threats, controls, compliance, costs, schedules, or "
        "operational effectiveness. Those matters must be developed during professional review."
    )


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


def _apply_report_handling(document, requested_handling: str) -> None:
    """Adapt the approved Salus cover without asserting an unverified CUI designation."""
    display = "CUI review requested" if requested_handling == "CUI" else requested_handling
    watermark = "REVIEW" if requested_handling == "CUI" else requested_handling.upper()
    notice = (
        f"Requested handling: {display}. Salus must validate applicable distribution, "
        "records, and government information controls before formal release. "
        "Distribute this preliminary report only to authorized recipients."
    )
    substitutions = (
        ("CONFIDENTIALITY NOTICE and Controlled Unclassified Information (CUI):", "REPORT HANDLING NOTICE"),
        (
            "The contents of this document include information the Government or related entities",
            "This preliminary Salus report is prepared for the recipient identified on the cover. "
            "It describes self-reported conditions and is subject to professional review.",
        ),
        (
            "The contents of this document or email, including attachments, may also contain information that is CUI.",
            notice,
        ),
    )
    for paragraph in document.element.body.xpath(".//w:p"):
        nodes = paragraph.xpath(".//w:t")
        combined = "".join(node.text or "" for node in nodes)
        for prefix, replacement in substitutions:
            if combined.startswith(prefix) and nodes:
                nodes[0].text = replacement
                for node in nodes[1:]:
                    node.text = ""
                break

    for paragraph in document.sections[0].header._element.xpath(".//w:p"):
        nodes = paragraph.xpath(".//w:t")
        combined = "".join(node.text or "" for node in nodes)
        if "Controlled Unclassified Information (CUI)" in combined and nodes:
            nodes[0].text = f"---SALUS SOLUTIONS | PROTECTION ADVISOR | {display.upper()}---"
            for node in nodes[1:]:
                node.text = ""
    for element in document.sections[0].header._element.iter():
        if element.tag.endswith("}textpath") and element.get("string") == "CONFIDENTIAL":
            element.set("string", watermark)


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

    _apply_report_handling(document, fields["InformationClassificationHandling"])

    cover_section = document.sections[0]
    # Capture the source story parts before creating any new section. Accessing a
    # new section's linked header/footer can change which part python-docx
    # resolves for earlier sections; retaining these handles preserves embedded
    # image relationships when the template footer is copied.
    cover_header_part = cover_section.header.part
    cover_footer_part = cover_section.footer.part
    cover_header = deepcopy(cover_section.header._element)
    cover_footer = deepcopy(cover_section.footer._element)

    blank_section = document.add_section(WD_SECTION.CONTINUOUS)
    # The intentionally blank second page retains only the template's light
    # CONFIDENTIAL watermark; it has no visible header text or footer.
    _replace_story(blank_section.header, cover_header, cover_header_part)
    _clear_story(blank_section.footer)

    results_section = document.add_section(WD_SECTION.NEW_PAGE)
    _replace_story(results_section.header, cover_header, cover_header_part)
    _replace_story(results_section.footer, cover_footer, cover_footer_part)

    try:
        result = json.loads(part1_text)
        package = json.loads(part2_text)
    except (TypeError, json.JSONDecodeError):
        # Preserve the original renderer contract for controlled callers that
        # supply already-written narrative instead of model JSON. The text is
        # placed inside the professional architecture, never emitted as a raw
        # questionnaire or serialized export.
        result = {
            "recommendation": "Professional review recommended",
            "strength_count": 0,
            "attention_count": 1,
            "information_gap_count": 0,
            "core_capabilities_considered": 32,
            "mission_area_scores": {},
            "priority_capabilities": [],
            "attention_topics": [part1_text.strip()],
            "information_gaps": [],
        }
        package = {
            "primary_service": {
                "title": "Protection Advisor Professional Review",
                "level": 1,
                "level_name": "Initial Pass",
                "summary": part2_text.strip(),
                "why": "The supplied preliminary narrative requires authorized Salus validation.",
            },
            "sequence": ["Protection Advisor Professional Review"],
            "later_phase_services": [],
            "services": [],
            "rationale": part2_text.strip(),
        }
    if not isinstance(result, dict) or not isinstance(package, dict):
        raise ValueError("Protection Advisor report content must be structured objects")
    _professional_body(document, fields, result, package)

    destination.parent.mkdir(parents=True, exist_ok=True)
    document.save(str(destination))
    return destination


def render_protection_advisor_pdf(
    *,
    output_path: str | os.PathLike[str],
    context: ProtectionAdvisorReportContext,
    result: dict,
    package: dict,
) -> Path:
    """Render the participant PDF from the same governed assessment objects."""
    try:
        from reportlab.lib import colors
        from reportlab.lib.enums import TA_CENTER, TA_LEFT
        from reportlab.lib.pagesizes import letter
        from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
        from reportlab.lib.units import inch
        from reportlab.lib.utils import ImageReader
        from reportlab.pdfbase import pdfmetrics
        from reportlab.pdfbase.ttfonts import TTFont
        from reportlab.pdfgen.canvas import Canvas
        from reportlab.platypus import (
            BaseDocTemplate, Frame, KeepTogether, PageBreak, PageTemplate,
            Paragraph, Spacer, Table, TableStyle,
        )
    except ImportError as exc:
        raise RuntimeError("reportlab is required for Protection Advisor PDF reports") from exc

    destination = Path(output_path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    font_dir = Path("/usr/share/fonts/truetype/dejavu")
    for font_name, filename in (("SalusSans", "DejaVuSans.ttf"), ("SalusSans-Bold", "DejaVuSans-Bold.ttf")):
        font_path = font_dir / filename
        if not font_path.is_file():
            raise RuntimeError(f"Required embedded report font is missing: {font_path}")
        pdfmetrics.registerFont(TTFont(font_name, str(font_path)))
    template_path = Path(__file__).with_name(_TEMPLATE_NAME)
    if not template_path.is_file():
        raise RuntimeError(f"Approved Salus report template is missing: {template_path}")
    with zipfile.ZipFile(template_path) as template:
        logo_image = ImageReader(io.BytesIO(template.read("word/media/image1.png")))
    fields = context.as_template_fields()
    requested_handling = fields["InformationClassificationHandling"]
    display_handling = "CUI review requested" if requested_handling == "CUI" else requested_handling
    watermark = "CONFIDENTIAL"
    styles = getSampleStyleSheet()
    body = ParagraphStyle("SalusBody", parent=styles["BodyText"], fontName="SalusSans", fontSize=11.5, leading=16, spaceAfter=9)
    h1 = ParagraphStyle("SalusH1", parent=styles["Heading1"], fontName="SalusSans-Bold", fontSize=17, leading=21, textColor=colors.black, spaceBefore=13, spaceAfter=9)
    h2 = ParagraphStyle("SalusH2", parent=styles["Heading2"], fontName="SalusSans-Bold", fontSize=12, leading=16, textColor=colors.black, spaceBefore=9, spaceAfter=6)
    title = ParagraphStyle("SalusTitle", parent=styles["Title"], fontName="SalusSans-Bold", fontSize=22, leading=26, alignment=TA_CENTER, textColor=colors.black)
    subtitle = ParagraphStyle("SalusSubtitle", parent=body, fontSize=11, leading=14, alignment=TA_CENTER, textColor=colors.HexColor("#2F75B5"))
    small = ParagraphStyle("SalusSmall", parent=body, fontSize=10, leading=13, spaceAfter=0)
    table_header = ParagraphStyle(
        "SalusTableHeader", parent=small, fontName="SalusSans-Bold",
        fontSize=9.5, leading=12, textColor=colors.white, alignment=TA_LEFT,
    )

    def P(text, style=body):
        return Paragraph(str(text or "").replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;"), style)

    def T(headers, rows, widths, *, centered_columns=()):
        """Build a compact table with semantic alignment and stable header spacing."""
        data = [[P(value, table_header) for value in headers]] + [[P(value, small) for value in row] for row in rows]
        table = Table(data, colWidths=widths, repeatRows=1, hAlign="CENTER")
        commands = [
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#17365D")),
            ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
            ("FONTNAME", (0, 0), (-1, 0), "SalusSans-Bold"),
            ("ALIGN", (0, 0), (-1, -1), "LEFT"),
            ("VALIGN", (0, 0), (-1, 0), "MIDDLE"),
            ("VALIGN", (0, 1), (-1, -1), "TOP"),
            ("GRID", (0, 0), (-1, -1), .35, colors.HexColor("#D9E1E8")),
            ("ROWBACKGROUNDS", (0, 1), (-1, -1), (colors.white, colors.HexColor("#F5F8FA"))),
            ("LEFTPADDING", (0, 0), (-1, -1), 5), ("RIGHTPADDING", (0, 0), (-1, -1), 5),
            ("TOPPADDING", (0, 0), (-1, 0), 5), ("BOTTOMPADDING", (0, 0), (-1, 0), 5),
            ("TOPPADDING", (0, 1), (-1, -1), 4), ("BOTTOMPADDING", (0, 1), (-1, -1), 4),
        ]
        for column in centered_columns:
            commands.append(("ALIGN", (column, 0), (column, -1), "CENTER"))
            data[0][column].style = ParagraphStyle(
                f"SalusTableHeaderCenter{column}", parent=table_header, alignment=TA_CENTER
            )
        table.setStyle(TableStyle(commands))
        return table

    def bullets(items):
        return [P("- " + str(item), body) for item in items]

    class NumberedCanvas(Canvas):
        """Write a real total page count after Platypus has laid out the story."""

        def __init__(self, *args, **kwargs):
            super().__init__(*args, **kwargs)
            self._page_states = []

        def showPage(self):
            self._page_states.append(dict(self.__dict__))
            self._startPage()

        def save(self):
            total = len(self._page_states)
            for state in self._page_states:
                self.__dict__.update(state)
                self.saveState()
                self.setFillAlpha(1)
                number = self._pageNumber
                width, height = letter
                if number == 2:
                    self.setFillColor(colors.Color(.4, .4, .4, alpha=.10))
                    self.setFont("SalusSans-Bold", 52)
                    self.translate(width / 2, height / 2)
                    self.rotate(45)
                    self.drawCentredString(0, 0, watermark)
                else:
                    if number >= 3:
                        self.setFillColor(colors.HexColor("#7A1F1F"))
                        self.setFont("SalusSans", 7.5)
                        self.drawCentredString(width / 2, height - .42 * inch, "CONFIDENTIAL — SALUS PROTECTED INFORMATION")
                        self.setFillColor(colors.Color(.4, .4, .4, alpha=.07))
                        self.setFont("SalusSans-Bold", 46)
                        self.translate(width / 2, height / 2)
                        self.rotate(45)
                        self.drawCentredString(0, 0, watermark)
                        self.rotate(-45)
                        self.translate(-width / 2, -height / 2)
                    draw_brand_footer(self)
                    self.setFillAlpha(1)
                    self.setFillColor(colors.black)
                    self.setFont("SalusSans", 8)
                    self.drawRightString(width - .65 * inch, .30 * inch, f"Page {number} of {total}")
                self.restoreState()
                super().showPage()
            super().save()

    def draw_brand_footer(canvas):
        # The watermark uses transparency; explicitly restore opaque graphics
        # before drawing the template's black logo and footer text.
        canvas.setFillAlpha(1)
        canvas.drawImage(logo_image, .65 * inch, .25 * inch,
                         width=1.65 * inch, height=.25 * inch,
                         preserveAspectRatio=True, mask="auto")
        canvas.setFillColor(colors.black)
        canvas.setFont("SalusSans", 8)
        canvas.drawString(2.75 * inch, .30 * inch, "+1-888-496-6668")
        canvas.drawString(4.22 * inch, .30 * inch, "www.Salus.Solutions")

    def page_frame(canvas, doc):
        canvas.setTitle("Protection Advisor Assessment Report")
        canvas.setAuthor("Salus Solutions")

    doc = BaseDocTemplate(str(destination), pagesize=letter, leftMargin=.7 * inch, rightMargin=.7 * inch, topMargin=.7 * inch, bottomMargin=.65 * inch, lang="en-US")
    frame = Frame(doc.leftMargin, doc.bottomMargin, doc.width, doc.height, id="body")
    doc.addPageTemplates(PageTemplate(id="Salus", frames=(frame,), onPage=page_frame))
    story = [Spacer(1, .45 * inch), P("SALUS SOLUTIONS", subtitle), Spacer(1, .08 * inch),
             P("Protection Advisor Assessment Report", title), P("Preliminary results and recommended protection package", subtitle), Spacer(1, .25 * inch)]
    story.append(T(("Report detail", "Value"), (
        ("Protected Member code name", fields["ClientCodeName"]), ("Project code name", fields["ProjectCodeName"]),
        ("Report reference", fields["ReportReference"]), ("Prepared", fields["GeneratedAt"]),
        ("Handling", display_handling),
    ), (2.0 * inch, 4.1 * inch)))
    story += [Spacer(1, .22 * inch), P("Report handling notice", h1),
              P(f"Requested handling: {display_handling}. Salus must validate applicable distribution, records, and government information controls before formal release. Distribute this preliminary report only to authorized recipients."),
              Spacer(1, .12 * inch), P("SALUS PROFESSIONAL REVIEW REQUIRED", subtitle), PageBreak(), Spacer(1, 8.5 * inch), PageBreak()]

    capabilities = result.get("priority_capabilities") or []
    scores = result.get("mission_area_scores") or {}
    primary = package.get("primary_service") or {}
    priority_names = [str(item.get("capability", "")).strip() for item in capabilities[:6]]
    priority_names = [name for name in priority_names if name]
    sequence = [str(item).strip() for item in (package.get("sequence") or []) if str(item).strip()]
    story += [P("Protection Advisor Assessment Report", h1), P("Preliminary results and recommended protection package", subtitle),
              T(("Report detail", "Value"), (
                  ("Protected Member code name", fields["ClientCodeName"]),
                  ("Project code name", fields["ProjectCodeName"]),
                  ("Report reference", fields["ReportReference"]),
                  ("Prepared", fields["GeneratedAt"]),
                  ("Handling", display_handling),
                  ("Status", "Preliminary - Salus professional review required"),
              ), (2.0 * inch, 4.1 * inch)),
              P("Executive Summary", h1),
              P(f"The assessment recorded {result.get('strength_count', 0)} positive indicators; "
                f"{result.get('attention_count', 0)} conditions require attention and "
                f"{result.get('information_gap_count', 0)} material information gaps prevent a final "
                "determination of readiness. The results support one connected review of protection, "
                "preparedness, continuity, response, and recovery."),
              P(("The highest preliminary capability priorities are " + ", ".join(priority_names) + ". "
                 "They identify where professional validation should begin across the five mission areas; "
                 "they do not establish a confirmed deficiency or threat.") if priority_names else
                "The preliminary capability priorities require Salus professional validation against current evidence."),
              P(f"Salus recommends beginning with {primary.get('title', 'a qualification and validation review')} "
                f"at Level {primary.get('level', '')} {primary.get('level_name', '')}. "
                f"{primary.get('summary', '')} "
                + ("The proposed sequence continues with " + "; ".join(sequence[1:4]) + ". "
                   if len(sequence) > 1 else "")
                + "The sequence remains preliminary until Salus validates the operating environment, "
                  "evidence, authorities, resources, and priorities."),
              PageBreak(), P("Assessment Snapshot", h1),
              T(("Measure", "Result", "Interpretation"), (
                  ("Overall result", result.get("recommendation", "Professional review recommended"), "Preliminary decision-support result"),
                  ("Positive indicators", result.get("strength_count", 0), "Reported practices that may support improvement"),
                  ("Conditions requiring attention", result.get("attention_count", 0), "Potential gaps or unvalidated capability"),
                  ("Information gaps", result.get("information_gap_count", 0), "Unknowns that could change conclusions"),
                  ("Core capabilities", result.get("core_capabilities_considered", 32), "Evaluated across five mission areas"),
              ), (1.75 * inch, 1.45 * inch, 2.9 * inch), centered_columns=(1,)),
              P("Mission Area Profile", h1),
              T(("Mission area", "Score", "Preliminary interpretation"), tuple((a, f"{int(scores.get(a, 0))} / 100", "Relative strength" if int(scores.get(a, 0)) >= 60 else "Moderate concern" if int(scores.get(a, 0)) >= 50 else "Priority concern") for a in ("Prevention", "Protection", "Mitigation", "Response", "Recovery")), (1.8 * inch, 1.15 * inch, 3.15 * inch), centered_columns=(1,)),
              P("Primary Conclusions", h1)]
    story += bullets(("Treat protection, emergency planning, continuity, and capability validation as one integrated program.", "Test reported capability against current evidence and performance under realistic stress.", "Validate authority, succession, escalation, dependencies, and alternate arrangements.", "Require authorized Salus review before final scope, price, or assurance statements."))
    story += [PageBreak(), P("Priority Capability Findings", h1),
              T(("Priority", "Capability", "Need", "Mission areas", "Basis"), tuple((i, x.get("capability", ""), x.get("need_score", ""), ", ".join(x.get("mission_areas") or []), "Information incomplete" if x.get("information_gap") else "Reported need") for i, x in enumerate(capabilities, 1)), (.8 * inch, 1.85 * inch, .55 * inch, 1.65 * inch, 1.25 * inch), centered_columns=(0, 2)),
              P("Need scores rank review urgency within this submission. They are not probability estimates, compliance findings, or final measures of readiness."), P("Conditions Requiring Attention", h1)]
    story += bullets(result.get("attention_topics") or ("No specific attention topic was preserved in this preliminary record.",))
    story += [PageBreak(), P("Information Gaps", h1), P("These issues could materially change the assessment and should be resolved before a final opinion, scope, or price is issued.")]
    story += bullets(result.get("information_gaps") or ("Professional validation remains required.",))
    story += [P("Evidence Needed", h1)] + bullets(("Current emergency, continuity, communications, security, and recovery plans.", "Authority, succession, delegation, notification, and escalation records.", "Essential-function, dependency, vendor, utility, and restoration-priority information.", "Training, exercise, incident, corrective-action, maintenance, and inspection records.", "Relevant interviews, demonstrations, observations, and current performance evidence."))
    hypothesis = result.get("preliminary_hypothesis") or {}
    if hypothesis:
        story.append(P("Preliminary Working Hypothesis and Level 1 Action", h2))
        for key in ("reported_basis", "working_assumption", "level_1_action"):
            if hypothesis.get(key):
                story.append(P(str(hypothesis[key])))
        story += bullets(hypothesis.get("checklist") or ())
    story += [PageBreak(), P("Recommended Protection Package", h1), P(f"The preliminary lead engagement is {primary.get('title', 'Professional Review')} - Level {primary.get('level', '')} {primary.get('level_name', '')}. {primary.get('summary', '')}"), P("Why this leads the package. " + str(primary.get("why", ""))), P("Recommended Sequence", h1), T(("Phase", "Service", "Purpose"), _sequence_rows(package), (.65 * inch, 2.45 * inch, 3.0 * inch), centered_columns=(0,)), P("Additional Later Phase Services", h1)]
    for service in package.get("later_phase_services") or []:
        story.append(P(f"{service.get('title', 'Service')} - Level {service.get('level', '')} {service.get('level_name', '')}. {service.get('summary', '')}"))
    story += [PageBreak(), P("Preliminary Scope for Salus Review", h1), P("A Salus professional should validate the Protected Member's objectives, operating environment, authorities, evidence, facilities, dependencies, handling requirements, desired outcomes, schedule, and resources before finalizing an engagement."), P("Proposed Deliverables", h1), T(("Deliverable", "Purpose"), (("Validated assessment record", "Separates verified facts, reported conditions, inferences, and unknowns"), ("Capability and dependency map", "Shows essential functions, supporting resources, failure points, and alternates"), ("Prioritized improvement plan", "Identifies actions, owners, sequence, dependencies, and completion measures"), ("Exercise and validation plan", "Tests priority capabilities and creates defensible evidence"), ("Executive briefing", "Presents decisions, risks, resource implications, and next steps")), (2.2 * inch, 3.9 * inch)), P("Human Review and Decision Points", h1), P("No automated recommendation becomes a final scope, assurance statement, price, contract commitment, or protective decision without authorized Salus review. The reviewer confirms service selection, level, specialists, deliverables, schedule, pricing basis, handling controls, and eligibility."), P("Recommended Immediate Actions", h1), T(("Timing", "Action", "Responsible party"), (("Now", "Assign an authorized Salus reviewer and confirm secure handling.", "Salus"), ("Within 5 business days", "Conduct a qualification and validation interview.", "Salus and Protected Member"), ("After interview", "Request only evidence needed to resolve priority findings and gaps.", "Salus"), ("After evidence review", "Confirm or revise sequence, scope, level, schedule, and specialists.", "Authorized Salus reviewer"), ("Before engagement", "Approve scope, commercial terms, handling, and points of contact.", "Salus and Protected Member")), (1.3 * inch, 3.35 * inch, 1.45 * inch)), P("Decision Required", h1), P("The next decision is whether to authorize a Salus qualification and validation review. That review determines the appropriate package and evidence needed before work is proposed."), P("Important Notice", h1), P("This preliminary report is based on self-reported information and automated screening. It is not a certification or a legal, insurance, regulatory, engineering, medical, cybersecurity, or safety determination. Final conclusions require qualified Salus review."), PageBreak(), P("Appendix A Assessment Method", h1), P("Protection Advisor screens reported conditions against 32 core capabilities across Prevention, Protection, Mitigation, Response, and Recovery. Scores and rankings organize professional review; they do not independently establish risk, compliance, or readiness."), P("Interpretation Rules", h2), T(("Element", "How it should be interpreted"), (("Mission area score", "Screening indicator; not an audit grade"), ("Need score", "Relative priority; not probability or consequence"), ("Reported need", "Condition that may require improvement or validation"), ("Information gap", "Unknown that could alter findings, priorities, or scope"), ("Service level", "Preliminary engagement depth; subject to human review")), (1.6 * inch, 4.5 * inch)), PageBreak(), P("Appendix B Preliminary Service Rationale", h1), P(package.get("rationale") or "Service recommendations require Salus professional validation."), T(("Recommended service", "Level", "Preliminary rationale"), tuple((x.get("title", "Service"), f"Level {x.get('level', '')}", x.get("why", "")) for x in package.get("services") or []), (2.05 * inch, .8 * inch, 3.25 * inch), centered_columns=(1,)), P("Limitations", h2), P("This report does not contain enough validated evidence to support final findings about specific facilities, personnel, threats, controls, compliance, costs, schedules, or operational effectiveness.")]
    doc.build(story, canvasmaker=NumberedCanvas)
    return destination
