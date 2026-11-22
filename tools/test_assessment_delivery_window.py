import unittest
from copy import deepcopy
from assessment_delivery_window import check

class DeliveryWindowTests(unittest.TestCase):
    def record(self):
        return {'task_id':'fictional-assessment','instruction_reference':'retained-request',
                'observed_acceptance_at':'2026-11-22T17:00:00-06:00',
                'original_acceptance_at':'2026-11-22T23:00:00Z',
                'original_deadline_at':'2026-11-23T23:00:00Z','timezone':'America/Chicago',
                'scope':'bounded fictional coordination review','analyst':'test role',
                'capacity':'recorded','source_inventory_reference':'inventory',
                'quality_record_reference':'quality','quality_state':'bounded_internal',
                'material_gaps':['unread original'],'qualification_pending':True,
                'external_issue_authorized':False}
    def test_open_not_complete(self):
        r=check(self.record(),'2026-11-23T00:00:00Z')
        self.assertTrue(r['record_valid']);self.assertEqual(r['time_state'],'open_before_deadline')
    def test_deadline_boundary_and_late(self):
        r=self.record();r.update(returned_at='2026-11-23T23:00:00Z',return_evidence_reference='receipt')
        self.assertEqual(check(r,'2026-11-23T23:00:00Z')['time_state'],'timely_return_recorded')
        r['returned_at']='2026-11-23T23:00:01Z'
        self.assertEqual(check(r,'2026-11-23T23:00:01Z')['time_state'],'late_return_recorded')
    def test_wait_does_not_stop_clock(self):
        r=self.record();r['outside_wait']='awaiting records'
        self.assertEqual(check(r,'2026-11-24T00:00:00Z')['time_state'],'deadline_breached_no_return')
    def test_no_silent_reset(self):
        r=self.record();r['observed_acceptance_at']='2026-11-23T00:00:00Z'
        self.assertIn('ORIGINAL_CLOCK_DRIFT',check(r,'2026-11-23T01:00:00Z')['errors'])
    def test_no_timezone_is_invalid(self):
        r=self.record();r['observed_acceptance_at']='2026-11-22T23:00:00'
        self.assertFalse(check(r,'2026-11-23T00:00:00Z')['record_valid'])
    def test_legacy_preserves_history(self):
        r=self.record();r['legacy_transition']=True
        self.assertIn('LEGACY_HISTORY_MISSING',check(r,'2026-11-23T00:00:00Z')['errors'])
        r.update(historical_start_reference='historical authority',legacy_exception='elapsed legacy retained')
        self.assertTrue(check(r,'2026-11-23T00:00:00Z')['record_valid'])
    def test_timely_not_qualified_or_issued(self):
        r=self.record();r.update(returned_at='2026-11-23T00:00:00Z',return_evidence_reference='receipt',quality_state='verified_for_issue')
        out=check(r,'2026-11-23T00:00:00Z')
        self.assertIn('QUALIFICATION_CONFLICT_WITH_ISSUE_QUALITY',out['errors'])
        self.assertIn('GAPS_CONFLICT_WITH_ISSUE_QUALITY',out['errors'])
    def test_missing_proof_and_future_return_rejected(self):
        r=self.record();r['returned_at']='2026-11-23T02:00:00Z'
        out=check(r,'2026-11-23T00:00:00Z')
        self.assertIn('RETURN_TIME_INVALID',out['errors']);self.assertIn('RETURN_EVIDENCE_MISSING',out['errors'])
    def test_issue_requires_own_authority(self):
        r=self.record();r['external_issue_authorized']=True
        self.assertIn('ISSUE_AUTHORITY_MISSING',check(r,'2026-11-23T00:00:00Z')['errors'])

if __name__=='__main__': unittest.main()
