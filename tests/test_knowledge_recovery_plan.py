"""Availability, exact per-source batches, atomicity, drift and privacy proofs."""
import contextlib
import copy
import hashlib
import io
import json
import os
import sqlite3
import tempfile
import unittest
from tools import live_knowledge_recovery_plan as plan

SCHEMA = """
CREATE TABLE m365_knowledge_candidates(id BIGINT PRIMARY KEY, source_drive_id TEXT,source_item_id TEXT,
 source_etag TEXT,source_sha256 TEXT,source_size BIGINT,source_modified_at TEXT,source_archive_item_id TEXT,
 source_archive_etag TEXT,source_archived_at TEXT,status TEXT,decision TEXT,reviewed_at TEXT,
 destination_item_id TEXT,destination_etag TEXT,source_removed_at TEXT,classification_json TEXT,
 reviewed_by TEXT DEFAULT '',review_rationale TEXT DEFAULT '');
CREATE TABLE m365_knowledge_holds(source_drive_id TEXT,source_item_id TEXT,source_parent_id TEXT,source_etag TEXT,
 source_size BIGINT,source_modified_at TEXT,source_area TEXT,status TEXT,hold_reason TEXT,
 research_disposition TEXT,teaching_disposition TEXT,citation_disposition TEXT,reviewed_by TEXT,reviewed_at TEXT,review_rationale TEXT);
CREATE TABLE m365_bulk_items(drive_id TEXT,pending_id TEXT,item_id TEXT,parent_id TEXT,etag TEXT,size BIGINT,
 status TEXT,attempts INTEGER,next_attempt BIGINT,updated_at BIGINT,lease_owner TEXT,lease_until BIGINT,kind TEXT,reason TEXT DEFAULT '');
CREATE TABLE m365_bulk_extraction_checks(candidate_id BIGINT,attempts INTEGER,next_attempt BIGINT,
 lease_owner TEXT,lease_until BIGINT,checked_at BIGINT,last_code TEXT);
"""
CLOCK = 1794747600
COHORTS = {k: 0 for k in plan.CATEGORIES}
COHORTS.update(governed_review=1,retry_paused=1,automatic_retry=1,governed_hold=1,other_or_conflicting=1)


