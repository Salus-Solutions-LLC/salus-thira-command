"""Approve and promote the exact governed Knowledge pending-review boundary.

This one-time operation is deliberately narrow.  It records Marc Duncan's
explicit 2026-11-11 approval for the thirteen current Salus-only review
records, preserves their extraction and source-reconciliation evidence, and
attempts promotion only from the exact recorded source identity.  A missing,
changed, or unverifiable source fails closed and is never substituted.
"""

from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from typing import Any, Callable

from database import connect_database
from salcapa_knowledge_promotion import (
    GraphKnowledgeWriter,
    KnowledgeDestinationConfig,
    KnowledgePromotionError,
    TARGETS,
)
from salcapa_m365_intake import GovernedM365Config, GovernedM365Intake, M365IntakeError


EXPECTED_TOTAL = 13
EXPECTED_EXTRACTION = 8
EXPECTED_RECONCILIATION = 5
APPROVAL_EVENT = "OwnerBatchApprovedForPromotion"
PROMOTION_EVENT = "OwnerApprovedPromotedVerifiedAndArchived"
FAILURE_EVENT = "OwnerApprovedPromotionRetryRequired"
ACTOR = "Marc Duncan"
RATIONALE = (
    "Explicit owner approval on 2026-11-11 for governed internal research, citation, "
    "assignment, and Knowledge Library promotion; public release or disclosure remains "
    "a separate authorization gate."
)
ALLOWED_PRODUCTS = {"ChatGPT", "SalCAPA", "SalINTEL", "SalTHIRA", "SalOPS"}
ACTIVE_STATUSES = {
    "Approved for Promotion",
    "Automatic Retry Required",
    "Destination Verified",
    "Ingested and Verified",
}


def _now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _category(classification: dict[str, Any]) -> str:
    extraction = classification.get("extraction") or {}
    reconciliation = classification.get("source_reconciliation") or {}
    if (
        extraction.get("status") == "Review Required"
        and extraction.get("disposition") == "Governed Extraction Review Required"
        and extraction.get("retry_eligible") is False
        and not reconciliation
    ):
        return "extraction"
    if (
        extraction.get("status") == "Complete"
        and reconciliation.get("status") == "Review Required"
        and reconciliation.get("disposition")
        == "Governed Missing Source Reconciliation Required"
        and reconciliation.get("successor_match") == "None"
        and int(reconciliation.get("boundary_files_rechecked") or 0) == 22_377
    ):
        return "reconciliation"
    raise RuntimeError("pending_review_boundary_changed")


def _validate_row(row: Any) -> str:
    try:
        classification = json.loads(row["classification_json"] or "{}")
    except (TypeError, ValueError) as exc:
        raise RuntimeError("pending_review_classification_invalid") from exc
    category = _category(classification)
    if row["decision"] != "Approved" or row["target_folder"] not in TARGETS:
        raise RuntimeError("pending_review_approval_metadata_changed")
    products = classification.get("permit_products") or []
    if (
        not isinstance(products, list)
        or not products
        or any(product not in ALLOWED_PRODUCTS for product in products)
    ):
        raise RuntimeError("pending_review_product_scope_changed")
    if classification.get("target_folder") != row["target_folder"]:
        raise RuntimeError("pending_review_approval_metadata_changed")
    if row["source_drive_id"] == "" or row["source_item_id"] == "":
        raise RuntimeError("pending_review_source_identity_changed")
    if row["source_etag"] == "" or len(str(row["source_sha256"] or "")) != 64:
        raise RuntimeError("pending_review_source_identity_changed")
    return category


def _select_pending(conn: Any) -> list[Any]:
    sql = (
        "SELECT * FROM m365_knowledge_candidates WHERE status='Pending Review' ORDER BY id"
    )
    if getattr(conn, "backend", "sqlite") == "postgres":
        sql += " FOR UPDATE"
    return conn.execute(sql).fetchall()


