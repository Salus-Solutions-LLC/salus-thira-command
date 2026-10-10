from __future__ import annotations

import argparse
from collections import Counter
import hashlib
import json
import re
import sys
import xml.etree.ElementTree as ET
from pathlib import Path
from zipfile import BadZipFile, ZipFile


W = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
R = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"
REL = "http://schemas.openxmlformats.org/package/2006/relationships"
WP = "http://schemas.openxmlformats.org/drawingml/2006/wordprocessingDrawing"
WP14 = "http://schemas.microsoft.com/office/word/2010/wordprocessingDrawing"
V = "urn:schemas-microsoft-com:vml"


def qn(namespace: str, tag: str) -> str:
    return f"{{{namespace}}}{tag}"


def text(root: ET.Element) -> str:
    return "".join(node.text or "" for node in root.iter(qn(W, "t")))


def hyperlink_own_text(root: ET.Element) -> str:
    """Return text owned by one hyperlink, excluding nested fallback hyperlinks."""
    parts: list[str] = []

    def visit(node: ET.Element) -> None:
        for child in node:
            if child.tag == qn(W, "hyperlink"):
                continue
            if child.tag == qn(W, "t"):
                parts.append(child.text or "")
            visit(child)

    visit(root)
    return "".join(parts)


def main() -> None:
    parser = argparse.ArgumentParser(description="Deterministically validate a controlled Salus DOCX package.")
    parser.add_argument("docx", type=Path)
    parser.add_argument("--expected-revision", required=True)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()

    problems: list[str] = []
    try:
        with ZipFile(args.docx) as package:
            bad_member = package.testzip()
            names = package.namelist()
            blobs = {name: package.read(name) for name in names}
    except (BadZipFile, OSError) as exc:
        raise SystemExit(f"invalid DOCX ZIP: {exc}")
    if bad_member:
        problems.append(f"ZIP CRC failure: {bad_member}")

    xml_roots: dict[str, ET.Element] = {}
    for name, blob in blobs.items():
        if name.endswith((".xml", ".rels")):
            try:
                xml_roots[name] = ET.fromstring(blob)
            except ET.ParseError as exc:
                problems.append(f"XML parse failure {name}: {exc}")

    required = {"[Content_Types].xml", "_rels/.rels", "word/document.xml", "word/_rels/document.xml.rels"}
    missing_required = sorted(required.difference(blobs))
    if missing_required:
        problems.append("missing required parts: " + ", ".join(missing_required))

    document = xml_roots.get("word/document.xml")
    relationships = xml_roots.get("word/_rels/document.xml.rels")
    bookmark_names: list[str] = []
    bookmark_ids: list[str] = []
    internal_targets: list[str] = []
    hyperlink_rel_ids: list[str] = []
    master_toc_links = 0
    malformed_master_toc_links = 0
    drawing_ids: list[str] = []
    drawing_anchor_ids: list[str] = []
    drawing_edit_ids: list[str] = []
    vml_master_toc_shapes = 0
    malformed_vml_master_toc_shapes = 0
    if document is not None:
        for node in document.iter(qn(W, "bookmarkStart")):
            bookmark_names.append(node.get(qn(W, "name"), ""))
            bookmark_ids.append(node.get(qn(W, "id"), ""))
        for node in document.iter(qn(W, "hyperlink")):
            anchor = node.get(qn(W, "anchor"))
            rel_id = node.get(qn(R, "id"))
            if anchor:
                internal_targets.append(anchor)
            if rel_id:
                hyperlink_rel_ids.append(rel_id)
            if "MASTER TOC" in hyperlink_own_text(node).upper():
                master_toc_links += 1
                if anchor != "Master_Table_of_Contents":
                    malformed_master_toc_links += 1
        for node in document.iter(qn(V, "rect")):
            if "MASTER TOC" in text(node).upper():
                vml_master_toc_shapes += 1
                if node.get("href") != "#Master_Table_of_Contents":
                    malformed_vml_master_toc_shapes += 1
        drawing_ids = [node.get("id", "") for node in document.iter(qn(WP, "docPr"))]
        for node in document.iter():
            anchor_id = node.get(qn(WP14, "anchorId"))
            edit_id = node.get(qn(WP14, "editId"))
            if anchor_id:
                drawing_anchor_ids.append(anchor_id)
            if edit_id:
                drawing_edit_ids.append(edit_id)

    def duplicates(values: list[str]) -> list[str]:
        return sorted(value for value, count in Counter(values).items() if value and count > 1)

    duplicate_drawing_ids = duplicates(drawing_ids)
    duplicate_drawing_anchor_ids = duplicates(drawing_anchor_ids)
    duplicate_drawing_edit_ids = duplicates(drawing_edit_ids)
    if malformed_master_toc_links:
        problems.append(f"MASTER TOC links with incorrect internal target: {malformed_master_toc_links}")
    if malformed_vml_master_toc_shapes:
        problems.append(f"MASTER TOC VML fallbacks with incorrect internal target: {malformed_vml_master_toc_shapes}")
    if duplicate_drawing_ids:
        problems.append("duplicate drawing IDs: " + ", ".join(duplicate_drawing_ids))
    if duplicate_drawing_anchor_ids:
        problems.append("duplicate drawing anchor IDs: " + ", ".join(duplicate_drawing_anchor_ids))
    if duplicate_drawing_edit_ids:
        problems.append("duplicate drawing edit IDs: " + ", ".join(duplicate_drawing_edit_ids))

    duplicate_bookmark_names = sorted({name for name in bookmark_names if name and bookmark_names.count(name) > 1})
    duplicate_bookmark_ids = sorted({value for value in bookmark_ids if value and bookmark_ids.count(value) > 1})
    missing_internal_targets = sorted(set(internal_targets).difference(bookmark_names))
    if duplicate_bookmark_names:
        problems.append("duplicate bookmark names: " + ", ".join(duplicate_bookmark_names))
    if duplicate_bookmark_ids:
        problems.append("duplicate bookmark IDs: " + ", ".join(duplicate_bookmark_ids))
    if missing_internal_targets:
        problems.append("missing internal targets: " + ", ".join(missing_internal_targets))

    rel_ids: set[str] = set()
    external_rels = 0
    if relationships is not None:
        for node in relationships.iter(qn(REL, "Relationship")):
            rel_id = node.get("Id", "")
            if rel_id in rel_ids:
                problems.append(f"duplicate relationship ID: {rel_id}")
            rel_ids.add(rel_id)
            if node.get("TargetMode") == "External":
                external_rels += 1
    missing_hyperlink_rels = sorted(set(hyperlink_rel_ids).difference(rel_ids))
    if missing_hyperlink_rels:
        problems.append("missing hyperlink relationships: " + ", ".join(missing_hyperlink_rels))

    header_footer_toc = 0
    revision_hits = 0
    stale_revision_values: list[str] = []
    for name, root in xml_roots.items():
        if re.fullmatch(r"word/(header|footer)\d+\.xml", name):
            part_text = text(root)
            header_footer_toc += part_text.upper().count("MASTER TOC")
            if name.startswith("word/footer"):
                revision_hits += part_text.count(args.expected_revision)
                stale_revision_values.extend(
                    value for value in re.findall(r"(?<!\d)20\d{6}(?!\d)", part_text)
                    if value != args.expected_revision
                )
    if header_footer_toc:
        problems.append(f"MASTER TOC present in headers/footers: {header_footer_toc}")
    if revision_hits != 2:
        problems.append(f"expected revision appears {revision_hits} times in footers, expected 2")
    if stale_revision_values:
        problems.append("stale footer revisions: " + ", ".join(sorted(set(stale_revision_values))))

    result = {
        "file": args.docx.name,
        "sha256": hashlib.sha256(args.docx.read_bytes()).hexdigest(),
        "size_bytes": args.docx.stat().st_size,
        "zip_members": len(blobs),
        "xml_parts_parsed": len(xml_roots),
        "bookmarks": len(bookmark_names),
        "duplicate_bookmark_names": duplicate_bookmark_names,
        "duplicate_bookmark_ids": duplicate_bookmark_ids,
        "internal_hyperlinks": len(internal_targets),
        "missing_internal_targets": missing_internal_targets,
        "relationship_hyperlinks": len(hyperlink_rel_ids),
        "missing_hyperlink_relationships": missing_hyperlink_rels,
        "external_relationships": external_rels,
        "master_toc_body_hyperlinks": master_toc_links,
        "malformed_master_toc_body_hyperlinks": malformed_master_toc_links,
        "master_toc_vml_fallback_shapes": vml_master_toc_shapes,
        "malformed_master_toc_vml_fallback_shapes": malformed_vml_master_toc_shapes,
        "master_toc_header_footer_instances": header_footer_toc,
        "drawing_ids": len(drawing_ids),
        "duplicate_drawing_ids": duplicate_drawing_ids,
        "duplicate_drawing_anchor_ids": duplicate_drawing_anchor_ids,
        "duplicate_drawing_edit_ids": duplicate_drawing_edit_ids,
        "footer_revision_hits": revision_hits,
        "status": "passed" if not problems else "failed",
        "problems": problems,
    }
    payload = json.dumps(result, indent=2, sort_keys=True) + "\n"
    if args.output:
        args.output.write_text(payload, encoding="utf-8")
    sys.stdout.write(payload)
    if problems:
        raise SystemExit(1)


if __name__ == "__main__":
    main()

