"""Print content-free structure metadata for a fictional Protection Advisor PDF pair.

This is a screening aid. Tags and role counts do not establish readable order,
visual quality, or qualified acceptance. Never print report text or file paths.
"""

from __future__ import annotations

import json
import sys
from collections import Counter
from pathlib import Path

from pypdf import PdfReader


def inspect(path: Path, *, check_blank_second_page: bool) -> dict[str, object]:
    reader = PdfReader(path)
    catalog = reader.trailer["/Root"]
    structure = catalog.get("/StructTreeRoot")
    mark = catalog.get("/MarkInfo")
    roles: Counter[str] = Counter()
    figures_with_alt = 0
    stack = [structure] if structure is not None else []
    seen: set[int] = set()

    while stack:
        item = stack.pop()
        item = item.get_object() if hasattr(item, "get_object") else item
        if not isinstance(item, dict) or id(item) in seen:
            continue
        seen.add(id(item))
        role = str(item.get("/S", ""))
        if role:
            roles[role] += 1
            if role == "/Figure" and item.get("/Alt"):
                figures_with_alt += 1
        children = item.get("/K")
        stack.extend(
            children if isinstance(children, list)
            else [children] if children is not None
            else []
        )

    mark = mark.get_object() if hasattr(mark, "get_object") else mark
    result: dict[str, object] = {
        "page_count": len(reader.pages),
        "language": str(catalog.get("/Lang", "")),
        "structure_tree_present": structure is not None,
        "marked_content": bool(mark.get("/Marked", False)) if isinstance(mark, dict) else False,
        "structure_roles": dict(sorted(roles.items())),
        "figures_with_alt": figures_with_alt,
    }
    if check_blank_second_page:
        result["page_two_blank"] = len(reader.pages) >= 2 and not (
            reader.pages[1].extract_text() or ""
        ).strip()
    return result


def main() -> None:
    if len(sys.argv) != 3:
        raise SystemExit("Usage: advisor_pdf_structure_metadata.py <fictional-report.pdf> <fictional-receipt.pdf>")
    print(json.dumps({
        "report": inspect(Path(sys.argv[1]), check_blank_second_page=True),
        "scope_receipt": inspect(Path(sys.argv[2]), check_blank_second_page=False),
        "screening_only": True,
    }, sort_keys=True))


if __name__ == "__main__":
    main()
