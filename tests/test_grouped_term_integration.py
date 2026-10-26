"""Synthetic/default-manifest integration; no translation quality claims."""
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('grouped_pipeline', ROOT / 'experiments/context_contract/pipeline.py')
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)


class GroupedIntegrationTests(unittest.TestCase):
    def test_complete_default_groups_and_migrated_candidates(self):
        expected = [e for p in m.default_term_paths() for e in m.read_json(p)]
        self.assertEqual(m.merged_terms(), list({e['term']: e for e in expected}.values()))
        self.assertEqual(len(expected), 939)
        self.assertEqual(len(m.default_term_paths()), 11)
        terms = m.merged_terms()
        self.assertIn('Motherboard', {e['term'] for e in terms})
        self.assertNotIn('Arcane', {e['term'] for e in terms})
        hits = m.candidates('Motherboard uses Hope. hope remains an ordinary possibility.', terms)
        self.assertTrue(any(h['term'] == 'Motherboard' for h in hits))
        self.assertTrue(any(h['quote'] == 'hope' and h['match'] == 'case-review' for h in hits))

    def fixture(self, root, entries, extra=None):
        groups = []
        for i, rows in enumerate(entries):
            name = f'group{i}.json'
            m.dump(root / name, rows)
            groups.append({'file': name, 'default': True})
        m.dump(root / 'disabled.json', [{'term': 'Disabled', 'translation': '禁用'}])
        groups.append({'file': 'disabled.json', 'default': False})
        (root / 'scoped').mkdir()
        m.dump(root / 'scoped/unused.json', [{'term': 'Scoped', 'translation': '范围'}])
        (root / 'reference').mkdir()
        m.dump(root / 'reference/unused.json', {'entries': [{'term': 'Context'}]})
        if extra:
            groups.append(extra)
        m.dump(root / 'term-groups.json', {'groups': groups})

    def test_exclusion_and_identical_duplicate(self):
        entry = {'term': 'Sample', 'translation': '示例', 'variants': ['Samples']}
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self.fixture(root, [[entry], [entry]])
            with patch.object(m, 'RES', root):
                self.assertEqual(m.merged_terms(), [entry])

    def test_conflicts_require_review_including_aliases_and_case(self):
        first = {'term': 'Sample', 'translation': '示例', 'variants': ['Samples']}
        for other in [
            {'term': 'Sample', 'translation': '另一译名'},
            {'term': 'sample', 'translation': '另一译名'},
            {'term': 'Other', 'translation': '另一译名', 'variants': ['SAMPLES']},
            {'term': 'Sample', 'translation': '示例', 'note': 'different scope'},
        ]:
            with self.subTest(other=other), tempfile.TemporaryDirectory() as tmp:
                root = Path(tmp)
                self.fixture(root, [[first], [other]])
                with patch.object(m, 'RES', root), self.assertRaisesRegex(ValueError, 'requires review'):
                    m.merged_terms()

    def test_same_translation_different_scope_keeps_both_candidate_notes(self):
        entries = [
            {'term': 'Sample', 'translation': '示例', 'note': 'feature scope', 'case_sensitive': True},
            {'term': 'sample', 'translation': '示例', 'note': 'type scope'},
        ]
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self.fixture(root, [[entries[0]], [entries[1]]])
            with patch.object(m, 'RES', root):
                terms = m.merged_terms()
            self.assertEqual(terms, entries)
            hits = m.candidates('sample', terms)
            self.assertEqual(len(hits), 2)
            self.assertEqual({h['note'] for h in hits}, {'feature scope', 'type scope'})
            self.assertEqual({h['match'] for h in hits}, {'declared-form', 'case-review'})
            self.assertEqual(len({h['id'] for h in hits}), 2)
            packet = m.compact_units([{'id': 'synthetic', 'source': 'sample', 'candidates': hits}])
            self.assertEqual({g['note'] for g in packet['glossary'].values()}, {'feature scope', 'type scope'})
            self.assertEqual(len(packet['units'][0]['occurrences_id_start_end_glossary_match']), 2)

    def test_scoped_or_context_groups_cannot_be_enabled_as_defaults(self):
        for name in ['scoped/unused.json', 'reference/unused.json', '../outside.json']:
            with self.subTest(name=name), tempfile.TemporaryDirectory() as tmp:
                root = Path(tmp)
                self.fixture(root, [[{'term': 'Sample', 'translation': '示例'}]], {'file': name, 'default': True})
                with patch.object(m, 'RES', root), self.assertRaises(ValueError):
                    m.merged_terms()

    def test_prepare_freezes_manifest_all_groups_and_actual_implementation(self):
        with tempfile.TemporaryDirectory() as tmp:
            run = Path(tmp) / 'new-run'
            manifest = m.prepare([{'id': 'synthetic', 'source': 'Motherboard uses Hope.'}], run)
            for p in [m.RES / 'term-groups.json', *m.default_term_paths(), m.BASE / 'scripts/makeup.py']:
                self.assertEqual(manifest['rules'][str(p.relative_to(ROOT))], m.digest(p.read_bytes()))
            self.assertNotIn('base_commit', manifest)
            self.assertIn('working_tree_dirty', manifest['implementation'])
            self.assertIn('Motherboard', {h['term'] for h in m.read_json(run / 'candidate-units.json')[0]['candidates']})
            with self.assertRaisesRegex(ValueError, 'overwrite'):
                m.prepare([{'id': 'synthetic', 'source': 'Other.'}], run)
            group = m.default_term_paths()[-1]
            original = Path.read_bytes
            def changed(path):
                data = original(path)
                return data + b' ' if path == group else data
            with patch.object(Path, 'read_bytes', changed), self.assertRaisesRegex(ValueError, 'frozen rule changed'):
                m.freeze(run)


if __name__ == '__main__':
    unittest.main()
