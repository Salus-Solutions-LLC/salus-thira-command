import json
import unittest
from tools import knowledge_postsearch_history as history


class HistoryTests(unittest.TestCase):
    def test_original_guard_failure_and_phase_are_recovered_without_raw_text(self):
        rows=['STABILITY_FAILURE_CODE=PLAN_08','STABILITY_FAILURE_STAGE=atomic_manifest_commit',
              'STABILITY_SAMPLE_4_COMPLETE=1','TASK_KNOWLEDGE_Q1_RECEIPT_ID=95838b67-b96f-4d75-a079-d1c4b72bfddb',
              'PRIVATE CONTENT https://private.example']
        result=history.reduce_history(rows)
        self.assertEqual(result['query_state'],'RECOVERED')
        self.assertEqual(result['failure_code'],'PLAN_08')
        self.assertEqual(result['failure_stage'],'atomic_manifest_commit')
        self.assertEqual(result['complete_inventory_markers'],1)
        self.assertEqual(result['query_receipt_markers'],1)
        self.assertNotIn('PRIVATE',json.dumps(result))

    def test_missing_denied_and_conflicting_results_remain_distinct(self):
        self.assertEqual(history.reduce_history([],False)['query_state'],'UNAVAILABLE')
        self.assertEqual(history.reduce_history([])['query_state'],'NO_FAILURE_MARKER')
        self.assertEqual(history.reduce_history(['STABILITY_FAILURE_CODE=PLAN_08','STABILITY_FAILURE_CODE=PLAN_19'])['query_state'],'CONFLICTING_MARKERS')
        self.assertEqual(history.reduce_history(['STABILITY_FAILURE_CODE=PRIVATE_SECRET'])['query_state'],'UNRECOGNIZED_CODE')

    def test_bounds_unknown_types_and_unknown_fields_do_not_leak(self):
        for rows in ({'PRIVATE':'TOKEN'},['x'*501],['x']*301,[123]):
            result=history.reduce_history(rows)
            self.assertEqual(result['query_state'],'INVALID_RESULT')
            self.assertNotIn('PRIVATE',json.dumps(result))

    def test_duplicate_ingestion_is_not_misread_as_another_failure(self):
        result=history.reduce_history(['STABILITY_FAILURE_CODE=PLAN_08']*3)
        self.assertEqual(result['query_state'],'RECOVERED')
        self.assertEqual(result['accepted_record_count'],1)


if __name__=='__main__':unittest.main()
