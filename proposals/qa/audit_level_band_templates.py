"""Read-only exact-version structural and rendered-text check for four draft templates."""

import hashlib
import json
import re
import sys
from pathlib import Path
from zipfile import ZipFile

from docx import Document
from pypdf import PdfReader
from docx.oxml.ns import qn

ROOT = Path(__file__).resolve().parents[2]
TEMPLATES = ROOT / 'proposals' / 'level_band_templates'
sys.path.insert(0, str(TEMPLATES))
from build_candidates import SPECS  # noqa: E402


def fonts_on_page(page):
    resources = page.get('/Resources')
    if not resources:
        return set()
    result = set()
    for font in resources.get_object().get('/Font', {}).get_object().values():
        name = font.get_object().get('/BaseFont', '')
        result.add(str(name))
    return result


def inspect(product, source, expected_hash):
    candidate = TEMPLATES / f'{product} Level Band Template Candidate.docx'
    pdf = ROOT / 'proposals' / 'qa' / f'template_exact_{product}' / f'{candidate.stem}.pdf'
    issues = []
    source_sha = hashlib.sha256(source.read_bytes()).hexdigest().upper()
    candidate_sha = hashlib.sha256(candidate.read_bytes()).hexdigest().upper()
    if source_sha != expected_hash:
        issues.append('Registered reference hash mismatch')
    with ZipFile(source) as old, ZipFile(candidate) as new:
        if old.testzip() or new.testzip():
            issues.append('Damaged Word ZIP member')
        if set(old.namelist()) != set(new.namelist()):
            issues.append('Word package member set changed')
        changed = sorted(name for name in set(old.namelist()) & set(new.namelist())
                         if hashlib.sha256(old.read(name)).digest() != hashlib.sha256(new.read(name)).digest())
        if changed != ['word/document.xml', 'word/styles.xml']:
            issues.append(f'Unexpected Word package changes: {changed}')
        xml = new.read('word/document.xml').decode('utf-8')
        if f'- {product} Level [path]' not in xml:
            issues.append('Expected path title missing')
        image_alts = re.findall(r'<wp:docPr\b[^>]*\bdescr="([^"]*)"', xml)
        drawings = len(re.findall(r'<wp:docPr\b', xml))
        if drawings and len(image_alts) < drawings:
            issues.append('A drawing lacks alternate description in the document body')
    document = Document(candidate)
    title_styles = [paragraph.style.name for paragraph in document.paragraphs
                    if f'- {product} Level [path]' in paragraph.text]
    if title_styles != ['Title']:
        issues.append('Cover title is not a Word Title paragraph')
    heading_count = sum(paragraph.style.name.startswith('Heading') for paragraph in document.paragraphs)
    if heading_count < 10:
        issues.append('Expected semantic heading structure missing')
    table_count = len(document.tables)
    table_headers = sum(bool(table.rows and table.rows[0]._tr.find('.//' + qn('w:tblHeader')) is not None)
                        for table in document.tables)
    if table_headers != table_count:
        issues.append(f'{table_count - table_headers} tables lack a marked header row')
    section_count = len(document.sections)
    if section_count != 3:
        issues.append(f'Expected three Word sections; found {section_count}')
    pages = PdfReader(str(pdf)).pages
    expected_pages = 9 if product == 'SalINTEL' else 6
    if len(pages) != expected_pages:
        issues.append(f'Page count {len(pages)} differs from expected {expected_pages}')
    page_text = [page.extract_text() or '' for page in pages]
    if len(page_text) < 2 or page_text[1].strip():
        issues.append('Second page is not text blank')
    footers = []
    for index, content in enumerate(page_text, 1):
        if index == 2:
            continue
        matches = re.findall(rf'page\s+{index}\s+of\s+{len(pages)}', content, flags=re.I)
        footers.append(bool(matches))
        if not matches:
            issues.append(f'Page {index} lacks page {index} of {len(pages)}')
    fonts = sorted(set().union(*(fonts_on_page(page) for page in pages)))
    if not any('Arial' in name for name in fonts):
        issues.append('Rendered Arial font missing')
    if not any('TimesNewRoman' in name or 'Times' in name for name in fonts):
        issues.append('Rendered Times New Roman font missing')
    return {'product': product, 'reference_sha256': source_sha, 'candidate_sha256': candidate_sha,
            'rendered_pdf_sha256': hashlib.sha256(pdf.read_bytes()).hexdigest().upper(),
            'changed_package_members': changed, 'pages': len(pages), 'blank_second_page': not page_text[1].strip(),
            'nonblank_page_footers_checked': sum(footers), 'fonts': fonts,
            'word_title_styles': title_styles, 'semantic_heading_count': heading_count,
            'word_sections': section_count, 'tables': table_count, 'marked_table_headers': table_headers,
            'body_drawings': drawings, 'body_image_alts': len(image_alts), 'issues': issues}


if __name__ == '__main__':
    results = [inspect(product, source, expected) for product, (source, expected, _) in SPECS.items()]
    print(json.dumps(results, indent=2))
    if any(item['issues'] for item in results):
        sys.exit(1)
