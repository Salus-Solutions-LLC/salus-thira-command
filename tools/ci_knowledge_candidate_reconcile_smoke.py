"""Regression coverage for bounded candidate metadata reconciliation."""

from __future__ import annotations

import json
import os
from pathlib import Path
import sqlite3
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
from tools import live_knowledge_candidate_reconcile as reconcile


ROOT = Path(__file__).resolve().parents[1]
JOB_NAME = "salcapa-cand-reconcile-b48224"


def check_azure_job_name_contract() -> None:
    assert 2 <= len(JOB_NAME) <= 32, len(JOB_NAME)
    assert JOB_NAME[0].isalpha() and JOB_NAME[-1].isalnum(), JOB_NAME
    assert JOB_NAME.replace("-", "").isalnum() and JOB_NAME == JOB_NAME.lower(), JOB_NAME
    workflow = (ROOT / ".github/workflows/salcapa-knowledge-candidate-reconcile.yml").read_text(encoding="utf-8")
    bicep = (ROOT / "infra/azure/knowledge-candidate-reconcile-job.bicep").read_text(encoding="utf-8")
    assert workflow.count(f"JOB_NAME={JOB_NAME}") == 2
    assert f"name: '{JOB_NAME}'" in bicep
    assert "salcapa-candidate-reconcile-b48224" not in workflow + bicep


def check() -> None:
    check_azure_job_name_contract()
    with tempfile.TemporaryDirectory() as directory:
        conn = sqlite3.connect(os.path.join(directory, "candidate-reconcile.sqlite"))
        conn.row_factory = sqlite3.Row
        conn.executescript("""
        CREATE TABLE m365_knowledge_candidates(
          id INTEGER PRIMARY KEY,status TEXT NOT NULL,classification_json TEXT NOT NULL,
          destination_drive_id TEXT NOT NULL,destination_item_id TEXT NOT NULL,
          destination_web_url TEXT NOT NULL,destination_etag TEXT NOT NULL,
          source_archive_item_id TEXT NOT NULL,source_archive_web_url TEXT NOT NULL,
          source_archive_etag TEXT NOT NULL,source_archived_at TEXT NOT NULL
        );
        CREATE TABLE m365_knowledge_events(
          id INTEGER PRIMARY KEY AUTOINCREMENT,candidate_id INTEGER NOT NULL,
          event_type TEXT NOT NULL,actor TEXT NOT NULL,detail_json TEXT NOT NULL,
          created_at TEXT NOT NULL
        );
        """)
        complete = json.dumps({"extraction": {"status": "Complete"}})
        review = json.dumps({"extraction": {"status": "Review Required",
            "disposition": "Governed Extraction Review Required"}})
        conn.execute("INSERT INTO m365_knowledge_candidates VALUES(?,?,?,?,?,?,?,?,?,?,?)",
                     (1, "Automatic Retry Required", complete, "d", "i", "u", "e", "a", "w", "t", "now"))
        conn.execute("INSERT INTO m365_knowledge_events(candidate_id,event_type,actor,detail_json,created_at) VALUES(?,?,?,?,?)",
                     (1, "AutomaticallyPromotedVerifiedAndArchived", "test", "{}", "now"))
        for candidate_id in range(2, 10):
            conn.execute("INSERT INTO m365_knowledge_candidates VALUES(?,?,?,?,?,?,?,?,?,?,?)",
                         (candidate_id, "Automatic Retry Required", review, "", "", "", "", "", "", "", ""))
        for candidate_id in range(10, 18):
            conn.execute("INSERT INTO m365_knowledge_candidates VALUES(?,?,?,?,?,?,?,?,?,?,?)",
                         (candidate_id, "Approved for Promotion", complete, "", "", "", "", "", "", "", ""))
        result = reconcile.reconcile(conn)
        assert result["stale_promoted_reconciled"] == 1, result
        assert result["review_blocked_routed"] == 8, result
        assert result["audit_events"] == 9 and result["open_remaining"] == 16, result
        assert conn.execute("SELECT status FROM m365_knowledge_candidates WHERE id=1").fetchone()[0] == "Ingested and Verified"
        assert conn.execute("SELECT COUNT(*) FROM m365_knowledge_candidates WHERE status='Pending Review'").fetchone()[0] == 8
        assert conn.execute("SELECT COUNT(*) FROM m365_knowledge_events").fetchone()[0] == 10
        conn.close()
    print("KNOWLEDGE_CANDIDATE_RECONCILE_PASS")


if __name__ == "__main__":
    check()
