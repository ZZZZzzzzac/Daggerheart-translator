#!/usr/bin/env python3
"""Render a standalone, paginated translation-audit review report (standard library only)."""
import argparse, html, json, pathlib

REQUIRED = ('finding_id', 'id', 'title', 'label', 'status', 'severity', 'problem', 'suggestion', 'original', 'translation', 'original_focus', 'translation_focus', 'location')

def validate_link(value):
    from urllib.parse import urlsplit
    if not isinstance(value, str):raise ValueError('Source URL must be text')
    if not value:return
    try:
        link = urlsplit(value)
        valid = link.scheme == 'https' and link.hostname and not link.username and not link.password
    except ValueError:
        valid = False
    if not valid:raise ValueError('Source links must be absolute HTTPS links without credentials')

def render(data):
    if data.get('schemaVersion') != 1 or not isinstance(data.get('reportId'), str) or not data['reportId']:
        raise ValueError('schemaVersion=1 and stable reportId are required')
    if not isinstance(data.get('title'), str):
        raise ValueError('title must be a string')
    rows=data.get('findings')
    if not isinstance(rows,list):
        raise ValueError('findings must be an array')
    for key in ('progressFormat','storagePrefix','notes','emptyMessage','sourceDescription','sourceCutoff','progressNotice'):
        if key in data and not isinstance(data[key],str):raise ValueError('Invalid optional text field')
    ids=set()
    for f in rows:
        if not isinstance(f,dict) or any(k not in f for k in REQUIRED): raise ValueError('Missing finding fields')
        if not isinstance(f['finding_id'],str) or not f['finding_id'] or f['finding_id'] in ids: raise ValueError('Invalid/duplicate finding_id')
        ids.add(f['finding_id'])
        if f['status'] not in ('confirmed','uncertain'):raise ValueError('Invalid status')
        if any(not isinstance(f[k],str) for k in REQUIRED if k!='id'):raise ValueError('Finding fields must be strings except id')
        for key in ('url', 'provider'):
            if key in f and not isinstance(f[key], str):raise ValueError('Optional source fields must be strings')
        if 'url' in f:validate_link(f['url'])
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
        contexts=f.get('related_contexts',[])
        if not isinstance(contexts,list):raise ValueError('Related contexts must be an array')
        for c in contexts:
            if not isinstance(c,dict) or not all(isinstance(c.get(k),str) for k in ('label','original','translation')):raise ValueError('Bad related context')
            if 'url' in c:validate_link(c['url'])
        for field in ('reference_evidence', 'official_evidence'):
            if f.get(field):
                c=f[field]
                if not isinstance(c,dict) or not isinstance(c.get('text'),str):raise ValueError('Bad reference evidence')
                if 'url' in c:validate_link(c['url'])
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
