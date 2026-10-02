"""Expand all four member-neutral Word candidates with fictional layout data.

The output is an internal page-flow fixture, never a Protected Member report.
Original templates and issued artifacts are not changed.
"""

from pathlib import Path
import re

from docx import Document


ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "level_band_templates"
OUTPUT = ROOT / "qa" / "template_populated_stress"
NAME = "Cedar Valley Child Care and Community Services Cooperative"
SCOPE = (
    "the main child care center and its shared administration function; "
    "the separately operated transport contractor and second campus are excluded"
)
BODY = (
    "Fictional layout test only. The center relies on one director, a designated alternate, "
    "a small staff team, contracted maintenance, municipal utilities and a regional response "
    "partner. A prolonged power interruption could stop refrigeration, communications and "
    "safe occupancy. The available plan names a backup contact but does not establish tested "
    "runtime, decision authority or a restoration target. The analyst would verify the dated "
    "plan, utility arrangement and exercise record before making a final finding. The current "
    "illustrative priority is to confirm who decides, how families are notified and what proof "
    "will show the corrective action works. This paragraph is deliberately long to challenge "
    "the page flow, heading placement and footers; it is not evidence about any real Member."
)
TABLE_VALUE = (
    "Fictional record and owner; evidence remains unverified. Review the scoped operation, "
    "decision effect, date, source and next validation step before use."
)


def fill_text(value: str, *, short: bool = False) -> str:
    result = value.replace("[Protected Member customer name]", NAME).replace("[path]", "1A Access")
    result = result.replace("[covered operation and included/excluded units]", SCOPE)
    if result.startswith("[") and result.endswith("]"):
        return "Fictional Cedar Valley record; limited reviewer access." if short else BODY
    return re.sub(r"\[[^\[\]]+\]", "Fictional layout value", result)


def build(product: str) -> Path:
    doc = Document(SOURCE / f"{product} Level Band Template Candidate.docx")
    for index, paragraph in enumerate(doc.paragraphs):
        text = paragraph.text
        if not text.strip():
            continue
        if index == 2:
            paragraph.text = "Fictional populated layout fixture | 30 September 2026 | Not a client report"
        elif "[" in text:
            paragraph.text = fill_text(text, short=index < 9)
    for table_index, table in enumerate(doc.tables):
        for row in table.rows[1:]:
            for cell in row.cells:
                if "[" in cell.text:
                    cell.text = ("Fictional Cedar Valley | Level 1A Access" if table_index < 2
                                 else fill_text(cell.text, short=True))
        if len(table.columns) >= 4 and len(table.rows) == 2:
            for number in range(3):
                row = table.add_row()
                for col, cell in enumerate(row.cells):
                    cell.text = f"Fictional example {number + 1}, field {col + 1}. {TABLE_VALUE}"
    OUTPUT.mkdir(parents=True, exist_ok=True)
    target = OUTPUT / f"{product} Level 1A Access populated stress.docx"
    doc.save(target)
    return target


def main() -> None:
    for product in ("SalINTEL", "SalTHIRA", "SalOPS", "SalCAPA"):
        target = build(product)
        reopened = Document(target)
        assert NAME in "\n".join(p.text for p in reopened.paragraphs[:8])
        assert all("[" not in p.text for p in reopened.paragraphs if p.text.strip())
        print(product, target, len(reopened.paragraphs), len(reopened.tables))


if __name__ == "__main__":
    main()
