import copy
import importlib.util
import unittest
from pathlib import Path
from urllib.parse import parse_qs, urlparse

spec = importlib.util.spec_from_file_location('audit_data', Path(__file__).resolve().parents[1] / 'scripts/audit_data.py')
a = importlib.util.module_from_spec(spec)
spec.loader.exec_module(a)


class FakeAPI:
    def __init__(self, count=3):
        self.files = [{'id': 12, 'name': 'synthetic.json', 'total': count, 'modifiedAt': 't1'}]
        self.rows = [dict(id=i, fileId=12, key=f'item-{i}', original='Lose 2 Hope.',
                          translation='失去1希望点。', version=1) for i in range(count)]
        self.requests = []
        self.page_hook = lambda body: body
        self.file_reads = 0
        self.change_files = False

    def __call__(self, path):
        self.requests.append(path)
        if path == '/files':
            self.file_reads += 1
            fs = copy.deepcopy(self.files)
            if self.change_files and self.file_reads > 1:
                fs[0]['modifiedAt'] = 't2'
            return fs
        q = parse_qs(urlparse(path).query)
        page, size = int(q['page'][0]), int(q['pageSize'][0])
        body = dict(page=page, pageSize=size, rowCount=len(self.rows),
                    pageCount=(len(self.rows) + size - 1) // size,
                    results=copy.deepcopy(self.rows[(page - 1) * size:page * size]))
        return self.page_hook(body)


