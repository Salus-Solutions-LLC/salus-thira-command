"""Durable, bounded member index for an already verified enterprise ZIP source."""

from __future__ import annotations

import hashlib
import mimetypes
import time
import uuid

from salcapa_zip_members import ArchiveLimitError, iter_zip_members, zip_entry_count

MAX_TEXT_BYTES = 100_000


def create_tables(conn):
    conn.executescript("""
    CREATE TABLE IF NOT EXISTS m365_zip_jobs (
      candidate_id INTEGER PRIMARY KEY, source_sha256 TEXT NOT NULL,
      source_archive_item_id TEXT NOT NULL, next_ordinal INTEGER NOT NULL DEFAULT 0,
      total_entries INTEGER NOT NULL DEFAULT -1, status TEXT NOT NULL DEFAULT 'Pending',
      failure_code TEXT NOT NULL DEFAULT '', next_attempt INTEGER NOT NULL DEFAULT 0,
      lease_owner TEXT NOT NULL DEFAULT '', lease_until INTEGER NOT NULL DEFAULT 0,
      updated_at INTEGER NOT NULL DEFAULT 0
    );
    CREATE TABLE IF NOT EXISTS m365_zip_member_index (
      candidate_id INTEGER NOT NULL, ordinal INTEGER NOT NULL,
      member_path TEXT NOT NULL, path_sha256 TEXT NOT NULL,
      source_sha256 TEXT NOT NULL DEFAULT '', content_sha256 TEXT NOT NULL DEFAULT '',
      text_sha256 TEXT NOT NULL DEFAULT '', content_text TEXT NOT NULL DEFAULT '',
      size INTEGER NOT NULL DEFAULT 0, status TEXT NOT NULL,
      failure_code TEXT NOT NULL DEFAULT '', attempts INTEGER NOT NULL DEFAULT 0,
      next_attempt INTEGER NOT NULL DEFAULT 0, updated_at INTEGER NOT NULL,
      PRIMARY KEY(candidate_id,ordinal)
    );
    CREATE INDEX IF NOT EXISTS idx_m365_zip_member_retry
      ON m365_zip_member_index(candidate_id,status,next_attempt);
    """)


def enqueue(conn, candidate_id, source_sha256, archive_item_id, *, now=None):
    if (not isinstance(candidate_id,int) or candidate_id <= 0
            or len(source_sha256) != 64 or any(c not in '0123456789abcdef' for c in source_sha256)
            or not archive_item_id):
        raise ValueError("Verified ZIP source identity is incomplete")
    create_tables(conn)
    clock = int(time.time() if now is None else now)
    conn.execute(
        """INSERT INTO m365_zip_jobs
        (candidate_id,source_sha256,source_archive_item_id,updated_at)
        VALUES(?,?,?,?) ON CONFLICT(candidate_id) DO NOTHING""",
        (candidate_id,source_sha256,archive_item_id,clock),
    )
    row = conn.execute(
        "SELECT source_sha256,source_archive_item_id FROM m365_zip_jobs WHERE candidate_id=?",
        (candidate_id,),
    ).fetchone()
    if row["source_sha256"] != source_sha256 or row["source_archive_item_id"] != archive_item_id:
        raise ValueError("Verified ZIP source changed after indexing was queued")
    conn.commit()


def defer_job(connect, candidate_id, reason, *, now=None):
    """Back off a source read failure so one archive cannot starve the queue."""
    clock = int(time.time() if now is None else now)
    conn = connect()
    try:
        conn.execute(
            "UPDATE m365_zip_jobs SET next_attempt=?,failure_code=?,updated_at=? "
            "WHERE candidate_id=? AND status IN ('Pending','Partial')",
            (clock+300,str(reason)[:120],clock,candidate_id),
        )
        conn.commit()
    finally:
        conn.close()


