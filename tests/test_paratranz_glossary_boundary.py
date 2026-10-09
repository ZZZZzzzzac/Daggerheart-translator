from pathlib import Path
import unittest
ROOT=Path(__file__).resolve().parents[1]
class GlossaryBoundaryTests(unittest.TestCase):
 def test_export_snapshot_is_not_core_or_default_scoped_input(self):
  doc=(ROOT/'skills/paratranz-ops/SKILL.md').read_text()
  for text in ['terms-core.json','独立快照','不能自动覆盖','只按项目显式选用','不默认合并']:
   self.assertIn(text,doc)
  self.assertTrue((ROOT/'skills/daggerheart-translation-pipeline/resources/terms-core.json').is_file())
  self.assertTrue((ROOT/'skills/daggerheart-translation-pipeline/resources/README.md').is_file())
if __name__=='__main__':unittest.main()
