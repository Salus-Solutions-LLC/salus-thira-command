import json
import os
import sqlite3
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from salcapa_knowledge_consideration import consider


class Connection:
    backend = "sqlite"

    def __init__(self):
        self.conn = sqlite3.connect(":memory:")
        self.conn.row_factory = sqlite3.Row

    def execute(self, *args):
        return self.conn.execute(*args)

    def executescript(self, value):
        return self.conn.executescript(value)

    def commit(self):
        return self.conn.commit()


def main():
    conn = Connection()
    conn.executescript("""
      CREATE TABLE m365_bulk_items(
        item_id TEXT, name TEXT, metadata_json TEXT, status TEXT, reason TEXT,
        kind TEXT, updated_at INTEGER
      );
      CREATE TABLE m365_knowledge_candidates(
        id INTEGER, source_item_id TEXT, source_name TEXT, source_relative_path TEXT,
        source_sha256 TEXT, source_modified_at TEXT, source_owner TEXT, status TEXT,
        target_folder TEXT, classification_json TEXT
      );
      CREATE TABLE m365_knowledge_holds(
        source_item_id TEXT, source_name TEXT, source_relative_path TEXT,
        source_area TEXT, hold_reason TEXT, status TEXT
      );
    """)
    for number in range(3):
        conn.execute(
            "INSERT INTO m365_bulk_items VALUES(?,?,?,?,?,?,?)",
            (f"item-{number}", f"File {number}.txt",
             json.dumps({"relative_path": f"Area/File {number}.txt"}),
             "Done", "", "file", number),
        )
    classification = {
        "extraction": {"status": "Complete", "text": "Continuity strategy and recovery data"},
        "citation_metadata": {"document_title": "Continuity Source"},
    }
    for number in range(3):
        conn.execute(
            "INSERT INTO m365_knowledge_candidates VALUES(?,?,?,?,?,?,?,?,?,?)",
            (number + 1, f"item-{number}", f"File {number}.txt", f"Area/File {number}.txt",
             "a" * 64, "2026-11-02", "Salus", "Ingested and Verified",
             "05 Research and Reference", json.dumps(classification, sort_keys=True)),
        )
    conn.execute(
        "INSERT INTO m365_knowledge_candidates VALUES(?,?,?,?,?,?,?,?,?,?)",
        (4, "historical-only", "Historical File.txt", "Historical/File.txt", "b" * 64,
         "2026-10-01", "Salus", "Ingested and Verified", "05 Research and Reference",
         json.dumps(classification, sort_keys=True)),
    )
    conn.execute(
        "INSERT INTO m365_knowledge_holds VALUES(?,?,?,?,?,?)",
        ("item-3", "Held continuity image", "Area/Held.jpg", "Does Not Upload",
         "governed hold", "Governed Hold"),
    )
    os.environ["SALUS_KNOWLEDGE_MINIMUM_BOUNDARY_FILES"] = "4"
    result = consider(conn, "continuity strategy", "test-actor", "2026-11-02T12:00:00Z")
    assert result["coverage"] == {
        "boundary_files": 4,
        "represented_files": 5,
        "considered_files": 5,
        "historical_additional_representations": 1,
        "matched_files": 5,
        "considered_without_match": 0,
        "content_available_files": 4,
        "metadata_only_or_unresolved_files": 1,
        "governed_hold_files": 1,
        "all_boundary_files_considered": True,
        "all_represented_files_considered": True,
    }
    assert result["results"][0]["content_preview"]
    assert any(row["relative_path"] == "Historical/File.txt" for row in result["results"])
    assert any(row["representation"] == "Governed hold metadata" for row in result["results"])
    assert result["protected_member_access"] is False
    assert result["assignment_or_release_authority"] is False
    receipt = conn.execute(
        "SELECT boundary_count,considered_count FROM m365_knowledge_consideration_receipts"
    ).fetchone()
    assert (receipt["boundary_count"], receipt["considered_count"]) == (4, 5)
    print("knowledge consideration smoke passed")


if __name__ == "__main__":
    main()
