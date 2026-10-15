"""Post-feedback Chinese delivery policy and fail-closed release gate.
Never rewrites translation text; old frozen experiments remain unchanged.
"""
import argparse,collections,importlib.util,json,re,subprocess,shutil
from pathlib import Path
spec=importlib.util.spec_from_file_location('delivery_tp',Path(__file__).with_name('two_pass.py'));tp=importlib.util.module_from_spec(spec);spec.loader.exec_module(tp);v=tp.v1
POLICY='''最新交付要求优先于旧REFERENCE的双语保留规则：成稿为中文。已经译出的职业、种族、领域、资源、特性等，不附加无必要英文（例如“守护者 Guardian”不合格）。正文和标题统一受此约束。
仅保留原始骰式、链接目标及交付profile逐项列明确有必要保留的原名；不能因为原文出现英文就默认全部保留。遇到旧规范要求“译名 原名”时按本条覆盖，不把规范冲突交给用户。
固定模板保护的是机制正文与明确中文定式（如每长休一次）；模板示例中的英文标题或原名补注不因此成为必保留内容。中文固定表达与规则不得删改，原名仍按本profile决定。
保留正确Markdown结构，但不残留审阅标记、KILO、断裂加粗或未闭合链接。不得通过删掉整句或机械清除全部ASCII来过检查；中文事实完整、骰式和链接不变。最终交付检查失败必须阻止自动发布，保留原稿和具体问题。'''

def profile_validate(profile):
 if not isinstance(profile,dict) or not isinstance(profile.get('allowed_latin',[]),list):raise ValueError('profile allowed_latin must be array')
 for x in profile.get('allowed_latin',[]):
  if not isinstance(x,dict) or ('required' in x and not isinstance(x['required'],bool)) or not isinstance(x.get('text'),str) or not x['text'] or not isinstance(x.get('reason'),str) or not x['reason']:raise ValueError('explicit Latin name and reason required')

DICE_PATTERN=r'(?<![A-Za-z0-9])\d*[dD]\d+(?:\s*[+−-]\s*\d+)?(?![A-Za-z0-9])'
BARE_URL_PATTERN=r"https?://[A-Za-z0-9:/?#\[\]@!$&'()*+,;=%._~+\-]+"

def parse_commonmark_ast(text):
 if not shutil.which('pandoc'):raise RuntimeError('pandoc CommonMark parser unavailable')
 result=subprocess.run(['pandoc','--from=commonmark','--to=json'],input=text,text=True,capture_output=True,timeout=15)
 if result.returncode:raise RuntimeError('CommonMark parse failed: '+result.stderr[:200])
 return json.loads(result.stdout)

def parse_commonmark(text):
 ast=parse_commonmark_ast(text);segments=[];targets=set()
 def walk(node,mode='text'):
  if isinstance(node,list):
   for x in node:walk(x,mode)
  elif isinstance(node,dict):
   tag=node.get('t');c=node.get('c')
   if tag=='Str':segments.append((mode,c))
   elif tag in {'Space','SoftBreak','LineBreak'}:segments.append((mode,' '))
   elif tag in {'Code','CodeBlock'}:
    if tag=='CodeBlock':segments.append(('text','\n'))
    segments.append(('code',c[-1]))
    if tag=='CodeBlock':segments.append(('text','\n'))
   elif tag in {'RawInline','RawBlock'}:segments.append(('raw',c[-1]))
   elif tag in {'Link','Image'}:
    targets.add(c[-1][0]);walk(c[-2],mode)
    if c[-1][1]:segments.append(('title',c[-1][1]))
   elif c is not None:
    block=tag in {'Para','Plain','Header','BlockQuote','BulletList','OrderedList','Table','Div'}
    if block:segments.append(('text','\n'))
    walk(c,mode)
    if block:segments.append(('text','\n'))
 walk(ast.get('blocks',[]))
 # Preserve node boundaries for markup checks; visible prose is reconstructed for
 # multiword explicit names. Destinations never count as visible retained names.
 visible=''.join(x[1] for x in segments)
 raw_urls={x.rstrip('.,;:!?') for x in re.findall(BARE_URL_PATTERN,visible)}
 return {'segments':segments,'visible':visible,'targets':targets|raw_urls,'ast_api_version':ast.get('pandoc-api-version')}

