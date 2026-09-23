#!/usr/bin/env python3
"""Bounded live Graph write and pending-extraction diagnosis without source disclosure."""

from __future__ import annotations

import re
import uuid
from urllib.parse import quote

from salcapa_knowledge_promotion import (
    GRAPH_ROOT, GraphKnowledgeWriter, KnowledgeDestinationConfig,
    PENDING_PREFIX, _extract_all_accessible_content,
)
from salcapa_m365_intake import GovernedM365Config, GovernedM365Intake

KNOWLEDGE_DRIVE = "b!mn-UaUzJ6UOGBLc9xcQ2DYwuRoUBrB9KtakxYIYG5o1riGTeQsB8T4jy0ttFW_fN"
KNOWLEDGE_ROOT = "01WETF6P56Y2GOVW7725BZO354PWSELRRZ"
PROCESSED_FOLDER = "01DBTAFULEFCM3ALTBFNHZVKGCHE7QGFJ4"
TARGET_FOLDER = "05 Research and Reference"


def safe_code(response) -> str:
    try:
        value = response.json().get("error", {}).get("code", "none")
    except (ValueError, AttributeError, TypeError):
        value = "unavailable"
    value = str(value)[:80]
    return value if re.fullmatch(r"[A-Za-z0-9_.-]+", value) else "unavailable"


def main() -> None:
    intake_config = GovernedM365Config.from_environment()
    intake = GovernedM365Intake(intake_config)
    files = [row for row in intake.list_files()
             if row["relative_path"].startswith(PENDING_PREFIX)]
    if len(files) > 20:
        raise RuntimeError("Pending sample exceeds diagnostic bound")
    for row in files:
        document = intake.read_document(row["id"], access_classification="Salus Internal")
        extraction = _extract_all_accessible_content(document)
        extension = document.name.rsplit(".", 1)[-1].lower() if "." in document.name else "none"
        if extension not in {"pdf", "docx", "txt", "xlsx", "pptx", "csv", "png", "jpg"}:
            extension = "other"
        code = str(extraction.get("failure_code", "none"))
        if not re.fullmatch(r"[A-Z0-9_]+|none", code):
            code = "unavailable"
        print(f"PENDING_EXTRACTION extension={extension} status={extraction['status']} code={code}")
        if extension == "pdf":
            from pathlib import Path
            from tempfile import TemporaryDirectory
            from tools.salcapa_pdf_worker import WorkerFailure, extract
            with TemporaryDirectory(prefix="salcapa-pdf-diagnostic-") as tmp:
                path = Path(tmp) / "source.pdf"
                path.write_bytes(document.content)
                try:
                    extract(path)
                except WorkerFailure as exc:
                    reason = {
                        "The PDF declares an interactive, active, form, portfolio, or rich-media feature and was not processed.": "root_active_feature",
                        "The PDF declares embedded files or document JavaScript and was not processed.": "named_active_feature",
                        "The PDF contains page actions or rich media and was not processed.": "page_active_feature",
                        "The PDF annotation declaration could not be inspected safely.": "annotation_invalid",
                        "The PDF contains annotations and was not processed.": "annotation_present",
                    }.get(exc.detail, "other")
                    print(f"PENDING_PDF_WORKER_REASON={reason}")
                    allowed_codes = {"PDF_ACTIVE_CONTENT", "PDF_PARSE_FAILED", "PDF_RESOURCE_LIMIT", "PDF_CONTENT_STREAM_INVALID", "PDF_TEXT_EXTRACTION_FAILED", "PDF_ENCRYPTED", "PDF_WORKER_FAILED"}
                    print("PENDING_PDF_WORKER_CODE=" + (exc.code if exc.code in allowed_codes else "other"))
                else:
                    print("PENDING_PDF_WORKER_REASON=none")

    writer = GraphKnowledgeWriter(
        intake_config,
        KnowledgeDestinationConfig(KNOWLEDGE_DRIVE, KNOWLEDGE_ROOT, PROCESSED_FOLDER),
    )
    folder_id = writer._resolve_folder(TARGET_FOLDER)
    print("KNOWLEDGE_DESTINATION_READ=200")
    name = f"SalCAPA-Write-Diagnostic-{uuid.uuid4().hex}.txt"
    url = (
        f"{GRAPH_ROOT}/drives/{KNOWLEDGE_DRIVE}/items/{folder_id}:/"
        f"{quote(name, safe='')}:/content"
    )
    response = writer.client.put(
        url, headers=writer._headers() | {"Content-Type": "application/octet-stream"},
        content=b"SalCAPA authorized scoped write diagnostic.\n",
    )
    print(f"KNOWLEDGE_DESTINATION_WRITE_HTTP={response.status_code}")
    print(f"KNOWLEDGE_DESTINATION_WRITE_GRAPH_CODE={safe_code(response)}")
    if response.status_code not in {200, 201}:
        return
    item = response.json()
    item_id = str(item.get("id", ""))
    if not re.fullmatch(r"[A-Za-z0-9_!.-]{8,256}", item_id):
        raise RuntimeError("Diagnostic item identity unavailable; cleanup required")
    delete_response = writer.client.delete(
        f"{GRAPH_ROOT}/drives/{KNOWLEDGE_DRIVE}/items/{item_id}",
        headers=writer._headers() | {"If-Match": str(item.get("eTag", "*"))},
    )
    print(f"KNOWLEDGE_DIAGNOSTIC_CLEANUP_HTTP={delete_response.status_code}")
    if delete_response.status_code != 204:
        raise RuntimeError("Diagnostic item cleanup failed")


if __name__ == "__main__":
    main()
