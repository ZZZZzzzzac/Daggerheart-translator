"""Validate translated markdown for recurring real-world errors.

Usage:
    python validate_translation.py <translated.md> [--allow-term-markers]

原则：
- 只检查已经在实际翻译中出现过、且能稳定判断的问题
- KILO 包装文件优先检查 KILO 结构完整性 + KILO_TARGET 正文
- 图片/表格/标题数量等对照检查暂不预加；遇到真实问题再加
"""

import re
import sys
import os

if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')

# Only exclude non-text patterns — everything else goes to AI for context judgment
KEEP_ENGLISH = re.compile(
    r'!\[.*\]\(.*\)'           # image refs: ![](_page_0_Picture_0.jpeg)
    r'|https?://\S+'            # URLs
    r'|\b\w+\.(?:com|org|net|io|co|dev|cn)\b'  # domain names: Daggerheart.com, stock.adobe.com
)

# 只放已在真实项目中出现过的高价值检查。
CHECKS = [
    # (pattern, description, severity: error|warn)
    (r'生命值', '❌ 生命值 → 生命点', 'error'),
    (r'希望值', '❌ 希望值 → 希望点', 'error'),
    (r'压力值', '❌ 压力值 → 压力点', 'error'),
    (r'恐惧值', '❌ 恐惧值 → 恐惧点', 'error'),
    (r'回响值', '❌ 回响值 → 回响点', 'error'),
    (r'恩宠值', '❌ 恩宠值 → 恩宠点', 'error'),
    (r'专注值', '❌ 专注值 → 专注点', 'error'),
    (r'绝望点', '❌ 绝望点 → 恐惧点', 'error'),
    (r'恐怖点|恐怖值', '❌ 恐怖点/值 → 恐惧点', 'error'),
    (r'清除生命点', '❌ 清除生命点 → 恢复生命点', 'error'),
    (r'易伤', '❌ 易伤 → 脆弱', 'error'),
    (r'临近(?:范围|距离)', '❌ 临近范围/临近距离 → 邻近范围/邻近距离', 'error'),
    (r'检定|豁免', '❌ 检定/豁免 → 掷骰', 'error'),
    (r'承受劣势', '❌ 承受劣势 → 获得劣势', 'error'),
    (r'（使用你的熟练值）', '❌ 熟练值括号置后', 'error'),
    (r'\*\*使用你的熟练值\*\*', '❌ 熟练值孤儿加粗 → 合并进伤害描述，如"使用你的熟练值造成XdX..."', 'error'),
    (r'[，,]\s*使用你的熟练值[，,。]', '⚠ 熟练值尾置 → 提到造成/受到前，如"使用你的熟练值造成..."', 'error'),
    (r'【.*】', '❌ 残留术语标记【】', 'error'),
    (r'\*\*\d+\*\* \*\*', '❌ 拆分加粗', 'error'),
]

TERM_MARKER_PATTERN = r'【.*】'

KILO_MARKER_ORDER = [
    '[[[KILO_META_START]]]',
    '[[[KILO_META_END]]]',
    '[[[KILO_CONTEXT_PREV_START]]]',
    '[[[KILO_CONTEXT_PREV_END]]]',
    '[[[KILO_TARGET_START]]]',
    '[[[KILO_TARGET_END]]]',
    '[[[KILO_CONTEXT_NEXT_START]]]',
    '[[[KILO_CONTEXT_NEXT_END]]]',
]
KILO_MARKERS = set(KILO_MARKER_ORDER)
KILO_META_KEYS = (
    'source_file:',
    'chunk_label:',
    'target_line_start:',
    'target_line_end:',
)

CONTEXT = 2


def is_kilo_control_line(stripped):
    return stripped in KILO_MARKERS or stripped.startswith(KILO_META_KEYS)


def expects_kilo_wrapper(filepath):
    parts = set(os.path.normpath(filepath).split(os.sep))
    return '_chunks' in parts or '_translated_chunks' in parts


def mask_non_target_lines(lines):
    """For KILO-wrapped files, only validate the KILO_TARGET body content."""
    target_start = None
    target_end = None

    for idx, line in enumerate(lines):
        stripped = line.strip()
        if stripped == '[[[KILO_TARGET_START]]]':
            target_start = idx
            continue
        if stripped == '[[[KILO_TARGET_END]]]' and target_start is not None:
            target_end = idx
            break

    if target_start is None or target_end is None or target_end <= target_start:
        return lines

    masked = []
    for idx, line in enumerate(lines):
        if target_start < idx < target_end:
            masked.append(line)
        else:
            masked.append('')
    return masked


def find_english_spans(text):
    """Find English words (3+ letters), excluding non-text patterns."""
    cleaned = KEEP_ENGLISH.sub(' ', text)
    matches = list(re.finditer(r'\b[A-Za-z]{3,}\b', cleaned))
    return [(m.group(), m.start()) for m in matches]


