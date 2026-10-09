"""Build a per-occurrence term review report from tagged chunks.

Usage:
    python check_terms.py <project_dir> [--output <report.md>] [--json-output <report.json>]

Reads:
    source/temp/_chunks/              -> source markers: 【原文｜推荐译文｜注释】
    source/temp/_translated_chunks/   -> translated markers: 【当前译文｜推荐译文｜注释】

Writes:
    source/temp/_term_review_report.md
    source/temp/_term_review_report.json

Exit code:
    0 = report generated successfully
    1 = structural anomalies found or input missing
"""

from collections import Counter
import argparse
import json
import os
import re
import sys
from datetime import datetime

from term_markers import parse_markers, readable_context

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

MARKER_RE = re.compile(r"【([^｜】]+)｜([^｜】]+)(?:｜([^】]*))?】")

TARGET_START = "[[[KILO_TARGET_START]]]"
TARGET_END = "[[[KILO_TARGET_END]]]"


def _extract_kilo_target(text):
    lines = text.splitlines(True)
    start = None
    end = None
    for idx, line in enumerate(lines):
        stripped = line.strip()
        if stripped == TARGET_START:
            start = idx
        elif stripped == TARGET_END and start is not None:
            end = idx
            break
    if start is None or end is None or end <= start:
        return ""
    return "".join(lines[start + 1 : end])


def _normalise(text):
    return re.sub(r"\s+", "", (text or "")).strip()


def _split_recommended(text):
    parts = re.split(r"\s*[\/／]\s*", text or "")
    return [_normalise(part) for part in parts if _normalise(part)]


def _extract_markers(text):
    return parse_markers(text)[0]


def _marker_key(marker):
    if not marker:
        return ("", "")
    return (_normalise(marker.get("slot2", "")), _normalise(marker.get("slot3", "")))


def _choose_nearest(candidates, target_index):
    return min(candidates, key=lambda idx: (abs(idx - target_index), idx))


def _pair_markers(src_markers, trans_markers):
    """优先按 推荐译文+注释 对位；仅在无法精确匹配时退回顺序兜底。"""
    pairings = {}
    pairing_modes = {}
    unmatched_trans = set(range(len(trans_markers)))
    key_to_trans = {}

    for trans_idx, trans_marker in enumerate(trans_markers):
        key_to_trans.setdefault(_marker_key(trans_marker), []).append(trans_idx)

    for src_idx, src_marker in enumerate(src_markers):
        candidates = [
            trans_idx
            for trans_idx in key_to_trans.get(_marker_key(src_marker), [])
            if trans_idx in unmatched_trans
        ]
        if not candidates:
            continue
        # Match repeated metadata in occurrence order, not nearest absolute index.
        # Other terms can reorder and shift global indices; nearest may consume a
        # later occurrence then wrap back, presenting unrelated sentence contexts.
        best_idx = candidates[0]
        pairings[src_idx] = best_idx
        pairing_modes[src_idx] = "exact"
        unmatched_trans.remove(best_idx)

    remaining_src = [idx for idx in range(len(src_markers)) if idx not in pairings]
    remaining_trans = sorted(unmatched_trans)
    paired_count = min(len(remaining_src), len(remaining_trans))

    for offset in range(paired_count):
        src_idx = remaining_src[offset]
        trans_idx = remaining_trans[offset]
        pairings[src_idx] = trans_idx
        pairing_modes[src_idx] = "fallback"

    missing_src = remaining_src[paired_count:]
    extra_trans = remaining_trans[paired_count:]
    return pairings, pairing_modes, missing_src, extra_trans


def _context_snippet(text, pos, radius=40):
    return readable_context(text, pos)


def _adopted(current, recommended):
    current_norm = _normalise(current)
    if not current_norm:
        return "无法判断"
    options = _split_recommended(recommended)
    if not options:
        return "无法判断"
    return "是" if current_norm in options else "否"


def _build_row(
    label,
    src_marker=None,
    trans_marker=None,
    anomaly_messages=None,
    src_target="",
    trans_target="",
):
    anomaly_messages = anomaly_messages or []

    original = src_marker["slot1"] if src_marker else ""
    recommended = src_marker["slot2"] if src_marker else ""
    note = src_marker["slot3"] if src_marker else ""
    current = trans_marker["slot1"] if trans_marker else ""

    if not recommended and trans_marker:
        recommended = trans_marker["slot2"]
    if not note and trans_marker:
        note = trans_marker["slot3"]

    source_context = ""
    translated_context = ""
    if src_marker and src_target:
        source_context = _context_snippet(src_target, src_marker["pos"])
    if trans_marker and trans_target:
        translated_context = _context_snippet(trans_target, trans_marker["pos"])

    return {
        "chunk": label,
        "index": src_marker["index"] if src_marker else (trans_marker["index"] if trans_marker else 0),
        "original": original,
        "recommended": recommended,
        "current": current,
        "adopted_recommendation": _adopted(current, recommended),
        "context": translated_context or source_context,
        "source_context": source_context,
        "translated_context": translated_context,
        "note": note,
        "anomalies": anomaly_messages,
    }


