#!/usr/bin/env python3
"""V2: source-anchored mechanics draft -> independent Chinese polish + difference audit.
V1 frozen artifacts remain untouched. Final candidate text is validated, never rewritten
by main's broad resource-phrase regex after polishing.
"""
import argparse,collections,difflib,hashlib,importlib.util,json,re,sys
from pathlib import Path
HERE=Path(__file__).resolve().parent
spec=importlib.util.spec_from_file_location('context_v1',HERE/'pipeline.py');v1=importlib.util.module_from_spec(spec);spec.loader.exec_module(v1)
VERSION='two-pass-v2'

PRIORITY='''规范优先级（按适用范围，不作同义宽免）：
1. 原文完整机制与事实是硬边界，参考例句不得覆盖原文。
2. 明确对应当前实体、字段和句式的专门规范优先于孤立词面。敌人攻击字段允许既定“近战/邻近/近/远/极远”缩写及完整范围名；正文范围引用不因此任意缩写。熟练值伤害句允许专门模板“使用你熟练值的 dy+z”以及核心句式“使用你的熟练值造成……”，不能把二者误作机制差别。
3. 完整固定频率短语（如每长休一次）及明确规定的完整特性模板（如集群/无情）逐字保留，实体/数值参数按源文替换。
4. context_required条目的default_translation只是语境用法参考；若未给出完整英文模板与明确逐字锁定要求，不把它升级成整句硬模板。尤其背景/关系提问的引导句，应保留谁问谁、由谁的角色回答、可自创问题等信息，用自然中文表达。
5. 不明确的词义、指代与普通风格判断由译者解决；只有确实缺少会改变事实的上下文才提问。源文自身未定的取整等细节忠实保留，不补造答案。'''
PHASE1='''第一阶段：规则与匕语核准粗译。你只看英文原文和项目规范，不看旧译或人工参考。
先确保完整信息、规则和术语正确，再形成可读粗稿，不以润色为由删改信息。保持原文Markdown层级、数字、骰子原式、URL、代词标记；文中规则知识仅按原文，不从示例补入效果。
逐个单元记录必须保持的可核对命题（不是思考过程）：条件、主体、成本支付者、资源/数量、目标集合、骰子/比较、成功失败分支、时序、持续与终止、否定和例外；问答/叙事则记录事实、指代方向、提问者与回答者。一个命题一个invariant，用源文原样片段作锚；不得只复述译稿而跳过原文。
记录实际适用的完整固定短语/模板为protected_phrases。不是把每个普通句子锁死，更不是把有争议的context_required句式当固定模板。
这些核准项仍是暂定的模型结论，不是原文事实的替身；第二阶段必须独立回查原文，发现首稿错误须明确纠正。
输出JSON {"units":[{"id":"...","translation":"完整粗译Markdown","invariants":[{"id":"i1","source_quote":"原文原样片段","meaning":"简短中文命题"}],"protected_phrases":[{"id":"p1","source_quote":"原文原样片段","target_phrase":"实际应原样保留的中文","scope":"为何是适用的明确固定表达"}],"questions":[]}]}。
所有单元恰好一次；各单元内ID唯一；至少一条真实命题。没有适用固定模板时protected_phrases为空。不要输出隐含推理，只给译文与可审核结论。'''
PHASE2='''第二阶段：独立精译与差异核查。你的目标是让第一稿的中文自然、顺口，调整句子结构而不新造歧义。
必须先看完整英文，再看粗稿和核准项。不要盲信首稿：首稿或核准项若违背英文，应纠正并标为source_correction，而不是把错误锁死。其他改动标wording_only。
允许调序、拆句、并句、改连接词和代词、消除翻译腔；不改变条件、主体、数量、时序、范围、可选性、因果、否定或例外。不要为了显示“做过精修”强行修改已经自然的句子。
对照原文确认每个invariant在最终译文中的对应片段，并复查源文有没有首稿遗漏、核准项未覆盖的信息。完整固定模板不因润色换同义说法；有明确专门规范支持的变体按适用范围处理。
对每个实质修改记录before/after原样片段、wording_only或source_correction分类、涉及的invariant_id及简短依据。不得用一条“已保持全部含义”代替逐项证据。没有改动可以changes=[]。
对最终句子再查歧义：谁做什么、对谁、何时、在哪个条件下、是否可选；原文已有歧义保持原样，别自作决定。
直接完成最终Markdown格式（资源数字空格、状态、标题等）。你的最终文字只会检查，不再经过会改写句子的资源正则，因此不要依赖后处理修句子。
输出JSON {"units":[{"id":"...","translation":"完整最终中文Markdown","invariant_checks":[{"invariant_id":"i1","source_quote":"原文原样片段","target_quote":"最终译文原样片段","verdict":"preserved|source_correction","note":"纠正首稿时说明依据"}],"phrase_exceptions":[{"phrase_id":"p1","source_quote":"原文证据","reason":"首稿错误锁定的原文依据"}],"changes":[{"before":"粗稿原样片段","after":"终稿原样片段","kind":"wording_only|source_correction","invariant_ids":["i1"],"reason":"简短核对结论"}],"ambiguity_checks":[{"source_quote":"原文原样片段","target_quote":"终稿原样片段","verdict":"no_new_ambiguity|source_ambiguity_preserved"}],"questions":[]}]}。
每个原核准项必须有且仅有一个invariant_check，首稿有错也必须明确记录source_correction。phrase_exceptions只能用来纠正源文不支持的错误锁定，不能当作放宽术语的通行证。'''


