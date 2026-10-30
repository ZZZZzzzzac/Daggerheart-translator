"""Synthetic offline preview/draft tests; no real translations or live configs."""
import copy
import importlib.util
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from test_pbres_names import ROOT, fixture, m as names

SCRIPT = ROOT / 'experiments/context_contract/config_preview.py'
spec = importlib.util.spec_from_file_location('config_preview', SCRIPT)
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)


class PreviewTests(unittest.TestCase):
    def setUp(self):
        self.resources = fixture()
        self.resources['resources'][0]['data']['希望特性']['特性名称'] = '不屈'
        self.resources['resources'][0]['data']['特性'] = [
            dict(特性名称='无畏', 特性原文='Fearless', 特性描述='描述'),
            dict(特性名称='无畏', 特性原文='', 特性描述='另一描述')]
        self.sources = [{'id': 's', 'source': '# Guardian\n\n- Mark 7 Stress.\n\n**Fearless:** Mark 2 Stress.'}]
        self.translations = {'units': [{'id': 's', 'translation':
                                      '# **守护者**\n\n说明。\n\n> 标记7压力点。\n\n**无畏 - 反应：** 标记二压力点。'}]}

    def preview(self, **options):
        return m.preview(self.resources, self.sources, self.translations,
                         **dict({'resource_id': 'r1', 'unit_id': 's'}, **options))

    def draft(self, preview=None, **options):
        return m.draft(self.resources, self.sources, self.translations,
                       self.preview() if preview is None else preview, **options)

    def test_actual_independent_indices_preserve_unsupported_blocks(self):
        preview = self.preview()
        source, target = [preview['sides'][key] for key in ('source', 'translation')]
        self.assertEqual([b['block'] for b in source['blocks']], [0, 1, 2])
        self.assertEqual([b['block'] for b in target['blocks']], [0, 1, 2, 3])
        self.assertEqual(source['blocks'][1]['node_type'], 'BulletList')
        self.assertEqual(target['blocks'][2]['node_type'], 'BlockQuote')
        self.assertNotIn('quantity_candidate', source['blocks'][1])
        self.assertNotIn('name_candidate', target['blocks'][2])
        self.assertEqual(target['blocks'][3]['name_candidate']['selector'],
                         {'kind': 'feature_label', 'block': 3})
        self.assertEqual(source['blocks'][2]['ast_path'], '/blocks/2')
        self.assertEqual(source['raw_text'], self.sources[0]['source'])
        self.assertEqual(target['record_pointer'], '/units/0')
        self.assertTrue(source['blocks'][1]['ast']['c'])

    def test_names_keep_pointer_identity_and_missing_original_status(self):
        choices = self.preview()['name_choices']
        self.assertEqual([row['choice'] for row in choices], [0, 1, 2, 3])
        self.assertEqual(choices[1]['status'], 'absent')
        self.assertEqual(choices[3]['status'], 'empty')
        self.assertEqual(choices[2]['translation'], choices[3]['translation'])
        self.assertNotEqual(choices[2]['name_pointer'], choices[3]['name_pointer'])
        self.assertTrue(all(row['resource_id'] == 'r1' for row in choices))

    def test_reduced_inputs_generate_combined_unconfirmed_draft(self):
        result = self.draft(name_selections=[(0, 0), (2, 3, ' - 反应')], quantity_selections=[(2, 3)])
        self.assertEqual(result['approval_status'], 'unconfirmed')
        self.assertFalse(result['semantic_verified'])
        self.assertEqual(result['proposed_parent'],
                         {'resource_id': 'r1', 'unit_id': 's', 'approval_status': 'unconfirmed'})
        first, feature = result['proposed_name_bindings']
        self.assertEqual(first['selector'], {'kind': 'heading', 'block': 0, 'level': 1})
        self.assertEqual(feature['name_pointer'], '/data/特性/0/特性名称')
        self.assertEqual(feature['observed_name'], '无畏')
        scope = result['proposed_quantity_scopes'][0]
        self.assertEqual(scope['unit_id'], 's')
        self.assertEqual(scope['source']['selector'], {'kind': 'block', 'block': 2})
        self.assertEqual(scope['translation']['selector'], {'kind': 'block', 'block': 3})
        self.assertIn('Mark 2 Stress.', scope['source']['text'])
        self.assertTrue(all(r['approval_status'] == 'unconfirmed' for r in [first, feature, scope]))
        self.assertNotIn('version', result)
        self.assertNotIn('bindings', result)
        self.assertNotIn('scopes', result)

    def test_no_automatic_alignment_or_numeric_check_or_approval(self):
        with patch.object(m.quantities, 'tokenize', side_effect=AssertionError('must not scan')), \
                patch.object(m.quantities, 'scan', side_effect=AssertionError('must not compare')), \
                patch.object(m.bindings, 'scan', side_effect=AssertionError('must not check')):
            preview = self.preview()
            self.assertNotIn('proposed_name_bindings', preview)
            with self.assertRaises(ValueError):
                self.draft(preview)
            # Structurally selectable but deliberately wrong name and alignment.
            result = self.draft(preview, name_selections=[(2, 0)], quantity_selections=[(2, 1)])
        binding = result['proposed_name_bindings'][0]
        self.assertNotEqual(binding['observed_name'], binding['expected_name'])
        self.assertEqual(result['approval_status'], 'unconfirmed')
        self.assertEqual(result['preview']['review_status'], {
            'parent_attribution': 'unconfirmed', 'alignment': 'unconfirmed', 'homonym_identity': 'unconfirmed'})
        self.assertNotIn('release_allowed', result)

    def test_homonym_resource_and_pointer_choices_never_approve_identity(self):
        second = copy.deepcopy(self.resources['resources'][0])
        second['id'] = 'other'
        self.resources['resources'].append(second)
        preview = self.preview(resource_id='other')
        result = self.draft(preview, name_selections=[(3, 3, ' - 反应')])
        row = result['proposed_name_bindings'][0]
        self.assertEqual(row['resource_id'], 'other')
        self.assertEqual(row['name_pointer'], '/data/特性/1/特性名称')
        self.assertEqual(row['expected_name'], row['observed_name'])
        self.assertEqual(row['approval_status'], 'unconfirmed')
        self.assertEqual(result['proposed_parent']['approval_status'], 'unconfirmed')

    def test_input_immutability_and_determinism(self):
        before = copy.deepcopy([self.resources, self.sources, self.translations])
        preview = self.preview()
        saved = copy.deepcopy(preview)
        first = self.draft(preview, name_selections=[(0, 0)], quantity_selections=[(2, 3)])
        second = self.draft(preview, name_selections=[(0, 0)], quantity_selections=[(2, 3)])
        self.assertEqual(json.dumps(first), json.dumps(second))
        self.assertEqual(preview, saved)
        self.assertEqual([self.resources, self.sources, self.translations], before)
        first['preview']['name_choices'][0]['translation'] = 'changed result'
        self.assertEqual(preview, saved)
        self.assertEqual([self.resources, self.sources, self.translations], before)

    def test_changed_structure_or_text_or_resource_requires_new_preview(self):
        for mutation in ('source_structure', 'target_structure', 'source_text', 'resource', 'unselected_unit'):
            with self.subTest(mutation=mutation):
                self.setUp()
                preview = self.preview()
                if mutation == 'source_structure':
                    self.sources[0]['source'] = 'Preface.\n\n' + self.sources[0]['source']
                elif mutation == 'target_structure':
                    self.translations['units'][0]['translation'] = '新增。\n\n' + self.translations['units'][0]['translation']
                elif mutation == 'source_text':
                    self.sources[0]['source'] = self.sources[0]['source'].replace('2', '3')
                elif mutation == 'resource':
                    self.resources['resources'][0]['data']['名称'] = '变更'
                else:
                    self.sources.append({'id': 'other', 'source': 'Unselected.'})
                with self.assertRaisesRegex(ValueError, 'stale or modified'):
                    self.draft(preview, name_selections=[(0, 0)])
                fresh = self.preview()
                self.assertEqual(fresh['approval_status'], 'unconfirmed')

    def test_modified_snapshot_parser_or_implementation_is_rejected(self):
        preview = self.preview()
        for field in ('approval_status', 'input_sha256', 'implementation_sha256', 'parser', 'blocks'):
            modified = copy.deepcopy(preview)
            if field == 'blocks':
                modified['sides']['source']['blocks'][1]['block'] = True
            else:
                modified[field] = 'tampered'
            with self.assertRaisesRegex(ValueError, 'stale or modified'):
                self.draft(modified, name_selections=[(0, 0)])
        with patch.object(m.gate, 'parser_identity', return_value={'version': 'changed'}):
            with self.assertRaisesRegex(ValueError, 'stale or modified'):
                self.draft(preview, name_selections=[(0, 0)])

    def test_unknown_missing_duplicate_ids_rejected(self):
        for options in ({'resource_id': 'missing'}, {'unit_id': 'missing'}, {'unit_id': ''}, {'resource_id': []}):
            with self.subTest(options=options), self.assertRaises(ValueError):
                self.preview(**options)
        for field in ('resources', 'sources', 'translations'):
            with self.subTest(field=field):
                self.setUp()
                records = self.resources['resources'] if field == 'resources' else \
                    self.sources if field == 'sources' else self.translations['units']
                records.append(copy.deepcopy(records[0]))
                with self.assertRaises(ValueError):
                    self.preview()
        self.setUp()
        self.translations['units'][0]['id'] = 'other'
        with self.assertRaisesRegex(ValueError, 'missing from translation'):
            self.preview()

    def test_bad_indices_unsupported_slots_and_duplicate_targets_rejected(self):
        preview = self.preview()
        for choices in [[(-1, 0)], [(True, 0)], [(0, False)], [(99, 0)], [(0, 99)],
                        [(0, 1)], [(0, 2)], [(0, 0), (2, 0)], [(0,)], [(0, 0, 'suffix')],
                        [(2, 3, '')], [(2, 3, ' - 动作')], [(2, 3, [])]]:
            with self.subTest(choices=choices), self.assertRaises(ValueError):
                self.draft(preview, name_selections=choices)
        for choices in [[(1, 3)], [(2, 2)], [(True, 3)], [(2, False)], [(2, 99)],
                        [(-1, 3)], [(2, 3), (2, 1)], [(2, 3), (0, 3)], [(2,)]]:
            with self.subTest(choices=choices), self.assertRaises(ValueError):
                self.draft(preview, quantity_selections=choices)

    def test_feature_suffix_is_never_inferred(self):
        row = self.draft(name_selections=[(2, 3)])['proposed_name_bindings'][0]
        self.assertEqual(row['observed_name'], '无畏 - 反应')
        self.assertNotIn('suffix', row['selector'])
        self.assertEqual(row['approval_status'], 'unconfirmed')

    def test_malformed_selection_containers_are_rejected(self):
        preview = self.preview()
        for invalid in [None, 1, True, {}, '0 0']:
            for option in ['name_selections', 'quantity_selections']:
                with self.subTest(option=option, invalid=invalid), self.assertRaises(ValueError):
                    self.draft(preview, **{option: invalid})

    def test_setext_heading_and_link_visible_text_use_real_ast(self):
        self.translations['units'][0]['translation'] = '[**守护者**](https://example.test/target2 "title3")\n======='
        block = self.preview()['sides']['translation']['blocks'][0]
        self.assertEqual(block['name_candidate']['selector'], {'kind': 'heading', 'block': 0, 'level': 1})
        self.assertEqual(block['name_candidate']['text'], '守护者')
        self.assertEqual(block['quantity_candidate']['text'], '守护者')

    def test_code_html_images_and_nested_blocks_never_supply_candidate_slots(self):
        for text in ['# `守护者`', '# <span>守护者</span>', '# ![守护者](#图像)',
                     '```\n# 守护者\n```', '> # 守护者', '- # 守护者', '<!-- # 守护者 -->']:
            with self.subTest(text=text):
                self.translations['units'][0]['translation'] = text
                blocks = self.preview()['sides']['translation']['blocks']
                self.assertTrue(blocks)
                self.assertNotIn('name_candidate', blocks[0])
                self.assertNotIn('quantity_candidate', blocks[0])

    def test_parser_unavailable_fails_closed(self):
        with patch.object(m.gate, 'parse_commonmark_ast', side_effect=RuntimeError('parser unavailable')):
            with self.assertRaisesRegex(RuntimeError, 'parser unavailable'):
                self.preview()

    def test_live_validators_prepare_and_checks_reject_entire_envelopes(self):
        sidecar = names.extract(self.resources)
        for envelope in [self.preview(), self.draft(name_selections=[(0, 0)], quantity_selections=[(2, 3)])]:
            with self.subTest(format=envelope['format']):
                with self.assertRaises(ValueError):
                    names.validate_bindings(self.resources, sidecar, self.sources, envelope)
                with self.assertRaises(ValueError):
                    m.quantities.validate_config(self.sources, envelope)
                checked = names.check(self.resources, sidecar, self.sources, self.translations,
                                      bindings=envelope, quantity_scopes=envelope)
                self.assertFalse(checked['release_allowed'])
                self.assertTrue(checked['name_binding_check']['configuration_errors'])
                self.assertTrue(checked['quantity_risk_check']['configuration_errors'])
                with tempfile.TemporaryDirectory() as tmp:
                    run = Path(tmp) / 'run'
                    for options in ({'bindings': envelope}, {'quantity_scopes': envelope}):
                        with self.assertRaises(ValueError):
                            names.prepare(self.sources, self.resources, run, **options)
                        self.assertFalse(run.exists())

    def test_cli_stdout_only_strict_json_and_no_write_modes(self):
        with tempfile.TemporaryDirectory() as tmp:
            directory = Path(tmp)
            paths = [directory / name for name in ['resources.json', 'sources.json', 'translations.json']]
            for path, value in zip(paths, [self.resources, self.sources, self.translations]):
                path.write_text(json.dumps(value, ensure_ascii=False), encoding='utf-8')
            command = [sys.executable, str(SCRIPT)]
            before = {p: p.read_bytes() for p in paths}
            result = subprocess.run(command + ['preview', *map(str, paths), '--resource-id', 'r1', '--unit-id', 's'],
                                    capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual({p: p.read_bytes() for p in paths}, before)
            self.assertEqual(set(directory.iterdir()), set(paths))
            preview_path = directory / 'preview.json'
            preview_path.write_text(result.stdout, encoding='utf-8')
            before[preview_path] = preview_path.read_bytes()
            draft_command = command + ['draft', *map(str, paths), str(preview_path)]
            result = subprocess.run(draft_command + ['--name', '0', '0', '--name-with-suffix', '2', '3', ' - 反应',
                                                     '--quantity', '2', '3'], capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(json.loads(result.stdout)['approval_status'], 'unconfirmed')
            for option in ['--out', '--approve', '--export']:
                result = subprocess.run(draft_command + [option, str(paths[0])], capture_output=True, text=True)
                self.assertNotEqual(result.returncode, 0)
                self.assertFalse(result.stdout)
            self.assertEqual({p: p.read_bytes() for p in before}, before)
            for invalid in ['{"a":1,"a":2}', '{', '{"a":NaN}']:
                paths[0].write_text(invalid, encoding='utf-8')
                result = subprocess.run(command + ['preview', *map(str, paths), '--resource-id', 'r1', '--unit-id', 's'],
                                        capture_output=True, text=True)
                self.assertEqual(result.returncode, 2)
                self.assertFalse(result.stdout)
                self.assertEqual(paths[0].read_text(encoding='utf-8'), invalid)

    def test_release_rejects_draft_even_if_file_hashes_are_recalculated(self):
        envelope = self.draft(name_selections=[(0, 0)], quantity_selections=[(2, 3)])
        for mode in ['name', 'quantity']:
            with self.subTest(mode=mode), tempfile.TemporaryDirectory() as tmp:
                run = Path(tmp) / 'run'
                if mode == 'name':
                    options = {'bindings': {'version': m.bindings.VERSION, 'unit_parents': [], 'bindings': []}}
                    filename, contract = 'name-bindings.json', 'name_binding_contract'
                else:
                    options = {'quantity_scopes': {'version': m.quantities.VERSION, 'scopes': []}}
                    filename, contract = 'quantity-scopes.json', 'quantity_scope_contract'
                names.prepare(self.sources, self.resources, run, **options)
                names.write(run / filename, envelope)
                digest = m.gate.v.digest((run / filename).read_bytes())
                packet = names.read(run / 'two-pass-packet.json')
                packet[contract]['sha256'] = digest
                names.write(run / 'two-pass-packet.json', packet)
                manifest = names.read(run / 'manifest.json')
                manifest['prepared_files'][filename] = digest
                manifest['prepared_files']['two-pass-packet.json'] = m.gate.v.digest((run / 'two-pass-packet.json').read_bytes())
                names.write(run / 'manifest.json', manifest)
                with self.assertRaisesRegex(ValueError, 'requires exactly'):
                    m.gate.release(run, development=True)
                self.assertFalse(names.read(run / 'delivery-gate.json')['release_allowed'])


if __name__ == '__main__':
    unittest.main()