def process_page(connect, candidate_id, source, decoder, *, failure_types=(), limit=20, now=None):
    """Checkpoint at most ``limit`` central-directory entries as separate records.

    ``source`` must be an archived original whose exact hash was verified before
    this call. A competing worker cannot commit the same page while its lease
    remains valid. If a process dies, the page is replayed idempotently.
    """
    if not 1 <= limit <= 100:
        raise ValueError("ZIP page limit is out of range")
    clock = int(time.time() if now is None else now)
    owner = uuid.uuid4().hex
    conn = connect()
    try:
        create_tables(conn)
        job = conn.execute(
            """UPDATE m365_zip_jobs SET lease_owner=?,lease_until=?
            WHERE candidate_id=? AND status IN ('Pending','Partial','Working')
              AND lease_until<? AND next_attempt<=?
            RETURNING source_sha256,next_ordinal,total_entries,status""",
            (owner,clock+300,candidate_id,clock,clock),
        ).fetchone()
        conn.commit()
        if job is None:
            return {"processed":0,"busy_or_complete":True}
        if hashlib.sha256(source).hexdigest() != job["source_sha256"]:
            raise ValueError("Archived ZIP source hash differs from the queued original")
        try:
            total = zip_entry_count(source)
        except ArchiveLimitError as exc:
            conn.execute(
                "UPDATE m365_zip_jobs SET status='Partial',failure_code=?,next_attempt=?,"
                "lease_owner='',lease_until=0 WHERE candidate_id=? AND lease_owner=?",
                (exc.code,clock+3600,candidate_id,owner),
            )
            conn.commit()
            return {"processed":0,"failure_code":exc.code}
        if job["total_entries"] not in (-1,total):
            raise ValueError("Archived ZIP entry count changed")
        start = job["next_ordinal"]
        retry_phase = start >= total
        if retry_phase:
            retry_rows = conn.execute(
                "SELECT ordinal FROM m365_zip_member_index WHERE candidate_id=? "
                "AND status='Retry' AND next_attempt<=? ORDER BY next_attempt,ordinal LIMIT ?",
                (candidate_id,clock,limit),
            ).fetchall()
            ordinals = [row["ordinal"] for row in retry_rows]
        else:
            ordinals = list(range(start,min(start+limit,total)))
        records = []
        if retry_phase:
            for ordinal in ordinals:
                records.extend(iter_zip_members(source,start=ordinal,limit=1))
        elif ordinals:
            records = list(iter_zip_members(source,start=start,limit=len(ordinals)))
        for member in records:
            path = member["path"]
            sha = member.get("sha256", "")
            text_hash = ""
            excerpt = ""
            code = member.get("reason", "")
            status = ("Review" if code in {"unsafe_member_path", "duplicate_member_path",
                       "unsupported_member_type", "encrypted_member", "member_size_limit",
                       "member_compression_limit", "nested_archive_requires_review"}
                      else "Retry") if member["status"] != "Ready" else "Indexed"
            if status == "Indexed":
                try:
                    mime = mimetypes.guess_type(path)[0] or "application/octet-stream"
                    text_value = decoder(member["content"],path,mime)
                    if not isinstance(text_value,str):
                        raise ValueError("ZIP member decoder returned invalid text")
                    encoded = text_value.encode("utf-8")
                    text_hash = hashlib.sha256(encoded).hexdigest()
                    excerpt = encoded[:MAX_TEXT_BYTES].decode("utf-8",errors="ignore")
                except failure_types as exc:
                    status,code = "Retry",str(getattr(exc,"code","member_processing_failed"))[:120]
            previous = conn.execute(
                "SELECT attempts FROM m365_zip_member_index WHERE candidate_id=? AND ordinal=?",
                (candidate_id,member["ordinal"]),
            ).fetchone()
            attempts = (previous["attempts"] if previous else 0) + 1
            delay = min(3600,30 * (2 ** min(attempts-1,7))) if status == "Retry" else 0
            conn.execute(
                """INSERT INTO m365_zip_member_index
                (candidate_id,ordinal,member_path,path_sha256,source_sha256,content_sha256,
                 text_sha256,content_text,size,status,failure_code,attempts,next_attempt,updated_at)
                VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?)
                ON CONFLICT(candidate_id,ordinal) DO UPDATE SET
                  member_path=excluded.member_path,path_sha256=excluded.path_sha256,
                  content_sha256=excluded.content_sha256,text_sha256=excluded.text_sha256,
                  content_text=excluded.content_text,size=excluded.size,status=excluded.status,
                  failure_code=excluded.failure_code,attempts=excluded.attempts,
                  next_attempt=excluded.next_attempt,updated_at=excluded.updated_at""",
                (candidate_id,member["ordinal"],path,member["path_sha256"],
                 job["source_sha256"],sha,text_hash,excerpt,member["size"],status,code,
                 attempts,clock+delay,clock),
            )
        next_ordinal = total if retry_phase else min(start+limit,total)
        retry = conn.execute(
            "SELECT MIN(next_attempt) FROM m365_zip_member_index "
            "WHERE candidate_id=? AND status='Retry'",(candidate_id,),
        ).fetchone()[0]
        reviewed = conn.execute(
            "SELECT 1 FROM m365_zip_member_index WHERE candidate_id=? AND status='Review' LIMIT 1",
            (candidate_id,),
        ).fetchone()
        status = ("Review" if reviewed else "Complete") if next_ordinal == total and retry is None else "Partial" if next_ordinal == total else "Pending"
        conn.execute(
            """UPDATE m365_zip_jobs SET next_ordinal=?,total_entries=?,status=?,
               failure_code='',next_attempt=?,updated_at=?,lease_owner='',lease_until=0
               WHERE candidate_id=? AND lease_owner=?""",
            (next_ordinal,total,status,(retry or 0) if next_ordinal == total else 0,
             clock,candidate_id,owner),
        )
        conn.commit()
        return {"processed":len(records),"next_ordinal":next_ordinal,
                "total_entries":total,"status":status}
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()