def prepare(cases,out):
 v1.prepare(cases,out);out=Path(out).resolve();units=v1.read_json(out/'candidate-units.json')
 # Existing complete reference + scoped retrieval, never merge contextual rules as replacements.
 reference=(v1.SKILLS/'daggerheart-chinese-writing/REFERENCE.md').read_text()
 context=v1.retrieve_context('\n'.join(u['source'] for u in units))
 guidance=PRIORITY+'\n\n项目参考（冲突按以上范围优先级）：\n'+reference+'\n条件参考：\n'+json.dumps(context,ensure_ascii=False,separators=(',',':'))
 packet={'version':VERSION,'guidance':guidance,'input':v1.compact_units(units)}
 v1.dump(out/'two-pass-packet.json',packet)
 prompt=PHASE1+'\n\n'+guidance+'\n\n输入：\n'+json.dumps(packet['input'],ensure_ascii=False,separators=(',',':'))+'\n\n只将结果写入 '+str(out/'candidate-draft.json')
 (out/'phase1-generate.txt').write_text(prompt,encoding='utf-8')
 # A v1 prompt is not used for v2; preserve it explicitly as an unused comparison artifact.
 (out/'candidate-generate.txt').rename(out/'unused-v1-candidate-prompt.txt')
 manifest=v1.read_json(out/'manifest.json');manifest.update(version=VERSION,candidate_prompt_chars=len(prompt),candidate_formatter='none: final polished bytes are the delivery text')
 rule_files=[Path(__file__),HERE/'protocol-v2.json']+[p for p in v1.SKILLS.rglob('*') if p.is_file() and p.suffix in {'.py','.md','.json'}]
 manifest['rules'].update({str(p.relative_to(v1.ROOT)):v1.digest(p.read_bytes()) for p in rule_files})
 manifest['prepared_files']={str(p.relative_to(out)):v1.digest(p.read_bytes()) for p in out.rglob('*') if p.is_file() and p.name!='manifest.json'}
 v1.dump(out/'manifest.json',manifest);return manifest


def unique_ids(items,key):return len(items)==len({x.get(key) for x in items}) and all(x.get(key) for x in items)

def schema_errors(result,stage):
 errors=[]
 if not isinstance(result,dict) or not isinstance(result.get('units'),list):return ['units must be an array in an object']
 fields={'draft':{'invariants':('id','source_quote','meaning'),'protected_phrases':('id','source_quote','target_phrase','scope')},'final':{'invariant_checks':('invariant_id','source_quote','target_quote','verdict'),'phrase_exceptions':('phrase_id','source_quote','reason'),'changes':('before','after','kind','reason'),'ambiguity_checks':('source_quote','target_quote','verdict')}}[stage]
 for x in result['units']:
  if not isinstance(x,dict):errors.append('unit must be object');continue
  for key in ('id','translation'):
   if not isinstance(x.get(key),str) or not x[key].strip():errors.append(key+' must be nonempty string')
  for key,required in fields.items():
   if not isinstance(x.get(key),list):errors.append(key+' must be array');continue
   for row in x[key]:
    if not isinstance(row,dict):errors.append(key+' item must be object');continue
    for f in required:
     if not isinstance(row.get(f),str) or not row[f].strip():errors.append(key+'.'+f+' must be nonempty string')
    if key=='changes' and (not isinstance(row.get('invariant_ids'),list) or any(not isinstance(i,str) for i in row['invariant_ids'])):errors.append('change invariant_ids must be string array')
  if not isinstance(x.get('questions'),list):errors.append('questions must be array')
 return errors


