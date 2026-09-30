"""One-time revision of four local review copies without new identities.

The source files are held in the parent work directory. Candidate output is
rendered and reviewed before replacement. The originals have since been
replaced, so rerunning this helper safely fails on its old-version assertions.
This helper never touches sources/.
"""

from pathlib import Path

from docx import Document
from docx.shared import Pt


ROOT = Path(__file__).resolve().parents[3]
OUT = Path(__file__).resolve().parent / "questionnaire_candidates"
OUT.mkdir(exist_ok=True)


def replace(paragraphs, old: str, new: str) -> None:
    matching = [p for p in paragraphs if old in p.text]
    if len(matching) != 1:
        raise ValueError(f"Expected one matching paragraph for {old!r}; got {len(matching)}")
    p = matching[0]
    if len(p.runs) == 1:
        p.runs[0].text = p.runs[0].text.replace(old, new)
    else:
        # In these review copies the matched sentences are plain Normal text.
        p.text = p.text.replace(old, new)


def add_before(anchor, text: str, style: str = "Normal") -> None:
    p = anchor.insert_paragraph_before(text, style=style)
    p.paragraph_format.keep_together = True


def apply_fonts(doc) -> None:
    for style_name in ("Normal", "List Bullet"):
        if style_name in doc.styles:
            doc.styles[style_name].font.name = "Times New Roman"
            doc.styles[style_name].font.size = Pt(11)
    for style_name in ("Title", "Heading 1", "Heading 2", "Heading 3"):
        if style_name in doc.styles:
            doc.styles[style_name].font.name = "Arial"


def save(name: str, fn) -> None:
    source = ROOT / name
    doc = Document(source)
    fn(doc)
    apply_fonts(doc)
    doc.save(OUT / name)


def part1(doc) -> None:
    replace(doc.paragraphs, "SPA-PUBLIC-QUESTIONNAIRE-2.0.0", "SPA-PUBLIC-QUESTIONNAIRE-2.2.0")
    replace(doc.paragraphs, "28 September 2026", "29 September 2026")
    doc.add_heading("What happens after this screen", level=1)
    doc.add_paragraph(
        "Your answers can identify possible strengths, concerns and missing information. "
        "They do not establish readiness or compliance. If you choose to continue, Part 2 helps "
        "Salus understand the operation you want assessed and suggest a starting Level 1 package path."
    )
    doc.add_paragraph(
        "Salus begins paid assessment work only after it confirms the boundary, eligibility, "
        "fee and schedule in writing and receives authorization. A qualified Level 1 package "
        "contains separate SalINTEL™, SalTHIRA™, SalOPS™ and SalCAPA™ reports. "
        "Optional Salus services require their own scope and approval."
    )


def part2(doc) -> None:
    replace(doc.paragraphs, "28 September 2026", "29 September 2026")
    replace(doc.paragraphs, "Detailed organization profile | current live field set for review",
            "Scope and readiness profile | SPA-PUBLIC-QUESTIONNAIRE-2.2.0 | working review copy")
    anchor = next(p for p in doc.paragraphs if p.text.startswith("Personnel range:"))
    for text in (
        "Operation or function you want assessed (optional for now):  _________________________________________________",
        "Examples: one daycare site; warehouse only; two lumber yards. This is a proposed boundary, not an approved scope.",
        "How many operations need their own decision?  _________________________________________________",
        "Choices: Not sure yet; One combined operation; Two named sites or operations; A group needing shared priorities",
        "Will different sites or activities need separate findings and a comparison?  _________________________________________________",
        "Choices: Not sure yet; No, one combined set of findings; Yes, separate findings and a comparison",
        "Must leadership rank investments across a group of sites or activities?  _________________________________________________",
        "Choices: Not sure yet; No; Yes",
        "These answers suggest a starting band. Salus confirms the covered boundary and price in writing before work begins.",
    ):
        add_before(anchor, text)
    doc.add_heading("Your possible Level 1 path", level=1)
    doc.add_paragraph(
        "One combined decision may point to Band A; two distinct findings and a comparison may "
        "point to Band B; group priorities may point to Band C. These are provisional suggestions. "
        "Salus checks the actual boundary and complexity before quoting. Revenue and personnel "
        "count alone do not set the band."
    )
    doc.add_paragraph(
        "Level 1A Access is $1,500 only when Salus confirms a simple eligible scope. "
        "Level 1A Standard and all other bands receive a written price after scope review. "
        "The written agreement sets start and delivery dates after Salus confirms capacity "
        "and receives authorization."
    )
    doc.add_paragraph(
        "Your draft scope receipt names the requested operation and location, possible path, "
        "records to prepare, price and schedule status, decision role, five steps and your "
        "choices. It is not a quote or authorization. After agreement, Salus requests the "
        "minimum relevant records through an approved secure channel."
    )