def review_chunk(tagged_path, trans_path, label):
    with open(tagged_path, "r", encoding="utf-8") as f:
        tagged_text = f.read()
    with open(trans_path, "r", encoding="utf-8") as f:
        trans_text = f.read()

    tagged_target = _extract_kilo_target(tagged_text)
    trans_target = _extract_kilo_target(trans_text)

    rows = []
    structural_anomalies = 0

    for side, text in [('原文', tagged_text), ('译文', trans_text)]:
        lines = [line.strip() for line in text.splitlines()]
        if lines.count(TARGET_START) != 1 or lines.count(TARGET_END) != 1 or lines.index(TARGET_START) >= lines.index(TARGET_END):
            return [_build_row(label, anomaly_messages=[side + ' KILO_TARGET 包装缺失、重复或顺序错误'])], 1

    if not tagged_target:
        rows.append(
            {
                "chunk": label,
                "index": 0,
                "original": "",
                "recommended": "",
                "current": "",
                "adopted_recommendation": "无法判断",
                "context": "",
                "source_context": "",
                "translated_context": "",
                "note": "",
                "anomalies": ["原文 chunk 缺少 KILO_TARGET 区段"],
            }
        )
        return rows, 1

    if not trans_target:
        rows.append(
            {
                "chunk": label,
                "index": 0,
                "original": "",
                "recommended": "",
                "current": "",
                "adopted_recommendation": "无法判断",
                "context": "",
                "source_context": "",
                "translated_context": "",
                "note": "",
                "anomalies": ["译文 chunk 缺少 KILO_TARGET 区段"],
            }
        )
        return rows, 1

    src_markers = _extract_markers(tagged_target)
    trans_markers = _extract_markers(trans_target)

    for side, text in [('原文', tagged_target), ('译文', trans_target)]:
        for pos, error in parse_markers(text)[1]:
            row = _build_row(label, anomaly_messages=[side + ': ' + error])
            row['index'] = pos
            row['context'] = readable_context(text, pos)
            row['source_context' if side == '原文' else 'translated_context'] = row['context']
            rows.append(row)
            structural_anomalies += 1
    if not src_markers and not trans_markers:
        return rows, structural_anomalies

    pairings, pairing_modes, missing_src, extra_trans = _pair_markers(src_markers, trans_markers)

    for src_idx, src_marker in enumerate(src_markers):
        trans_idx = pairings.get(src_idx)
        trans_marker = trans_markers[trans_idx] if trans_idx is not None else None
        anomalies = []

        if trans_marker is None:
            anomalies.append("译文缺少术语标记")
        elif pairing_modes.get(src_idx) == "fallback":
            if _normalise(src_marker["slot2"]) != _normalise(trans_marker["slot2"]):
                anomalies.append("推荐译文槽位被改动")
            if _normalise(src_marker["slot3"]) != _normalise(trans_marker["slot3"]):
                anomalies.append("注释槽位被改动")
        if trans_marker:
            if not _normalise(trans_marker["slot1"]):
                anomalies.append("当前译文槽位为空")

        if anomalies:
            structural_anomalies += 1

        rows.append(
            _build_row(
                label,
                src_marker=src_marker,
                trans_marker=trans_marker,
                anomaly_messages=anomalies,
                src_target=tagged_target,
                trans_target=trans_target,
            )
        )

    for trans_idx in extra_trans:
        structural_anomalies += 1
        rows.append(
            _build_row(
                label,
                src_marker=None,
                trans_marker=trans_markers[trans_idx],
                anomaly_messages=["译文多出术语标记"],
                src_target=tagged_target,
                trans_target=trans_target,
            )
        )

    src_counts = Counter(_marker_key(m) for m in src_markers)
    trans_counts = Counter(_marker_key(m) for m in trans_markers)
    for row in rows:
        key = (_normalise(row['recommended']), _normalise(row['note']))
        row['alignment_assumption'] = 'same_metadata_occurrence_order'
        # Different legitimate first-slot choices do not prove misalignment.
        # Unequal multiplicity does: without persistent IDs we cannot know which
        # duplicate was added/removed, even for the remaining paired occurrences.
        if not row['anomalies'] and src_counts[key] != trans_counts[key]:
            row['alignment_unknown'] = True
    return rows, structural_anomalies


def default_output_path(project_dir):
    return os.path.join(project_dir, "source", "temp", "_term_review_report.md")


def default_json_output_path(project_dir):
    return os.path.join(project_dir, "source", "temp", "_term_review_report.json")


def _escape_cell(text):
    return (text or "").replace("|", "\\|").replace("\n", " ")


