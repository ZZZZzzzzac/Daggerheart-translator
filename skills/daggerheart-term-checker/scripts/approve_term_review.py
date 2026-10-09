"""Record explicit decisions; does not itself perform semantic review."""
import argparse
import json
import os
import tempfile
from datetime import datetime, timezone
from check_terms import build_report
from term_review import approval_path


def approve(project_dir, reviewer, decision_ids, baseline=False, semantic=False, all_decisions=False, reason="", expected_digest="", release=False):
    return _record_approval(project_dir, build_report(project_dir), reviewer, decision_ids,
                            baseline, semantic, all_decisions, reason, expected_digest, release)


def approve_batch(project_dir, reviewer, payload):
    """Validate a complete per-ID batch once; write all decisions or none.

    A batch cannot declare semantic completion, baseline acceptance, or release.
    Those remain separate explicit operations. Unknown fields are rejected rather
    than silently interpreting possible authorization flags.
    """
    if not isinstance(payload, dict) or set(payload) != {'review_digest', 'input_digest', 'decisions'}:
        raise ValueError('批量文件必须仅含 review_digest、input_digest、decisions')
    if not isinstance(payload['decisions'], list) or not payload['decisions']:
        raise ValueError('批量 decisions 必须是非空数组')
    reasons = {}
    for item in payload['decisions']:
        if not isinstance(item, dict) or set(item) != {'id', 'reason'}:
            raise ValueError('每项必须仅含 id、reason')
        if any(not isinstance(item[k], str) or not item[k].strip() for k in ('id', 'reason')):
            raise ValueError('每项 id、reason 必须是非空字符串')
        if item['id'] in reasons:
            raise ValueError('批量决策 ID 重复或冲突: ' + item['id'])
        reasons[item['id']] = item['reason']
    report = build_report(project_dir)
    if payload['input_digest'] != report['input_digest']:
        raise ValueError('批量输入哈希不匹配')
    return _record_approval(project_dir, report, reviewer, list(reasons),
                            expected_digest=payload['review_digest'], reasons=reasons,
                            reject_conflicts=True)


def _record_approval(project_dir, report, reviewer, decision_ids, baseline=False,
                     semantic=False, all_decisions=False, reason='', expected_digest='',
                     release=False, reasons=None, reject_conflicts=False):
    if not isinstance(reviewer, str) or not reviewer.strip():
        raise ValueError('审阅者不能为空')
    if reasons is None:
        if (decision_ids or all_decisions) and not reason.strip():
            raise ValueError('接受决策必须记录 --reason 理由')
        reasons = {decision_id: reason for decision_id in decision_ids}
    if expected_digest != report['review_digest']:
        raise ValueError('审阅哈希不匹配；先生成并阅读当前报告')
    if report['stats']['structural_anomalies']:
        raise ValueError('先修复结构异常并重新生成报告，不能批准绕过')
    known = {d['id'] for d in report['decisions']}
    requested = set(decision_ids)
    if requested - known:
        raise ValueError('未知或过期决策 ID: ' + ', '.join(sorted(requested-known)))
    path = approval_path(project_dir)
    record = {}
    if path.exists():
        record = json.loads(path.read_text(encoding='utf-8'))
        if not isinstance(record, dict):
            raise ValueError('批准记录必须是 JSON object')
    if record.get('review_digest') != report['review_digest']:
        record = {}
    approved = set(record.get('approved_decisions', [])) | (known if all_decisions else requested)
    reviews = record.get('decision_reviews', {})
    for decision_id in (known if all_decisions else requested):
        per_id_reason = reason if all_decisions else reasons[decision_id]
        previous = reviews.get(decision_id)
        if reject_conflicts and previous:
            if not isinstance(previous, dict) or previous.get('reason') != per_id_reason:
                raise ValueError('批量决策与已有理由冲突: ' + decision_id)
            continue  # Idempotent import preserves the original review provenance.
        reviews[decision_id] = dict(reviewer=reviewer, reason=per_id_reason)
    if semantic:
        record['semantic_reviewer'] = reviewer
    if baseline:
        record['baseline_reviewer'] = reviewer
    record.update(decision_reviews=reviews, review_digest=report['review_digest'], input_digest=report['input_digest'],
                  approved_decisions=sorted(approved), reviewer=reviewer,
                  baseline_accepted=baseline or record.get('baseline_accepted', False),
                  semantic_reviewed=semantic or record.get('semantic_reviewed', False),
                  updated_at=datetime.now(timezone.utc).isoformat())
    if release:
        from term_review import validate_approval
        record['manual_release'] = dict(by=reviewer, review_digest=report['review_digest'])
        validate_approval(report, record)
    temp_path = None
    try:
        with tempfile.NamedTemporaryFile(mode='w', encoding='utf-8', dir=path.parent,
                                         prefix='.term-approval-', delete=False) as f:
            temp_path = f.name
            json.dump(record, f, ensure_ascii=False, indent=2)
            f.write('\n')
            f.flush()
            os.fsync(f.fileno())
        os.replace(temp_path, path)
    finally:
        if temp_path and os.path.exists(temp_path):
            os.unlink(temp_path)
    print(f'已记录批准 {len(approved)}/{len(known)} 项；待决策 {len(known-approved)} 项。声明不代表脚本验证了语义。')
    return record


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('project_dir')
    parser.add_argument('--review-digest', default='', help='从实际审阅的队列复制审阅哈希')
    parser.add_argument('--batch', help='JSON 批量逐项接受；含输入/审阅哈希及每项 id、reason，不隐含语义声明或人工放行')
    parser.add_argument('--reviewer', required=True, help='实际语义审阅者，例如 AI:model 或 human:name')
    parser.add_argument('--approve', action='append', default=[], metavar='DECISION_ID')
    parser.add_argument('--release', action='store_true', help='仅在用户明确确认继续后记录手动放行；不用于 AI 自行裁决')
    parser.add_argument('--reason', default='', help='接受当前决策的上下文依据；保留为审计记录')
    parser.add_argument('--approve-all', action='store_true', help='明确接受当前完整队列（必须实际审阅）')
    parser.add_argument('--accept-baseline', action='store_true')
    parser.add_argument('--semantic-reviewed', action='store_true', help='声明已完成全文语义审阅，包括推荐词面一致和无标记部分')
    args = parser.parse_args()
    try:
        if not args.reviewer.strip():
            raise ValueError('审阅者不能为空')
        if args.batch:
            if args.review_digest or args.approve or args.accept_baseline or args.semantic_reviewed or args.approve_all or args.reason or args.release:
                raise ValueError('--batch 不能与单项接受、声明或放行选项混用')
            with open(args.batch, encoding='utf-8') as f:
                approve_batch(args.project_dir, args.reviewer, json.load(f))
        else:
            if not args.review_digest:
                raise ValueError('非批量模式必须提供 --review-digest')
            approve(args.project_dir, args.reviewer, args.approve, args.accept_baseline,
                    args.semantic_reviewed, args.approve_all, args.reason, args.review_digest, args.release)
    except (ValueError, OSError) as exc:
        parser.exit(1, f'错误：{exc}\n')
