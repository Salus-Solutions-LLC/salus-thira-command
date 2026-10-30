"""Regression coverage for aggregate extraction-retry readiness evidence."""

from __future__ import annotations

import json
import os
import sqlite3
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
from tools import live_knowledge_retry_readiness as readiness


def check() -> None:
    with tempfile.TemporaryDirectory() as directory:
        conn = sqlite3.connect(os.path.join(directory, "readiness.sqlite"))
        conn.row_factory = sqlite3.Row
        conn.executescript("""
        CREATE TABLE m365_knowledge_candidates(
          id INTEGER PRIMARY KEY,classification_json TEXT NOT NULL
        );
        CREATE TABLE m365_bulk_extraction_checks(
          candidate_id INTEGER PRIMARY KEY,attempts INTEGER NOT NULL,
          next_attempt INTEGER NOT NULL,lease_until INTEGER NOT NULL
        );
        """)
        due = {"extraction": {
            "status": readiness.RETRY_STATUS,
            "failure_code": "PDF_RESOURCE_LIMIT",
        }}
        backoff = {"extraction": {
            "status": readiness.RETRY_STATUS,
            "failure_code": "IMAGE_RESOURCE_LIMIT",
        }}
        conn.execute("INSERT INTO m365_knowledge_candidates VALUES(?,?)", (1, json.dumps(due)))
        conn.execute("INSERT INTO m365_knowledge_candidates VALUES(?,?)", (2, json.dumps(backoff)))
        conn.execute("INSERT INTO m365_bulk_extraction_checks VALUES(?,?,?,?)", (2, 6, 2000, 0))
        result = readiness.collect(conn, clock=1000)
        assert result["remaining"] == 2 and result["resolved_since_transition"] == 731, result
        assert result["due"] == 1 and result["backoff"] == 1 and result["leased"] == 0, result
        assert result["without_check"] == 1 and result["with_check"] == 1, result
        assert result["attempts_0"] == 1 and result["attempts_6_plus"] == 1, result
        assert result["code_pdf_resource_limit"] == 1, result
        assert result["code_image_resource_limit"] == 1, result
        conn.execute(
            "INSERT INTO m365_knowledge_candidates VALUES(?,?)",
            (3, json.dumps({"extraction": {
                "status": readiness.RETRY_STATUS,
                "failure_code": "DOCUMENT_PACKAGE_INVALID",
            }})),
        )
        try:
            readiness.collect(conn, clock=1000)
        except RuntimeError as exc:
            assert "approved boundary" in str(exc), exc
        else:
            raise AssertionError("Unexpected retry code did not fail closed")
        conn.close()
    print("KNOWLEDGE_RETRY_READINESS_PASS")


if __name__ == "__main__":
    check()
