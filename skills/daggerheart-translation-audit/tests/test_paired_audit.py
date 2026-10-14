"""Local paired-text review and evidence tests for the source-agnostic audit entry point."""
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

BASE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BASE / 'scripts'))
import paired_audit as audit
from render_report import render


def sample():
    return {'title': 'Generic audit', 'segments': [{'id': 'stable-key', 'original': 'Before cleaning.\n',
                                                   'translation': '清洁之后。\n', 'location': 'Cleaning'}]}


def normalized_input():
    return audit.normalize(sample())


def review_no_issue(snap):
    review = audit.prepare(snap)
    for entry in review['coverage']:
        entry.update(status='reviewed', alignment='verified', reviewer='Test semantic reviewer',
                     reviewedAt='2026-10-14T07:01:00+00:00', assessment='Test-only authored judgment.',
                     conclusion='no_issue')
    return review


def reviewed_finding(snap):
    review = review_no_issue(snap)
    entry = review['coverage'][0]
    entry.update(conclusion='findings', findingIds=['order-reversed'])
    review['findings'] = [{'finding_id': 'order-reversed', 'id': entry['id'],
                          'segmentSha256': entry['segmentSha256'], 'title': 'Wrong order',
                          'status': 'confirmed', 'severity': 'high', 'category': 'meaning',
                          'second_pass': {'reviewer': 'Independent test reviewer', 'decision': 'support', 'reason': 'Test-only independent assessment supports this finding.'},
                          'problem': 'Before was translated as after.', 'suggestion': 'Use 清洁之前。',
                          'original_highlights': [{'start': 0, 'end': 6, 'text': 'Before', 'reason': 'Before is a prerequisite.'}],
                          'translation_highlights': [{'start': 2, 'end': 4, 'text': '之后', 'reason': 'After reverses the order.'}]}]
    return review


