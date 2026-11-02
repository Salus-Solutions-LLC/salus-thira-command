"""Regression coverage for the four-item governed destination repair."""

from __future__ import annotations

import hashlib
import json
import sqlite3
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from tools import live_knowledge_destination_repair as repair


class Destination:
    drive_id = "knowledge-drive"


class Writer:
    destination = Destination()

    def __init__(self) -> None:
        self.contents: dict[str, bytes] = {}

    def verify_already_archived_source(self, item_id, sha256, *, include_content=False):
        content = self.contents[item_id]
        assert hashlib.sha256(content).hexdigest() == sha256
        return {
            "item_id": item_id, "web_url": f"https://salus.sharepoint.com/{item_id}",
            "etag": f"etag-{item_id}", "content": content,
        }

    def _resolve_folder(self, folder_name):
        assert folder_name == "Salus Governed Knowledge"
        return "knowledge-folder"


def schema(conn) -> None:
    conn.executescript("""
    CREATE TABLE m365_knowledge_candidates (
      id INTEGER PRIMARY KEY, source_drive_id TEXT, source_item_id TEXT,
      source_name TEXT, source_relative_path TEXT, source_etag TEXT,
      source_sha256 TEXT, source_size INTEGER, source_modified_at TEXT,
      source_owner TEXT, discovered_at TEXT, status TEXT, decision TEXT,
      target_folder TEXT, classification_json TEXT, reviewed_by TEXT,
      reviewed_at TEXT, review_rationale TEXT, destination_drive_id TEXT DEFAULT '',
      destination_item_id TEXT DEFAULT '', destination_web_url TEXT DEFAULT '',
      destination_etag TEXT DEFAULT '', promoted_at TEXT DEFAULT '',
      source_removed_at TEXT DEFAULT '', source_archived_at TEXT DEFAULT '',
      source_archive_item_id TEXT DEFAULT '', source_archive_web_url TEXT DEFAULT '',
      source_archive_etag TEXT DEFAULT ''
    );
    CREATE TABLE m365_knowledge_events (
      id INTEGER PRIMARY KEY AUTOINCREMENT, candidate_id INTEGER,
      event_type TEXT, actor TEXT, detail_json TEXT, created_at TEXT
    );
    CREATE TABLE m365_bulk_items (drive_id TEXT, item_id TEXT);
    """)


def candidate(conn, candidate_id: int, status: str, writer: Writer) -> None:
    item_id = f"source-{candidate_id:08d}"
    content = f"governed-{candidate_id}".encode()
    sha256 = hashlib.sha256(content).hexdigest()
    writer.contents[item_id] = content
    rationale = (
        "Automatically processed under policy."
        if status == "Approved for Promotion"
        else "Approved knowledge file could not be written"
    )
    conn.execute(
        "INSERT INTO m365_knowledge_candidates"
        "(id,source_drive_id,source_item_id,source_name,source_relative_path,source_etag,"
        "source_sha256,source_size,source_modified_at,source_owner,discovered_at,status,"
        "decision,target_folder,classification_json,reviewed_by,reviewed_at,review_rationale) "
        "VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
        (
            candidate_id, "intake-drive", item_id, f"file-{candidate_id}.pdf",
            f"90 Processed Intake/file-{candidate_id}.pdf", f"etag-{item_id}", sha256,
            len(content), "2026-10-31T00:00:00Z", "", "2026-10-31T00:00:00Z",
            status, "Approved", "Salus Governed Knowledge",
            json.dumps({"extraction": {"status": "Complete"}}), "worker",
            "2026-10-31T00:00:00Z", rationale,
        ),
    )


def check() -> None:
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    schema(conn)
    writer = Writer()
    for candidate_id in range(1, 14):
        conn.execute(
            "INSERT INTO m365_knowledge_candidates"
            "(id,source_drive_id,source_item_id,source_name,source_relative_path,source_etag,"
            "source_sha256,source_size,source_modified_at,source_owner,discovered_at,status,"
            "decision,target_folder,classification_json,reviewed_by,reviewed_at,review_rationale) "
            "VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (
                candidate_id, "d", f"pending-{candidate_id:08d}", "p.txt", "p.txt", "e",
                "0" * 64, 1, "t", "", "t", "Pending Review", "Approved", "Review",
                json.dumps({"extraction": {"status": "Review Required"}}), "", "", "review",
            ),
        )
    for candidate_id in range(14, 17):
        candidate(conn, candidate_id, "Approved for Promotion", writer)
    candidate(conn, 17, "Automatic Retry Required", writer)
    conn.commit()

    def probe(_writer, _folder, name, _sha):
        if name.startswith("file-17") and ".repair." not in name:
            if name.endswith(".original.bin"):
                return {"state": "missing"}
            return {"state": "mismatch"}
        return {"state": "missing"}

    uploaded = []
    def upload(_writer, _folder, name, content, sha256):
        assert hashlib.sha256(content).hexdigest() == sha256
        uploaded.append(name)
        return {
            "item_id": f"destination-{len(uploaded):08d}",
            "web_url": f"https://salus.sharepoint.com/destination-{len(uploaded)}",
            "etag": f"destination-etag-{len(uploaded)}",
        }

    result = repair.repair(conn, writer, probe=probe, upload=upload)
    assert result["destinations_verified"] == 4
    assert result["mismatched_objects_preserved"] == 1
    assert len(uploaded) == 4 and sum(".repair." in name for name in uploaded) == 1
    rows = conn.execute(
        "SELECT status,destination_item_id,source_archive_item_id,classification_json "
        "FROM m365_knowledge_candidates WHERE id>=14 ORDER BY id"
    ).fetchall()
    assert all(row["status"] == "Ingested and Verified" for row in rows)
    assert all(row["destination_item_id"] and row["source_archive_item_id"] for row in rows)
    assert all(json.loads(row["classification_json"])["destination_repair"]["status"] == "Verified" for row in rows)
    assert conn.execute(
        "SELECT COUNT(*) FROM m365_knowledge_events WHERE event_type=?", (repair.EVENT_TYPE,),
    ).fetchone()[0] == 4

    root = Path(__file__).resolve().parents[1]
    workflow = (root / ".github/workflows/salcapa-knowledge-destination-repair.yml").read_text()
    bicep = (root / "infra/azure/knowledge-destination-repair-job.bicep").read_text()
    module = (root / "tools/live_knowledge_destination_repair.py").read_text()
    promotion = (root / "salcapa_knowledge_promotion.py").read_text()
    assert "ACTIVATION=deploy/azure/activations/application-dev.json" in workflow
    assert "DESTINATION_REPAIR_COMPLETE=1" in workflow
    assert "environment: salcapa-dev-approval" in workflow
    assert "replicaRetryLimit: 0" in bicep
    assert "_upload_large(item_path, content)" in module
    assert '"@microsoft.graph.conflictBehavior": "fail"' in promotion
    assert "GovernedDestinationRepairedAndArchiveReconciled" in module
    assert ".delete(" not in module and ".patch(" not in module


if __name__ == "__main__":
    check()
    print("knowledge destination repair smoke passed")
