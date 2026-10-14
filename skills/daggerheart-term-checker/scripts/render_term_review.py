"""HTML presentation for main's existing per-occurrence checker, not a new gate.

Uses the checker's unchanged pairing and marker parser. Full TARGET sections
are shown; malformed/missing TARGET falls back to the actual whole chunk.
"""
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import tempfile

NOTICE = '完成仅记阅读进度，不批准译文、不放行。'


def snapshot_inputs(project):
    base = Path(project) / 'source/temp'
    return {f'{folder}/{p.name}': p.read_bytes()
            for folder in ('_chunks', '_translated_chunks')
            for p in sorted((base / folder).glob('*.md')) if not p.name.startswith('_prompt_')}


def digest(value):
    return hashlib.sha256(json.dumps(value, ensure_ascii=False, sort_keys=True,
                                    separators=(',', ':')).encode('utf-8')).hexdigest()


def display_text(text, parser):
    """Keep all nonmarker text and map each exact marker occurrence to code points."""
    out, positions, cursor, length = [], {}, 0, 0
    for match in parser.MARKER_RE.finditer(text):
        before, first = text[cursor:match.start()], match.group(1).strip()
        out.extend((before, first))
        length += len(before)
        positions[match.start()] = (length, length + len(first))
        length += len(first)
        cursor = match.end()
    out.append(text[cursor:])
    return ''.join(out), positions


def report_data(report, snapshot):
    import check_terms as parser
    manifest = {k: hashlib.sha256(v).hexdigest() for k, v in snapshot.items()}
    identity = digest(dict(version=1, manifest=manifest, rows=report['rows'], stats=report['stats']))
    findings = []
    for ordinal, row in enumerate(report['rows']):
        texts, targets, maps, markers = {}, {}, {}, {}
        for side, folder in (('original', '_chunks'), ('translation', '_translated_chunks')):
            raw = snapshot.get(f"{folder}/{row['chunk']}.md", b'').decode('utf-8').replace('\r\n', '\n')
            target = parser._extract_kilo_target(raw)
            targets[side] = target
            # Missing target is a structural case: show actual file, not invented context.
            texts[side], maps[side] = display_text(target or raw, parser)
            markers[side] = parser._extract_markers(target)
        source = translation = None
        if row['index'] and '译文多出术语标记' not in row['anomalies']:
            source = next((m for m in markers['original'] if m['index'] == row['index']), None)
            if source is None or source['slot1'] != row['original']:
                raise ValueError('HTML 原文定位与当前报告不匹配')
            pairs, _, _, _ = parser._pair_markers(markers['original'], markers['translation'])
            ti = pairs.get(source['index'] - 1)
            translation = markers['translation'][ti] if ti is not None else None
        elif row['index'] and row['current']:
            translation = next((m for m in markers['translation'] if m['index'] == row['index']), None)
        if (translation['slot1'] if translation else '') != row['current']:
            raise ValueError('HTML 译文定位与当前报告不匹配')
        highlights = {}
        for side, marker in (('original', source), ('translation', translation)):
            values = []
            if marker:
                start, end = maps[side][marker['pos']]
                if start < end:
                    values.append(dict(start=start, end=end, text=texts[side][start:end], reason='本条术语的实际出现位置'))
            highlights[side + '_highlights'] = values
        anomaly = '；'.join(row['anomalies'])
        finding_id = 'term-' + digest(dict(row=row, ordinal=ordinal))[:24]
        findings.append(dict(
            finding_id=finding_id, id=finding_id, title='结构异常' if anomaly else '术语待语境核对',
            label=f"{row['chunk']} · {row['original'] or row['current'] or '结构检查'}",
            status='uncertain', severity='结构异常' if anomaly else '逐项核对',
            location=f"{row['chunk']}.md · TARGET · 术语位置 {row['index']}",
            original=texts['original'], translation=texts['translation'],
            original_focus=texts['original'], translation_focus=texts['translation'],
            problem='\n'.join([f"原词：{row['original']}；当前译法：{row['current']}",
                                f"表内推荐：{row['recommended']}；词面采用：{row['adopted_recommendation']}",
                                '注释：' + (row['note'] or '无'), '异常：' + (anomaly or '此项未报告结构异常')]),
            suggestion='先修复结构异常，再重新生成报告。' if anomaly else
                       '结合完整原译文判断是否采用表内推荐；词面一致不代表语义正确。需要修改时沿用既有流程修改译文，再重新生成报告。',
            reference_evidence=dict(text='来源：source/temp/_chunks/' + row['chunk'] + '.md\n现译：source/temp/_translated_chunks/' + row['chunk'] + '.md\n正常条目展示完整 TARGET；区段缺失时展示实际整个文件。对位沿用原 checker，兜底或重复键仍需人工核对。'),
            **highlights))
    stats = report['stats']
    return dict(schemaVersion=1, title='术语逐项审阅', reportId='main-term-review:' + identity,
                progressFormat='main-term-review-reading-progress', progressNotice='完成仅记进度，不批准/放行', findings=findings,
                sourceDescription=f"共 {stats['total_rows']} 条；{stats['structural_anomalies']} 条结构异常。保留全部出现位置。",
                notes=NOTICE + '\n词面统计和浏览进度都不是语义审阅完成证明。手动模式仍需用户明确确认；此页面不写审批或译文。\n内容版本：' + identity,
                emptyMessage='没有检测到术语标记；不代表全文已审阅或译文正确。' + NOTICE)


def render_html(report, snapshot):
    path = Path(__file__).resolve().parents[2] / 'daggerheart-translation-audit/scripts/render_report.py'
    spec = importlib.util.spec_from_file_location('term_audit_renderer', path)
    renderer = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(renderer)
    return renderer.render(report_data(report, snapshot))


def write_html_report(report, snapshot, path):
    text = render_html(report, snapshot)
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(mode='w', encoding='utf-8', dir=path.parent,
                                         prefix='.' + path.name + '.', delete=False) as out:
            temporary = Path(out.name)
            out.write(text)
            out.flush()
            os.fsync(out.fileno())
        os.replace(temporary, path)
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)