def check_urls(lines):
    """Find URLs and verify they look intact."""
    url_errors = {}
    for i, line in enumerate(lines, 1):
        urls = re.findall(r'https?://[^\s\)\]]+', line)
        for url in urls:
            if url.endswith('.') or url.endswith(',') or url.endswith(';'):
                url_errors.setdefault(i, []).append(
                    (r'', '⚠ URL 可能被截断', line.strip()[:120])
                )
            elif '...' in url or '…' in url:
                url_errors.setdefault(i, []).append(
                    (r'', '⚠ URL 包含省略号', line.strip()[:120])
                )
    return url_errors


def check_english(lines):
    """Flag lines with English words — AI decides keep or translate based on context."""
    eng_errors = {}
    for i, line in enumerate(lines, 1):
        stripped = line.strip()
        if not stripped or stripped.startswith('```') or stripped.startswith('![') or is_kilo_control_line(stripped):
            continue
        eng_words = find_english_spans(line)
        if eng_words:
            words = list(dict.fromkeys(w for w, _ in eng_words))  # unique, preserve order
            eng_errors.setdefault(i, []).append(
                ('', f'⚠ 待AI判断: {" ".join(words)}', stripped[:120])
            )
    return eng_errors


def check_kilo_markers(lines, filepath):
    """Validate KILO wrapper structure used by translated chunk files."""
    errors = {}
    warns = {}
    marker_lines = []
    meta_lines = []

    for i, line in enumerate(lines, 1):
        stripped = line.strip()
        if stripped in KILO_MARKERS:
            marker_lines.append((i, stripped))
            continue
        if stripped.startswith(KILO_META_KEYS):
            meta_lines.append((i, stripped))
            continue
        if ('[[[' in stripped or ']]]' in stripped) and 'KILO' in stripped:
            errors.setdefault(i, []).append(
                ('', '❌ 非法 KILO 标记行', stripped[:120])
            )

    expect_wrapper = expects_kilo_wrapper(filepath)
    if expect_wrapper and not marker_lines:
        errors.setdefault(1, []).append(
            ('', '❌ chunk 文件缺少 KILO 包装标记', os.path.basename(filepath))
        )
        return errors, warns

    if not marker_lines and not meta_lines:
        return errors, warns

    if not expect_wrapper and marker_lines:
        warns.setdefault(marker_lines[0][0], []).append(
            ('', '⚠ 检测到 KILO 包装标记；若这是最终合并稿，说明还未去掉上下文包装', marker_lines[0][1])
        )

    counts = {marker: [] for marker in KILO_MARKER_ORDER}
    for line_no, marker in marker_lines:
        counts[marker].append(line_no)

    for marker in KILO_MARKER_ORDER:
        positions = counts[marker]
        if len(positions) != 1:
            line_no = positions[0] if positions else 1
            errors.setdefault(line_no, []).append(
                ('', f'❌ KILO 标记 {marker} 应出现 1 次，实际 {len(positions)} 次', marker)
            )

    observed_order = [marker for _, marker in sorted(marker_lines)]
    if all(len(counts[marker]) == 1 for marker in KILO_MARKER_ORDER):
        if observed_order != KILO_MARKER_ORDER:
            line_no = marker_lines[0][0] if marker_lines else 1
            errors.setdefault(line_no, []).append(
                ('', '❌ KILO 标记顺序错误', ' -> '.join(observed_order[:8]))
            )

        meta_start = counts['[[[KILO_META_START]]]'][0]
        meta_end = counts['[[[KILO_META_END]]]'][0]
        target_start = counts['[[[KILO_TARGET_START]]]'][0]
        target_end = counts['[[[KILO_TARGET_END]]]'][0]

        for line_no, stripped in meta_lines:
            if not (meta_start < line_no < meta_end):
                errors.setdefault(line_no, []).append(
                    ('', '❌ KILO 元数据必须位于 META_START / META_END 之间', stripped[:120])
                )

        meta_body = [line.strip() for line in lines[meta_start:meta_end - 1] if line.strip()]
        for key in KILO_META_KEYS:
            if not any(line.startswith(key) for line in meta_body):
                errors.setdefault(meta_start, []).append(
                    ('', f'❌ 缺少 KILO 元数据字段 {key}', key)
                )

        if target_end == target_start + 1:
            errors.setdefault(target_start, []).append(
                ('', '❌ KILO_TARGET 区段为空', '[[[KILO_TARGET_START]]]')
            )

    return errors, warns


