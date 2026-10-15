"""Synthetic name-slot tests. No real translation artifacts are modified."""
import copy
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from test_pbres_names import ROOT, fixture, m


def binding(pointer='/data/名称', *, unit='s', resource='r1', selector=None):
    return {'unit_id': unit, 'resource_id': resource, 'name_pointer': pointer,
            'selector': selector or {'kind': 'heading', 'block': 0, 'level': 1}}


def config(*rows):
    return {'version': 'pbres-name-bindings-v1',
            'unit_parents': [{'unit_id': 's', 'resource_id': 'r1'}],
            'bindings': list(rows or [binding()])}


class BindingTests(unittest.TestCase):
    def setUp(self):
        self.resources = fixture()
        self.resources['resources'][0]['data']['特性'] = [
            dict(特性名称='无畏', 特性原文='Fearless', 特性描述='描述'),
            dict(特性名称='坚定', 特性原文='Steadfast', 特性描述='描述')]
        self.sidecar = m.extract(self.resources)
        self.sources = [{'id': 's', 'source': '# Guardian\n\nGain 1 Hope.'}]
        self.translations = {'units': [{'id': 's', 'translation': '# 守护者\n\n获得 1 希望点。'}]}

    def check(self, text=None, bindings=None):
        if text is not None:
            self.translations['units'][0]['translation'] = text
        return m.check(self.resources, self.sidecar, self.sources, self.translations,
                       config() if bindings is None else bindings)

    def test_valid_heading_and_full_input_immutability(self):
        inputs = [self.resources, self.sidecar, self.sources, self.translations, config()]
        before = copy.deepcopy(inputs)
        result = m.check(*inputs)
        self.assertTrue(result['release_allowed'])
        self.assertEqual(inputs, before)
        self.assertEqual(result['name_binding_check']['bindings'][0]['actual'], '守护者')

    def test_wrong_missing_or_displaced_heading_blocks(self):
        for text in ['# 圣骑士', '获得 1 希望点。', '# \n\n获得 1 希望点。',
                     '获得 1 希望点。\n\n# 守护者', '# 守护者说明']:
            with self.subTest(text=text):
                result = self.check(text)
                self.assertFalse(result['release_allowed'])
                self.assertTrue(result['name_binding_check']['bindings'][0]['findings'])

    def test_commonmark_headings_and_emphasis(self):
        for text in ['# 守护者', '# **守护者**', '# *守护者*', '# **守*护*者**',
                     '守护者\n========', '# [守护者](#规则)', '# 守&#25252;者']:
            with self.subTest(text=text):
                self.assertTrue(self.check(text)['release_allowed'])

    def test_wrong_heading_level_and_nested_heading_block(self):
        for text in ['## 守护者', '> # 守护者', '- # 守护者']:
            self.assertFalse(self.check(text)['name_binding_check']['release_allowed'])

    def test_comments_code_html_image_and_link_targets_cannot_supply_name(self):
        for text in ['<!-- # 守护者 -->', '```\n# 守护者\n```', '    # 守护者',
                     '# `守护者`', '# <!-- 守护者 -->', '# <span>守护者</span>',
                     '# ![守护者](#图像)', '# [错误](#守护者)', '# [错误](#规则 "守护者")',
                     '# [错误][参考]\n\n[参考]: #守护者', '# 错误\n\n[守护者]: #目标']:
            with self.subTest(text=text):
                self.assertFalse(self.check(text)['name_binding_check']['release_allowed'])

    def test_unclosed_markup_does_not_fake_emphasis(self):
        self.assertFalse(self.check('# **守护者')['release_allowed'])
        cfg = config(binding('/data/特性/0/特性名称', selector={'kind': 'feature_label', 'block': 0}))
        self.assertFalse(self.check('**无畏：**描述', cfg)['name_binding_check']['release_allowed'])

    def test_explicit_feature_labels_supported(self):
        cfg = config(binding('/data/特性/0/特性名称', selector={'kind': 'feature_label', 'block': 0}))
        for text in ['**无畏：** 描述。', '**无畏**：描述。', '*无畏*：描述。',
                     '***无畏***: 描述。', '**无畏:** 描述。', '**[无畏](#特性)**：描述。']:
            with self.subTest(text=text):
                self.assertTrue(self.check(text, cfg)['release_allowed'])

    def test_wrong_missing_and_nonlabel_feature_names_block(self):
        cfg = config(binding('/data/特性/0/特性名称', selector={'kind': 'feature_label', 'block': 0}))
        for text in ['**坚定**：描述。', '**无畏** 描述。', '无畏：描述。',
                     '**`无畏`**：描述。', '**<!-- 无畏 -->**：描述。',
                     '描述。**无畏**：描述。', '- **无畏**：描述。']:
            self.assertFalse(self.check(text, cfg)['name_binding_check']['release_allowed'])

    def test_typed_feature_label_requires_its_explicit_literal_suffix(self):
        cfg = config(binding('/data/特性/0/特性名称', selector={
            'kind': 'feature_label', 'block': 0, 'suffix': ' - 反应'}))
        for text in ['**无畏 - 反应：** 描述。', '**无畏 - 反应**：描述。']:
            self.assertTrue(self.check(text, cfg)['release_allowed'])
        for text in ['**坚定 - 反应：** 描述。', '**无畏 - 动作：** 描述。', '**无畏：** 描述。']:
            self.assertFalse(self.check(text, cfg)['name_binding_check']['release_allowed'])
        del cfg['bindings'][0]['selector']['suffix']
        self.assertFalse(self.check('**无畏 - 反应：** 描述。', cfg)['name_binding_check']['release_allowed'])

    def test_main_and_feature_slots_are_independently_checked(self):
        cfg = config(binding(), binding('/data/特性/0/特性名称',
                                       selector={'kind': 'feature_label', 'block': 1}))
        self.assertTrue(self.check('# 守护者\n\n**无畏**：描述。', cfg)['release_allowed'])
        result = self.check('# 守护者\n\n**坚定**：描述。', cfg)
        self.assertFalse(result['release_allowed'])
        self.assertFalse(result['name_binding_check']['bindings'][0]['findings'])
        self.assertTrue(result['name_binding_check']['bindings'][1]['findings'])

    def test_no_bindings_preserves_existing_behavior_and_unbound_prose(self):
        self.translations['units'][0]['translation'] = '获得 1 希望点。'
        result = m.check(self.resources, self.sidecar, self.sources, self.translations)
        self.assertTrue(result['release_allowed'])
        self.assertNotIn('name_binding_check', result)
        self.sources.append({'id': 'prose', 'source': 'Guardian rests.'})
        self.translations['units'] = [{'id': 's', 'translation': '# 守护者'},
                                      {'id': 'prose', 'translation': '你休息。'}]
        self.assertTrue(self.check()['release_allowed'])

    def test_parent_association_required_and_wrong_parent_rejected(self):
        second = copy.deepcopy(self.resources['resources'][0]); second['id'] = 'r2'
        self.resources['resources'].append(second); self.sidecar = m.extract(self.resources)
        for cfg in [config(binding(resource='r2')), dict(config(), unit_parents=[])]:
            result = self.check(bindings=cfg)
            self.assertFalse(result['release_allowed'])
            self.assertTrue(result['name_binding_check']['configuration_errors'])

    def test_homonyms_keep_resource_identity_but_do_not_prove_attribution(self):
        second = copy.deepcopy(self.resources['resources'][0]); second['id'] = 'r2'
        self.resources['resources'].append(second); self.sidecar = m.extract(self.resources)
        self.sources.append({'id': 's2', 'source': '# Guardian'})
        self.translations['units'].append({'id': 's2', 'translation': '# 守护者'})
        cfg = config(binding(), binding(unit='s2', resource='r2'))
        cfg['unit_parents'].append({'unit_id': 's2', 'resource_id': 'r2'})
        result = self.check(bindings=cfg)
        self.assertTrue(result['release_allowed'])
        self.assertEqual([row['resource_id'] for row in result['name_binding_check']['bindings']], ['r1', 'r2'])
        # A consistently wrong human declaration cannot be disproved from text.
        cfg['unit_parents'][0]['resource_id'] = 'r2'
        cfg['bindings'][0]['resource_id'] = 'r2'
        self.assertTrue(self.check(bindings=cfg)['release_allowed'])

    def test_same_resource_repeated_name_pointers_do_not_collapse(self):
        self.resources['resources'][0]['data']['特性'][1]['特性名称'] = '无畏'
        self.sidecar = m.extract(self.resources)
        cfg = config(*[binding(f'/data/特性/{index}/特性名称',
                               selector={'kind': 'feature_label', 'block': index}) for index in range(2)])
        result = self.check('**无畏**：描述。\n\n**无畏**：描述。', cfg)
        self.assertTrue(result['release_allowed'])
        self.assertNotEqual(*[row['name_pointer'] for row in result['name_binding_check']['bindings']])

    def test_standalone_structured_plain_fields_and_pointer_escaping(self):
        self.translations['units'][0]['name_fields'] = {'主名': '守护者', '特性': ['无畏'], 'a/b': {'~': '坚定'}}
        cfg = config(binding(selector={'kind': 'field', 'pointer': '/name_fields/主名'}),
                     binding('/data/特性/0/特性名称', selector={'kind': 'field', 'pointer': '/name_fields/特性/0'}),
                     binding('/data/特性/1/特性名称', selector={'kind': 'field', 'pointer': '/name_fields/a~1b/~0'}))
        self.assertTrue(self.check(bindings=cfg)['release_allowed'])
        self.translations['units'][0]['name_fields']['主名'] = '圣骑士'
        self.assertFalse(self.check(bindings=cfg)['release_allowed'])

    def test_field_missing_empty_wrong_type_markup_and_noncanonical_array_index(self):
        cfg = config(binding(selector={'kind': 'field', 'pointer': '/name_fields/主名'}))
        for fields in [{}, {'主名': ''}, {'主名': ['守护者']}, {'主名': '**守护者**'}, {'主名': '<!-- 守护者 -->'}]:
            self.translations['units'][0]['name_fields'] = fields
            self.assertFalse(self.check(bindings=cfg)['release_allowed'])
        self.translations['units'][0]['name_fields'] = ['守护者']
        for index in ['00', '-1', '-', '1']:
            cfg['bindings'][0]['selector']['pointer'] = '/name_fields/' + index
            self.assertFalse(self.check(bindings=cfg)['release_allowed'])

    def test_malformed_configuration_fails_closed_separately_from_text(self):
        malformed = [None, [], {}, dict(config(), extra=1), dict(config(), version='unknown'),
                     dict(config(), bindings=None), dict(config(), unit_parents={})]
        for key, value in [('unit_id', []), ('resource_id', None), ('name_pointer', '/data/原文'),
                           ('name_pointer', '/data/特性/00/特性名称'), ('selector', None)]:
            cfg = config(); cfg['bindings'][0][key] = value; malformed.append(cfg)
        for selector in [{'kind': []}, {'kind': 'regex', 'pattern': '守护者'},
                         {'kind': 'heading', 'block': True, 'level': 1},
                         {'kind': 'heading', 'block': -1, 'level': 1},
                         {'kind': 'heading', 'block': 0, 'level': False},
                         {'kind': 'heading', 'block': 0, 'level': 7},
                         {'kind': 'heading', 'block': 0, 'level': 1, 'extra': 1},
                         {'kind': 'feature_label', 'block': 0, 'suffix': ''},
                         {'kind': 'feature_label', 'block': 0, 'suffix': []},
                         {'kind': 'field', 'pointer': '/translation'},
                         {'kind': 'field', 'pointer': '/name_fields'},
                         {'kind': 'field', 'pointer': '/name_fields/~2'}]:
            cfg = config(); cfg['bindings'][0]['selector'] = selector; malformed.append(cfg)
        for cfg in malformed:
            with self.subTest(config=cfg):
                result = m.check(self.resources, self.sidecar, self.sources, self.translations, cfg)
                self.assertFalse(result['release_allowed'])
                self.assertTrue(result['name_binding_check']['configuration_errors'])

    def test_unknown_and_duplicate_parents_and_targets_rejected(self):
        configs = []
        for parent in [{'unit_id': 'unknown', 'resource_id': 'r1'},
                       {'unit_id': 's', 'resource_id': 'unknown'}]:
            cfg = config(); cfg['unit_parents'] = [parent]; configs.append(cfg)
        cfg = config(); cfg['unit_parents'] *= 2; configs.append(cfg)
        cfg = config(); cfg['bindings'] *= 2; configs.append(cfg)
        cfg = config(binding(), binding('/data/特性/0/特性名称')); configs.append(cfg)
        cfg = config(binding(), binding('/data/特性/0/特性名称', selector={'kind': 'feature_label', 'block': 0})); configs.append(cfg)
        for cfg in configs:
            self.assertTrue(self.check(bindings=cfg)['name_binding_check']['configuration_errors'])

    def test_duplicate_or_missing_records_block(self):
        for records in [[], self.translations['units'] * 2, None, [None]]:
            self.translations = {'units': records}
            result = self.check()
            self.assertFalse(result['release_allowed'])
            self.assertTrue(result['name_binding_check']['bindings'][0]['findings'])

    def test_source_duplicates_and_missing_ids_are_configuration_errors(self):
        for sources in [self.sources * 2, [{'id': 's'}], [{'id': '', 'source': ''}]]:
            self.sources = sources
            self.assertTrue(self.check()['name_binding_check']['configuration_errors'])

    def test_sidecar_integrity_still_precedes_name_check(self):
        self.sidecar['rows'][0]['translation'] = '圣骑士'
        with self.assertRaisesRegex(ValueError, 'sidecar differs'):
            self.check('# 圣骑士')

    def test_dice_links_and_english_not_exempted_by_binding(self):
        self.sources = [{'id': 's', 'source': '# Guardian\n\nRoll d6. [Rules](#rules)'}]
        for text in ['# 守护者\n\n掷 d8。见[规则](#rules)。',
                     '# 守护者\n\n掷 d6。', '# 守护者\n\nGuardian 掷 d6。见[规则](#rules)。']:
            self.assertFalse(self.check(text)['release_allowed'])

    def test_parser_failure_is_a_blocker(self):
        gate = m.gate_module()
        with patch.object(m, 'gate_module', return_value=gate), patch.object(gate.shutil, 'which', return_value=None):
            result = self.check()
            self.assertFalse(result['release_allowed'])
            self.assertTrue(result['name_binding_check']['bindings'][0]['findings'])

    def test_malformed_ast_is_a_selector_finding(self):
        module = m.binding_module()
        for ast in [None, {}, {'blocks': [None]}, {'blocks': [{'t': 'Header', 'c': []}]},
                    {'blocks': [{'t': 'Header', 'c': [1, [], [{'t': 'Strong', 'c': None}]]}]}]:
            result = module.scan(self.sidecar, self.translations, config(), lambda _: ast)
            self.assertFalse(result['release_allowed'])
            self.assertEqual(result['bindings'][0]['findings'][0]['kind'], 'bound_name_selector_failed')

    def make_run(self, run, text='# 守护者\n\n获得 1 希望点。', bindings=None):
        m.prepare(self.sources, self.resources, run, config() if bindings is None else bindings)
        draft = {'units': [{'id': 's', 'translation': text, 'invariants': [
            {'id': 'i', 'source_quote': 'Gain 1 Hope', 'meaning': '获得1希望点'}],
            'protected_phrases': [], 'questions': []}]}
        final = {'units': [{'id': 's', 'translation': text, 'invariant_checks': [
            {'invariant_id': 'i', 'source_quote': 'Gain 1 Hope', 'target_quote': '获得 1 希望点', 'verdict': 'preserved'}],
            'phrase_exceptions': [], 'changes': [], 'ambiguity_checks': [
            {'source_quote': 'Gain 1 Hope', 'target_quote': '获得 1 希望点', 'verdict': 'no_new_ambiguity'}], 'questions': []}]}
        m.write(run / 'candidate-draft.json', draft)
        m.polish(run, development=True)
        m.write(run / 'candidate-final.json', final)

    def test_prepare_binds_configuration_and_refinement_guidance(self):
        with tempfile.TemporaryDirectory() as tmp:
            run = Path(tmp) / 'run'; self.make_run(run)
            manifest = m.read(run / 'manifest.json')
            self.assertEqual(manifest['name_bindings'], 'name-bindings.json')
            self.assertIn('name-bindings.json', manifest['prepared_files'])
            self.assertIn('experiments/context_contract/pbres_bindings.py', manifest['rules'])
            for name in ['phase1-generate.txt', 'baseline-generate.txt', 'two-pass-packet.json', 'phase2-polish.txt']:
                self.assertIn('名称绑定', (run / name).read_text())
            self.assertTrue(m.gate_module().release(run, development=True)['release_allowed'])

    def test_prepare_rejects_bad_configuration_and_fields_before_creating_run(self):
        bad = [None, config(binding(resource='wrong')),
               config(binding(selector={'kind': 'field', 'pointer': '/name_fields/主名'}))]
        for cfg in bad:
            with tempfile.TemporaryDirectory() as tmp:
                run = Path(tmp) / 'run'
                with self.assertRaises(ValueError):
                    m.prepare(self.sources, self.resources, run, cfg)
                self.assertFalse(run.exists())

    def test_release_enforces_name_check_after_basic_gate_success_and_preserves_bytes(self):
        with tempfile.TemporaryDirectory() as tmp:
            run = Path(tmp) / 'run'; self.make_run(run, '# 圣骑士\n\n获得 1 希望点。')
            before = (run / 'candidate-final.json').read_bytes()
            gate = m.gate_module()
            self.assertTrue(gate.scan_records(self.sources, m.read(run / 'candidate-final.json'))['release_allowed'])
            m.write(run / 'delivery-gate.json', {'release_allowed': True})
            result = gate.release(run, development=True)
            self.assertFalse(result['release_allowed'])
            self.assertFalse(m.read(run / 'delivery-gate.json')['release_allowed'])
            self.assertEqual((run / 'candidate-final.json').read_bytes(), before)
            self.assertTrue(any(row.get('name_pointer') and row['findings'] for row in result['findings']['candidate']))

    def test_prepared_bindings_tamper_removal_and_marker_omission_block(self):
        for mutation in ['tamper', 'remove', 'marker', 'registration', 'combined', 'combined_rule']:
            with self.subTest(mutation=mutation), tempfile.TemporaryDirectory() as tmp:
                run = Path(tmp) / 'run'; self.make_run(run)
                gate = m.gate_module()
                self.assertTrue(gate.release(run, development=True)['release_allowed'])
                if mutation == 'tamper':
                    cfg = config(); cfg['bindings'][0]['selector']['block'] = 1
                    m.write(run / 'name-bindings.json', cfg)
                elif mutation == 'remove':
                    (run / 'name-bindings.json').unlink()
                else:
                    manifest = m.read(run / 'manifest.json')
                    if mutation == 'marker': del manifest['name_bindings']
                    elif mutation == 'registration': del manifest['prepared_files']['name-bindings.json']
                    else:
                        (run / 'name-bindings.json').unlink()
                        del manifest['name_bindings']
                        del manifest['prepared_files']['name-bindings.json']
                        if mutation == 'combined_rule':
                            del manifest['rules']['experiments/context_contract/pbres_bindings.py']
                    m.write(run / 'manifest.json', manifest)
                with self.assertRaises((ValueError, FileNotFoundError)):
                    gate.release(run, development=True)
                self.assertFalse(m.read(run / 'delivery-gate.json')['release_allowed'])

    def test_cli_optional_bindings_exit_status_and_no_file_mutation(self):
        with tempfile.TemporaryDirectory() as tmp:
            folder = Path(tmp)
            values = [('resources', self.resources), ('sidecar', self.sidecar),
                      ('sources', self.sources), ('translations', self.translations), ('bindings', config())]
            for name, data in values:
                m.write(folder / (name + '.json'), data)
            cmd = [sys.executable, str(ROOT / 'experiments/context_contract/pbres_names.py'), 'check']
            cmd += [str(folder / (name + '.json')) for name, _ in values[:4]]
            cmd += ['--bindings', str(folder / 'bindings.json')]
            before = {p.name: p.read_bytes() for p in folder.iterdir()}
            result = subprocess.run(cmd, capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertTrue(json.loads(result.stdout)['release_allowed'])
            self.assertEqual(before, {p.name: p.read_bytes() for p in folder.iterdir()})
            self.translations['units'][0]['translation'] = '# 圣骑士'
            m.write(folder / 'translations.json', self.translations)
            result = subprocess.run(cmd, capture_output=True, text=True)
            self.assertEqual(result.returncode, 2)
            self.assertFalse(json.loads(result.stdout)['release_allowed'])
            cfg = config(); cfg['bindings'][0]['selector']['kind'] = 'regex'
            m.write(folder / 'bindings.json', cfg)
            result = subprocess.run(cmd, capture_output=True, text=True)
            self.assertEqual(result.returncode, 2)
            self.assertTrue(json.loads(result.stdout)['name_binding_check']['configuration_errors'])
            result = subprocess.run(cmd[:-2], capture_output=True, text=True)
            self.assertEqual(result.returncode, 0)
            m.write(folder / 'bindings.json', None)
            result = subprocess.run(cmd, capture_output=True, text=True)
            self.assertEqual(result.returncode, 2)
            self.assertTrue(json.loads(result.stdout)['name_binding_check']['configuration_errors'])

    def test_duplicate_json_keys_not_silently_overwritten(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / 'bindings.json'
            path.write_text('{"version":"wrong","version":"pbres-name-bindings-v1"}')
            with self.assertRaisesRegex(ValueError, 'duplicate JSON object key'):
                m.read(path)


if __name__ == '__main__':
    unittest.main()
