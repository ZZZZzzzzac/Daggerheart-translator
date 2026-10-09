"""Synthetic-only handoff contract tests; these do not measure translation quality."""
import copy
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

SCRIPTS = Path(__file__).resolve().parents[1] / 'skills/daggerheart-term-checker/scripts'
sys.path.insert(0, str(SCRIPTS))
from check_terms import build_report
from export_human_review import SCHEMA, build_export, prepare, render_markdown
import export_human_review

SOURCE = '# Signal Lantern\n\nWhen a visitor gives a guide a 【token｜标记】, they may keep it until sunset.\n\nThe guide can repeat this once.\n'
CHINESE = '# 信号灯\n\n访客交给向导一枚【标记｜标记】时，TA可以保管到日落。\n\n向导可以重复一次。\n'
SOURCE_SENTENCE = 'When a visitor gives a guide a token, they may keep it until sunset.'
CHINESE_SENTENCE = '访客交给向导一枚标记时，TA可以保管到日落。'


def wrap(text):
    return '[[[KILO_TARGET_START]]]\n' + text + '[[[KILO_TARGET_END]]]\n'


class HumanReviewExportTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.project = Path(self.tmp.name)
        self.base = self.project / 'source/temp'
        for folder in ('_chunks', '_translated_chunks'):
            (self.base / folder).mkdir(parents=True)
        self.put('01', SOURCE, CHINESE)
        self.issue_file = self.base / '_term_semantic_issues.json'
        self.set_issues(['Who keeps the token?', 'What can be repeated?'])

    def put(self, chunk, source, chinese):
        (self.base / '_chunks' / (chunk + '.md')).write_text(wrap(source), encoding='utf-8')
        (self.base / '_translated_chunks' / (chunk + '.md')).write_text(wrap(chinese), encoding='utf-8')

    def set_issues(self, problems):
        self.issue_file.unlink(missing_ok=True)
        report = build_report(self.project)
        self.issue_file.write_text(json.dumps(dict(input_digest=report['input_digest'], issues=[
            dict(chunk='01', problem=p, source_context=SOURCE_SENTENCE, translated_context=CHINESE_SENTENCE)
            for p in problems]), ensure_ascii=False), encoding='utf-8')

    def payload(self):
        snapshot = prepare(self.project)
        src = next(r for r in snapshot['available_units'] if r['side'] == 'source' and r['chunk'] == '01')
        zh = next(r for r in snapshot['available_units'] if r['side'] == 'translation' and r['chunk'] == '01')
        return dict(schema_version=SCHEMA, input_digest=snapshot['input_digest'], review_digest=snapshot['review_digest'],
                    semantic_review=dict(completed=True, reviewer='AI:synthetic-test', reviewed_chunks=snapshot['required_chunks'],
                                         summary='Test-only attestation; no semantic quality claim.'),
                    questions=[dict(id='q-' + str(i), kind='translation_blocker', decision_ids=[d['id']], source=copy.deepcopy(src), translation=copy.deepcopy(zh),
                                    context=[copy.deepcopy(src)], context_complete=True,
                                    context_reason='The entire synthetic heading unit is included.', problem=d['problem'],
                                    options=[dict(id='A', text='保留当前译法，并按访客执行。'), dict(id='B', text='明确改为由向导执行。')],
                                    recommendation='A', reason='Synthetic recommendation for format testing only.')
                               for i, d in enumerate(snapshot['unresolved_decisions'], 1)])

    def test_two_questions_one_card_with_single_original_and_translation(self):
        value = build_export(self.project, self.payload())
        self.assertEqual(value['counts'], dict(independent_questions=2, cards=1, translation_blockers=2,
                                             optional_rule_rulings=0, unresolved_audit_decisions=2))
        md = render_markdown(value)
        self.assertEqual(md.count(SOURCE_SENTENCE), 1)
        self.assertEqual(md.count(CHINESE_SENTENCE), 1)
        self.assertIn('The guide can repeat this once.', md)
        self.assertIn('独立问题 2 个；卡片 1 张', md)
        self.assertIn('_chunks/01.md · TARGET:L1-L5', md)
        self.assertIn('不证明语义正确', md)
        self.assertIn('建议：A · 保留当前译法，并按访客执行。', md)

    def test_missing_required_fields_fail(self):
        for field in ('id', 'kind', 'decision_ids', 'source', 'translation', 'context', 'context_complete',
                      'context_reason', 'problem', 'options', 'recommendation', 'reason'):
            with self.subTest(field=field):
                payload = self.payload()
                del payload['questions'][0][field]
                with self.assertRaises(ValueError):
                    build_export(self.project, payload)

    def test_empty_context_and_fake_context_fail(self):
        for context in ([], None, [dict(self.payload()['questions'][0]['source'], text='Made-up surrounding prose.')]):
            payload = self.payload()
            payload['questions'][0]['context'] = context
            with self.assertRaises(ValueError):
                build_export(self.project, payload)

    def test_fake_source_or_chinese_fail_even_with_current_hashes(self):
        for field in ('source', 'translation'):
            with self.subTest(field=field):
                payload = self.payload()
                payload['questions'][0][field]['text'] += ' A paraphrase is not an original.'
                with self.assertRaisesRegex(ValueError, '真实文件'):
                    build_export(self.project, payload)

    def test_changed_source_or_translation_invalidates_input(self):
        for folder in ('_chunks', '_translated_chunks'):
            with self.subTest(folder=folder):
                payload = self.payload()
                path = self.base / folder / '01.md'
                original = path.read_bytes()
                path.write_bytes(original + b'\n')
                with self.assertRaises(ValueError):
                    build_export(self.project, payload)
                path.write_bytes(original)

    def test_changed_issue_content_invalidates_review_hash(self):
        payload = self.payload()
        self.set_issues(['A revised uncertainty', 'What can be repeated?'])
        with self.assertRaisesRegex(ValueError, 'review_digest'):
            build_export(self.project, payload)

    def test_duplicate_question_ids_decisions_or_same_doubt_fail(self):
        for mode in ('id', 'decision_ids', 'problem'):
            payload = self.payload()
            payload['questions'][1][mode] = copy.deepcopy(payload['questions'][0][mode])
            with self.subTest(mode=mode), self.assertRaisesRegex(ValueError, '重复'):
                build_export(self.project, payload)

    def test_missing_question_or_invented_zero_fail(self):
        for count in (0, 1):
            payload = self.payload()
            payload['questions'] = payload['questions'][:count]
            with self.assertRaisesRegex(ValueError, '遗漏'):
                build_export(self.project, payload)

    def test_whole_heading_unit_includes_all_paragraphs(self):
        payload = self.payload()
        src = payload['questions'][0]['source']
        src['end_line'] = 3
        src['text'] = '# Signal Lantern\n\n' + SOURCE_SENTENCE
        with self.assertRaisesRegex(ValueError, '完整 TARGET'):
            build_export(self.project, payload)

    def test_no_arbitrary_cap_or_silent_truncation(self):
        self.set_issues(['Synthetic independent field ' + str(i) for i in range(137)])
        value = build_export(self.project, self.payload())
        self.assertEqual(value['counts']['independent_questions'], 137)
        self.assertEqual(value['counts']['cards'], 1)
        md = render_markdown(value)
        self.assertEqual(md.count('### 问题 '), 137)
        self.assertIn('q-137', md)

    def test_full_review_attestation_is_required_and_exact(self):
        for update in ({'completed': False}, {'reviewer': ''}, {'summary': ''},
                       {'reviewed_chunks': []}, {'reviewed_chunks': ['01', '01']}):
            payload = self.payload()
            payload['semantic_review'].update(update)
            with self.subTest(update=update), self.assertRaises(ValueError):
                build_export(self.project, payload)

    def test_options_and_recommendation_are_real_and_distinct(self):
        for update in ({'options': []}, {'options': [{'id': 'A', 'text': 'A'}]},
                       {'options': [{'id': 'A', 'text': 'same'}, {'id': 'B', 'text': ' same '}]},
                       {'recommendation': 'C'}, {'reason': ' '}):
            payload = self.payload()
            payload['questions'][0].update(update)
            with self.subTest(update=update), self.assertRaises(ValueError):
                build_export(self.project, payload)

    def test_unknown_locator_and_wrong_unit_fail(self):
        self.put('01', SOURCE + '\n# Other Ability\n\nAnother visitor waits.\n',
                 CHINESE + '\n# 另一能力\n\n另一个访客等待。\n')
        self.set_issues(['Who keeps the token?'])
        payload = self.payload()
        snapshot = prepare(self.project)
        other = next(r for r in snapshot['available_units'] if r['side'] == 'source' and r['text'].startswith('# Other'))
        payload['questions'][0]['source'] = other
        with self.assertRaisesRegex(ValueError, '另一能力'):
            build_export(self.project, payload)
        payload = self.payload()
        payload['questions'][0]['source']['chunk'] = '../not-a-chunk'
        with self.assertRaisesRegex(ValueError, '未知'):
            build_export(self.project, payload)

    def test_marker_rendering_and_newlines_are_documented_and_exact(self):
        for folder in ('_chunks', '_translated_chunks'):
            path = self.base / folder / '01.md'
            path.write_bytes(path.read_bytes().replace(b'\n', b'\r\n'))
        self.set_issues(['Who keeps the token?'])
        value = build_export(self.project, self.payload())
        self.assertNotIn('【', value['cards'][0]['source']['text'])
        self.assertNotIn('\r', value['cards'][0]['translation']['text'])
        payload = self.payload()
        payload['questions'][0]['source']['text'] = payload['questions'][0]['source']['text'].replace('a visitor', 'a  visitor')
        with self.assertRaisesRegex(ValueError, '真实文件'):
            build_export(self.project, payload)

    def test_export_does_not_grant_approval_or_change_inputs(self):
        before = {str(p): p.read_bytes() for p in self.base.rglob('*') if p.is_file()}
        build_export(self.project, self.payload())
        after = {str(p): p.read_bytes() for p in self.base.rglob('*') if p.is_file()}
        self.assertEqual(before, after)
        self.assertFalse((self.base / '_term_review_approval.json').exists())

    def test_zero_is_only_attested_and_has_no_implicit_release(self):
        self.set_issues([])
        payload = self.payload()
        value = build_export(self.project, payload)
        self.assertEqual(value['counts']['independent_questions'], 0)
        self.assertIn('不是脚本证明译文无误', render_markdown(value))
        payload['semantic_review']['completed'] = False
        with self.assertRaises(ValueError):
            build_export(self.project, payload)

    def test_cli_prepare_export_and_invalid_input_no_new_cards(self):
        cmd = [sys.executable, str(SCRIPTS / 'export_human_review.py'), str(self.project)]
        subprocess.run(cmd + ['--prepare'], check=True, capture_output=True)
        self.assertTrue((self.base / '_human_review_inputs.json').exists())
        self.assertFalse((self.base / '_human_review_cards.md').exists())
        path = self.base / '_human_review.json'
        payload = self.payload()
        payload['questions'][0]['reason'] = ''
        path.write_text(json.dumps(payload), encoding='utf-8')
        self.assertEqual(subprocess.run(cmd, capture_output=True).returncode, 1)
        self.assertFalse((self.base / '_human_review_cards.md').exists())
        self.assertFalse((self.base / '_human_review_cards.json').exists())
        path.write_text(json.dumps(self.payload()), encoding='utf-8')
        subprocess.run(cmd, check=True, capture_output=True)
        self.assertTrue((self.base / '_human_review_cards.md').exists())

    def test_optional_rule_rulings_count_separately_across_two_cards(self):
        self.put('01', SOURCE + '\n# Blue Lamp\n\nThe lantern turns blue.\n',
                 CHINESE + '\n# 蓝灯\n\n灯变为蓝色。\n')
        self.set_issues(['Who keeps the token?', 'What can be repeated?'])
        data = json.loads(self.issue_file.read_text())
        data['issues'].append(dict(chunk='01', problem='Does it end immediately?',
                                   source_context='The lantern turns blue.', translated_context='灯变为蓝色。'))
        self.issue_file.write_text(json.dumps(data), encoding='utf-8')
        payload = self.payload()
        units = prepare(self.project)['available_units']
        for q in payload['questions']:
            q['kind'] = 'optional_rule_ruling'
            if q['problem'] == 'Does it end immediately?':
                q['source'] = next(r for r in units if r['side'] == 'source' and r['text'].startswith('# Blue'))
                q['translation'] = next(r for r in units if r['side'] == 'translation' and r['text'].startswith('# 蓝灯'))
                q['context'] = [q['source']]
        counts = build_export(self.project, payload)['counts']
        self.assertEqual((counts['translation_blockers'], counts['optional_rule_rulings'], counts['cards']), (0, 3, 2))
        self.assertEqual(counts['independent_questions'], 3)

    def test_final_freshness_rechecks_semantic_review_digest(self):
        payload = self.payload()
        original = export_human_review.build_report
        calls = 0
        def changed_report(project):
            nonlocal calls
            calls += 1
            if calls == 2:
                value = json.loads(self.issue_file.read_text())
                value['issues'][0]['problem'] += ' Changed while exporting.'
                self.issue_file.write_text(json.dumps(value), encoding='utf-8')
            return original(project)
        with patch.object(export_human_review, 'build_report', side_effect=changed_report):
            with self.assertRaisesRegex(ValueError, '审阅内容变化'):
                build_export(self.project, payload)

    def test_cli_rejects_duplicate_json_keys(self):
        payload = json.dumps(self.payload())
        payload = payload.replace('"questions":', '"questions": [], "questions":', 1)
        (self.base / '_human_review.json').write_text(payload, encoding='utf-8')
        cmd = [sys.executable, str(SCRIPTS / 'export_human_review.py'), str(self.project)]
        result = subprocess.run(cmd, capture_output=True, text=True)
        self.assertEqual(result.returncode, 1)
        self.assertIn('重复 JSON 字段', result.stderr)
        self.assertFalse((self.base / '_human_review_cards.md').exists())

    def test_atomic_outputs_do_not_follow_symlinks_or_mutate_hardlinks(self):
        source = self.base / '_chunks/01.md'
        chinese = self.base / '_translated_chunks/01.md'
        before = (source.read_bytes(), chinese.read_bytes())
        (self.base / '_human_review_cards.md').symlink_to(source)
        os.link(chinese, self.base / '_human_review_cards.json')
        (self.base / '_human_review_inputs.json').symlink_to(source)
        (self.base / '_human_review.json').write_text(json.dumps(self.payload()), encoding='utf-8')
        cmd = [sys.executable, str(SCRIPTS / 'export_human_review.py'), str(self.project)]
        subprocess.run(cmd + ['--prepare'], check=True, capture_output=True)
        subprocess.run(cmd, check=True, capture_output=True)
        self.assertEqual(before, (source.read_bytes(), chinese.read_bytes()))
        self.assertFalse((self.base / '_human_review_cards.md').is_symlink())


if __name__ == '__main__':
    unittest.main()
