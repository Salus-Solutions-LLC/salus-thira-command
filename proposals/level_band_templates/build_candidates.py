"""Make narrow member-neutral title candidates from the four retained Word templates."""

from hashlib import sha256
from pathlib import Path
from zipfile import ZipFile
from html import escape, unescape
import re

HERE = Path(__file__).resolve().parent
WORK = HERE.parents[2]

# These instructions travel with the relevant substantive section, rather
# than relying on a cover label to communicate the selected commercial path.
SECTION_RULES = {
    "SalINTEL": {
        "[State authorized service level, site and asset boundary": "For A, qualify one integrated decision unit. For B, give separate findings for each named unit and identify shared versus different evidence. For C, qualify each included unit before stating a group finding and resource implication.",
        "[Describe location and jurisdiction, ownership/control": "Record the legal entity, actual activity, shifts and affected people for every included unit; never extend a site-only conclusion to excluded operations.",
        "[Screen natural, accidental, operational and relevant intentional conditions": "Level 1 uses source-qualified scenarios; Level 2 tests named decision-changing claims through authorized visits, interviews and records; Level 3 identifies only separately approved specialist or exercise proof.",
        "[Describe authorities, plans, people, equipment": "For Access, keep the full 32-capability applicability screen and five mission areas within the bounded unit. For B/C, retain unit-specific capability evidence before comparing or aggregating it.",
        "[Create member-specific numbered questions": "Label every request as included current-level work or a proposed next-level collection item; give its decision effect, custodian and evidence limit so missing records do not silently become an upgrade.",
    },
    "SalTHIRA": {
        "[Define member, facilities, population and essential functions": "A names one integrated unit; B compares named units; C ranks a defined group's priorities. State every exclusion.",
        "[List credible human-caused, natural, technological": "Level 1A Access retains two decision-driving scenarios without suppressing high-consequence screening.",
        "[Compare demonstrated capacity against targets": "A ranks one unit's gap; B compares unit gaps; C ranks group resource choices. Self-report is not tested capacity.",
    },
    "SalOPS": {
        "[State requested, authorized and completed level": "Use the exact covered boundary from the same-level SalINTEL and SalTHIRA versions; newly added units require their own qualified Level 1 extension first.",
        "[Connect each option to a SalTHIRA scenario": "A produces one coordinated action set. B identifies shared and unit-specific work. C sequences group priorities and scarce resources; none implies that Salus has performed an unapproved service.",
        "[For each option record ID, source gap": "Include the Member alternative, separate-service quote status and a measurable closure test for every material option; Access retains the same qualified recommendation floor.",
        "[State deferred/rejected options, residual risk owner": "Name exactly what the optional next level would validate, its predecessor and the Member decision it could change; a Level 1 action may proceed without buying Level 2.",
    },
    "SalCAPA": {
        "[Protected Member, assets and functions, requested/authorized/completed level": "Show the exact paid path, all included and excluded units, Access eligibility or Standard quote, and separately confirmed fee; do not infer enterprise coverage from one unit.",
        "[Reconcile changed dates, boundaries, classifications": "Reconcile the same stable decision ID and exact source-report versions across all four products before presenting a Member choice; a missing or unqualified predecessor remains pending.",
        "[Explain verified strengths, observed events, vulnerabilities": "For A explain the integrated unit; for B compare shared and distinct findings; for C show how the named group's priorities and resource tradeoffs were determined.",
        "[Summarize immediate safety matters, options offered": "Distinguish recommended, Member-authorized, Salus-performed and independently verified work; separately quoted services are never shown as completed by the assessment.",
        "[For each unresolved consequential question": "State the exact prior-level finding, field or specialist proof proposed, included boundary, separate authority and decision value before presenting an optional next level.",
    },
}


