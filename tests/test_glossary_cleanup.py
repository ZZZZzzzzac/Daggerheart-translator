"""Regression tests for owner-authorized, source-grounded glossary cleanup.

These test literal matching and declared provenance, not autonomous semantic understanding.
"""
import hashlib
import importlib.util
import json
import re
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PIPE = ROOT / 'skills/daggerheart-translation-pipeline'
RES = PIPE / 'resources'
REF = RES / 'reference'

def read(p):
    return json.loads(p.read_text(encoding='utf-8'))

class CleanupTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.core = read(RES / 'terms-core.json')
        cls.by = {x['term']: x for x in cls.core}
        cls.decisions = read(REF / 'glossary-cleanup-decisions.json')
        cls.context = read(REF / 'contextual-usage.json')
        cls.new_context = read(REF / 'srd2-context-only.json')
        spec = importlib.util.spec_from_file_location('cleanup_matcher', PIPE / 'scripts/replace_terms.py')
        cls.matcher = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(cls.matcher)

    def test_reroll_and_variant_use_requested_translation(self):
        self.assertEqual(self.by['reroll'], {
            'term': 'reroll', 'translation': '重掷', 'variants': ['rerolling'],
        })
        for source in ('reroll', 'rerolling', 'Reroll'):
            with self.subTest(source=source):
                self.assertEqual(self.tag(source), '【' + source + '｜重掷】')

    def test_fixed_rest_phrase_is_preserved(self):
        self.assertEqual(self.by["Once per long rest"]["translation"], "每长休一次")
        for source in ('Once per long rest', 'once per long rest'):
            self.assertIn('【' + source + '｜每长休一次', self.tag(source))
            self.assertNotIn('每次长休限一次', self.tag(source))

    def tag(self, text):
        return self.matcher.replace_terms(text, str(RES / 'terms-core.json'))

    def test_all_old_cards_and_25_candidates_have_decisions(self):
        cards = self.decisions['audit_card_resolutions']
        self.assertEqual(len(cards), 44)
        self.assertEqual({x['finding_id'] for x in cards},
                         {f'G{i:03d}' for i in range(1, 32)} | {f'A{i:03d}' for i in range(1, 14)})
        self.assertTrue(all(x['decision'] and 'pending' not in x['status'] for x in cards))
        candidates = self.decisions['other_candidate_decisions']
        self.assertEqual(len(candidates), 25)
        self.assertEqual(sum(x['destination'] == 'core' for x in candidates), 22)
        for x in candidates:
            self.assertTrue(x['source_ids'])
            if x['destination'] == 'core':
                self.assertEqual(self.by[x['term']]['translation'], x['translation'])
            else:
                self.assertTrue(any(r['term'] == x['term'] for r in self.context['entries']))

    def test_live_project_choices(self):
        for word, translation in {'Support':'辅助','spotlight':'聚焦','Dazed':'恍惚',
                                  'Stunned':'眩晕','Blaze of Glory':'光荣就义',
                                  'Unarmed Attack':'徒手攻击','Unarmed Attack Roll':'徒手攻击掷骰'}.items():
            self.assertEqual(self.by[word]['translation'], translation)
        self.assertNotIn('Supports', self.by)
        self.assertNotIn('SPOTLIGHT', self.by)
        self.assertIn('【Support｜辅助', self.tag('Support'))
        self.assertIn('【Supports｜辅助', self.tag('Supports'))
        self.assertIn('【SPOTLIGHT｜聚焦', self.tag('SPOTLIGHT'))

    def test_attested_wrong_sense_examples_no_longer_get_wrong_markers(self):
        for text in ['windowsills or thresholds', 'were close to',
                     'suggestions and support of the rest of the table',
                     'advanced technology', 'No advancement', 'a running jump',
                     'the stress of daily life', 'Health', 'Arcane steel']:
            with self.subTest(text=text):
                self.assertEqual(self.tag(text), text)

    def test_damage_prefix_is_context_not_literal_variable_or_regex_engine(self):
        for text in ['reduce the damage by 1d8', 'reduce the damage by one threshold',
                     'reduce the damage by 2 thresholds', 'reduce the severity by one threshold']:
            self.assertEqual(self.tag(text), text)
        self.assertFalse(any(x['term'].startswith('reduce the ') for x in self.core))
        reference = (ROOT / 'skills/daggerheart-chinese-writing/REFERENCE.md').read_text()
        self.assertIn('X只是', reference)
        self.assertIn('伤害减少 1d8 点', reference)
        self.assertIn('伤害等级降低 X 级', reference)
        self.assertIn('少标记 X 生命点', reference)
        self.assertIn('不新增正则捕获机制', reference)

    def test_context_choices_are_kept_and_not_automatic_matching_input(self):
        for doc in [self.context, self.new_context]:
            self.assertIsInstance(doc, dict)
            self.assertIs(doc['automatic_matching'], False)
            self.assertTrue(all(x['automatic_matching'] is False for x in doc['entries']))
        self.assertEqual(len(self.context['entries']), 44)
        self.assertEqual(len(self.new_context['entries']), 6)
        for word in ['Clear', 'Cloaked', 'Ghost', 'Minor Threshold', 'kohd', 'Close', 'Far']:
            self.assertNotIn(word, self.by)
        features = read(RES / 'adversaries_features.json')
        self.assertFalse({'Cloaked', 'Ghost'} & {x['term'] for x in features})
        feature_context = {x['term']: x for x in self.context['entries'] if x['usage'] == 'adversary_feature'}
        self.assertEqual(feature_context['Ghost']['default_translation'], '幽灵形态')
        self.assertEqual(feature_context['Cloaked']['default_translation'], '隐匿无踪')
        ghost = next(x for x in self.new_context['entries'] if x['term'] == 'Ghost')
        self.assertEqual(ghost['resolved_translation'], '鬼魂')
        self.assertEqual(ghost['status'], 'context_required')

    def test_canonical_spelling_and_no_parenthesis_boundary_failure(self):
        for term in ['Companion sheet','Faerie','Infernis','Firbolg','Halfling','Hit Point Slot','Exploration','Player Character']:
            self.assertIn(term, self.by)
            self.assertIn('【'+term+'｜', self.tag(term))
        for old in ['Campanion sheet','Faeire','Inferis','Halfing','HP Slot','Explorations','Player Character (PC)']:
            self.assertNotIn(old, self.by)
        tagged = self.tag('Player Character (PC)')
        self.assertIn('【Player Character｜玩家角色', tagged)

    def test_attested_compound_plurals_and_resource_heading(self):
        for term, zh in [('attack rolls','攻击掷骰'),('reaction rolls','反应掷骰'),
                         ('Spellcast Rolls','施法掷骰'),('Fear Dice','恐惧骰'),
                         ('Hit Point Slots','生命槽'),('HOPE','希望点')]:
            self.assertIn('【'+term+'｜'+zh, self.tag(term))

    def test_scoped_plural_does_not_reenter_core(self):
        self.assertNotIn('flavor profile', self.by)
        self.assertNotIn('Colossal Power', self.by)
        beast = RES / 'scoped/beast-feast.json'
        self.assertIn('【flavor profiles｜风味组合', self.matcher.replace_terms('flavor profiles', str(beast)))
        self.assertEqual(self.tag('flavor profiles Colossal Power'), 'flavor profiles Colossal Power')

    def test_no_conflicting_active_forms_across_default_tables(self):
        tables = [('core', self.core)] + [(p.name, read(p)) for p in RES.glob('adversaries_*.json')]
        by = {}
        for table, entries in tables:
            for entry in entries:
                for form in [entry['term'], *entry.get('variants', [])]:
                    for old_form, old, old_table in by.get(form.casefold(), []):
                        if entry.get('case_sensitive') and old.get('case_sensitive') and form != old_form:
                            continue
                        self.assertEqual(entry['translation'], old['translation'],
                                         (table, form, old_table, old['term']))
                    by.setdefault(form.casefold(), []).append((form, entry, table))

    def test_existing_literal_matcher_is_unchanged_and_limit_is_not_hidden(self):
        baseline = read(ROOT / 'tests/fixtures/srd2-glossary-baseline.json')
        for relative, expected in baseline['protected_files'].items():
            if '/scripts/' in relative:
                # The glossary base predates separately published HTML UI work.
                # Keep its exact authorized upstream hashes without changing the
                # matcher baseline or accepting unrecorded script edits.
                authorized = self.decisions['authorized_protected_file_changes'].get(relative)
                if authorized:
                    self.assertEqual(authorized['before_sha256'], expected)
                    expected = authorized['after_sha256']
                self.assertEqual(hashlib.sha256((ROOT / relative).read_bytes()).hexdigest(), expected)
        # Known lexical limitations remain; this task does not claim a new matching mechanism.
        self.assertEqual(self.tag('_Hope_'), '_Hope_')
        self.assertEqual(self.tag('Armor\nScore'), 'Armor\nScore')
        self.assertTrue(any('line-break' in x for x in self.decisions['limits']))

if __name__ == '__main__':
    unittest.main()
