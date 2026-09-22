#!/usr/bin/env python3
"""Regression checks for governed knowledge classification and promotion."""

import hashlib
import sqlite3
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from salcapa_knowledge_promotion import (
    ClassificationCommand, KnowledgeDestinationConfig, GraphKnowledgeWriter,
    PENDING_PREFIX, TARGETS,
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
    assert "Human approval is required before promotion" in module
    assert "Changed - Re-review Required" in module
    assert "Knowledge destination verification failed" in module
    assert "untrusted verification location" in module
    assert "endswith(\".sharepoint.com\")" in module
    assert "SALUS_M365_PROCESSED_INTAKE_FOLDER_ITEM_ID" in module
    assert "archive_verified_source" in module
    assert "Ingested and Verified" in module
    assert ".delete(" not in module
    assert "If-Match" in module
    assert "m365_knowledge_events" in module
    print("M365_KNOWLEDGE_PROMOTION_PASS")


if __name__ == "__main__":
    main()
