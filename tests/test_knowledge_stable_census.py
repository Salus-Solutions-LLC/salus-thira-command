"""Read-only census diagnostics, strict stability and durable receipt regressions."""
import contextlib
import copy
import io
import json
import os
import sqlite3
import tempfile
import unittest
from types import SimpleNamespace
from tools import live_knowledge_stable_census as census
from salcapa_knowledge_consideration import _create_receipt_table

STAMP="2026-11-15T05:00:00+00:00"

def row(key="source-0000",version="v1"):
    return {"item_id":key,"area_id":"folder-0000","area":"10 Pending Classification",
            "parent_id":"folder-0000","name":"PRIVATE-SOURCE.txt","etag":version,"size":12,
            "metadata_json":census.canonical({"relative_path":"10 Pending Classification/PRIVATE-SOURCE.txt",
              "last_modified":STAMP,"ctag":"c1","mime_type":"text/plain","source_owner":"PRIVATE OWNER",
              "source_owner_id":"PRIVATE-ID","last_modified_by":"PRIVATE MODIFIER",
              "web_url":"https://private.example/source","source_root_id":"root-0000",
              "representation_only":True,"processing_authorized":False})}

def provider(values):
    queue=iter(values)
    def call(_intake):
        value=next(queue)
        if isinstance(value,Exception):
            raise value
        return copy.deepcopy(value)
    return call

class StabilityTests(unittest.TestCase):
    def setUp(self):
        census.INVENTORY_ATTEMPTS=census.INVENTORIES_COMPLETED=0
    def test_two_identical_complete_inventories_establish_stability(self):
        value={"source-0000":row()}
        with contextlib.redirect_stdout(io.StringIO()) as out:
            result=census.establish_stable_inventory(None,inventory_fn=provider([value,value]))
        self.assertEqual(result,value)
        self.assertEqual(census.INVENTORIES_COMPLETED,2)
        self.assertIn("CONSECUTIVE_COMPLETE_INVENTORIES_EQUAL=1",out.getvalue())
        self.assertNotIn("PRIVATE",out.getvalue())
    def test_completed_change_can_settle_at_new_baseline_without_waiver(self):
        first={"source-0000":row()}
        second={"source-0000":row(version="v2")}
        with contextlib.redirect_stdout(io.StringIO()) as out:
            result=census.establish_stable_inventory(None,inventory_fn=provider([first,second,second]))
        self.assertEqual(result,second)
        self.assertEqual(census.INVENTORIES_COMPLETED,3)
        self.assertIn("STABILITY_PAIR_1_2_ETAG=1",out.getvalue())
        self.assertIn("STABILITY_PAIR_2_3_CHANGED=0",out.getvalue())
    def test_continuous_changes_stop_at_three_observations(self):
        values=[{"source-0000":row(version="v"+str(n))} for n in range(3)]
        with contextlib.redirect_stdout(io.StringIO()) as out:
            with self.assertRaises(census.CensusFailure) as caught:
                census.establish_stable_inventory(None,inventory_fn=provider(values))
        self.assertEqual(caught.exception.code,"STABILITY_NOT_ESTABLISHED")
        self.assertEqual(census.INVENTORY_ATTEMPTS,3)
        self.assertNotIn("CONSECUTIVE_COMPLETE_INVENTORIES_EQUAL=1",out.getvalue())
    def test_failed_inventory_is_distinct_and_not_reobserved(self):
        value={"source-0000":row()}
        with contextlib.redirect_stdout(io.StringIO()) as out:
            with self.assertRaises(census.CensusFailure) as caught:
                census.establish_stable_inventory(None,inventory_fn=provider(
                    [value,census.CensusFailure("PAGE_HTTP_FORBIDDEN"),value]))
        self.assertEqual(caught.exception.code,"PAGE_HTTP_FORBIDDEN")
        self.assertEqual(census.INVENTORY_ATTEMPTS,2)
        self.assertEqual(census.INVENTORIES_COMPLETED,1)
        self.assertNotIn("SAMPLE_2_COMPLETE",out.getvalue())
        self.assertNotIn("PAIR_1_2",out.getvalue())
    def test_same_count_replacement_and_all_field_changes_remain_visible(self):
        left={"source-0000":row(),"source-0001":row("source-0001")}
        right=copy.deepcopy(left)
        del right["source-0001"]
        right["source-0002"]=row("source-0002")
        right["source-0000"].update(etag="v2",size=13,parent_id="other-0000",name="OTHER PRIVATE",
                                   unknown_field="PRIVATE")
        meta=json.loads(right["source-0000"]["metadata_json"])
        meta.update(relative_path="OTHER PRIVATE",last_modified="later",ctag="c2",
                    mime_type="other",source_owner="OTHER PRIVATE",web_url="https://private.example/other",
                    unknown_meta="PRIVATE")
        right["source-0000"]["metadata_json"]=census.canonical(meta)
        result=census.inventory_diff(left,right)
        for field in ("added","removed","changed","etag","size","parent_or_area","name","relative_path",
                      "modified_time","content_tag","mime","attribution","trusted_url","other_metadata","other_row_fields"):
            self.assertEqual(result[field],1,field)
        self.assertNotIn("PRIVATE",json.dumps(result))
    def test_serialization_difference_is_measured_and_never_ignored(self):
        left={"source-0000":row()}
        right=copy.deepcopy(left)
        right["source-0000"]["metadata_json"]=json.dumps(json.loads(left["source-0000"]["metadata_json"]))
        self.assertEqual(census.inventory_diff(left,right)["serialization_only"],1)
        with contextlib.redirect_stdout(io.StringIO()):
            with self.assertRaises(census.CensusFailure):
                census.establish_stable_inventory(None,inventory_fn=provider([left,right]),max_observations=2)
    def test_failure_output_cannot_emit_unknown_exception_values(self):
        with contextlib.redirect_stdout(io.StringIO()) as out:
            census.emit_failure(RuntimeError("PRIVATE TOKEN https://private.example"))
            census.emit_failure(census.CensusFailure("PRIVATE SOURCE"))
        self.assertNotIn("PRIVATE",out.getvalue())
        self.assertIn("FAILURE_CODE=UNEXPECTED_FAILURE",out.getvalue())
    def test_observation_bound_cannot_be_increased(self):
        with self.assertRaises(ValueError):
            census.establish_stable_inventory(None,max_observations=4)

