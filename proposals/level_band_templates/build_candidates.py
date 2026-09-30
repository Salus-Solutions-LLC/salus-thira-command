"""Make narrow member-neutral title candidates from the four retained Word templates."""

from hashlib import sha256
from pathlib import Path
from zipfile import ZipFile
import re

HERE = Path(__file__).resolve().parent
WORK = HERE.parents[2]

SPECS = {
    "SalINTEL": (
        WORK / "approved_templates/SalINTEL Report Template.docx",
        "5A99C3F0A3DB126F101407617AABA7CB8EB098C3D704E436B01C5D8520BB1959",
        {
            "SalINTEL™ Facility Assessment — [Level 1 / Level 2 / Level 3]": "[Protected Member customer name] - SalINTEL Level [path]",
            "Approved sequential-package report template | Version 1.0 | 27 September 2026": "Level and band template candidate 1.1 | 29 September 2026 | SAL-D089",
            "Status: approved member-neutral report template.": "Status: member-neutral candidate derived from approved template v1.0.",
            "This is the Level __ SalINTEL report, with working/qualified/issued and prerequisite status.": "This is the Level [path] SalINTEL report for [covered operation and included/excluded units], with working/qualified/issued and prerequisite status.",
        },
    ),
    "SalTHIRA": (
        WORK / "approved_templates/SalTHIRA Report Template.docx",
        "29B896804C44B56D5A32BA377FE557B676649FAC88C83D674BE77EA088B81FF8",
        {
            "[Protected Member customer name] - SalTHIRA Level [1, 2, or 3]": "[Protected Member customer name] - SalTHIRA Level [path]",
            "Controlled template version 1.0 | 27 September 2026": "Level and band candidate 1.1 | 29 September 2026",
            "Bottom Line Up Front (BLUF) - Level [1, 2, or 3] ranked judgment": "Bottom Line Up Front (BLUF) - Level [path] ranked judgment",
            "state the represented level, package status, ranked priorities": "state the exact level and band, covered operation and exclusions, package status, ranked priorities",
        },
    ),
    "SalOPS": (
        WORK / "salops_design/SalOPS Report Template DRAFT.docx",
        "4CE3DB45CA2C39BF28D278296D23CCEC322AC4E7738793D95B7170EC12170043",
        {
            "[Protected Member customer name] - SalOPS Level [1, 2, or 3]": "[Protected Member customer name] - SalOPS Level [path]",
            "Member-neutral working report template | 27 September 2026": "Level and band template candidate 1.1 | 29 September 2026 | SAL-D089",
            "State the represented level, package and predecessor-report status.": "State the exact level and band, covered operation and exclusions, package and predecessor-report status.",
        },
    ),
    "SalCAPA": (
        WORK / "salcapa_report_design/SalCAPA Integrated Report Template DRAFT.docx",
        "A1FAE0F2187C0B7DE74246DE70203B6F40F172434BC197127EF30E907153D3A1",
        {
            "[Protected Member customer name] - SalCAPA Level [1, 2, or 3]": "[Protected Member customer name] - SalCAPA Level [path]",
            "Integrated decision summary working template | 27 September 2026": "Level and band template candidate 1.1 | 29 September 2026 | SAL-D089",
            "state represented level and completion status;": "state the exact level and band, covered operation and exclusions, and completion status;",
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
                output.writestr(info, data)
            output.comment = original.comment
        with ZipFile(source) as original, ZipFile(target) as candidate:
            assert candidate.testzip() is None
            assert set(original.namelist()) == set(candidate.namelist())
            for name in original.namelist():
                if name not in ("word/document.xml", "word/styles.xml"):
                    assert sha256(original.read(name)).digest() == sha256(candidate.read(name)).digest(), (product, name)
        print(product, target, sha256(target.read_bytes()).hexdigest().upper())


if __name__ == "__main__":
    build()
