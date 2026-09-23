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
