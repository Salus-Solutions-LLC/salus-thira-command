"""Remove Word theme-font overrides from four exact questionnaire review copies.

The original builder set visible font names, but heading styles retained Word's
major-HAnsi theme binding. Native Word then rendered those headings in Calibri.
This controlled QA repair keeps the same files, paragraphs, and pagination.
"""

from pathlib import Path

from docx import Document
from docx.enum.style import WD_STYLE_TYPE
from docx.oxml.ns import qn


ROOT = Path(__file__).resolve().parent / "questionnaire_candidates"
FILES = (
    "Protection Advisor Part 1 Questionnaire.docx",
    "Protection Advisor Part 2 Questionnaire.docx",
    "Protection_Advisor_Level_1_Intake_Revision_DRAFT.docx",
    "Salus_Level_1_Protected_Member_Information_Request_DRAFT.docx",
)
FONT_ATTRS = ("ascii", "hAnsi", "eastAsia", "cs")
THEME_ATTRS = ("asciiTheme", "hAnsiTheme", "eastAsiaTheme", "cstheme", "csTheme")


def set_explicit_font(run_or_style, font: str) -> None:
    run_or_style.font.name = font
    r_pr = run_or_style._element.get_or_add_rPr()
    fonts = r_pr.rFonts
    if fonts is None:
        fonts = r_pr.get_or_add_rFonts()
    for attr in THEME_ATTRS:
        fonts.attrib.pop(qn("w:" + attr), None)
    for attr in FONT_ATTRS:
        fonts.set(qn("w:" + attr), font)


def is_heading(name: str) -> bool:
    return name == "Title" or name == "Subtitle" or name.startswith("Heading ")


for filename in FILES:
    path = ROOT / filename
    doc = Document(path)
    before = [paragraph.text for paragraph in doc.paragraphs]
    for style in doc.styles:
        if style.type != WD_STYLE_TYPE.PARAGRAPH:
            continue
        if is_heading(style.name):
            set_explicit_font(style, "Arial")
        elif style.name in {"Normal", "List Bullet", "List Number"}:
            set_explicit_font(style, "Times New Roman")
    for paragraph in doc.paragraphs:
        if is_heading(paragraph.style.name):
            for run in paragraph.runs:
                set_explicit_font(run, "Arial")
        if filename.startswith("Protection Advisor Part 2") and paragraph.text == "Your possible Level 1 path":
            # Keep the final package-path explanation on one deliberate page.
            paragraph.paragraph_format.page_break_before = True
    assert before == [paragraph.text for paragraph in doc.paragraphs]
    doc.save(path)
    print(path)
