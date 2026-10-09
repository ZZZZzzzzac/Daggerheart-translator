"""Offline synthetic-example contract tests; not semantic-quality measurements."""
import json
from pathlib import Path
import unittest
ROOT=Path(__file__).resolve().parents[1]
WRITING=ROOT/'skills/daggerheart-chinese-writing'
class ReferenceExampleTests(unittest.TestCase):
 def setUp(self):
  self.data=json.loads((WRITING/'examples/synthetic-review-examples.json').read_text())
 def test_small_advisory_examples_are_discoverable(self):
  self.assertEqual(self.data['status'],'advisory_examples_only')
  self.assertEqual(len(self.data['examples']),2)
  self.assertIn('examples/synthetic-review-examples.json',(WRITING/'REFERENCE.md').read_text())
 def test_no_licensed_corpus_or_user_approval(self):
  self.assertEqual(self.data['provenance']['kind'],'synthetic')
  self.assertNotIn('reviewed_decisions',self.data)
  self.assertNotIn('replacements',self.data)
  for e in self.data['examples']:
   for k in ['id','type','source','comparison_zh','illustrative_revision_zh','lesson']:
    self.assertTrue(isinstance(e[k],str) and e[k].strip())
 def test_clarity_and_fidelity_are_distinguished(self):
  self.assertEqual([e['type'] for e in self.data['examples']],['contextual_clarity','source_fidelity'])
  self.assertTrue(self.data['usage_limits'])
if __name__=='__main__':unittest.main()