class PlanningTests(unittest.TestCase):
    def connect(self):
        c = sqlite3.connect(self.path)
        c.row_factory = sqlite3.Row
        c.create_function("sha256text", 1, lambda v: hashlib.sha256(v.encode()).hexdigest())
        return c

    def setUp(self):
        self.folder = tempfile.TemporaryDirectory()
        self.path = os.path.join(self.folder.name, "fixture.db")
        self.conn = self.connect()
        self.conn.executescript(SCHEMA)
        # Five unresolved sources; source 5 has two conflicting versions. Source
        # 6 is a sixth, separate legacy-available false positive, not unresolved.
        states = [("s1", "Review Required", "PDF_ENCRYPTED"),
                  ("s2", "Retry Paused", "IMAGE_RESOURCE_LIMIT"),
                  ("s3", "Automatic Retry Required", "DOCUMENT_EXPANSION_LIMIT"),
                  ("s5", "Review Required", "PDF_ACTIVE_CONTENT"),
                  ("s5", "Retry Paused", "PDF_RESOURCE_LIMIT"),
                  ("s6", "Review Required", "PDF_ENCRYPTED")]
        for n, (source, status, code) in enumerate(states, 1):
            obj = {"extraction": {"status": status, "text": "", "failure_code": code}}
            if source == "s6": obj["unrelated"] = {"status": "Complete"}
            self.insert(n, source, obj, archive="" if source == "s3" else "PRIVATE-ARCHIVE")
        self.conn.execute("INSERT INTO m365_knowledge_holds VALUES(" + ",".join("?" for _ in range(15)) + ")",
            ("PRIVATE-DRIVE", "s4", "PRIVATE-PARENT", "v1", 12, "stamp", "Does Not Upload", "Governed Hold", "PRIVATE-REASON",
             "Pending", "Pending", "Pending", "", "", ""))
        for source in ["s1", "s2", "s3", "s4", "s5", "s6"]:
            self.conn.execute("INSERT INTO m365_bulk_items(drive_id,pending_id,item_id,parent_id,etag,size,status,attempts,next_attempt,updated_at,lease_owner,lease_until,kind) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)",
                ("PRIVATE-DRIVE", "PRIVATE-FOLDER", source, "PRIVATE-PARENT", "v1", 12, "Assignment Required", 2, 0, 1, "", 0, "file"))
        for n in range(1, 7):
            self.conn.execute("INSERT INTO m365_bulk_extraction_checks VALUES(?,?,?,?,?,?,?)",
                (n, 8, 4102444800 if n == 2 else 0, "PRIVATE-LEASE" if n == 3 else "", CLOCK + 100 if n == 3 else 0, 9, "PRIVATE-ERROR"))
        self.conn.commit()
        self.inventory = {s: {"etag": "v1", "size": 12, "parent_id": "PRIVATE-PARENT",
            "area_id": "PRIVATE-FOLDER", "area": "10 Pending Classification"} for s in ["s1", "s2", "s3", "s4", "s5", "s6"]}

    def insert(self, n, source, obj, *, archive="PRIVATE-ARCHIVE", compact=False):
        encoded = json.dumps(obj, separators=(",", ":")) if compact else json.dumps(obj)
        self.conn.execute("INSERT INTO m365_knowledge_candidates(id,source_drive_id,source_item_id,source_etag,source_sha256,source_size,source_modified_at,source_archive_item_id,source_archive_etag,source_archived_at,status,decision,reviewed_at,destination_item_id,destination_etag,source_removed_at,classification_json) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (n, "PRIVATE-DRIVE", source, "v1" if n != 5 else "v0", "a" * 64, 12,
             "2026-11-15T05:00:00Z", archive, "av1", "2026-11-15T06:00:00Z", "Ingested and Verified",
             "", "", "", "", "", encoded))

    def tearDown(self):
        self.conn.close()
        self.folder.cleanup()

    def build(self):
        evidence = plan.read_evidence(self.conn)
        return evidence, plan.make_plan(evidence, self.inventory, clock=CLOCK,
                                       expected_cohorts=COHORTS, expected_discrepancies=1)

    def test_exact_five_way_partition_retains_both_versions_and_separate_exception(self):
        evidence, result = self.build()
        self.assertEqual(result["summary"]["categories"], COHORTS)
        records = [r for b in result["batches"] for r in b["records"]]
        self.assertEqual({r["source_item_id"] for r in records}, {"s1", "s2", "s3", "s4", "s5"})
        self.assertEqual(len(records), 5)
        self.assertEqual(len(next(r for r in records if r["source_item_id"] == "s5")["candidate_versions"]), 2)
        self.assertEqual(result["availability_exceptions"][0]["source_item_id"], "s6")
        self.assertEqual(result["availability_exceptions"][0]["candidate_versions"][0]["availability_condition"],
                         "BROAD_COMPLETE_MATCH_OUTSIDE_EXTRACTION_STATUS")
        self.assertEqual(result["summary"]["overlapping_traits"]["active_lease_sources"], 1)
        self.assertEqual(result["summary"]["overlapping_traits"]["no_recorded_archive_sources"], 1)
        matrix = result["summary"]["candidate_cross_matrix"]
        self.assertEqual(matrix["retry_paused/IMAGE_RESOURCE_LIMIT/future"], 1)
        self.assertEqual(matrix["automatic_retry/DOCUMENT_EXPANSION_LIMIT/leased"], 1)
        self.assertFalse(any(r["processing_authorized"] for r in records))

    def test_complete_empty_text_is_a_different_exact_diagnosis(self):
        obj = {"extraction": {"status": "Complete", "text": ""}}
        self.conn.execute("UPDATE m365_knowledge_candidates SET classification_json=? WHERE id=6", (json.dumps(obj),))
        _, result = self.build()
        self.assertEqual(result["availability_exceptions"][0]["candidate_versions"][0]["availability_condition"], "EXACT_COMPLETE_EMPTY_TEXT")

    def test_compact_json_whitespace_and_nonstring_text_fail_closed(self):
        for obj, compact in (({"status": "Complete", "text": "substance"}, True),
                             ({"status": "Complete", "text": "\t\r\n"}, False),
                             ({"status": "Complete", "text": 123}, False)):
            self.conn.execute("DELETE FROM m365_knowledge_candidates WHERE id=6")
            self.insert(6, "s6", {"extraction": obj}, compact=compact)
            with self.assertRaises(RuntimeError): self.build()

    def test_checkpoint_and_candidate_drift_prevent_any_manifest_commit(self):
        for field in ("checkpoint", "candidate", "hold", "bulk"):
            self.conn.execute("UPDATE m365_bulk_extraction_checks SET attempts=8 WHERE candidate_id=1")
            self.conn.execute("UPDATE m365_knowledge_candidates SET source_etag='v1' WHERE id=1")
            self.conn.execute("UPDATE m365_knowledge_holds SET status='Governed Hold'")
            self.conn.execute("UPDATE m365_bulk_items SET lease_owner='' WHERE item_id='s1'")
            self.conn.commit()
            evidence, result = self.build()
            if field == "checkpoint": self.conn.execute("UPDATE m365_bulk_extraction_checks SET attempts=attempts+1 WHERE candidate_id=1")
            elif field == "candidate": self.conn.execute("UPDATE m365_knowledge_candidates SET source_etag='changed' WHERE id=1")
            elif field == "hold": self.conn.execute("UPDATE m365_knowledge_holds SET status='changed'")
            else: self.conn.execute("UPDATE m365_bulk_items SET lease_owner='changed' WHERE item_id='s1'")
            self.conn.commit()
            with self.assertRaises(RuntimeError): plan.save_plan(self.conn, evidence, result)
            # Rollback must not undo the independently committed source drift.
            self.assertNotEqual(plan.read_evidence(self.conn), evidence)

    def test_atomic_rollback_replay_prevention_and_fresh_connection_readback(self):
        evidence, result = self.build()
        plan.create_plan_tables(self.conn)
        self.conn.commit()
        with self.assertRaises(RuntimeError): plan.save_plan(self.conn, evidence, result, fail_after_batches=True)
        self.assertEqual(self.conn.execute("SELECT COUNT(*) FROM m365_knowledge_recovery_batches").fetchone()[0], 0)
        checksum = plan.save_plan(self.conn, evidence, result)
        fresh = self.connect()
        try:
            self.assertEqual(plan.verify_plan(fresh, result), checksum)
            self.assertEqual(plan.read_evidence(fresh), evidence)
        finally: fresh.close()
        with self.assertRaises(RuntimeError): plan.save_plan(self.conn, evidence, result)
        self.assertEqual(self.conn.execute("SELECT COUNT(*) FROM m365_knowledge_recovery_plan_events").fetchone()[0], 1)

    def test_corruption_of_batch_manifest_or_event_is_detected_independently(self):
        evidence, result = self.build()
        plan.save_plan(self.conn, evidence, result)
        for table, field in (("m365_knowledge_recovery_batches", "record_count"),
                             ("m365_knowledge_recovery_plans", "manifest_sha256"),
                             ("m365_knowledge_recovery_plan_events", "detail_json")):
            self.conn.execute("UPDATE " + table + " SET " + field + "=?", (999 if field == "record_count" else "corrupt",))
            self.conn.commit()
            fresh = self.connect()
            try:
                with self.assertRaises(RuntimeError): plan.verify_plan(fresh, result)
            finally: fresh.close()
            self.conn.execute("DELETE FROM m365_knowledge_recovery_plans")
            self.conn.execute("DELETE FROM m365_knowledge_recovery_batches")
            self.conn.execute("DELETE FROM m365_knowledge_recovery_plan_events")
            self.conn.commit()
            plan.save_plan(self.conn, evidence, result)

    def test_batch_bound_and_no_cross_code_mixing(self):
        for n in range(7, 108):
            self.insert(n, "extra-" + str(n), {"extraction": {"status": "Review Required", "failure_code": "PDF_ENCRYPTED"}})
        self.conn.commit()
        evidence = plan.read_evidence(self.conn)
        counts = dict(COHORTS)
        counts["governed_review"] += 101
        result = plan.make_plan(evidence, self.inventory, clock=CLOCK, expected_cohorts=counts, expected_discrepancies=1)
        self.assertTrue(all(b["record_count"] <= 50 for b in result["batches"]))
        self.assertEqual(result["summary"]["prepared_sources"], 106)
        for b in result["batches"]:
            self.assertTrue(all(r["failure_codes"] == b["failure_codes"] for r in b["records"]))

    def test_telemetry_never_exposes_private_metadata_or_content(self):
        _, result = self.build()
        with contextlib.redirect_stdout(io.StringIO()) as out: plan.emit_plan_summary(result, "a" * 64)
        for forbidden in ("PRIVATE", "s1", "source_item_id", "archive_item_id", "classification_json"):
            self.assertNotIn(forbidden, out.getvalue())
        self.assertIn("PREPARED_SOURCES=5", out.getvalue())

    def test_source_tables_refuse_writes_through_complete_planning_transaction(self):
        if getattr(self.conn, "backend", "sqlite") != "sqlite": self.skipTest("SQLite write-denial regression")
        forbidden = set(plan.SOURCE_TABLES)
        self.conn.set_authorizer(lambda action, a1, *_: sqlite3.SQLITE_DENY
            if action in (sqlite3.SQLITE_INSERT, sqlite3.SQLITE_UPDATE, sqlite3.SQLITE_DELETE) and a1 in forbidden else sqlite3.SQLITE_OK)
        evidence, result = self.build()
        plan.save_plan(self.conn, evidence, result)
        self.assertEqual(plan.read_evidence(self.conn), evidence)

    def test_hold_reason_and_classification_content_drift_are_bound_without_text_output(self):
        evidence, result = self.build()
        self.conn.execute("UPDATE m365_knowledge_holds SET hold_reason='changed-private-reason'")
        self.conn.commit()
        with self.assertRaises(RuntimeError): plan.save_plan(self.conn, evidence, result)
        evidence, result = self.build()
        self.conn.execute("UPDATE m365_knowledge_candidates SET classification_json=? WHERE id=1",
            (json.dumps({"extraction": {"status": "Review Required", "text": "PRIVATE CONTENT", "failure_code": "PDF_ENCRYPTED"}}),))
        self.conn.commit()
        with self.assertRaises(RuntimeError): plan.save_plan(self.conn, evidence, result)