def add_section_rules(xml: str, product: str) -> str:
    for anchor, rule in SECTION_RULES[product].items():
        matches = []
        for paragraph in re.finditer(r'<w:p(?:\s[^>]*)?>.*?</w:p>', xml, flags=re.S):
            runs = list(re.finditer(r'<w:t(?:\s[^>]*)?>(.*?)</w:t>', paragraph.group(), flags=re.S))
            content = ''.join(unescape(run.group(1)) for run in runs)
            if anchor in content:
                matches.append((paragraph, runs))
        assert len(matches) == 1, (product, anchor, len(matches))
        paragraph, runs = matches[0]
        assert runs, (product, anchor)
        last = runs[-1]
        inner = paragraph.group()
        append_at = last.end(1)
        inner = inner[:append_at] + escape(f' [Path-specific authoring: {rule}]', quote=False) + inner[append_at:]
        xml = xml[:paragraph.start()] + inner + xml[paragraph.end():]
    return xml

SPECS = {
    "SalINTEL": (
        WORK / "approved_templates/SalINTEL Report Template.docx",
        "5A99C3F0A3DB126F101407617AABA7CB8EB098C3D704E436B01C5D8520BB1959",
        {
            "SalINTEL™ Facility Assessment — [Level 1 / Level 2 / Level 3]": "[Protected Member customer name] - SalINTEL Level [path]",
            "Approved sequential-package report template | Version 1.0 | 27 September 2026": "Level and band template candidate 1.3 | 1 October 2026 | SAL-D088–D090",
            "Status: approved member-neutral report template.": "Status: member-neutral candidate derived from approved template v1.0.",
            "This is the Level __ SalINTEL report, with working/qualified/issued and prerequisite status.": "This is the Level [path] SalINTEL report for [covered operation and included/excluded units], with working/qualified/issued and prerequisite status. Identify A as one integrated decision unit, B as separately analyzed units or operating profiles with a comparison, or C as a named group with group priorities. For Level 1A distinguish Access from Standard; Access includes two decision-driving scenarios and the full qualified four-report sequence at the selected price when eligible. State the specific Member decision enabled, what was actually examined, proof limits, exclusions, and the next optional step. Do not imply field validation at Level 1, specialist assurance at Level 2, or implementation services in the assessment fee.",
        },
    ),
    "SalTHIRA": (
        WORK / "approved_templates/SalTHIRA Report Template.docx",
        "29B896804C44B56D5A32BA377FE557B676649FAC88C83D674BE77EA088B81FF8",
        {
            "[Protected Member customer name] - SalTHIRA Level [1, 2, or 3]": "[Protected Member customer name] - SalTHIRA Level [path]",
            "Controlled template version 1.0 | 27 September 2026": "Level and band candidate 1.3 | 1 October 2026",
            "Bottom Line Up Front (BLUF) - Level [1, 2, or 3] ranked judgment": "Bottom Line Up Front (BLUF) - Level [path] ranked judgment",
            "state the represented level, package status, ranked priorities": "state the exact level and band, covered operation and exclusions, package status, ranked priorities",
            "Explain the member mission, leading risks, current capability, recovery posture, same-level SalOPS options, and what Level 2 or Level 3 would validate.": "Explain the member mission, leading risks, current capability, recovery posture, decision enabled by this path and same-level SalOPS options. For A assess one integrated decision unit; for B compare separately analyzed units or operating profiles; for C rank the named group's priorities. Distinguish Level 1 source-bound judgment from Level 2 field validation and Level 3 authorized specialist proof. State what remains uncertain and what the next optional level would change.",
        },
    ),
    "SalOPS": (
        WORK / "salops_design/SalOPS Report Template DRAFT.docx",
        "4CE3DB45CA2C39BF28D278296D23CCEC322AC4E7738793D95B7170EC12170043",
        {
            "[Protected Member customer name] - SalOPS Level [1, 2, or 3]": "[Protected Member customer name] - SalOPS Level [path]",
            "Member-neutral working report template | 27 September 2026": "Level and band template candidate 1.3 | 1 October 2026 | SAL-D088–D090",
            "State the represented level, package and predecessor-report status.": "State the exact level and band, covered operation and exclusions, package and predecessor-report status. For A name the one integrated decision unit; for B distinguish shared and unit-specific actions; for C rank group-wide resource choices. State which options support this level's findings, which implementation help requires a separate quote and authorization, and what evidence would justify the next optional level.",
        },
    ),
    "SalCAPA": (
        WORK / "salcapa_report_design/SalCAPA Integrated Report Template DRAFT.docx",
        "A1FAE0F2187C0B7DE74246DE70203B6F40F172434BC197127EF30E907153D3A1",
        {
            "[Protected Member customer name] - SalCAPA Level [1, 2, or 3]": "[Protected Member customer name] - SalCAPA Level [path]",
            "Integrated decision summary working template | 27 September 2026": "Level and band template candidate 1.3 | 1 October 2026 | SAL-D088–D090",
            "state represented level and completion status;": "state the exact level and band, covered operation and exclusions, and completion status; distinguish Access from Standard within Level 1A, an integrated A decision from a B unit comparison and a C group priority decision; identify the four included reports, Member decision enabled, proof limits and separately authorized implementation help;",
        },
    ),
}


