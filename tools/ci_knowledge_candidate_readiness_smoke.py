"""Regression coverage for aggregate open-candidate readiness evidence."""

from __future__ import annotations

import json
import hashlib
import os
from pathlib import Path
import sqlite3
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
from tools import live_knowledge_candidate_readiness as readiness


ROOT = Path(__file__).resolve().parents[1]


def check_protected_graph_contract() -> None:
    workflow = (ROOT / ".github/workflows/salcapa-knowledge-candidate-readiness.yml").read_text(
        encoding="utf-8"
    )
    bicep = (ROOT / "infra/azure/knowledge-candidate-readiness-job.bicep").read_text(
        encoding="utf-8"
    )
    mapping = {
        "tenantId": "SALUS_OIDC_TENANT_ID",
        "applicationClientId": "SALUS_OIDC_CLIENT_ID",
        "driveId": "SALUS_M365_INTAKE_DRIVE_ID",
        "folderItemId": "SALUS_M365_INTAKE_FOLDER_ITEM_ID",
        "enterpriseFolderItemId": "SALUS_M365_ENTERPRISE_INTAKE_FOLDER_ITEM_ID",
        "knowledgeDriveId": "SALUS_M365_KNOWLEDGE_DRIVE_ID",
        "knowledgeFolderItemId": "SALUS_M365_KNOWLEDGE_FOLDER_ITEM_ID",
        "processedIntakeFolderItemId": "SALUS_M365_PROCESSED_INTAKE_FOLDER_ITEM_ID",
    }
    for parameter, environment in mapping.items():
        assert f'{parameter}="$(env_value {environment})"' in workflow
        assert f"param {parameter} string" in bicep
        assert f"name: '{environment}'" in bicep
    assert "ACTIVATION=deploy/azure/activations/application-dev.json" in workflow
    assert "EXPECTED_IMAGE=\"$(jq -er '.image_digest' \"$ACTIVATION\")\"" in workflow
    live = (ROOT / "tools/live_knowledge_candidate_readiness.py").read_text(
        encoding="utf-8"
    )
    main = live.split("def main() -> None:", 1)[1]
    assert "collect_source_preflight(" not in main
    assert "collect_processed_evidence(" not in main
    assert '"source_requests": 0' in live
    assert '"rows_changed": 0' in live


