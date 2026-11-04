"""Corpus-wide, Salus-only consideration of the governed Knowledge Library."""

from __future__ import annotations

import hashlib
import json
import os
import re
import uuid
from typing import Any

from fastapi import Query


EXPECTED_MINIMUM_FILES = 22_377
MAX_RESULTS = 100


def _terms(value: str) -> list[str]:
    words = re.findall(r"[a-z0-9][a-z0-9._-]{1,79}", value.casefold())
    return list(dict.fromkeys(words))[:20]


def _patterns(terms: list[str]) -> tuple[str, tuple[str, ...]]:
    clause = " OR ".join("lower(search_text) LIKE ?" for _ in terms)
    return clause, tuple(f"%{term}%" for term in terms)


def _excerpt(text: str, terms: list[str]) -> str:
    normalized = str(text or "")
    lowered = normalized.casefold()
    positions = [lowered.find(term) for term in terms if lowered.find(term) >= 0]
    start = max(0, (min(positions) if positions else 0) - 180)
    return normalized[start:start + 700]


def _create_receipt_table(conn: Any) -> None:
    conn.executescript("""
    CREATE TABLE IF NOT EXISTS m365_knowledge_consideration_receipts (
      receipt_id TEXT PRIMARY KEY,
      query_sha256 TEXT NOT NULL,
      boundary_count INTEGER NOT NULL,
      considered_count INTEGER NOT NULL,
      matched_count INTEGER NOT NULL,
      content_available_count INTEGER NOT NULL,
      metadata_only_count INTEGER NOT NULL,
      governed_hold_count INTEGER NOT NULL,
      actor TEXT NOT NULL,
      created_at TEXT NOT NULL
    );
    """)