def approve_exact_boundary(
    conn: Any, emit: Callable[[str, str | int], None]
) -> list[int]:
    """Atomically approve exactly the current 8+5 governed review boundary."""
    rows = _select_pending(conn)
    if not rows:
        resumed = conn.execute(
            "SELECT c.* FROM m365_knowledge_candidates c "
            "WHERE EXISTS (SELECT 1 FROM m365_knowledge_events e "
            "WHERE e.candidate_id=c.id AND e.event_type=?) ORDER BY c.id",
            (APPROVAL_EVENT,),
        ).fetchall()
        if len(resumed) != EXPECTED_TOTAL:
            raise RuntimeError("pending_review_prestate_changed")
        for row in resumed:
            if row["status"] not in ACTIVE_STATUSES:
                raise RuntimeError("approved_boundary_state_changed")
            _validate_row(row)
        emit("approval_mode", "resume")
        return [int(row["id"]) for row in resumed]
    if len(rows) != EXPECTED_TOTAL:
        raise RuntimeError("pending_review_prestate_changed")
    categories = [_validate_row(row) for row in rows]
    if categories.count("extraction") != EXPECTED_EXTRACTION:
        raise RuntimeError("pending_review_category_counts_changed")
    if categories.count("reconciliation") != EXPECTED_RECONCILIATION:
        raise RuntimeError("pending_review_category_counts_changed")
    timestamp = _now()
    detail = json.dumps(
        {
            "approval_scope": "governed_internal_knowledge_promotion",
            "public_release_authorized": False,
            "source_substitution_authorized": False,
            "exact_source_verification_required": True,
        },
        sort_keys=True,
        separators=(",", ":"),
    )
    try:
        for row in rows:
            updated = conn.execute(
                "UPDATE m365_knowledge_candidates SET status='Approved for Promotion',"
                "reviewed_by=?,reviewed_at=?,review_rationale=? "
                "WHERE id=? AND status='Pending Review'",
                (ACTOR, timestamp, RATIONALE, row["id"]),
            )
            if updated.rowcount != 1:
                raise RuntimeError("pending_review_concurrency_guard_failed")
            conn.execute(
                "INSERT INTO m365_knowledge_events"
                "(candidate_id,event_type,actor,detail_json,created_at) VALUES(?,?,?,?,?)",
                (row["id"], APPROVAL_EVENT, ACTOR, detail, timestamp),
            )
        remaining = int(
            conn.execute(
                "SELECT COUNT(*) FROM m365_knowledge_candidates WHERE status='Pending Review'"
            ).fetchone()[0]
            or 0
        )
        event_count = int(
            conn.execute(
                "SELECT COUNT(*) FROM m365_knowledge_events WHERE event_type=?",
                (APPROVAL_EVENT,),
            ).fetchone()[0]
            or 0
        )
        if remaining != 0 or event_count != EXPECTED_TOTAL:
            raise RuntimeError("pending_review_approval_readback_failed")
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    emit("approval_mode", "committed")
    emit("approved", EXPECTED_TOTAL)
    return [int(row["id"]) for row in rows]


def _failure_code(exc: Exception) -> str:
    if isinstance(exc, M365IntakeError):
        return "exact_source_unavailable"
    if isinstance(exc, KnowledgePromotionError):
        detail = str(exc).lower()
        if "destination" in detail or "folder" in detail or "upload" in detail:
            return "destination_verification_required"
        if "archive" in detail:
            return "source_archive_verification_required"
        return "promotion_verification_required"
    if isinstance(exc, RuntimeError) and str(exc) in {
        "source_identity_changed",
        "approved_boundary_state_changed",
    }:
        return str(exc)
    return "unexpected_promotion_failure"


def _record_retry(conn: Any, candidate_id: int, code: str) -> None:
    current = conn.execute(
        "SELECT destination_item_id FROM m365_knowledge_candidates WHERE id=?",
        (candidate_id,),
    ).fetchone()
    status = "Destination Verified" if current and current["destination_item_id"] else "Automatic Retry Required"
    timestamp = _now()
    conn.execute(
        "UPDATE m365_knowledge_candidates SET status=? WHERE id=?",
        (status, candidate_id),
    )
    conn.execute(
        "INSERT INTO m365_knowledge_events"
        "(candidate_id,event_type,actor,detail_json,created_at) VALUES(?,?,?,?,?)",
        (
            candidate_id,
            FAILURE_EVENT,
            ACTOR,
            json.dumps({"failure_code": code}, sort_keys=True, separators=(",", ":")),
            timestamp,
        ),
    )
    conn.commit()


def _finish(
    conn: Any,
    row: Any,
    writer: GraphKnowledgeWriter,
    destination: dict[str, str],
    archived: dict[str, str],
) -> None:
    timestamp = _now()
    conn.execute(
        "UPDATE m365_knowledge_candidates SET status='Ingested and Verified',"
        "destination_drive_id=?,destination_item_id=?,destination_web_url=?,"
        "destination_etag=?,promoted_at=?,source_archived_at=?,"
        "source_archive_item_id=?,source_archive_web_url=?,source_archive_etag=? WHERE id=?",
        (
            writer.destination.drive_id,
            destination["item_id"],
            destination["web_url"],
            destination["etag"],
            timestamp,
            timestamp,
            archived["item_id"],
            archived["web_url"],
            archived["etag"],
            row["id"],
        ),
    )
    conn.execute(
        "INSERT INTO m365_knowledge_events"
        "(candidate_id,event_type,actor,detail_json,created_at) VALUES(?,?,?,?,?)",
        (
            row["id"],
            PROMOTION_EVENT,
            ACTOR,
            json.dumps(
                {
                    "destination_verified": True,
                    "source_archived_verified": True,
                    "public_release_authorized": False,
                },
                sort_keys=True,
                separators=(",", ":"),
            ),
            timestamp,
        ),
    )
    conn.commit()


