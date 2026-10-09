"""Export source-verified human question cards; never grant approval.

--prepare writes current hashes, decisions and exact selectable units.
Otherwise validate _human_review.json and write _human_review_cards.md/json.
Display transform: UTF-8, CRLF -> LF, first-slot marker rendering (trimmed as
in the marker parser), then remove one final LF. No other rewriting or clipping.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import sys
import tempfile

from check_terms import build_report
from term_markers import parse_markers
from term_review import digest

SCHEMA = 'contextual-human-review-v1'
SECTIONS = ('TARGET', 'CONTEXT_PREV', 'CONTEXT_NEXT')
FOLDERS = {'source': '_chunks', 'translation': '_translated_chunks'}
HEADING = re.compile(r'^ {0,3}(#{1,6})[ \t]+\S')
KINDS = {'translation_blocker': '译文交付阻断', 'optional_rule_ruling': '可选源规则裁定'}


def unique_keys(pairs):
    value = {}
    for key, item in pairs:
        if key in value:
            raise ValueError('重复 JSON 字段: ' + key)
        value[key] = item
    return value


def atomic_write(path, text):
    """Replace directory entries, never follow old output symlinks/hardlinks."""
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


def required_text(value, label):
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f'{label} 必须是非空文本')
    return value


def render(text):
    """Only the documented transform; marker metadata is never original text."""
    markers, errors = parse_markers(text)
    if errors:
        raise ValueError('引文含损坏术语标记')
    pieces, cursor = [], 0
    for marker in markers:
        pieces.extend((text[cursor:marker['pos']], marker['slot1']))
        cursor = marker['end']
    pieces.append(text[cursor:])
    result = ''.join(pieces)
    return result[:-1] if result.endswith('\n') else result


def read_sections(project, manifest):
    result = {}
    for side, folder in FOLDERS.items():
        for name, expected_hash in sorted(manifest.items()):
            if not name.startswith(folder + '/'):
                continue
            path = Path(project) / 'source/temp' / name
            raw = path.read_bytes()
            if hashlib.sha256(raw).hexdigest() != expected_hash:
                raise ValueError('读取期间输入变化，请重新审阅')
            text = raw.decode('utf-8').replace('\r\n', '\n')
            for section in SECTIONS:
                lines = text.splitlines(keepends=True)
                starts = [i for i, line in enumerate(lines) if line.strip() == f'[[[KILO_{section}_START]]]']
                ends = [i for i, line in enumerate(lines) if line.strip() == f'[[[KILO_{section}_END]]]']
                if not starts and not ends and section != 'TARGET':
                    continue
                if len(starts) != 1 or len(ends) != 1 or starts[0] >= ends[0]:
                    raise ValueError(f'{side}/{path.stem}/{section} 包装缺失、重复或顺序错误')
                body = lines[starts[0] + 1:ends[0]]
                if render(''.join(body)).strip():
                    result[(side, path.stem, section)] = body
    return result


def unit_ranges(lines):
    """Whole Markdown heading sections; heading-free sections stay whole.

    Include every paragraph up to the next same/higher heading. This deliberately
    favors excess context to truncation; it cannot infer cross-chunk continuations.
    """
    headings = [(i, len(match.group(1))) for i, line in enumerate(lines)
                if (match := HEADING.match(line))]
    if not headings:
        return [(1, len(lines))]
    ranges = []
    if any(line.strip() for line in lines[:headings[0][0]]):
        ranges.append((1, headings[0][0]))
    for i, level in headings:
        end = next((j for j, other in headings if j > i and other <= level), len(lines))
        ranges.append((i + 1, end))
    return ranges


def reference(side, chunk, section, start, end, lines):
    return dict(side=side, chunk=chunk, section=section, start_line=start,
                end_line=end, text=render(''.join(lines[start - 1:end])))


def ref_key(ref):
    return tuple(ref[k] for k in ('side', 'chunk', 'section', 'start_line', 'end_line'))


def verified_ref(value, sections, side=None, whole_unit=False):
    if not isinstance(value, dict):
        raise ValueError('引文定位必须是对象')
    keys = ('side', 'chunk', 'section', 'start_line', 'end_line', 'text')
    if set(value) != set(keys):
        raise ValueError('引文必须包含且仅包含 side/chunk/section/start_line/end_line/text')
    if any(not isinstance(value[k], str) for k in ('side', 'chunk', 'section', 'text')):
        raise ValueError('引文定位和文本必须是字符串')
    if side is not None and value['side'] != side:
        raise ValueError('引文来源方向不匹配')
    lines = sections.get((value['side'], value['chunk'], value['section']))
    if lines is None:
        raise ValueError('引文引用未知或空 chunk/section')
    start, end = value['start_line'], value['end_line']
    if type(start) is not int or type(end) is not int or not 1 <= start <= end <= len(lines):
        raise ValueError('引文行号必须是区段内有效的 1-based 闭区间')
    if whole_unit and (value['section'] != 'TARGET' or (start, end) not in unit_ranges(lines)):
        raise ValueError('必须选择完整 TARGET 标题单元；无标题时使用整个 TARGET，不能截取句子')
    current = reference(value['side'], value['chunk'], value['section'], start, end, lines)
    if not value['text'].strip() or value['text'] != current['text']:
        raise ValueError('引文与当前真实文件不一致；禁止伪造、改写、截断或沿用旧原文/中文')
    return current


def current_inputs(project):
    report = build_report(project)
    if report['stats']['structural_anomalies']:
        raise ValueError('结构异常未修复，不能导出人工卡片')
    return report, read_sections(project, report['input_manifest'])


def prepare(project):
    report, sections = current_inputs(project)
    units = [reference(side, chunk, section, start, end, lines)
             for (side, chunk, section), lines in sorted(sections.items())
             for start, end in (unit_ranges(lines) if section == 'TARGET' else [(1, len(lines))])]
    return dict(schema_version=SCHEMA, input_digest=report['input_digest'],
                review_digest=report['review_digest'],
                required_chunks=sorted(key[1] for key in sections if key[0] == 'source' and key[2] == 'TARGET'),
                unresolved_decisions=[d for d in report['decisions'] if d['status'] == 'unresolved'],
                available_units=units,
                notice='这是准备材料，不是人工卡片或语义审校完成证明。按文档填写 _human_review.json 后运行导出。')


def normalized(text):
    return ' '.join(text.split())


def build_export(project, payload):
    report, sections = current_inputs(project)
    if not isinstance(payload, dict) or payload.get('schema_version') != SCHEMA:
        raise ValueError('人工审阅 schema_version 不匹配')
    for field in ('input_digest', 'review_digest'):
        if payload.get(field) != report[field]:
            raise ValueError(f'{field} 已失效；必须重新审阅，不能只替换哈希')
    coverage = payload.get('semantic_review')
    chunks = sorted(key[1] for key in sections if key[0] == 'source' and key[2] == 'TARGET')
    if not isinstance(coverage, dict) or coverage.get('completed') is not True:
        raise ValueError('缺少全文语义审阅完成声明')
    for field in ('reviewer', 'summary'):
        required_text(coverage.get(field), 'semantic_review.' + field)
    if coverage.get('reviewed_chunks') != chunks:
        raise ValueError('全文语义审阅 reviewed_chunks 必须完整、无重复并按当前 chunk 名排序')
    questions = payload.get('questions')
    if not isinstance(questions, list):
        raise ValueError('questions 必须是数组')
    unresolved = {d['id']: d for d in report['decisions'] if d['status'] == 'unresolved'}
    used_decisions, question_ids, fingerprints, cards = set(), set(), set(), {}
    for item in questions:
        if not isinstance(item, dict):
            raise ValueError('每个问题必须是对象')
        qid = required_text(item.get('id'), '问题 id')
        if qid in question_ids:
            raise ValueError('重复问题 id')
        question_ids.add(qid)
        kind = item.get('kind')
        if not isinstance(kind, str) or kind not in KINDS:
            raise ValueError('问题 kind 必须为 translation_blocker 或 optional_rule_ruling')
        problem = required_text(item.get('problem'), '疑点 problem')
        reason = required_text(item.get('reason'), '推荐理由 reason')
        required_text(item.get('context_reason'), '上下文充分性说明 context_reason')
        if item.get('context_complete') is not True:
            raise ValueError('缺少完整上下文核对声明 context_complete')
        src = verified_ref(item.get('source'), sections, 'source', True)
        zh = verified_ref(item.get('translation'), sections, 'translation', True)
        if src['chunk'] != zh['chunk']:
            raise ValueError('原文与当前中文必须位于对应 chunk')
        context = item.get('context')
        if not isinstance(context, list) or not context:
            raise ValueError('缺少必要上下文 context；单元自足时仍需引用其完整标题单元')
        context = [verified_ref(ref, sections) for ref in context]
        if not any(ref['side'] == 'source' for ref in context):
            raise ValueError('context 必须包含实际原文上下文')
        options = item.get('options')
        if not isinstance(options, list) or len(options) < 2:
            raise ValueError('每个问题至少需要两个具体选项')
        choices, texts = set(), set()
        for option in options:
            if not isinstance(option, dict) or set(option) != {'id', 'text'}:
                raise ValueError('选项必须包含 id/text')
            oid = required_text(option['id'], '选项 id')
            text = required_text(option['text'], '具体选项 text')
            norm = normalized(text).casefold()
            if oid in choices or norm in texts:
                raise ValueError('重复选项')
            choices.add(oid)
            texts.add(norm)
        if not isinstance(item.get('recommendation'), str) or item['recommendation'] not in choices:
            raise ValueError('recommendation 必须引用一个实际选项 id')
        decision_ids = item.get('decision_ids')
        if not isinstance(decision_ids, list) or not decision_ids or any(not isinstance(d, str) for d in decision_ids):
            raise ValueError('decision_ids 必须包含此问题对应的未决审计 ID')
        if len(set(decision_ids)) != len(decision_ids) or used_decisions.intersection(decision_ids):
            raise ValueError('重复决策/问题；同一独立问题不能重复提交')
        for did in decision_ids:
            if did not in unresolved:
                raise ValueError('未知或已接受的决策 ID: ' + did)
            decision = unresolved[did]
            decision_chunks = {o['chunk'] for o in decision['occurrences']} | ({decision['chunk']} if 'chunk' in decision else set())
            if src['chunk'] not in decision_chunks:
                raise ValueError('决策 ID 与原文 chunk 不匹配')
            for field, ref in (('source_context', src), ('translated_context', zh)):
                if not decision[field].strip() or normalized(decision[field]) not in normalized(ref['text']):
                    raise ValueError('决策对应引文不在选定完整单元中；不得以同 chunk 的另一能力代替')
        used_decisions.update(decision_ids)
        key = ref_key(src)
        fingerprint = (key, normalized(problem).casefold())
        if fingerprint in fingerprints:
            raise ValueError('同一单元重复疑点；请合并为一个独立问题')
        fingerprints.add(fingerprint)
        if key not in cards:
            for other in cards.values():
                ref = other['source']
                if (src['chunk'], src['section']) == (ref['chunk'], ref['section']) and max(src['start_line'], ref['start_line']) <= min(src['end_line'], ref['end_line']):
                    raise ValueError('原文单元重叠；同一能力请统一定位并合并为一张卡片')
            cards[key] = dict(id='card-' + digest(key)[:16], source=src, translation=zh, context=[], questions=[])
        card = cards[key]
        if card['translation'] != zh:
            raise ValueError('同一源文单元的中文定位不一致，请合并为一个完整译文单元')
        existing_context = {ref_key(ref) for ref in card['context']}
        for ref in context:
            if ref_key(ref) not in existing_context:
                card['context'].append(ref)
                existing_context.add(ref_key(ref))
        card['questions'].append(dict(id=qid, kind=kind, decision_ids=decision_ids, problem=problem,
                                      options=options, recommendation=item['recommendation'], reason=reason,
                                      context_reason=item['context_reason']))
    if used_decisions != set(unresolved):
        raise ValueError(f'遗漏 {len(set(unresolved) - used_decisions)} 个未决审计项；先由 AI 裁决或完整提交，禁止截断/虚报零')
    latest = build_report(project)
    if any(latest[key] != report[key] for key in ('input_digest', 'review_digest')):
        raise ValueError('验证期间输入或审阅内容变化，禁止导出')
    if {d['id'] for d in latest['decisions'] if d['status'] == 'unresolved'} != set(unresolved):
        raise ValueError('验证期间决策接受状态变化，请重新准备')
    result = dict(schema_version=SCHEMA, input_digest=report['input_digest'], review_digest=report['review_digest'],
                  semantic_review=coverage, counts=dict(independent_questions=len(questions), cards=len(cards),
                  translation_blockers=sum(q['kind'] == 'translation_blocker' for q in questions),
                  optional_rule_rulings=sum(q['kind'] == 'optional_rule_ruling' for q in questions),
                  unresolved_audit_decisions=len(unresolved)), cards=list(cards.values()),
                  limits='仅验证当前输入、引文、定位、必填字段和完整覆盖；不证明语义正确、上下文充分、问题独立性或审阅者身份，不构成批准。')
    result['export_digest'] = digest(result)
    return result


def locator(ref):
    return f"source/temp/{FOLDERS[ref['side']]}/{ref['chunk']}.md · {ref['section']}:L{ref['start_line']}-L{ref['end_line']}"


def contains(outer, inner):
    return ref_key(outer)[:3] == ref_key(inner)[:3] and outer['start_line'] <= inner['start_line'] <= inner['end_line'] <= outer['end_line']


def quote(text):
    return '\n'.join('> ' + line for line in text.split('\n'))


def render_markdown(export):
    counts = export['counts']
    lines = ['# 人工审阅卡片', '',
             f"独立问题 {counts['independent_questions']} 个；卡片 {counts['cards']} 张；覆盖未决审计项 {counts['unresolved_audit_decisions']} 个。",
             f"其中译文交付阻断 {counts['translation_blockers']} 个；可选源规则裁定 {counts['optional_rule_rulings']} 个（不等同于译文错误）。",
             '同一完整源文单元的问题合并展示；源文与当前中文只显示一次。无数量上限、无静默截断。',
             f"输入哈希：{export['input_digest']}", f"审阅哈希：{export['review_digest']}",
             f"导出哈希：{export['export_digest']}", export['limits'],
             f"全文审阅声明人：{export['semantic_review']['reviewer']}",
             '全文审阅声明：' + export['semantic_review']['summary'], '']
    for card in export['cards']:
        lines += [f"## {card['id']}（{len(card['questions'])} 个独立问题）", '',
                  '### 对应完整原文', locator(card['source']), quote(card['source']['text']), '',
                  '### 当前完整中文', locator(card['translation']), quote(card['translation']['text']), '',
                  '### 必要上下文']
        for ref in card['context']:
            lines.append(locator(ref))
            if contains(card['source'], ref) or contains(card['translation'], ref):
                lines.append('已包含于上方完整引文，不重复展示。')
            else:
                lines.append(quote(ref['text']))
        for q in card['questions']:
            lines += ['', f"### 问题 {q['id']} · {KINDS[q['kind']]}", '疑点：' + q['problem'],
                      '上下文核对：' + q['context_reason']]
            lines += [f"- {option['id']}：{option['text']}" for option in q['options']]
            recommended_text = next(o['text'] for o in q['options'] if o['id'] == q['recommendation'])
            lines += ['建议：' + q['recommendation'] + ' · ' + recommended_text, '理由：' + q['reason'],
                      '对应审计项：' + ', '.join(q['decision_ids'])]
        lines.append('')
    if not export['cards']:
        lines.append('本次登记 0 个未决问题；这是上述审阅者的全文审阅声明，不是脚本证明译文无误。')
    return '\n'.join(lines) + '\n'


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('project')
    parser.add_argument('--prepare', action='store_true', help='Only write current units/hashes; no human handoff')
    parser.add_argument('--review-file', help='Default: source/temp/_human_review.json')
    args = parser.parse_args(argv)
    if args.prepare and args.review_file:
        parser.error('--prepare 不能与 --review-file 混用')
    base = Path(args.project) / 'source/temp'
    try:
        if args.prepare:
            value = prepare(args.project)
            target = base / '_human_review_inputs.json'
            atomic_write(target, json.dumps(value, ensure_ascii=False, indent=2) + '\n')
            print(f'已生成准备材料（不是人工卡片）：{target}')
        else:
            path = Path(args.review_file) if args.review_file else base / '_human_review.json'
            value = build_export(args.project, json.loads(path.read_text(encoding='utf-8'), object_pairs_hook=unique_keys))
            md = render_markdown(value)
            atomic_write(base / '_human_review_cards.json', json.dumps(value, ensure_ascii=False, indent=2) + '\n')
            atomic_write(base / '_human_review_cards.md', md)
            counts = value['counts']
            print(f"已导出 {counts['independent_questions']} 个独立问题 / {counts['cards']} 张卡片：{base / '_human_review_cards.md'}")
    except (ValueError, OSError) as exc:
        print(f'错误：{exc}；未生成新的有效导出，旧卡片不可视为当前结果。', file=sys.stderr)
        return 1
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
