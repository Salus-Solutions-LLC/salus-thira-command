"""Build the controlled internal Word copy of the sequential package proposal."""
from pathlib import Path
import re

from docx import Document
from docx.enum.section import WD_SECTION_START
from docx.enum.table import WD_CELL_VERTICAL_ALIGNMENT
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.shared import Inches, Pt, RGBColor
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.opc.constants import RELATIONSHIP_TYPE as RT

HERE = Path(__file__).resolve().parent
SOURCE = HERE / "SALUS_LEVEL_PACKAGE_BUSINESS_MODEL_CANDIDATE_20260929.md"
OUTPUT = HERE / "Salus Sequential Package Business Model Decision Candidate.docx"


def field(paragraph, instruction):
    run = paragraph.add_run()
    begin = OxmlElement("w:fldChar")
    begin.set(qn("w:fldCharType"), "begin")
    code = OxmlElement("w:instrText")
    code.set(qn("xml:space"), "preserve")
    code.text = f" {instruction} "
    separate = OxmlElement("w:fldChar")
    separate.set(qn("w:fldCharType"), "separate")
    shown = OxmlElement("w:t")
    shown.text = "1"
    end = OxmlElement("w:fldChar")
    end.set(qn("w:fldCharType"), "end")
    for part in (begin, code, separate, shown, end):
        run._r.append(part)


def set_cell_shading(cell, fill):
    tc_pr = cell._tc.get_or_add_tcPr()
    shd = OxmlElement("w:shd")
    shd.set(qn("w:fill"), fill)
    tc_pr.append(shd)


def set_cell_border(cell):
    tc_pr = cell._tc.get_or_add_tcPr()
    borders = tc_pr.first_child_found_in("w:tcBorders")
    if borders is None:
        borders = OxmlElement("w:tcBorders")
        tc_pr.append(borders)
    for edge in ("top", "left", "bottom", "right"):
        item = OxmlElement(f"w:{edge}")
        item.set(qn("w:val"), "single")
        item.set(qn("w:sz"), "4")
        item.set(qn("w:color"), "D9D9D9")
        borders.append(item)


def set_cell_margin(cell, twips=90):
    tc_pr = cell._tc.get_or_add_tcPr()
    margins = tc_pr.first_child_found_in("w:tcMar")
    if margins is None:
        margins = OxmlElement("w:tcMar")
        tc_pr.append(margins)
    for side in ("top", "start", "bottom", "end"):
        el = OxmlElement(f"w:{side}")
        el.set(qn("w:w"), str(twips))
        el.set(qn("w:type"), "dxa")
        margins.append(el)


def add_inline(paragraph, text):
    pattern = re.compile(r"(\[([^\]]+)\]\((https?://[^)]+)\)|\*\*([^*]+)\*\*|`([^`]+)`|\*([^*]+)\*)")
    cursor = 0
    for match in pattern.finditer(text):
        if match.start() > cursor:
            paragraph.add_run(text[cursor:match.start()])
        if match.group(2):
            label, url = match.group(2), match.group(3)
            relation = paragraph.part.relate_to(url, RT.HYPERLINK, is_external=True)
            link = OxmlElement("w:hyperlink")
            link.set(qn("r:id"), relation)
            run = OxmlElement("w:r")
            props = OxmlElement("w:rPr")
            color = OxmlElement("w:color")
            color.set(qn("w:val"), "154A7A")
            props.append(color)
            underline = OxmlElement("w:u")
            underline.set(qn("w:val"), "single")
            props.append(underline)
            run.append(props)
            value = OxmlElement("w:t")
            value.text = label
            run.append(value)
            link.append(run)
            paragraph._p.append(link)
        elif match.group(4):
            paragraph.add_run(match.group(4)).bold = True
        elif match.group(5):
            paragraph.add_run(match.group(5))
        elif match.group(6):
            paragraph.add_run(match.group(6)).italic = True
        cursor = match.end()
    if cursor < len(text):
        paragraph.add_run(text[cursor:])


doc = Document()
sec1 = doc.sections[0]
for sec in (sec1,):
    sec.page_width, sec.page_height = Inches(8.5), Inches(11)
    sec.top_margin, sec.bottom_margin = Inches(0.78), Inches(0.68)
    sec.left_margin, sec.right_margin = Inches(0.75), Inches(0.75)