def validate_draft(sources,result):
 shape=schema_errors(result,'draft')
 if shape:return shape
 errors=[];lookup={x['id']:x for x in sources};units=result.get('units',[])
 if collections.Counter(x.get('id') for x in units)!=collections.Counter(lookup.keys()):errors.append('unit identity mismatch')
 for x in units:
  if x.get('id') not in lookup:continue
  source=lookup[x['id']]['source'];prefix=x['id']+': '
  if not x.get('translation'):errors.append(prefix+'empty draft')
  inv=x.get('invariants',[]);phr=x.get('protected_phrases',[])
  if not inv or not unique_ids(inv,'id'):errors.append(prefix+'missing/duplicate invariant')
  if not unique_ids(phr,'id'):errors.append(prefix+'duplicate phrase')
  for i in inv:
   if not i.get('source_quote') or i['source_quote'] not in source or not i.get('meaning'):errors.append(prefix+'invalid invariant evidence')
  for p in phr:
   if not p.get('source_quote') or p['source_quote'] not in source or not p.get('target_phrase') or not p.get('scope'):errors.append(prefix+'invalid protected phrase')
  if not isinstance(x.get('questions'),list):errors.append(prefix+'questions array required')
 return errors


def prepare_main_review(run):
 run=Path(run).resolve();v1.baseline_collect(run,'drafts');sys.path.insert(0,str(v1.SKILLS/'daggerheart-term-checker/scripts'));checker=v1.module('v2_main_checker',v1.SKILLS/'daggerheart-term-checker/scripts/check_terms.py');report=[];units=v1.read_json(run/'sources.json')
 for u in units:
  cid=u['id'];rows,n=checker.review_chunk(str(run/'baseline/chunks'/f'{cid}.md'),str(run/'baseline/drafts'/f'{cid}.md'),cid);report.append({'id':cid,'rows':rows,'structural_anomalies':n})
 v1.dump(run/'baseline-term-review.json',report);(run/'baseline/finals').mkdir(exist_ok=True)
 prompt='按main全自动第7–11步审阅术语标记译文，结合完整原文、REFERENCE及其中链接规范修复确定问题。保留原draft，最终带标记文件写入baseline/finals。不改推荐槽或注释，保留KILO。一般选词自行决定。不得读其他条件或人工参考。\n'
 for u in units:
  cid=u['id'];prompt+='\n原文 '+str(run/'baseline/chunks'/f'{cid}.md')+'\n初稿 '+str(run/'baseline/drafts'/f'{cid}.md')+'\n终稿 '+str(run/'baseline/finals'/f'{cid}.md')+'\n'
 prompt+='\n完整main报告：'+str(run/'baseline-term-review.json')+'\n规范：'+str(v1.SKILLS/'daggerheart-chinese-writing/REFERENCE.md')+'\n写baseline-review-log.json，格式 {"questions":[],"changes":[{"id":"...","summary":"..."}]}。'
 (run/'baseline-review.txt').write_text(prompt,encoding='utf-8')


def polish_packet(run,main=True):
 run=Path(run).resolve();sources=v1.read_json(run/'sources.json');draft=v1.read_json(run/'candidate-draft.json');errors=validate_draft(sources,draft);v1.dump(run/'phase1-structural-errors.json',errors)
 packet=v1.read_json(run/'two-pass-packet.json')
 text=PHASE2+'\n\n'+packet['guidance']+'\n\n原文与术语：\n'+json.dumps(packet['input'],ensure_ascii=False,separators=(',',':'))+'\n\n第一稿与暂定核准项：\n'+json.dumps(draft,ensure_ascii=False,separators=(',',':'))+'\n\n结构检查（不证明语义）：\n'+json.dumps(errors,ensure_ascii=False)+'\n\n只将结果写入 '+str(run/'candidate-final.json')
 (run/'phase2-polish.txt').write_text(text,encoding='utf-8')
 if main:prepare_main_review(run)
 names=['candidate-draft.json','phase2-polish.txt','phase1-structural-errors.json']
 if main:names+=['baseline-drafts.json','baseline-review.txt','baseline-term-review.json']+[str(p.relative_to(run)) for p in (run/'baseline/drafts').glob('*.md')]
 v1.dump(run/'stage-input-hashes.json',{n:v1.digest((run/n).read_bytes()) for n in names})


