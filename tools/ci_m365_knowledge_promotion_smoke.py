#!/usr/bin/env python3
"""Regression checks for governed knowledge classification and promotion."""

import hashlib
import sqlite3
import sys
from pathlib import Path
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from salcapa_knowledge_promotion import (
    ClassificationCommand, KnowledgeDestinationConfig, GraphKnowledgeWriter,
    PENDING_PREFIX, TARGETS, _init_tables, automatic_classification, refresh_archived_extraction,
)


def main():
    assert PENDING_PREFIX == "10 Pending Classification/"
    assert "01 Salus Doctrine and Methodologies" in TARGETS
    approved = ClassificationCommand(
        decision="Approved",
        target_folder="01 Salus Doctrine and Methodologies",
        rationale="Reviewed and approved as current Salus doctrine.",
        permit_products=["ChatGPT", "SalCAPA", "SalINTEL"],
    )
    assert approved.decision == "Approved"
    assert approved.permit_products == ["ChatGPT", "SalCAPA", "SalINTEL"]
    assessment = SimpleNamespace(
        name="Strategic assessment research.txt",
        content=b"Approved internal reference material.",
        content_type="text/plain",
    )
    automated, reason = automatic_classification(assessment, duplicate=False)
    assert reason == ""
    assert automated["target_folder"] == "05 Research and Reference"
    assert automated["permit_products"] == ["SalCAPA", "SalINTEL", "SalTHIRA"]
    citation = automated["citation_metadata"]
    assert citation["document_title"] == "Strategic assessment research"
    assert citation["citation_key"].startswith("sha256:")
    assert citation["source_sha256"] == hashlib.sha256(assessment.content).hexdigest()
    assert citation["locator_scheme"] == "content section"
    sensitive, reason = automatic_classification(
        SimpleNamespace(
            name="personnel assessment.txt",
            content=b"CONFIDENTIAL personnel material",
            content_type="text/plain",
        ),
        duplicate=False,
    )
    assert reason == ""
    assert sensitive["decision"] == "Approved"
    assert "Sensitive" in sensitive["processing_flags"]
    ambiguous, reason = automatic_classification(
        SimpleNamespace(name="document.txt", content=b"routine material", content_type="text/plain"), duplicate=False
    )
    assert reason == ""
    assert ambiguous["target_folder"] == "05 Research and Reference"
    assert "Default Research Classification" in ambiguous["processing_flags"]
    duplicate, reason = automatic_classification(assessment, duplicate=True)
    assert reason == ""
    assert duplicate["decision"] == "Approved"
    assert "Duplicate" in duplicate["processing_flags"]
    binary, reason = automatic_classification(
        SimpleNamespace(
            name="Strategic Assessment_ ISIS-K Threat to U.S. Hospitals - 19 March 2025.pdf",
            content=b"CONFIDENTIAL",
            content_type="application/pdf",
        ),
        duplicate=False,
    )
    assert reason == ""
    assert binary["decision"] == "Approved"
    assert binary["extraction"]["status"] == "Automatic Retry Required"
    assert "Automatic Extraction Retry Required" in binary["processing_flags"]
    binary_original = SimpleNamespace(
        name="Strategic Assessment_ ISIS-K Threat to U.S. Hospitals - 19 March 2025.pdf",
        content=b"CONFIDENTIAL",
        content_type="application/pdf",
        sha256=hashlib.sha256(b"CONFIDENTIAL").hexdigest(),
    )
    pending_retry, retry_code = refresh_archived_extraction(
        binary, binary_original, binary_original.sha256
    )
    assert retry_code == "extraction_retry_required"
    assert pending_retry == binary
    mismatched, retry_code = refresh_archived_extraction(
        binary, binary_original, hashlib.sha256(b"other").hexdigest()
    )
    assert retry_code == "archived_source_hash_mismatch"
    assert mismatched == binary

    archived_text = b"Approved internal reference material."
    archived_doc = SimpleNamespace(
        name="Strategic assessment research.txt", content=archived_text,
        content_type="text/plain", sha256=hashlib.sha256(archived_text).hexdigest(),
    )
    retried = {
        **binary,
        "citation_metadata": {"citation_key": "sha256:immutable-source"},
    }
    completed, retry_code = refresh_archived_extraction(
        retried, archived_doc, archived_doc.sha256
    )
    assert not retry_code
    assert completed["extraction"]["status"] == "Complete"
    assert completed["citation_metadata"] == retried["citation_metadata"]
    assert "Automatic Extraction Retry Required" not in completed["processing_flags"]
    assert retried["extraction"]["status"] == "Automatic Retry Required"
    destination = KnowledgeDestinationConfig("12345678", "abcdefgh", "archive12")
    destination.validate()
    assert destination.processed_folder_item_id == "archive12"
    try:
        ClassificationCommand(decision="Approved", target_folder="Uncontrolled", rationale="This must be rejected.")
    except Exception:
        pass
    else:
        raise AssertionError("An uncontrolled destination was accepted")
    source = b"governed-knowledge"
    assert len(hashlib.sha256(source).hexdigest()) == 64
    original = b"office-original-byte-stream"
    original_hash = hashlib.sha256(original).hexdigest()

    class Response:
        def __init__(self, status, *, payload=None, content=b"", headers=None):
            self.status_code = status
            self._payload = payload or {}
            self.content = content
            self.headers = headers or {}

        def json(self):
            return self._payload

    class MutatingOfficeClient:
        def __init__(self):
            self.uploaded = []

        def get(self, url, **kwargs):
            if url.endswith("/children"):
                return Response(200, payload={"value": [{"id": "folder123", "name": "05 Research and Reference", "folder": {}}]})
            if url.endswith("/content"):
                return Response(302, headers={"Location": "https://tenant.sharepoint.com/download"})
            return Response(200, content=original if self.uploaded[-1].endswith(".original.bin") else original + b"changed")

        def put(self, url, **kwargs):
            self.uploaded.append(url.rsplit("/items/folder123:/", 1)[1].removesuffix(":/content"))
            return Response(201, payload={"id": "item12345", "webUrl": "https://tenant.sharepoint.com/doc", "eTag": "etag"})

    fake_client = MutatingOfficeClient()
    writer = GraphKnowledgeWriter(
        SimpleNamespace(managed_identity_client_id="unused"), destination,
        credential=object(), client=fake_client,
    )
    writer._headers = lambda: {}
    verified = writer.put_verified("05 Research and Reference", "example.docx", original, original_hash)
    assert verified["item_id"] == "item12345"
    assert len(fake_client.uploaded) == 2
    assert fake_client.uploaded[-1].endswith(f"example.{original_hash[:24]}.docx.{original_hash[:16]}.original.bin")
    # Same-title, different-content documents must get different library paths.
    class ExactClient:
        def __init__(self):
            self.uploaded = []
            self.data = b""

        def get(self, url, **kwargs):
            if url.endswith("/children"):
                return Response(200, payload={"value": [{"id": "folder123", "name": "05 Research and Reference", "folder": {}}]})
            if url.endswith("/content"):
                return Response(200, content=self.data)
            raise AssertionError(url)

        def put(self, url, **kwargs):
            self.uploaded.append(url)
            self.data = kwargs["content"]
            return Response(201, payload={"id": "item12345", "webUrl": "https://tenant.sharepoint.com/doc", "eTag": "etag"})

    exact_client = ExactClient()
    writer.client = exact_client
    for data in (b"first document", b"second document"):
        writer.put_verified("05 Research and Reference", "duplicate.pdf", data, hashlib.sha256(data).hexdigest())
    assert len(set(exact_client.uploaded)) == 2

    # Graph can reject a move when the processed folder already has that name.
    class ArchiveConflictClient:
        def __init__(self):
            self.calls = []

        def patch(self, url, **kwargs):
            self.calls.append((url, kwargs))
            if len(self.calls) == 1:
                return Response(409)
            return Response(200, payload={
                "id": "source123", "name": kwargs["json"]["name"],
                "parentReference": {"id": "processed123"},
                "webUrl": "https://tenant.sharepoint.com/processed",
                "eTag": "new-etag",
            })

    archive_client = ArchiveConflictClient()
    writer.client = archive_client
    writer.intake_config = SimpleNamespace(drive_id="intake123")
    writer.destination = SimpleNamespace(processed_folder_item_id="processed123")
    result = writer.archive_verified_source("source123", "original-etag", "duplicate.pdf", original_hash)
    assert result["item_id"] == "source123"
    assert len(archive_client.calls) == 2
    first, second = (call[1] for call in archive_client.calls)
    assert first["headers"]["If-Match"] == second["headers"]["If-Match"] == "original-etag"
    assert "name" not in first["json"]
    assert second["json"]["name"].startswith("duplicate.")
    assert second["json"]["name"].endswith(".pdf")
    assert first["json"]["parentReference"] == second["json"]["parentReference"]

    # Existing installations have a unique SHA index; migration must preserve
    # provenance for two separate source files containing identical bytes.
    connection = sqlite3.connect(":memory:")
    _init_tables(connection)
    connection.execute("DROP INDEX idx_m365_knowledge_sha_destination")
    connection.execute(
        "CREATE UNIQUE INDEX idx_m365_knowledge_sha_destination "
        "ON m365_knowledge_candidates(source_sha256,target_folder) "
        "WHERE status IN ('Promoted','Source Retained','Source Removed','Ingested and Verified')"
    )
    insert = (
        "INSERT INTO m365_knowledge_candidates "
        "(source_drive_id,source_item_id,source_name,source_relative_path,"
        "source_etag,source_sha256,source_size,source_modified_at,discovered_at,"
        "status,target_folder) VALUES (?,?,?,?,?,?,?,?,?,?,?)"
    )
    def record(item_id):
        connection.execute(insert, (
            "drive12345",item_id,"duplicate.pdf","10 Pending Classification/duplicate.pdf",
            "etag12345",original_hash,len(original),"2026-09-23","2026-09-23",
            "Ingested and Verified","05 Research and Reference",
        ))
    record("source12345")
    _init_tables(connection)
    record("source23456")
    assert connection.execute(
        "SELECT count(*) FROM m365_knowledge_candidates WHERE source_sha256=?",
        (original_hash,),
    ).fetchone()[0] == 2
    connection.close()

    module = open("salcapa_knowledge_promotion.py", encoding="utf-8").read()
    assert "Human approval is required before promotion" not in module
    assert "Changed - Re-review Required" not in module
    assert "Knowledge destination verification failed" in module
    assert "untrusted verification location" in module
    assert "endswith(\".sharepoint.com\")" in module
    assert "SALUS_M365_PROCESSED_INTAKE_FOLDER_ITEM_ID" in module
    assert "archive_verified_source" in module
    assert "AutomaticallyPromotedVerifiedAndArchived" in module
    assert "RoutedToExceptionReview" not in module
    assert "AutomaticExtractionRetryScheduled" in module
    assert "SALUS_KNOWLEDGE_SCAN_INTERVAL_SECONDS" in module
    assert '\"exception_review\": 0' in module
    assert "citation_metadata" in module
    assert "source_created_at" in module
    assert "source_web_url" in module
    assert "Ingested and Verified" in module
    assert ".delete(" not in module
    assert "If-Match" in module
    assert "m365_knowledge_events" in module
    assert "RETURNING id" in module
    assert "Automatic knowledge candidate identity was not returned" in module
    runtime = open("salcapa_runtime.py", encoding="utf-8").read()
    assert "from salcapa_knowledge_promotion import register_knowledge_promotion" in runtime
    assert "register_knowledge_promotion(core.app, core.__dict__)" in runtime
    assert "knowledge_processing" in runtime
    assert "last_error_code" in module
    assert "destination_write_denied" in module
    assert "last_retry_codes" in module
    print("M365_KNOWLEDGE_PROMOTION_PASS")


if __name__ == "__main__":
    main()
