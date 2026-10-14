"""Core/project glossary boundary and pipeline regression tests (standard library)."""
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PIPELINE = ROOT / 'skills/daggerheart-translation-pipeline'
RESOURCES = PIPELINE / 'resources'
CORE = RESOURCES / 'terms-core.json'
COLOSSUS = RESOURCES / 'scoped/colossus-of-the-drylands.json'
BEAST_FEAST = RESOURCES / 'scoped/beast-feast.json'
FRAME_NAMES = {
    'Age of Umbra', 'Beast Feast', 'Colossus of the Drylands',
    'Five Banners Burning', 'Motherboard', 'Witherwild',
}


class CoreTermsTests(unittest.TestCase):
    def setUp(self):
        self.core = json.loads(CORE.read_text(encoding='utf-8'))
        self.colossus = json.loads(COLOSSUS.read_text(encoding='utf-8'))
        self.beast_feast = json.loads(BEAST_FEAST.read_text(encoding='utf-8'))
        self.scoped = self.colossus + self.beast_feast

    def test_resource_schema_and_unique_primary_terms(self):
        for entries in (self.core, self.scoped):
            self.assertIsInstance(entries, list)
            names = []
            for entry in entries:
                for field in ('term', 'translation'):
                    self.assertIsInstance(entry[field], str)
                    self.assertTrue(entry[field].strip())
                if 'variants' in entry:
                    self.assertIsInstance(entry['variants'], list)
                    self.assertTrue(all(isinstance(v, str) and v.strip() for v in entry['variants']))
                if 'note' in entry:
                    self.assertIsInstance(entry['note'], str)
                if 'case_sensitive' in entry:
                    self.assertIsInstance(entry['case_sensitive'], bool)
                names.append(entry['term'])
            self.assertEqual(len(names), len(set(names)))

    def test_official_campaign_names_remain_core(self):
        core_names = {e['term'] for e in self.core}
        self.assertTrue(FRAME_NAMES <= core_names)
        self.assertFalse(FRAME_NAMES & {e['term'] for e in self.scoped})
        self.assertFalse((RESOURCES / 'terms-14448.json').exists())

    def test_frame_mechanics_are_optional(self):
        names = {'flavor profile', 'Colossal Power'}
        self.assertFalse(names & {e['term'] for e in self.core})
        self.assertEqual({'Colossal Power'}, {e['term'] for e in self.colossus})
        self.assertEqual({'flavor profile'}, {e['term'] for e in self.beast_feast})
        self.assertFalse((RESOURCES / 'scoped/campaign-frame-mechanics.json').exists())

    def test_rule_categories_remain(self):
        names = {e['term'] for e in self.core}
        self.assertTrue({
            'Action Roll', 'Hope', 'Fear', 'Stress', 'Damage Threshold',
            'Bard', 'Warrior', 'Clank', 'Fungril', 'Highborne',
            'Arcana', 'Codex', 'Nightwalker', 'Bruiser', 'Horde', 'Minion',
            'Solo', 'Phase Change', 'CHAOS REALM', 'CIRCLES BELOW',
        } <= names)

    def test_documented_defaults_use_core_and_no_scoped_resources(self):
        text = (PIPELINE / 'SKILL.md').read_text(encoding='utf-8')
        command = next(line for line in text.splitlines() if line.startswith('python scripts/merge_terms.py'))
        self.assertIn('resources/terms-core.json', command)
        self.assertNotIn('terms-14448.json', command)
        self.assertNotIn('scoped/', command)

    def run_merge(self, project_entries, auto=False):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        path = Path(tmp.name)
        (path / 'original.md').write_text('Hope and action rolls in Motherboard. Colossal Power and flavor profile.', encoding='utf-8')
        (path / 'project.json').write_text(json.dumps(project_entries, ensure_ascii=False), encoding='utf-8')
        command = [sys.executable, str(PIPELINE / 'scripts/merge_terms.py'),
                   '--terms', str(CORE), str(path / 'project.json'),
                   '--output', str(path / 'merged.json'), '--original', str(path / 'original.md')]
        if auto:
            command.append('--auto-resolve')
        result = subprocess.run(command, capture_output=True, text=True)
        return result, path

    def test_default_merge_does_not_reintroduce_scoped_name(self):
        result, path = self.run_merge([])
        self.assertEqual(result.returncode, 0, result.stderr)
        entries = json.loads((path / 'merged.json').read_text(encoding='utf-8'))
        self.assertIn('Motherboard', {e['term'] for e in entries})
        self.assertNotIn('Colossal Power', {e['term'] for e in entries})
        self.assertNotIn('flavor profile', {e['term'] for e in entries})
        self.assertIn('Action Roll', {e['term'] for e in entries})

    def test_project_can_opt_in_and_markers_still_work(self):
        entry = next(e for e in self.scoped if e['term'] == 'Colossal Power')
        result, path = self.run_merge([entry])
        self.assertEqual(result.returncode, 0, result.stderr)
        tagged = subprocess.run([sys.executable, str(PIPELINE / 'scripts/replace_terms.py'),
                                 str(path / 'original.md'), str(path / 'merged.json')],
                                capture_output=True, text=True, check=True).stdout
        self.assertIn('【Hope｜希望点】', tagged)
        self.assertIn('【action rolls｜动作掷骰】', tagged)
        self.assertIn('【Motherboard｜主板】', tagged)
        self.assertIn('【Colossal Power｜巨像之力】', tagged)
        self.assertNotIn('【flavor profile', tagged)

    def test_beast_feast_opt_in_does_not_load_colossus(self):
        result, path = self.run_merge(self.beast_feast)
        self.assertEqual(result.returncode, 0, result.stderr)
        names = {e['term'] for e in json.loads((path / 'merged.json').read_text(encoding='utf-8'))}
        self.assertIn('flavor profile', names)
        self.assertNotIn('Colossal Power', names)

    def test_conflicts_require_review_or_preserve_core_when_auto(self):
        project = [{'term': 'Hope', 'translation': '项目临时译名'}]
        result, path = self.run_merge(project)
        self.assertEqual(result.returncode, 1)
        self.assertFalse((path / 'merged.json').exists())
        report = json.loads((path / 'merged_conflicts.json').read_text(encoding='utf-8'))
        self.assertEqual(report['conflict_count'], 1)
        result, path = self.run_merge(project, auto=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        entries = json.loads((path / 'merged.json').read_text(encoding='utf-8'))
        self.assertEqual(next(e['translation'] for e in entries if e['term'] == 'Hope'), '希望点')


if __name__ == '__main__':
    unittest.main()
