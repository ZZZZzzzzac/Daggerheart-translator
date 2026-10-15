#!/usr/bin/env python3
"""Render a saved UNCONFIRMED draft or quantity scan as standalone offline HTML.

This adapter reuses the audit skill's safe, code-point-aware review UI. It does
not parse Markdown into active HTML, align texts, approve configuration, compare
quantities, or change the inputs. Saved evidence is a snapshot, not a signature.
"""
import argparse
import base64
import hashlib
import html
import importlib.util
import json
from pathlib import Path
import re

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
NOTICE = '未确认 · 完成只记阅读进度，不批准配置或证明语义正确'
OFFSET_BASIS = 'Unicode code points in extracted_text, not raw Markdown'
STATIC_CSS = '''
#static-review{max-width:1400px;margin:0 auto;padding:24px;color:#182933}
#static-review h1{font-size:25px;margin:0 0 12px}
#static-review h2{font-size:20px;margin:0 0 8px;overflow-wrap:anywhere}
#static-review h3{font-size:16px;margin:16px 0 6px}
#static-review p{line-height:1.6;overflow-wrap:anywhere}
#static-review .static-notice{padding:12px 16px;background-color:#fff1ce;border:1px solid #d6ae54;border-radius:6px}
#static-review .static-entry{margin:24px 0;padding:20px;background-color:white;border:1px solid #c8d5de;border-radius:8px;break-inside:auto}
#static-review .static-meta{font-size:13px;color:#566872}
#static-review table{width:100%;table-layout:fixed;border-collapse:collapse;margin:14px 0}
#static-review th,#static-review td{width:50%;text-align:left;vertical-align:top;padding:12px;border:1px solid #c8d5de}
#static-review th{background-color:#edf1f4;font-size:14px}
#static-review .static-text{white-space:pre-wrap;overflow-wrap:anywhere;font-size:16px;line-height:1.6;margin:0;font-family:inherit}
#static-review mark,#static-review .static-highlight{background-color:#ffe58a;color:inherit;padding:0;border-radius:2px}
#static-review .static-highlight{font-weight:700;text-decoration:underline}
#static-review .static-translation mark,#static-review .static-translation .static-highlight{background-color:#ffd4b8}
#static-review .static-context{margin:18px 0 0;padding-top:10px;border-top:1px solid #c8d5de}
#static-review .static-missing{color:#695126;font-size:13px}
@media(max-width:700px){#static-review{padding:12px}#static-review .static-entry{padding:12px}#static-review th,#static-review td{padding:8px}}
'''


