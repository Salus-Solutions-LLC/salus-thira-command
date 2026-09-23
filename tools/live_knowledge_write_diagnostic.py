#!/usr/bin/env python3
"""Bounded live Graph write and pending-extraction diagnosis without source disclosure."""

from __future__ import annotations

import hashlib
import re
import uuid
from urllib.parse import quote, urlparse

from salcapa_knowledge_promotion import (
    GRAPH_ROOT, GraphKnowledgeWriter, KnowledgeDestinationConfig,
    PENDING_PREFIX, _extract_all_accessible_content, automatic_classification,
)
from salcapa_m365_intake import GovernedM365Config, GovernedM365Intake, M365IntakeError

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
    processed_names = {row["name"].casefold() for row in intake.list_files() if row["relative_path"].startswith("90 Processed Intake/")}
    pending = []
    for row in files:
        document = intake.read_document(row["id"], access_classification="Salus Internal")
        extraction = _extract_all_accessible_content(document)
        extension = document.name.rsplit(".", 1)[-1].lower() if "." in document.name else "none"
        if extension not in {"pdf", "docx", "txt", "xlsx", "pptx", "csv", "png", "jpg"}:
            extension = "other"
        print(f"PENDING_ARCHIVE_NAME_CONFLICT extension={extension} conflict={document.name.casefold() in processed_names}", flush=True)
        pending.append((extension, document.name, document.sha256, len(document.content)))
        code = str(extraction.get("failure_code", "none"))
        if not re.fullmatch(r"[A-Z0-9_]+|none", code):
            code = "unavailable"
        print(f"PENDING_EXTRACTION extension={extension} status={extraction['status']} code={code}")
        classification, _ = automatic_classification(document, duplicate=False)
        print(f"PENDING_CLASSIFICATION extension={extension} target={classification['target_folder']}", flush=True)
        fresh = intake.client.get(
            f"{GRAPH_ROOT}/drives/{intake_config.drive_id}/items/{document.item_id}",
            headers={"Authorization": f"Bearer {intake._graph_token()}"},
        )
        fresh_etag = str(fresh.json().get("eTag", "")) if fresh.status_code == 200 else ""
        print(f"PENDING_SOURCE_VERSION extension={extension} http={fresh.status_code} current={fresh_etag == document.etag}", flush=True)
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
                    if reason == "other" and exc.code == "PDF_ACTIVE_CONTENT":
                        from pypdf import PdfReader
                        from tools.salcapa_pdf_worker import _resolve
                        reader = PdfReader(path, strict=True, root_object_recovery_limit=10_000)
                        try:
                            root = _resolve(reader.trailer["/Root"])
                            names = _resolve(root.get("/Names")) if root.get("/Names") is not None else {}
                            root_active = any(key in root for key in
                                              ("/OpenAction", "/AA", "/AcroForm", "/Collection", "/RichMedia"))
                            named_active = any(key in names for key in ("/EmbeddedFiles", "/JavaScript"))
                            page_active = any(any(key in page for key in ("/AA", "/RichMedia"))
                                              for page in reader.pages)
                            annotation_active = False
                            annotation_invalid = False
                            for page in reader.pages:
                                annots = page.get("/Annots")
                                if annots is not None:
                                    try:
                                        annotation_active |= len(_resolve(annots)) != 0
                                    except (TypeError, ValueError, KeyError, AttributeError):
                                        annotation_invalid = True
                            print("PENDING_PDF_ACTIVE_FLAGS=" + ",".join(
                                str(int(flag)) for flag in
                                (root_active, named_active, page_active,
                                 annotation_active, annotation_invalid)
                            ))
                        finally:
                            reader.close()
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
    for extension, source_name, source_sha256, source_size in pending:
        readback = writer.client.get(
            f"{GRAPH_ROOT}/drives/{KNOWLEDGE_DRIVE}/items/{folder_id}:/"
            f"{quote(source_name, safe='')}:/content",
            headers=writer._headers(),
        )
        host = (urlparse(readback.headers.get("Location", "")).hostname or "").lower()
        host_class = (
            "sharepoint.com" if host.endswith(".sharepoint.com") else
            "sharepointonline.com" if host.endswith(".sharepointonline.com") else
            "none" if not host else "other"
        )
        print(f"DESTINATION_READBACK extension={extension} http={readback.status_code} redirect_host={host_class}")
        if readback.status_code == 200:
            print(f"DESTINATION_BYTES extension={extension} size_match={len(readback.content) == source_size} sha_match={hashlib.sha256(readback.content).hexdigest() == source_sha256}")
        elif readback.status_code in {302, 303, 307, 308} and host_class == "sharepoint.com":
            downloaded = writer.client.get(readback.headers["Location"])
            print(f"DESTINATION_BYTES extension={extension} http={downloaded.status_code} size_match={len(downloaded.content) == source_size} sha_match={hashlib.sha256(downloaded.content).hexdigest() == source_sha256}")
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

    # Exercise the application's source-drive move with a temporary item outside
    # the watched Pending Classification folder. Always clean up the test item.
    intake_drive = intake_config.drive_id
    test_name = f"SalCAPA-Archive-Diagnostic-{uuid.uuid4().hex}.txt"
    test_url = (
        f"{GRAPH_ROOT}/drives/{intake_drive}/items/{intake_config.folder_item_id}:/"
        f"{quote(test_name, safe='')}:/content"
    )
    test_item_id = ""
    try:
        created = writer.client.put(
            test_url, headers=writer._headers() | {"Content-Type": "text/plain"},
            content=b"SalCAPA scoped archive diagnostic.\\n",
        )
        print(f"SOURCE_DIAGNOSTIC_CREATE_HTTP={created.status_code}")
        print(f"SOURCE_DIAGNOSTIC_CREATE_CODE={safe_code(created)}")
        if created.status_code not in {200, 201}:
            return
        test_item = created.json()
        test_item_id = str(test_item.get("id", ""))
        if not re.fullmatch(r"[A-Za-z0-9_!.-]{8,256}", test_item_id):
            raise RuntimeError("Source diagnostic identity unavailable")
        moved = writer.client.patch(
            f"{GRAPH_ROOT}/drives/{intake_drive}/items/{test_item_id}",
            headers=writer._headers() | {
                "If-Match": str(test_item.get("eTag", "")),
                "Content-Type": "application/json",
                "Accept": "application/json",
            },
            json={"parentReference": {"id": PROCESSED_FOLDER}},
        )
        print(f"SOURCE_DIAGNOSTIC_ARCHIVE_HTTP={moved.status_code}")
        print(f"SOURCE_DIAGNOSTIC_ARCHIVE_CODE={safe_code(moved)}")
        if moved.status_code == 200:
            actual_parent = str((moved.json().get("parentReference") or {}).get("id", ""))
            print(f"SOURCE_DIAGNOSTIC_ARCHIVE_PARENT_MATCH={actual_parent == PROCESSED_FOLDER}")
    finally:
        if test_item_id:
            cleanup = writer.client.delete(
                f"{GRAPH_ROOT}/drives/{intake_drive}/items/{test_item_id}",
                headers=writer._headers(),
            )
            print(f"SOURCE_DIAGNOSTIC_CLEANUP_HTTP={cleanup.status_code}")
            if cleanup.status_code != 204:
                raise RuntimeError("Source diagnostic cleanup failed")


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        # Type only: names, paths, and document contents must stay out of Actions logs.
        print(f"SAFE_DIAGNOSTIC_ERROR_TYPE={type(exc).__name__}", flush=True)
        raise SystemExit(1) from None