def write_md_report(report, output_path):
    lines = [
        "# 术语审阅报告",
        "",
        f"**项目**：`{report['project']}`",
        f"**检查时间**：{report['checked_at']}",
        (
            f"**统计**：共 {report['stats']['total_rows']} 条术语，"
            f"{report['stats']['adopted_yes']} 条采用推荐，"
            f"{report['stats']['adopted_no']} 条未采用推荐，"
            f"{report['stats']['adopted_unknown']} 条无法判断，"
            f"{report['stats']['structural_anomalies']} 条结构异常"
        ),
        "",
    ]

    if not report["rows"]:
        lines.append("未发现任何术语标记。")
    else:
        headers = [
            "chunk",
            "原文",
            "推荐译文",
            "当前译文",
            "是否采用推荐",
            "原文上下文",
            "译文上下文",
            "注释",
            "异常",
        ]
        lines.append("| " + " | ".join(headers) + " |")
        lines.append("| " + " | ".join(["---"] * len(headers)) + " |")
        for row in report["rows"]:
            lines.append(
                "| "
                + " | ".join(
                    [
                        _escape_cell(row["chunk"]),
                        _escape_cell(row["original"]),
                        _escape_cell(row["recommended"]),
                        _escape_cell(row["current"]),
                        _escape_cell(row["adopted_recommendation"]),
                        _escape_cell(row.get("source_context", "")),
                        _escape_cell(row.get("translated_context", "")),
                        _escape_cell(row["note"]),
                        _escape_cell("；".join(row["anomalies"])),
                    ]
                )
                + " |"
            )

    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")


def write_json_report(report, output_path):
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(report, f, ensure_ascii=False, indent=2)
        f.write("\n")


def _print_summary(report, md_path, json_path):
    stats = report["stats"]
    print(
        f"\n共审阅 {stats['total_rows']} 条术语："
        f"{stats['adopted_yes']} 条采用推荐，"
        f"{stats['adopted_no']} 条未采用推荐，"
        f"{stats['adopted_unknown']} 条无法判断，"
        f"{stats['structural_anomalies']} 条结构异常"
    )
    print(f"Markdown 报告已写入: {md_path}")
    print(f"JSON 报告已写入: {json_path}")


def build_report(project_dir):
    chunks_dir = os.path.join(project_dir, "source", "temp", "_chunks")
    trans_dir = os.path.join(project_dir, "source", "temp", "_translated_chunks")

    if not os.path.isdir(chunks_dir):
        print(f"错误：_chunks/ 目录不存在: {chunks_dir}")
        sys.exit(1)
    if not os.path.isdir(trans_dir):
        print(f"错误：_translated_chunks/ 目录不存在: {trans_dir}")
        sys.exit(1)

    chunk_files = sorted(
        f for f in os.listdir(chunks_dir) if f.endswith(".md") and not f.startswith("_prompt_")
    )
    if not chunk_files:
        print("错误：_chunks/ 中没有 chunk 文件。")
        sys.exit(1)

    all_rows = []
    structural_anomalies = 0
    for extra in sorted(set(f for f in os.listdir(trans_dir) if f.endswith('.md') and not f.startswith('_prompt_')) - set(chunk_files)):
        all_rows.append(_build_row(os.path.splitext(extra)[0], anomaly_messages=['译文多出 chunk 文件']))
        structural_anomalies += 1

    for chunk_file in chunk_files:
        tagged_path = os.path.join(chunks_dir, chunk_file)
        trans_path = os.path.join(trans_dir, chunk_file)
        label = os.path.splitext(chunk_file)[0]

        if not os.path.exists(trans_path):
            all_rows.append(
                {
                    "chunk": label,
                    "index": 0,
                    "original": "",
                    "recommended": "",
                    "current": "",
                    "adopted_recommendation": "无法判断",
                    "context": "",
                    "source_context": "",
                    "translated_context": "",
                    "note": "",
                    "anomalies": ["译文 chunk 文件不存在"],
                }
            )
            structural_anomalies += 1
            continue

        rows, chunk_anomalies = review_chunk(tagged_path, trans_path, label)
        all_rows.extend(rows)
        structural_anomalies += chunk_anomalies

    stats = {
        "total_rows": len(all_rows),
        "adopted_yes": sum(1 for row in all_rows if row["adopted_recommendation"] == "是"),
        "adopted_no": sum(1 for row in all_rows if row["adopted_recommendation"] == "否"),
        "adopted_unknown": sum(1 for row in all_rows if row["adopted_recommendation"] == "无法判断"),
        "structural_anomalies": structural_anomalies,
    }

    report = {
        "project": os.path.abspath(project_dir),
        "checked_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "stats": stats,
        "rows": all_rows,
    }

    from term_review import enrich_report
    return enrich_report(report, project_dir)


def main(project_dir, output_path="", json_output_path=""):
    report = build_report(project_dir)
    output_path = output_path or default_output_path(project_dir)
    json_output_path = json_output_path or default_json_output_path(project_dir)
    write_md_report(report, output_path)
    write_json_report(report, json_output_path)
    from term_review import write_queue
    write_queue(report, project_dir)
    _print_summary(report, output_path, json_output_path)
    print(f"决策队列: {report['review_stats']['unresolved_decisions']} 项；词面符合推荐: {report['review_stats']['baseline_matches']} 条（不是语义正确认证）")
    if report['stats']['structural_anomalies']:
        sys.exit(1)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('project_dir')
    parser.add_argument('--output', default='')
    parser.add_argument('--json-output', default='')
    args = parser.parse_args()
    try:
        main(args.project_dir, args.output, args.json_output)
    except (ValueError, OSError) as exc:
        parser.exit(1, f"错误：{exc}\n")