def build() -> None:
    for product, (source, expected_hash, replacements) in SPECS.items():
        assert sha256(source.read_bytes()).hexdigest().upper() == expected_hash, source
        target = HERE / f"{product} Level Band Template Candidate.docx"
        with ZipFile(source) as original, ZipFile(target, "w") as output:
            for info in original.infolist():
                data = original.read(info.filename)
                if info.filename == "word/document.xml":
                    xml = data.decode("utf-8")
                    for old, new in replacements.items():
                        assert xml.count(old) == 1, (source, old, xml.count(old))
                        xml = xml.replace(old, new, 1)
                    xml = add_section_rules(xml, product)
                    logo = '<wp:docPr id="1" name="Picture 1"/>'
                    assert xml.count(logo) == 1, (source, 'Salus logo alternate description')
                    xml = xml.replace(logo,
                        '<wp:docPr id="1" name="Picture 1" title="Salus Solutions" descr="Salus Solutions logo"/>', 1)
                    data = xml.encode("utf-8")
                elif info.filename == "word/styles.xml":
                    # The reference Heading/Title styles specify Arial but
                    # theme attributes take precedence and render Calibri.
                    # Remove only those theme font selectors. Explicit font
                    # values and the entire style hierarchy remain intact.
                    xml = data.decode("utf-8")
                    for attr in ("asciiTheme", "hAnsiTheme", "eastAsiaTheme", "cstheme"):
                        xml = re.sub(rf' w:{attr}="[^"]*"', "", xml)
                    data = xml.encode("utf-8")
                elif info.filename == "docProps/core.xml":
                    # Native Word uses this title for accessible PDF exports
                    # when IncludeDocProps is enabled. Keep it member-neutral.
                    xml = data.decode("utf-8")
                    title = f"{product} Level and Band Report Template Candidate 1.3"
                    xml, count = re.subn(
                        r"<dc:title(?:/>|>[^<]*</dc:title>)",
                        f"<dc:title>{title}</dc:title>",
                        xml,
                        count=1,
                    )
                    assert count == 1, (source, "document title")
                    data = xml.encode("utf-8")
                output.writestr(info, data)
            output.comment = original.comment
        with ZipFile(source) as original, ZipFile(target) as candidate:
            assert candidate.testzip() is None
            assert set(original.namelist()) == set(candidate.namelist())
            for name in original.namelist():
                if name not in ("docProps/core.xml", "word/document.xml", "word/styles.xml"):
                    assert sha256(original.read(name)).digest() == sha256(candidate.read(name)).digest(), (product, name)
        print(product, target, sha256(target.read_bytes()).hexdigest().upper())


if __name__ == "__main__":
    build()
