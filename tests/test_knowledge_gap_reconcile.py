"""Atomic parked representation, durable audit and root-scope validation tests."""
import contextlib
import io
import json
import os
import sqlite3
import unittest
from types import SimpleNamespace
from tools import live_knowledge_gap_reconcile as gap

TABLES = ("m365_knowledge_representation_events","m365_knowledge_representation_batches",
          "m365_bulk_items","m365_knowledge_candidates","m365_knowledge_holds")
SCHEMA = """
CREATE TABLE m365_bulk_items (
 drive_id TEXT,pending_id TEXT,item_id TEXT,parent_id TEXT,name TEXT,kind TEXT,etag TEXT,
 size BIGINT,metadata_json TEXT,status TEXT,reason TEXT,attempts INTEGER DEFAULT 0,
 next_attempt BIGINT DEFAULT 0,updated_at BIGINT,seen_generation INTEGER DEFAULT 0,
 lease_owner TEXT DEFAULT '',lease_until BIGINT DEFAULT 0,
 PRIMARY KEY(drive_id,pending_id,item_id));
CREATE TABLE m365_knowledge_candidates(source_item_id TEXT,classification_json TEXT);
CREATE TABLE m365_knowledge_holds(source_item_id TEXT,status TEXT);
"""
STAMP = "2026-11-15T04:30:00+00:00"

def item(key, area="10 Pending Classification"):
    return {"item_id":key,"area_id":"area-" + gap.AREA_CODES[area],"area":area,
            "parent_id":"nested-0000","name":"fictional.txt","etag":"version-1","size":123,
            "metadata_json":gap.canonical({"last_modified":STAMP,"relative_path":area+"/fictional.txt",
                "representation_only":True,"processing_authorized":False})}