def validate_final(sources,draft,result):
 shape=schema_errors(draft,'draft')+schema_errors(result,'final')
 if shape:return shape
 errors=[];lookup={x['id']:x for x in sources};drafts={x['id']:x for x in draft['units']};units=result.get('units',[])
 if collections.Counter(x.get('id') for x in units)!=collections.Counter(lookup.keys()):errors.append('unit identity mismatch')
 for x in units:
  cid=x.get('id');
  if cid not in lookup or cid not in drafts:continue
  src=lookup[cid]['source'];d=drafts[cid];target=x.get('translation','');prefix=cid+': '
  if not target:errors.append(prefix+'empty final')
  checks=x.get('invariant_checks',[]);expected={i['id'] for i in d['invariants']}
  if collections.Counter(i.get('invariant_id') for i in checks)!=collections.Counter(expected):errors.append(prefix+'invariant accounting mismatch')
  for i in checks:
   if not i.get('source_quote') or i['source_quote'] not in src or not i.get('target_quote') or i['target_quote'] not in target:errors.append(prefix+'invalid invariant evidence')
   original=next((r['source_quote'] for r in d['invariants'] if r['id']==i.get('invariant_id')),None)
   if i.get('verdict')=='preserved' and original and not (original in i['source_quote'] or i['source_quote'] in original):errors.append(prefix+'preserved invariant changed source anchor')
   if i.get('verdict') not in {'preserved','source_correction'}:errors.append(prefix+'invalid invariant verdict')
   if i.get('verdict')=='source_correction' and not i.get('note'):errors.append(prefix+'source correction needs evidence note')
  exceptions=x.get('phrase_exceptions',[]);known={p['id'] for p in d['protected_phrases']}
  if not unique_ids(exceptions,'phrase_id'):errors.append(prefix+'duplicate phrase exception')
  for e in exceptions:
   if e.get('phrase_id') not in known or not e.get('source_quote') or e['source_quote'] not in src or not e.get('reason'):errors.append(prefix+'invalid phrase exception')
  exempt={e['phrase_id'] for e in exceptions}
  for p in d['protected_phrases']:
   if p['id'] not in exempt and re.sub(r'[\s*]+','',p['target_phrase']) not in re.sub(r'[\s*]+','',target):errors.append(prefix+'protected phrase changed: '+p['id'])
  changes=x.get('changes',[])
  if target!=d['translation'] and not changes:errors.append(prefix+'changed draft without change record')
  for c in changes:
   if c.get('before')==c.get('after'):errors.append(prefix+'no-op change record')
   if not c.get('before') or c['before'] not in d['translation'] or not c.get('after') or c['after'] not in target:errors.append(prefix+'invalid change spans')
   if c.get('kind') not in {'wording_only','source_correction'} or not c.get('reason'):errors.append(prefix+'invalid change classification')
   if not set(c.get('invariant_ids',[]))<=expected:errors.append(prefix+'unknown change invariant')
  amb=x.get('ambiguity_checks',[])
  if not amb:errors.append(prefix+'missing ambiguity check')
  for a in amb:
   if not a.get('source_quote') or a['source_quote'] not in src or not a.get('target_quote') or a['target_quote'] not in target or a.get('verdict') not in {'no_new_ambiguity','source_ambiguity_preserved'}:errors.append(prefix+'invalid ambiguity evidence')
  if not isinstance(x.get('questions'),list):errors.append(prefix+'questions array required')
 return errors


