"""SRD2-only additions, provenance, and unchanged legacy matching boundaries."""
import hashlib
import importlib.util
import json
import re
import shlex
import subprocess
import sys
import tempfile
import unittest
from grouped_terms import default_entries, write_default_table
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PIPELINE = ROOT / 'skills/daggerheart-translation-pipeline'
RESOURCES = PIPELINE / 'resources'
REFERENCE = RESOURCES / 'reference'
CORE = RESOURCES / 'terms-core.json'
BASELINE = ROOT / 'tests/fixtures/srd2-glossary-baseline.json'
SOURCE_MAP = REFERENCE / 'srd2-additions-source-map.json'
CONTEXT = REFERENCE / 'srd2-context-only.json'
EXPECTED = {
    'Dread': '恐怖', 'Assassin': '刺客', 'Brawler': '格斗家',
    'Warlock': '邪术师', 'Witch': '灵巫',
    'Executioners Guild': '执刑公会', 'Poisoners Guild': '毒师公会',
    'Juggernaut': '重拳主宰', 'Martial Artist': '武艺达人',
    'Pact of the Endless': '无尽之契', 'Pact of the Wrathful': '愤怒之契',
    'Hedge': '树篱集会', 'Moon': '月亮集会',
    'Aetheris': '天辉族', 'Elemental Kin': '元素裔', 'Earthkin': '地裔',
    'Emberkin': '烬裔', 'Skykin': '空裔', 'Tidekin': '潮裔', 'Gnome': '侏儒',
    'Duneborne': '沙丘之民', 'Freeborne': '自由之民', 'Frostborne': '霜雪之民',
    'Hearthborne': '炉火之民', 'Reborne': '失乡之民', 'Warborne': '战乱之民',
    'Transformation': '转变', 'Demigod': '半神', 'Ghost': '鬼魂',
    'Reanimated': '复生者', 'Shapeshifter': '变形者', 'Vampire': '吸血鬼',
    'Werewolf': '狼人', 'Combo Die': '连击骰', 'Patron Die': '宗主骰',
    'Focus': '专注点', 'Favor': '恩惠点', 'Patron': '宗主',
    'Sphere of Influence': '权能领域', 'Martial Stance': '武术架势',
    'Hexed': '诅咒', 'Marked for Death': '死亡标记',
}
CONTEXT_NAMES = {'Hedge', 'Moon', 'Transformation', 'Ghost', 'Focus', 'Favor'}
FRAME_NAMES = {
    'Age of Umbra': '暗影纪元', 'Beast Feast': '野兽饭',
    'Colossus of the Drylands': '旱土巨像', 'Five Banners Burning': '五旗成焰',
    'Motherboard': '主板', 'Witherwild': '秽野之息',
}


def read_json(path):
    return json.loads(path.read_text(encoding='utf-8'))


def digest(record):
    data = json.dumps(record, ensure_ascii=False, sort_keys=True, separators=(',', ':'))
    return hashlib.sha256(data.encode('utf-8')).hexdigest()


def forms(entry):
    return [entry['term'], *entry.get('variants', [])]


def aliases_overlap(left, right):
    return any(a == b if left.get('case_sensitive') and right.get('case_sensitive')
               else a.casefold() == b.casefold()
               for a in forms(left) for b in forms(right))


