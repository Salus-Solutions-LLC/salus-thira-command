"""Repair four exact Knowledge Library destinations without replacing content.

The protected transition verifies the archived originals, requires the known
three-missing/one-mismatched destination pre-state, creates new hash-bound
objects with conflict behavior ``fail``, and only then commits destination and
archive evidence in one database transaction. The mismatched object is never
overwritten, renamed, or deleted.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
from datetime import datetime, timezone
from typing import Any, Callable
from urllib.parse import quote, urlparse

from database import connect_database
from salcapa_knowledge_promotion import (
    GRAPH_ROOT,
    GovernedM365Config,
    GraphKnowledgeWriter,
    KnowledgeDestinationConfig,
)


EXPECTED_BEFORE = {
    "Pending Review": 13,
    "Approved for Promotion": 3,
    "Automatic Retry Required": 1,
    "Destination Verified": 0,
}
EXPECTED_REPAIR = {"Approved for Promotion": 3, "Automatic Retry Required": 1}
OPEN_STATUSES = tuple(EXPECTED_BEFORE)
EVENT_TYPE = "GovernedDestinationRepairedAndArchiveReconciled"
ACTOR = "SalCAPA Governed Destination Repair Worker"
_IDENTIFIER = re.compile(r"^[A-Za-z0-9_!.-]{8,256}$")
FAILURE_CODES = {
    "Open candidate pre-state changed": "open_prestate_changed",
    "Destination-repair candidate pre-state changed": "repair_prestate_changed",
    "Archived original verification failed": "archive_verification_failed",
    "Destination defect correlation changed": "destination_correlation_changed",
    "Safe destination already contains different bytes": "safe_destination_conflict",
    "Safe destination upload failed": "safe_destination_upload_failed",
    "Destination-repair concurrency guard failed": "repair_concurrency_guard",
    "Destination-repair readback is incomplete": "repair_readback_incomplete",
}


def _json_expression(conn: Any, path: str) -> str:
    if getattr(conn, "backend", "sqlite") == "postgres":
        return f"COALESCE(c.classification_json::jsonb #>> '{{{path}}}','')"
    return "COALESCE(json_extract(c.classification_json,'$." + path.replace(",", ".") + "'),'')"


def _status_counts(conn: Any) -> dict[str, int]:
    marks = ",".join("?" for _ in OPEN_STATUSES)
    rows = conn.execute(
        f"SELECT status,COUNT(*) AS count FROM m365_knowledge_candidates "
        f"WHERE status IN ({marks}) GROUP BY status", OPEN_STATUSES,
    ).fetchall()
    observed = {status: 0 for status in OPEN_STATUSES}
    for row in rows:
        status = str(row["status"] or "")
        if status not in observed:
            raise RuntimeError("Open candidate pre-state changed")
        observed[status] = int(row["count"] or 0)
    return observed


def _destination_names(name: str, sha256: str) -> tuple[str, str, str]:
    stem, separator, extension = name.rpartition(".")
    if not stem:
        stem, separator, extension = name, "", ""
    primary_suffix = f".{sha256[:24]}" + (f".{extension}" if separator else "")
    primary = stem[:max(1, 240 - len(primary_suffix))] + primary_suffix
    fallback_suffix = f".{sha256}.original.bin"
    fallback = primary[:max(1, 240 - len(fallback_suffix))] + fallback_suffix
    repair_suffix = f".repair.{sha256}.original.bin"
    repair = stem[:max(1, 240 - len(repair_suffix))] + repair_suffix
    return primary, fallback, repair


def _download_exact(writer: Any, item_id: str, sha256: str) -> bool:
    response = writer.client.get(
        f"{GRAPH_ROOT}/drives/{writer.destination.drive_id}/items/{item_id}/content",
        headers=writer._headers() | {"Accept": "application/octet-stream"},
        timeout=120.0,
    )
    if response.status_code in {302, 303, 307, 308}:
        location = str(response.headers.get("Location", ""))
        parsed = urlparse(location)
        if (parsed.scheme != "https" or parsed.username or parsed.password
                or not (parsed.hostname or "").lower().endswith(".sharepoint.com")):
            raise RuntimeError("Safe destination upload failed")
        response = writer.client.get(
            location, headers={"Accept": "application/octet-stream"}, timeout=120.0,
        )
    if response.status_code != 200:
        raise RuntimeError("Safe destination upload failed")
    return hashlib.sha256(response.content).hexdigest() == sha256


def probe_named(writer: Any, folder_id: str, name: str, sha256: str) -> dict[str, Any]:
    item_path = (
        f"{GRAPH_ROOT}/drives/{writer.destination.drive_id}/items/"
        f"{folder_id}:/{quote(name, safe='')}:"
    )
    response = writer.client.get(
        item_path,
        headers=writer._headers() | {"Accept": "application/json"},
        params={"$select": "id,name,size,eTag,parentReference,file,webUrl"},
    )
    if response.status_code == 404:
        return {"state": "missing"}
    if response.status_code != 200:
        raise RuntimeError("Destination defect correlation changed")
    item = response.json()
    item_id = str(item.get("id", ""))
    web_url = str(item.get("webUrl", ""))
    parsed = urlparse(web_url)
    if (
        not _IDENTIFIER.fullmatch(item_id)
        or item.get("name") != name
        or str((item.get("parentReference") or {}).get("id", "")) != folder_id
        or not isinstance(item.get("file"), dict)
        or int(item.get("size", -1)) < 0
        or parsed.scheme != "https" or parsed.username or parsed.password
        or not (parsed.hostname or "").lower().endswith(".sharepoint.com")
    ):
        raise RuntimeError("Destination defect correlation changed")
    exact = _download_exact(writer, item_id, sha256)
    return {
        "state": "exact" if exact else "mismatch",
        "item_id": item_id,
        "web_url": web_url,
        "etag": str(item.get("eTag", ""))[:512],
    }


def upload_safe(writer: Any, folder_id: str, name: str, content: bytes, sha256: str) -> dict[str, str]:
    existing = probe_named(writer, folder_id, name, sha256)
    if existing["state"] == "exact":
        return {key: str(existing[key]) for key in ("item_id", "web_url", "etag")}
    if existing["state"] != "missing":
        raise RuntimeError("Safe destination already contains different bytes")
    item_path = (
        f"{GRAPH_ROOT}/drives/{writer.destination.drive_id}/items/"
        f"{folder_id}:/{quote(name, safe='')}:"
    )
    try:
        item = writer._upload_large(item_path, content)
    except Exception as exc:
        # A prior response may be lost after Graph commits the exact object.
        observed = probe_named(writer, folder_id, name, sha256)
        if observed["state"] == "exact":
            return {key: str(observed[key]) for key in ("item_id", "web_url", "etag")}
        raise RuntimeError("Safe destination upload failed") from exc
    item_id = str(item.get("id", ""))
    if not _IDENTIFIER.fullmatch(item_id) or not _download_exact(writer, item_id, sha256):
        raise RuntimeError("Safe destination upload failed")
    observed = probe_named(writer, folder_id, name, sha256)
    if observed["state"] != "exact" or observed.get("item_id") != item_id:
        raise RuntimeError("Safe destination upload failed")
    return {key: str(observed[key]) for key in ("item_id", "web_url", "etag")}


def _repair_rows(conn: Any, *, lock: bool = False) -> list[Any]:
    extraction = _json_expression(conn, "extraction,status")
    sql = (
        "SELECT c.* FROM m365_knowledge_candidates c "
        "WHERE c.status IN ('Approved for Promotion','Automatic Retry Required') "
        f"AND {extraction}='Complete' "
        "AND c.destination_drive_id='' AND c.destination_item_id='' "
        "AND c.destination_web_url='' AND c.destination_etag='' "
        "AND c.source_archive_item_id='' AND c.source_archive_web_url='' "
        "AND c.source_archive_etag='' AND c.source_archived_at='' "
        "AND NOT EXISTS (SELECT 1 FROM m365_bulk_items b "
        "WHERE b.drive_id=c.source_drive_id AND b.item_id=c.source_item_id) "
        "AND NOT EXISTS (SELECT 1 FROM m365_knowledge_events e "
        "WHERE e.candidate_id=c.id AND e.event_type=?) ORDER BY c.id"
    )
    if lock and getattr(conn, "backend", "sqlite") == "postgres":
        sql += " FOR UPDATE"
    rows = conn.execute(sql, (EVENT_TYPE,)).fetchall()
    observed = {status: 0 for status in EXPECTED_REPAIR}
    for row in rows:
        status = str(row["status"] or "")
        if status not in observed:
            raise RuntimeError("Destination-repair candidate pre-state changed")
        if status == "Approved for Promotion" and "automatically processed under" not in str(row["review_rationale"] or "").lower():
            raise RuntimeError("Destination-repair candidate pre-state changed")
        if status == "Automatic Retry Required" and "file could not be written" not in str(row["review_rationale"] or "").lower():
            raise RuntimeError("Destination-repair candidate pre-state changed")
        observed[status] += 1
    if observed != EXPECTED_REPAIR or len(rows) != 4:
        raise RuntimeError("Destination-repair candidate pre-state changed")
    return rows


def repair(
    conn: Any,
    writer: Any,
    emit: Callable[[str, str | int], None] | None = None,
    probe: Callable[[Any, str, str, str], dict[str, Any]] = probe_named,
    upload: Callable[[Any, str, str, bytes, str], dict[str, str]] = upload_safe,
) -> dict[str, int]:
    emit = emit or (lambda _key, _value: None)
    if _status_counts(conn) != EXPECTED_BEFORE:
        raise RuntimeError("Open candidate pre-state changed")
    rows = _repair_rows(conn)
    prepared: dict[int, dict[str, Any]] = {}
    emit("stage", "archive_and_destination_preflight")
    for row in rows:
        sha256 = str(row["source_sha256"] or "")
        if not re.fullmatch(r"[0-9a-f]{64}", sha256):
            raise RuntimeError("Archived original verification failed")
        archived = writer.verify_already_archived_source(
            str(row["source_item_id"]), sha256, include_content=True,
        )
        content = archived.get("content") if archived else None
        if (
            not archived or archived.get("item_id") != row["source_item_id"]
            or archived.get("etag") != row["source_etag"]
            or not isinstance(content, bytes)
            or len(content) != int(row["source_size"])
            or hashlib.sha256(content).hexdigest() != sha256
        ):
            raise RuntimeError("Archived original verification failed")
        folder_id = writer._resolve_folder(str(row["target_folder"] or ""))
        primary, fallback, repair_name = _destination_names(str(row["source_name"]), sha256)
        primary_state = probe(writer, folder_id, primary, sha256)["state"]
        fallback_state = probe(writer, folder_id, fallback, sha256)["state"]
        if row["status"] == "Approved for Promotion":
            if (primary_state, fallback_state) != ("missing", "missing"):
                raise RuntimeError("Destination defect correlation changed")
            destination_name = primary
            preserved_mismatch = False
        else:
            if sorted((primary_state, fallback_state)) != ["mismatch", "missing"]:
                raise RuntimeError("Destination defect correlation changed")
            if probe(writer, folder_id, repair_name, sha256)["state"] not in {"missing", "exact"}:
                raise RuntimeError("Safe destination already contains different bytes")
            destination_name = repair_name
            preserved_mismatch = True
        destination = upload(writer, folder_id, destination_name, content, sha256)
        prepared[int(row["id"])] = {
            "destination": destination,
            "archive": archived,
            "classification_json": str(row["classification_json"] or "{}"),
            "prior_status": str(row["status"]),
            "preserved_mismatch": preserved_mismatch,
        }

    emit("stage", "atomic_evidence_transition")
    timestamp = datetime.now(timezone.utc).replace(microsecond=0).isoformat()
    try:
        locked = _repair_rows(conn, lock=True)
        if {int(row["id"]) for row in locked} != set(prepared):
            raise RuntimeError("Destination-repair concurrency guard failed")
        for row in locked:
            candidate_id = int(row["id"])
            item = prepared[candidate_id]
            classification = json.loads(item["classification_json"])
            classification["destination_repair"] = {
                "status": "Verified",
                "method": "Conflict-safe exact-byte upload",
                "mismatched_object_preserved": item["preserved_mismatch"],
            }
            updated = conn.execute(
                "UPDATE m365_knowledge_candidates SET status='Ingested and Verified',"
                "classification_json=?,destination_drive_id=?,destination_item_id=?,"
                "destination_web_url=?,destination_etag=?,promoted_at=?,source_archived_at=?,"
                "source_archive_item_id=?,source_archive_web_url=?,source_archive_etag=? "
                "WHERE id=? AND status=? AND destination_item_id='' AND source_archive_item_id=''",
                (
                    json.dumps(classification, sort_keys=True, separators=(",", ":")),
                    writer.destination.drive_id,
                    item["destination"]["item_id"], item["destination"]["web_url"],
                    item["destination"]["etag"], timestamp, timestamp,
                    item["archive"]["item_id"], item["archive"]["web_url"],
                    item["archive"]["etag"], candidate_id, item["prior_status"],
                ),
            )
            if updated.rowcount != 1:
                raise RuntimeError("Destination-repair concurrency guard failed")
            conn.execute(
                "INSERT INTO m365_knowledge_events"
                "(candidate_id,event_type,actor,detail_json,created_at) VALUES(?,?,?,?,?)",
                (
                    candidate_id, EVENT_TYPE, ACTOR,
                    json.dumps({
                        "prior_status": item["prior_status"],
                        "status": "Ingested and Verified",
                        "destination_item_id": item["destination"]["item_id"],
                        "source_archive_item_id": item["archive"]["item_id"],
                        "mismatched_object_preserved": item["preserved_mismatch"],
                    }, sort_keys=True), timestamp,
                ),
            )
        remaining = _status_counts(conn)
        event_count = int(conn.execute(
            "SELECT COUNT(*) FROM m365_knowledge_events WHERE event_type=?", (EVENT_TYPE,),
        ).fetchone()[0] or 0)
        completed = int(conn.execute(
            "SELECT COUNT(*) FROM m365_knowledge_candidates c WHERE c.status='Ingested and Verified' "
            f"AND {_json_expression(conn, 'destination_repair,status')}='Verified' "
            "AND c.destination_item_id<>'' AND c.source_archive_item_id<>''",
        ).fetchone()[0] or 0)
        if remaining != {
            "Pending Review": 13, "Approved for Promotion": 0,
            "Automatic Retry Required": 0, "Destination Verified": 0,
        } or event_count != 4 or completed != 4:
            raise RuntimeError("Destination-repair readback is incomplete")
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    emit("stage", "committed")
    return {
        "destinations_verified": 4,
        "archive_evidence_reconciled": 4,
        "mismatched_objects_preserved": 1,
        "audit_events": 4,
        "pending_review_remaining": 13,
        "open_remaining": 13,
        "protected_member_access_changes": 0,
        "assignment_changes": 0,
        "releases": 0,
        "complete": 1,
    }


def main() -> None:
    def emit(key: str, value: str | int) -> None:
        print(f"DESTINATION_REPAIR_{key.upper()}={value}", flush=True)

    if os.getenv("SALUS_DB_BACKEND", "").strip().lower() != "postgres":
        raise RuntimeError("Live destination repair requires managed PostgreSQL")
    emit("stage", "database_connect")
    conn = connect_database()
    try:
        writer = GraphKnowledgeWriter(
            GovernedM365Config.from_environment(),
            KnowledgeDestinationConfig.from_environment(),
        )
        result = repair(conn, writer, emit)
    except Exception as exc:
        emit("failure", FAILURE_CODES.get(str(exc), "unexpected_graph_database_or_runtime_error"))
        emit("complete", 0)
        raise RuntimeError("Governed destination repair failed closed") from None
    finally:
        conn.close()
    for key in sorted(result):
        emit(key, result[key])


if __name__ == "__main__":
    main()
