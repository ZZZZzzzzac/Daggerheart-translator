"""Check whether tagged terms were correctly adopted in translated output.

Compares _chunks/ (term-tagged originals) against _translated_chunks/
(translations) chunk by chunk. For each 【译文 (原文) ...】 marker in the
tagged chunk, verifies that the English term is gone and the recommended
Chinese translation appears in the translated chunk.

Usage:
    python check_terms.py <project_dir> [--output <report.md>]

Prints a summary table to stdout and writes a full Markdown report.
Exit code 0 = no issues found.
"""

import os
import re
import sys
from datetime import datetime

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

TERM_MARKER = re.compile(r"【([^(】]+?)\s*\(([^)]+)\)[^】]*】")

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


def _extract_terms(text):
    pairs = []
    seen = set()
    for m in TERM_MARKER.finditer(text):
        cn = m.group(1).strip()
        en = m.group(2).strip()
        key = (en.lower(), cn)
        if key not in seen:
            seen.add(key)
            pairs.append((en, cn))
    return pairs


def _has_english(text, term):
    try:
        return bool(re.search(r"\b" + re.escape(term) + r"\b", text, re.IGNORECASE))
    except re.error:
        return term.lower() in text.lower()


def _has_chinese(text, cn):
    normalised_text = re.sub(r"\s+", "", text)
    parts = [p.strip() for p in cn.split("/") if p.strip()]
    for p in parts:
        normalised_cn = re.sub(r"\s+", "", p)
        if normalised_cn in normalised_text:
            return True
    return False


def _find_section_headers(text):
    """Return list of (position, header_text) for ✦ lines."""
    return [(m.start(), m.group().strip()) for m in re.finditer(r"^✦[^\n]*", text, re.MULTILINE)]


def _find_snippet(en, tagged_target, trans_target):
    """Find the translated text around where the term should appear.

    Uses ✦ section headers as anchors to locate the corresponding
    section in the translated chunk, then returns a short snippet.
    """
    # Find the term position in tagged text
    term_pat = re.compile(r"【[^】]*\(" + re.escape(en) + r"\)[^】]*】")
    term_match = term_pat.search(tagged_target)
    if not term_match:
        return ""

    term_pos = term_match.start()

    # Locate which ✦ section the term falls in
    tagged_sections = _find_section_headers(tagged_target)
    trans_sections = _find_section_headers(trans_target)

    section_idx = -1
    for i, (pos, _header) in enumerate(tagged_sections):
        if pos < term_pos:
            section_idx = i

    if section_idx < 0 or section_idx >= len(trans_sections):
        # No matching section — return first content line of translated
        lines = [
            l.strip()
            for l in trans_target.split("\n")
            if l.strip() and not l.strip().startswith("✦")
        ]
        return lines[0][:60] if lines else ""

    # Extract the corresponding section from translated
    trans_start = trans_sections[section_idx][0]
    trans_end = (
        trans_sections[section_idx + 1][0]
        if section_idx + 1 < len(trans_sections)
        else len(trans_target)
    )
    section_text = trans_target[trans_start:trans_end]

    # Clean: remove header, blank lines, join first few content lines
    content_lines = [
        l.strip()
        for l in section_text.split("\n")
        if l.strip() and not l.strip().startswith("✦")
    ]
    snippet = " ".join(content_lines[:3])
    if len(snippet) > 60:
        snippet = snippet[:57] + "..."
    return snippet


def check_chunk(tagged_path, trans_path, label):
    with open(tagged_path, "r", encoding="utf-8") as f:
        tagged_text = f.read()
    with open(trans_path, "r", encoding="utf-8") as f:
        trans_text = f.read()

    tagged_target = _extract_kilo_target(tagged_text)
    trans_target = _extract_kilo_target(trans_text)

    if not tagged_target:
        return [], {"skip": 1, "ok": 0, "eng_residual": 0, "not_found": 0}
    if not trans_target:
        issues = []
        for en, cn in _extract_terms(tagged_target):
            issues.append(
                {
                    "en": en,
                    "cn": cn,
                    "chunk": label,
                    "problem": "译文 TARGET 区段为空",
                    "snippet": "",
                }
            )
        return issues, {"skip": 0, "ok": 0, "eng_residual": 0, "not_found": len(issues)}

    terms = _extract_terms(tagged_target)
    if not terms:
        return [], {"skip": 0, "ok": 0, "eng_residual": 0, "not_found": 0}

    issues = []
    stats = {"skip": 0, "ok": 0, "eng_residual": 0, "not_found": 0}

    for en, cn in terms:
        eng_left = _has_english(trans_target, en)
        cn_used = _has_chinese(trans_target, cn)

        if eng_left and cn_used:
            snippet = _find_snippet(en, tagged_target, trans_target)
            issues.append(
                {
                    "en": en,
                    "cn": cn,
                    "chunk": label,
                    "problem": "英文残留且存在中文译法",
                    "snippet": snippet,
                }
            )
            stats["eng_residual"] += 1
        elif eng_left:
            snippet = _find_snippet(en, tagged_target, trans_target)
            issues.append(
                {
                    "en": en,
                    "cn": cn,
                    "chunk": label,
                    "problem": "英文残留",
                    "snippet": snippet,
                }
            )
            stats["eng_residual"] += 1
        elif not cn_used:
            snippet = _find_snippet(en, tagged_target, trans_target)
            issues.append(
                {
                    "en": en,
                    "cn": cn,
                    "chunk": label,
                    "problem": "未使用推荐译法",
                    "snippet": snippet,
                }
            )
            stats["not_found"] += 1
        else:
            stats["ok"] += 1

    return issues, stats


