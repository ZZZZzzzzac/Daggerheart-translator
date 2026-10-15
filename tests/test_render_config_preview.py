"""Synthetic offline HTML adapter regressions; no real translation artifacts."""
import copy
import base64
import hashlib
from html.parser import HTMLParser
import importlib.util
import json
import re
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

try:
    from lxml import html as lxml_html
except ImportError:
    lxml_html = None

from test_config_preview import m as preview
from test_pbres_names import ROOT, fixture, m as names
from test_pbres_bindings import config as name_config
from test_quantity_risks import config, gate, q, records

SCRIPT = ROOT / 'experiments/context_contract/render_config_preview.py'
spec = importlib.util.spec_from_file_location('render_config_preview', SCRIPT)
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)


def draft():
    resources = fixture()
    resources['resources'][0]['data']['特性'] = [
        dict(特性名称='无畏', 特性原文='Fearless', 特性描述='描述')]
    sources, translations = records(
        '# Guardian\n\n**Fearless:** Fearless costs 2 Stress, then gain 2 Hope.',
        '# **守护者**\n\n说明。\n\n**无畏 - 反应：** 无畏标记二压力点，再获得3希望点。')
    saved = preview.preview(resources, sources, translations, resource_id='r1', unit_id='s')
    return preview.draft(resources, sources, translations, saved,
                         name_selections=[(0, 0), (2, 2, ' - 反应')], quantity_selections=[(1, 2)])


def scan(source='🦊 **2** then [2](https://example.org/99 "2").', translation='🦊 **二**，再标记3压力点。'):
    sources, translations = records(source, translation)
    return q.scan(sources, translations, config(), gate.parse_commonmark_ast)


def combined(name='守护者', quantity='2', *, with_names=True, with_quantities=True):
    resources = fixture()
    sources, translations = records('# Guardian\n\nMark 2 Stress.', '#' + (' ' + name if name else '') +
                                    '\n\n标记' + quantity + '压力点。')
    options = {}
    if with_names:
        options['bindings'] = name_config()
    if with_quantities:
        options['quantity_scopes'] = config({'kind': 'block', 'block': 1}, {'kind': 'block', 'block': 1})
    return names.check(resources, names.extract(resources), sources, translations, **options)


class StaticReader(HTMLParser):
    """Read the delivered static nodes without executing any JavaScript."""
    def __init__(self, output):
        super().__init__(convert_charrefs=True)
        self.sides, self.current, self.mark = [], None, None
        self.feed(output)

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if attrs.get('data-side') in ('original', 'translation'):
            self.current = {'side': attrs['data-side'], 'text': '', 'marks': []}
        elif self.current is not None and tag == 'mark':
            self.mark = {'start': len(self.current['text']), 'reason': attrs['title']}

    def handle_data(self, data):
        if self.current is not None:
            self.current['text'] += data

    def handle_endtag(self, tag):
        if self.current is not None and tag == 'mark':
            self.mark['end'] = len(self.current['text'])
            self.mark['text'] = self.current['text'][self.mark['start']:self.mark['end']]
            self.current['marks'].append(self.mark)
            self.mark = None
        elif self.current is not None and tag == 'div':
            self.sides.append(self.current)
            self.current = None