class Srd2AdditionsTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.core = default_entries()
        cls.temp = tempfile.TemporaryDirectory()
        cls.addClassCleanup(cls.temp.cleanup)
        cls.active_table = write_default_table(Path(cls.temp.name) / 'terms.json')
        cls.baseline = read_json(BASELINE)
        cls.source_map = read_json(SOURCE_MAP)
        cls.sources = {e['term']: e for e in cls.source_map['entries']}
        cls.context_doc = read_json(CONTEXT)
        cls.context = {e['term']: e for e in cls.context_doc['entries']}
        cls.cleanup = read_json(REFERENCE / 'glossary-cleanup-decisions.json')
        cls.new = [e for e in cls.core if e['term'] in set(EXPECTED) - CONTEXT_NAMES]
        spec = importlib.util.spec_from_file_location('srd2_replace_terms', PIPELINE / 'scripts/replace_terms.py')
        cls.matcher = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(cls.matcher)

    def test_exact_counts_and_authorized_set(self):
        # Keep the 2026-10-14 cleanup count historical; track later approved additions.
        later_additions = {'reroll'}
        manifest = read_json(RESOURCES / 'term-groups.json')
        self.assertEqual(len(self.core), sum(g['count'] for g in manifest['groups'] if g['default']))
        self.assertTrue(later_additions <= {e['term'] for e in self.core})
        self.assertEqual(len(self.new), 36)
        self.assertEqual(len(self.context), 6)
        self.assertEqual({e['term'] for e in self.new}, set(EXPECTED) - CONTEXT_NAMES)
        self.assertEqual(set(self.context), CONTEXT_NAMES)
        self.assertEqual(set(self.sources), set(EXPECTED))
        scoped = list((RESOURCES / 'scoped').glob('*.json'))
        self.assertEqual(len(scoped), 2)
        self.assertEqual(sum(len(read_json(p)) for p in scoped), 2)
        self.assertEqual({e['finding_id'] for e in self.sources.values()},
                         {'A001', 'A002', 'A003', 'A004', 'A005', 'A006', 'A009'})

    def test_every_legacy_record_has_authorized_traceable_disposition(self):
        # First-addition immutability is historical. Owner subsequently authorized cleanup.
        self.assertEqual(len(self.baseline['legacy_records']), 326)
        decisions = {e['term']: e for e in self.cleanup['legacy_decisions']}
        manifest = read_json(RESOURCES / 'term-groups.json')
        active = {e['term']: e for g in manifest['groups'] for e in read_json(RESOURCES / g['file'])}
        contextual = read_json(REFERENCE / 'contextual-usage.json')['entries']
        for old in self.baseline['legacy_records']:
            with self.subTest(term=old['term']):
                d = decisions[old['term']]
                self.assertEqual(d['before_sha256'], old['sha256'])
                self.assertTrue(d['reason'])
                if d['action'] in {'keep', 'normalize'}:
                    self.assertEqual(digest(active[d['destination_term']]), d['after_sha256'])
                    if d['action'] == 'keep':
                        self.assertEqual(d['after_sha256'], old['sha256'])
                elif d['action'] == 'context_reference':
                    records = [x for x in contextual if x['term'] == old['term'] and x.get('usage') == 'context_required']
                    self.assertEqual(len(records), 1)
                    self.assertEqual(digest(records[0]['original_entry']), old['sha256'])
                else:
                    self.assertEqual(d['action'], 'merge_duplicate')
                    self.assertIn(d['destination_term'], active)

    def test_existing_tables_and_matching_code_unchanged(self):
        for relative, expected_hash in self.baseline['protected_files'].items():
            with self.subTest(path=relative):
                authorized = self.cleanup['authorized_protected_file_changes'].get(relative)
                if authorized:
                    self.assertEqual(authorized['before_sha256'], expected_hash)
                    expected_hash = authorized['after_sha256']
                if '/scripts/' in relative and not relative.endswith('/makeup.py'):
                    self.assertEqual(hashlib.sha256((ROOT / relative).read_bytes().replace(b'\r\n', b'\n')).hexdigest(), expected_hash)

    def test_all_six_official_framework_names_preserved(self):
        core = {e['term']: e for e in self.core}
        for term, translation in FRAME_NAMES.items():
            self.assertEqual(core[term]['translation'], translation)
        self.assertNotIn('Colossal Power', core)
        self.assertNotIn('flavor profile', core)

    def test_exact_chinese_source_alignment_for_all_42(self):
        translations = {e['term']: e['translation'] for e in self.new}
        translations.update({t: e['current_source_translation'] for t, e in self.context.items()})
        self.assertEqual(translations, EXPECTED)
        self.assertEqual(self.source_map['snapshot']['record_count'], 1777)
        self.assertRegex(self.source_map['snapshot']['sha256'], r'^[0-9a-f]{64}$')
        for term, expected_cn in EXPECTED.items():
            with self.subTest(term=term):
                source = self.sources[term]
                self.assertEqual(source['source_translation'], expected_cn)
                self.assertIn(expected_cn, source['translation_excerpt'])
                self.assertEqual(source['source_key'], f"SRD2_SECTION_{source['source_id'] - 1052583239}")
                self.assertEqual(source['source_file'], 'SRD/DH_SRD_2_2026_08_25.md.json')
                self.assertGreaterEqual(source['pdf_page'], 7)
                self.assertLessEqual(source['pdf_page'], 45)
                self.assertTrue(source['pdf_url'].endswith(f"#page={source['pdf_page']}"))
                self.assertIn(str(source['source_id']), source['source_url'])
                for field in ('original_sha256', 'translation_sha256'):
                    self.assertRegex(source[field], r'^[0-9a-f]{64}$')
        favor = self.context['Favor']
        self.assertEqual(favor['source_feature_title_translation'], '恩惠')
        self.assertEqual(favor['current_source_translation'], '恩惠点')

    def test_context_choices_are_resolved_and_not_matcher_schema(self):
        self.assertEqual(self.context_doc['usage'], 'read-only-context-reference')
        self.assertIs(self.context_doc['automatic_matching'], False)
        self.assertNotIsInstance(self.context_doc, list)
        for term, entry in self.context.items():
            with self.subTest(term=term):
                self.assertIs(entry['automatic_matching'], False)
                self.assertNotIn('translation', entry)
                self.assertIn(entry['status'], {'context_required'})
                self.assertTrue(entry['domain'])
                self.assertTrue(entry['context'])
                self.assertEqual(entry['resolved_translation'], EXPECTED[term])
                self.assertEqual(entry['source_id'], self.sources[term]['source_id'])
        self.assertEqual(self.context['Ghost']['existing_mapping']['translation'], '幽灵形态')
        self.assertEqual(self.context['Ghost']['status'], 'context_required')

    def test_context_reference_is_visible_to_writing_skill(self):
        writing = ROOT / 'skills/daggerheart-chinese-writing'
        skill = (writing / 'SKILL.md').read_text(encoding='utf-8')
        reference = (writing / 'REFERENCE.md').read_text(encoding='utf-8')
        self.assertIn('REFERENCE.md', skill)
        self.assertIn('../daggerheart-translation-pipeline/resources/reference/srd2-context-only.json', reference)
        self.assertIn('不作为自动替换表', reference)
        self.assertIn('实体选择按已记录上下文执行', reference)

    def test_no_unhandled_active_alias_collision(self):
        tables = [('terms-core.json', [e for e in self.core if e not in self.new])]
        tables += [(p.name, read_json(p)) for p in RESOURCES.glob('adversaries_*.json')]
        overlaps = set()
        for entry in self.new:
            for table, old_entries in tables:
                for old in old_entries:
                    if aliases_overlap(entry, old):
                        overlaps.add((entry['term'], table, old['term']))
                        self.assertEqual(entry['translation'], old['translation'])
            for other in self.new:
                if entry is not other:
                    self.assertFalse(aliases_overlap(entry, other), (entry['term'], other['term']))
        self.assertTrue(all(term == 'Vampire' and table == 'adversaries_name.json' for term, table, _ in overlaps))
        approved = self.source_map['allowed_same_translation_alias_reuse']
        self.assertEqual(len(approved), 1)
        self.assertEqual(approved[0]['new_term'], 'Vampire')
        self.assertIn('按正文辨别实体', approved[0]['reason'])

    def test_every_new_standard_and_attested_alias_marks_correctly(self):
        for entry in self.new:
            with self.subTest(term=entry['term']):
                self.assertIs(entry['case_sensitive'], True)
                self.assertEqual(len(forms(entry)), len(set(forms(entry))))
                source = self.sources[entry['term']]
                self.assertEqual(source['active_forms'], forms(entry))
                alias_evidence = {e['form']: e for e in source['alias_evidence']}
                self.assertEqual(set(alias_evidence), set(entry.get('variants', [])))
                for form in forms(entry):
                    tagged = self.matcher.replace_terms(form, str(self.active_table))
                    self.assertIn(f"【{form}｜{entry['translation']}｜", tagged)
                    if form != entry['term']:
                        self.assertIn(form, alias_evidence[form]['original_excerpt'])
        self.assertIn('Patron Dice', next(e for e in self.new if e['term'] == 'Patron Die')['variants'])
        self.assertIn('Werewolves', next(e for e in self.new if e['term'] == 'Werewolf')['variants'])

    def test_ordinary_lowercase_bare_words_are_not_new_aliases(self):
        text = 'dread juggernaut reanimated patron hexed hedge moon transformation ghost focus favor'
        self.assertEqual(self.matcher.replace_terms(text, str(self.active_table)), text)
        for term in ('Dread', 'Juggernaut', 'Reanimated', 'Patron', 'Hexed'):
            entry = next(e for e in self.new if e['term'] == term)
            self.assertNotIn(term.lower(), forms(entry))

    def test_default_pipeline_excludes_context_and_does_not_globally_override_ghost(self):
        skill = (PIPELINE / 'SKILL.md').read_text(encoding='utf-8')
        command = next(line for line in skill.splitlines() if line.startswith('python scripts/merge_terms.py'))
        self.assertNotIn('reference/', command)
        self.assertNotIn('scoped/', command)
        self.assertNotIn('*', command)
        with tempfile.TemporaryDirectory() as directory:
            tmp = Path(directory)
            original = tmp / 'original.md'
            original.write_text(' '.join(EXPECTED) + ' Patron Dice Ghost VAMPIRE', encoding='utf-8')
            project = tmp / 'project.json'
            project.write_text('[]', encoding='utf-8')
            output = tmp / 'merged.json'
            args = shlex.split(command)
            args[0] = sys.executable
            args[1] = str(PIPELINE / args[1])
            for i, arg in enumerate(args):
                if arg.startswith('resources/'):
                    args[i] = str(PIPELINE / arg)
                elif arg == 'glossary/_glossary.json':
                    args[i] = str(project)
                elif arg == 'source/temp/_merged_terms.json':
                    args[i] = str(output)
                elif arg == 'source/_original.md':
                    args[i] = str(original)
            result = subprocess.run(args, capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            merged = read_json(output)
            names = {e['term']: e for e in merged}
            self.assertFalse((CONTEXT_NAMES - {'Focus', 'Favor'}) & names.keys())
            self.assertNotIn('Ghost', names)
            self.assertFalse(any(e['translation'] == '鬼魂' for e in merged))
            tagged = self.matcher.replace_terms('Ghost Patron Die Patron Dice VAMPIRE', str(output))
            self.assertIn('Ghost ', tagged)
            self.assertNotIn('【Ghost｜', tagged)
            self.assertIn('【Patron Die｜宗主骰｜', tagged)
            self.assertIn('【Patron Dice｜宗主骰｜', tagged)
            self.assertIn('【VAMPIRE｜吸血鬼', tagged)
            self.assertNotIn('【Patron｜', tagged)


if __name__ == '__main__':
    unittest.main()
