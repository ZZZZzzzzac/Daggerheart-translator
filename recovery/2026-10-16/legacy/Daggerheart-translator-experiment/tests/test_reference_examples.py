"""Offline corpus/schema guards; not a translation-quality or model-behavior test."""
import json
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
WRITING = ROOT / 'skills/daggerheart-chinese-writing'
CORPUS = WRITING / 'examples/source-grounded-reference.json'


class ReferenceExampleTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.data = json.loads(CORPUS.read_text(encoding='utf-8'))

    def test_small_advisory_schema_and_discoverability(self):
        data = self.data
        self.assertEqual(data['schema_version'], 1)
        self.assertEqual(data['status'], 'advisory_examples_only')
        self.assertEqual(len(data['examples']), 2)
        self.assertEqual(len({e['id'] for e in data['examples']}), 2)
        self.assertIn('examples/source-grounded-reference.json',
                      (WRITING / 'REFERENCE.md').read_text(encoding='utf-8'))
        self.assertNotIn('reviewed_decisions', data)
        self.assertNotIn('replacements', data)
        for example in data['examples']:
            for field in ('id', 'type', 'assessment', 'section', 'source_excerpt',
                          'source_url', 'human_excerpt', 'human_url', 'comparison_zh',
                          'context', 'context_url', 'lesson', 'scope'):
                self.assertIsInstance(example[field], str)
                self.assertTrue(example[field].strip())

    def test_source_links_are_pinned_and_credit_is_joint(self):
        provenance = self.data['provenance']
        commit = provenance['commit']
        self.assertRegex(commit, r'^[a-f0-9]{40}$')
        base = f"https://github.com/{provenance['repository']}/blob/{commit}/"
        links = [provenance['source']['url'], provenance['human_reference']['url'],
                 provenance['human_reference']['byline_url']]
        for item in self.data['examples'] + [self.data['reference_caution']]:
            links.extend(value for field, value in item.items() if field.endswith('_url'))
        self.assertTrue(all(link.startswith(base) for link in links))
        self.assertEqual(provenance['human_reference']['byline'], '翻译：三得利乌龙茶，昆仑')
        self.assertEqual(provenance['human_reference']['edition'], '未明确标注')
        self.assertIn('Beta-1', provenance['source']['url'])
        self.assertTrue(provenance['pairing_limit'])
        for record in (provenance['source'], provenance['human_reference']):
            self.assertRegex(record['blob_sha'], r'^[a-f0-9]{40}$')

    def test_clarity_and_semantic_addition_are_not_conflated(self):
        access, location = self.data['examples']
        self.assertEqual(access['assessment'],
                         'stylistic_clarification_not_established_mechanical_error')
        self.assertEqual(location['assessment'],
                         'minor_semantic_embellishment_not_formal_rule_change')
        self.assertEqual(access['section'], 'SECTION_62')
        self.assertEqual(location['section'], 'SECTION_63')
        self.assertEqual(self.data['reference_caution']['source_excerpt'],
                         'fueling mighty new spells')
        self.assertTrue(self.data['usage_limits'])


if __name__ == '__main__':
    unittest.main()
