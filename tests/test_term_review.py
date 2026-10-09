"""Focused review regressions. Run: python -m unittest discover -s tests -v"""
import importlib.util
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parents[1] / 'skills/daggerheart-term-checker/scripts'
sys.path.insert(0, str(SCRIPTS))
from check_terms import build_report, review_chunk, _pair_markers, _extract_markers
from term_markers import parse_markers, readable_context
from term_review import validate_approval, write_queue
from approve_term_review import approve, approve_batch
from strip_term_markers import main as strip, strip_term_markers_text


def wrap(text):
    return '[[[KILO_TARGET_START]]]\n' + text + '\n[[[KILO_TARGET_END]]]\n'


class ReviewTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.base = self.root / 'source/temp'
        for name in ('_chunks', '_translated_chunks'):
            (self.base/name).mkdir(parents=True)
        self.put('01', 'Spend 【Hope｜希望】. Clear 【HP｜生命点】.', '花费【希望｜希望】。恢复【生命值｜生命点】。')

    def put(self, name, source, translated):
        (self.base/'_chunks'/f'{name}.md').write_text(wrap(source), encoding='utf-8')
        (self.base/'_translated_chunks'/f'{name}.md').write_text(wrap(translated), encoding='utf-8')

    def approved(self, **kwargs):
        return approve(self.root, 'AI:test', [], baseline=True, semantic=True,
                       all_decisions=True, reason='Test-only explicit context decision',
                       expected_digest=build_report(self.root)['review_digest'], release=True, **kwargs)

    def test_clean_full_sentence_context_and_nested_note(self):
        text = 'Before. Spend 【Hope｜希望｜见【说明】】 to aid an ally. After.'
        markers, errors = parse_markers(text)
        self.assertFalse(errors)
        self.assertEqual(readable_context(text, markers[0]['pos']), 'Spend Hope to aid an ally.')
        self.assertEqual(strip_term_markers_text(text), 'Before. Spend Hope to aid an ally. After.')

    def test_audit_kept_and_difference_not_called_error(self):
        report = build_report(self.root)
        self.assertEqual(len(report['rows']), 2)
        self.assertEqual(report['review_stats']['baseline_matches'], 1)
        self.assertEqual(report['decisions'][0]['kind'], 'string_difference')
        self.assertEqual(report['stats']['structural_anomalies'], 0)

    def test_exact_context_grouping_only_and_stable_ids(self):
        self.put('02', 'Clear 【HP｜生命点】.', '恢复【生命值｜生命点】。')
        first = build_report(self.root)
        self.assertEqual(len(first['decisions']), 1)
        self.assertEqual(len(first['decisions'][0]['occurrences']), 2)
        self.put('03', 'Lose 【HP｜生命点】.', '失去【生命值｜生命点】。')
        second = build_report(self.root)
        self.assertEqual(len(second['decisions']), 2)
        self.assertIn(first['decisions'][0]['id'], [d['id'] for d in second['decisions']])

    def test_malformed_markers_and_duplicate_wrappers_block_both_modes(self):
        for text in ('【希望|希望】', '【｜希望】', '【希望｜】', '【希望｜希望', '希望｜希望】', '【外【内｜希望】｜希望】'):
            self.put('01', '【Hope｜希望】', text)
            self.assertGreater(build_report(self.root)['stats']['structural_anomalies'], 0, text)
            with self.assertRaises(ValueError):
                strip(self.root, mode='auto')
        self.put('01', '【Hope｜希望】', '【希望｜希望】')
        path = self.base/'_translated_chunks/01.md'
        path.write_text(wrap('【希望｜希望】')*2, encoding='utf-8')
        self.assertGreater(build_report(self.root)['stats']['structural_anomalies'], 0)

    def test_missing_extra_files_and_zero_markers(self):
        self.put('01', 'No markers.', '没有标记。')
        self.assertEqual(build_report(self.root)['review_stats']['unresolved_decisions'], 0)
        (self.base/'_translated_chunks/extra.md').write_text(wrap('额外'), encoding='utf-8')
        self.assertEqual(build_report(self.root)['stats']['structural_anomalies'], 1)

    def test_manual_requires_approval_and_semantic_attestation(self):
        with self.assertRaises(FileNotFoundError):
            strip(self.root)
        report = build_report(self.root)
        record = approve(self.root, 'AI:test', [], all_decisions=True, reason='Reviewed', expected_digest=report['review_digest'])
        with self.assertRaises(ValueError):
            validate_approval(report, record)
        self.approved()
        strip(self.root)
        self.assertIn('生命值', (self.base/'_translated_chunks_clean/01.md').read_text())

    def test_ai_acceptance_does_not_grant_manual_release(self):
        report = build_report(self.root)
        approve(self.root, 'AI:test', [], True, True, True, 'Reviewed', report['review_digest'])
        with self.assertRaisesRegex(ValueError, '手动放行'):
            strip(self.root)
        approve(self.root, 'human:test', [], expected_digest=report['review_digest'], release=True)
        strip(self.root)

    def test_partial_approval_unresolved_and_changed_source_invalidates(self):
        self.put('02', 'Lose 【HP｜生命点】.', '失去【生命值｜生命点】。')
        report = build_report(self.root)
        record = approve(self.root, 'AI:test', [report['decisions'][0]['id']], True, True, reason='Reviewed', expected_digest=report['review_digest'])
        self.assertEqual(build_report(self.root)['review_stats']['unresolved_decisions'], 1)
        with self.assertRaises(ValueError):
            validate_approval(report, record)
        self.approved()
        source = self.base/'_chunks/01.md'
        source.write_text(source.read_text()+'\nChanged source\n', encoding='utf-8')
        with self.assertRaises(ValueError):
            strip(self.root)
        self.assertEqual(build_report(self.root)['review_stats']['accepted_decisions'], 0)

    def test_regroup_and_changed_translation_invalidate(self):
        record = self.approved()
        self.put('02', 'Clear 【HP｜生命点】.', '恢复【生命值｜生命点】。')
        with self.assertRaises(ValueError):
            validate_approval(build_report(self.root), record)
        record = self.approved()
        self.put('01', 'Spend 【Hope｜希望】.', '获得【希望｜希望】。')
        with self.assertRaises(ValueError):
            validate_approval(build_report(self.root), record)

    def batch_payload(self):
        report = build_report(self.root)
        return dict(review_digest=report['review_digest'], input_digest=report['input_digest'],
                    decisions=[dict(id=d['id'], reason='Reviewed context ' + d['id']) for d in report['decisions']])

    def test_batch_rebuilds_once_and_never_grants_attestations_or_release(self):
        import approve_term_review as module
        self.put('02', 'Lose 【HP｜生命点】.', '失去【生命值｜生命点】。')
        payload = self.batch_payload()
        with patch.object(module, 'build_report', wraps=module.build_report) as builder:
            record = approve_batch(self.root, 'AI:batch', payload)
        self.assertEqual(builder.call_count, 1)
        self.assertEqual(len(record['approved_decisions']), 2)
        self.assertFalse(record['semantic_reviewed'])
        self.assertFalse(record['baseline_accepted'])
        self.assertNotIn('manual_release', record)
        with self.assertRaises(ValueError):
            strip(self.root)

    def test_batch_invalid_items_leave_existing_record_byte_identical(self):
        import copy
        self.put('02', 'Lose 【HP｜生命点】.', '失去【生命值｜生命点】。')
        payload = self.batch_payload()
        first = dict(payload, decisions=payload['decisions'][:1])
        approve_batch(self.root, 'AI:batch', first)
        path = self.base/'_term_review_approval.json'
        before = path.read_bytes()
        invalid = []
        for key in ('review_digest', 'input_digest'):
            item = copy.deepcopy(payload); item[key] = 'stale'; invalid.append(item)
            item = copy.deepcopy(payload); del item[key]; invalid.append(item)
        item = copy.deepcopy(payload); item['decisions'][1]['id'] = 'unknown'; invalid.append(item)
        item = copy.deepcopy(payload); item['decisions'][1]['reason'] = ' '; invalid.append(item)
        item = copy.deepcopy(payload); del item['decisions'][1]['reason']; invalid.append(item)
        item = copy.deepcopy(payload); del item['decisions'][1]['id']; invalid.append(item)
        item = copy.deepcopy(payload); item['decisions'][1]['id'] = ''; invalid.append(item)
        item = copy.deepcopy(payload); item['decisions'].append(dict(item['decisions'][0])); invalid.append(item)
        item = copy.deepcopy(payload); item['decisions'].append(dict(item['decisions'][0], reason='Conflicting')); invalid.append(item)
        item = copy.deepcopy(payload); item['decisions'][0]['reason'] = 'Conflicts with saved reason'; invalid.append(item)
        item = copy.deepcopy(payload); item['release'] = True; invalid.append(item)
        item = copy.deepcopy(payload); item['decisions'] = []; invalid.append(item)
        for bad in invalid:
            with self.subTest(payload=bad):
                with self.assertRaises(ValueError):
                    approve_batch(self.root, 'AI:batch', bad)
                self.assertEqual(path.read_bytes(), before)
        # A later bad item must not create an approval file if there was none.
        path.unlink()
        with self.assertRaises(ValueError):
            approve_batch(self.root, 'AI:batch', invalid[4])
        self.assertFalse(path.exists())

    def test_batch_cli_excludes_release_and_old_cli_still_works(self):
        payload = self.batch_payload()
        batch = self.root/'batch.json'
        batch.write_text(json.dumps(payload), encoding='utf-8')
        cmd = [sys.executable, str(SCRIPTS/'approve_term_review.py'), str(self.root), '--reviewer', 'AI:test']
        invalid = subprocess.run(cmd + ['--batch', str(batch), '--release'], capture_output=True, text=True)
        self.assertNotEqual(invalid.returncode, 0)
        self.assertFalse((self.base/'_term_review_approval.json').exists())
        valid = subprocess.run(cmd + ['--batch', str(batch)], capture_output=True, text=True)
        self.assertEqual(valid.returncode, 0, valid.stderr)
        old = subprocess.run(cmd + ['--review-digest', payload['review_digest'], '--accept-baseline', '--semantic-reviewed'], capture_output=True, text=True)
        self.assertEqual(old.returncode, 0, old.stderr)
        record = json.loads((self.base/'_term_review_approval.json').read_text())
        self.assertTrue(record['semantic_reviewed'])
        self.assertNotIn('manual_release', record)

    def test_batch_atomic_write_failure_preserves_old_record(self):
        import approve_term_review as module
        payload = self.batch_payload()
        approve_batch(self.root, 'AI:batch', payload)
        path = self.base/'_term_review_approval.json'
        before = path.read_bytes()
        with patch.object(module.os, 'replace', side_effect=OSError('Simulated replace failure')):
            with self.assertRaises(OSError):
                approve_batch(self.root, 'AI:batch', payload)
        self.assertEqual(path.read_bytes(), before)
        self.assertFalse(list(self.base.glob('.term-approval-*')))

    def test_batch_idempotent_import_preserves_decision_reviewer(self):
        payload = self.batch_payload()
        first = approve_batch(self.root, 'AI:first', payload)
        second = approve_batch(self.root, 'AI:second', payload)
        self.assertEqual(first['decision_reviews'], second['decision_reviews'])
        self.assertNotIn('manual_release', second)

    def test_reviewed_digest_required_and_unknown_id_rejected(self):
        with self.assertRaises(ValueError):
            approve(self.root, 'AI:test', [], expected_digest='old')
        with self.assertRaises(ValueError):
            approve(self.root, 'AI:test', ['d-unknown'], reason='Reviewed', expected_digest=build_report(self.root)['review_digest'])

    def test_semantic_issue_can_cover_unmarked_or_adopted_text(self):
        report = build_report(self.root)
        path = self.base/'_term_semantic_issues.json'
        issue = dict(chunk='01', problem='Wrong actor in unmarked prose', source_context='An ally acts.', translated_context='你行动。')
        path.write_text(json.dumps(dict(input_digest=report['input_digest'], issues=[issue])), encoding='utf-8')
        new = build_report(self.root)
        self.assertEqual(new['review_stats']['semantic_issues'], 1)
        self.assertNotEqual(new['review_digest'], report['review_digest'])
        self.put('02', 'New.', '新增。')
        with self.assertRaises(ValueError):
            build_report(self.root)

    def test_strip_writes_validated_snapshot_if_input_changes_later(self):
        import strip_term_markers as module
        self.approved()
        original_path = self.base/'_translated_chunks/01.md'
        reviewed = original_path.read_text()
        actual_process = module.process_directory
        def change_then_process(input_dir, output_dir, text_snapshot=None):
            original_path.write_text(wrap('Unreviewed concurrent edit.'), encoding='utf-8')
            return actual_process(input_dir, output_dir, text_snapshot=text_snapshot)
        with patch.object(module, 'process_directory', side_effect=change_then_process):
            strip(self.root)
        output = (self.base/'_translated_chunks_clean/01.md').read_text()
        self.assertEqual(output, strip_term_markers_text(reviewed))
        self.assertNotIn('Unreviewed', output)
        with self.assertRaises(ValueError):
            strip(self.root)

    def test_output_hardlink_cannot_mutate_original(self):
        out = self.base/'_translated_chunks_clean'
        out.mkdir()
        original = self.base/'_translated_chunks/01.md'
        before = original.read_bytes()
        os.link(original, out/'01.md')
        strip(self.root, mode='auto')
        self.assertEqual(original.read_bytes(), before)
        self.assertNotEqual(original.stat().st_ino, (out/'01.md').stat().st_ino)

    def test_approval_cannot_transfer_to_another_project(self):
        record = self.approved()
        other = self.root/'copy'
        shutil.copytree(self.base, other/'source/temp')
        with self.assertRaises(ValueError):
            validate_approval(build_report(other), record)

    def test_auto_explicit_and_same_cleaned_content(self):
        original = (self.base/'_translated_chunks/01.md').read_text()
        strip(self.root, mode='auto')
        self.assertEqual((self.base/'_translated_chunks_clean/01.md').read_text(), strip_term_markers_text(original))
        with self.assertRaises(ValueError):
            strip(self.root, output_dir=self.base/'_chunks', mode='auto')

    def test_repeated_key_pairing_does_not_jump_to_nearest_global_index(self):
        source = _extract_markers('【X｜X】 【Y｜Y】 First 【A｜甲】. Second 【A｜甲】.')
        target = _extract_markers('First 【第一甲｜甲】. 【X｜X】 【Y｜Y】 Second 【第二甲｜甲】.')
        paired, modes, missing, extra = _pair_markers(source, target)
        self.assertEqual(paired[2], 0)
        self.assertEqual(paired[3], 3)
        self.assertFalse(missing or extra)
        self.assertTrue(all(v == 'exact' for v in modes.values()))

    def test_duplicate_count_mismatch_marks_remaining_alignment_unknown(self):
        self.put('01', '【damage｜伤害】 and 【harm｜伤害】.', '【损伤｜伤害】。')
        report = build_report(self.root)
        self.assertEqual(report['stats']['structural_anomalies'], 1)
        self.assertEqual({d['kind'] for d in report['decisions']}, {'structural', 'alignment_unknown'})

    def test_contextual_override_does_not_poison_baseline_labels(self):
        self.put('01', 'Thresholds: 【Thresholds｜伤害阈值】. Lower by 1 【threshold｜伤害阈值】. Next: 【Thresholds｜伤害阈值】.',
                 '阈值：【伤害阈值｜伤害阈值】。降低 1 【级｜伤害阈值】。下一项：【伤害阈值｜伤害阈值】。')
        report = build_report(self.root)
        self.assertEqual(report['stats']['structural_anomalies'], 0)
        self.assertEqual(report['review_stats']['baseline_matches'], 2)
        self.assertEqual(len(report['decisions']), 1)
        self.assertEqual(report['decisions'][0]['kind'], 'string_difference')
        self.assertEqual(report['decisions'][0]['original'], 'threshold')
        self.assertIn('Lower by 1 threshold.', report['decisions'][0]['source_context'])
        self.assertIn('降低 1 级。', report['decisions'][0]['translated_context'])

    def test_queue_no_truncation_and_accepted_are_auditable(self):
        for i in range(2, 62):
            self.put(str(i), f'Clear {i} 【HP｜生命点】.', f'恢复 {i} 【生命值｜生命点】。')
        report = build_report(self.root)
        write_queue(report, self.root)
        text = (self.base/'_term_decision_queue.md').read_text()
        self.assertEqual(text.count('## d-'), 61)
        self.approved()
        report = build_report(self.root)
        write_queue(report, self.root)
        self.assertEqual(report['review_stats']['unresolved_decisions'], 0)
        self.assertEqual(len(report['decisions']), 61)


if __name__ == '__main__':
    unittest.main()
