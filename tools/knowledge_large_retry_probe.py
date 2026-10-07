"""Read only the status category of the observed 103,344,128-byte candidate.

Run in one bounded execution of the existing governed knowledge job. Never
print source identifiers, names, hashes, paths, exception text or row data.
"""

from __future__ import annotations

import json
import signal


SOURCE_SIZE = 103_344_128
PREFIX = "SALUS_LARGE_RETRY_DIAGNOSTIC="


def category(reason: object) -> str:
    value = str(reason or "")
    markers = (
        ("Knowledge upload session could not be created", "session_creation"),
        ("Knowledge upload session returned an untrusted location", "session_location"),
        ("Knowledge upload status is unavailable", "session_status"),
        ("Knowledge upload did not complete", "upload_response"),
        ("Knowledge upload status was ambiguous", "upload_range"),
        ("Knowledge upload range was invalid", "upload_range"),
        ("Knowledge upload made no verified progress", "upload_progress"),
        ("Knowledge upload completion was not confirmed", "upload_completion"),
        ("Knowledge upload completion was incomplete", "upload_completion"),
        ("Microsoft 365 token exchange was rejected", "token_exchange"),
        ("Approved knowledge folder was not uniquely resolved", "destination_folder"),
        ("Approved knowledge file could not be written", "destination_write"),
        ("Knowledge destination could not be checked", "destination_check"),
        ("Knowledge destination could not be read", "destination_read"),
        ("Knowledge destination verification failed", "destination_verification"),
        ("Verified intake source could not be archived", "source_archive"),
        ("Processed intake archive could not be verified", "source_archive"),
    )
    return next((code for fragment, code in markers if fragment in value), "unclassified")


def summary(rows: list[object]) -> dict[str, object]:
    if len(rows) != 1:
        return {"match_count": min(len(rows), 6), "unique_match": False}
    row = rows[0]
    safe_statuses = {
        "Automatic Retry Required", "Destination Verified", "Ingested and Verified",
        "Approved for Promotion", "Pending Review", "Source Retained", "Source Removed",
    }
    status = str(row["status"] or "")
    return {
        "match_count": 1,
        "unique_match": True,
        "status": status if status in safe_statuses else "Other",
        "failure_category": category(row["review_rationale"]),
        "has_destination": bool(row["destination_item_id"]),
        "has_archive": bool(row["source_archive_item_id"]),
    }


def main() -> None:
    signal.alarm(45)
    from database import backend_name, connect_database

    if backend_name() != "postgres":
        raise SystemExit("Governed PostgreSQL backend is required")
    conn = connect_database()
    try:
        conn.execute("SET TRANSACTION READ ONLY")
        rows = conn.execute(
            "SELECT status,review_rationale,destination_item_id,source_archive_item_id "
            "FROM m365_knowledge_candidates WHERE source_size=? LIMIT 6",
            (SOURCE_SIZE,),
        ).fetchall()
        result = summary(rows)
    finally:
        conn.rollback()
        conn.close()
    print(PREFIX + json.dumps(result, sort_keys=True), flush=True)
    if result["unique_match"] is not True:
        raise SystemExit(2)


if __name__ == "__main__":
    main()