def intake(doc) -> None:
    replace(doc.paragraphs, "27 September 2026", "29 September 2026")
    replace(doc.paragraphs, "Level 1 Initial Pass", "Level 1 package")
    doc.add_heading("Approved package path and staged request", level=1)
    doc.add_paragraph(
        "Part 1 remains an anonymous educational screen with no upload. Part 2 asks for a "
        "preliminary decision boundary and does not collect the assessment packet. The "
        "Member receives a draft scope receipt. Salus validates the band, Access eligibility, "
        "fixed fee, dates, handling and authorized decision owner in a written agreement "
        "before paid work or document transfer."
    )
    doc.add_paragraph(
        "The initial Level 1 request is a short organization chart with reporting lines, "
        "decision authority and role responsibilities; covered-site or function map if "
        "available; current emergency or continuity plan; recent incident summary; and "
        "critical utility and supplier list. The Member may mark an item unavailable. "
        "Request sector-specific records only when justified by the agreed boundary. "
        "Do not request personal directories by default."
    )


def member_request(doc) -> None:
    replace(doc.paragraphs, "28 September 2026", "29 September 2026")
    replace(doc.paragraphs, "A. Needed to scope and begin Level 1", "A. Confirm scope and authority before document transfer")
    replace(doc.paragraphs,
            "Send a short scope and authority package first. A Salus lead will specify the secure channel and request only material records needed for Level 1.",
            "First give brief descriptions of the requested unit, authority, essential work and main concerns; do not send files at this stage. Confirm Access eligibility, fixed fee, schedule, handling and secure channel in a written agreement. Salus then requests only material records needed for that Level 1 boundary.")
    replace(doc.paragraphs,
            "B. Provide when available; identify missing or outdated records",
            "B. After agreement provide available records in stages")
    anchor = next(p for p in doc.paragraphs if p.text == "Risk and compliance")
    add_before(anchor, "First packet after agreement", "Heading 2")
    add_before(anchor,
               "Begin with an organization chart showing reporting lines, decision authority and role responsibilities; "
               "an available site or function map; the current emergency or continuity plan; a recent incident summary; "
               "and a critical utility and supplier list. Mark missing items unavailable. Salus will request further "
               "records only when justified by the agreed boundary and findings.")
    doc.add_heading("Package and privacy rule", level=1)
    doc.add_paragraph(
        "The signed Level 1 package produces separate SalINTEL™, SalTHIRA™, SalOPS™ and SalCAPA™ reports "
        "for the named unit. A Level 2 visit or interview program requires a qualified Level 1 result and a "
        "new agreement; Level 3 specialist work requires a qualified Level 2 result and separate scope. "
        "Do not provide personal directories, medical records, credentials or individual background files by default."
    )


if __name__ == "__main__":
    save("Protection Advisor Part 1 Questionnaire.docx", part1)
    save("Protection Advisor Part 2 Questionnaire.docx", part2)
    save("Protection_Advisor_Level_1_Intake_Revision_DRAFT.docx", intake)
    save("Salus_Level_1_Protected_Member_Information_Request_DRAFT.docx", member_request)
    print(OUT)
