"""Check rendered fictional page-flow fixtures, not client reports."""

from pathlib import Path
import re

from pypdf import PdfReader


ROOT = Path(__file__).resolve().parent / "template_populated_stress"


def main() -> None:
    failures = []
    for product in ("SalINTEL", "SalTHIRA", "SalOPS", "SalCAPA"):
        pdf = next((ROOT / f"render_final_{product}").glob("*.pdf"))
        pages = PdfReader(str(pdf)).pages
        text = [(page.extract_text() or "") for page in pages]
        if len(pages) < 7:
            failures.append(f"{product}: unexpectedly short populated fixture")
        if text[1].strip():
            failures.append(f"{product}: second page contains text")
        if "1A Access" not in text[0]:
            failures.append(f"{product}: cover lacks represented path")
        if "Fictional" not in "".join(text[2:]):
            failures.append(f"{product}: fictional body content missing")
        for index, page_text in enumerate(text, 1):
            if index == 2:
                continue
            footer = rf"page\s+{index}\s+of\s+{len(pages)}"
            if not re.search(footer, page_text, re.I):
                failures.append(f"{product}: page {index} footer missing")
            if len(page_text) < 80:
                failures.append(f"{product}: page {index} has too little text")
        print(f"{product}: {len(pages)} pages, page 2 blank, {len(pages)-1} footers checked")
    if failures:
        raise SystemExit("\n".join(failures))


if __name__ == "__main__":
    main()