class InventoryTests(unittest.TestCase):
    def items(self):
        values=[{"id":f"folder-{n:04d}","name":area,"folder":{},
                 "parentReference":{"id":"root-0000","driveId":"drive-0000"}} for n,area in enumerate(census.AREA_CODES)]
        values.append({"id":"source-0000","name":"PRIVATE-SOURCE.txt","file":{"mimeType":"text/plain"},
            "parentReference":{"id":"folder-0000","driveId":"drive-0000"},"eTag":"v1","size":12,
            "lastModifiedDateTime":STAMP,"webUrl":"https://salussolutions-my.sharepoint.com/private"})
        return values
    def intake(self, mutate=None, payloads=None, root=None, fail_url=False):
        endpoint="https://graph.microsoft.com/v1.0/drives/drive-0000/items/root-0000/delta"
        items=self.items()
        if mutate: mutate(items)
        root=root if root is not None else {"id":"root-0000","name":"SalCAPA Intake","folder":{}}
        queue=iter(payloads if payloads is not None else
            [root,{"value":items,"@odata.deltaLink":endpoint+"?token=end"}])
        class Client:
            def __init__(self): self.calls=[]
            def get(self,url,**kwargs):
                self.calls.append(url)
                payload=next(queue)
                if isinstance(payload,Exception): raise payload
                if isinstance(payload,tuple):
                    status,payload=payload
                else: status=200
                def parse():
                    if isinstance(payload,Exception): raise payload
                    return payload
                return SimpleNamespace(status_code=status,json=parse)
        def trusted(value):
            if fail_url: raise RuntimeError("PRIVATE URL "+str(value))
            return value
        return SimpleNamespace(config=SimpleNamespace(drive_id="drive-0000",folder_item_id="root-0000"),
            client=Client(),_headers=lambda:{},_identity=lambda _v:("PRIVATE OWNER","PRIVATE-ID"),
            _trusted_source_url=trusted)
    def assert_code(self,intake,code):
        with self.assertRaises(census.CensusFailure) as caught:
            census.scoped_inventory(intake)
        self.assertEqual(caught.exception.code,code)
        self.assertNotIn("PRIVATE",str(caught.exception))
    def test_valid_inventory_is_metadata_only(self):
        intake=self.intake()
        result=census.scoped_inventory(intake)
        self.assertEqual(result["source-0000"]["etag"],"v1")
        self.assertTrue(all("/content" not in url for url in intake.client.calls))
    def test_root_failures_are_specific_and_redacted(self):
        cases=[([(403,{"error":"PRIVATE TOKEN"})],"ROOT_HTTP_FORBIDDEN"),
               ([RuntimeError("PRIVATE REQUEST")],"ROOT_REQUEST_FAILED"),
               ([(200,ValueError("PRIVATE JSON"))],"ROOT_JSON_INVALID"),
               ([[]],"ROOT_PAYLOAD_INVALID"),
               ([{"id":"other-0000","name":"SalCAPA Intake","folder":{}}],"ROOT_BOUNDARY_MISMATCH")]
        for payloads,code in cases:
            with self.subTest(code=code): self.assert_code(self.intake(payloads=payloads),code)
    def test_page_failures_are_specific_and_not_source_values(self):
        root={"id":"root-0000","name":"SalCAPA Intake","folder":{}}
        cases=[((429,{"error":"PRIVATE"}),"PAGE_HTTP_THROTTLED"),
               ((410,{"error":"PRIVATE"}),"PAGE_HTTP_RESYNC_REQUIRED"),
               ((503,{"error":"PRIVATE"}),"PAGE_HTTP_SERVER_ERROR"),
               ((418,{"error":"PRIVATE"}),"PAGE_HTTP_OTHER"),
               ((200,ValueError("PRIVATE JSON")),"PAGE_JSON_INVALID"),
               ((200,[]),"PAGE_PAYLOAD_INVALID"),
               (RuntimeError("PRIVATE REQUEST"),"PAGE_REQUEST_FAILED"),
               ({},"PAGE_SHAPE_INVALID"),
               ({"value":[],"@odata.deltaLink":"https://private.example/?token=private"},"CONTINUATION_SCOPE_INVALID")]
        for value,code in cases:
            with self.subTest(code=code): self.assert_code(self.intake(payloads=[root,value]),code)
    def test_ancestry_provenance_and_source_guard_diagnostics(self):
        cases=[
          (lambda a:a[-1].update(remoteItem={}),"SHORTCUT_REJECTED"),
          (lambda a:a[-1].update(id="bad"),"ITEM_ID_INVALID"),
          (lambda a:a[-1]["parentReference"].update(driveId="other-0000"),"DRIVE_MISMATCH"),
          (lambda a:a[-1].update(parentReference="PRIVATE"),"PARENT_ID_INVALID"),
          (lambda a:a[-1]["parentReference"].update(id="foreign-0000"),"ANCESTRY_INVALID"),
          (lambda a:a[-1].update(name="../PRIVATE"),"NAME_INVALID"),
          (lambda a:a[-1].update(folder={}),"ITEM_TYPE_INVALID"),
          (lambda a:a[-1].update(eTag=""),"SOURCE_PROVENANCE_INCOMPLETE"),
          (lambda a:a[0].update(name="PRIVATE"),"TOP_LEVEL_BOUNDARY_CHANGED"),
        ]
        for mutate,code in cases:
            with self.subTest(code=code): self.assert_code(self.intake(mutate=mutate),code)
        self.assert_code(self.intake(fail_url=True),"METADATA_HELPER_REJECTED")
    def test_all_pages_last_occurrence_and_cycle_guard(self):
        root={"id":"root-0000","name":"SalCAPA Intake","folder":{}}
        endpoint="https://graph.microsoft.com/v1.0/drives/drive-0000/items/root-0000/delta"
        items=self.items()
        newer=copy.deepcopy(items[-1]); newer["eTag"]="v2"
        result=census.scoped_inventory(self.intake(payloads=[root,
            {"value":items,"@odata.nextLink":endpoint+"?page=2"},
            {"value":[newer],"@odata.deltaLink":endpoint+"?token=end"}]))
        self.assertEqual(result["source-0000"]["etag"],"v2")
        self.assert_code(self.intake(payloads=[root,
            {"value":items,"@odata.nextLink":endpoint+"?page=2"},
            {"value":[],"@odata.nextLink":endpoint+"?page=2"}]),"PAGINATION_BOUND_EXCEEDED")

