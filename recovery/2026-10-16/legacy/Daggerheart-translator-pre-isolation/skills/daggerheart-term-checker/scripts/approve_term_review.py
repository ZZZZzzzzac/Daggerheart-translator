"""Record explicit decisions; does not itself perform semantic review."""
import argparse
import json
from datetime import datetime, timezone
from check_terms import build_report
from term_review import approval_path


def approve(project_dir, reviewer, decision_ids, baseline=False, semantic=False, all_decisions=False):
    report = build_report(project_dir)
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
    if record.get('review_digest') != report['review_digest']:
        record = {}
    approved = set(record.get('approved_decisions', [])) | (known if all_decisions else requested)
    record.update(review_digest=report['review_digest'], input_digest=report['input_digest'],
                  approved_decisions=sorted(approved), reviewer=reviewer,
                  baseline_accepted=baseline or record.get('baseline_accepted', False),
                  semantic_reviewed=semantic or record.get('semantic_reviewed', False),
                  updated_at=datetime.now(timezone.utc).isoformat())
    path.write_text(json.dumps(record, ensure_ascii=False, indent=2)+'\n', encoding='utf-8')
    print(f'已记录批准 {len(approved)}/{len(known)} 项；待决策 {len(known-approved)} 项。声明不代表脚本验证了语义。')
    return record


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('project_dir')
    parser.add_argument('--reviewer', required=True, help='实际语义审阅者，例如 AI:model 或 human:name')
    parser.add_argument('--approve', action='append', default=[], metavar='DECISION_ID')
    parser.add_argument('--approve-all', action='store_true', help='明确接受当前完整队列（必须实际审阅）')
    parser.add_argument('--accept-baseline', action='store_true')
    parser.add_argument('--semantic-reviewed', action='store_true', help='声明已完成全文语义审阅，包括推荐词面一致和无标记部分')
    args = parser.parse_args()
    try:
        if not args.reviewer.strip():
            raise ValueError('审阅者不能为空')
        approve(args.project_dir, args.reviewer, args.approve, args.accept_baseline,
                args.semantic_reviewed, args.approve_all)
    except (ValueError, OSError) as exc:
        parser.exit(1, f'错误：{exc}\n')