class EnrollmentTests(unittest.TestCase):
    def setUp(self):
        self.conn = sqlite3.connect(":memory:")
        self.conn.row_factory = sqlite3.Row
        self.conn.executescript(SCHEMA)
        self.conn.commit()
    def tearDown(self):
        self.conn.close()
    def count(self, table):
        assert table in TABLES
        return self.conn.execute("SELECT COUNT(*) FROM " + table).fetchone()[0]
    def enroll(self, inventory):
        plan = gap.coverage_plan(self.conn, inventory)
        self.conn.commit()
        result = gap.enroll_missing(self.conn, inventory, plan, "drive-0000", "root-0000", STAMP)
        gap.verify_enrollment(self.conn, plan, "drive-0000", "root-0000", result)
        return plan,result
    def test_all_areas_are_scoped_and_parked_without_reprocessing(self):
        inventory = {f"source-{n:04d}":item(f"source-{n:04d}",area) for n,area in enumerate(gap.AREA_CODES)}
        plan,result = self.enroll(inventory)
        self.assertEqual(result["item_count"],7)
        self.assertEqual(self.count("m365_knowledge_representation_events"),7)
        rows = self.conn.execute("SELECT * FROM m365_bulk_items").fetchall()
        for row in rows:
            self.assertEqual(row["pending_id"],"root-0000")
            self.assertNotEqual(row["pending_id"],inventory[row["item_id"]]["area_id"])
            self.assertEqual(row["status"],"Assignment Required")
            self.assertNotIn(row["status"],("Pending","Retry","Working"))
            self.assertEqual(row["attempts"],0)
            self.assertEqual(json.loads(row["metadata_json"])["processing_authorized"],False)
        self.assertEqual(gap.coverage_plan(self.conn,inventory),{})
    def test_preserves_existing_candidate_hold_and_work_states(self):
        self.conn.execute("INSERT INTO m365_knowledge_candidates VALUES(?,?)",
                          ("candidate-0000",'{"extraction":{"status":"Retry Paused"}}'))
        self.conn.execute("INSERT INTO m365_knowledge_holds VALUES(?,?)",("hold-0000","Governed Hold"))
        self.conn.execute("INSERT INTO m365_bulk_items(drive_id,pending_id,item_id,kind,status) VALUES(?,?,?,?,?)",
                          ("drive-0000","area-PENDING","work-0000","file","Working"))
        self.conn.commit()
        inv = {key:item(key) for key in ("candidate-0000","hold-0000","work-0000","missing-0000")}
        plan,result = self.enroll(inv)
        self.assertEqual(set(plan),{"missing-0000"})
        self.assertEqual(self.conn.execute("SELECT status FROM m365_bulk_items WHERE item_id='work-0000'").fetchone()[0],"Working")
        self.assertIn("Retry Paused",self.conn.execute("SELECT classification_json FROM m365_knowledge_candidates").fetchone()[0])
        self.assertEqual(self.conn.execute("SELECT status FROM m365_knowledge_holds").fetchone()[0],"Governed Hold")
    def test_current_gap_not_historical_count_and_cap(self):
        plan,result = self.enroll({})
        self.assertEqual(result["item_count"],0)
        self.assertEqual(self.count("m365_knowledge_representation_events"),0)
        too_many = {f"source-{n:04d}":item(f"source-{n:04d}") for n in range(117)}
        with self.assertRaisesRegex(RuntimeError,"116-item"):
            gap.coverage_plan(self.conn,too_many)
    def test_duplicate_operation_fails_without_extra_events(self):
        inv = {"source-0000":item("source-0000")}
        plan,result = self.enroll(inv)
        self.conn.commit()
        with self.assertRaisesRegex(RuntimeError,"already recorded"):
            gap.enroll_missing(self.conn,inv,plan,"drive-0000","root-0000",STAMP)
        self.assertEqual(self.count("m365_knowledge_representation_events"),1)
    def test_concurrent_representation_change_fails_before_insert(self):
        inv = {"source-0000":item("source-0000")}
        plan = gap.coverage_plan(self.conn,inv)
        self.conn.execute("INSERT INTO m365_knowledge_candidates VALUES(?,?)",("source-0000","{}"))
        self.conn.commit()
        with self.assertRaisesRegex(RuntimeError,"membership changed"):
            gap.enroll_missing(self.conn,inv,plan,"drive-0000","root-0000",STAMP)
        self.assertEqual(self.count("m365_bulk_items"),0)
        self.assertEqual(self.count("m365_knowledge_representation_batches"),0)
    def test_removed_record_is_not_overwritten(self):
        inv = {"source-0000":item("source-0000")}
        self.conn.execute("INSERT INTO m365_bulk_items(drive_id,pending_id,item_id,kind,status) VALUES(?,?,?,?,?)",
                          ("drive-0000","root-0000","source-0000","file","Removed"))
        self.conn.commit()
        plan = gap.coverage_plan(self.conn,inv)
        with self.assertRaisesRegex(RuntimeError,"conflicts"):
            gap.enroll_missing(self.conn,inv,plan,"drive-0000","root-0000",STAMP)
        self.assertEqual(self.conn.execute("SELECT status FROM m365_bulk_items").fetchone()[0],"Removed")
        self.assertEqual(self.count("m365_knowledge_representation_batches"),0)
    def test_mid_batch_failure_rolls_back_rows_batch_and_events(self):
        inv = {f"source-{n:04d}":item(f"source-{n:04d}") for n in range(2)}
        plan = gap.coverage_plan(self.conn,inv)
        self.conn.commit()
        class FailSecond:
            inserts = 0
            def __init__(self,conn): self.conn = conn
            def __getattr__(self,name): return getattr(self.conn,name)
            def execute(self,sql,params=()):
                if "INSERT INTO m365_bulk_items" in sql:
                    self.inserts += 1
                    if self.inserts == 2:
                        raise RuntimeError("simulated batch failure")
                return self.conn.execute(sql,params)
        with self.assertRaisesRegex(RuntimeError,"simulated batch"):
            gap.enroll_missing(FailSecond(self.conn),inv,plan,"drive-0000","root-0000",STAMP)
        for table in ("m365_bulk_items","m365_knowledge_representation_batches","m365_knowledge_representation_events"):
            self.assertEqual(self.count(table),0)
    def test_durable_event_and_row_tampering_are_rejected(self):
        inv = {"source-0000":item("source-0000")}
        plan,result = self.enroll(inv)
        self.conn.execute("UPDATE m365_knowledge_representation_events SET detail_json='{}'")
        self.conn.commit()
        with self.assertRaisesRegex(RuntimeError,"events disagree"):
            gap.verify_enrollment(self.conn,plan,"drive-0000","root-0000",result)
        self.conn.execute("UPDATE m365_knowledge_representation_events SET detail_json=?",
                          (gap.canonical(plan["source-0000"]),))
        self.conn.execute("UPDATE m365_bulk_items SET status='Pending'")
        self.conn.commit()
        with self.assertRaisesRegex(RuntimeError,"parked representation"):
            gap.verify_enrollment(self.conn,plan,"drive-0000","root-0000",result)
    @unittest.skipUnless(os.getenv("GAP_REAL_DEPENDENCIES") == "1","real intake dependencies available in CI")
    def test_existing_scheduler_does_not_claim_parked_rows(self):
        from salcapa_bulk_delta import claim_work, _apply_item
        self.enroll({"source-0000":item("source-0000")})
        class Shared:
            def __init__(self,conn): self.conn = conn
            def __getattr__(self,name): return getattr(self.conn,name)
            def close(self): pass
        self.assertEqual(claim_work(lambda:Shared(self.conn),"drive-0000","root-0000",limit=1,now=2000000000),[])
        self.assertEqual(claim_work(lambda:Shared(self.conn),"drive-0000","area-PENDING",limit=1,now=2000000000),[])
        # A later ordinary Pending delta pass must not overwrite the root inventory row.
        intake = SimpleNamespace(config=SimpleNamespace(drive_id="drive-0000",max_file_bytes=104857600),
            _safe_path_component=lambda value:value,_identity=lambda _value:("Salus","owner"),
            _trusted_source_url=lambda value:value)
        incoming = {"id":"source-0000","parentReference":{"id":"nested-0000"},
            "name":"fictional.txt","file":{"mimeType":"text/plain"},"size":123,
            "eTag":"version-1","lastModifiedDateTime":STAMP,"webUrl":"https://salussolutions-my.sharepoint.com/example"}
        _apply_item(self.conn,intake,"area-PENDING",incoming,2000000000,1)
        self.conn.commit()
        root_row = self.conn.execute("SELECT status FROM m365_bulk_items WHERE pending_id='root-0000'").fetchone()
        self.assertEqual(root_row["status"],"Assignment Required")
        selected = claim_work(lambda:Shared(self.conn),"drive-0000","area-PENDING",limit=1,now=2000000000)
        self.assertEqual(len(selected),1)
        self.assertEqual(self.conn.execute("SELECT status FROM m365_bulk_items WHERE pending_id='root-0000'").fetchone()[0],"Assignment Required")