styles = doc.styles
normal = styles["Normal"]
normal.font.name = "Times New Roman"
normal.font.size = Pt(11)
normal.font.color.rgb = RGBColor(0, 0, 0)
normal.paragraph_format.space_after = Pt(4)
normal.paragraph_format.line_spacing = 1.10
def clear_theme_font(style):
    rfonts = style.element.rPr.rFonts
    if rfonts is not None:
        for attr in ("asciiTheme", "hAnsiTheme", "eastAsiaTheme", "cstheme"):
            rfonts.attrib.pop(qn("w:" + attr), None)


clear_theme_font(normal)
for name, size, before, after in [("Title", 22, 0, 12), ("Heading 1", 15, 14, 7), ("Heading 2", 12.5, 10, 5)]:
    st = styles[name]
    st.font.name = "Arial"
    st.font.size = Pt(size)
    st.font.bold = True
    st.font.color.rgb = RGBColor(0, 0, 0)
    st.paragraph_format.space_before = Pt(before)
    st.paragraph_format.space_after = Pt(after)
    st.paragraph_format.keep_with_next = True
    clear_theme_font(st)

# Confidential cover. Page 2 remains wholly blank.
sec1.different_first_page_header_footer = True
cover_footer = sec1.first_page_footer.paragraphs[0]
cover_footer.alignment = WD_ALIGN_PARAGRAPH.CENTER
cover_run = cover_footer.add_run("Salus Internal Confidential  |  page ")
cover_run.font.name, cover_run.font.size = "Times New Roman", Pt(9)
field(cover_footer, "PAGE")
cover_footer.add_run(" of ")
field(cover_footer, "NUMPAGES")
p = doc.add_paragraph()
p.alignment = WD_ALIGN_PARAGRAPH.CENTER
p.paragraph_format.space_before = Pt(95)
run = p.add_run("SALUS SOLUTIONS")
run.font.name, run.font.size, run.font.bold = "Arial", Pt(18), True
p = doc.add_paragraph(style="Title")
p.alignment = WD_ALIGN_PARAGRAPH.CENTER
p.paragraph_format.space_before = Pt(74)
ppr = p._p.get_or_add_pPr()
bdr = OxmlElement("w:pBdr")
bottom = OxmlElement("w:bottom")
bottom.set(qn("w:val"), "nil")
bdr.append(bottom)
ppr.append(bdr)
p.add_run("Salus Sequential Package Business Model")
p = doc.add_paragraph()
p.alignment = WD_ALIGN_PARAGRAPH.CENTER
run = p.add_run("Decision Candidate  |  29 September 2026")
run.font.name, run.font.size = "Arial", Pt(11)
p = doc.add_paragraph()
p.alignment = WD_ALIGN_PARAGRAPH.CENTER
p.paragraph_format.space_before = Pt(55)
run = p.add_run("SALUS INTERNAL CONFIDENTIAL")
run.font.name, run.font.size, run.font.bold = "Arial", Pt(13), True
p = doc.add_paragraph()
p.alignment = WD_ALIGN_PARAGRAPH.CENTER
p.add_run("For Marc Duncan and authorized Salus personnel only. Store and share through approved Salus channels. This proposal contains unapproved package and price hypotheses; it is not a customer offer, approved rate card, or authorization to perform professional or operational services.")

doc.add_page_break()
doc.add_paragraph()  # an empty paragraph holds the wholly blank second page
sec2 = doc.add_section(WD_SECTION_START.NEW_PAGE)  # body begins page 3
sec2.header.is_linked_to_previous = False
sec2.footer.is_linked_to_previous = False
sec2.page_width, sec2.page_height = Inches(8.5), Inches(11)
sec2.top_margin, sec2.bottom_margin = Inches(0.72), Inches(0.62)
sec2.left_margin, sec2.right_margin = Inches(0.75), Inches(0.75)
hp = sec2.header.paragraphs[0]
hp.alignment = WD_ALIGN_PARAGRAPH.CENTER
hr = hp.add_run("SALUS SOLUTIONS  |  INTERNAL CONFIDENTIAL  |  BUSINESS MODEL")
hr.font.name, hr.font.size, hr.font.color.rgb = "Arial", Pt(8), RGBColor(0, 0, 0)
fp = sec2.footer.paragraphs[0]
fp.alignment = WD_ALIGN_PARAGRAPH.CENTER
fr = fp.add_run("Salus Internal Confidential  |  page ")
fr.font.name, fr.font.size = "Times New Roman", Pt(9)
field(fp, "PAGE")
fp.add_run(" of ")
field(fp, "NUMPAGES")