def check() -> None:
    check_protected_graph_contract()
    assert readiness.EXPECTED_INITIAL_STATUS_COUNTS == {
        "Pending Review": 13,
        "Approved for Promotion": 0,
        "Automatic Retry Required": 0,
        "Destination Verified": 0,
    }
    assert readiness.EXPECTED_PROMOTION_SCOPE_COUNTS == {
        "Approved for Promotion": 0,
        "Automatic Retry Required": 0,
    }
    assert readiness.EXPECTED_PENDING_REVIEW_COUNTS == {
        "extraction_review": 8,
        "source_reconciliation": 5,
    }
    pending_conn = sqlite3.connect(":memory:")
    pending_conn.row_factory = sqlite3.Row
    pending_conn.executescript("""
    CREATE TABLE m365_knowledge_candidates(
      id INTEGER PRIMARY KEY,source_drive_id TEXT NOT NULL,source_item_id TEXT NOT NULL,
      source_name TEXT NOT NULL,source_relative_path TEXT NOT NULL,
      source_etag TEXT NOT NULL,source_size INTEGER NOT NULL,
      source_modified_at TEXT NOT NULL,status TEXT NOT NULL,decision TEXT NOT NULL,
      target_folder TEXT NOT NULL,classification_json TEXT NOT NULL,
      destination_drive_id TEXT NOT NULL,destination_item_id TEXT NOT NULL,
      destination_web_url TEXT NOT NULL,destination_etag TEXT NOT NULL,
      source_archive_item_id TEXT NOT NULL,source_archive_web_url TEXT NOT NULL,
      source_archive_etag TEXT NOT NULL,source_archived_at TEXT NOT NULL,
      review_rationale TEXT NOT NULL
    );
    CREATE TABLE m365_knowledge_events(
      id INTEGER PRIMARY KEY,candidate_id INTEGER NOT NULL,event_type TEXT NOT NULL
    );
    CREATE TABLE m365_bulk_items(
      drive_id TEXT NOT NULL,item_id TEXT NOT NULL,status TEXT NOT NULL,
      reason TEXT NOT NULL,attempts INTEGER NOT NULL,next_attempt INTEGER NOT NULL,
      lease_until INTEGER NOT NULL
    );
    """)
    failure_codes = (
        "DOCUMENT_PACKAGE_INVALID", "DOCUMENT_XML_INVALID", "PDF_PARSE_FAILED",
        "PDF_ENCRYPTED", "IMAGE_HEADER_INVALID", "MEDIA_HEADER_INVALID",
        "TEXT_ENCODING_UNSUPPORTED", "FORMAT_NOT_SUPPORTED",
    )
    for index, failure_code in enumerate(failure_codes, 1):
        classification = {
            "extraction": {
                "status": "Review Required", "retry_eligible": False,
                "disposition": readiness.EXTRACTION_REVIEW_DISPOSITION,
                "failure_code": failure_code,
            }
        }
        pending_conn.execute(
            "INSERT INTO m365_knowledge_candidates VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (
                index, "drive-12345678", f"item-{index:08d}", f"name-{index}",
                f"10 Pending Classification/Enterprise/name-{index}", f"etag-{index}",
                100 + index, "2026-11-02T00:00:00Z", "Pending Review", "Approved",
                "05 Research and Reference", json.dumps(classification),
                "", "", "", "", "", "", "", "", "Governed extraction review",
            ),
        )
        pending_conn.execute(
            "INSERT INTO m365_knowledge_events VALUES(?,?,?)",
            (index, index, "CandidateRoutedToGovernedExtractionReview"),
        )
    for index in range(9, 14):
        classification = {
            "extraction": {"status": "Complete"},
            "source_reconciliation": {
                "status": "Review Required",
                "disposition": readiness.SOURCE_RECONCILIATION_DISPOSITION,
                "successor_match": "None", "boundary_files_rechecked": 22377,
            },
        }
        pending_conn.execute(
            "INSERT INTO m365_knowledge_candidates VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (
                index, "drive-12345678", f"item-{index:08d}", f"name-{index}",
                f"10 Pending Classification/Enterprise/name-{index}", f"etag-{index}",
                100 + index, "2026-11-02T00:00:00Z", "Pending Review", "Approved",
                "05 Research and Reference", json.dumps(classification),
                "", "", "", "", "", "", "", "", "Processed intake archive review",
            ),
        )
        pending_conn.execute(
            "INSERT INTO m365_knowledge_events VALUES(?,?,?)",
            (index, index, "CandidateRoutedToGovernedSourceReconciliation"),
        )
    pending = readiness.collect(pending_conn, clock=1000)
    assert pending["open_remaining"] == 13, pending
    assert pending["pending_scope_extraction_review"] == 8, pending
    assert pending["pending_scope_source_reconciliation"] == 5, pending
    assert pending["source_reconciliation_unresolved"] == 5, pending
    assert pending["pending_scope_other"] == 0, pending
    assert pending["content_downloads"] == 0 and pending["source_requests"] == 0, pending
    assert pending["rows_changed"] == 0 and pending["releases"] == 0, pending
    pending_conn.close()
    with tempfile.TemporaryDirectory() as directory:
        conn = sqlite3.connect(os.path.join(directory, "candidate-readiness.sqlite"))
        conn.row_factory = sqlite3.Row
        conn.executescript("""
        CREATE TABLE m365_knowledge_candidates(
          id INTEGER PRIMARY KEY,source_drive_id TEXT NOT NULL,source_item_id TEXT NOT NULL,
          source_name TEXT NOT NULL,source_relative_path TEXT NOT NULL,
          source_etag TEXT NOT NULL,source_size INTEGER NOT NULL,
          source_modified_at TEXT NOT NULL,
          status TEXT NOT NULL,decision TEXT NOT NULL,
          target_folder TEXT NOT NULL,classification_json TEXT NOT NULL,
          destination_drive_id TEXT NOT NULL,destination_item_id TEXT NOT NULL,
          destination_web_url TEXT NOT NULL,destination_etag TEXT NOT NULL,
          source_archive_item_id TEXT NOT NULL,source_archive_web_url TEXT NOT NULL,
          source_archive_etag TEXT NOT NULL,source_archived_at TEXT NOT NULL,
          review_rationale TEXT NOT NULL
        );
        CREATE TABLE m365_knowledge_events(
          id INTEGER PRIMARY KEY,candidate_id INTEGER NOT NULL,event_type TEXT NOT NULL
        );
        CREATE TABLE m365_bulk_items(
          drive_id TEXT NOT NULL,item_id TEXT NOT NULL,status TEXT NOT NULL,
          reason TEXT NOT NULL,attempts INTEGER NOT NULL,next_attempt INTEGER NOT NULL,
          lease_until INTEGER NOT NULL
        );
        """)
        fixtures = (
            (1, "Approved for Promotion", "Complete", "Automatically processed under policy."),
            (2, "Automatic Retry Required", "Complete", "Processed intake archive could not be verified"),
            (3, "Automatic Retry Required", "Retry Paused", "Knowledge upload did not complete"),
        )
        for candidate_id, status, extraction_status, rationale in fixtures:
            conn.execute(
                "INSERT INTO m365_knowledge_candidates VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                (
                    candidate_id, "drive-12345678", f"item-0000000{candidate_id}",
                    f"name-{candidate_id}",
                    f"10 Pending Classification/Enterprise/name-{candidate_id}",
                    f"etag-{candidate_id}", 100 + candidate_id,
                    "2026-10-30T00:00:00Z", status,
                    "Approved", "05 Research and Reference",
                    json.dumps({"extraction": {"status": extraction_status}}),
                    "", "", "", "", "", "", "", "", rationale,
                ),
            )
            conn.execute(
                "INSERT INTO m365_knowledge_events VALUES(?,?,?)",
                (candidate_id, candidate_id, "AutomaticallyClassified"),
            )
        conn.execute(
            "UPDATE m365_knowledge_candidates SET destination_drive_id='d',"
            "destination_item_id='i',destination_web_url='u',destination_etag='e',"
            "source_archive_item_id='a' WHERE id=2"
        )
        conn.execute(
            "INSERT INTO m365_knowledge_events VALUES(?,?,?)",
            (4, 2, "CandidateRoutedToGovernedExtractionReview"),
        )
        conn.execute(
            "INSERT INTO m365_knowledge_events VALUES(?,?,?)",
            (5, 2, "AutomaticPromotionRetryScheduled"),
        )
        conn.execute(
            "INSERT INTO m365_knowledge_events VALUES(?,?,?)",
            (6, 2, "AutomaticallyPromotedVerifiedAndArchived"),
        )
        conn.execute(
            "INSERT INTO m365_bulk_items VALUES(?,?,?,?,?,?,?)",
            ("drive-12345678", "item-00000001", "Done", "", 1, 0, 0),
        )
        conn.execute(
            "INSERT INTO m365_bulk_items VALUES(?,?,?,?,?,?,?)",
            ("drive-12345678", "item-00000002", "Retry", "promotion_retry_required", 6, 2000, 0),
        )
        result = readiness.collect(
            conn,
            {
                "Pending Review": 0,
                "Approved for Promotion": 1,
                "Automatic Retry Required": 2,
                "Destination Verified": 0,
            },
            {
                "Approved for Promotion": 1,
                "Automatic Retry Required": 1,
            },
            clock=1000,
        )
        assert result["open_remaining"] == 3, result
        assert result["status_approved_for_promotion"] == 1, result
        assert result["status_automatic_retry_required"] == 2, result
        assert result["matrix_approved_for_promotion_complete"] == 1, result
        assert result["matrix_automatic_retry_required_complete"] == 1, result
        assert result["matrix_automatic_retry_required_retry_paused"] == 1, result
        assert result["decision_approved"] == 3 and result["target_configured"] == 3, result
        assert result["destination_any"] == 1 and result["destination_complete"] == 1, result
        assert result["archive_any"] == 1 and result["archive_complete"] == 0, result
        assert result["rationale_policy"] == 1, result
        assert result["rationale_archive"] == 1, result
        assert result["rationale_upload"] == 1, result
        assert result["event_automaticallyclassified"] == 3, result
        assert result["event_candidateroutedtogovernedextractionreview"] == 1, result
        assert result["event_automaticpromotionretryscheduled"] == 1, result
        assert result["promotion_scope_total"] == 2, result
        assert result["promotion_scope_fingerprint_groups"] == 2, result
        assert result[
            "promotion_fingerprint_approved_for_promotion_destination_none_"
            "archive_none_rationale_policy_promoted_absent_retry_absent"
        ] == 1, result
        assert result[
            "promotion_fingerprint_automatic_retry_required_destination_complete_"
            "archive_partial_rationale_archive_promoted_present_retry_present"
        ] == 1, result
        assert result["work_scope_total"] == 2, result
        assert result["work_scope_fingerprint_groups"] == 2, result
        assert result[
            "work_fingerprint_approved_for_promotion_failure_policy_work_done_"
            "reason_blank_attempts_one_two_schedule_not_scheduled"
        ] == 1, result
        assert result[
            "work_fingerprint_automatic_retry_required_failure_archive_other_work_retry_"
            "reason_promotion_retry_attempts_six_plus_schedule_retry_backoff"
        ] == 1, result
        conn.execute("DELETE FROM m365_bulk_items")

        evidence_content = b"governed evidence fixture"
        evidence_sha = hashlib.sha256(evidence_content).hexdigest()
        primary_name, fallback_name = readiness._destination_names(
            "evidence.docx", evidence_sha
        )
        assert primary_name.endswith(f".{evidence_sha[:24]}.docx")
        assert fallback_name.endswith(f".{evidence_sha}.original.bin")

        class EvidenceResponse:
            def __init__(
                self, status_code: int, payload: dict | None = None,
                content: bytes = b"", headers: dict | None = None,
            ):
                self.status_code = status_code
                self.payload = payload or {}
                self.content = content
                self.headers = headers or {}

            def json(self) -> dict:
                return self.payload

        class EvidenceClient:
            def __init__(self, primary_content: bytes, fallback_content: bytes | None):
                self.primary_content = primary_content
                self.fallback_content = fallback_content

            def get(self, url: str, **_kwargs):
                if url.endswith("/primary-item-00000000/content"):
                    return EvidenceResponse(200, content=self.primary_content)
                if url.endswith("/fallback-item-0000000/content"):
                    return EvidenceResponse(200, content=self.fallback_content or b"")
                if fallback_name.replace(" ", "%20") in url:
                    if self.fallback_content is None:
                        return EvidenceResponse(404)
                    return EvidenceResponse(200, {
                        "id": "fallback-item-0000000", "name": fallback_name,
                        "size": len(self.fallback_content), "eTag": "fallback-etag",
                        "parentReference": {"id": "folder-12345678"}, "file": {},
                        "webUrl": "https://salussolutions.sharepoint.com/fallback",
                    })
                if primary_name.replace(" ", "%20") in url:
                    return EvidenceResponse(200, {
                        "id": "primary-item-00000000", "name": primary_name,
                        "size": len(self.primary_content), "eTag": "primary-etag",
                        "parentReference": {"id": "folder-12345678"}, "file": {},
                        "webUrl": "https://salussolutions.sharepoint.com/primary",
                    })
                raise AssertionError(url)

        class EvidenceWriter:
            class Destination:
                drive_id = "knowledge-drive-12345678"

                @staticmethod
                def validate() -> None:
                    return None

            class IntakeConfig:
                max_file_bytes = 104857600

            def __init__(self, primary_content: bytes, fallback_content: bytes | None):
                self.destination = self.Destination()
                self.intake_config = self.IntakeConfig()
                self.client = EvidenceClient(primary_content, fallback_content)

            def _headers(self) -> dict[str, str]:
                return {"Authorization": "test"}

            @staticmethod
            def _resolve_folder(_target: str) -> str:
                return "folder-12345678"

            @staticmethod
            def verify_already_archived_source(item_id: str, _sha256: str) -> dict:
                return {"item_id": item_id, "etag": "evidence-etag"}

        exact_state, exact_downloads = readiness._destination_evidence_state(
            EvidenceWriter(evidence_content, None), "folder-12345678",
            "evidence.docx", evidence_sha,
        )
        assert (exact_state, exact_downloads) == ("exact", 1)
        fallback_state, fallback_downloads = readiness._destination_evidence_state(
            EvidenceWriter(b"transformed", evidence_content), "folder-12345678",
            "evidence.docx", evidence_sha,
        )
        assert (fallback_state, fallback_downloads) == ("fallback_exact", 2)

        evidence_conn = sqlite3.connect(":memory:")
        evidence_conn.row_factory = sqlite3.Row
        evidence_conn.executescript("""
        CREATE TABLE m365_knowledge_candidates(
          id INTEGER PRIMARY KEY,source_drive_id TEXT NOT NULL,
          source_item_id TEXT NOT NULL,source_etag TEXT NOT NULL,
          source_sha256 TEXT NOT NULL,source_name TEXT NOT NULL,
          target_folder TEXT NOT NULL,status TEXT NOT NULL,
          classification_json TEXT NOT NULL,
          destination_drive_id TEXT NOT NULL,destination_item_id TEXT NOT NULL,
          destination_web_url TEXT NOT NULL,destination_etag TEXT NOT NULL,
          source_archive_item_id TEXT NOT NULL,source_archive_web_url TEXT NOT NULL,
          source_archive_etag TEXT NOT NULL,source_archived_at TEXT NOT NULL
        );
        CREATE TABLE m365_bulk_items(drive_id TEXT NOT NULL,item_id TEXT NOT NULL);
        """)
        for candidate_id, status in (
            (1, "Approved for Promotion"),
            (2, "Automatic Retry Required"),
        ):
            evidence_conn.execute(
                "INSERT INTO m365_knowledge_candidates VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                (
                    candidate_id, "drive-12345678", f"archive-item-0000000{candidate_id}",
                    "evidence-etag", evidence_sha, "evidence.docx",
                    "05 Research and Reference", status,
                    json.dumps({"extraction": {"status": "Complete"}}),
                    "", "", "", "", "", "", "", "",
                ),
            )
        processed = readiness.collect_processed_evidence(
            evidence_conn, EvidenceWriter(evidence_content, None),
            expected_counts={
                "Approved for Promotion": 1,
                "Automatic Retry Required": 1,
            },
            expected_scope=2,
        )
        assert processed["processed_evidence_archive_verified"] == 2, processed
        assert processed["processed_evidence_destination_exact"] == 2, processed
        assert processed[
            "processed_evidence_status_approved_for_promotion_destination_exact"
        ] == 1, processed
        assert processed[
            "processed_evidence_status_automatic_retry_required_destination_exact"
        ] == 1, processed
        assert processed["processed_evidence_content_downloads"] == 4, processed
        assert processed["processed_evidence_rows_changed"] == 0, processed
        evidence_conn.close()

        class Response:
            def __init__(self, status_code: int, payload: dict | None = None):
                self.status_code = status_code
                self.payload = payload or {}

            def json(self) -> dict:
                return self.payload

        class Client:
            def get(self, url: str, **_kwargs):
                item_id = url.rsplit("/", 1)[-1]
                if item_id == "item-00000001":
                    return Response(200, {
                        "id": item_id, "name": "name-1", "size": 101,
                        "eTag": "etag-1", "lastModifiedDateTime": "2026-10-30T00:00:00Z",
                        "parentReference": {"id": "enterprise-12345678"},
                        "file": {},
                        "webUrl": "https://salussolutions.sharepoint.com/source",
                    })
                if item_id == "enterprise-12345678":
                    return Response(200, {
                        "id": item_id, "name": "Enterprise",
                        "parentReference": {"id": "pending-12345678"}, "folder": {},
                    })
                if item_id == "item-00000002":
                    return Response(404)
                raise AssertionError(item_id)

        source = readiness.collect_source_preflight(
            conn, Client(), {"Authorization": "test"},
            drive_id="drive-12345678", pending_id="pending-12345678",
            enterprise_id="enterprise-12345678", intake_root_id="root-12345678",
            expected_counts={
                "Approved for Promotion": 1,
                "Automatic Retry Required": 1,
            },
        )
        assert source["source_scope_total"] == 2, source
        assert source["source_verified_total"] == 1, source
        assert source["source_approved_for_promotion_verified"] == 1, source
        assert source["source_automatic_retry_required_not_found"] == 1, source
        assert source["source_outside_area_total"] == 0, source
        assert source["source_content_requests"] == 0, source

        class OutsideClient(Client):
            def get(self, url: str, **kwargs):
                item_id = url.rsplit("/", 1)[-1]
                if item_id == "item-00000001":
                    return Response(200, {
                        "id": item_id, "name": "name-1", "size": 101,
                        "eTag": "etag-1", "lastModifiedDateTime": "2026-10-30T00:00:00Z",
                        "parentReference": {"id": "ready-12345678"},
                        "file": {},
                        "webUrl": "https://salussolutions.sharepoint.com/source",
                    })
                if item_id == "ready-12345678":
                    return Response(200, {
                        "id": item_id, "name": "20 Ready for Intake Review",
                        "parentReference": {"id": "root-12345678"}, "folder": {},
                    })
                return super().get(url, **kwargs)

        outside = readiness.collect_source_preflight(
            conn, OutsideClient(), {"Authorization": "test"},
            drive_id="drive-12345678", pending_id="pending-12345678",
            enterprise_id="enterprise-12345678", intake_root_id="root-12345678",
            expected_counts={
                "Approved for Promotion": 1,
                "Automatic Retry Required": 1,
            },
            expected_states={
                ("Approved for Promotion", "outside_pending"): 1,
                ("Automatic Retry Required", "not_found"): 1,
            },
        )
        assert outside["source_approved_for_promotion_outside_pending"] == 1, outside
        assert outside[
            "source_approved_for_promotion_outside_area_ready_for_intake_review"
        ] == 1, outside
        assert outside["source_outside_area_total"] == 1, outside

        area_names = ["10 Pending Classification", *readiness.SOURCE_AREA_KEYS]
        area_ids = {name: f"area-{index:08d}" for index, name in enumerate(area_names)}
        root_url = f"{readiness.GRAPH_ROOT}/drives/drive-12345678/items/root-12345678/children"
        pages = {
            root_url: {"value": [
                {"id": area_ids[name], "name": name, "folder": {},
                 "parentReference": {"id": "root-12345678"}}
                for name in area_names
            ]},
        }
        for name, area_id in area_ids.items():
            pages[
                f"{readiness.GRAPH_ROOT}/drives/drive-12345678/items/{area_id}/children"
            ] = {"value": []}
        fingerprints = [
            {"source_item_id": f"old-{index:08d}", "source_name": f"missing-{index}",
             "source_size": 200 + index, "source_modified_at": "2026-10-30T00:00:00Z",
             "source_etag": f"old-etag-{index}"}
            for index in range(5)
        ]
        processed_url = (
            f"{readiness.GRAPH_ROOT}/drives/drive-12345678/items/"
            f"{area_ids['90 Processed Intake']}/children"
        )
        files = []
        for suffix, index, etag in (
            ("exact", 0, "old-etag-0"),
            ("metadata", 1, "new-etag-1"),
            ("ambiguous-a", 2, "new-etag-2a"),
            ("ambiguous-b", 2, "new-etag-2b"),
            ("exact-a", 4, "old-etag-4"),
            ("exact-b", 4, "old-etag-4"),
        ):
            files.append({
                "id": f"new-{suffix}-00000000", "name": f"missing-{index}",
                "size": 200 + index, "eTag": etag,
                "lastModifiedDateTime": "2026-10-30T00:00:00Z", "file": {},
                "parentReference": {"id": area_ids["90 Processed Intake"]},
            })
        pages[processed_url] = {"value": files}

        class CensusClient:
            def get(self, url: str, **_kwargs):
                if url not in pages:
                    raise AssertionError(url)
                return Response(200, pages[url])

        matches = readiness.collect_missing_source_matches(
            CensusClient(), {"Authorization": "test"},
            drive_id="drive-12345678", intake_root_id="root-12345678",
            missing_rows=fingerprints, expected_boundary_files=6,
        )
        assert matches["missing_successor_exact_unique"] == 1, matches
        assert matches["missing_successor_exact_ambiguous"] == 1, matches
        assert matches["missing_successor_metadata_unique"] == 1, matches
        assert matches["missing_successor_metadata_ambiguous"] == 1, matches
        assert matches["missing_successor_none"] == 1, matches
        assert matches["missing_successor_content_requests"] == 0, matches
        assert result["content_downloads"] == 0 and result["rows_changed"] == 0, result
        conn.execute(
            "INSERT INTO m365_knowledge_candidates VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (
                4, "drive-12345678", "item-00000004", "name-4",
                "10 Pending Classification/Enterprise/name-4", "etag-4", 104,
                "2026-10-30T00:00:00Z", "Automatic Retry Required", "Approved",
                "05 Research and Reference",
                json.dumps({"extraction": {"status": "Complete"}}),
                "", "", "", "", "", "", "", "", "Automatically processed under policy.",
            ),
        )
        try:
            readiness.collect(
                conn,
                {
                    "Pending Review": 0,
                    "Approved for Promotion": 1,
                    "Automatic Retry Required": 2,
                    "Destination Verified": 0,
                },
                {
                    "Approved for Promotion": 1,
                    "Automatic Retry Required": 1,
                },
                clock=1000,
            )
            raise AssertionError("open-candidate scope growth was not rejected")
        except RuntimeError as error:
            assert "exact checkpoint changed" in str(error), error
        conn.close()
    print("KNOWLEDGE_CANDIDATE_READINESS_PASS")


if __name__ == "__main__":
    check()