@unittest.skipUnless(os.getenv("TEST_RECOVERY_POSTGRES") == "1", "dedicated CI PostgreSQL only")
class PostgreSQLPlanningTests(PlanningTests):
    def connect(self):
        from database import connect_database
        return connect_database()

    def setUp(self):
        assert os.getenv("SALUS_DATABASE_URL", "").startswith("postgresql://postgres:postgres@localhost:5432/recovery_plan") # repo-hygiene: allow - localhost-only ephemeral PostgreSQL CI fixture
        self.conn = self.connect()
        for t in (*plan.PLAN_TABLES, *plan.SOURCE_TABLES): self.conn.execute("DROP TABLE IF EXISTS " + t)
        self.conn.commit()
        self.conn.close()
        # Parent creates a temp path only for SQLite. Its overridden connect()
        # uses the dedicated real PostgreSQL service throughout.
        super().setUp()

    def tearDown(self):
        self.conn.rollback()
        for t in (*plan.PLAN_TABLES, *plan.SOURCE_TABLES): self.conn.execute("DROP TABLE IF EXISTS " + t)
        self.conn.commit()
        super().tearDown()

    def test_concurrent_writer_blocks_commit_without_waiting_or_changing_source(self):
        evidence, result = self.build()
        other = self.connect()
        try:
            other.execute("UPDATE m365_bulk_extraction_checks SET attempts=attempts+1 WHERE candidate_id=1")
            with self.assertRaises(Exception): plan.save_plan(self.conn, evidence, result)
            other.rollback()
            self.assertEqual(plan.read_evidence(self.conn), evidence)
        finally: other.close()


if __name__ == "__main__": unittest.main()
