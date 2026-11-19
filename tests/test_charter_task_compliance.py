"""Fictional, offline adversarial cases; no Member/corpus/runtime access."""
import copy
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from datetime import datetime, timezone, timedelta
from tools.test_assessment_research_entry import research_fixture

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
        self.task['task_type'] = 'other'
        self.remind('gpt-6.1-sol', 'medium', 'Please switch to GPT-6.1 Sol at Medium reasoning.')
        self.task['analytical_review'] = {}
        for lens in gate.ANALYTICAL_LENSES:
            row = {'state': 'reviewed', 'conclusion': 'Fictional conclusion for ' + lens,
                   'reasoning': 'Fictional comparison and basis for ' + lens,
                   'limitations': ['Fictional fixture scope only'], 'evidence': ['review-' + lens]}
            self.add_evidence('review-' + lens, {'task_id': self.task['task_id'], 'lens': lens,
                **{k: row[k] for k in ('conclusion', 'reasoning', 'limitations')}})
            self.task['analytical_review'][lens] = row
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
        self.add_evidence('answer', {'text': 'Fictional decision and its scope.'})
        self.task['outputs'] = [{'format': 'text', 'claim': 'Fictional decision', 'evidence': 'answer',
                                 'verification_evidence': ['proof']}]
        for focus in ('scope', 'source', 'currency', 'calculation', 'alternative', 'effect', 'owner', 'limits'):
            self.add_pass('substantive', focus)
        self.add_pass('editorial', 'clarity')

    def add_evidence(self, eid, value):
        data = json.dumps(value).encode()
        path = self.evidence / (eid + '.json')
        path.write_bytes(data)
        self.task['evidence'][eid] = {'path': path.name, 'sha256': gate.fingerprint(data),
            'provenance': 'Fictional fixture only', 'method': 'fixture_readback', 'result': 'verified'}

    def remind(self, model, reasoning, text):
        self.add_evidence('reminder', {'task_id': self.task['task_id'], 'visible_text': text})
        self.task['model_reminder'] = {'task_id': self.task['task_id'], 'model': model,
            'reasoning': reasoning, 'text': text, 'evidence': ['reminder'],
            'automatic_switching_claimed': False}

    def add_pass(self, kind, focus, reviewed=None):
        ledger = self.task['review_passes']
        number = len(ledger) + 1
        eid = 'pass-' + str(number)
        reviewed = ['answer'] if reviewed is None else reviewed
        entry = {'kind': kind, 'focus': focus, 'finding': 'Fixture observation about ' + focus,
                 'disposition': 'Retained because the fixture supports ' + focus}
        self.add_evidence(eid, {'task_id': self.task['task_id'], 'sequence': number, **entry,
            'reviewed_sha256': {i: self.task['evidence'][i]['sha256'] for i in reviewed}})
        ledger.append({**entry, 'reviewed': list(reviewed), 'evidence': [eid]})

    def mutate_evidence(self, eid, fn):
        value = gate.load(self.evidence / self.task['evidence'][eid]['path'])
        fn(value)
        self.add_evidence(eid, value)

    def result(self):
        return gate.check(self.root, self.catalog, self.task, self.evidence, self.now)

    def rejects(self, code):
        self.assertIn(code, self.result()['errors'])

    def test_assessment_reminder_passes_without_switch_confirmation(self):
        self.task['task_type'] = 'assessment'
        self.remind('gpt-6.2-astra', 'highest_available',
                    'Please switch to GPT-6.2 Astra at the highest available reasoning setting.')
        self.assertNotIn('TASK_MODEL_REMINDER_NOT_VERIFIED', self.result()['errors'])
        self.rejects('PROSPECTIVE_ASSESSMENT_ENTRY_NOT_VERIFIED')

    def test_many_public_sources_and_executed_generic_searches_cannot_open_entry(self):
        task, raw, now = research_fixture(self.task['task_id'])
        review = json.loads(raw['review-internet'])
        review['items'].extend({'id': 'reference-' + str(i), 'version': '1', 'state': 'screened_no_match'}
                               for i in range(1000))
        raw['review-internet'] = json.dumps(review).encode()
        research = json.loads(raw['research'])
        for number, row in enumerate(research['searches']):
            receipt = json.loads(raw[row['evidence']])
            generic = f'General continuity literature edition {number}'
            receipt['query'] = row['query'] = generic
            raw[row['evidence']] = json.dumps(receipt).encode()
            raw[receipt['result']] = (generic + ' results returned by fixture search').encode()
            task['locations']['internet']['queries'][number]['query'] = generic
        raw['research'] = json.dumps(research).encode()
        self.assertIn('ASSESSMENT_RESEARCH_ENTRY_SEARCH', gate.check_research_entry(task, raw, now, True))

    def test_legacy_record_cannot_manufacture_a_research_start_on_reconcile(self):
        self.task['task_type'] = 'assessment'
        self.task.pop('started_at', None)
        recovered = gate.reconcile(self.task, self.catalog)
        self.assertEqual(recovered['assessment_research'], {})
        self.assertNotIn('started_at', recovered)

    def test_cli_records_entry_before_analysis_and_reopens_changed_evidence(self):
        projected, raw, fixture_now = research_fixture(self.task['task_id'])
        for key in ('task_type', 'started_at', 'assessment_research', 'locations'):
            self.task[key] = copy.deepcopy(projected[key])
        self.remind('gpt-6.2-astra', 'highest_available',
                    'Switch to GPT-6.2 Astra at the highest available reasoning setting.')
        for key, body in raw.items():
            meta = projected['evidence'][key]
            (self.evidence / meta['path']).write_bytes(body)
            self.task['evidence'][key] = meta.copy()
        for location, record in self.task['locations'].items():
            boundary = location + '-fictional-scope'
            rows = json.loads(raw[record['review']])['items']
            inventory = {'task_id': self.task['task_id'], 'boundary': boundary,
                         'authority': 'Fictional scoped inventory',
                         'observed_at': projected['started_at'],
                         'items': [{'id': row['id'], 'version': row['version']} for row in rows]}
            for snapshot in ('before', 'after'):
                eid = location + '-' + snapshot
                self.add_evidence(eid, inventory)
                record[snapshot] = eid
                record['evidence'].append(eid)
            record.update(boundary=boundary, discovery_method='Fictional inventory readback')
        catalog = self.base / 'register.json'
        task_path = self.base / 'task.json'
        ledger = self.base / 'journal.json'
        entry_receipt = self.evidence / 'research-entry.json'
        final_receipt = self.base / 'final.json'
        gate.save(catalog, self.catalog)
        args = ['--root', str(self.root), '--register', str(catalog), '--task', str(task_path),
                '--evidence-root', str(self.evidence), '--journal', str(ledger)]
        def run(command, receipt, moment):
            gate.save(task_path, self.task)
            class Clock(datetime):
                @classmethod
                def now(cls, tz=None):
                    return moment
            with patch.object(gate, 'datetime', Clock):
                return gate.main([command, *args, '--receipt', str(receipt)])

        analysis = self.task['assessment_research'].pop('analysis')
        outputs = self.task.pop('outputs')
        recommendations = self.task['analytical_review'].pop('recommendations')
        for key in (analysis, 'initial-analysis'):
            del self.task['evidence'][key]
        entry_time = datetime.fromisoformat(json.loads(raw['research'])['at']) + timedelta(seconds=1)
        self.assertEqual(run('research-entry', entry_receipt, entry_time), 0)
        self.assertEqual(gate.load(entry_receipt)['result'], 'entry_verified')
        self.assertEqual(run('research-entry', entry_receipt, entry_time), 1)
        self.task['assessment_research']['analysis'] = analysis
        self.task['analytical_review']['recommendations'] = recommendations
        for key in (analysis, 'initial-analysis'):
            self.task['evidence'][key] = projected['evidence'][key]
        self.task['outputs'] = outputs
        first_pass = self.task['review_passes'][0]
        first_pass['reviewed'].append('initial-analysis')
        self.mutate_evidence(first_pass['evidence'][0],
                             lambda record: record['reviewed_sha256'].update(
                                 {'initial-analysis': self.task['evidence']['initial-analysis']['sha256']}))
        self.task['evidence']['checkpoint'] = {'path': entry_receipt.name,
            'sha256': gate.fingerprint(entry_receipt.read_bytes()), 'method': 'checkpoint_readback',
            'provenance': 'Fictional private journal', 'result': 'verified'}
        self.task['assessment_entry_receipt'] = 'checkpoint'
        self.assertEqual(run('verify', final_receipt, fixture_now), 0, gate.load(final_receipt)['errors'])
        self.assertEqual(gate.load(final_receipt)['result'], 'verified_record')
        # Identical receipt bytes without the earlier journal event cannot close an assessment.
        self.assertIn('PROSPECTIVE_ASSESSMENT_ENTRY_NOT_VERIFIED',
                      gate.check(self.root, self.catalog, self.task, self.evidence, fixture_now,
                                 journal_path=self.base / 'another-ledger.json')['errors'])
        self.assertEqual(run('research-entry', self.base / 'late.json', fixture_now), 2)
        self.assertIn('ENTRY_AFTER_SUBSTANTIVE_ASSESSMENT', gate.load(self.base / 'late.json')['errors'])
        # The old excerpt is still there, but the current source has material new text.
        source = self.task['evidence']['body-M']
        source_path = self.evidence / source['path']
        source_path.write_bytes(source_path.read_bytes() + b' The issuer has revised those instructions.')
        source['sha256'] = gate.fingerprint(source_path.read_bytes())
        self.assertEqual(run('verify', final_receipt, fixture_now), 2)
        self.assertIn('PROSPECTIVE_ASSESSMENT_ENTRY_NOT_VERIFIED', gate.load(final_receipt)['errors'])

    def test_missing_reminder_is_blocked(self):
        del self.task['model_reminder']
        self.rejects('TASK_MODEL_REMINDER_NOT_VERIFIED')

    def test_unclassified_task_cannot_pass(self):
        self.task['task_type'] = 'unclassified'
        self.rejects('TASK_MODEL_REMINDER_NOT_VERIFIED')

    def test_assessment_using_other_reminder_is_blocked(self):
        self.task['task_type'] = 'assessment'
        self.rejects('TASK_MODEL_REMINDER_NOT_VERIFIED')

    def test_other_work_using_assessment_reminder_is_blocked(self):
        self.remind('gpt-6.2-astra', 'highest_available',
                    'Please switch to GPT-6.2 Astra at the highest available reasoning setting.')
        self.rejects('TASK_MODEL_REMINDER_NOT_VERIFIED')

    def test_wrong_reasoning_is_blocked(self):
        self.task['model_reminder']['reasoning'] = 'high'
        self.rejects('TASK_MODEL_REMINDER_NOT_VERIFIED')

    def test_foreign_task_reminder_is_blocked(self):
        self.task['model_reminder']['task_id'] = 'another-task'
        self.rejects('TASK_MODEL_REMINDER_NOT_VERIFIED')

    def test_reminder_without_actual_proof_is_blocked(self):
        self.task['model_reminder']['evidence'] = []
        self.rejects('TASK_MODEL_REMINDER_NOT_VERIFIED')

    def test_reminder_text_does_not_match_proof_is_blocked(self):
        self.task['model_reminder']['text'] = 'Please switch to GPT-6.1 Sol at Medium reasoning. Extra.'
        self.rejects('TASK_MODEL_REMINDER_NOT_VERIFIED')

    def test_reminder_fields_cannot_disguise_wrong_visible_text(self):
        self.task['model_reminder']['text'] = 'Please switch to GPT-6.2 Astra at highest reasoning.'
        self.rejects('TASK_MODEL_REMINDER_NOT_VERIFIED')

    def test_false_automatic_switch_claim_is_blocked(self):
        self.task['model_reminder']['automatic_switching_claimed'] = True
        self.rejects('TASK_MODEL_REMINDER_NOT_VERIFIED')

    def test_model_listing_without_switch_request_is_blocked(self):
        self.remind('gpt-6.1-sol', 'medium', 'GPT-6.1 Sol Medium reasoning.')
        self.rejects('TASK_MODEL_REMINDER_NOT_VERIFIED')

    def test_reminder_rechecked_at_task_category_change(self):
        self.task['task_type'] = 'assessment'
        self.assertIn('TASK_MODEL_REMINDER_NOT_VERIFIED', self.result()['errors'])
        self.remind('gpt-6.2-astra', 'highest_available',
                    'Please switch to GPT-6.2 Astra at highest available reasoning.')
        self.assertNotIn('TASK_MODEL_REMINDER_NOT_VERIFIED', self.result()['errors'])
        self.rejects('PROSPECTIVE_ASSESSMENT_ENTRY_NOT_VERIFIED')
        self.task['task_type'] = 'other'
        self.assertIn('TASK_MODEL_REMINDER_NOT_VERIFIED', self.result()['errors'])

    def test_reminder_typography_normalization(self):
        self.task['model_reminder']['text'] = 'Please switch to **GPT\u20116.1 Sol** at **Medium reasoning**.'
        self.assertEqual(self.result()['result'], 'verified_record')

    def test_foreign_task_reminder_evidence_is_blocked(self):
        self.mutate_evidence('reminder', lambda x: x.update(task_id='other-task'))
        self.rejects('TASK_MODEL_REMINDER_NOT_VERIFIED')

    def test_malformed_reminder_evidence_is_blocked(self):
        self.add_evidence('reminder', ['not-a-reminder-record'])
        self.rejects('TASK_MODEL_REMINDER_NOT_VERIFIED')


    def test_previous_astra_model_is_rejected_for_current_assessment(self):
        self.task['task_type'] = 'assessment'
        self.remind('gpt-6-astra', 'highest_available',
                    'Please switch to GPT-6 Astra at highest available reasoning.')
        self.rejects('TASK_MODEL_REMINDER_NOT_VERIFIED')

    def test_previous_astra_visible_text_cannot_disguise_new_model(self):
        self.task['task_type'] = 'assessment'
        self.remind('gpt-6.2-astra', 'highest_available',
                    'Please switch to GPT-6 Astra at highest available reasoning.')
        self.rejects('TASK_MODEL_REMINDER_NOT_VERIFIED')

    def test_assessment_reasoning_cannot_silently_drop_to_medium(self):
        self.task['task_type'] = 'assessment'
        self.remind('gpt-6.2-astra', 'medium',
                    'Please switch to GPT-6.2 Astra at highest available reasoning.')
        self.rejects('TASK_MODEL_REMINDER_NOT_VERIFIED')

    def test_missing_analytical_review_is_rejected(self):
        del self.task['analytical_review']
        self.rejects('ANALYTICAL_REVIEW_MEMBERSHIP_MISMATCH')

    def test_each_analytical_duty_is_mandatory(self):
        for lens in gate.ANALYTICAL_LENSES:
            with self.subTest(lens=lens):
                saved = self.task['analytical_review'].pop(lens)
                self.rejects('ANALYTICAL_REVIEW_MEMBERSHIP_MISMATCH')
                self.task['analytical_review'][lens] = saved

    def test_unknown_analytical_duty_cannot_replace_required_review(self):
        self.task['analytical_review']['extra'] = {}
        self.rejects('ANALYTICAL_REVIEW_MEMBERSHIP_MISMATCH')

    def test_blanket_not_applicable_cannot_skip_analytical_duty(self):
        self.task['analytical_review']['methodologies']['state'] = 'not_applicable'
        self.rejects('ANALYTICAL_REVIEW_NOT_VERIFIED:methodologies')

    def test_analytical_conclusion_and_reasoning_are_required(self):
        for field in ('conclusion', 'reasoning'):
            with self.subTest(field=field):
                row = self.task['analytical_review']['assumptions']
                saved = row[field]
                row[field] = ' '
                self.rejects('ANALYTICAL_REVIEW_NOT_VERIFIED:assumptions')
                row[field] = saved

    def test_analytical_limits_are_required(self):
        self.task['analytical_review']['recommendations']['limitations'] = []
        self.rejects('ANALYTICAL_REVIEW_NOT_VERIFIED:recommendations')

    def test_analytical_proof_is_required(self):
        self.task['analytical_review']['evidence_and_consequences']['evidence'] = []
        self.rejects('ANALYTICAL_REVIEW_NOT_VERIFIED:evidence_and_consequences')

    def test_analytical_proof_from_foreign_task_is_rejected(self):
        self.mutate_evidence('review-assumptions', lambda x: x.update(task_id='other-task'))
        self.rejects('ANALYTICAL_REVIEW_NOT_VERIFIED:assumptions')

    def test_analytical_proof_from_wrong_duty_is_rejected(self):
        self.mutate_evidence('review-methodologies', lambda x: x.update(lens='recommendations'))
        self.rejects('ANALYTICAL_REVIEW_NOT_VERIFIED:methodologies')

    def test_analytical_summary_must_match_evidence(self):
        self.task['analytical_review']['recommendations']['conclusion'] = 'Unproved changed recommendation'
        self.rejects('ANALYTICAL_REVIEW_NOT_VERIFIED:recommendations')

    def test_bounded_no_conflict_result_is_allowed_with_review_proof(self):
        lens = 'evidence_and_consequences'
        row = self.task['analytical_review'][lens]
        row['conclusion'] = 'No material conflict found in the two fictional source versions reviewed.'
        row['reasoning'] = 'Compared both complete fictional records; considered side effects of assuming agreement.'
        self.add_evidence('review-' + lens, {'task_id': self.task['task_id'], 'lens': lens,
            **{k: row[k] for k in ('conclusion', 'reasoning', 'limitations')}})
        self.assertEqual(self.result()['result'], 'verified_record')

    def test_brief_status_task_still_requires_all_four_reviews(self):
        self.task['objective'] = 'Brief status answer'
        del self.task['analytical_review']['methodologies']
        self.rejects('ANALYTICAL_REVIEW_MEMBERSHIP_MISMATCH')

    def test_malformed_analytical_record_is_rejected(self):
        self.task['analytical_review']['assumptions'] = []
        self.rejects('ANALYTICAL_REVIEW_NOT_VERIFIED:assumptions')

    def test_malformed_analytical_evidence_is_rejected(self):
        self.add_evidence('review-assumptions', ['not a review'])
        self.rejects('ANALYTICAL_REVIEW_NOT_VERIFIED:assumptions')


    def test_complete_record_needs_no_routine_human_attestation(self):
        self.assertEqual(self.result()['errors'], [])
        self.assertEqual(self.result()['result'], 'verified_record')

    def test_exact_minimum_and_extra_genuine_reviews(self):
        result = self.result()
        self.assertEqual(result['result'], 'verified_record')
        self.assertEqual(result['counts']['verified_substantive_passes'], 8)
        self.assertEqual(result['counts']['verified_editorial_passes'], 1)
        self.add_pass('substantive', 'response to a correction')
        self.rejects('FINAL_EDITORIAL_PASS_NOT_VERIFIED')
        self.add_pass('editorial', 'final correction readback')
        self.assertEqual(self.result()['result'], 'verified_record')

    def test_substantive_minimum_cannot_include_editorial_or_initial_work(self):
        self.task['review_passes'] = self.task['review_passes'][:7]
        self.add_pass('editorial', 'final wording')
        self.rejects('EIGHT_SUBSTANTIVE_REPASSES_REQUIRED')
        self.task['review_passes'] = []
        self.add_pass('initial', 'first draft')
        self.rejects('REVIEW_PASS_NOT_VERIFIED:1')

    def test_eight_substantive_passes_cannot_replace_editorial(self):
        self.task['review_passes'].pop()
        self.rejects('FINAL_EDITORIAL_PASS_NOT_VERIFIED')

    def test_replayed_foreign_out_of_order_or_unbound_pass_receipt(self):
        row = self.task['review_passes'][0]
        self.mutate_evidence('pass-1', lambda r: r.update(task_id='foreign'))
        self.rejects('REVIEW_PASS_NOT_VERIFIED:1')
        self.mutate_evidence('pass-1', lambda r: r.update(task_id=self.task['task_id'], sequence=True))
        self.rejects('REVIEW_PASS_NOT_VERIFIED:1')
        self.mutate_evidence('pass-1', lambda r: r.update(sequence=1))
        row['evidence'] = ['pass-2']
        self.rejects('REVIEW_PASS_NOT_VERIFIED:1')
        row['evidence'] = ['pass-1']
        row['finding'] = 'Unrecorded conclusion'
        self.rejects('REVIEW_PASS_NOT_VERIFIED:1')

    def test_relabelled_duplicate_pass_on_same_bytes_does_not_count(self):
        self.task['review_passes'].pop()
        self.add_pass('substantive', 'fresh heading for same work')
        old, new = self.task['review_passes'][0], self.task['review_passes'][-1]
        for key in ('finding', 'disposition'):
            new[key] = '  ' + old[key].upper()
        self.mutate_evidence('pass-9', lambda r: r.update(finding=new['finding'], disposition=new['disposition']))
        self.add_pass('editorial', 'clarity')
        self.rejects('REVIEW_PASS_NOT_VERIFIED:9')

    def test_same_focus_can_be_rechecked_on_new_revision(self):
        self.task['review_passes'].pop()
        self.add_evidence('revision', {'text': 'Updated fictional response'})
        self.add_pass('substantive', 'scope', ['revision'])
        self.task['outputs'][0]['evidence'] = 'revision'
        self.add_pass('editorial', 'latest wording', ['revision'])
        self.assertEqual(self.result()['result'], 'verified_record')

    def test_unchanged_task_id_cannot_hide_changed_output_bytes(self):
        self.add_evidence('answer', {'text': 'Different fictional final response'})
        self.rejects('FINAL_EDITORIAL_PASS_NOT_VERIFIED')
        self.rejects('REVIEW_PASS_NOT_VERIFIED:9')

    def test_one_editorial_record_can_cover_multiple_final_outputs(self):
        self.add_evidence('second', {'text': 'Fictional appendix'})
        self.task['outputs'].append({'format': 'text', 'evidence': 'second', 'claim': 'Fictional appendix',
                                     'verification_evidence': ['proof']})
        self.rejects('FINAL_EDITORIAL_PASS_NOT_VERIFIED')
        self.add_pass('editorial', 'complete package', ['answer', 'second'])
        self.assertEqual(self.result()['result'], 'verified_record')

    def test_pass_receipt_cannot_review_another_pass_as_the_work(self):
        self.add_pass('editorial', 'record-only reading', ['answer', 'pass-1'])
        self.rejects('REVIEW_RECEIPT_USED_AS_WORK')

    def test_missing_passes_in_legacy_record_reconcile_without_inventing_history(self):
        del self.task['review_passes']
        self.rejects('REVIEW_PASS_HISTORY_MISSING')
        updated = gate.reconcile(self.task, self.catalog)
        self.assertEqual(updated['review_passes'], [])
        self.assertNotIn('review_passes', self.task)
        (self.root / gate.ROOTS[0]).write_text('# Next authority\n')
        new_authority = gate.reconcile(self.task, gate.register(self.root))
        self.assertEqual(new_authority['authority_history'][-1]['task_sha256'], gate.fingerprint(self.task))
        self.assertEqual(new_authority['review_passes'], [])

    def test_missing_or_malformed_material_and_no_declared_deliverable_fail_closed(self):
        self.task['review_passes'][0]['reviewed'] = [{}]
        self.rejects('REVIEW_PASS_NOT_VERIFIED:1')
        self.task['outputs'] = []
        self.rejects('FINAL_EDITORIAL_PASS_NOT_VERIFIED')

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
