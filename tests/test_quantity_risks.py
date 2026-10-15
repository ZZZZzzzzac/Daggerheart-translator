"""Scoped quantity regressions; no model runs or external artifact dependencies."""
import copy
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from test_pbres_names import ROOT, fixture, m as names

gate = names.gate_module()
q = gate.quantity_module()


def config(source=None, translation=None):
    return {'version': q.VERSION, 'scopes': [
        {'id': 'cost', 'unit_id': 's', 'source': source or {'kind': 'unit'},
         'translation': translation or {'kind': 'unit'}}]}


def records(source='Mark 2 Stress.', translation='标记2压力点。'):
    return [{'id': 's', 'source': source}], {'units': [{'id': 's', 'translation': translation}]}


class QuantityTests(unittest.TestCase):
    def scan(self, source='Mark 2 Stress.', translation='标记2压力点。', cfg=None):
        sources, translations = records(source, translation)
        return q.scan(sources, translations, cfg if cfg is not None else config(), gate.parse_commonmark_ast)

    def test_changed_stress_is_a_located_review_risk_not_an_error_verdict(self):
        sources, translations = records(translation='标记3压力点。')
        before = copy.deepcopy([sources, translations])
        result = gate.scan_records(sources, translations, quantity_scopes=config())
        self.assertFalse(result['release_allowed'])
        check = result['quantity_risk_check']
        self.assertEqual(check['status'], 'needs_review')
        self.assertFalse(check['semantic_verified'])
        self.assertEqual(check['risk_count'], 1)
        risk = check['scopes'][0]['risks'][0]
        self.assertEqual(risk['kind'], 'quantity_sequence_difference')
        self.assertEqual(risk['source']['field_pointer'], '/0/source')
        self.assertEqual(risk['translation']['field_pointer'], '/units/0/translation')
        self.assertEqual([t['quote'] for t in risk['source']['tokens']], ['2'])
        self.assertEqual([t['quote'] for t in risk['translation']['tokens']], ['3'])
        for side in ['source', 'translation']:
            evidence = risk[side]
            for token in evidence['tokens']:
                self.assertEqual(evidence['extracted_text'][token['start']:token['end']], token['quote'])
            self.assertIn('not raw Markdown', evidence['offset_basis'])
        self.assertEqual([sources, translations], before)
        self.assertNotIn('error_count', check)

    def test_default_and_empty_config_do_not_add_requirements(self):
        sources, translations = records(translation='标记3压力点。')
        old = gate.scan_records(sources, translations)
        self.assertTrue(old['release_allowed'])
        self.assertNotIn('quantity_risk_check', old)
        empty = gate.scan_records(sources, translations, quantity_scopes={'version': q.VERSION, 'scopes': []})
        self.assertTrue(empty['release_allowed'])
        self.assertEqual(empty['quantity_risk_check']['status'], 'no_scopes_configured')
        self.assertFalse(empty['quantity_risk_check']['semantic_verified'])

    def test_common_integer_spellings(self):
        examples = [('2', '二'), ('2', '两'), ('2', '兩'), ('2', '２'), ('2', '02'),
                    ('zero', '零'), ('one', '一'), ('two', '2'), ('twenty-one', '二十一'),
                    ('twenty one', '二十一'), ('once', '一'), ('twice', '二'),
                    ('10', '十'), ('20', '二十'), ('102', '一百零二'),
                    ('1020', '一千零二十'), ('2000', '两千'), ('9999', '九千九百九十九')]
        for left, right in examples:
            with self.subTest(left=left, right=right):
                result = self.scan('Mark ' + left + ' Stress.', '标记' + right + '压力点。')
                self.assertEqual(result['status'], 'quantity_surface_match', result)
                self.assertFalse(result['semantic_verified'])

    def test_counted_hp_article_has_exact_original_evidence(self):
        source = ('**Healing Skin - Reaction:** When the Eeligator is spotlighted, '
                  'you can mark 2 Stress to clear a HP.')
        target = '**自愈表皮 - 反应：** 当电鳗鳄获得聚焦时，你可以为它标记 2 压力点，使它恢复 1 生命点。'
        sources, translations = records(source, target)
        before = copy.deepcopy([sources, translations])
        result = q.scan(sources, translations, config(), gate.parse_commonmark_ast)
        self.assertEqual(result['status'], 'quantity_surface_match', result)
        self.assertFalse(result['semantic_verified'])
        row = result['scopes'][0]
        self.assertEqual(row['source']['tokens'], [
            {'start': 73, 'end': 74, 'quote': '2', 'kind': 'integer', 'value': '2'},
            {'start': 91, 'end': 92, 'quote': 'a', 'kind': 'integer', 'value': '1'}])
        self.assertEqual([(t['start'], t['end'], t['quote']) for t in row['translation']['tokens']],
                         [(29, 30, '2'), (40, 41, '1')])
        for side in ['source', 'translation']:
            for token in row[side]['tokens']:
                self.assertEqual(row[side]['extracted_text'][token['start']:token['end']], token['quote'])
        self.assertEqual([sources, translations], before)

    def test_counted_hp_article_variants_and_repetition_keep_order(self):
        for source, quote in [('Clear a HP', 'a'), ('clear an HP.', 'an'),
                              ('CLEAR A HP!', 'A'), ('Clear\ta\tHP?', 'a'),
                              ('Clear **an** HP.', 'an')]:
            with self.subTest(source=source):
                result = self.scan(source, '恢复1生命点。')
                self.assertEqual(result['status'], 'quantity_surface_match', result)
                self.assertEqual(result['scopes'][0]['source']['tokens'][0]['quote'], quote)
        result = self.scan('Clear a HP; clear an HP. Mark 2 Stress.', '恢复1生命点，恢复1生命点，标记2压力点。')
        self.assertEqual(result['status'], 'quantity_surface_match', result)
        self.assertEqual([t['value'] for t in result['scopes'][0]['source']['tokens']], ['1', '1', '2'])

    def test_counted_hp_article_does_not_hide_changes_or_omissions(self):
        source = 'Mark 2 Stress to clear a HP.'
        for target in ['标记3压力点，恢复1生命点。', '标记2压力点，恢复2生命点。',
                       '标记2压力点。', '恢复1生命点。',
                       '标记2压力点，恢复1生命点，再恢复1生命点。', '恢复1生命点，标记2压力点。']:
            with self.subTest(target=target):
                result = self.scan(source, target)
                self.assertEqual(result['status'], 'needs_review', result)
                self.assertIn('quantity_sequence_difference', [r['kind'] for r in result['scopes'][0]['risks']])
                self.assertFalse(result['semantic_verified'])

    def test_unsupported_hp_articles_are_uncertain_not_silent_matches(self):
        for expression in ['a HP', 'a HP threshold', 'clear a HP threshold.',
                           "clear a HP's value.", 'clear a HP-related effect.',
                           'clear a HP/Stress.', 'clear a HP or two.',
                           'clear a HP, then act.', 'clear a HP every turn.',
                           'clear a HP.threshold', 'unclear a HP.', 'un-clear a HP.',
                           'foo/clear a HP.', '_clear a HP.', 'clear\n\na HP.',
                           'negative a HP.', 'half a HP.']:
            with self.subTest(expression=expression):
                result = self.scan('Mark 2 Stress. ' + expression, '标记2压力点。')
                self.assertEqual(result['status'], 'needs_review', result)
                evidence = result['scopes'][0]['source']
                self.assertTrue(evidence['uncertain'], evidence)
                self.assertNotIn('1', [t['value'] for t in evidence['tokens']])
                for token in evidence['tokens'] + evidence['uncertain']:
                    self.assertEqual(evidence['extracted_text'][token['start']:token['end']], token['quote'])

    def test_articles_and_resource_compounds_are_not_globally_one(self):
        for expression in ['a target', 'an ally', 'a Stress', 'a Fear', 'a HPs',
                           'a HP1', 'a HPP', 'a _HP', 'a HP_threshold', 'a HP-target']:
            with self.subTest(expression=expression):
                result = q.tokenize('clear ' + expression + '.')
                self.assertNotIn('1', [t['value'] for t in result['tokens']], result)
                self.assertEqual(self.scan('clear ' + expression + '.', '恢复1生命点。')['status'], 'needs_review')
        self.assertEqual(q.tokenize('Choose a target or an ally.')['tokens'], [])
        result = self.scan('You cannot clear a HP.', '你不能恢复1生命点。')
        self.assertEqual(result['status'], 'quantity_surface_match')
        self.assertFalse(result['semantic_verified'])

    def test_counted_hp_article_uses_only_visible_supported_markdown(self):
        result = self.scan('[Clear a HP](https://example.org/99 "clear a HP").', '恢复1生命点。')
        self.assertEqual(result['status'], 'quantity_surface_match', result)
        self.assertEqual(len(result['scopes'][0]['source']['tokens']), 1)
        result = self.scan('Mark 2 Stress. https://example.org/clear/a/HP', '标记2压力点。')
        self.assertEqual(result['status'], 'quantity_surface_match', result)
        for source in ['`clear a HP.`', '<!-- clear a HP. -->', '![clear a HP.](#1)']:
            with self.subTest(source=source):
                result = self.scan(source, '恢复1生命点。')
                self.assertEqual(result['status'], 'needs_review', result)
                self.assertIn('unavailable', result['scopes'][0]['source'])

    def test_url_mask_cannot_complete_the_counted_article_frame(self):
        for source in ['clear https://example.org/thing a HP.',
                       'clear a https://example.org/thing HP.',
                       'clear a HP https://example.org/thing']:
            with self.subTest(source=source):
                self.assertNotIn('1', [t['value'] for t in q.tokenize(source)['tokens']])
                result = self.scan('Mark 2 Stress. ' + source, '标记2压力点，恢复1生命点。')
                self.assertEqual(result['status'], 'needs_review', result)
        source = 'Clear a HP. https://example.org/99'
        result = self.scan(source, '恢复1生命点。')
        self.assertEqual(result['status'], 'quantity_surface_match', result)
        self.assertEqual(result['scopes'][0]['source']['tokens'], [
            {'start': 6, 'end': 7, 'quote': 'a', 'kind': 'integer', 'value': '1'}])

    def test_whole_dice_normalization_and_atomicity(self):
        for left, right in [('d6', '1d6'), ('D6', 'd6'), ('2d6 + 2', '2D6+2'),
                            ('d8 − 2', '1d8-2'), ('1 d 6', 'd6'), ('d6', 'ｄ６')]:
            with self.subTest(left=left, right=right):
                result = self.scan('Roll ' + left + '.', '掷' + right + '。')
                self.assertEqual(result['status'], 'quantity_surface_match', result)
                self.assertEqual(len(result['scopes'][0]['source']['tokens']), 1)
                self.assertEqual(result['scopes'][0]['source']['tokens'][0]['kind'], 'dice')
        self.assertEqual(self.scan('Roll 2d6.', '掷6d2。')['status'], 'needs_review')
        self.assertEqual(self.scan('Roll d6 + 2.', '掷d6，另加2。')['status'], 'needs_review')

    def test_existing_exact_dice_policy_remains_independent(self):
        sources, translations = records('Roll d6.', '掷1d6。')
        result = gate.scan_records(sources, translations, quantity_scopes=config())
        self.assertEqual(result['quantity_risk_check']['status'], 'quantity_surface_match')
        self.assertFalse(result['release_allowed'])
        self.assertTrue(any(f['kind'] == 'missing_original_dice_expression' for f in result['units'][0]['findings']))

    def test_multiple_numbers_repetition_and_reordering_are_not_sets(self):
        self.assertEqual(self.scan('Mark 2 Stress and gain 3 Hope.', '标记二压力点，获得三希望点。')['status'], 'quantity_surface_match')
        for target in ['标记2压力点。', '标记2压力点，获得2希望点。', '获得3希望点，标记2压力点。']:
            self.assertEqual(self.scan('Mark 2 Stress and gain 3 Hope.', target)['status'], 'needs_review')
        self.assertEqual(self.scan('Mark 2 Stress and gain 2 Hope.', '标记2压力点。')['status'], 'needs_review')

    def test_matching_values_do_not_verify_semantics_or_roles(self):
        result = self.scan('Mark 2 Stress and gain 3 Hope.', '获得2希望点，标记3压力点。')
        self.assertEqual(result['status'], 'quantity_surface_match')
        self.assertFalse(result['semantic_verified'])
        self.assertFalse(result['scopes'][0]['semantic_verified'])
        self.assertIn('attribution', result['note'])

    def test_unsupported_lexemes_never_pass_as_integer_fragments(self):
        examples = ['1.5', '.5', '1,000', '1/2', '10%', '10 percent', '2–3', '2-3',
                    '2 to 3', '2:3', '1e3', '-2', '- 2', '+2', '2nd', 'x2', '2x',
                    '2 + 3', 'half', 'one hundred', 'one and two', '½', '²', 'Ⅲ', '٢',
                    '１．５', '１／２', '＋２', '2d6kh1', 'd6!', 'd6+2+3', 'd6/2',
                    'd6 + 1d4', '0d6', 'd0', 'd6 + Strength', 'negative two', 'minus 2',
                    'two-thirds', 'twenty-first', 'two point five', 'two thirds', 'twenty first',
                    'two percent', '2 per cent', '1 000', '1\u202f000', '2点5', '2÷3', '2^3', '2d6÷2']
        for expression in examples:
            with self.subTest(expression=expression):
                result = self.scan('Pay ' + expression + '.', '支付2压力点。')
                evidence = result['scopes'][0]['source']
                self.assertEqual(result['status'], 'needs_review')
                self.assertTrue(evidence['uncertain'], evidence)
        for expression in ['二点五', '三分之一', '百分之二十', '半', '一百二', '二〇二六', '一万', '第2', '第三', '壹', '负二', '负2']:
            with self.subTest(expression=expression):
                result = self.scan('Mark 2 Stress.', '标记' + expression + '压力点。')
                self.assertTrue(result['scopes'][0]['translation']['uncertain'], result)

    def test_ambiguous_chinese_lexemes_are_review_visible(self):
        for text in ['一起行动。', '一旦触发。', '统一处理。', '两者任选。', '唯一目标。', '十分困难。', '一半压力。']:
            result = self.scan('Act.', text)
            self.assertEqual(result['status'], 'needs_review')
            self.assertTrue(result['scopes'][0]['translation']['uncertain'], text)

    def test_empty_and_no_quantity_scopes_need_review(self):
        for source, target in [('', ''), ('Rest.', '休息。'), ('Pay half.', '支付一半。')]:
            self.assertEqual(self.scan(source, target)['status'], 'needs_review')

    def test_explicit_blocks_use_independent_top_level_ast_indices(self):
        cfg = config({'kind': 'block', 'block': 1}, {'kind': 'block', 'block': 2})
        result = self.scan('# Level 9\n\nMark **2** Stress.', '# 第8级\n\n说明。\n\n标记二压力点。', cfg)
        self.assertEqual(result['status'], 'quantity_surface_match')
        row = result['scopes'][0]
        self.assertEqual(row['source']['ast_paths'], ['/blocks/1'])
        self.assertEqual(row['translation']['ast_paths'], ['/blocks/2'])
        self.assertEqual(row['source']['extracted_text'], 'Mark 2 Stress.')

    def test_unbound_units_and_blocks_are_not_scanned(self):
        sources, translations = records('Mark 2 Stress.', '标记2压力点。')
        sources.append({'id': 'other', 'source': 'Gain 3 Hope.'})
        translations['units'].append({'id': 'other', 'translation': '获得9希望点。'})
        self.assertTrue(gate.scan_records(sources, translations, quantity_scopes=config())['release_allowed'])
        cfg = config({'kind': 'block', 'block': 0}, {'kind': 'block', 'block': 0})
        self.assertEqual(self.scan('Mark 2 Stress.\n\nGain 3 Hope.', '标记2压力点。\n\n获得9希望点。', cfg)['status'], 'quantity_surface_match')

    def test_links_only_visible_labels_and_bare_urls_are_not_quantities(self):
        result = self.scan('[Mark 2 Stress](https://example.org/99 "3").', '[标记二压力点](https://example.org/88 "4")。')
        self.assertEqual(result['status'], 'quantity_surface_match')
        result = self.scan('Mark 2 Stress. https://example.org/99', '标记2压力点。 https://example.org/88')
        self.assertEqual(result['status'], 'quantity_surface_match')
        self.assertEqual(self.scan('[Rules](#2)', '[规则](#2)')['status'], 'needs_review')

    def test_unsupported_markup_cannot_supply_or_hide_evidence(self):
        for text in ['`2`', '```\n2\n```', '<!-- 2 -->', '<span>2</span>', '![2](#2)',
                     '> 2', '- 2', '1. 2', '***', '2\n\n<!-- hidden -->']:
            result = self.scan('2', text)
            self.assertEqual(result['status'], 'needs_review', text)
            self.assertIn('unavailable', result['scopes'][0]['translation'], text)

    def test_missing_block_or_field_retains_both_selectors_and_available_side(self):
        cfg = config({'kind': 'block', 'block': 1}, {'kind': 'block', 'block': 0})
        result = self.scan(cfg=cfg)
        risk = result['scopes'][0]['risks'][0]
        self.assertEqual(risk['kind'], 'quantity_scope_unavailable')
        self.assertEqual(risk['source']['selector']['block'], 1)
        self.assertTrue(risk['translation']['tokens'])

    def test_fields_support_rfc6901_and_are_explicit_plain_text(self):
        sources, translations = records()
        sources[0]['quantity_fields'] = {'a/b': {'~': ['2']}}
        translations['units'][0]['quantity_fields'] = {'cost': '二'}
        cfg = config({'kind': 'field', 'pointer': '/quantity_fields/a~1b/~0/0'},
                     {'kind': 'field', 'pointer': '/quantity_fields/cost'})
        result = q.scan(sources, translations, cfg, lambda _: self.fail('plain fields need no Markdown parser'))
        self.assertEqual(result['status'], 'quantity_surface_match')
        self.assertEqual(result['scopes'][0]['source']['field_pointer'], '/0/quantity_fields/a~1b/~0/0')
        for pointer in ['/quantity_fields/a~1b/~0/00', '/quantity_fields/a~1b/~0/-1', '/quantity_fields/missing']:
            cfg['scopes'][0]['source']['pointer'] = pointer
            self.assertEqual(q.scan(sources, translations, cfg, gate.parse_commonmark_ast)['status'], 'needs_review')
        for value in ['', None, [], 2, True]:
            translations['units'][0]['quantity_fields']['cost'] = value
            self.assertEqual(q.scan(sources, translations, config({'kind': 'unit'}, {'kind': 'field', 'pointer': '/quantity_fields/cost'}), gate.parse_commonmark_ast)['status'], 'needs_review')

    def test_invalid_config_is_distinct_from_text_risks(self):
        bad = [None, [], {}, dict(config(), extra=True), dict(config(), version='unknown'), dict(config(), scopes=None)]
        for selector in [None, [], {'kind': []}, {'kind': 'regex'}, {'kind': 'unit', 'extra': 1},
                         {'kind': 'block', 'block': True}, {'kind': 'block', 'block': -1},
                         {'kind': 'block', 'block': 1.0}, {'kind': 'block'},
                         {'kind': 'field', 'pointer': '/translation'}, {'kind': 'field', 'pointer': '/quantity_fields'},
                         {'kind': 'field', 'pointer': '/quantity_fields/~2'}]:
            cfg = config(); cfg['scopes'][0]['source'] = selector; bad.append(cfg)
        for key, value in [('id', ''), ('unit_id', 'unknown'), ('unit_id', []), ('id', False)]:
            cfg = config(); cfg['scopes'][0][key] = value; bad.append(cfg)
        cfg = config(); cfg['scopes'] *= 2; bad.append(cfg)
        cfg = config(); second = copy.deepcopy(cfg['scopes'][0]); second['id'] = 'other'; cfg['scopes'].append(second); bad.append(cfg)
        for cfg in bad:
            with self.subTest(config=cfg):
                result = q.scan(*records(), cfg, gate.parse_commonmark_ast)
                self.assertFalse(result['release_allowed'])
                self.assertTrue(result['configuration_errors'])
                self.assertEqual(result['risk_count'], 0)
                self.assertFalse(result['semantic_verified'])

    def test_missing_duplicate_invalid_unit_identity_is_not_guessed(self):
        sources, translations = records()
        for units in [[], None, [None], translations['units'] * 2, [{'id': 's', 'translation': None}]]:
            result = gate.scan_records(sources, {'units': units}, quantity_scopes=config())
            self.assertFalse(result['release_allowed'])
            self.assertEqual(result['quantity_risk_check']['status'], 'needs_review')
        for src in [[], sources * 2, [{'id': 's'}], [None], [{'id': '', 'source': '2'}]]:
            self.assertTrue(q.scan(src, translations, config(), gate.parse_commonmark_ast)['configuration_errors'])

    def test_parser_missing_and_invalid_ast_need_review(self):
        with patch.object(gate.shutil, 'which', return_value=None):
            self.assertEqual(self.scan()['status'], 'needs_review')
        for ast in [None, {}, {'blocks': [None]}, {'blocks': [{'t': 'Header', 'c': []}]}]:
            result = q.scan(*records(), config(), lambda _: ast)
            self.assertEqual(result['status'], 'needs_review')

    def test_pbres_optional_check_combines_quantity_and_name_binding(self):
        resources = fixture(); sidecar = names.extract(resources)
        sources, translations = records('# Guardian\n\nMark 2 Stress.', '# 守护者\n\n标记3压力点。')
        cfg = config({'kind': 'block', 'block': 1}, {'kind': 'block', 'block': 1})
        binding = {'version': 'pbres-name-bindings-v1', 'unit_parents': [{'unit_id': 's', 'resource_id': 'r1'}],
                   'bindings': [{'unit_id': 's', 'resource_id': 'r1', 'name_pointer': '/data/名称',
                                 'selector': {'kind': 'heading', 'block': 0, 'level': 1}}]}
        result = names.check(resources, sidecar, sources, translations, binding, quantity_scopes=cfg)
        self.assertTrue(result['name_binding_check']['release_allowed'])
        self.assertFalse(result['quantity_risk_check']['release_allowed'])
        self.assertFalse(result['release_allowed'])