lines = SOURCE.read_text(encoding="utf-8").splitlines()
i = 1  # cover contains the source title
while i < len(lines):
    line = lines[i].strip()
    if not line:
        i += 1
        continue
    if line.startswith("## "):
        heading = doc.add_paragraph(line[3:].replace("—", " ").replace("/", " and "), style="Heading 1")
        if line.startswith(("## Feature-to-delivery and SalOPS service crosswalk", "## One-page buyer sheets for each paid package", "## Personalized scope receipt after Protection Advisor Part 2")):
            heading.paragraph_format.page_break_before = True
        i += 1
        continue
    if line.startswith("### "):
        heading = doc.add_paragraph(line[4:], style="Heading 2")
        if line.startswith("### Buyer sheet —") and not line.startswith("### Buyer sheet — Level 1A Access"):
            heading.paragraph_format.page_break_before = True
        if line.startswith("### Scope receipt —") and not line.startswith("### Scope receipt — reusable one-page template"):
            heading.paragraph_format.page_break_before = True
        i += 1
        continue
    if line.startswith("| "):
        block = []
        while i < len(lines) and lines[i].strip().startswith("|"):
            block.append([c.strip() for c in lines[i].strip().strip("|").split("|")])
            i += 1
        if len(block) < 3:
            continue
        rows = [block[0]] + block[2:]
        cols = max(len(x) for x in rows)
        table = doc.add_table(rows=len(rows), cols=cols)
        table.autofit = False
        if cols == 4:
            widths = [Inches(1.05), Inches(1.96), Inches(1.96), Inches(2.02)]
        elif cols == 3:
            widths = [Inches(1.60), Inches(3.00), Inches(2.39)]
        elif cols == 2:
            widths = [Inches(1.53), Inches(5.46)]
        else:
            widths = [Inches(6.99 / cols)] * cols
        for ci, width in enumerate(widths):
            table.columns[ci].width = width
        for ri, row_data in enumerate(rows):
            row_props = table.rows[ri]._tr.get_or_add_trPr()
            row_props.append(OxmlElement("w:cantSplit"))
            for ci in range(cols):
                cell = table.cell(ri, ci)
                cell.width = widths[ci]
                cell.vertical_alignment = WD_CELL_VERTICAL_ALIGNMENT.CENTER
                set_cell_margin(cell)
                set_cell_border(cell)
                if row_data and "Choose your next step" in row_data[0]:
                    set_cell_shading(cell, "E7F0F7")
                elif ri == 0:
                    set_cell_shading(cell, "E7EBEF")
                elif ri % 2 == 0:
                    set_cell_shading(cell, "F7F8FA")
                paragraph = cell.paragraphs[0]
                paragraph.paragraph_format.space_after = Pt(0)
                add_inline(paragraph, row_data[ci] if ci < len(row_data) else "")
                for run in paragraph.runs:
                    run.font.name = "Arial" if ri == 0 else "Times New Roman"
                    run.font.size = Pt(8.5 if cols == 4 else 9)
                    if ri == 0:
                        run.bold = True
        tr_pr = table.rows[0]._tr.get_or_add_trPr()
        repeat = OxmlElement("w:tblHeader")
        repeat.set(qn("w:val"), "true")
        tr_pr.append(repeat)
        next_content = next((candidate.strip() for candidate in lines[i:] if candidate.strip()), "")
        if not next_content.startswith(("### Buyer sheet —", "### Scope receipt —")):
            doc.add_paragraph().paragraph_format.space_after = Pt(2)
        continue
    if re.match(r"^\d+\. ", line):
        p = doc.add_paragraph(style="List Number")
        add_inline(p, re.sub(r"^\d+\. ", "", line))
        i += 1
        continue
    if line.startswith("- "):
        p = doc.add_paragraph(style="List Bullet")
        add_inline(p, line[2:])
        i += 1
        continue
    paragraph_lines = [line]
    while i + 1 < len(lines) and lines[i + 1].strip() and not lines[i + 1].startswith(("## ", "### ", "| ", "- ")) and not re.match(r"^\d+\. ", lines[i + 1].strip()):
        i += 1
        paragraph_lines.append(lines[i].strip())
    p = doc.add_paragraph()
    add_inline(p, " ".join(paragraph_lines))
    if line.startswith(("**One finding through all four reports:", "**What a trackable decision looks like")):
        p.paragraph_format.keep_together = True
    i += 1

doc.core_properties.title = "Salus Sequential Package Business Model Decision Candidate"
doc.core_properties.subject = "Level 1 Level 2 Level 3 scope intake pricing and revenue model"
doc.core_properties.author = "Salus Solutions"
doc.save(OUTPUT)
print(OUTPUT)