def inspect(text,profile=None,source=None):
 profile=profile or {'allowed_latin':[]};profile_validate(profile);findings=[]
 try:parsed=parse_commonmark(text)
 except (RuntimeError,subprocess.SubprocessError,json.JSONDecodeError,OSError) as e:return [{'kind':'markdown_parser_unavailable','text':str(e)}]
 visible=parsed['visible'];cleaned=re.sub(BARE_URL_PATTERN,' ',visible);cleaned=re.sub(DICE_PATTERN,' ',cleaned)
 for allowed in profile.get('allowed_latin',[]):cleaned=re.sub(r'(?<![A-Za-z0-9])'+re.escape(allowed['text'])+r'(?![A-Za-z0-9])',' ',cleaned)
 for m in re.finditer(r"[A-Za-z]+(?:[’'_-][A-Za-z]+)*",cleaned):findings.append({'kind':'unapproved_latin','visible_start':m.start(),'text':m.group()})
 for pattern,kind in [(r'\[\[\[KILO_[^\n]*','internal_wrapper'),(r'<!--(?:.*?-->|.*$)','review_comment'),(r'【[^】\n]*[｜|][^】\n]*】','term_annotation')]:
  for m in re.finditer(pattern,text,re.S):findings.append({'kind':kind,'start':m.start(),'end':m.end(),'text':m.group()})
 prose=''.join(value for kind,value in parsed['segments'] if kind=='text')
 if '**' in prose or '__' in prose:
  kind='commonmark_bold_boundary' if re.search(r'\*\*[^*\n]*[：:，,。!?；;]\*\*(?=[A-Za-z0-9\u4e00-\u9fff])',text) else 'unbalanced_bold'
  findings.append({'kind':kind,'text':prose})
 if '](' in prose:findings.append({'kind':'orphan_link_target','text':prose})
 if source is not None:
  try:original=parse_commonmark(source)
  except (RuntimeError,subprocess.SubprocessError,json.JSONDecodeError,OSError) as e:return findings+[{'kind':'source_markdown_parse_failed','text':str(e)}]
  for missing in sorted(original['targets']-parsed['targets']):findings.append({'kind':'missing_source_link_target','text':missing})
  dice=lambda p:collections.Counter(re.sub(r'\s+','',x).lower() for x in re.findall(DICE_PATTERN,re.sub(BARE_URL_PATTERN,' ',p['visible'])))
  for missing,count in (dice(original)-dice(parsed)).items():findings.append({'kind':'missing_original_dice_expression','text':missing,'count':count})
  for name in profile.get('allowed_latin',[]):
   pattern=r'(?<![A-Za-z0-9])'+re.escape(name['text'])+r'(?![A-Za-z0-9])'
   if name.get('required',False) and re.search(pattern,original['visible']) and not re.search(pattern,visible):findings.append({'kind':'missing_required_original_name','text':name['text']})
 return findings

def scan_records(sources,translations,profile=None):
 errors=[]
 if not isinstance(sources,list) or not sources or any(not isinstance(u,dict) or not isinstance(u.get('id'),str) or not isinstance(u.get('source'),str) for u in sources):return {'release_allowed':False,'identity_errors':['invalid sources'],'units':[]}
 units=translations.get('units') if isinstance(translations,dict) else None
 if not isinstance(units,list) or any(not isinstance(u,dict) or not isinstance(u.get('id'),str) or not isinstance(u.get('translation'),str) or not u['translation'].strip() for u in units):return {'release_allowed':False,'identity_errors':['invalid translations'],'units':[]}
 expected=[u['id'] for u in sources];actual=[u['id'] for u in units]
 if len(set(expected))!=len(expected) or collections.Counter(expected)!=collections.Counter(actual):errors.append('source/translation identity mismatch')
 lookup={u['id']:u['source'] for u in sources};rows=[{'id':u['id'],'findings':inspect(u['translation'],profile,lookup[u['id']])} for u in units if u['id'] in lookup]
 return {'release_allowed':not errors and all(not r['findings'] for r in rows),'identity_errors':errors,'units':rows}

