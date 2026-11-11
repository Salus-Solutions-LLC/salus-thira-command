"""Smoke checks for the bounded Knowledge pending-review promotion."""

from __future__ import annotations

import hashlib
import json
import sqlite3
import sys
from pathlib import Path
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from salcapa_knowledge_promotion import _create_tables
from tools import live_knowledge_pending_review_promote as promotion


def _classification(category: str) -> str:
    if category == "extraction":
        evidence = {
            "extraction": {
                "status": "Review Required",
                "disposition": "Governed Extraction Review Required",
                "retry_eligible": False,
            }
        }
    else:
        evidence = {
            "extraction": {"status": "Complete"},
            "source_reconciliation": {
                "status": "Review Required",
                "disposition": "Governed Missing Source Reconciliation Required",
                "successor_match": "None",
                "boundary_files_rechecked": 22_377,
            },
        }
    evidence["permit_products"] = ["SalCAPA"]
    evidence["target_folder"] = "05 Research and Reference"
    return json.dumps(evidence, sort_keys=True)


def _database() -> sqlite3.Connection:
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    _create_tables(conn)
    for candidate_id in range(1, 14):
        content = f"exact-source-{candidate_id}".encode()
        conn.execute(
            "INSERT INTO m365_knowledge_candidates("
            "id,source_drive_id,source_item_id,source_name,source_relative_path,"
            "source_etag,source_sha256,source_size,source_modified_at,source_owner,"
            "discovered_at,status,decision,target_folder,classification_json) "
            "VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (
                candidate_id,
                "intake-drive",
                f"source-item-{candidate_id:02d}",
                f"Document {candidate_id}.txt",
                f"10 Pending Classification/Document {candidate_id}.txt",
                f'etag-{candidate_id}',
                hashlib.sha256(content).hexdigest(),
                len(content),
                "2026-11-01T00:00:00+00:00",
                "",
                "2026-11-02T00:00:00+00:00",
                "Pending Review",
                "Approved",
                "05 Research and Reference",
                _classification("extraction" if candidate_id <= 8 else "reconciliation"),
            ),
        )
    conn.commit()
    return conn


class _FakeIntake:
    available = 13

    def __init__(self, _config):
        pass

    def list_files(self):
        return [
            {
                "id": f"source-item-{candidate_id:02d}",
                "name": f"Document {candidate_id}.txt",
                "etag": f"etag-{candidate_id}",
            }
            for candidate_id in range(1, self.available + 1)
        ]

    def read_listed_document(self, row, *, access_classification):
        del access_classification
        candidate_id = int(row["id"].rsplit("-", 1)[1])
        content = f"exact-source-{candidate_id}".encode()
        return SimpleNamespace(
            item_id=row["id"],
            etag=row["etag"],
            sha256=hashlib.sha256(content).hexdigest(),
            name=row["name"],
            content=content,
            size=len(content),
        )


class _FakeWriter:
    def __init__(self, _intake_config, _destination):
        self.destination = SimpleNamespace(
            drive_id="knowledge-drive", processed_folder_item_id="processed-folder"
        )

    def put_verified(self, _folder, name, _content, sha256):
        return {
            "item_id": "destination-" + sha256[:12],
            "web_url": "https://example.sharepoint.com/" + name.replace(" ", "%20"),
            "etag": "destination-etag",
        }

    def archive_verified_source(self, item_id, _etag, name, _sha256):
        return {
            "item_id": item_id,
            "web_url": "https://example.sharepoint.com/archive/" + name.replace(" ", "%20"),
            "etag": "archive-etag",
        }

    def verify_already_archived_source(self, _item_id, _sha256):
        return None


def _run(available: int) -> tuple[dict[str, int], sqlite3.Connection]:
    conn = _database()
    emitted: list[tuple[str, str | int]] = []
    ids = promotion.approve_exact_boundary(conn, lambda key, value: emitted.append((key, value)))
    assert ids == list(range(1, 14))
    assert conn.execute(
        "SELECT COUNT(*) FROM m365_knowledge_candidates WHERE status='Approved for Promotion'"
    ).fetchone()[0] == 13
    assert conn.execute(
        "SELECT COUNT(*) FROM m365_knowledge_events WHERE event_type=?",
        (promotion.APPROVAL_EVENT,),
    ).fetchone()[0] == 13
    promotion.GovernedM365Config = SimpleNamespace(
        from_environment=lambda: SimpleNamespace(drive_id="intake-drive")
    )
    promotion.KnowledgeDestinationConfig = SimpleNamespace(from_environment=lambda: SimpleNamespace())
    _FakeIntake.available = available
    promotion.GovernedM365Intake = _FakeIntake
    promotion.GraphKnowledgeWriter = _FakeWriter
    result = promotion.promote_exact_boundary(
        conn, ids, lambda key, value: emitted.append((key, value))
    )
    return result, conn


def main() -> None:
    workflow = (ROOT / ".github/workflows/salcapa-knowledge-pending-review-promotion.yml").read_text(
        encoding="utf-8"
    )
    bicep = (ROOT / "infra/azure/knowledge-pending-review-promotion-job.bicep").read_text(
        encoding="utf-8"
    )
    live = (ROOT / "tools/live_knowledge_pending_review_promote.py").read_text(
        encoding="utf-8"
    )
    assert "environment: salcapa-dev-approval" in workflow
    assert "push:" in workflow and "workflow_dispatch:" not in workflow
    assert "knowledge-pending-review-promotion-20261111.json" in workflow
    assert 'test "$GITHUB_RUN_ATTEMPT" = "1"' in workflow
    assert "--diff-filter=A" in workflow
    assert "triggerType\":\"Manual" in workflow
    assert "DRAINED=false" in workflow
    assert "triggerType\":\"Schedule" in workflow
    assert "*/2 * * * *" in workflow
    assert "d7b558b543431d2ed06dc9121d99f3fe409dd0dcde267ed06e87e956d28a4f14" in workflow
    assert "grep -E 'KNOWLEDGE_REVIEW_PROMOTION_[A-Z0-9_]+='" in workflow
    assert "replicaRetryLimit: 0" in bicep
    assert "SALUS_M365_PROCESSED_INTAKE_FOLDER_ITEM_ID" in bicep
    assert "SALUS_POSTGRES_AUTH" in bicep
    assert "public_release_authorized\": False" in live
    assert "source_substitution_authorized\": False" in live

    result, conn = _run(13)
    assert result == {
        "promoted": 13,
        "already_complete": 0,
        "failed_closed": 0,
        "verified_complete": 13,
    }
    assert conn.execute(
        "SELECT COUNT(*) FROM m365_knowledge_candidates WHERE status='Ingested and Verified'"
    ).fetchone()[0] == 13
    conn.close()

    result, conn = _run(8)
    assert result["promoted"] == 8
    assert result["failed_closed"] == 5
    assert result["verified_complete"] == 8
    assert conn.execute(
        "SELECT COUNT(*) FROM m365_knowledge_candidates WHERE status='Automatic Retry Required'"
    ).fetchone()[0] == 5
    assert conn.execute(
        "SELECT COUNT(*) FROM m365_knowledge_events WHERE event_type=?",
        (promotion.FAILURE_EVENT,),
    ).fetchone()[0] == 5
    conn.close()

    print("Knowledge pending-review approval and promotion smoke checks passed.")


if __name__ == "__main__":
    main()
