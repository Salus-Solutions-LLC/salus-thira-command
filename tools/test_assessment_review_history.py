import unittest
from tools.assessment_review_history import summarize

def event(eid='one',kind='human_assessment',**kw):
    return dict(id=eid,kind=kind,evidence_reference='receipt/'+eid,edition='0.13',scope='four reports',
                result='reviewed',date_status='18 November 2026',roles=['investigator'],human_confirmation=True,**kw)

class ReviewHistoryTests(unittest.TestCase):
    def test_package_is_one_event(self):
        x=summarize([event()]);self.assertEqual(x['human_assessment_review_events'],1)
    def test_source_decisions_not_package_reviews(self):
        x=summarize([event(kind='human_source',source_decisions=18)]);self.assertEqual(x['human_assessment_review_events'],0);self.assertEqual(x['source_decisions'],18)
    def test_joint_review_roles_overlap(self):
        e=event();e['roles'].append('other_salus_personnel');x=summarize([e]);self.assertEqual(x['human_assessment_review_events'],1);self.assertEqual(x['other_personnel_events'],1)
    def test_duplicate_id_rejected(self):
        with self.assertRaises(ValueError):summarize([event(),event()])
    def test_repeated_evidence_rejected(self):
        a=event();b=event('two');b['evidence_reference']=a['evidence_reference']
        with self.assertRaises(ValueError):summarize([a,b])
    def test_automation_cannot_be_personnel(self):
        with self.assertRaises(ValueError):summarize([event(kind='automated_substantive')])
    def test_no_human_confirmation_rejected(self):
        a=event();a['human_confirmation']=False
        with self.assertRaises(ValueError):summarize([a])
    def test_automated_editorial_separate(self):
        a=event(kind='automated_editorial');a['roles']=[];x=summarize([a]);self.assertEqual(x['automated_editorial_passes'],1);self.assertEqual(x['human_assessment_review_events'],0)
    def test_unknown_count_not_zero_claim(self):
        self.assertIn('Documented events only',summarize([])['scope'])

if __name__=='__main__':unittest.main()
