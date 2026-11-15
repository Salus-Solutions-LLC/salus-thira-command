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
from salcapa_m365_intake import (
    GRAPH_ROOT,
    GovernedM365Config,
    GovernedM365Intake,
    M365IntakeError,
)


EXPECTED_TOTAL = 13
EXPECTED_EXTRACTION = 8
EXPECTED_RECONCILIATION = 5
APPROVAL_EVENT = "OwnerBatchApprovedForPromotion"
PROMOTION_EVENT = "OwnerApprovedPromotedVerifiedAndArchived"
FAILURE_EVENT = "OwnerApprovedPromotionRetryRequired"
UNAVAILABLE_EVENT = "OwnerApprovedUnavailableSourceException"
UNAVAILABLE_STATUS = "Governed Source Unavailable"
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
    UNAVAILABLE_STATUS,
}


def _now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _archived_source_not_found(writer: GraphKnowledgeWriter, item_id: str) -> bool:
    """Distinguish an exact Graph 404 without relying on the frozen image helper."""
    response = writer.client.get(
        f"{GRAPH_ROOT}/drives/{writer.intake_config.drive_id}/items/{item_id}",
        headers=writer._headers() | {"Accept": "application/json"},
        params={"$select": "id,file"},
    )
    if response.status_code == 404:
        return True
    if response.status_code != 200:
        raise KnowledgePromotionError("Archived source preflight could not be read")
    payload = response.json()
    if payload.get("id") != item_id or "file" not in payload:
        raise KnowledgePromotionError("Archived source preflight identity could not be verified")
    return False


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


def _unavailable_exception_category(classification: dict[str, Any]) -> str | None:
    extraction = classification.get("extraction") or {}
    reconciliation = classification.get("source_reconciliation") or {}
    common = (
        reconciliation.get("content_available") is False
        and reconciliation.get("metadata_only") is True
        and reconciliation.get("source_substitution_authorized") is False
        and reconciliation.get("public_release_authorized") is False
        and reconciliation.get("approved_by") == ACTOR
    )
    if (
        extraction.get("status") == "Complete"
        and reconciliation.get("status")
        == "Governed Unavailable-Source Exception Approved"
        and reconciliation.get("disposition")
        == "Governed Missing Source Reconciliation Required"
        and reconciliation.get("successor_match") == "None"
        and int(reconciliation.get("boundary_files_rechecked") or 0) == 22_377
        and common
    ):
        return "reconciliation"
    if (
        extraction.get("status") == "Governed Unavailable-Source Exception Approved"
        and extraction.get("disposition") == "Governed Extraction Review Required"
        and extraction.get("content_available") is False
        and extraction.get("metadata_only") is True
        and extraction.get("source_substitution_authorized") is False
        and extraction.get("public_release_authorized") is False
        and extraction.get("approved_by") == ACTOR
    ):
        return "extraction"
    return None


def _validate_row(row: Any) -> str:
    try:
        classification = json.loads(row["classification_json"] or "{}")
    except (TypeError, ValueError) as exc:
        raise RuntimeError("pending_review_classification_invalid") from exc
    category = (
        _unavailable_exception_category(classification)
        if row["status"] == UNAVAILABLE_STATUS
        else _category(classification)
    )
    if category not in {"extraction", "reconciliation"}:
        raise RuntimeError("pending_review_boundary_changed")
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


def _record_unavailable_source_exception(conn: Any, row: Any) -> None:
    """Close a proven missing-source review without claiming source content exists."""
    classification = json.loads(row["classification_json"] or "{}")
    category = _category(classification)
    section_name = "source_reconciliation" if category == "reconciliation" else "extraction"
    section = dict(classification.get(section_name) or {})
    section.update(
        {
            "status": "Governed Unavailable-Source Exception Approved",
            "content_available": False,
            "metadata_only": True,
            "source_substitution_authorized": False,
            "public_release_authorized": False,
            "approved_by": ACTOR,
            "approved_at": _now(),
        }
    )
    classification[section_name] = section
    timestamp = _now()
    updated = conn.execute(
        "UPDATE m365_knowledge_candidates SET status=?,classification_json=? "
        "WHERE id=? AND status IN ('Approved for Promotion','Automatic Retry Required')",
        (UNAVAILABLE_STATUS, json.dumps(classification, sort_keys=True), row["id"]),
    )
    if updated.rowcount != 1:
        raise RuntimeError("approved_boundary_state_changed")
    conn.execute(
        "INSERT INTO m365_knowledge_events"
        "(candidate_id,event_type,actor,detail_json,created_at) VALUES(?,?,?,?,?)",
        (
            row["id"],
            UNAVAILABLE_EVENT,
            ACTOR,
            json.dumps(
                {
                    "content_available": False,
                    "metadata_only": True,
                    "public_release_authorized": False,
                    "source_substitution_authorized": False,
                    "source_item_id": row["source_item_id"],
                    "source_etag": row["source_etag"],
                    "source_sha256": row["source_sha256"],
                },
                sort_keys=True,
                separators=(",", ":"),
            ),
            timestamp,
        ),
    )
    conn.commit()


