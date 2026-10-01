"""Check the exact native-Word PDF exports without changing source documents."""

from __future__ import annotations

import json
import re
from pathlib import Path

import pdfplumber
from pypdf import PdfReader


ROOT = Path(__file__).resolve().parent / "native_word_20261001"
REPORT_NAMES = {"SalCAPA", "SalINTEL", "SalOPS", "SalTHIRA"}


def font_names(page):
    resources = page.get("/Resources") or {}
    fonts = resources.get("/Font") or {}
    return sorted({str(ref.get_object().get("/BaseFont", "")) for ref in fonts.values()})


rows = []
for path in sorted(ROOT.glob("*.pdf")):
    pdf = PdfReader(path)
    with pdfplumber.open(path) as visual_pdf:
        calibri_chars = sum(
            "calibri" in char.get("fontname", "").lower()
            for page in visual_pdf.pages
            for char in page.chars
        )
    texts = [page.extract_text() or "" for page in pdf.pages]
    report = any(path.name.startswith(name + " ") for name in REPORT_NAMES)
    questionnaire = path.name.startswith("Protection Advisor Part ")
    rows.append(
        {
            "file": path.name,
            "pages": len(pdf.pages),
            "second_page_blank": len(texts) > 1 and not texts[1].strip(),
            "page_indications": [
                bool(re.search(rf"page\s+{number}\s+of\s+{len(texts)}", text, re.I))
                for number, text in enumerate(texts, 1)
            ],
            "fonts": sorted({font for page in pdf.pages for font in font_names(page)}),
            "requires_blank_second_page": report or questionnaire,
            "cover_mentions_confidential": "confidential" in texts[0].lower(),
            "calibri_visible_characters": calibri_chars,
        }
    )

(ROOT / "audit.json").write_text(json.dumps(rows, indent=2), encoding="utf-8")
for row in rows:
    if row["calibri_visible_characters"]:
        raise AssertionError(f"Calibri visible in {row['file']}")
    if not row["cover_mentions_confidential"]:
        raise AssertionError(f"Confidential cover missing in {row['file']}")
    if row["requires_blank_second_page"] and not row["second_page_blank"]:
        raise AssertionError(f"Blank second page missing in {row['file']}")
    if any(
        not indicated and (pdf_page.extract_text() or "").strip()
        for indicated, pdf_page in zip(row["page_indications"], PdfReader(ROOT / row["file"]).pages)
    ):
        raise AssertionError(f"Page X of Y indication missing in {row['file']}")
print(json.dumps(rows, indent=2))