def policy_text(profile):return POLICY+'\n明确允许原名清单：'+json.dumps(profile.get('allowed_latin',[]),ensure_ascii=False)
def update_manifest(run):
 manifest=v.read_json(run/'manifest.json');manifest['rules'][str(Path(__file__).relative_to(v.ROOT))]=v.digest(Path(__file__).read_bytes());manifest['prepared_files'].update({n:v.digest((run/n).read_bytes()) for n in ['delivery-profile.json','phase1-generate.txt','baseline-generate.txt','two-pass-packet.json']});manifest['release_gate_required']=True;v.dump(run/'manifest.json',manifest)
def parser_identity():
 if not shutil.which('pandoc'):raise RuntimeError('pandoc required for delivery gate')
 r=subprocess.run(['pandoc','--version'],capture_output=True,text=True,check=True,timeout=15)
 return {'engine':'pandoc','format':'commonmark','version':r.stdout.splitlines()[0]}
def prepare(cases,out,profile):
 profile_validate(profile);parser=parser_identity();tp.prepare(cases,out);run=Path(out);v.dump(run/'delivery-profile.json',profile);policy=policy_text(profile)
 for name in ['phase1-generate.txt','baseline-generate.txt']:
  f=run/name;f.write_text(policy+'\n\n'+f.read_text(),encoding='utf-8')
 packet=v.read_json(run/'two-pass-packet.json');packet['guidance']=policy+'\n\n'+packet['guidance'];v.dump(run/'two-pass-packet.json',packet);update_manifest(run);manifest=v.read_json(run/'manifest.json');manifest['delivery_parser']=parser;v.dump(run/'manifest.json',manifest)
def polish(run,development=False):
 run=Path(run);tp.polish_packet(run,not development)
 if not development:
  f=run/'baseline-review.txt';f.write_text(policy_text(v.read_json(run/'delivery-profile.json'))+'\n\n'+f.read_text(),encoding='utf-8');h=v.read_json(run/'stage-input-hashes.json');h['baseline-review.txt']=v.digest(f.read_bytes());v.dump(run/'stage-input-hashes.json',h)