SCHEMA="""
CREATE TABLE m365_bulk_items(item_id TEXT,name TEXT,metadata_json TEXT,status TEXT,reason TEXT,kind TEXT,updated_at BIGINT);
CREATE TABLE m365_knowledge_candidates(id BIGINT,source_item_id TEXT,source_name TEXT,source_relative_path TEXT,
 source_sha256 TEXT,source_archive_item_id TEXT,source_modified_at TEXT,source_owner TEXT,status TEXT,
 target_folder TEXT,classification_json TEXT);
CREATE TABLE m365_knowledge_holds(source_item_id TEXT,source_name TEXT,source_relative_path TEXT,
 source_area TEXT,hold_reason TEXT,status TEXT);
"""
TABLES=("m365_knowledge_consideration_receipts","m365_knowledge_representation_batches",
        "m365_bulk_items","m365_knowledge_candidates","m365_knowledge_holds")

class ReceiptTests(unittest.TestCase):
    def setUp(self):
        self.folder=tempfile.TemporaryDirectory()
        self.path=os.path.join(self.folder.name,"test.db")
        self.conn=self.connect()
        self.conn.executescript(SCHEMA)
        self.seed()
    def connect(self):
        conn=sqlite3.connect(self.path)
        conn.row_factory=sqlite3.Row
        return conn
    def seed(self):
        census.INVENTORY_ATTEMPTS=census.INVENTORIES_COMPLETED=0
        for n in range(3):
            self.conn.execute("INSERT INTO m365_bulk_items VALUES(?,?,?,?,?,?,?)",
                (f"source-{n:04d}","Fictional", "{}", "Assignment Required" if n==1 else "Done","","file",n))
        for n,key in enumerate(("source-0000","source-0001","historical-0000")):
            extraction={"extraction":{"status":"Review Required" if n==1 else "Complete",
                "text":"" if n==1 else "source inventory provenance recovery complete corpus"}}
            self.conn.execute("INSERT INTO m365_knowledge_candidates VALUES(?,?,?,?,?,?,?,?,?,?,?)",
                (n,key,"Fictional","Reference","a"*64,"archive",STAMP,"Salus","Candidate","Reference",json.dumps(extraction)))
        self.conn.execute("INSERT INTO m365_knowledge_holds VALUES(?,?,?,?,?,?)",
                          ("source-0002","Fictional","Reference","Does Not Upload","review","Governed Hold"))
        _create_receipt_table(self.conn)
        self.conn.commit()
        self.inventory={f"source-{n:04d}":row(f"source-{n:04d}") for n in range(3)}
        self.previous=os.environ.get("SALUS_KNOWLEDGE_MINIMUM_BOUNDARY_FILES")
    def tearDown(self):
        self.conn.close()
        self.folder.cleanup()
        if self.previous is None: os.environ.pop("SALUS_KNOWLEDGE_MINIMUM_BOUNDARY_FILES",None)
        else: os.environ["SALUS_KNOWLEDGE_MINIMUM_BOUNDARY_FILES"]=self.previous
    def count_receipts(self):
        return self.conn.execute("SELECT COUNT(*) FROM m365_knowledge_consideration_receipts").fetchone()[0]
    def run_search(self,values=None):
        return census.verified_search(self.conn,None,self.inventory,
            inventory_fn=provider(values or [self.inventory,self.inventory]),minimum_boundary=3,minimum_represented=4)
    def test_four_real_receipts_and_independent_connection_readback(self):
        before=[tuple(r) for r in self.conn.execute("SELECT * FROM m365_knowledge_candidates ORDER BY id").fetchall()]
        with contextlib.redirect_stdout(io.StringIO()):
            census.prior_state_readback(self.conn)
            census.verify_membership(self.conn,self.inventory)
            summaries=self.run_search()
            fresh=self.connect()
            try: census.fresh_receipt_readback(fresh,summaries)
            finally: fresh.close()
        self.assertEqual(len(summaries),4)
        self.assertEqual(self.count_receipts(),4)
        for value in summaries:
            self.assertEqual(value["considered_files"],4)
            self.assertEqual(value["content_available_files"],2)
            self.assertEqual(value["metadata_only_or_unresolved_files"],2)
        after=[tuple(r) for r in self.conn.execute("SELECT * FROM m365_knowledge_candidates ORDER BY id").fetchall()]
        self.assertEqual(before,after)
    def test_sqlite_source_tables_refuse_writes_during_entire_search(self):
        if getattr(self.conn,"backend","sqlite")!="sqlite": self.skipTest("SQLite authorizer regression")
        forbidden={"m365_bulk_items","m365_knowledge_candidates","m365_knowledge_holds"}
        self.conn.set_authorizer(lambda action,a1,*_args: sqlite3.SQLITE_DENY
            if action in (sqlite3.SQLITE_INSERT,sqlite3.SQLITE_UPDATE,sqlite3.SQLITE_DELETE) and a1 in forbidden else sqlite3.SQLITE_OK)
        with contextlib.redirect_stdout(io.StringIO()):
            self.run_search()
        self.assertEqual(self.count_receipts(),4)
    def test_initial_source_change_creates_no_receipts(self):
        changed=copy.deepcopy(self.inventory); changed["source-0000"]["etag"]="v2"
        with contextlib.redirect_stdout(io.StringIO()):
            with self.assertRaises(census.CensusFailure) as caught: self.run_search([changed])
        self.assertEqual(caught.exception.code,"SOURCE_CHANGED_DURING_SEARCH")
        self.assertEqual(self.count_receipts(),0)
    def test_final_source_change_preserves_partial_receipts_and_blocks_completion(self):
        changed=copy.deepcopy(self.inventory); changed["source-0000"]["etag"]="v2"
        with contextlib.redirect_stdout(io.StringIO()) as out:
            with self.assertRaises(census.CensusFailure) as caught: self.run_search([self.inventory,changed])
        self.assertEqual(caught.exception.code,"SOURCE_CHANGED_DURING_SEARCH")
        self.assertEqual(self.count_receipts(),4)
        self.assertEqual(census.CREATED_RECEIPTS,4)
        self.assertNotIn("TASK_KNOWLEDGE_COMPLETE=1",out.getvalue())
    def test_fresh_readback_rejects_actor_timestamp_and_count_corruption(self):
        with contextlib.redirect_stdout(io.StringIO()): summaries=self.run_search()
        baseline=[dict(r) for r in self.conn.execute("SELECT * FROM m365_knowledge_consideration_receipts").fetchall()]
        for field,value in (("created_at","wrong"),("actor","wrong"),("considered_count",999)):
            assert field in {"created_at","actor","considered_count"}
            self.conn.execute("UPDATE m365_knowledge_consideration_receipts SET "+field+"=?",(value,))
            self.conn.commit()
            fresh=self.connect()
            try:
                with self.assertRaises(census.CensusFailure): census.fresh_receipt_readback(fresh,summaries)
            finally: fresh.close()
            for original in baseline:
                self.conn.execute("UPDATE m365_knowledge_consideration_receipts SET "+field+"=? WHERE receipt_id=?",
                                  (original[field],original["receipt_id"]))
            self.conn.commit()
    def test_prior_receipts_and_enrollment_stop_a_new_operation(self):
        self.conn.execute("INSERT INTO m365_knowledge_consideration_receipts VALUES(?,?,?,?,?,?,?,?,?,?)",
            ("prior","hash",3,4,0,2,2,1,"System Administrator - task consideration salus-representation-gap-reconciliation-20261115 / q",STAMP))
        self.conn.commit()
        with contextlib.redirect_stdout(io.StringIO()):
            with self.assertRaises(census.CensusFailure) as caught: census.prior_state_readback(self.conn)
        self.assertEqual(caught.exception.code,"PRIOR_TASK_RECEIPTS_PRESENT")
        self.conn.execute("DELETE FROM m365_knowledge_consideration_receipts")
        self.conn.execute("CREATE TABLE m365_knowledge_representation_batches(operation_key TEXT)")
        self.conn.execute("INSERT INTO m365_knowledge_representation_batches VALUES(?)",("salus-representation-gap-reconciliation-20261115",))
        self.conn.commit()
        with contextlib.redirect_stdout(io.StringIO()):
            with self.assertRaises(census.CensusFailure) as caught: census.prior_state_readback(self.conn)
        self.assertEqual(caught.exception.code,"PRIOR_ENROLLMENT_BATCH_PRESENT")
    def test_missing_membership_fails_without_enrollment(self):
        self.inventory["source-9999"]=row("source-9999")
        with contextlib.redirect_stdout(io.StringIO()):
            with self.assertRaises(census.CensusFailure) as caught: census.verify_membership(self.conn,self.inventory)
        self.assertEqual(caught.exception.code,"MISSING_REPRESENTATION")
        self.assertEqual(self.count_receipts(),0)

@unittest.skipUnless(os.getenv("TEST_STABILITY_POSTGRES")=="1","dedicated CI PostgreSQL only")
class PostgreSQLReceiptTests(ReceiptTests):
    def setUp(self):
        assert os.getenv("SALUS_DATABASE_URL","").startswith("postgresql://postgres:postgres@localhost:5432/stable_census")
        self.conn=self.connect()
        for table in TABLES: self.conn.execute("DROP TABLE IF EXISTS "+table)
        self.conn.executescript(SCHEMA)
        self.conn.commit()
        self.seed()
    def connect(self):
        from database import connect_database
        return connect_database()
    def tearDown(self):
        self.conn.rollback()
        for table in TABLES: self.conn.execute("DROP TABLE IF EXISTS "+table)
        self.conn.commit()
        self.conn.close()
        if self.previous is None: os.environ.pop("SALUS_KNOWLEDGE_MINIMUM_BOUNDARY_FILES",None)
        else: os.environ["SALUS_KNOWLEDGE_MINIMUM_BOUNDARY_FILES"]=self.previous

if __name__=="__main__": unittest.main()
