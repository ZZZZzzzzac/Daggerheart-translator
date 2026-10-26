"""Presentation-only tests: no new glossary, pairing or approval mechanism."""
import contextlib
import io
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'skills/daggerheart-term-checker/scripts'))
import check_terms
from render_term_review import report_data, snapshot_inputs, render_html


def wrap(text):
    return '[[[KILO_TARGET_START]]]\n' + text + '\n[[[KILO_TARGET_END]]]\n'


class TermHtmlTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.project = Path(self.tmp.name)
        self.base = self.project / 'source/temp'
        for folder in ('_chunks', '_translated_chunks'):
            (self.base / folder).mkdir(parents=True)
        self.put('A 😀 【Hope｜希望】.\n\nAnother 【Hope｜希望】 after all conditions.',
                 '甲 😀 【希望｜希望】。\n\n全部条件之后另一个【希望｜希望】。')

    def put(self, source, translation):
        (self.base / '_chunks/01.md').write_text(wrap(source))
        (self.base / '_translated_chunks/01.md').write_text(wrap(translation))

    def run_report(self, expected_exit=None, **kwargs):
        with contextlib.redirect_stdout(io.StringIO()):
            if expected_exit is None:
                check_terms.main(str(self.project), **kwargs)
            else:
                with self.assertRaises(SystemExit) as caught:
                    check_terms.main(str(self.project), **kwargs)
                self.assertEqual(caught.exception.code, expected_exit)
        return json.loads((self.base / '_term_review_report.json').read_text())

    def test_defaults_keep_rows_and_full_context_with_precise_unicode_occurrences(self):
        report = self.run_report()
        self.assertEqual(report['stats']['total_rows'], 2)
        self.assertEqual(set(report['rows'][0]), {'chunk','index','original','recommended','current',
                         'adopted_recommendation','context','source_context','translated_context','note','anomalies'})
        data = report_data(report, snapshot_inputs(self.project))
        first, second = data['findings']
        self.assertIn('after all conditions.', first['original'])
        self.assertEqual(first['original'], second['original'])
        self.assertLess(first['original_highlights'][0]['start'], second['original_highlights'][0]['start'])
        h = second['original_highlights'][0]
        self.assertEqual(second['original'][h['start']:h['end']], 'Hope')
        self.assertTrue((self.base / '_term_review_report.html').exists())
        self.assertTrue((self.base / '_term_review_report.md').exists())
        self.assertFalse((self.base / '_term_review_approval.json').exists())
        self.assertFalse((self.base / '_translated_chunks_clean').exists())

    def test_identity_ignores_clock_but_invalidates_on_input_change(self):
        report = self.run_report(); snapshot = snapshot_inputs(self.project)
        first = report_data(report, snapshot)['reportId']
        report['checked_at'] = 'different'; report['project'] = '/another/path'
        self.assertEqual(first, report_data(report, snapshot)['reportId'])
        self.put('【Hope｜希望】 changed.', '【希望｜希望】变化。')
        self.assertNotEqual(first, report_data(self.run_report(), snapshot_inputs(self.project))['reportId'])

    def test_reordered_markers_use_unchanged_checker_pairing(self):
        self.put('【Hope｜希望】 and 【Fear｜恐惧】.', '【恐惧｜恐惧】与【希望｜希望】。')
        data = report_data(self.run_report(), snapshot_inputs(self.project))
        self.assertEqual(data['findings'][0]['translation_highlights'][0]['text'], '希望')
        self.assertEqual(data['findings'][1]['translation_highlights'][0]['text'], '恐惧')

    def test_structural_missing_extra_and_fallback_preserve_exit_and_display(self):
        cases = [('【Hope｜希望】', 'none'), ('none', '【希望｜希望】'),
                 ('【Hope｜希望】', '【希望｜变动】'), ('【 ｜希望】', '【希望｜希望】')]
        for source, translation in cases:
            with self.subTest(source=source, translation=translation):
                self.put(source, translation)
                # Whitespace source slot is existing main behavior, not newly classified.
                report = self.run_report(expected_exit=None if source.startswith('【 ') else 1)
                self.assertEqual(len(report_data(report, snapshot_inputs(self.project))['findings']), 1)
                self.assertTrue((self.base / '_term_review_report.html').exists())

    def test_missing_chunk_and_missing_target_do_not_invent_evidence(self):
        (self.base / '_translated_chunks/01.md').unlink()
        report = self.run_report(expected_exit=1)
        row = report_data(report, snapshot_inputs(self.project))['findings'][0]
        self.assertEqual(row['translation'], '')
        self.assertEqual(row['translation_highlights'], [])
        (self.base / '_translated_chunks/01.md').write_text('Actual file without wrapper.')
        report = self.run_report(expected_exit=1)
        self.assertEqual(report_data(report, snapshot_inputs(self.project))['findings'][0]['translation'], 'Actual file without wrapper.')

    def test_zero_rows_does_not_claim_approval(self):
        self.put('No terms.', '无术语。')
        report = self.run_report()
        data = report_data(report, snapshot_inputs(self.project))
        self.assertEqual(data['findings'], [])
        self.assertIn('不批准译文', render_html(report, snapshot_inputs(self.project)))

    def test_xss_and_output_links_are_safe(self):
        self.put('【Hope｜希望｜</script><img src=x onerror=alert(1)>】', '【希望｜希望｜</script><img src=x onerror=alert(1)>】')
        source = self.base / '_chunks/01.md'; before = source.read_bytes()
        target = self.base / '_term_review_report.html';
        try:
            target.symlink_to(source)
        except OSError as exc:
            if getattr(exc, 'winerror', None) == 1314: self.skipTest('Windows symlink privilege unavailable')
            raise
        self.run_report()
        self.assertEqual(source.read_bytes(), before)
        self.assertFalse(target.is_symlink())
        self.assertNotIn('</script><img', target.read_text())
        with self.assertRaisesRegex(ValueError, '覆盖'):
            self.run_report(html_output_path=str(source))
        self.assertEqual(source.read_bytes(), before)

    def test_html_output_cannot_replace_an_input_symlink_or_its_target(self):
        source = self.base / '_chunks/01.md'
        target = self.project / 'actual-source.md'
        source.rename(target)

        try:
            source.symlink_to(target)
        except OSError as exc:
            if getattr(exc, 'winerror', None) == 1314: self.skipTest('Windows symlink privilege unavailable')
            raise
        before = target.read_bytes()
        for destination in (source, target):
            with self.subTest(destination=destination), self.assertRaisesRegex(ValueError, '覆盖'):
                self.run_report(html_output_path=str(destination))
            self.assertTrue(source.is_symlink())
            self.assertEqual(source.read_bytes(), before)
            self.assertEqual(target.read_bytes(), before)
        self.assertFalse((self.base / '_term_review_report.html').exists())

    def test_existing_output_hardlink_is_replaced_without_changing_input(self):
        source = self.base / '_chunks/01.md'
        before = source.read_bytes()
        target = self.base / '_term_review_report.html'
        target.hardlink_to(source)
        self.assertEqual(source.stat().st_ino, target.stat().st_ino)
        self.run_report()
        self.assertEqual(source.read_bytes(), before)
        self.assertNotEqual(source.stat().st_ino, target.stat().st_ino)
        self.assertTrue(target.read_text().startswith('<!doctype html>'))

    def test_changed_inputs_during_check_fail_before_new_output(self):
        original = snapshot_inputs
        calls = 0
        def changed(project):
            nonlocal calls
            calls += 1
            if calls == 2:
                self.put('【Hope｜希望】 changed.', '【希望｜希望】变化。')
            return original(project)
        with patch('render_term_review.snapshot_inputs', changed), self.assertRaisesRegex(ValueError, '变化'):
            self.run_report()
        self.assertFalse((self.base / '_term_review_report.html').exists())

    def test_custom_html_output(self):
        path = self.project / 'review.html'
        self.run_report(html_output_path=str(path))
        self.assertTrue(path.exists())
        self.assertFalse((self.base / '_term_review_report.html').exists())


if __name__ == '__main__':
    unittest.main()