@unittest.skipUnless(os.getenv("TEST_GAP_POSTGRES") == "1","dedicated CI PostgreSQL only")
class PostgreSQLEnrollmentTests(EnrollmentTests):
    def setUp(self):
        assert os.getenv("SALUS_DATABASE_URL","").startswith("postgresql://postgres:postgres@localhost:5432/gap_reconcile")
        from database import connect_database
        self.conn = connect_database()
        for table in TABLES:
            self.conn.execute("DROP TABLE IF EXISTS " + table)
        self.conn.executescript(SCHEMA)
        self.conn.commit()
    def tearDown(self):
        self.conn.rollback()
        for table in TABLES:
            self.conn.execute("DROP TABLE IF EXISTS " + table)
        self.conn.commit()
        self.conn.close()
    def test_busy_writer_lock_fails_closed(self):
        from database import connect_database
        gap.audit_tables(self.conn)
        other = connect_database()
        try:
            other.execute("LOCK TABLE m365_bulk_items IN ACCESS EXCLUSIVE MODE")
            inv = {"source-0000":item("source-0000")}
            with self.assertRaises(Exception) as caught:
                gap.enroll_missing(self.conn,inv,inv,"drive-0000","root-0000",STAMP)
            self.assertEqual(type(caught.exception).__name__,"LockNotAvailable")
        finally:
            other.rollback()
            other.close()
        self.assertEqual(self.count("m365_bulk_items"),0)

class InventoryTests(unittest.TestCase):
    def fixture(self, extra=(), mutate=None):
        root_id,drive = "root-0000","drive-0000"
        items = [{"id":f"folder-{n:04d}","name":area,"folder":{},"parentReference":{"id":root_id,"driveId":drive}}
                 for n,area in enumerate(gap.AREA_CODES)]
        items.append({"id":"source-0000","name":"fictional.txt","file":{"mimeType":"text/plain"},
             "parentReference":{"id":"folder-0000","driveId":drive},"eTag":"v1","size":12,
             "lastModifiedDateTime":STAMP,"webUrl":"https://salussolutions-my.sharepoint.com/example"})
        items.extend(extra)
        if mutate: mutate(items)
        root = {"id":root_id,"name":"SalCAPA Intake","folder":{}}
        endpoint = f"https://graph.microsoft.com/v1.0/drives/{drive}/items/{root_id}/delta"
        payloads = iter((root,{"value":items,"@odata.deltaLink":endpoint+"?token=end"}))
        class Client:
            calls=[]
            def get(self,url,**_kwargs):
                self.calls.append(url)
                return SimpleNamespace(status_code=200,json=lambda:next(payloads))
        return SimpleNamespace(config=SimpleNamespace(drive_id=drive,folder_item_id=root_id),
            client=Client(),_headers=lambda:{},_identity=lambda _v:("Salus","owner-0000"),
            _trusted_source_url=lambda value:value)
    def test_metadata_scope_and_no_content_requests(self):
        intake = self.fixture()
        result = gap.scoped_inventory(intake)
        self.assertEqual(result["source-0000"]["area"],"10 Pending Classification")
        self.assertEqual(result["source-0000"]["area_id"],"folder-0000")
        self.assertTrue(all("/content" not in url for url in intake.client.calls))
    def test_unknown_parent_rejected(self):
        with self.assertRaisesRegex(RuntimeError,"ancestry"):
            gap.scoped_inventory(self.fixture(mutate=lambda items:items[-1]["parentReference"].update(id="foreign-0000")))
    def test_shortcut_rejected(self):
        with self.assertRaisesRegex(RuntimeError,"shortcut"):
            gap.scoped_inventory(self.fixture(mutate=lambda items:items[-1].update(remoteItem={})))
    def test_duplicate_top_level_area_rejected(self):
        duplicate={"id":"folder-9999","name":"10 Pending Classification","folder":{},
                   "parentReference":{"id":"root-0000","driveId":"drive-0000"}}
        with self.assertRaisesRegex(RuntimeError,"top-level boundary"):
            gap.scoped_inventory(self.fixture(extra=(duplicate,)))
    def test_other_drive_rejected(self):
        with self.assertRaisesRegex(RuntimeError,"drive mismatch"):
            gap.scoped_inventory(self.fixture(mutate=lambda items:items[-1]["parentReference"].update(driveId="other-0000")))

if __name__ == "__main__":
    unittest.main()