class AuditDataTests(unittest.TestCase):
    def snapshot(self, api=None):
        return a.capture(api or FakeAPI(), 'example-project', [12], 2)

    def audit(self):
        s = self.snapshot()
        return dict(schema_version=1, snapshot=s, findings=[], coverage=[dict(
            id=r['id'], scope='in_scope', reviewed=True, reviewer='reader-a',
            reviewed_at='2026-01-01T00:00:00Z', snapshot_version=1, record_sha256=a.digest(r)) for r in s['records']])

    def finding(self):
        return dict(finding_id='EXAMPLE-001', id=0, title='资源数量', status='confirmed',
                    severity='high', kind='translation', problem='2被误译为1', suggestion='失去2希望点。',
                    original='Lose 2 Hope.', translation='失去1希望点。', snapshot_version=1,
                    record_sha256=a.digest(self.snapshot()['records'][0]),
                    url='https://paratranz.cn/projects/1/strings?id=0',
                    second_pass=dict(reviewer='reader-b', decision='support', reason='数值改变效果'))

    def test_all_pages_and_digest(self):
        api = FakeAPI(); s = self.snapshot(api)
        self.assertEqual(len(s['records']), 3)
        self.assertEqual([p['rows'] for p in s['pages']], [2, 1])
        self.assertEqual(len(a.index(s)), 3)
        self.assertFalse(s['atomic'])

    def test_empty_file(self):
        self.assertEqual(self.snapshot(FakeAPI(0))['record_count'], 0)

    def test_duplicate_page_rejected(self):
        api = FakeAPI(); api.rows[2]['id'] = 0
        with self.assertRaisesRegex(ValueError, 'duplicate'): self.snapshot(api)

    def test_truncated_page_rejected(self):
        api = FakeAPI(); api.page_hook = lambda b: {**b, 'results': b['results'][:1]}
        with self.assertRaisesRegex(ValueError, 'Incomplete'): self.snapshot(api)

    def test_changed_file_rejected(self):
        api = FakeAPI(); api.change_files = True
        with self.assertRaisesRegex(ValueError, 'changed during'): self.snapshot(api)

    def test_changed_page_count_rejected(self):
        api = FakeAPI(); api.page_hook = lambda b: {**b, 'pageCount': 3 if b['page'] == 2 else 2}
        with self.assertRaisesRegex(ValueError, 'Page count changed'): self.snapshot(api)

    def test_missing_file_rejected(self):
        with self.assertRaisesRegex(ValueError, 'missing'): a.capture(FakeAPI(), 'p', [99])

    def test_wrong_file_rejected(self):
        api = FakeAPI(); api.rows[0]['fileId'] = 99
        with self.assertRaisesRegex(ValueError, 'Wrong file'): self.snapshot(api)

    def test_tampered_hash_rejected(self):
        s = self.snapshot(); s['records'][0]['translation'] = 'tampered'
        with self.assertRaisesRegex(ValueError, 'hash'): a.index(s)

    def test_delta_tracks_added_removed_changed_without_resolving(self):
        before = self.snapshot(); api = FakeAPI()
        api.rows[0]['id'] = 99; api.rows[1]['translation'] = '更新'; api.rows[2]['version'] = 2
        d = a.delta(before, self.snapshot(api))
        self.assertEqual(d['added'], [99]); self.assertEqual(d['removed'], [0])
        self.assertEqual(d['changed'], [{'id': 1, 'fields': ['translation']}, {'id': 2, 'fields': ['version']}])
        self.assertNotIn('resolved', d)

    def test_missing_coverage_rejected(self):
        data = self.audit(); data['coverage'].pop()
        with self.assertRaisesRegex(ValueError, 'every snapshot'): a.validate(data)

    def test_unreviewed_reported(self):
        data = self.audit(); data['coverage'][1]['reviewed'] = False
        self.assertEqual(a.validate(data)['unreviewed_ids'], [1])

    def test_partial_requires_specific_context(self):
        data = self.audit(); data['coverage'][0].update(scope='partial', reason='重复正文')
        with self.assertRaisesRegex(ValueError, 'included context'): a.validate(data)

    def test_counts_separate_findings_and_entries(self):
        data = self.audit(); f = self.finding(); g = {**f, 'finding_id': 'EXAMPLE-002'}
        data['findings'] = [f, g]; result = a.validate(data)
        self.assertEqual(result['findings']['confirmed'], 2)
        self.assertEqual(result['affected_entries']['confirmed'], 1)

    def test_confirmed_requires_independent_review(self):
        data = self.audit(); f = self.finding(); f['second_pass']['reviewer'] = 'reader-a'; data['findings'] = [f]
        with self.assertRaisesRegex(ValueError, 'independent'): a.validate(data)

    def test_stale_content_cannot_be_confirmed(self):
        data = self.audit(); f = self.finding(); f['translation'] = 'old'; data['findings'] = [f]
        with self.assertRaisesRegex(ValueError, 'text is stale'): a.validate(data)
        f['status'] = 'stale'; self.assertEqual(a.validate(data)['findings']['stale'], 1)

    def test_source_import_requires_official_evidence(self):
        data = self.audit(); f = self.finding(); f['kind'] = 'source_import'; data['findings'] = [f]
        with self.assertRaisesRegex(ValueError, 'official'): a.validate(data)

    def test_resolved_requires_readback(self):
        data = self.audit(); f = self.finding(); f['status'] = 'resolved'; data['findings'] = [f]
        with self.assertRaisesRegex(ValueError, 'readback'): a.validate(data)

    def test_snapshot_metadata_must_match_records(self):
        for mutation in ('schema', 'pages', 'total'):
            data = self.audit()
            if mutation == 'schema': data['snapshot']['schema_version'] = 999
            if mutation == 'pages': data['snapshot']['pages'] = []
            if mutation == 'total': data['snapshot']['files'][0]['total'] = 5000
            with self.assertRaises(ValueError): a.validate(data)

    def test_coverage_detects_content_change_without_version_change(self):
        data = self.audit(); data['snapshot']['records'][0]['context'] = 'changed'
        data['snapshot']['records_sha256'] = a.digest(data['snapshot']['records'])
        with self.assertRaisesRegex(ValueError, 'coverage record hash'): a.validate(data)

    def test_deleted_stale_history_with_delta_evidence(self):
        data = self.audit(); old = data['snapshot']; f = self.finding()
        api = FakeAPI(2); api.rows = api.rows[1:]; api.files[0]['total'] = 1
        latest = self.snapshot(api); data['snapshot'] = latest
        data['coverage'] = [c for c in data['coverage'] if c['id'] == 1]
        f['status'] = 'stale'
        f['removal_evidence'] = dict(removed_id=0, baseline_sha256=old['records_sha256'],
                                     latest_sha256=latest['records_sha256'])
        data['findings'] = [f]
        self.assertEqual(a.validate(data)['findings']['stale'], 1)

    def test_finding_detects_context_change_after_coverage_refresh(self):
        data = self.audit(); data['findings'] = [self.finding()]
        data['snapshot']['records'][0]['context'] = 'changed'
        data['snapshot']['records_sha256'] = a.digest(data['snapshot']['records'])
        data['coverage'][0]['record_sha256'] = a.digest(data['snapshot']['records'][0])
        with self.assertRaisesRegex(ValueError, 'Finding record hash'): a.validate(data)

    def test_highlights_use_code_points_and_allow_one_sided_omission(self):
        a.validate_highlights('A😀少一段', [dict(start=1, end=2, reason='emoji example')])
        a.validate_highlights('', [])
        data = self.audit(); f = self.finding()
        f['original_highlights'] = [dict(start=5, end=6, reason='数值不一致')]
        f['translation_highlights'] = []
        data['findings'] = [f]
        self.assertEqual(a.validate(data)['findings']['confirmed'], 1)

    def test_highlight_ranges_reject_invalid_evidence(self):
        bad = [None, {}, [None], [dict(start=True, end=2, reason='x')],
               [dict(start=0, end=1.5, reason='x')],
               [dict(start=-1, end=1, reason='x')],
               [dict(start=2, end=2, reason='x')],
               [dict(start=0, end=9, reason='x')],
               [dict(start=0, end=1, reason=' ')],
               [dict(start=2, end=3, reason='x'), dict(start=0, end=1, reason='x')],
               [dict(start=0, end=2, reason='x'), dict(start=1, end=3, reason='x')]]
        for spans in bad:
            with self.subTest(spans=spans), self.assertRaises(ValueError):
                a.validate_highlights('abc', spans)

    def test_finding_invalid_highlight_is_rejected(self):
        data = self.audit(); f = self.finding()
        f['translation_highlights'] = [dict(start=0, end=999, reason='bad offset')]
        data['findings'] = [f]
        with self.assertRaisesRegex(ValueError, 'outside full text'): a.validate(data)

    def test_highlight_text_assertion(self):
        a.validate_highlights('A😀B', [dict(start=1, end=2, reason='x', text='😀')])
        with self.assertRaisesRegex(ValueError, 'assertion'):
            a.validate_highlights('A😀B', [dict(start=1, end=2, reason='x', text='B')])

    def test_focus_ranges_reconstruct_selected_text(self):
        data = self.audit(); f = self.finding()
        f['original_focus_ranges'] = [dict(start=0, end=4), dict(start=7, end=11)]
        f['original_segments'] = ['Lose', 'Hope']
        f['original_focus'] = 'Lose\n\nHope'
        data['findings'] = [f]
        self.assertEqual(a.validate(data)['findings']['confirmed'], 1)
        f['original_focus'] = 'invented'
        with self.assertRaisesRegex(ValueError, 'reconstruct'): a.validate(data)

    def test_empty_focus_anchor_for_untranslated_side(self):
        a.validate_highlights('', [dict(start=0, end=0)], require_reason=False)
        with self.assertRaises(ValueError):
            a.validate_highlights('', [dict(start=0, end=0, reason='no invented evidence')])


if __name__ == '__main__':
    unittest.main()
