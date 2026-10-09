"""Deterministic lexical triage and hash-bound explicit review records.

This module makes no semantic correctness or calibrated-confidence claim.
"""
import hashlib
import json
from pathlib import Path

POLICY_VERSION = 'focused-terms-v2'


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=False,
                                     separators=(',', ':')).encode()).hexdigest()


def input_manifest(project_dir):
    base = Path(project_dir) / 'source/temp'
    manifest = {}
    for folder in ('_chunks', '_translated_chunks'):
        for path in sorted((base / folder).glob('*.md')):
            if not path.name.startswith('_prompt_'):
                manifest[f'{folder}/{path.name}'] = hashlib.sha256(path.read_bytes()).hexdigest()
    return manifest


def enrich_report(report, project_dir):
    manifest = input_manifest(project_dir)
    report.update(policy_version=POLICY_VERSION, input_manifest=manifest,
                  input_digest=digest(manifest))
    decisions, baseline, seen = {}, 0, {}
    for row in report['rows']:
        identity = {k: row[k] for k in ('chunk', 'index', 'original', 'recommended', 'current', 'note', 'source_context', 'translated_context', 'anomalies')}
        base_id = digest(identity)
        seen[base_id] = seen.get(base_id, 0) + 1
        row['occurrence_id'] = 'o-' + digest([identity, seen[base_id]])[:20]
        uncertain = row.get('alignment_unknown', False)
        kind = ('structural' if row['anomalies'] else 'alignment_unknown' if uncertain
                else 'unknown' if row['adopted_recommendation'] == '无法判断'
                else 'string_difference' if row['adopted_recommendation'] == '否'
                else 'baseline_match')
        row['review_kind'] = kind
        if kind == 'baseline_match':
            baseline += 1
            continue
        # Only exact same bilingual sentence + metadata + choice may share a decision.
        # Structural and ambiguous alignments are never grouped across occurrences.
        group = {k: row[k] for k in ('original', 'recommended', 'current', 'note', 'source_context', 'translated_context', 'anomalies')}
        group['kind'] = kind
        if kind in ('structural', 'alignment_unknown', 'unknown'):
            group['occurrence_id'] = row['occurrence_id']
        decision_id = 'd-' + digest(group)[:20]
        decision = decisions.setdefault(decision_id, dict(id=decision_id, **group, occurrences=[]))
        decision['occurrences'].append(dict(id=row['occurrence_id'], chunk=row['chunk'], index=row['index']))
    semantic_path = Path(project_dir) / 'source/temp/_term_semantic_issues.json'
    semantic = None
    if semantic_path.exists():
        semantic = json.loads(semantic_path.read_text(encoding='utf-8'))
        if not isinstance(semantic, dict) or semantic.get('input_digest') != report['input_digest']:
            raise ValueError('语义审阅输入哈希不匹配；请对当前输入重新审阅或移走旧语义文件')
        if not isinstance(semantic.get('issues'), list):
            raise ValueError('语义审阅 issues 必须是数组')
        for item in semantic['issues']:
            fields = ('chunk', 'problem', 'source_context', 'translated_context')
            if not isinstance(item, dict) or any(not isinstance(item.get(k), str) or not item[k].strip() for k in fields):
                raise ValueError('每条语义问题必须包含非空 chunk/problem/source_context/translated_context')
            if '_chunks/' + item['chunk'] + '.md' not in manifest:
                raise ValueError('语义问题引用未知 chunk: ' + item['chunk'])
            group = {k: item[k] for k in fields}
            did = 's-' + digest(group)[:20]
            decisions[did] = dict(id=did, kind='semantic_issue', **group, occurrences=[])
    report['decisions'] = sorted(decisions.values(), key=lambda d: (d['kind'] != 'structural', d['kind'], d['id']))
    report['review_digest'] = digest(dict(policy=POLICY_VERSION, project=str(Path(project_dir).resolve()), inputs=manifest, decisions=report['decisions'], semantic=semantic))
    report['review_stats'] = dict(baseline_matches=baseline, unresolved_decisions=len(decisions),
                                  queued_occurrences=sum(len(d['occurrences']) for d in decisions.values()),
                                  semantic_issues=sum(d['kind']=='semantic_issue' for d in decisions.values()))
    accepted = set()
    path = approval_path(project_dir)
    if path.exists():
        try:
            approval = json.loads(path.read_text(encoding='utf-8'))
            if isinstance(approval, dict) and approval.get('review_digest') == report['review_digest']:
                accepted = set(approval.get('approved_decisions', []))
        except (ValueError, TypeError):
            pass  # Corrupt records grant no approval; the stripping gate rejects them.
    for decision in report['decisions']:
        decision['status'] = 'accepted' if decision['id'] in accepted else 'unresolved'
    report['review_stats'].update(candidate_decisions=len(decisions),
                                  accepted_decisions=sum(d['status']=='accepted' for d in report['decisions']),
                                  unresolved_decisions=sum(d['status']=='unresolved' for d in report['decisions']))
    return report


