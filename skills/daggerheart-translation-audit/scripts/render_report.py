#!/usr/bin/env python3
"""Render a standalone, paginated translation-audit review report (standard library only)."""
import argparse, html, json, pathlib

REQUIRED = ('finding_id', 'id', 'url', 'title', 'label', 'status', 'severity', 'problem', 'suggestion', 'original', 'translation', 'original_focus', 'translation_focus', 'location')

def render(data):
    if data.get('schemaVersion') != 1 or not isinstance(data.get('reportId'), str) or not data['reportId']:
        raise ValueError('schemaVersion=1 and stable reportId are required')
    if not isinstance(data.get('title'), str) or not isinstance(data.get('sourceCutoff'), str):
        raise ValueError('title and sourceCutoff must be strings')
    rows=data.get('findings')
    if not isinstance(rows,list) or not rows:
        raise ValueError('findings must be a nonempty array')
    for key in ('progressFormat','storagePrefix','notes'):
        if key in data and not isinstance(data[key],str):raise ValueError('Invalid optional text field')
    ids=set()
    for f in rows:
        if not isinstance(f,dict) or any(k not in f for k in REQUIRED): raise ValueError('Missing finding fields')
        if not isinstance(f['finding_id'],str) or not f['finding_id'] or f['finding_id'] in ids: raise ValueError('Invalid/duplicate finding_id')
        ids.add(f['finding_id'])
        if f['status'] not in ('confirmed','uncertain'):raise ValueError('Invalid status')
        if any(not isinstance(f[k],str) for k in REQUIRED if k!='id'):raise ValueError('Finding fields must be strings except id')
        if not f['url'].startswith('https://'):raise ValueError('Source links must use https')
        if not isinstance(f['id'],(int,str)) or isinstance(f['id'],bool):raise ValueError('Invalid source id')
        for lang in ('original','translation'):
            pieces=f.get(lang+'_segments')
            if pieces is not None:
                if not isinstance(pieces,list) or not all(isinstance(x,str) and x in f[lang] for x in pieces):raise ValueError('Focus segments must be exact source substrings')
                if f[lang+'_focus']!='\n\n'.join(pieces):raise ValueError('Focus must match source segment join')
            elif f[lang+'_focus'] not in f[lang]:raise ValueError('Focus must be an exact source substring')
        for lang in ('original','translation'):
            full=f[lang]; hs=f.get(lang+'_highlights',[])
            if not isinstance(hs,list):raise ValueError('Highlights must be arrays')
            previous=0
            for h in hs:
                if not isinstance(h,dict) or any(not isinstance(h.get(k),int) or isinstance(h.get(k),bool) for k in ('start','end')):raise ValueError('Highlight offsets must be code-point integers')
                start,end=h['start'],h['end']
                if not 0<=start<end<=len(full) or start<previous:raise ValueError('Highlights must be in bounds, ordered and nonoverlapping')
                if not isinstance(h.get('reason'),str) or not h['reason'].strip():raise ValueError('Highlight reason required')
                if 'text' in h and h['text']!=full[start:end]:raise ValueError('Highlight text must equal exact source slice')
                previous=end
            parts=f.get(lang+'_segments',[f[lang+'_focus']]); ranges=f.get(lang+'_focus_ranges')
            if ranges is not None:
                if not isinstance(ranges,list) or len(ranges)!=len(parts):raise ValueError('Focus range/segment count mismatch')
                previous=0
                for r,part in zip(ranges,parts):
                    if not isinstance(r,dict) or any(not isinstance(r.get(k),int) or isinstance(r.get(k),bool) for k in ('start','end')):raise ValueError('Invalid focus range')
                    start,end=r['start'],r['end']
                    if not 0<=start<=end<=len(full) or start<previous or full[start:end]!=part:raise ValueError('Focus range must anchor its exact source occurrence')
                    previous=end
            else:
                previous=0
                for part in parts:
                    start=full.find(part)
                    if part and full.find(part,start+1)!=-1:
                        raise ValueError('Repeated focus text requires explicit focus_ranges; do not guess its occurrence')
                    if start<previous:raise ValueError('Inferred focus ranges must preserve source order and not overlap')
                    previous=start+len(part)
        for c in f.get('related_contexts',[]):
            if not all(isinstance(c.get(k),str) for k in ('label','original','translation')):raise ValueError('Bad related context')
            if c.get('url') and not c['url'].startswith('https://'):raise ValueError('Bad related URL')
        if f.get('official_evidence'):
            c=f['official_evidence']
            if not isinstance(c.get('text'),str) or not c.get('url','').startswith('https://'):raise ValueError('Bad official evidence')
    base=pathlib.Path(__file__).resolve().parents[1]/'assets'
    payload=json.dumps(data,ensure_ascii=False,separators=(',',':')).replace('&','\\u0026').replace('<','\\u003c').replace('>','\\u003e').replace('\u2028','\\u2028').replace('\u2029','\\u2029')
    values={'__TITLE__':html.escape(data['title']),'__CSS__':(base/'report.css').read_text(),'__JS__':(base/'report.js').read_text(),'__DATA__':payload}
    template=(base/'report.html').read_text()
    # One-pass replacement prevents input content from being interpreted as template directives.
    import re
    return re.sub('|'.join(map(re.escape,values)),lambda m:values[m.group()],template)

def main():
    ap=argparse.ArgumentParser();ap.add_argument('input',type=pathlib.Path);ap.add_argument('output',type=pathlib.Path);a=ap.parse_args()
    text=render(json.loads(a.input.read_text(encoding='utf-8')));a.output.parent.mkdir(parents=True,exist_ok=True);a.output.write_text(text,encoding='utf-8');print(a.output)

if __name__=='__main__':main()