def _module(path):
    spec = importlib.util.spec_from_file_location('offline_' + path.stem, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _json(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(',', ':'), allow_nan=False)


def _digest(value):
    return hashlib.sha256(_json(value).encode('utf-8')).hexdigest()


def read(path):
    def unique(pairs):
        result = {}
        for key, value in pairs:
            if key in result:
                raise ValueError('duplicate JSON object key: ' + key)
            result[key] = value
        return result

    def invalid(value):
        raise ValueError('non-finite JSON number: ' + value)

    return json.loads(Path(path).read_text(encoding='utf-8'),
                      object_pairs_hook=unique, parse_constant=invalid)


def _text(value, label):
    if not isinstance(value, str):
        raise ValueError(label + ' must be text')
    return value


def _array(value, label):
    if not isinstance(value, list):
        raise ValueError(label + ' must be an array')
    return value


def _finding(identity, uid, title, original, translation, problem, location):
    return {'finding_id': _digest(identity), 'id': uid, 'title': title,
            'label': title, 'status': 'uncertain', 'severity': 'review',
            'problem': problem,
            'suggestion': '人工回查完整上下文、归属和对应关系；此页不批准配置，也不修改原译文。',
            'original': original, 'translation': translation,
            'original_focus': original, 'translation_focus': translation,
            'original_focus_ranges': [{'start': 0, 'end': len(original)}],
            'translation_focus_ranges': [{'start': 0, 'end': len(translation)}],
            'original_highlights': [], 'translation_highlights': [],
            'location': location}


def _whole(text, reason):
    return [{'start': 0, 'end': len(text), 'text': text, 'reason': reason}] if text else []


def _context(source, translation):
    return [{'label': '完整原始 Markdown（仅文本展示，不按数量偏移高亮）',
             'original': source, 'translation': translation}]


def _draft_findings(data):
    helper = _module(HERE / 'config_preview.py')
    if data.get('approval_status') != 'unconfirmed' or data.get('semantic_verified') is not False:
        raise ValueError('draft must remain unconfirmed and semantically unverified')
    preview = data['preview']
    if (preview.get('format') != helper.PREVIEW_VERSION or
            preview.get('approval_status') != 'unconfirmed' or
            preview.get('semantic_verified') is not False or
            data.get('preview_sha256') != _digest(preview)):
        raise ValueError('invalid or modified draft preview snapshot')
    selection = preview['selection']
    uid, rid = selection['unit_id'], selection['resource_id']
    _text(uid, 'unit ID'); _text(rid, 'resource ID')
    if data.get('proposed_parent') != dict(selection, approval_status='unconfirmed'):
        raise ValueError('draft parent disagrees with the selected snapshot')
    sides = preview['sides']
    raw = {side: _text(sides[side]['raw_text'], side + ' raw text') for side in ('source', 'translation')}
    blocks = {side: _array(sides[side]['blocks'], side + ' blocks') for side in raw}

    def block(side, selector):
        index = selector.get('block')
        if type(index) is not int or not 0 <= index < len(blocks[side]):
            raise ValueError('invalid selected block')
        result = blocks[side][index]
        if result.get('block') != index:
            raise ValueError('block index disagrees with snapshot')
        return result

    findings, targets = [], set()
    for item in _array(data['proposed_name_bindings'], 'name bindings'):
        if (item.get('approval_status') != 'unconfirmed' or item.get('unit_id') != uid or
                item.get('resource_id') != rid):
            raise ValueError('name selection disagrees with unconfirmed parent')
        selector = item['selector']
        selected = block('translation', selector)
        base_selector = selected['name_candidate']['selector']
        if {k: v for k, v in selector.items() if k != 'suffix'} != base_selector:
            raise ValueError('name selector disagrees with snapshot')
        target = _json(base_selector)
        if target in targets:
            raise ValueError('duplicate name target')
        targets.add(target)
        rows = [row for row in preview['name_choices']
                if row['resource_id'] == rid and row['name_pointer'] == item['name_pointer']]
        if len(rows) != 1 or rows[0]['translation'] != item['expected_name']:
            raise ValueError('name pointer or expected name disagrees with snapshot')
        ast = [b['ast'] for b in blocks['translation']]
        observed = helper.bindings._markdown_name(ast, selector)
        if observed != item['observed_name']:
            raise ValueError('observed name disagrees with selected AST slot')
        # The slot is structurally anchored at the start, never found by keyword.
        try:
            target_text = helper.quantities._block(selected['ast'])
            start = len(target_text) - len(target_text.lstrip())
            if target_text[start:start + len(observed)] != observed:
                raise ValueError('name prefix does not match the selected block')
            display = '译文显示所选块的可见文字；只高亮名称槽位，后缀及重复正文词不高亮。'
        except ValueError:
            target_text, start = observed, 0
            display = '此块正文含不支持的结构，译文只显示提取的名称槽位；完整原始文本见关联上下文。'
        ref = rows[0]
        problem = ('UNCONFIRMED：资源归属、名称身份及原译文对应关系均待核对。\n'
                   '未指定原文名称位置：左侧保留完整原文，不按同名词面推断位置。\n'
                   + display + '\n资源原名参考（不是正文位置证据）：' + _json(ref.get('original')) +
                   '；状态：' + _text(ref['status'], 'original status') + '\n期望名称：' +
                   _text(item['expected_name'], 'expected name') + '；所选名称：' + observed +
                   '\n资源：' + rid + '；名称路径：' + item['name_pointer'])
        f = _finding(['draft-name', rid, item['name_pointer'], uid, selector], uid,
                     '未确认名称槽位 · ' + item['expected_name'], raw['source'], target_text,
                     problem, 'unit ' + uid + ' · translation ' + selected['ast_path'])
        if observed:
            f['translation_highlights'] = [{'start': start, 'end': start + len(observed),
                                           'text': observed, 'reason': '人工选中的名称槽位；身份未确认'}]
        f['related_contexts'] = _context(raw['source'], raw['translation'])
        findings.append(f)
    endpoints = set()
    for item in _array(data['proposed_quantity_scopes'], 'quantity scopes'):
        if item.get('approval_status') != 'unconfirmed' or item.get('unit_id') != uid:
            raise ValueError('quantity selection disagrees with unconfirmed parent')
        texts, locations = {}, []
        for side in raw:
            candidate = item[side]
            selected = block(side, candidate['selector'])
            endpoint = (side, selected['block'])
            if endpoint in endpoints:
                raise ValueError('duplicate quantity endpoint')
            endpoints.add(endpoint)
            if candidate != selected.get('quantity_candidate'):
                raise ValueError('quantity choice disagrees with snapshot')
            texts[side] = helper.quantities._block(selected['ast'])
            if texts[side] != candidate['text']:
                raise ValueError('quantity text disagrees with selected AST block')
            locations.append(side + ' ' + selected['ast_path'])
        f = _finding(['draft-quantity', uid, item['id']], uid,
                     '未确认数量范围 · ' + _text(item['id'], 'scope ID'),
                     texts['source'], texts['translation'],
                     'UNCONFIRMED：两侧整块高亮只表示人工选择的范围，不是数字风险证据。\n'
                     '此草稿未运行数字比较；没有批准范围对应关系，数字相同也不能证明语义正确。',
                     'unit ' + uid + ' · ' + ' / '.join(locations))
        f['original_highlights'] = _whole(texts['source'], '未确认的所选原文范围，不是数量风险')
        f['translation_highlights'] = _whole(texts['translation'], '未确认的所选译文范围，不是数量风险')
        f['related_contexts'] = _context(raw['source'], raw['translation'])
        findings.append(f)
    return findings, '配置草稿：仅显示已显式选择的位置；未选择的内容不算已审。'


def _quantity_side(evidence, side, uid):
    if not isinstance(evidence, dict) or evidence.get('side') != side or evidence.get('unit_id') != uid:
        raise ValueError('quantity evidence side or unit disagrees with its scope')
    if evidence.get('offset_basis') != OFFSET_BASIS:
        raise ValueError('quantity offsets must explicitly refer to extracted_text')
    text = _text(evidence.get('extracted_text', ''), 'extracted_text')
    if 'extracted_text' not in evidence and 'unavailable' not in evidence:
        raise ValueError('quantity evidence requires extracted_text or unavailable reason')
    highlights = []
    for key in ('tokens', 'uncertain'):
        for item in _array(evidence.get(key, []), key):
            start, end = item.get('start'), item.get('end')
            if (type(start) is not int or type(end) is not int or
                    not 0 <= start < end <= len(text) or item.get('quote') != text[start:end]):
                raise ValueError('quantity quote must match its exact extracted_text code-point range')
            reason = ('数量表面证据，未核对语义：' + _text(item['kind'], 'token kind') + '=' +
                      _text(item['value'], 'token value')) if key == 'tokens' else (
                          '不确定数量表达：' + _text(item['reason'], 'uncertain reason'))
            highlights.append({'start': start, 'end': end, 'text': item['quote'], 'reason': reason})
    highlights.sort(key=lambda h: (h['start'], h['end']))
    if any(a['end'] > b['start'] for a, b in zip(highlights, highlights[1:])):
        raise ValueError('quantity evidence ranges overlap')
    return text, highlights


def _quantity_findings(data):
    if data.get('version') != 'mechanic-quantity-scopes-v1' or data.get('semantic_verified') is not False:
        raise ValueError('expected a semantically unverified quantity risk report')
    if data.get('status') not in {'needs_review', 'quantity_surface_match', 'no_scopes_configured'}:
        raise ValueError('invalid quantity report status')
    findings, ids = [], set()
    for scope in _array(data.get('scopes'), 'scopes'):
        uid, sid = _text(scope['unit_id'], 'unit ID'), _text(scope['id'], 'scope ID')
        if not sid or sid in ids:
            raise ValueError('invalid or duplicate scope ID')
        ids.add(sid)
        if scope.get('semantic_verified') is not False:
            raise ValueError('scope cannot claim semantic verification')
        status = scope['status']
        if status not in {'needs_review', 'quantity_surface_match'}:
            raise ValueError('invalid scope status')
        left, lh = _quantity_side(scope['source'], 'source', uid)
        right, rh = _quantity_side(scope['translation'], 'translation', uid)
        risks = _array(scope['risks'], 'risks')
        detail = '\n'.join(_text(r['kind'], 'risk kind') + '：' + _text(r['detail'], 'risk detail') for r in risks)
        title = ('数量风险待审' if status == 'needs_review' else '数量表面相同，语义未核对') + ' · ' + sid
        locations, notes = [], []
        for side in ('source', 'translation'):
            ev = scope[side]
            locations.append(side + ' ' + _json(ev['selector']))
            notes.append(side + ' 定位：' + _text(ev.get('field_pointer', '不可用'), 'field pointer') +
                         '；AST：' + _json(ev.get('ast_paths', [])))
            if 'unavailable' in ev:
                notes.append(side + ' 无法提取：' + _text(ev['unavailable'], 'unavailable reason'))
        f = _finding(['quantity', uid, sid], uid, title, left, right,
                     '这是风险线索，不是确认译错。数字相同也不能证明主体、单位、条件或语义正确。\n'
                     '高亮严格对应 extracted_text 的 Unicode 码点偏移，不是原始 Markdown 偏移。\n'
                     + detail + '\n' + '\n'.join(notes), 'unit ' + uid + ' · ' + ' / '.join(locations))
        f['original_highlights'], f['translation_highlights'] = lh, rh
        f['related_contexts'] = _context(
            _text(scope['source'].get('raw_text', left), 'raw source'),
            _text(scope['translation'].get('raw_text', right), 'raw translation'))
        findings.append(f)
    errors = _array(data.get('configuration_errors'), 'configuration errors')
    for index, error in enumerate(errors):
        findings.append(_finding(['configuration-error', index, error], 'configuration',
                                 '配置错误 · 无法完成数量范围核对', '', '',
                                 _text(error, 'configuration error'), 'configuration'))
    return findings, ('数量报告仅包含显式范围，未扫描或未配置的内容不算已审。'
                      '输入状态：' + data['status'] + '；配置错误：' + str(len(errors)))


def to_report(data):
    """Adapt saved evidence without approving it or re-running a comparison."""
    if not isinstance(data, dict):
        raise ValueError('input must be an object')
    if data.get('format') == 'pbres-config-draft-v1':
        findings, coverage = _draft_findings(data)
    else:
        quantity = data.get('quantity_risk_check', data)
        if not isinstance(quantity, dict):
            raise ValueError('quantity_risk_check must be an object')
        findings, coverage = _quantity_findings(quantity)
    return {'schemaVersion': 1, 'reportId': 'offline-config-' + _digest(data),
            'title': '离线配置与数量证据审阅 · 未确认', 'findings': findings,
            'progressFormat': 'offline-config-reading-progress', 'progressNotice': NOTICE,
            'sourceDescription': coverage,
            'notes': '这是输入快照；本页不证明它与当前项目文件一致。名称槽位、范围边界和数字证据分别说明；'
                     '不自动配对，不批准配置，不修改原译文，也不证明译文正确。',
            'emptyMessage': coverage + ' 当前没有可显示的条目；空队列不等于审核通过。'}


def _escape_static(text, quote=True):
    # HTML tokenizers normalize literal CRLF/CR to LF. A character reference
    # keeps the original code point and therefore the evidence offset basis.
    if '\x00' in text:
        raise ValueError('displayed text contains NUL, which HTML cannot preserve losslessly')
    return html.escape(text, quote=quote).replace('\r', '&#13;')


def _static_text(text, highlights):
    """Build inert marks from validated code-point slices, never a substring search."""
    parts, cursor = [], 0
    for mark in highlights:
        parts.append(_escape_static(text[cursor:mark['start']]))
        parts.append('<mark title="' + _escape_static(mark['reason'], quote=True) + '"><strong class="static-highlight">' +
                     _escape_static(text[mark['start']:mark['end']]) + '</strong></mark>')
        cursor = mark['end']
    parts.append(_escape_static(text[cursor:]))
    return ''.join(parts)


def _static_report(report):
    escape = _escape_static
    parts = ['<div id="static-review" role="main" aria-label="完整离线静态审阅">',
             '<h1>' + escape(report['title']) + '</h1>',
             '<p class="static-notice">' + escape(NOTICE) +
             '。全部条目已在下方显示，无需 JavaScript。脚本成功启动后可使用逐条浏览与进度功能。</p>',
             '<p>' + escape(report['sourceDescription']) + '</p>',
             '<p>' + escape(report['notes']) + '</p>']
    if not report['findings']:
        parts.append('<p>' + escape(report['emptyMessage']) + '</p>')
    for index, finding in enumerate(report['findings'], 1):
        parts.extend(['<div class="static-entry" role="article" data-finding-id="' + escape(finding['finding_id'], quote=True) + '">',
                      '<h2>' + str(index) + '. ' + escape(finding['title']) + '</h2>',
                      '<p class="static-meta">待核实 · ' + escape(finding['location']) + '</p>',
                      '<table width="100%"><thead><tr><th scope="col" width="50%">原文</th><th scope="col" width="50%">现译</th></tr></thead><tbody><tr>'])
        for side in ('original', 'translation'):
            parts.append('<td class="static-' + side + '"><div class="static-text" data-side="' + side + '">' +
                         _static_text(finding[side], finding[side + '_highlights']) + '</div>')
            if not finding[side]:
                parts.append('<p class="static-missing">此侧没有可显示的文本，详见下方说明。</p>')
            parts.append('</td>')
        parts.extend(['</tr></tbody></table><h3>待核对事项</h3>',
                      '<div class="static-text">' + escape(finding['problem']) + '</div>',
                      '<h3>建议</h3><p>' + escape(finding['suggestion']) + '</p>'])
        for context in finding.get('related_contexts', []):
            parts.extend(['<div class="static-context"><h3>' + escape(context['label']) + '</h3>',
                          '<h3>原文</h3><div class="static-text">' + escape(context['original']) + '</div>',
                          '<h3>现译</h3><div class="static-text">' + escape(context['translation']) + '</div></div>'])
        parts.append('</div>')
    parts.append('</div>')
    return ''.join(parts)


def render(data):
    renderer = _module(ROOT / 'skills/daggerheart-translation-audit/scripts/render_report.py')
    report = to_report(data)
    output = renderer.render(report)  # Validate every span before generating static marks.
    output = output.replace('<main id="app">', _static_report(report) + '<main id="app" hidden>', 1)
    output = output.replace('<dialog id="more">', '<div id="enhanced-menu" hidden><dialog id="more">', 1)
    output = output.replace('</dialog>', '</dialog></div>', 1)
    output = output.replace('</head>', '<style>' + STATIC_CSS + '</style></head>', 1)
    output = output.replace('<noscript>此报告的逐条阅读与高亮需要JavaScript。请在支持JavaScript的浏览器中打开。</noscript>', '', 1)

    def enhance(match):
        script = match.group(1)
        ready = 'requestAnimationFrame(()=>render());'
        if script.count(ready) != 1:
            raise ValueError('audit initialization contract changed; static fallback must stay visible until render succeeds')
        # Adapt only the trusted executable script, never JSON/input strings.
        script = script.replace(ready, "requestAnimationFrame(()=>{render();el('enhanced-menu').hidden=false;el('app').hidden=false;el('static-review').hidden=true;});")
        return '<script>' + script + '</script>'

    output = re.sub(r'<script>(.*?)</script>', enhance, output, flags=re.S)
    # Only the existing local renderer script/style are permitted. No network,
    # embedded objects, forms, remote images, or injected executable markup.
    def hashes(tag):
        return ' '.join("'sha256-" + base64.b64encode(hashlib.sha256(text.encode('utf-8')).digest()).decode('ascii') + "'"
                        for text in re.findall('<' + tag + '>(.*?)</' + tag + '>', output, re.S))
    policy = ("default-src 'none'; connect-src 'none'; object-src 'none'; base-uri 'none'; "
              "form-action 'none'; script-src " + hashes('script') + '; style-src ' + hashes('style'))
    return output.replace('<head>', '<head><meta http-equiv="Content-Security-Policy" content="' + policy + '">', 1)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('input', type=Path, help='saved config draft or quantity scan report JSON')
    parser.add_argument('output', type=Path, help='new standalone HTML file (never overwritten)')
    args = parser.parse_args()
    try:
        output = render(read(args.input))
        args.output.parent.mkdir(parents=True, exist_ok=True)
        with args.output.open('x', encoding='utf-8') as file:
            file.write(output)
        print(args.output)
    except (ValueError, KeyError, TypeError, IndexError, AttributeError, OSError) as error:
        parser.exit(2, 'offline config report: ' + str(error) + '\n')


if __name__ == '__main__':
    main()
