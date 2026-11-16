"""Fictional, offline adversarial cases; no Member/corpus/runtime access."""
import copy
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
from datetime import datetime, timezone, timedelta

MODULE = Path(__file__).resolve().parents[1] / 'tools/charter_task_compliance.py'
spec = importlib.util.spec_from_file_location('charter_task_compliance', MODULE)
gate = importlib.util.module_from_spec(spec)
spec.loader.exec_module(gate)


class ComplianceGateTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.base = Path(self.temp.name)
        self.root = self.base / 'repo'
        self.root.mkdir()
        self.evidence = self.base / 'private'
        self.evidence.mkdir()
        self.now = datetime(2026, 11, 15, 22, 0, tzinfo=timezone.utc)
        for name in gate.ROOTS:
            (self.root / name).write_text('# Fictional authority\n\nAlways retain proof.\n', encoding='utf-8')
        self.catalog = gate.register(self.root)
        self.task = gate.new_task(self.catalog, 'FICTIONAL-CONTROL-TEST', 'Check a fictional artifact')
        self.task['scope'] = {'authorization': 'Fictional test only', 'boundary': 'Fixture bytes only', 'limitations': []}
        self.add_evidence('proof', {'method': 'fictional test execution', 'outcome': 'expected result'})
        for row in self.task['requirements']:
            row.update(state='met', reason='Fictional predicate proved by fixture', evidence=['proof'],
                       checks=[{'criterion': 'Fixture criterion', 'result': 'pass', 'evidence': ['proof']}])
        self.task['locations'] = {}
        for kind in gate.LOCATIONS:
            inventory = {'task_id': self.task['task_id'], 'boundary': kind + '-fixture',
                         'observed_at': self.now.isoformat(), 'authority': 'Fictional inventory fixture',
                         'items': [{'id': kind + '-one', 'version': 'v1'}]}
            reviewed = {'task_id': self.task['task_id'], 'items': [
                {'id': kind + '-one', 'version': 'v1', 'state': 'content_reviewed',
                 'relevant': True, 'reason': 'Relevant to fictional check',
                 'evidence': ['proof'], 'portion_reviewed': 'Entire fictional item',
                 'where_used': ['fixture decision'], 'url': 'https://example.invalid/fixture',
                 'publisher': 'Fictional', 'title': 'Fixture', 'accessed_at': self.now.isoformat()}]}
            before, after, review = (kind + x for x in ['-before', '-after', '-review'])
            self.add_evidence(before, inventory)
            self.add_evidence(after, inventory)
            self.add_evidence(review, reviewed)
            self.task['locations'][kind] = {'state': 'considered', 'boundary': inventory['boundary'],
                'discovery_method': 'Fictional exact inventory', 'before': before, 'after': after,
                'review': review, 'evidence': [before, after, review],
                'queries': [{'query': 'fictional task query', 'searched_at': self.now.isoformat(), 'evidence': ['proof']}]}
        self.add_evidence('holds-before', {'reader_enabled': False, 'assessment': 'paused'})
        self.add_evidence('holds-after', {'reader_enabled': False, 'assessment': 'paused'})
        self.task['holds'] = {'expected': {'reader_enabled': False, 'assessment': 'paused'},
                              'before_evidence': ['holds-before'], 'after_evidence': ['holds-after']}
        self.task['capture'] = {'state': 'reconciled', 'expected': 2, 'retained': 2,
                                'destination': 'private fixture', 'evidence': ['proof']}

    def add_evidence(self, eid, value):
        data = json.dumps(value).encode()
        path = self.evidence / (eid + '.json')
        path.write_bytes(data)
        self.task['evidence'][eid] = {'path': path.name, 'sha256': gate.fingerprint(data),
            'provenance': 'Fictional fixture only', 'method': 'fixture_readback', 'result': 'verified'}

    def mutate_evidence(self, eid, fn):
        value = gate.load(self.evidence / self.task['evidence'][eid]['path'])
        fn(value)
        self.add_evidence(eid, value)

    def result(self):
        return gate.check(self.root, self.catalog, self.task, self.evidence, self.now)

    def rejects(self, code):
        self.assertIn(code, self.result()['errors'])

    def test_complete_record_needs_no_routine_human_attestation(self):
        self.assertEqual(self.result()['errors'], [])
        self.assertEqual(self.result()['result'], 'verified_record')

    def test_every_nonblank_line_is_accounted_for(self):
        path = self.root / gate.ROOTS[0]
        path.write_text('# Title\n\nPlain context\n- Mandatory action\n| Header |\n|---|\n| Rule |\n')
        c = gate.register(self.root)
        self.assertEqual([u['line'] for u in c['units'] if u['source'] == gate.ROOTS[0]], [1, 3, 4, 5, 6, 7])

    def test_transitive_reference_changes_stale_the_register(self):
        (self.root / 'nested.md').write_text('# Extra\nSpecific requirement\n')
        with (self.root / gate.ROOTS[0]).open('a') as f:
            f.write('Apply `nested.md` and `unavailable.md`.\n')
        c = gate.register(self.root)
        self.assertIn('nested.md', c['sources'])
        self.assertEqual(next(r for r in c['references'] if r['reference'] == 'unavailable.md')['state'], 'unexpanded')
        self.catalog = c
        self.task['register_sha256'] = c['register_sha256']
        self.rejects('REFERENCED_AUTHORITY_MEMBERSHIP_MISMATCH')

    def test_changed_charter_blocks_existing_record(self):
        with (self.root / gate.ROOTS[0]).open('a') as f:
            f.write('New requirement\n')
        self.rejects('AUTHORITY_OR_REGISTER_DRIFT')

    def test_missing_authority_blocks(self):
        (self.root / gate.ROOTS[0]).unlink()
        self.rejects('AUTHORITY_UNAVAILABLE')

    def test_crlf_does_not_change_canonical_register(self):
        p = self.root / gate.ROOTS[0]
        p.write_bytes(p.read_bytes().replace(b'\r\n', b'\n').replace(b'\n', b'\r\n'))
        self.assertEqual(self.result()['errors'], [])

    def test_stale_task_register(self):
        self.task['register_sha256'] = '0' * 64
        self.rejects('TASK_REGISTER_STALE')

    def test_omitted_requirement(self):
        self.task['requirements'].pop()
        self.rejects('REQUIREMENT_MEMBERSHIP_MISMATCH')

    def test_duplicate_requirement(self):
        self.task['requirements'].append(copy.deepcopy(self.task['requirements'][0]))
        self.rejects('REQUIREMENT_MEMBERSHIP_MISMATCH')

    def test_unknown_requirement(self):
        self.task['requirements'][0]['id'] = 'invented'
        self.rejects('REQUIREMENT_MEMBERSHIP_MISMATCH')

    def test_open_requirement(self):
        self.task['requirements'][0]['state'] = 'blocked'
        self.rejects('REQUIREMENTS_OPEN')

    def test_met_requires_acceptance_criteria_and_verified_check(self):
        self.task['requirements'][0]['checks'] = []
        self.rejects('REQUIREMENT_ACCEPTANCE_CHECK_MISSING')

    def test_reconcile_retains_history_and_reopens_obligations(self):
        (self.root / gate.ROOTS[0]).write_text('# Changed authority\nNew obligation\n')
        current = gate.register(self.root)
        task = gate.reconcile(self.task, current)
        self.assertEqual(task['task_id'], self.task['task_id'])
        self.assertEqual(task['authority_history'][0]['requirements'], self.task['requirements'])
        self.assertTrue(all(x['state'] == 'pending' for x in task['requirements']))
        self.assertEqual(task['register_sha256'], current['register_sha256'])

    def test_reconcile_unchanged_authority_does_not_reset_proof(self):
        self.assertEqual(gate.reconcile(self.task, self.catalog), self.task)

    def test_unjustified_nonapplicability(self):
        self.task['requirements'][0].update(state='not_applicable', reason='')
        self.rejects('REQUIREMENT_PROOF_MISSING')

    def test_false_supersession(self):
        self.task['requirements'][0].update(state='superseded', superseded_by='missing')
        self.rejects('SUPERSESSION_UNRESOLVED')

    def test_assertion_is_not_evidence(self):
        self.task['evidence']['proof']['method'] = 'attestation'
        self.rejects('EVIDENCE_INVALID:proof')

    def test_evidence_byte_drift(self):
        (self.evidence / 'proof.json').write_text('changed')
        self.rejects('EVIDENCE_INVALID:proof')

    def test_evidence_path_escape(self):
        self.task['evidence']['proof']['path'] = '../repo/SALUS_PROGRAM_CHARTER.md'
        self.rejects('EVIDENCE_INVALID:proof')

    def test_absolute_and_windows_path_escape(self):
        for p in ['/tmp/anything', 'C:/anything', 'sub/../anything', 'x\\anything']:
            with self.assertRaises(ValueError):
                gate.confined(self.evidence, p)

    def test_omitted_location(self):
        del self.task['locations']['knowledge']
        self.rejects('LOCATION_MEMBERSHIP_MISMATCH')

    def test_search_results_do_not_replace_corpus_coverage(self):
        self.task['locations']['knowledge']['state'] = 'searched'
        self.rejects('LOCATION_OPEN:knowledge')

    def test_inventory_drift(self):
        self.mutate_evidence('knowledge-after', lambda x: x['items'].append({'id': 'late', 'version': 'v2'}))
        self.rejects('COVERAGE_NOT_VERIFIED:knowledge')

    def test_missing_inventory_member(self):
        self.mutate_evidence('knowledge-review', lambda x: x['items'].clear())
        self.rejects('COVERAGE_NOT_VERIFIED:knowledge')

    def test_wrong_version_or_duplicate_member(self):
        self.mutate_evidence('osint-review', lambda x: x['items'].append(copy.deepcopy(x['items'][0])))
        self.rejects('COVERAGE_NOT_VERIFIED:osint')

    def test_duplicate_corrective_action_rejected(self):
        item = {'id': 'CAPA-duplicate', 'cause': 'fixture', 'affected_work': 'fixture',
                'correction': 'fixture', 'evidence': ['proof']}
        self.task['corrective_actions'] = [item, item]
        self.assertIn('CORRECTIVE_ACTION_PROOF_INVALID', self.result()['errors'])

    def test_foreign_task_receipt(self):
        self.mutate_evidence('knowledge-review', lambda x: x.update(task_id='different'))
        self.rejects('COVERAGE_NOT_VERIFIED:knowledge')

    def test_stale_or_future_snapshot(self):
        for delta in [-90000, 60]:
            stamp = (self.now + timedelta(seconds=delta)).isoformat()
            for eid in ['knowledge-before', 'knowledge-after']:
                self.mutate_evidence(eid, lambda x: x.update(observed_at=stamp))
            self.rejects('COVERAGE_NOT_VERIFIED:knowledge')

    def test_relevant_held_content_blocks_review_claim(self):
        self.mutate_evidence('knowledge-review', lambda x: x['items'][0].update(state='unavailable'))
        self.rejects('COVERAGE_NOT_VERIFIED:knowledge')

    def test_content_review_requires_portion_and_where_used(self):
        self.mutate_evidence('osint-review', lambda x: x['items'][0].update(portion_reviewed=''))
        self.rejects('COVERAGE_NOT_VERIFIED:osint')

    def test_internet_requires_queries_and_exact_source_metadata(self):
        self.task['locations']['internet']['queries'] = []
        self.rejects('COVERAGE_NOT_VERIFIED:internet')

    def test_unlisted_download_is_not_a_reviewed_source(self):
        self.mutate_evidence('internet-review', lambda x: x['items'][0].update(state='downloaded'))
        self.rejects('COVERAGE_NOT_VERIFIED:internet')

    def test_missing_bibliography(self):
        self.mutate_evidence('internet-review', lambda x: x['items'][0].update(url=''))
        self.rejects('COVERAGE_NOT_VERIFIED:internet')

    def test_unbound_inventory_receipt(self):
        self.task['locations']['knowledge']['evidence'].remove('knowledge-review')
        self.rejects('COVERAGE_NOT_VERIFIED:knowledge')

    def test_capture_gap_blocks_completion(self):
        self.task['capture']['retained'] = 1
        self.rejects('CAPTURE_NOT_RECONCILED')

    def test_reader_or_pause_drift(self):
        self.mutate_evidence('holds-after', lambda x: x.update(reader_enabled=True))
        self.rejects('PROTECTED_HOLD_STATE_DRIFT')

    def test_false_expected_hold(self):
        self.task['holds']['expected']['assessment'] = 'active'
        self.rejects('PROTECTED_HOLD_STATE_DRIFT')

    def test_routine_attestation_is_not_delegated_to_user(self):
        self.task['routine_human_attestation_required'] = True
        self.rejects('ROUTINE_COMPLIANCE_IS_ASSISTANT_RESPONSIBILITY')

    def test_human_decision_requires_exact_action_target(self):
        self.add_evidence('approval', {'actor_role': 'human', 'decision': 'authorized',
                          'action': 'merge', 'target': 'wrong', 'source_reference': 'fictional message'})
        self.task['protected_actions'] = [{'action': 'merge', 'target': 'approved-head', 'approval_evidence': 'approval'}]
        self.rejects('HUMAN_AUTHORIZATION_MISSING_OR_MISMATCHED')

    def test_human_decision_separate_from_routine_verification(self):
        self.add_evidence('approval', {'actor_role': 'human', 'decision': 'authorized',
                          'action': 'merge', 'target': 'approved-head', 'source_reference': 'fictional message'})
        self.task['protected_actions'] = [{'action': 'merge', 'target': 'approved-head', 'approval_evidence': 'approval'}]
        self.assertEqual(self.result()['errors'], [])

    def test_document_partial_page_review_cannot_pass(self):
        self.add_evidence('document', {'fictional': 'artifact'})
        self.add_evidence('page-review', {'artifact_sha256': self.task['evidence']['document']['sha256'],
            'pages': 3, 'reviewed_pages': [1, 2], 'defects_open': 0})
        self.task['outputs'] = [{'format': 'docx', 'claim': 'working artifact', 'evidence': 'document',
            'verification_evidence': ['proof'], 'page_review': 'page-review'}]
        self.rejects('DOCUMENT_EXACT_PAGE_REVIEW_MISSING')

    def test_correction_retest_retains_history(self):
        ledger = self.base / 'journal.json'
        self.task['requirements'][0]['state'] = 'pending'
        gate.journal(ledger, self.result())
        self.task['requirements'][0]['state'] = 'met'
        self.task['corrective_actions'] = [{'id': cid, 'cause': 'Fixture left disposition pending',
            'affected_work': 'Fictional check', 'correction': 'Restored evidence-backed disposition',
            'evidence': ['proof']} for cid in gate.load(ledger)['corrections']]
        gate.journal(ledger, self.result())
        data = gate.load(ledger)
        self.assertEqual(len(data['events']), 2)
        self.assertTrue(all(v['state'] == 'corrected_and_rechecked' for v in data['corrections'].values()))

    def test_retest_does_not_silently_close_missing_cause_and_treatment(self):
        ledger = self.base / 'journal.json'
        self.task['requirements'][0]['state'] = 'pending'
        gate.journal(ledger, self.result())
        self.task['requirements'][0]['state'] = 'met'
        result = self.result()
        gate.journal(ledger, result)
        self.assertEqual(result['result'], 'incomplete')
        self.assertIn('CORRECTIVE_ACTION_DETAIL_OR_RETEST_OPEN', result['errors'])

    def test_corrective_action_requires_verified_proof(self):
        self.task['corrective_actions'] = [{'id': 'CAPA-fictional', 'cause': 'X', 'affected_work': 'Y',
            'correction': 'Z', 'evidence': ['missing']}]
        self.rejects('CORRECTIVE_ACTION_PROOF_INVALID')

    def test_journal_tampering_blocks(self):
        ledger = self.base / 'journal.json'
        gate.journal(ledger, self.result())
        x = gate.load(ledger)
        x['events'][0]['result']['result'] = 'invented'
        gate.save(ledger, x)
        with self.assertRaises(ValueError):
            gate.journal(ledger, self.result())

    def test_corrective_action_tampering_blocks(self):
        ledger = self.base / 'journal.json'
        self.task['requirements'][0]['state'] = 'pending'
        gate.journal(ledger, self.result())
        x = gate.load(ledger)
        next(iter(x['corrections'].values()))['state'] = 'closed'
        gate.save(ledger, x)
        with self.assertRaises(ValueError):
            gate.journal(ledger, self.result())

    def test_new_task_does_not_overwrite_existing_record(self):
        p = self.base / 'task.json'
        gate.save(p, self.task, exclusive=True)
        with self.assertRaises(FileExistsError):
            gate.save(p, {}, exclusive=True)

    def test_initialized_task_is_incomplete(self):
        self.task = gate.new_task(self.catalog, 'new-task', 'New fictional task')
        self.assertEqual(self.result()['result'], 'incomplete')

    def test_existing_journal_lock_blocks_parallel_write(self):
        p = self.base / 'journal.json'
        p.with_name(p.name + '.lock').write_text('other writer')
        with self.assertRaises(FileExistsError):
            gate.journal(p, self.result())
        self.assertFalse(p.exists())

    def test_cli_failure_retains_receipt_and_correction_without_evidence_mutation(self):
        catalog = self.base / 'register.json'
        task = self.base / 'task.json'
        receipt, journal = self.base / 'receipt.json', self.base / 'journal.json'
        self.task['requirements'][0]['state'] = 'pending'
        gate.save(catalog, self.catalog)
        gate.save(task, self.task)
        before = (self.evidence / 'proof.json').read_bytes()
        code = gate.main(['verify', '--root', str(self.root), '--register', str(catalog),
            '--task', str(task), '--evidence-root', str(self.evidence), '--receipt', str(receipt),
            '--journal', str(journal)])
        self.assertEqual(code, 2)
        self.assertEqual(gate.load(receipt)['result'], 'incomplete')
        self.assertTrue(gate.load(journal)['corrections'])
        self.assertEqual(before, (self.evidence / 'proof.json').read_bytes())

    def test_cli_cannot_overwrite_a_source_or_evidence_with_receipt(self):
        catalog, task = self.base / 'register.json', self.base / 'task.json'
        gate.save(catalog, self.catalog)
        gate.save(task, self.task)
        code = gate.main(['verify', '--root', str(self.root), '--register', str(catalog),
            '--task', str(task), '--evidence-root', str(self.evidence),
            '--receipt', str(self.evidence / 'proof.json'), '--journal', str(self.base / 'journal.json')])
        self.assertEqual(code, 1)


if __name__ == '__main__':
    unittest.main()