def release(run,development=False):
 run=Path(run);v.dump(run/'delivery-gate.json',{'release_allowed':False,'status':'REVALIDATING_OR_BLOCKED','note':'Prior success invalidated before checking current bytes.'});manifest=v.read_json(run/'manifest.json')
 for n,h in manifest['rules'].items():
  if v.digest((v.ROOT/n).read_bytes())!=h:raise ValueError('delivery rule changed: '+n)
 for n,h in manifest['prepared_files'].items():
  if v.digest((run/n).read_bytes())!=h:raise ValueError('prepared delivery input changed: '+n)
 if manifest.get('delivery_parser')!=parser_identity():raise ValueError('delivery parser changed since prepare')
 profile=v.read_json(run/'delivery-profile.json')
 # Cross-check the hash-pinned packet and rule registration, not just the optional marker.
 bindings=None;names=None;packet=v.read_json(run/'two-pass-packet.json')
 binding_rule='experiments/context_contract/pbres_bindings.py'
 if 'name_bindings' in manifest or 'name-bindings.json' in manifest['prepared_files'] or (run/'name-bindings.json').exists() or binding_rule in manifest['rules'] or 'name_binding_contract' in packet:
  if manifest.get('name_bindings')!='name-bindings.json' or 'name-bindings.json' not in manifest['prepared_files']:raise ValueError('prepared name binding registration missing or invalid')
  if binding_rule not in manifest['rules']:raise ValueError('prepared name binding rule registration missing')
  if packet.get('name_binding_contract')!={'file':'name-bindings.json','sha256':v.digest((run/'name-bindings.json').read_bytes())}:raise ValueError('prepared name binding packet contract missing or changed')
  if manifest.get('original_name_sidecar')!='original-names.json':raise ValueError('name bindings require the prepared PBRES sidecar')
  for name in ['original-name-resources.json','original-names.json']:
   if name not in manifest['prepared_files']:raise ValueError('unregistered PBRES input: '+name)
  spec=importlib.util.spec_from_file_location('release_pbres_names',Path(__file__).with_name('pbres_names.py'));names=importlib.util.module_from_spec(spec);spec.loader.exec_module(names)
  resources=names.read(run/'original-name-resources.json');sidecar=names.read(run/'original-names.json');bindings=names.read(run/'name-bindings.json')
  names.validate_bindings(resources,sidecar,v.read_json(run/'sources.json'),bindings,markdown_only=True)
 if not (run/'frozen.json').exists():tp.freeze(run,development,delivery_gate=True)
 frozen=v.read_json(run/'frozen.json')
 for n,h in frozen['output_hashes'].items():
  if v.digest((run/n).read_bytes())!=h:raise ValueError('frozen output changed: '+n)
 sources={u['id']:u['source'] for u in v.read_json(run/'sources.json')};arms=['candidate'] if development else ['baseline','candidate'];results={}
 for arm in arms:
  path=run/(arm+'-delivery.json')
  if not path.exists():results[arm]=[{'kind':'missing_valid_delivery'}];continue
  checked=scan_records(v.read_json(run/'sources.json'),v.read_json(path),profile)
  if names is not None:
   bound=names.check(resources,sidecar,v.read_json(run/'sources.json'),v.read_json(path),bindings)['name_binding_check']
   checked['units']+=bound['bindings']+[{'kind':'name_binding_configuration_error','detail':e} for e in bound['configuration_errors']]
  results[arm]=checked['units']+[{'kind':'identity_error','detail':e} for e in checked['identity_errors']]
 allowed=not frozen.get('structural_errors') and all(all(not row.get('findings') and 'kind' not in row for row in rows) for rows in results.values())
 out={'release_allowed':allowed,'status':'ready-for-semantic-review' if allowed else 'BLOCKED','parser':manifest['delivery_parser'],'checked_output_hashes':frozen['output_hashes'],'profile_sha256':v.digest((run/'delivery-profile.json').read_bytes()),'findings':results,'gate_scope':'Basic delivery only; true does not authorize automatic publication or replace semantic review.','note':'No text changed. Passing basic gate is not semantic/fluency proof. A blocked result cannot be automatically delivered as clean final.'};v.dump(run/'delivery-gate.json',out);return out

def main():
 p=argparse.ArgumentParser();s=p.add_subparsers(dest='command',required=True);q=s.add_parser('scan');q.add_argument('sources');q.add_argument('translations');q.add_argument('--profile');q.add_argument('--output');q=s.add_parser('prepare');q.add_argument('cases');q.add_argument('out');q.add_argument('--profile');
 for name in ['polish','release']:
  q=s.add_parser(name);q.add_argument('run');q.add_argument('--development',action='store_true')
 a=p.parse_args()
 if a.command=='scan':
  profile=v.read_json(a.profile) if a.profile else {'allowed_latin':[]};result=scan_records(v.read_json(a.sources),v.read_json(a.translations),profile);result['policy']='Latest Chinese-delivery gate; findings are blockers, not automatic semantic error counts'
  if a.output:v.dump(a.output,result)
  print(json.dumps(result,ensure_ascii=False,indent=2))
  if not result['release_allowed']:raise SystemExit(2)
 elif a.command=='prepare':prepare(v.read_json(a.cases),a.out,v.read_json(a.profile) if a.profile else {'allowed_latin':[]})
 elif a.command=='polish':polish(a.run,a.development)
 else:
  result=release(a.run,a.development);print(json.dumps(result,ensure_ascii=False,indent=2))
  if not result['release_allowed']:raise SystemExit(2)
if __name__=='__main__':main()