def write_queue(report, project_dir):
    path = Path(project_dir) / 'source/temp/_term_decision_queue.md'
    stats = report['review_stats']
    lines = ['# 术语决策队列', '',
             f"待决策 {stats['unresolved_decisions']} 项；覆盖 {stats['queued_occurrences']} 个标记出现位置；语义问题 {stats['semantic_issues']} 项。",
             f"已接受 {stats['accepted_decisions']} / {stats['candidate_decisions']} 项候选决策（完整 JSON 保留）。",
             f"词面符合推荐 {stats['baseline_matches']} 条，仍需 AI 或人工做全文语义审阅。这不是正确率。",
             '字符串不同不等于翻译错误；此处没有经过验证的置信度分数。所有待决策项完整列出，不截断。',
             f"输入哈希：{report['input_digest']}", f"审阅哈希：{report['review_digest']}", '']
    for d in report['decisions']:
        if d['status'] == 'accepted':
            continue
        lines += [f"## {d['id']} · {d['kind']}"]
        if d['kind'] == 'semantic_issue':
            lines += [d['problem'], '位置：' + d['chunk']]
        else:
            lines += [f"{d['original']} → 当前「{d['current']}」；推荐「{d['recommended']}」",
                      '位置：' + ', '.join(f"{o['chunk']}#{o['index']} ({o['id']})" for o in d['occurrences'])]
            if d['note']:
                lines.append('注释：' + d['note'])
            if d['anomalies']:
                lines.append('结构异常：' + '；'.join(d['anomalies']))
        lines += ['原句：' + d['source_context'], '译句：' + d['translated_context'], '']
    path.write_text('\n'.join(lines) + '\n', encoding='utf-8')
    (path.with_suffix('.json')).write_text(json.dumps({k: report[k] for k in ('policy_version', 'input_digest', 'review_digest', 'review_stats', 'decisions')}, ensure_ascii=False, indent=2)+'\n', encoding='utf-8')


def approval_path(project_dir):
    return Path(project_dir) / 'source/temp/_term_review_approval.json'


def validate_approval(report, approval):
    if report['stats']['structural_anomalies']:
        raise ValueError('结构异常未修复，禁止清标记')
    if not isinstance(approval, dict) or approval.get('review_digest') != report['review_digest']:
        raise ValueError('审阅批准缺失或已失效（输入、语义问题或分组规则已改变）')
    if approval.get('semantic_reviewed') is not True or not isinstance(approval.get('reviewer'), str) or not approval['reviewer'].strip():
        raise ValueError('缺少全文语义审阅声明及审阅者')
    required = {d['id'] for d in report['decisions']}
    approved = approval.get('approved_decisions')
    if not isinstance(approved, list) or any(not isinstance(x, str) for x in approved):
        raise ValueError('批准记录格式无效')
    if set(approved) != required:
        raise ValueError(f'批准不完整或含旧 ID；仍有 {len(required-set(approved))} 项待处理')
    reviews = approval.get('decision_reviews', {})
    if not isinstance(reviews, dict) or any(not isinstance(reviews.get(i), dict) or not reviews[i].get('reviewer') or not reviews[i].get('reason') for i in required):
        raise ValueError('决策缺少审阅者或理由')
    if not approval.get('semantic_reviewer'):
        raise ValueError('缺少全文语义审阅者')
    if approval.get('baseline_accepted') is not True:
        raise ValueError('缺少词面符合推荐部分的明确接受声明')
    release = approval.get('manual_release')
    if not isinstance(release, dict) or release.get('review_digest') != report['review_digest'] or not release.get('by'):
        raise ValueError('缺少用户明确确认后的手动放行记录（--release）')
