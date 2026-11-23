import sqlite3
import unittest

from tools.live_planning_evidence_search import protected_source_controls


class PlanningControlProofTest(unittest.TestCase):
    def setUp(self):
        self.conn=sqlite3.connect(':memory:')
        self.conn.row_factory=sqlite3.Row
        self.conn.executescript('''
        CREATE TABLE m365_knowledge_holds(source_item_id TEXT,status TEXT,hold_reason TEXT);
        CREATE TABLE m365_knowledge_candidates(id INTEGER,source_item_id TEXT,status TEXT);
        CREATE TABLE m365_bulk_items(drive_id TEXT,pending_id INTEGER,item_id TEXT,kind TEXT,status TEXT,reason TEXT,attempts INTEGER,next_attempt TEXT,lease_owner TEXT,lease_until TEXT);
        CREATE TABLE m365_bulk_extraction_checks(candidate_id INTEGER,attempts INTEGER,next_attempt TEXT,lease_owner TEXT,lease_until TEXT,last_code TEXT);
        INSERT INTO m365_knowledge_holds VALUES('held-source','Governed Hold','restricted');
        INSERT INTO m365_knowledge_candidates VALUES(1,'held-source','Candidate'),(2,'paused-source','Paused');
        INSERT INTO m365_bulk_items VALUES('drive',1,'held-source','file','Done','',0,NULL,NULL,NULL),('drive',2,'paused-source','file','Paused','pause',2,'later',NULL,NULL);
        INSERT INTO m365_bulk_extraction_checks VALUES(1,0,NULL,NULL,NULL,NULL),(2,2,'later',NULL,NULL,'paused');
        ''')

    def tearDown(self):
        self.conn.close()

    def assert_drift(self,sql):
        before=protected_source_controls(self.conn)
        self.conn.execute(sql)
        self.assertNotEqual(before,protected_source_controls(self.conn))

    def test_stable_read_only_and_no_source_disclosure(self):
        changes=self.conn.total_changes
        before=protected_source_controls(self.conn)
        self.assertEqual(before,protected_source_controls(self.conn))
        self.assertEqual(changes,self.conn.total_changes)
        self.assertEqual(before['counts'],{'holds':1,'paused_candidates':1,'bulk_controls':2,'extraction_controls':2})
        self.assertEqual(len(before['sha256']),64)
        self.assertNotIn('held-source',str(before))

    def test_hold_removal_detected(self):
        self.assert_drift("DELETE FROM m365_knowledge_holds")

    def test_pause_release_detected(self):
        self.assert_drift("UPDATE m365_knowledge_candidates SET status='Ready' WHERE id=2")

    def test_retry_change_detected(self):
        self.assert_drift("UPDATE m365_bulk_extraction_checks SET attempts=3 WHERE candidate_id=2")

    def test_lease_change_detected(self):
        self.assert_drift("UPDATE m365_bulk_items SET lease_owner='new-owner' WHERE item_id='paused-source'")

    def test_missing_control_table_fails_closed(self):
        self.conn.execute('DROP TABLE m365_bulk_extraction_checks')
        with self.assertRaises(sqlite3.OperationalError):
            protected_source_controls(self.conn)
