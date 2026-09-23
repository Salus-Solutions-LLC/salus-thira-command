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
    PENDING_PREFIX, TARGETS, automatic_classification,
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
    print("M365_KNOWLEDGE_PROMOTION_PASS")


if __name__ == "__main__":
    main()