class PairedAuditTests(unittest.TestCase):
    def assert_invalid(self, snap, review, text):
        with self.assertRaisesRegex(ValueError, text):
            audit.validate(snap, review)

    def test_plain_input_needs_no_capture_or_source_metadata(self):
        data = sample()
        data['segments'][0]['provenance'] = {'page': '7', 'paragraph': '2'}
        normalized = audit.normalize(data)
        self.assertEqual(normalized['type'], 'paired-audit-input')
        self.assertEqual(normalized['segments'][0]['provenance'], data['segments'][0]['provenance'])
        for key in ('inputSources', 'capturedAt', 'snapshotSha256'):
            self.assertNotIn(key, normalized)
        self.assertNotIn('originalSha256', normalized['segments'][0])
        report = audit.export_report(normalized, review_no_issue(normalized), 'plain-input')
        self.assertNotIn('sourceCutoff', report)
        self.assertEqual(report['inputSha256'], normalized['inputSha256'])

    def test_prepare_never_claims_review(self):
        snap = normalized_input()
        review = audit.prepare(snap)
        summary = audit.validate(snap, review)
        self.assertEqual(review['coverage'][0]['status'], 'unreviewed')
        self.assertEqual(review['coverage'][0]['alignment'], 'unverified')
        self.assertFalse(summary['completeReview'])
        self.assertEqual(summary['reviewedSegments'], 0)
        with self.assertRaisesRegex(ValueError, 'incomplete'):
            audit.export_report(snap, review, 'test')
        partial = audit.export_report(snap, review, 'test', allow_incomplete=True)
        self.assertEqual(partial['findings'], [])
        self.assertIn('not a clean audit', partial['emptyMessage'])
        self.assertIn('Partial report', partial['notes'])
        self.assertIn('test', render(partial))

    def test_complete_no_errors_has_no_fake_findings(self):
        data = sample()
        data['segments'][0]['translation'] = '清洁之前。\n'
        snap = audit.normalize(data)
        review = review_no_issue(snap)
        report = audit.export_report(snap, review, 'clean-audit')
        self.assertTrue(report['coverageSummary']['completeReview'])
        self.assertEqual(report['findings'], [])
        self.assertIn('completed semantic review', report['emptyMessage'])
        self.assertIn('clean-audit', render(report))

    def test_export_exact_text_without_provider_or_url(self):
        snap = normalized_input()
        report = audit.export_report(snap, reviewed_finding(snap), 'test')
        finding = report['findings'][0]
        self.assertNotIn('url', finding)
        self.assertNotIn('provider', finding)
        self.assertEqual(finding['original'], snap['segments'][0]['original'])
        self.assertEqual(finding['translation_focus'], '清洁之后。\n')
        self.assertEqual(finding['translation_focus_ranges'], [{'start': 0, 'end': 6}])
        self.assertIn('order-reversed', render(report))

    def test_input_missing_or_duplicate_ids(self):
        for bad_id in (None, '', 42, True):
            data = sample(); data['segments'][0]['id'] = bad_id
            with self.assertRaisesRegex(ValueError, 'string id'):
                audit.normalize(data)
        data = sample(); data['segments'] *= 2
        with self.assertRaisesRegex(ValueError, 'Duplicate segment'):
            audit.normalize(data)

    def test_explicit_missing_side_required(self):
        data = sample(); del data['segments'][0]['translation']
        with self.assertRaisesRegex(ValueError, 'explicit translation'):
            audit.normalize(data)
        data['segments'][0]['translation'] = ''
        self.assertEqual(audit.normalize(data)['segments'][0]['translation'], '')
        data['segments'][0]['original'] = ''
        with self.assertRaisesRegex(ValueError, 'both sides'):
            audit.normalize(data)

    def test_duplicate_or_missing_coverage_rejected(self):
        snap = normalized_input(); review = review_no_issue(snap)
        review['coverage'] *= 2
        self.assert_invalid(snap, review, 'Duplicate coverage')
        review['coverage'] = []
        self.assert_invalid(snap, review, 'every segment')

    def test_content_change_invalidates_review(self):
        snap = normalized_input(); review = reviewed_finding(snap)
        data = sample(); data['segments'][0]['translation'] = '清洁之前。\n'
        revised = audit.normalize(data)
        self.assert_invalid(revised, review, 'different paired input')
        review['inputSha256'] = revised['inputSha256']
        self.assert_invalid(revised, review, 'stale segment hash')
        review['coverage'][0]['segmentSha256'] = revised['segments'][0]['segmentSha256']
        self.assert_invalid(revised, review, 'stale finding segment hash')

    def test_metadata_or_alignment_change_requires_review(self):
        snap = normalized_input(); review = reviewed_finding(snap)
        data = sample(); data['segments'][0]['alignmentNote'] = 'Now paired against the next paragraph.'
        revised = audit.normalize(data)
        self.assert_invalid(revised, review, 'different paired input')

    def test_normalized_input_tamper_rejected(self):
        snap = normalized_input(); review = review_no_issue(snap)
        snap['segments'][0]['translation'] += '!'
        self.assert_invalid(snap, review, 'stale segment hash')
        snap = normalized_input(); snap['inputSha256'] = '0' * 64
        self.assert_invalid(snap, review, 'collection hash')

    def test_claiming_review_requires_authored_fields(self):
        snap = normalized_input()
        for field, value in [('reviewer', ''), ('reviewedAt', '2026-10-14'), ('assessment', ''), ('alignment', 'unverified')]:
            review = reviewed_finding(snap); review['coverage'][0][field] = value
            self.assert_invalid(snap, review, 'reviewer|timezone|assessment|alignment')

    def test_unresolved_alignment_cannot_be_confirmed_or_complete(self):
        snap = normalized_input(); review = reviewed_finding(snap)
        review['coverage'][0].update(alignment='unresolved', conclusion='uncertain')
        self.assert_invalid(snap, review, 'cannot support a confirmed')
        review['findings'][0]['status'] = 'uncertain'
        summary = audit.validate(snap, review)
        self.assertFalse(summary['completeReview'])
        self.assertEqual(summary['unresolvedAlignmentIds'], ['stable-key'])

    def test_exclusion_requires_scope_trace_and_is_not_semantic_review(self):
        snap = normalized_input(); review = audit.prepare(snap)
        review['coverage'][0]['status'] = 'excluded'
        self.assert_invalid(snap, review, 'exclusion needs')
        review['coverage'][0]['reason'] = 'Outside the authorized review scope.'
        self.assert_invalid(snap, review, 'scopeEvidence')
        review['coverage'][0].update(excludedBy='User scope instruction', scopeEvidence='User asked to review only the setup section.')
        summary = audit.validate(snap, review)
        self.assertFalse(summary['completeReview'])
        self.assertEqual(summary['excludedIds'], ['stable-key'])

    def test_authorized_exclusion_allows_complete_in_scope_review(self):
        data = sample()
        data['segments'].append({'id': 'excluded-appendix', 'original': 'Appendix', 'translation': '附录'})
        snap = audit.normalize(data); review = review_no_issue(snap)
        review['coverage'][1].update(status='excluded', alignment='unverified', conclusion='',
                                     reason='Appendix excluded by requested scope.', excludedBy='User',
                                     scopeEvidence='User request: review only the cleaning section.')
        summary = audit.validate(snap, review)
        self.assertTrue(summary['completeReview'])
        self.assertFalse(summary['allInputReviewed'])
        report = audit.export_report(snap, review, 'scoped-report')
        self.assertIn('Excluded segments are not reviewed', report['notes'])
        self.assertIn('in-scope', report['emptyMessage'])

    def test_confirmed_requires_independent_support(self):
        snap = normalized_input(); review = reviewed_finding(snap)
        del review['findings'][0]['second_pass']
        self.assert_invalid(snap, review, 'independent supporting')
        review = reviewed_finding(snap)
        review['findings'][0]['second_pass']['reviewer'] = review['coverage'][0]['reviewer']
        self.assert_invalid(snap, review, 'different from first')
        review = reviewed_finding(snap)
        review['findings'][0]['second_pass']['decision'] = 'reject'
        self.assert_invalid(snap, review, 'independent supporting')

    def test_unreviewed_findings_rejected(self):
        snap = normalized_input(); review = reviewed_finding(snap)
        review['coverage'][0].update(status='unreviewed', alignment='unverified', conclusion='', findingIds=[])
        self.assert_invalid(snap, review, 'lacks an actual semantic review')

    def test_findings_and_coverage_must_agree(self):
        snap = normalized_input(); review = reviewed_finding(snap)
        review['coverage'][0]['findingIds'] = []
        self.assert_invalid(snap, review, 'do not match')
        review = reviewed_finding(snap); review['coverage'][0]['conclusion'] = 'no_issue'
        self.assert_invalid(snap, review, 'no_issue')
        review = reviewed_finding(snap); review['findings'] *= 2
        self.assert_invalid(snap, review, 'duplicate finding_id')

    def test_evidence_and_focus_are_precise(self):
        snap = normalized_input()
        for field, value in [('text', 'After'), ('reason', ''), ('start', True), ('end', 1000)]:
            review = reviewed_finding(snap)
            review['findings'][0]['original_highlights'][0][field] = value
            self.assert_invalid(snap, review, 'exact source slice|reason|integers|outside exact')
        review = reviewed_finding(snap)
        review['findings'][0]['original_focus_ranges'] = [{'start': 7, 'end': 15}]
        self.assert_invalid(snap, review, 'include every evidence')
        review = reviewed_finding(snap)
        review['findings'][0]['original_highlights'] *= 2
        self.assert_invalid(snap, review, 'non-overlapping')

    def test_unlocalized_missing_text_does_not_need_fake_highlight(self):
        snap = normalized_input(); review = reviewed_finding(snap)
        finding = review['findings'][0]
        finding['translation_highlights'] = []
        self.assert_invalid(snap, review, 'explain why translation')
        finding['translation_absence_reason'] = 'Only a missing sentence is wrong; existing target text is not highlighted.'
        self.assertTrue(audit.validate(snap, review)['completeReview'])

    def test_invalid_domains_or_stale_optional_text(self):
        snap = normalized_input()
        for field, value in [('status', 'resolved'), ('severity', 'catastrophic'), ('category', 'game_rule'), ('original', 'Different')]:
            review = reviewed_finding(snap); review['findings'][0][field] = value
            self.assert_invalid(snap, review, 'invalid|stale')

    def test_unicode_crlf_and_repeated_occurrences_preserved(self):
        data = sample(); row = data['segments'][0]
        row['original'] = '🐈\r\nSame. Same.\r\n'
        row['translation'] = '🐈\r\n同。同。\r\n'
        snap = audit.normalize(data)
        self.assertEqual(snap['segments'][0]['original'], row['original'])
        review = reviewed_finding(snap); f = review['findings'][0]
        f['original_highlights'] = [{'start': 9, 'end': 13, 'text': 'Same', 'reason': 'Second occurrence is the selected evidence.'}]
        f['translation_highlights'] = [{'start': 5, 'end': 6, 'text': '同', 'reason': 'Second occurrence.'}]
        f['original_focus_ranges'] = [{'start': 9, 'end': 14}]
        f['translation_focus_ranges'] = [{'start': 5, 'end': 7}]
        report = audit.export_report(snap, review, 'unicode')
        self.assertEqual(report['findings'][0]['original_focus'], 'Same.')
        self.assertIn('unicode', render(report))

    def test_malformed_and_duplicate_key_json(self):
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / 'bad.json'
            for text in ('{', '{"title":"a","title":"b"}', '{"bad":NaN}'):
                path.write_text(text)
                with self.assertRaises(ValueError):
                    audit.read_json(path)
        for data in ([], {}, {'title': 'x', 'segments': []}, {'title': 'x', 'segments': ['bad']}):
            with self.assertRaises(ValueError):
                audit.normalize(data)

    def test_urls_optional_but_safe(self):
        for url in ('http://example.com', 'javascript:alert(1)', 'https://user:secret@example.com'):
            data = sample(); data['segments'][0]['url'] = url
            with self.assertRaisesRegex(ValueError, 'HTTPS'):
                audit.normalize(data)
        data = sample(); data['segments'][0].update(url='https://example.com/manual', provider='Manual')
        snap = audit.normalize(data)
        report = audit.export_report(snap, reviewed_finding(snap), 'provider')
        self.assertEqual(report['findings'][0]['provider'], 'Manual')

    def test_local_file_cli_preserves_text_and_never_aligns_lines(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp); source, target = root/'source.txt', root/'target.txt'
            source.write_bytes(b'A\r\nB\r\n'); target.write_bytes('甲\n'.encode())
            out = root/'normalized_input.json'
            self.assertEqual(audit.main(['normalize', '--original-file', str(source), '--translation-file', str(target), '--out', str(out)]), 0)
            snap = audit.read_json(out)
            self.assertEqual(len(snap['segments']), 1)
            self.assertEqual(snap['segments'][0]['original'], 'A\r\nB\r\n')
            self.assertEqual(snap['segments'][0]['alignment']['method'], 'whole-document')
            self.assertNotIn('inputSources', snap)
            self.assertNotIn('capturedAt', snap)
            self.assertEqual(audit.main(['prepare', str(out), '--out', str(root/'review.json')]), 0)
            self.assertEqual(audit.main(['validate', str(out), str(root/'review.json')]), 1)
            self.assertEqual(audit.main(['normalize', '--original-text', 'x', '--translation-text', '', '--out', str(root/'empty.json')]), 0)
            # Explicit non-overwrite is deliberate evidence protection.
            self.assertEqual(audit.main(['normalize', '--original-text', 'x', '--translation-text', '', '--out', str(root/'empty.json')]), 2)

    def test_fixture_end_to_end_cli(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp); snap = root/'normalized_input.json'; report = root/'report.json'
            fixture = BASE/'examples/consumer-review.json'
            self.assertEqual(audit.main(['normalize', '--pairs', str(BASE/'examples/consumer-pairs.json'), '--out', str(snap)]), 0)
            self.assertEqual(audit.main(['validate', str(snap), str(fixture)]), 0)
            self.assertEqual(audit.main(['export', str(snap), str(fixture), '--report-id', 'consumer-synthetic', '--out', str(report)]), 0)
            output = root/'report.html'
            process = subprocess.run([sys.executable, str(BASE/'scripts/render_report.py'), str(report), str(output)], capture_output=True, text=True)
            self.assertEqual(process.returncode, 0, process.stderr)
            payload = audit.read_json(report)
            self.assertTrue(payload['coverageSummary']['completeReview'])
            self.assertEqual(payload['coverageSummary']['noIssueSegments'], 1)
            self.assertEqual(len(payload['findings']), 3)
            self.assertIn('missing-child-safety', output.read_text())
            self.assertEqual(payload['findings'][1]['translation_highlights'], [])

    def test_partial_report_exposes_unreviewed_ids_in_visible_notes(self):
        snap = audit.normalize(sample())
        report = audit.export_report(snap, audit.prepare(snap), 'partial-visible', allow_incomplete=True)
        self.assertIn('Unreviewed IDs:', report['notes'])
        for segment in snap['segments']:
            self.assertIn(segment['id'], report['notes'])


if __name__ == '__main__':
    unittest.main()