def _ledger_source(conn: Any, drive_id: str, source_item_id: str) -> tuple[str, dict[str, Any] | None]:
    cursors = conn.execute(
        "SELECT pending_id,phase,last_error FROM m365_bulk_cursors WHERE drive_id=?",
        (drive_id,),
    ).fetchall()
    if len(cursors) != 1 or cursors[0]["phase"] != "delta" or cursors[0]["last_error"]:
        raise RuntimeError("governed_source_ledger_not_ready")
    pending_id = str(cursors[0]["pending_id"] or "")
    source = conn.execute(
        "SELECT parent_id,name,kind,etag,size,metadata_json,status,reason "
        "FROM m365_bulk_items WHERE drive_id=? AND pending_id=? AND item_id=?",
        (drive_id, pending_id, source_item_id),
    ).fetchone()
    if source is None or source["status"] == "Removed":
        return pending_id, None
    if source["kind"] != "file":
        raise RuntimeError("approved_boundary_state_changed")
    metadata = json.loads(source["metadata_json"] or "{}")
    item = {
        "id": source_item_id,
        "parent_id": source["parent_id"],
        "name": source["name"],
        "etag": source["etag"],
        "size": int(source["size"]),
        "mime_type": metadata.get("mime_type", ""),
        "last_modified": metadata.get("last_modified", ""),
        "ctag": metadata.get("ctag", ""),
        "source_owner": metadata.get("source_owner", ""),
        "source_owner_id": metadata.get("source_owner_id", ""),
        "last_modified_by": metadata.get("last_modified_by", ""),
        "web_url": metadata.get("web_url", ""),
    }
    return pending_id, item


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
    promoted = already_complete = unavailable = already_unavailable = failed = 0
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
        if row["status"] == UNAVAILABLE_STATUS:
            if not _unavailable_exception_category(json.loads(row["classification_json"] or "{}")):
                raise RuntimeError("approved_boundary_state_changed")
            already_unavailable += 1
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
            pending_id, ledger_row = _ledger_source(
                conn, intake_config.drive_id, row["source_item_id"]
            )
            if ledger_row is None:
                if row["status"] == "Destination Verified":
                    raise KnowledgePromotionError(
                        "Verified destination awaits exact source archive verification"
                    )
                if _category(json.loads(row["classification_json"] or "{}")) == "reconciliation":
                    _record_unavailable_source_exception(conn, row)
                    unavailable += 1
                    emit("processed", ordinal)
                    continue
                if _archived_source_not_found(writer, row["source_item_id"]):
                    _record_unavailable_source_exception(conn, row)
                    unavailable += 1
                    emit("processed", ordinal)
                    continue
                try:
                    archived = writer.verify_already_archived_source(
                        row["source_item_id"], row["source_sha256"], include_content=True
                    )
                except KnowledgePromotionError as exc:
                    if str(exc) != "Archived source item was not found":
                        raise
                    _record_unavailable_source_exception(conn, row)
                    unavailable += 1
                    emit("processed", ordinal)
                    continue
                content = archived.get("content") if archived else None
                if (
                    not archived
                    or archived.get("item_id") != row["source_item_id"]
                    or archived.get("etag") != row["source_etag"]
                    or not isinstance(content, bytes)
                    or len(content) != int(row["source_size"])
                ):
                    raise M365IntakeError("Exact governed source is unavailable")
                destination = writer.put_verified(
                    row["target_folder"], row["source_name"], content, row["source_sha256"]
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
                _finish(conn, row, writer, destination, archived)
                promoted += 1
                emit("processed", ordinal)
                continue
            document = intake.read_delta_document(
                ledger_row,
                pending_folder_id=pending_id,
                access_classification="Salus Internal",
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
    verified_complete = int(
        conn.execute(
            "SELECT COUNT(*) FROM m365_knowledge_candidates c "
            "WHERE c.status='Ingested and Verified' AND EXISTS "
            "(SELECT 1 FROM m365_knowledge_events e WHERE e.candidate_id=c.id "
            "AND e.event_type=?)",
            (APPROVAL_EVENT,),
        ).fetchone()[0]
        or 0
    )
    unavailable_complete = int(
        conn.execute(
            "SELECT COUNT(*) FROM m365_knowledge_candidates c "
            "WHERE c.status=? AND EXISTS "
            "(SELECT 1 FROM m365_knowledge_events e WHERE e.candidate_id=c.id "
            "AND e.event_type=?)",
            (UNAVAILABLE_STATUS, UNAVAILABLE_EVENT),
        ).fetchone()[0]
        or 0
    )
    if verified_complete != promoted + already_complete:
        raise RuntimeError("promotion_readback_failed")
    if unavailable_complete != unavailable + already_unavailable:
        raise RuntimeError("unavailable_source_exception_readback_failed")
    return {
        "promoted": promoted,
        "already_complete": already_complete,
        "unavailable_source_exceptions": unavailable,
        "already_unavailable": already_unavailable,
        "failed_closed": failed,
        "verified_complete": verified_complete,
        "accounted_complete": verified_complete + unavailable_complete,
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
    complete = result["failed_closed"] == 0 and result["accounted_complete"] == EXPECTED_TOTAL
    emit("complete", 1 if complete else 0)
    if not complete:
        raise RuntimeError("One or more exact sources failed closed")


if __name__ == "__main__":
    main()