def promote_exact_boundary(
    conn: Any,
    candidate_ids: list[int],
    emit: Callable[[str, str | int], None],
) -> dict[str, int]:
    intake_config = GovernedM365Config.from_environment()
    intake = GovernedM365Intake(intake_config)
    writer = GraphKnowledgeWriter(intake_config, KnowledgeDestinationConfig.from_environment())
    listed = {item["id"]: item for item in intake.list_files()}
    promoted = already_complete = failed = 0
    failure_counts: dict[str, int] = {}
    for ordinal, candidate_id in enumerate(candidate_ids, 1):
        row = conn.execute(
            "SELECT * FROM m365_knowledge_candidates WHERE id=?", (candidate_id,)
        ).fetchone()
        if row is None or row["status"] not in ACTIVE_STATUSES:
            raise RuntimeError("approved_boundary_state_changed")
        _validate_row(row)
        if row["source_drive_id"] != intake_config.drive_id:
            raise RuntimeError("approved_boundary_state_changed")
        if row["status"] == "Ingested and Verified":
            already_complete += 1
            continue
        try:
            if row["status"] == "Destination Verified":
                archived = writer.verify_already_archived_source(
                    row["source_item_id"], row["source_sha256"]
                )
                if archived is not None:
                    destination = {
                        "item_id": row["destination_item_id"],
                        "web_url": row["destination_web_url"],
                        "etag": row["destination_etag"],
                    }
                    _finish(conn, row, writer, destination, archived)
                    promoted += 1
                    continue
            listed_row = listed.get(row["source_item_id"])
            if listed_row is None:
                raise M365IntakeError("Exact governed source is unavailable")
            document = intake.read_listed_document(
                listed_row, access_classification="Salus Internal"
            )
            if (
                document.item_id != row["source_item_id"]
                or document.etag != row["source_etag"]
                or document.sha256 != row["source_sha256"]
                or document.name != row["source_name"]
                or document.size != row["source_size"]
            ):
                raise RuntimeError("source_identity_changed")
            destination = writer.put_verified(
                row["target_folder"], document.name, document.content, document.sha256
            )
            conn.execute(
                "UPDATE m365_knowledge_candidates SET status='Destination Verified',"
                "destination_drive_id=?,destination_item_id=?,destination_web_url=?,"
                "destination_etag=? WHERE id=?",
                (
                    writer.destination.drive_id,
                    destination["item_id"],
                    destination["web_url"],
                    destination["etag"],
                    row["id"],
                ),
            )
            conn.commit()
            archived = writer.archive_verified_source(
                document.item_id, document.etag, document.name, document.sha256
            )
            _finish(conn, row, writer, destination, archived)
            promoted += 1
        except (KnowledgePromotionError, M365IntakeError, RuntimeError) as exc:
            code = _failure_code(exc)
            failure_counts[code] = failure_counts.get(code, 0) + 1
            failed += 1
            _record_retry(conn, candidate_id, code)
        emit("processed", ordinal)
    for code in sorted(failure_counts):
        emit(f"failure_{code}", failure_counts[code])
    final_complete = int(
        conn.execute(
            "SELECT COUNT(*) FROM m365_knowledge_candidates c "
            "WHERE c.status='Ingested and Verified' AND EXISTS "
            "(SELECT 1 FROM m365_knowledge_events e WHERE e.candidate_id=c.id "
            "AND e.event_type=?)",
            (APPROVAL_EVENT,),
        ).fetchone()[0]
        or 0
    )
    if final_complete != promoted + already_complete:
        raise RuntimeError("promotion_readback_failed")
    return {
        "promoted": promoted,
        "already_complete": already_complete,
        "failed_closed": failed,
        "verified_complete": final_complete,
    }


def main() -> None:
    def emit(key: str, value: str | int) -> None:
        print(f"KNOWLEDGE_REVIEW_PROMOTION_{key.upper()}={value}", flush=True)

    if os.getenv("SALUS_DB_BACKEND", "").strip().lower() != "postgres":
        raise RuntimeError("Live promotion requires managed PostgreSQL")
    emit("stage", "database_connect")
    conn = connect_database()
    try:
        candidate_ids = approve_exact_boundary(conn, emit)
        emit("stage", "exact_source_promotion")
        result = promote_exact_boundary(conn, candidate_ids, emit)
    except Exception as exc:
        emit("failure", _failure_code(exc))
        emit("complete", 0)
        raise RuntimeError("Knowledge review promotion failed closed") from None
    finally:
        conn.close()
    for key in sorted(result):
        emit(key, result[key])
    emit("complete", 1 if result["failed_closed"] == 0 else 0)
    if result["failed_closed"]:
        raise RuntimeError("One or more exact sources failed closed")


if __name__ == "__main__":
    main()
