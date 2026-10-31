"""Regression coverage for aggregate open-candidate readiness evidence."""

from __future__ import annotations

import json
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
    }
    for parameter, environment in mapping.items():
        assert f'{parameter}="$(env_value {environment})"' in workflow
        assert f"param {parameter} string" in bicep
        assert f"name: '{environment}'" in bicep


def check() -> None:
    check_protected_graph_contract()
    assert readiness.EXPECTED_INITIAL_STATUS_COUNTS == {
        "Pending Review": 8,
        "Approved for Promotion": 3,
        "Automatic Retry Required": 6,
        "Destination Verified": 0,
    }
    assert readiness.EXPECTED_PROMOTION_SCOPE_COUNTS == {
        "Approved for Promotion": 3,
        "Automatic Retry Required": 6,
    }
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
            assert "exceeded its approved boundary" in str(error), error
        conn.close()
    print("KNOWLEDGE_CANDIDATE_READINESS_PASS")


if __name__ == "__main__":
    check()