def check_bold_nesting(lines):
    """Flag lines where ** count is odd (unbalanced bold markers)."""
    errors = {}
    for i, line in enumerate(lines, 1):
        stripped = line.strip()
        if not stripped:
            continue
        count = stripped.count('**')
        if count % 2 != 0:
            errors.setdefault(i, []).append(
                ('', f'❌ ** 不成对 ({count} 个) → 加粗嵌套或断裂', stripped[:120])
            )
    return errors


def validate(filepath, allow_term_markers=False):
    with open(filepath, 'r', encoding='utf-8') as f:
        content = f.read()

    lines = content.split('\n')
    content_lines = mask_non_target_lines(lines) if expects_kilo_wrapper(filepath) else lines
    error_lines = {}  # line_no -> [(pattern, desc, matched_text)]
    warn_lines = {}   # line_no -> [(pattern, desc, matched_text)]

    for pattern, desc, severity in CHECKS:
        if allow_term_markers and pattern == TERM_MARKER_PATTERN:
            continue
        for i, line in enumerate(content_lines, 1):
            if re.search(pattern, line):
                if severity == 'error':
                    error_lines.setdefault(i, []).append((pattern, desc, line.strip()[:120]))
                else:
                    warn_lines.setdefault(i, []).append((pattern, desc, line.strip()[:120]))

    # URL checks (always warnings)
    url_errors = check_urls(content_lines)
    for line_no, errs in url_errors.items():
        warn_lines.setdefault(line_no, []).extend(errs)

    # English checks (always warnings - need human review)
    eng_errors = check_english(content_lines)
    for line_no, errs in eng_errors.items():
        warn_lines.setdefault(line_no, []).extend(errs)

    # Bold nesting check (odd ** count = broken)
    bold_errors = check_bold_nesting(content_lines)
    for line_no, errs in bold_errors.items():
        error_lines.setdefault(line_no, []).extend(errs)

    # KILO wrapper checks
    kilo_errors, kilo_warns = check_kilo_markers(lines, filepath)
    for line_no, errs in kilo_errors.items():
        error_lines.setdefault(line_no, []).extend(errs)
    for line_no, errs in kilo_warns.items():
        warn_lines.setdefault(line_no, []).extend(errs)

    return error_lines, warn_lines, lines


def format_errors(error_lines, warn_lines, all_lines):
    """Format errors with surrounding context."""
    out = []

    if error_lines:
        out.append(f"\n{'='*60}")
        out.append(f"错误 ({sum(len(v) for v in error_lines.values())} 处，{len(error_lines)} 行):")
        out.append(f"{'='*60}")
        for line_no in sorted(error_lines):
            errs = error_lines[line_no]
            for _, desc, text in errs:
                out.append(f"\n{'─'*60}")
                out.append(f"L{line_no}:")
                out.append(f"  错误: {desc}")
                out.append(f"  原文: {text}")
            out.append(f"  上下文:")
            start = max(0, line_no - CONTEXT - 1)
            end = min(len(all_lines), line_no + CONTEXT)
            for ctx_no in range(start, end):
                marker = '→' if ctx_no + 1 == line_no else ' '
                out.append(f"  {marker}L{ctx_no+1:4d}: {all_lines[ctx_no].rstrip()[:120]}")

    if warn_lines:
        out.append(f"\n{'='*60}")
        out.append(f"警告 ({sum(len(v) for v in warn_lines.values())} 处，{len(warn_lines)} 行):")
        out.append(f"{'='*60}")
        for line_no in sorted(warn_lines):
            errs = warn_lines[line_no]
            for _, desc, text in errs:
                out.append(f"\n{'─'*60}")
                out.append(f"L{line_no}:")
                out.append(f"  {desc}")
                out.append(f"  原文: {text}")

    return '\n'.join(out)


if __name__ == '__main__':
    args = sys.argv[1:]
    if not args:
        print("Usage: python validate_translation.py <translated.md> [--allow-term-markers]")
        sys.exit(1)

    allow_term_markers = False
    if "--allow-term-markers" in args:
        allow_term_markers = True
        args.remove("--allow-term-markers")

    path = args[0]
    if not os.path.exists(path):
        print(f"文件不存在: {path}")
        sys.exit(1)

    error_lines, warn_lines, all_lines = validate(path, allow_term_markers=allow_term_markers)

    if error_lines or warn_lines:
        total_err = sum(len(v) for v in error_lines.values())
        total_warn = sum(len(v) for v in warn_lines.values())
        print(f"\n发现 {total_err} 处错误，{total_warn} 处警告，涉及 {len(error_lines) + len(warn_lines)} 行:")
        print(format_errors(error_lines, warn_lines, all_lines))
        print(f"\n共 {total_err} 处错误，{total_warn} 处警告需要处理。")
        if error_lines:
            sys.exit(1)
    else:
        print("\n检查通过，未发现问题。")
