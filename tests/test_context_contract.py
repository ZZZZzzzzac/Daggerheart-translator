import importlib.util,json,tempfile,unittest
from pathlib import Path
P=Path(__file__).resolve().parents[1]/'experiments/context_contract/pipeline.py'
spec=importlib.util.spec_from_file_location('contract',P);m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
class ContractTests(unittest.TestCase):
 def test_source_is_immutable(self):
  source='Once per long\nrest, _Hope_ costs 1d6. [Hope](https://x.test/Hope)'
  original=source[:]; hits=m.candidates(source,[{'term':'Once per long rest','translation':'每长休一次'},{'term':'Hope','translation':'希望点','case_sensitive':True}])
  self.assertEqual(source,original)
  self.assertEqual([h['quote'] for h in hits],['Once per long\nrest','Hope','Hope'])
  for h in hits:self.assertEqual(source[h['start']:h['end']],h['quote'])
 def test_case_is_not_semantics(self):
  hits=m.candidates('hope Hope',[{'term':'Hope','translation':'希望点','case_sensitive':True}])
  self.assertEqual([h['match'] for h in hits],['case-review','declared-form'])
 def test_long_phrase_retains_overlap(self):
  h=m.candidates('Hope Die',[{'term':'Hope','translation':'希望点'},{'term':'Hope Die','translation':'希望骰'}])
  self.assertEqual([x['term'] for x in h],['Hope Die','Hope'])
 def test_once_template_is_strict(self):
  h=m.candidates('Once per long rest',[{'term':'Once per long rest','translation':'每长休一次'}])
  self.assertEqual(m.lint('Once per long rest','每次长休限一次',h)[0]['kind'],'fixed_template_missing')
  self.assertEqual(m.lint('Once per long rest','每长休一次',h),[])
 def test_no_reference_leakage(self):
  with tempfile.TemporaryDirectory() as d:
   run=Path(d)/'run';m.prepare([{'id':'a','source':'One tree.','reference':'秘密金标准'}],run)
   for p in run.rglob('*'):
    if p.is_file():self.assertNotIn('秘密金标准',p.read_text())
   self.assertEqual(json.loads((run/'sources.json').read_text())[0]['source'],'One tree.')
   with self.assertRaises(ValueError):m.prepare([{'id':'a','source':'One tree.'}],run)
 def test_duplicate_identity_rejected(self):
  with self.assertRaises(ValueError):m.validate_cases([{'id':'x','source':'a'},{'id':'x','source':'b'}])
 def test_evidence_validation_not_auto_approval(self):
  h=m.candidates('Hope',[{'term':'Hope','translation':'希望点'}]);u=[{'id':'x','source':'Hope','candidates':h}]
  r={'units':[{'id':'x','translation':'希望点','applied':['t1'],'exceptions':[],'mechanics':[],'questions':[]}]}
  self.assertEqual(m.validate_candidate(u,r),[])
  r['units'][0]['translation']='不存在'
  self.assertTrue(m.validate_candidate(u,r))
 def test_dice_multiplicity(self):
  self.assertTrue(m.lint('1d6 plus 1d6','1d6',[]))
 def test_html_escapes_source(self):
  with tempfile.TemporaryDirectory() as d:
   p=Path(d);m.dump(p/'sources.json',[{'id':'x','source':'<script>alert(1)</script>'}]);m.dump(p/'candidate-final.json',{'units':[{'id':'x','translation':'<img onerror=x>'}]});m.render(p)
   html=(p/'candidate-comparison.html').read_text();self.assertIn('&lt;script&gt;',html);self.assertNotIn('<script>',html)
 def test_freeze_and_blinding(self):
  with tempfile.TemporaryDirectory() as d:
   run=Path(d)/'run';m.prepare([{'id':'a','source':'A tree.'}],run)
   units=m.read_json(run/'candidate-units.json');self.assertEqual(units[0]['candidates'],[])
   output={'units':[{'id':'a','translation':'一棵树。','applied':[],'exceptions':[],'mechanics':[],'questions':[]}]}
   m.dump(run/'candidate-draft.json',output)
   chunk=(run/'baseline/chunks/a.md').read_text().replace('A tree.','一棵树。')
   (run/'baseline/drafts/a.md').write_text(chunk)
   m.review_packets(run)
   m.dump(run/'candidate-final.json',output);(run/'baseline/finals/a.md').write_text(chunk)
   m.dump(run/'baseline-review-log.json',{'questions':[],'changes':[]})
   frozen=m.freeze(run);self.assertEqual(frozen['structural_errors'],[])
   with self.assertRaises(ValueError):m.freeze(run)
   refs=Path(d)/'refs.json';m.dump(refs,[{'id':'a','reference':'一棵树。'}]);self.assertEqual(m.blind(run,refs)['units'],1)
   (run/'candidate-delivery.json').write_text('{}')
   with self.assertRaises(ValueError):m.blind(run,refs)
 def test_reject_source_mutation_before_freeze(self):
  with tempfile.TemporaryDirectory() as d:
   run=Path(d)/'run';m.prepare([{'id':'a','source':'A tree.'}],run)
   (run/'sources.json').write_text('[]')
   with self.assertRaises(ValueError):m.freeze(run)
if __name__=='__main__':unittest.main()
