import importlib.util,tempfile,unittest
from unittest.mock import patch
from pathlib import Path
s=importlib.util.spec_from_file_location('g',Path(__file__).resolve().parents[1]/'experiments/context_contract/delivery_gate.py');m=importlib.util.module_from_spec(s);s.loader.exec_module(m)
class GateTests(unittest.TestCase):
 def test_guardian_and_bard_are_blocked(self):self.assertEqual([x['text'] for x in m.inspect('守护者 Guardian 和吟游诗人 bard。')],['Guardian','bard'])
 def test_dice_and_link_targets_preserved(self):self.assertEqual(m.inspect('造成 1d6+2 点伤害，另掷 d8。见[此节](#page-107-0)和[资料](https://example.org/file.pdf)。'),[])
 def test_link_visible_english_still_blocked(self):self.assertTrue(m.inspect('[Guardian](https://example.org)'))
 def test_explicit_original_name_allowed(self):self.assertEqual(m.inspect('德贾·德瓦 Deja Deva。',{'allowed_latin':[{'text':'Deja Deva','reason':'明确保留原名的角色'}]}),[])
 def test_allowlist_is_not_blanket_ascii_amnesty(self):self.assertTrue(m.inspect('Deja Deva Guardian',{'allowed_latin':[{'text':'Deja Deva','reason':'specific name'}]}))
 def test_broken_markup_and_annotations_blocked(self):
  self.assertTrue(any(x['kind']=='unbalanced_bold' for x in m.inspect('护甲槽**')));self.assertTrue(any(x['kind']=='term_annotation' for x in m.inspect('【希望点｜希望点｜】')))
 def test_orphan_link_cannot_hide_english(self):
  f=m.inspect('守护者](Guardian)');self.assertTrue(any(x['kind']=='unapproved_latin' for x in f));self.assertTrue(any(x['kind']=='orphan_link_target' for x in f))
 def test_unclosed_chinese_comment_blocked(self):self.assertTrue(any(x['kind']=='review_comment' for x in m.inspect('<!-- 中文审阅备注')))
 def test_scan_rejects_missing_duplicate_and_malformed_units(self):
  src=[{'id':'a','source':'Guardian'},{'id':'b','source':'Hope'}]
  for target in [{'units':[]},{'units':[{'id':'a','translation':'守护者'}]},{'units':[{'id':'a','translation':'守护者'},{'id':'a','translation':'守护者'}]},{'units':None}]:self.assertFalse(m.scan_records(src,target)['release_allowed'])
 def test_bare_link_repeated_dice_and_required_name_preserved(self):
  f=m.inspect('掷 d6。',{'allowed_latin':[{'text':'Deja Deva','reason':'required name','required':True}]},source='Deja Deva rolls d6 then d6. See https://example.org/rules.')
  self.assertEqual({x['kind'] for x in f},{'missing_original_dice_expression','missing_source_link_target','missing_required_original_name'})
 def test_allowed_but_not_required_name_can_be_translated(self):
  self.assertEqual(m.inspect('德贾·德瓦来了。',{'allowed_latin':[{'text':'Deja Deva','reason':'optional source name'}]},source='Deja Deva arrives.'),[])
 def test_nonrendered_links_cannot_hide_english(self):
  for text in ['[守护者](Guardian bad)',r'\[守护者](Guardian)','`[守护者](Guardian)`']:
   self.assertTrue(any(x['kind']=='unapproved_latin' for x in m.inspect(text)),text)
 def test_url_does_not_swallow_chinese_or_guardian(self):
  self.assertTrue(any(x['kind']=='unapproved_latin' and x['text']=='Guardian' for x in m.inspect('见 https://example.org。守护者Guardian')))
 def test_valid_multiline_bold_and_link_title(self):
  self.assertEqual(m.inspect('**第一行\n第二行**'),[])
  self.assertEqual(m.inspect('[规则](#p1 "中文标题")'),[])
 def test_broken_underscore_bold_and_valid_code_literal(self):
  self.assertTrue(any(x['kind']=='unbalanced_bold' for x in m.inspect('__护甲槽')))
  self.assertEqual(m.inspect('符号 `**`。'),[])
 def test_complex_url_destination_change_is_detected(self):
  self.assertTrue(any(x['kind']=='missing_source_link_target' for x in m.inspect('[资料](https://example.org/a_(b)/2)',source='[Reference](https://example.org/a_(b)/1)')))
 def test_required_name_in_target_url_does_not_count(self):
  p={'allowed_latin':[{'text':'Deja','reason':'required original','required':True}]}
  self.assertTrue(any(x['kind']=='missing_required_original_name' for x in m.inspect('[资料](https://example.org/Deja)',p,source='Deja. [Reference](https://example.org/Deja)')))
 def test_parser_unavailable_blocks(self):
  with patch.object(m.shutil,'which',return_value=None):self.assertEqual(m.inspect('纯中文。')[0]['kind'],'markdown_parser_unavailable')
 def test_dice_across_paragraphs_counted(self):
  self.assertTrue(any(x['kind']=='missing_original_dice_expression' for x in m.inspect('掷 d6。',source='d6\n\nd6')))
 def test_valid_markdown(self):self.assertEqual(m.inspect('## **资源**\n\n处于 *脆弱* 状态。'),[])
 def test_commonmark_label_boundary_blocked(self):
  self.assertTrue(any(x['kind']=='commonmark_bold_boundary' for x in m.inspect('**示例：**鲁恩')))
  self.assertEqual(m.inspect('**示例：** 鲁恩'),[])
 def test_dropped_link_and_changed_dice_blocked(self):
  f=m.inspect('造成 1d8 点伤害。',source='Deal d8 damage. See [rules](#page-107-0).')
  self.assertEqual({x['kind'] for x in f},{'missing_source_link_target','missing_original_dice_expression'})
 def test_source_duplicate_link_can_be_consolidated(self):
  self.assertEqual(m.inspect('[规则](#p1)',source='[See](#p1) [rules](#p1)'),[])
 def test_policy_in_both_generation_and_refinement(self):
  with tempfile.TemporaryDirectory() as t:
   p=Path(t)/'run';m.prepare([{'id':'a','source':'Gain 1 Hope.'}],p,{'allowed_latin':[]})
   for n in ['phase1-generate.txt','baseline-generate.txt']:self.assertIn('守护者 Guardian',(p/n).read_text())
   m.v.dump(p/'candidate-draft.json',{'units':[{'id':'a','translation':'获得 1 希望点。','invariants':[{'id':'i','source_quote':'Gain 1 Hope','meaning':'获得1希望点'}],'protected_phrases':[],'questions':[]}]});m.polish(p,True);self.assertIn('最新交付要求优先',(p/'phase2-polish.txt').read_text());self.assertTrue(m.v.read_json(p/'manifest.json')['release_gate_required'])
 def test_baseline_review_gets_same_policy(self):
  with tempfile.TemporaryDirectory() as t:
   p=Path(t)/'run';m.prepare([{'id':'a','source':'Gain 1 Hope.'}],p,{'allowed_latin':[]})
   (p/'baseline/drafts/a.md').write_text((p/'baseline/chunks/a.md').read_text())
   m.v.dump(p/'candidate-draft.json',{'units':[{'id':'a','translation':'获得 1 希望点。','invariants':[{'id':'i','source_quote':'Gain 1 Hope','meaning':'获得1希望点'}],'protected_phrases':[],'questions':[]}]})
   m.polish(p,False)
   for name in ['baseline-review.txt','phase2-polish.txt']:self.assertIn('最新交付要求优先',(p/name).read_text())
   self.assertEqual(m.v.read_json(p/'stage-input-hashes.json')['baseline-review.txt'],m.v.digest((p/'baseline-review.txt').read_bytes()))
 def test_release_blocks_without_rewriting_raw_output(self):
  with tempfile.TemporaryDirectory() as t:
   p=Path(t)/'run';m.prepare([{'id':'a','source':'Guardian gains 1 Hope.'}],p,{'allowed_latin':[]})
   d={'units':[{'id':'a','translation':'守护者 Guardian 获得 1 希望点。','invariants':[{'id':'i','source_quote':'Guardian gains 1 Hope','meaning':'守护者获得1希望点'}],'protected_phrases':[],'questions':[]}]};m.v.dump(p/'candidate-draft.json',d);m.polish(p,True)
   f={'units':[{'id':'a','translation':d['units'][0]['translation'],'invariant_checks':[{'invariant_id':'i','source_quote':'Guardian gains 1 Hope','target_quote':'守护者 Guardian 获得 1 希望点','verdict':'preserved'}],'phrase_exceptions':[],'changes':[],'ambiguity_checks':[{'source_quote':'Guardian gains 1 Hope','target_quote':'守护者 Guardian 获得 1 希望点','verdict':'no_new_ambiguity'}],'questions':[]}]};m.v.dump(p/'candidate-final.json',f);before=(p/'candidate-final.json').read_bytes();
   with self.assertRaisesRegex(ValueError,'delivery gate required'):m.tp.freeze(p,True)
   result=m.release(p,True);self.assertFalse(result['release_allowed']);self.assertEqual(before,(p/'candidate-final.json').read_bytes())
   m.v.dump(p/'delivery-profile.json',{'allowed_latin':[{'text':'Guardian','reason':'late bypass'}]})
   with self.assertRaisesRegex(ValueError,'prepared delivery input changed'):m.release(p,True)
 def test_failed_revalidation_invalidates_previous_success(self):
  with tempfile.TemporaryDirectory() as t:
   p=Path(t)/'run';m.prepare([{'id':'a','source':'Hope.'}],p,{'allowed_latin':[]})
   m.v.dump(p/'candidate-delivery.json',{'units':[{'id':'a','translation':'希望点。'}]})
   m.v.dump(p/'frozen.json',{'structural_errors':[],'output_hashes':{'candidate-delivery.json':m.v.digest((p/'candidate-delivery.json').read_bytes())}})
   self.assertTrue(m.release(p,True)['release_allowed'])
   m.v.dump(p/'candidate-delivery.json',{'units':[{'id':'a','translation':'Hope'}]})
   with self.assertRaisesRegex(ValueError,'frozen output changed'):m.release(p,True)
   self.assertFalse(m.v.read_json(p/'delivery-gate.json')['release_allowed'])
if __name__=='__main__':unittest.main()