def consider(conn: Any, query: str, actor: str, created_at: str) -> dict[str, Any]:
    """Consider every represented file and return bounded relevant candidates plus coverage."""
    terms = _terms(query)
    if not terms:
        raise ValueError("A material inquiry of at least two searchable characters is required")

    represented_cte = """
      WITH represented AS (
        SELECT source_item_id FROM m365_knowledge_candidates
        UNION
        SELECT source_item_id FROM m365_knowledge_holds WHERE status='Governed Hold'
        UNION
        SELECT item_id FROM m365_bulk_items WHERE kind='file' AND status<>'Removed'
      )
    """
    represented_count = int(conn.execute(
        represented_cte + "SELECT COUNT(*) count FROM represented"
    ).fetchone()["count"])
    boundary_count = int(os.getenv(
        "SALUS_KNOWLEDGE_MINIMUM_BOUNDARY_FILES", EXPECTED_MINIMUM_FILES
    ))
    if represented_count < boundary_count:
        raise RuntimeError("The governed Knowledge Library boundary is incomplete")
    historical_additional = represented_count - boundary_count

    content_available = int(conn.execute(
        represented_cte + """
          SELECT COUNT(DISTINCT c.source_item_id) count
          FROM m365_knowledge_candidates c
          JOIN represented r ON r.source_item_id=c.source_item_id
          WHERE c.classification_json LIKE '%\"status\": \"Complete\"%'
        """
    ).fetchone()["count"])
    governed_holds = int(conn.execute(
        represented_cte + """
          SELECT COUNT(DISTINCT h.source_item_id) count
          FROM m365_knowledge_holds h
          JOIN represented r ON r.source_item_id=h.source_item_id
          WHERE h.status='Governed Hold'
        """
    ).fetchone()["count"])

    clause, parameters = _patterns(terms)
    searchable_cte = represented_cte + """
      , searchable AS (
        SELECT c.source_item_id,
          c.source_name || ' ' || c.source_relative_path || ' ' || c.classification_json search_text
        FROM m365_knowledge_candidates c JOIN represented r ON r.source_item_id=c.source_item_id
        UNION ALL
        SELECT b.item_id,
          b.name || ' ' || b.metadata_json || ' ' || b.status || ' ' || b.reason search_text
        FROM m365_bulk_items b JOIN represented r ON r.source_item_id=b.item_id
        WHERE b.kind='file'
        UNION ALL
        SELECT h.source_item_id,
          h.source_name || ' ' || h.source_relative_path || ' ' || h.source_area || ' ' || h.hold_reason search_text
        FROM m365_knowledge_holds h JOIN represented r ON r.source_item_id=h.source_item_id
        WHERE h.status='Governed Hold'
      ), matched AS (
        SELECT DISTINCT source_item_id FROM searchable WHERE """ + clause + ") "
    matched_count = int(conn.execute(
        searchable_cte + "SELECT COUNT(*) count FROM matched", parameters
    ).fetchone()["count"])

    results: list[dict[str, Any]] = []
    seen: set[str] = set()
    candidate_rows = conn.execute(
        represented_cte
        + "SELECT c.source_item_id,c.source_name,c.source_relative_path,c.source_sha256,"
        "source_modified_at,source_owner,status,target_folder,classification_json "
        "FROM m365_knowledge_candidates c JOIN represented r ON r.source_item_id=c.source_item_id WHERE "
        + " OR ".join(
            "lower(source_name || ' ' || source_relative_path || ' ' || classification_json) LIKE ?"
            for _ in terms
        )
        + " ORDER BY id DESC LIMIT ?",
        parameters + (MAX_RESULTS,),
    ).fetchall()
    for row in candidate_rows:
        source_id = str(row["source_item_id"])
        if source_id in seen:
            continue
        seen.add(source_id)
        try:
            classification = json.loads(row["classification_json"] or "{}")
        except (TypeError, ValueError):
            classification = {}
        extraction = classification.get("extraction") or {}
        citation = classification.get("citation_metadata") or {}
        complete = extraction.get("status") == "Complete"
        results.append({
            "record_key": hashlib.sha256(source_id.encode()).hexdigest(),
            "title": citation.get("document_title") or row["source_name"],
            "relative_path": row["source_relative_path"],
            "source_sha256": row["source_sha256"],
            "source_modified_at": row["source_modified_at"],
            "source_owner": row["source_owner"],
            "target_folder": row["target_folder"],
            "candidate_state": "Unvetted Candidate",
            "representation": "Extracted content and metadata" if complete else "Metadata and unresolved extraction record",
            "content_preview": _excerpt(extraction.get("text", ""), terms) if complete else "",
            "limitation": "" if complete else str(extraction.get("failure_detail") or extraction.get("failure_code") or "Content extraction remains unresolved"),
            "citation_metadata": citation,
            "customer_release_ready": False,
        })

    remaining = MAX_RESULTS - len(results)
    if remaining:
        hold_rows = conn.execute(
            represented_cte
            + "SELECT h.source_item_id,h.source_name,h.source_relative_path,h.source_area,h.hold_reason "
            "FROM m365_knowledge_holds h JOIN represented r ON r.source_item_id=h.source_item_id "
            "WHERE h.status='Governed Hold' AND ("
            + " OR ".join(
                "lower(h.source_name || ' ' || h.source_relative_path || ' ' || "
                "h.source_area || ' ' || h.hold_reason) LIKE ?"
                for _ in terms
            )
            + ") ORDER BY h.source_item_id LIMIT ?",
            parameters + (remaining,),
        ).fetchall()
        for row in hold_rows:
            source_id = str(row["source_item_id"])
            if source_id in seen:
                continue
            seen.add(source_id)
            results.append({
                "record_key": hashlib.sha256(source_id.encode()).hexdigest(),
                "title": row["source_name"],
                "relative_path": row["source_relative_path"],
                "source_area": row["source_area"],
                "candidate_state": "Unvetted Candidate",
                "representation": "Governed hold metadata",
                "content_preview": "",
                "limitation": row["hold_reason"] or "Content remains under governed hold",
                "customer_release_ready": False,
            })
            if len(results) >= MAX_RESULTS:
                break

    remaining = MAX_RESULTS - len(results)
    if remaining:
        metadata_rows = conn.execute(
            represented_cte
            + "SELECT b.item_id source_item_id,b.name,b.metadata_json,b.status,b.reason "
            "FROM m365_bulk_items b JOIN represented r ON r.source_item_id=b.item_id "
            "WHERE b.kind='file' AND ("
            + " OR ".join(
                "lower(b.name || ' ' || b.metadata_json || ' ' || b.status || ' ' || b.reason) LIKE ?"
                for _ in terms
            )
            + ") ORDER BY b.updated_at DESC LIMIT ?",
            parameters + (remaining,),
        ).fetchall()
        for row in metadata_rows:
            source_id = str(row["source_item_id"])
            if source_id in seen:
                continue
            seen.add(source_id)
            metadata = json.loads(row["metadata_json"] or "{}")
            results.append({
                "record_key": hashlib.sha256(source_id.encode()).hexdigest(),
                "title": row["name"],
                "relative_path": metadata.get("relative_path", ""),
                "candidate_state": "Unvetted Candidate",
                "representation": "Provenance-bound metadata",
                "content_preview": "",
                "limitation": row["reason"] or "Content has not produced a searchable extraction",
                "customer_release_ready": False,
            })
            if len(results) >= MAX_RESULTS:
                break

    receipt_id = str(uuid.uuid4())
    query_sha256 = hashlib.sha256(query.strip().encode("utf-8")).hexdigest()
    metadata_only = max(0, represented_count - min(content_available, represented_count))
    _create_receipt_table(conn)
    conn.execute(
        "INSERT INTO m365_knowledge_consideration_receipts VALUES(?,?,?,?,?,?,?,?,?,?)",
        (receipt_id, query_sha256, boundary_count, represented_count, matched_count,
         content_available, metadata_only, governed_holds, actor[:240], created_at),
    )
    conn.commit()
    return {
        "receipt_id": receipt_id,
        "query_sha256": query_sha256,
        "results": results,
        "coverage": {
            "boundary_files": boundary_count,
            "represented_files": represented_count,
            "considered_files": represented_count,
            "historical_additional_representations": historical_additional,
            "matched_files": matched_count,
            "considered_without_match": represented_count - matched_count,
            "content_available_files": content_available,
            "metadata_only_or_unresolved_files": metadata_only,
            "governed_hold_files": governed_holds,
            "all_boundary_files_considered": True,
            "all_represented_files_considered": True,
        },
        "use_state": "Salus-internal Unvetted Candidate",
        "release_gate": "Human validation is required before customer-facing release or material reliance.",
        "protected_member_access": False,
        "assignment_or_release_authority": False,
    }


def register_knowledge_consideration(app: Any, namespace: dict[str, Any]) -> None:
    Request = namespace["Request"]
    HTTPException = namespace["HTTPException"]
    db = namespace["db"]
    now = namespace["now"]
    auth_context = namespace["auth_context"]
    protected_member_request = namespace.get("protected_member_request", lambda _request: False)

    def corpus_consideration(request, q: str = Query(min_length=2, max_length=500)):
        context = auth_context(request)
        if protected_member_request(request) or context.get("role") != "System Administrator":
            raise HTTPException(403, "Salus Knowledge consideration authority is required")
        conn = db()
        try:
            return consider(
                conn, q,
                str(context.get("username") or context.get("display_name") or "authorized-user"),
                now(),
            )
        except ValueError as exc:
            raise HTTPException(422, str(exc)) from exc
        except RuntimeError as exc:
            raise HTTPException(409, str(exc)) from exc
        finally:
            conn.close()

    corpus_consideration.__annotations__["request"] = Request
    app.get(
        "/api/integrations/m365/knowledge/consideration", include_in_schema=False
    )(corpus_consideration)