class OfflineReportTests(unittest.TestCase):
    def test_combined_name_failure_and_quantity_match_both_remain_visible(self):
        data = combined(name='游侠')
        before = copy.deepcopy(data)
        report = m.to_report(data)
        self.assertEqual(len(report['findings']), 3)
        overview, name, quantity = report['findings']
        self.assertIn('阻止交付', overview['title'])
        self.assertIn('阻止交付', report['progressNotice'])
        self.assertIn('bound_name_mismatch', name['problem'])
        self.assertIn('守护者', name['problem'])
        self.assertEqual(name['translation'], '游侠')
        self.assertEqual(name['original'], '')
        self.assertEqual(name['original_highlights'], [])
        self.assertEqual(name['translation_highlights'], [])
        self.assertIn('证据缺口', name['problem'])
        self.assertIn('语义未核对', quantity['title'])
        self.assertEqual([h['text'] for h in quantity['translation_highlights']], ['2'])
        self.assertIn('bound_name_mismatch', m.render(data).split('<script id="report-data"', 1)[0])
        self.assertEqual(data, before)

    def test_combined_reverse_both_fail_and_both_without_blockers(self):
        for name_bad, quantity_bad in ((False, True), (True, True), (False, False)):
            data = combined(name='游侠' if name_bad else '守护者', quantity='3' if quantity_bad else '2')
            report = m.to_report(data)
            overview, name, quantity = report['findings']
            self.assertEqual('bound_name_mismatch' in name['problem'], name_bad)
            self.assertEqual('quantity_sequence_difference' in quantity['problem'], quantity_bad)
            self.assertEqual('阻止交付' in overview['title'], name_bad or quantity_bad)
            self.assertTrue(all(f['status'] == 'uncertain' for f in report['findings']))
            if not name_bad:
                self.assertIn('不等于语义通过', overview['problem'])

    def test_name_only_failure_and_empty_actual_have_explicit_evidence_gaps(self):
        data = combined(name='', with_quantities=False)
        report = m.to_report(data)
        self.assertEqual(len(report['findings']), 2)
        self.assertIn('数量检查：未提供', report['sourceDescription'])
        name = report['findings'][1]
        self.assertEqual(name['original'], '')
        self.assertEqual(name['translation'], '')
        self.assertIn('空字符串', name['problem'])
        self.assertIn('bound_name_mismatch', name['problem'])
        self.assertFalse(name['translation_highlights'])
        self.assertIn('阻止交付', m.render(data))

    def test_no_optional_checks_and_base_blockers_are_not_treated_as_checks_passed(self):
        for bad in (False, True):
            data = combined(with_names=False, with_quantities=False)
            if bad:
                data['release_allowed'] = False
                data['identity_errors'] = ['source/translation identity mismatch']
                data['units'][0]['findings'] = [{'kind': 'missing_original_dice_expression', 'text': 'd6', 'count': 2}]
            report = m.to_report(data)
            self.assertIn('名称检查：未提供', report['sourceDescription'])
            self.assertIn('数量检查：未提供', report['sourceDescription'])
            self.assertEqual('阻止交付' in report['progressNotice'], bad)
            if bad:
                self.assertEqual(len(report['findings']), 3)
                self.assertIn('identity mismatch', report['findings'][1]['problem'])
                self.assertIn('"count":2', report['findings'][2]['problem'])
                self.assertTrue(all(not row['original_highlights'] and not row['translation_highlights']
                                    for row in report['findings']))

    def test_name_configuration_errors_and_selector_failures_remain_visible(self):
        data = combined(with_quantities=False)
        data['release_allowed'] = False
        data['name_binding_check'] = {'release_allowed': False, 'configuration_errors': ['bad parent'], 'bindings': []}
        report = m.to_report(data)
        self.assertIn('名称配置错误', report['findings'][1]['title'])
        self.assertIn('bad parent', report['findings'][1]['problem'])
        data = combined(with_quantities=False)
        row = data['name_binding_check']['bindings'][0]
        del row['actual']
        row['findings'] = [{'kind': 'bound_name_selector_failed', 'text': 'selected slot unavailable'}]
        data['name_binding_check']['release_allowed'] = data['release_allowed'] = False
        finding = m.to_report(data)['findings'][1]
        self.assertIn('未提供，不能补造', finding['problem'])
        self.assertIn('bound_name_selector_failed', finding['problem'])

    def test_combined_statuses_are_preserved_not_recomputed_or_inferred(self):
        data = combined(name='游侠')
        data['release_allowed'] = True  # Deliberately inconsistent saved envelope.
        report = m.to_report(data)
        self.assertIn('状态矛盾', report['progressNotice'])
        self.assertIn('release_allowed：true', report['findings'][0]['problem'])
        del data['release_allowed']
        self.assertIn('总门禁状态缺失', m.to_report(data)['progressNotice'])
        for key in ('name_binding_check', 'quantity_risk_check'):
            bad = combined(); bad[key] = None
            with self.assertRaises(ValueError):
                m.render(bad)
        with self.assertRaises(ValueError):
            m.render({'release_allowed': True})

    def test_combined_name_text_is_escaped_in_static_and_interactive_payloads(self):
        data = combined(name='游侠')
        attack = '</script><img src="https://invalid.test" onerror="alert(1)">'
        row = data['name_binding_check']['bindings'][0]
        row['expected'] = row['actual'] = row['findings'][0]['text'] = attack
        output = m.render(data)
        self.assertNotIn('<img', output)
        self.assertIn('&lt;img', output)
        self.assertEqual(StaticReader(output).sides[3]['text'], attack)

    def test_static_html_rejects_nul_in_displayed_text_instead_of_replacing_it(self):
        sources, translations = records()
        sources[0]['quantity_fields'] = {'v': '2\x00 then 2'}
        translations['units'][0]['quantity_fields'] = {'v': '二点再二点'}
        cfg = config({'kind': 'field', 'pointer': '/quantity_fields/v'},
                     {'kind': 'field', 'pointer': '/quantity_fields/v'})
        data = q.scan(sources, translations, cfg, gate.parse_commonmark_ast)
        with self.assertRaisesRegex(ValueError, 'NUL'):
            m.render(data)
        with self.assertRaisesRegex(ValueError, 'NUL'):
            m._static_text('2', [{'start': 0, 'end': 1, 'reason': 'bad\x00reason'}])

    @unittest.skipUnless(lxml_html is not None, 'optional lxml HTML tokenizer regression')
    def test_static_html_tokenizer_preserves_crlf_cr_and_unicode_offsets(self):
        source = '🧑‍🚀 e\u0301 2\r\nthen 2\r'
        target = '🧑‍🚀 e\u0301 二点\r\n再标记3点\r'
        sources, translations = records()
        sources[0]['quantity_fields'] = {'v': source}
        translations['units'][0]['quantity_fields'] = {'v': target}
        cfg = config({'kind': 'field', 'pointer': '/quantity_fields/v'},
                     {'kind': 'field', 'pointer': '/quantity_fields/v'})
        data = q.scan(sources, translations, cfg, gate.parse_commonmark_ast)
        output = m.render(data)
        parsed = lxml_html.fromstring(output)
        sides = parsed.xpath('//*[@data-side]')
        self.assertEqual([el.text_content() for el in sides], [source, target])
        for el, side in zip(sides, ('source', 'translation')):
            self.assertEqual([mark.text_content() for mark in el.xpath('.//mark')],
                             [token['quote'] for token in data['scopes'][0][side]['tokens']])
        self.assertIn('&#13;\n', output)
        self.assertNotIn('\r', output)

    def test_no_javascript_static_text_and_exact_marks_cover_every_entry(self):
        for data in (draft(), scan()):
            expected = m.to_report(data)['findings']
            output = m.render(data)
            actual = StaticReader(output).sides
            self.assertEqual(len(actual), 2 * len(expected))
            for index, finding in enumerate(expected):
                for j, side in enumerate(('original', 'translation')):
                    self.assertEqual(actual[index * 2 + j]['text'], finding[side])
                    self.assertEqual(actual[index * 2 + j]['marks'], finding[side + '_highlights'])
            self.assertIn('<main id="app" hidden>', output)
            self.assertIn('全部条目已在下方显示，无需 JavaScript', output)
            self.assertIn('脚本成功启动后', output)

    def test_no_javascript_escaping_in_text_mark_reason_and_empty_state(self):
        hostile = '🦊 <script>alert(1)</script> & <img src="//invalid.test">'
        marked = m._static_text(hostile, [{'start': 2, 'end': len(hostile), 'reason': '\" onmouseover=\"alert(2)'}])
        self.assertNotIn('<script>', marked)
        self.assertNotIn('<img', marked)
        parsed = StaticReader('<div data-side="original">' + marked + '</div>').sides[0]
        self.assertEqual(parsed['text'], hostile)
        self.assertEqual(parsed['marks'][0]['reason'], '\" onmouseover=\"alert(2)')
        sources, translations = records()
        empty = q.scan(sources, translations, {'version': q.VERSION, 'scopes': []}, gate.parse_commonmark_ast)
        output = m.render(empty)
        static = output.split('<div id="static-review"', 1)[1].split('<main id="app"', 1)[0]
        self.assertIn('空队列不等于审核通过', static)

    def test_progressive_initialization_and_state_in_simulated_dom(self):
        with tempfile.TemporaryDirectory() as folder:
            output = Path(folder) / 'report.html'
            for data in (draft(), combined(name='游侠')):
                output.write_text(m.render(data), encoding='utf-8')
                result = subprocess.run(['node', str(ROOT / 'tests/test_config_preview_ui.js'), str(output)],
                                        capture_output=True, text=True)
                self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_csp_hashes_cover_final_enhanced_script_and_static_styles(self):
        output = m.render(draft())
        policy = re.search(r'http-equiv="Content-Security-Policy" content="([^"]+)"', output)[1]
        for tag in ('script', 'style'):
            for text in re.findall('<' + tag + '>(.*?)</' + tag + '>', output, re.S):
                digest = base64.b64encode(hashlib.sha256(text.encode('utf-8')).digest()).decode('ascii')
                self.assertIn("'sha256-" + digest + "'", policy)

    def test_quantity_reports_have_precise_repeated_codepoint_highlights(self):
        source = '🦊 **2** then [2](https://example.org/99 "2").'
        data = scan(source)
        before = copy.deepcopy(data)
        report = m.to_report(data)
        f = report['findings'][0]
        self.assertEqual(f['original'], '🦊 2 then 2.')
        self.assertEqual([(h['start'], h['end']) for h in f['original_highlights']], [(2, 3), (9, 10)])
        self.assertEqual([h['text'] for h in f['original_highlights']], ['2', '2'])
        self.assertEqual(f['related_contexts'][0]['original'], source)
        self.assertEqual(f['status'], 'uncertain')
        self.assertEqual(data, before)
        self.assertIn('extracted_text', f['problem'])

    def test_explicit_block_uses_extracted_scope_not_raw_markdown_or_first_same_word(self):
        sources, translations = records('2 before.\n\n🦊 **2** selected.', '前面2点。\n\n🦊 **三**点。')
        cfg = config({'kind': 'block', 'block': 1}, {'kind': 'block', 'block': 1})
        f = m.to_report(q.scan(sources, translations, cfg, gate.parse_commonmark_ast))['findings'][0]
        self.assertEqual(f['original'], '🦊 2 selected.')
        self.assertEqual(f['original_highlights'][0]['start'], 2)
        self.assertIn('"block":1', f['location'])
        self.assertIn('/0/source', f['problem'])
        self.assertIn('/blocks/1', f['problem'])
        self.assertNotIn('before', f['original'])

    def test_stale_wrong_basis_and_overlapping_evidence_are_rejected(self):
        original = scan()
        for mutation in ('quote', 'offset', 'basis', 'overlap', 'boolean', 'side', 'unit'):
            data = copy.deepcopy(original)
            side = data['scopes'][0]['source']
            token = side['tokens'][0]
            if mutation == 'quote': token['quote'] = 'wrong'
            elif mutation == 'offset': token['start'] = 0
            elif mutation == 'basis': side['offset_basis'] = 'raw Markdown'
            elif mutation == 'overlap': side['tokens'].append(copy.deepcopy(token))
            elif mutation == 'boolean': token['start'] = True
            elif mutation == 'side': side['side'] = 'translation'
            else: side['unit_id'] = 'other'
            with self.subTest(mutation=mutation), self.assertRaises(ValueError):
                m.render(data)

    def test_uncertain_numeric_forms_are_retained_and_matching_stays_unverified(self):
        f = m.to_report(scan('🦊 ½ and 2', '🦊 ½和二点'))['findings'][0]
        self.assertEqual([h['text'] for h in f['original_highlights']], ['½', '2'])
        self.assertIn('不确定', f['original_highlights'][0]['reason'])
        f = m.to_report(scan('Mark 2 Stress.', '标记二压力点。'))['findings'][0]
        self.assertIn('表面相同', f['title'])
        self.assertEqual(f['status'], 'uncertain')
        self.assertIn('不能证明', f['problem'])

    def test_unavailable_side_keeps_available_highlights_and_location(self):
        f = m.to_report(scan('`2`', '标记3压力点。'))['findings'][0]
        self.assertEqual(f['original'], '')
        self.assertEqual(f['original_highlights'], [])
        self.assertEqual([h['text'] for h in f['translation_highlights']], ['3'])
        self.assertIn('source 无法提取', f['problem'])
        self.assertIn('/0/source', f['problem'])

    def test_empty_and_invalid_config_never_claim_approval(self):
        sources, translations = records()
        empty = q.scan(sources, translations, {'version': q.VERSION, 'scopes': []}, gate.parse_commonmark_ast)
        report = m.to_report(empty)
        self.assertFalse(report['findings'])
        self.assertIn('空队列不等于审核通过', report['emptyMessage'])
        invalid = q.scan(sources, translations, None, gate.parse_commonmark_ast)
        self.assertIn('配置错误', m.to_report(invalid)['findings'][0]['title'])

    def test_wrapper_accepts_existing_scan_output(self):
        sources, translations = records()
        data = gate.scan_records(sources, translations, quantity_scopes=config())
        report = m.to_report(data)
        self.assertEqual(len(report['findings']), 2)
        self.assertIn('完整检查报告', report['findings'][0]['title'])
        self.assertIn('数量', report['findings'][1]['title'])

    def test_draft_names_use_exact_selected_slot_and_no_source_inference(self):
        data = draft()
        before = copy.deepcopy(data)
        report = m.to_report(data)
        first, feature, quantity = report['findings']
        self.assertEqual([h['text'] for h in first['translation_highlights']], ['守护者'])
        self.assertEqual(feature['original_highlights'], [])
        self.assertIn('未指定原文名称位置', feature['problem'])
        self.assertEqual(feature['translation'], '无畏 - 反应： 无畏标记二压力点，再获得3希望点。')
        self.assertEqual(feature['translation_highlights'], [
            {'start': 0, 'end': 2, 'text': '无畏', 'reason': '人工选中的名称槽位；身份未确认'}])
        self.assertIn('/data/特性/0/特性名称', feature['problem'])
        self.assertIn('/blocks/2', feature['location'])
        self.assertEqual(quantity['original_highlights'][0]['text'], quantity['original'])
        self.assertIn('未运行数字比较', quantity['problem'])
        self.assertIn('不批准配置', report['progressNotice'])
        self.assertEqual(before, data)

    def test_draft_tampering_or_approval_is_not_silently_rendered(self):
        for mutation in ('preview', 'name', 'quantity', 'parent', 'approved'):
            data = draft()
            if mutation == 'preview': data['preview']['sides']['source']['raw_text'] += '!'
            elif mutation == 'name': data['proposed_name_bindings'][0]['observed_name'] = 'wrong'
            elif mutation == 'quantity': data['proposed_quantity_scopes'][0]['translation']['text'] = 'wrong'
            elif mutation == 'parent': data['proposed_parent']['resource_id'] = 'wrong'
            else: data['approval_status'] = 'approved'
            with self.subTest(mutation=mutation), self.assertRaises(ValueError):
                m.render(data)

    def test_plain_field_malicious_html_and_escaped_text_stay_inert(self):
        attack = '🦊 2 </script><img src="https://invalid.test/x" onerror="alert(1)"> & __JS__'
        sources, translations = records()
        sources[0]['quantity_fields'] = {'v': attack}
        translations['units'][0]['quantity_fields'] = {'v': '二点 <script>alert(2)</script>'}
        cfg = config({'kind': 'field', 'pointer': '/quantity_fields/v'},
                     {'kind': 'field', 'pointer': '/quantity_fields/v'})
        data = q.scan(sources, translations, cfg, gate.parse_commonmark_ast)
        rendered = m.render(data)
        payload = json.loads(re.search(r'<script id="report-data" type="application/json">(.*?)</script>', rendered, re.S)[1])
        self.assertEqual(payload['findings'][0]['original'], attack)
        self.assertNotIn('<img', rendered)
        self.assertNotIn('<script>alert', rendered)
        self.assertIn('\\u003c/script\\u003e', rendered)
        self.assertIn('Content-Security-Policy', rendered)
        self.assertIn("default-src 'none'", rendered)
        self.assertIn("connect-src 'none'", rendered)
        self.assertIn("script-src 'sha256-", rendered)
        self.assertNotIn("'unsafe-inline'", rendered)

    def test_deterministic_and_no_numeric_recheck(self):
        data = draft()
        # Prepared report rendering does not load the scanner at all.
        saved = scan()
        with patch.object(q, 'scan', side_effect=AssertionError('no recheck')):
            self.assertEqual(m.render(saved), m.render(copy.deepcopy(saved)))
        self.assertEqual(m.render(data), m.render(copy.deepcopy(data)))

    def test_cli_preserves_input_and_refuses_existing_output_or_duplicate_json(self):
        with tempfile.TemporaryDirectory() as folder:
            source, output = Path(folder) / 'draft.json', Path(folder) / 'report.html'
            source.write_text(json.dumps(draft(), ensure_ascii=False), encoding='utf-8')
            before = source.read_bytes()
            result = subprocess.run([sys.executable, str(SCRIPT), str(source), str(output)], capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertTrue(output.read_text().startswith('<!doctype html>'))
            self.assertEqual(source.read_bytes(), before)
            first = output.read_bytes()
            result = subprocess.run([sys.executable, str(SCRIPT), str(source), str(output)], capture_output=True, text=True)
            self.assertEqual(result.returncode, 2)
            self.assertEqual(output.read_bytes(), first)
            result = subprocess.run([sys.executable, str(SCRIPT), str(source), str(source)], capture_output=True, text=True)
            self.assertEqual(result.returncode, 2)
            self.assertEqual(source.read_bytes(), before)
            source.write_text('{"x": 1, "x": 2}')
            result = subprocess.run([sys.executable, str(SCRIPT), str(source), str(Path(folder) / 'bad.html')], capture_output=True, text=True)
            self.assertEqual(result.returncode, 2)
            self.assertIn('duplicate', result.stderr)


if __name__ == '__main__':
    unittest.main()
