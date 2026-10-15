import copy,importlib.util,unittest,tempfile
from pathlib import Path
p=Path(__file__).resolve().parents[1]/'experiments/context_contract/two_pass.py';s=importlib.util.spec_from_file_location('tp',p);m=importlib.util.module_from_spec(s);s.loader.exec_module(m)
class TwoPassTests(unittest.TestCase):
 def setUp(self):
  self.src=[{'id':'a','source':'Once per long rest, gain 1 Hope.'}]
  self.d={'units':[{'id':'a','translation':'每长休一次，获得 1 希望点。','invariants':[{'id':'i1','source_quote':'gain 1 Hope','meaning':'获得1希望点'}],'protected_phrases':[{'id':'p1','source_quote':'Once per long rest','target_phrase':'每长休一次','scope':'固定频率'}],'questions':[]}]}
  self.f={'units':[{'id':'a','translation':'每长休一次，获得 1 希望点。','invariant_checks':[{'invariant_id':'i1','source_quote':'gain 1 Hope','target_quote':'获得 1 希望点','verdict':'preserved','note':''}],'phrase_exceptions':[],'changes':[],'ambiguity_checks':[{'source_quote':'gain 1 Hope','target_quote':'获得 1 希望点','verdict':'no_new_ambiguity'}],'questions':[]}]}
 def test_valid_structure(self):self.assertEqual(m.validate_draft(self.src,self.d)+m.validate_final(self.src,self.d,self.f),[])
 def test_missing_lock_not_silent(self):
  self.f['units'][0]['invariant_checks']=[];self.assertTrue(m.validate_final(self.src,self.d,self.f))
 def test_no_synonym_template_escape(self):
  self.f['units'][0]['translation']=self.f['units'][0]['translation'].replace('每长休一次','每次长休限一次')
  self.f['units'][0]['changes']=[{'before':'每长休一次','after':'每次长休限一次','kind':'wording_only','invariant_ids':[],'reason':'same meaning'}]
  self.assertIn('a: protected phrase changed: p1',m.validate_final(self.src,self.d,self.f))
 def test_changed_draft_needs_audit(self):
  self.f['units'][0]['translation']+='你笑了。';self.assertTrue(m.validate_final(self.src,self.d,self.f))
 def test_correction_must_explain_original(self):
  self.f['units'][0]['invariant_checks'][0]['verdict']='source_correction';self.assertTrue(m.validate_final(self.src,self.d,self.f))
 def test_fake_evidence_rejected(self):
  self.d['units'][0]['invariants'][0]['source_quote']='spend 2 Hope';self.assertTrue(m.validate_draft(self.src,self.d))
 def test_no_blindly_locked_first_error(self):
  self.d['units'][0]['translation']='每长休一次，花费 1 希望点。'
  self.d['units'][0]['invariants'][0]['meaning']='花费1希望点'
  self.f['units'][0]['invariant_checks'][0].update(verdict='source_correction',note='源文gain，不是spend')
  self.f['units'][0]['changes']=[{'before':'花费 1 希望点','after':'获得 1 希望点','kind':'source_correction','invariant_ids':['i1'],'reason':'gain means获得'}]
  self.assertEqual(m.validate_final(self.src,self.d,self.f),[])
 def test_duplicate_phrase_exception(self):
  x={'phrase_id':'p1','source_quote':'Once per long rest','reason':'test'};self.f['units'][0]['phrase_exceptions']=[x,x];self.assertTrue(m.validate_final(self.src,self.d,self.f))
 def test_candidate_final_not_rewritten_by_makeup(self):
  with tempfile.TemporaryDirectory() as tmp:
   run=Path(tmp)/'run';m.prepare(self.src,run)
   self.d['units'][0]['translation']='每长休一次，获得 1 希望点。已标记的生命点。'
   self.f['units'][0]['translation']=self.d['units'][0]['translation']
   m.v1.dump(run/'candidate-draft.json',self.d);m.v1.dump(run/'candidate-final.json',self.f)
   frozen=m.freeze(run,development=True)
   self.assertEqual(frozen['structural_errors'],[])
   self.assertEqual(m.v1.read_json(run/'candidate-delivery.json')['units'][0]['translation'],self.f['units'][0]['translation'])
   with self.assertRaises(ValueError):m.freeze(run,development=True)
 def test_polish_locks_first_stage(self):
  with tempfile.TemporaryDirectory() as tmp:
   run=Path(tmp)/'run';m.prepare(self.src,run)
   m.v1.dump(run/'candidate-draft.json',self.d);m.polish_packet(run,main=False)
   m.v1.dump(run/'candidate-final.json',self.f)
   self.d['units'][0]['translation']+='modified'
   m.v1.dump(run/'candidate-draft.json',self.d)
   with self.assertRaisesRegex(ValueError,'stage input changed'):m.freeze(run,development=True)
 def test_dependency_rules_include_formatter_and_protocol(self):
  with tempfile.TemporaryDirectory() as tmp:
   run=Path(tmp)/'run';manifest=m.prepare(self.src,run)
   for name in ['experiments/context_contract/protocol-v2.json','skills/daggerheart-translation-pipeline/scripts/makeup.py','skills/daggerheart-term-checker/scripts/strip_term_markers.py']:
    self.assertIn(name,manifest['rules'])
 def test_markdown_spacing_not_false_template_violation(self):
  self.f['units'][0]['translation']='**每长休一次**，获得 1 希望点。'
  self.f['units'][0]['changes']=[{'before':'每长休一次','after':'**每长休一次**','kind':'wording_only','invariant_ids':[],'reason':'仅加粗'}]
  self.assertEqual(m.validate_final(self.src,self.d,self.f),[])
 def test_malformed_schema_returns_findings(self):
  self.d['units'][0]['translation']=123
  self.assertTrue(m.validate_draft(self.src,self.d))
  self.assertTrue(m.validate_draft(self.src,{'units':None}))
  self.f['units'][0]['invariant_checks']=None
  self.assertTrue(m.validate_final(self.src,self.d,self.f))
 def test_no_op_change_rejected(self):
  self.f['units'][0]['changes']=[{'before':'每长休一次','after':'每长休一次','kind':'wording_only','reason':'none','invariant_ids':[]}]
  self.assertTrue(m.validate_final(self.src,self.d,self.f))
 def test_preserved_anchor_cannot_switch_claim(self):
  self.f['units'][0]['invariant_checks'][0]['source_quote']='Once per long rest'
  self.assertTrue(m.validate_final(self.src,self.d,self.f))
 def test_invalid_schema_freezes_raw_failure(self):
  with tempfile.TemporaryDirectory() as tmp:
   run=Path(tmp)/'run';m.prepare(self.src,run)
   m.v1.dump(run/'candidate-draft.json',{'units':None});m.v1.dump(run/'candidate-final.json',self.f)
   result=m.freeze(run,development=True)
   self.assertEqual(result['status'],'frozen-invalid-schema')
   self.assertFalse((run/'candidate-delivery.json').exists())
 def test_unknown_ids_rejected(self):
  self.f['units'][0]['id']='b';self.assertTrue(m.validate_final(self.src,self.d,self.f))
if __name__=='__main__':unittest.main()