def _print_table(issues, stats):
    if not issues:
        print("\n所有术语均已正确使用，未发现问题。")
        return

    en_w = min(max(len(r["en"]) for r in issues), 30)
    cn_w = min(max(len(r["cn"]) for r in issues), 25)
    prob_w = max(len(r["problem"]) for r in issues)
    snippet_w = min(max(len(r.get("snippet", "")) for r in issues), 40)

    header = (
        f"| {'原文':<{en_w}} | {'推荐译法':<{cn_w}} | {'当前译法':<{snippet_w}} | {'问题':<{prob_w}} |"
    )
    sep = (
        f"| {'-' * en_w} | {'-' * cn_w} | {'-' * snippet_w} | {'-' * prob_w} |"
    )
    print()
    print(header)
    print(sep)

    for r in issues:
        snippet = r.get("snippet", "")
        print(
            f"| {r['en']:<{en_w}} "
            f"| {r['cn']:<{cn_w}} "
            f"| {snippet:<{snippet_w}} "
            f"| {r['problem']:<{prob_w}} |"
        )

    total = stats["ok"] + stats["eng_residual"] + stats["not_found"]
    print(f"\n共检查 {total} 条术语：{stats['ok']} 正确，"
          f"{stats['eng_residual']} 英文残留，{stats['not_found']} 未使用推荐译法")


def _deduplicate_issues(issues):
    """Merge identical (en, cn, problem) issues. Keep the snippet from the
    first occurrence."""
    by_key = {}
    for r in issues:
        key = (r["en"], r["cn"], r["problem"])
        if key not in by_key:
            by_key[key] = dict(r)
        # Keep first snippet, discard "chunk" key
    result = []
    for entry in by_key.values():
        entry.pop("chunk", None)
        result.append(entry)
    return result


def default_output_path(project_dir):
    return os.path.join(project_dir, "source", "temp", "_term_check_report.md")


def write_md_report(issues, stats, project_dir, output_path):
    deviations = _deduplicate_issues(issues)
    project_abs = os.path.abspath(project_dir)
    checked_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    total = stats["ok"] + stats["eng_residual"] + stats["not_found"]

    lines = [
        "# 术语检查报告",
        "",
        f"**项目**：`{project_abs}`",
        f"**检查时间**：{checked_at}",
        f"**统计**：共 {total} 条术语 — {stats['ok']} 正确，"
        f"{stats['eng_residual']} 英文残留，{stats['not_found']} 未使用推荐译法",
        "",
    ]

    if not deviations:
        lines.append("所有术语均已正确使用，未发现问题。")
    else:
        en_w = min(max(len(r["en"]) for r in deviations), 30)
        cn_w = min(max(len(r["cn"]) for r in deviations), 25)
        snippet_w = min(max(len(r.get("snippet", "")) for r in deviations), 45)
        prob_w = max(len(r["problem"]) for r in deviations) if deviations else 10

        h_en = "原文".ljust(en_w)
        h_cn = "推荐译法".ljust(cn_w)
        h_snippet = "当前译法".ljust(snippet_w)
        h_prob = "问题".ljust(prob_w)

        lines.append(f"| {h_en} | {h_cn} | {h_snippet} | {h_prob} |")
        lines.append(f"| {'-' * en_w} | {'-' * cn_w} | {'-' * snippet_w} | {'-' * prob_w} |")

        for r in deviations:
            snippet = r.get("snippet", "")
            lines.append(
                f"| {r['en']:<{en_w}} "
                f"| {r['cn']:<{cn_w}} "
                f"| {snippet:<{snippet_w}} "
                f"| {r['problem']:<{prob_w}} |"
            )

    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")

    return output_path


def main(project_dir, output_path=""):
    chunks_dir = os.path.join(project_dir, "source", "temp", "_chunks")
    trans_dir = os.path.join(project_dir, "source", "temp", "_translated_chunks")

    if not os.path.isdir(chunks_dir):
        print(f"错误：_chunks/ 目录不存在: {chunks_dir}")
        sys.exit(1)
    if not os.path.isdir(trans_dir):
        print(f"错误：_translated_chunks/ 目录不存在: {trans_dir}")
        sys.exit(1)

    chunk_files = sorted(
        f
        for f in os.listdir(chunks_dir)
        if f.endswith(".md") and not f.startswith("_prompt_")
    )
    if not chunk_files:
        print("错误：_chunks/ 中没有 chunk 文件。")
        sys.exit(1)

    all_issues = []
    total_stats = {"skip": 0, "ok": 0, "eng_residual": 0, "not_found": 0}
    pairs_checked = 0

    for chunk_file in chunk_files:
        tagged_path = os.path.join(chunks_dir, chunk_file)
        trans_path = os.path.join(trans_dir, chunk_file)
        label = os.path.splitext(chunk_file)[0]

        if not os.path.exists(trans_path):
            print(f"警告：译文 chunk 不存在，跳过: {chunk_file}")
            total_stats["skip"] += 1
            continue

        issues, cstats = check_chunk(tagged_path, trans_path, label)
        all_issues.extend(issues)
        for k, v in cstats.items():
            total_stats[k] += v
        pairs_checked += 1

    if pairs_checked == 0:
        print("错误：没有可比较的 chunk 对。")
        sys.exit(1)

    _print_table(all_issues, total_stats)

    output_path = output_path or default_output_path(project_dir)
    report_path = write_md_report(all_issues, total_stats, project_dir, output_path)
    print(f"\n完整报告已写入: {report_path}")

    if all_issues:
        sys.exit(1)


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python check_terms.py <project_dir> [--output <report.md>]")
        sys.exit(1)

    project_dir = sys.argv[1]
    output_path = ""
    if "--output" in sys.argv:
        idx = sys.argv.index("--output")
        output_path = sys.argv[idx + 1]

    main(project_dir, output_path)