def freeze(run,development=False,delivery_gate=False):
 run=Path(run)
 if (run/'frozen.json').exists():raise ValueError('already frozen')
 manifest=v1.read_json(run/'manifest.json')
 if manifest.get('release_gate_required') and not delivery_gate:raise ValueError('delivery gate required: use delivery_gate.py release')
 for name,h in manifest['rules'].items():
  if v1.digest((v1.ROOT/name).read_bytes())!=h:raise ValueError('frozen rule changed: '+name)
 for name,h in manifest['prepared_files'].items():
  if v1.digest((run/name).read_bytes())!=h:raise ValueError('prepared input changed: '+name)
 stage_hashes=run/'stage-input-hashes.json'
 if not development and not stage_hashes.exists():raise ValueError('missing stage input hashes: run polish first')
 if stage_hashes.exists():
  for name,h in v1.read_json(stage_hashes).items():
   if v1.digest((run/name).read_bytes())!=h:raise ValueError('stage input changed: '+name)
 sources=v1.read_json(run/'sources.json');draft=v1.read_json(run/'candidate-draft.json');final=v1.read_json(run/'candidate-final.json');errors=validate_draft(sources,draft)+validate_final(sources,draft,final)
 shape=schema_errors(draft,'draft')+schema_errors(final,'final')
 if shape or any(collections.Counter(x.get('id') for x in data.get('units',[]) if isinstance(x,dict))!=collections.Counter(x['id'] for x in sources) for data in [draft,final]):
  out={'version':VERSION,'development_only':development,'status':'frozen-invalid-schema','structural_errors':errors,'output_hashes':{n:v1.digest((run/n).read_bytes()) for n in ['candidate-draft.json','candidate-final.json']}}
  v1.dump(run/'frozen.json',out);return out
 v1.dump(run/'candidate-delivery.json',{'units':[{'id':x['id'],'translation':x['translation']} for x in final['units']]})
 diffs=[]
 for x in final['units']:
  d=next(z for z in draft['units'] if z['id']==x['id']);diffs.append({'id':x['id'],'diff':list(difflib.unified_diff(d['translation'].splitlines(),x['translation'].splitlines(),fromfile='mechanics-draft',tofile='polished-final',lineterm=''))})
 v1.dump(run/'actual-phase2-diff.json',diffs)
 names=['candidate-draft.json','candidate-final.json','candidate-delivery.json','actual-phase2-diff.json'];baseline_questions=None
 if not development:
  rows=v1.baseline_collect(run,'finals');makeup=v1.module('v2_baseline_makeup',v1.BASE/'scripts/makeup.py');v1.dump(run/'baseline-delivery.json',{'units':[{'id':x['id'],'translation':makeup.process_markdown(x['translation'])} for x in rows]});names+=['baseline-drafts.json','baseline-finals.json','baseline-delivery.json'];baseline_questions=len(v1.read_json(run/'baseline-review-log.json')['questions'])
 names+=['stage-input-hashes.json'] if stage_hashes.exists() else []
 names+=[str(p.relative_to(run)) for p in run.rglob('*') if p.is_file() and (p.suffix=='.md' or p.name in {'phase2-polish.txt','baseline-review.txt','baseline-term-review.json','baseline-review-log.json'})]
 out={'version':VERSION,'development_only':development,'status':'frozen-with-findings' if errors else 'frozen-for-independent-review','structural_errors':errors,'candidate_questions':sum(len(x['questions']) for x in final['units']),'baseline_questions':baseline_questions,'output_hashes':{n:v1.digest((run/n).read_bytes()) for n in names},'caveat':'Exact spans and accounting do not prove meaning preservation. Independent review must compare source, phase1 and phase2 for new ambiguity or carried-forward error.'}
 v1.dump(run/'frozen.json',out);return out


def main():
 p=argparse.ArgumentParser();s=p.add_subparsers(dest='command',required=True);q=s.add_parser('prepare');q.add_argument('cases');q.add_argument('out');q=s.add_parser('polish');q.add_argument('run');q.add_argument('--development',action='store_true');q=s.add_parser('freeze');q.add_argument('run');q.add_argument('--development',action='store_true');a=p.parse_args()
 if a.command=='prepare':print(json.dumps(prepare(v1.read_json(a.cases),a.out),ensure_ascii=False,indent=2))
 elif a.command=='polish':polish_packet(a.run,not a.development)
 else:print(json.dumps(freeze(a.run,a.development),ensure_ascii=False,indent=2))
if __name__=='__main__':main()