class QuantityWorkflowTests(unittest.TestCase):
    def make_run(self, run, target='标记2压力点。', pbres=False):
        sources, _ = records()
        if pbres:
            names.prepare(sources, fixture(), run, quantity_scopes=config())
        else:
            gate.prepare(sources, run, {'allowed_latin': []}, quantity_scopes=config())
        draft = {'units': [{'id': 's', 'translation': target, 'invariants': [
            {'id': 'i', 'source_quote': 'Mark 2 Stress', 'meaning': '标记2压力点'}],
            'protected_phrases': [], 'questions': []}]}
        final = {'units': [{'id': 's', 'translation': target, 'invariant_checks': [
            {'invariant_id': 'i', 'source_quote': 'Mark 2 Stress', 'target_quote': target, 'verdict': 'preserved'}],
            'phrase_exceptions': [], 'changes': [], 'ambiguity_checks': [
            {'source_quote': 'Mark 2 Stress', 'target_quote': target, 'verdict': 'no_new_ambiguity'}], 'questions': []}]}
        gate.v.dump(run / 'candidate-draft.json', draft)
        (names.polish if pbres else gate.polish)(run, development=True)
        gate.v.dump(run / 'candidate-final.json', final)

    def test_prepare_polish_and_real_freeze_release_both_adapters(self):
        for pbres in [False, True]:
            with self.subTest(pbres=pbres), tempfile.TemporaryDirectory() as tmp:
                run = Path(tmp) / 'run'; self.make_run(run, pbres=pbres)
                manifest = gate.v.read_json(run / 'manifest.json')
                self.assertEqual(manifest['quantity_scopes'], 'quantity-scopes.json')
                self.assertIn('quantity-scopes.json', manifest['prepared_files'])
                self.assertIn('experiments/context_contract/quantity_risks.py', manifest['rules'])
                for filename in ['phase1-generate.txt', 'baseline-generate.txt', 'two-pass-packet.json', 'phase2-polish.txt']:
                    self.assertIn('机制数量范围', (run / filename).read_text())
                before = (run / 'candidate-final.json').read_bytes()
                result = gate.release(run, development=True)
                self.assertTrue(result['release_allowed'], result)
                self.assertEqual(result['quantity_risk_checks']['candidate']['status'], 'quantity_surface_match')
                self.assertFalse(result['semantic_verified'])
                self.assertEqual((run / 'candidate-final.json').read_bytes(), before)
                self.assertTrue((run / 'frozen.json').exists())

    def test_enabled_risks_block_clean_release_even_when_basic_gate_passes(self):
        with tempfile.TemporaryDirectory() as tmp:
            run = Path(tmp) / 'run'; self.make_run(run, '标记3压力点。')
            self.assertTrue(gate.scan_records(*records(translation='标记3压力点。'))['release_allowed'])
            before = (run / 'candidate-final.json').read_bytes()
            result = gate.release(run, development=True)
            self.assertFalse(result['release_allowed'])
            self.assertEqual(result['status'], 'BLOCKED')
            self.assertEqual(result['quantity_risk_checks']['candidate']['status'], 'needs_review')
            self.assertEqual(gate.v.read_json(run / 'frozen.json')['structural_errors'], [])
            self.assertEqual((run / 'candidate-final.json').read_bytes(), before)

    def test_baseline_review_gets_same_policy_and_updated_hash(self):
        with tempfile.TemporaryDirectory() as tmp:
            run = Path(tmp) / 'run'; self.make_run(run, pbres=True)
            (run / 'baseline/drafts/s.md').write_text((run / 'baseline/chunks/s.md').read_text())
            names.polish(run, development=False)
            self.assertIn('机制数量范围', (run / 'baseline-review.txt').read_text())
            self.assertEqual(gate.v.read_json(run / 'stage-input-hashes.json')['baseline-review.txt'], gate.v.digest((run / 'baseline-review.txt').read_bytes()))

    def test_full_release_checks_actual_baseline_and_candidate_delivery(self):
        for baseline_value in ['2', '3']:
            with self.subTest(baseline=baseline_value), tempfile.TemporaryDirectory() as tmp:
                run = Path(tmp) / 'run'; self.make_run(run)
                wrapper = '[[[KILO_TARGET_START]]]\n标记2压力点。\n[[[KILO_TARGET_END]]]\n'
                (run / 'baseline/drafts/s.md').write_text(wrapper)
                gate.polish(run, development=False)
                (run / 'baseline/finals/s.md').write_text(wrapper.replace('2压力', baseline_value + '压力'))
                gate.v.dump(run / 'baseline-review-log.json', {'questions': [], 'changes': []})
                result = gate.release(run)
                self.assertEqual(result['release_allowed'], baseline_value == '2', result)
                self.assertEqual(set(result['quantity_risk_checks']), {'baseline', 'candidate'})
                self.assertEqual(result['quantity_risk_checks']['candidate']['status'], 'quantity_surface_match')
                self.assertEqual(result['quantity_risk_checks']['baseline']['status'], 'quantity_surface_match' if baseline_value == '2' else 'needs_review')

    def test_prepare_rejects_invalid_and_field_selectors_before_creating_directory(self):
        field = {'kind': 'field', 'pointer': '/quantity_fields/cost'}
        for cfg in [None, {}, config(field), config(translation=field)]:
            with tempfile.TemporaryDirectory() as tmp:
                run = Path(tmp) / 'run'
                with self.assertRaises(ValueError):
                    gate.prepare(records()[0], run, {}, quantity_scopes=cfg)
                self.assertFalse(run.exists())

    def test_integrity_tamper_removal_marker_rule_packet_witness_and_old_success(self):
        for mutation in ['tamper', 'remove', 'marker', 'registration', 'rule', 'packet', 'combined', 'combined_rule', 'output']:
            with self.subTest(mutation=mutation), tempfile.TemporaryDirectory() as tmp:
                run = Path(tmp) / 'run'; self.make_run(run)
                self.assertTrue(gate.release(run, development=True)['release_allowed'])
                manifest = gate.v.read_json(run / 'manifest.json')
                if mutation == 'tamper':
                    gate.v.dump(run / 'quantity-scopes.json', {'version': q.VERSION, 'scopes': []})
                elif mutation == 'remove':
                    (run / 'quantity-scopes.json').unlink()
                elif mutation == 'marker':
                    del manifest['quantity_scopes']
                elif mutation == 'registration':
                    del manifest['prepared_files']['quantity-scopes.json']
                elif mutation == 'rule':
                    del manifest['rules']['experiments/context_contract/quantity_risks.py']
                elif mutation == 'packet':
                    packet = gate.v.read_json(run / 'two-pass-packet.json'); del packet['quantity_scope_contract']
                    gate.v.dump(run / 'two-pass-packet.json', packet)
                    manifest['prepared_files']['two-pass-packet.json'] = gate.v.digest((run / 'two-pass-packet.json').read_bytes())
                elif mutation in {'combined', 'combined_rule'}:
                    (run / 'quantity-scopes.json').unlink()
                    del manifest['quantity_scopes']; del manifest['prepared_files']['quantity-scopes.json']
                    if mutation == 'combined_rule':
                        del manifest['rules']['experiments/context_contract/quantity_risks.py']
                else:
                    gate.v.dump(run / 'candidate-delivery.json', records(translation='标记3压力点。')[1])
                gate.v.dump(run / 'manifest.json', manifest)
                with self.assertRaises((ValueError, FileNotFoundError)):
                    gate.release(run, development=True)
                self.assertFalse(gate.v.read_json(run / 'delivery-gate.json')['release_allowed'])

    def test_default_prepare_has_no_quantity_inputs_or_report(self):
        with tempfile.TemporaryDirectory() as tmp:
            run = Path(tmp) / 'run'
            gate.prepare(records()[0], run, {})
            manifest = gate.v.read_json(run / 'manifest.json')
            self.assertNotIn('quantity_scopes', manifest)
            self.assertFalse((run / 'quantity-scopes.json').exists())
            self.assertNotIn('quantity_scope_contract', gate.v.read_json(run / 'two-pass-packet.json'))

    def test_cli_scan_pbres_check_prepare_and_json_failures(self):
        with tempfile.TemporaryDirectory() as tmp:
            folder = Path(tmp)
            sources, translations = records(translation='标记3压力点。')
            resources = fixture()
            for name, value in [('sources', sources), ('translations', translations), ('scopes', config()),
                                ('resources', resources), ('sidecar', names.extract(resources))]:
                gate.v.dump(folder / (name + '.json'), value)
            script = ROOT / 'experiments/context_contract/delivery_gate.py'
            base = [sys.executable, str(script), 'scan', str(folder / 'sources.json'), str(folder / 'translations.json')]
            option = ['--quantity-scopes', str(folder / 'scopes.json')]
            before = {p.name: p.read_bytes() for p in folder.iterdir()}
            result = subprocess.run(base + option, capture_output=True, text=True)
            self.assertEqual(result.returncode, 2, result.stderr)
            self.assertEqual(json.loads(result.stdout)['quantity_risk_check']['status'], 'needs_review')
            self.assertEqual(before, {p.name: p.read_bytes() for p in folder.iterdir()})
            self.assertEqual(subprocess.run(base, capture_output=True).returncode, 0)
            self.assertNotEqual(subprocess.run(base + ['--quantity-scopes', ''], capture_output=True).returncode, 0)
            pbres = [sys.executable, str(ROOT / 'experiments/context_contract/pbres_names.py'), 'check']
            pbres += [str(folder / (name + '.json')) for name in ['resources', 'sidecar', 'sources', 'translations']]
            result = subprocess.run(pbres + option, capture_output=True, text=True)
            self.assertEqual(result.returncode, 2, result.stderr)
            self.assertIn('quantity_risk_check', json.loads(result.stdout))
            self.assertNotEqual(subprocess.run(pbres + ['--quantity-scopes', ''], capture_output=True).returncode, 0)
            cmd = [sys.executable, str(script), 'prepare', str(folder / 'sources.json'), str(folder / 'run')] + option
            result = subprocess.run(cmd, capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertTrue((folder / 'run/quantity-scopes.json').exists())
            for text in ['null', '{"version":"bad","version":"mechanic-quantity-scopes-v1","scopes":[]}']:
                (folder / 'scopes.json').write_text(text)
                self.assertNotEqual(subprocess.run(base + option, capture_output=True).returncode, 0)
            with self.assertRaisesRegex(ValueError, 'duplicate JSON object key'):
                q.read(folder / 'scopes.json')


if __name__ == '__main__':
    unittest.main()
