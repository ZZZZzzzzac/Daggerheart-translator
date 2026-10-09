"""Strip reviewed term markers from translated chunks into a clean output directory.

Usage:
    python strip_term_markers.py <project_dir> [--input-dir <dir>] [--output-dir <dir>]

Default:
    input  = source/temp/_translated_chunks
    output = source/temp/_translated_chunks_clean
"""

import argparse
import json
import hashlib
import io
import os
import re
import sys
import tempfile

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

OLD_MARKER_RE = re.compile(r"【([^(】]+?)\s*\([^)]+\)[^】]*】")


def strip_new_term_markers(text):
    """Strip pipe-delimited markers while respecting nested 【...】 in notes."""
    output = []
    index = 0

    while index < len(text):
        if text[index] != "【":
            output.append(text[index])
            index += 1
            continue

        depth = 0
        end = index
        while end < len(text):
            if text[end] == "【":
                depth += 1
            elif text[end] == "】":
                depth -= 1
                if depth == 0:
                    break
            end += 1

        if end >= len(text):
            output.append(text[index])
            index += 1
            continue

        marker = text[index + 1:end]
        if "｜" in marker:
            output.append(marker.split("｜", 1)[0].strip())
        else:
            output.append(text[index:end + 1])
        index = end + 1

    return "".join(output)


def strip_term_markers_text(text):
    text = strip_new_term_markers(text)
    text = OLD_MARKER_RE.sub(lambda match: match.group(1).strip(), text)
    return text


def process_directory(input_dir, output_dir, text_snapshot=None):
    if not os.path.isdir(input_dir):
        raise FileNotFoundError(f"输入目录不存在: {input_dir}")

    os.makedirs(output_dir, exist_ok=True)

    processed = 0
    for filename in sorted(text_snapshot if text_snapshot is not None else os.listdir(input_dir)):
        if not filename.endswith(".md") or filename.startswith("_prompt_"):
            continue

        input_path = os.path.join(input_dir, filename)
        output_path = os.path.join(output_dir, filename)

        if text_snapshot is None:
            with open(input_path, "r", encoding="utf-8") as f:
                text = f.read()
        else:
            text = text_snapshot[filename]

        cleaned = strip_term_markers_text(text)

        # Replace, never truncate a potentially hardlinked existing output inode.
        temp_path = None
        try:
            with tempfile.NamedTemporaryFile(mode='w', encoding='utf-8', dir=output_dir,
                                             prefix='.term-clean-', delete=False) as f:
                temp_path = f.name
                f.write(cleaned)
            os.replace(temp_path, output_path)
        finally:
            if temp_path and os.path.exists(temp_path):
                os.unlink(temp_path)

        processed += 1

    return processed


def main(project_dir, input_dir="", output_dir="", mode="manual", approval=""):
    input_dir = input_dir or os.path.join(project_dir, "source", "temp", "_translated_chunks")
    output_dir = output_dir or os.path.join(project_dir, "source", "temp", "_translated_chunks_clean")

    # Rebuild from actual bytes. An edited report cannot grant approval.
    from check_terms import build_report
    from term_review import approval_path, validate_approval
    default_input = os.path.join(project_dir, 'source', 'temp', '_translated_chunks')
    if os.path.realpath(input_dir) != os.path.realpath(default_input):
        raise ValueError('审批绑定默认译文目录；自定义输入请建立独立项目并重新检查')
    protected = [input_dir, os.path.join(project_dir, 'source', 'temp', '_chunks')]
    if os.path.realpath(output_dir) in {os.path.realpath(p) for p in protected}:
        raise ValueError('输出目录不能覆盖带标记输入')
    report = build_report(project_dir)
    if report['stats']['structural_anomalies']:
        raise ValueError('结构异常未修复，禁止清标记')
    if mode == 'manual':
        path = approval or approval_path(project_dir)
        with open(path, encoding='utf-8') as f:
            validate_approval(report, json.load(f))
    elif mode != 'auto':
        raise ValueError('未知模式')
    # Validate the full files too: context wrappers are stripped as well as targets.
    from term_markers import parse_markers
    from term_review import input_manifest
    text_snapshot = {}
    for filename in sorted(os.listdir(input_dir)):
        if filename.endswith('.md') and not filename.startswith('_prompt_'):
            with open(os.path.join(input_dir, filename), 'rb') as f:
                raw = f.read()
            if hashlib.sha256(raw).hexdigest() != report['input_manifest'].get('_translated_chunks/' + filename):
                raise ValueError('审阅后输入发生变化，请重新检查')
            # Match normal text-mode universal-newline behavior of the original stripper.
            text_snapshot[filename] = io.StringIO(raw.decode('utf-8'), newline=None).read()
            errors = parse_markers(text_snapshot[filename])[1]
            if errors:
                raise ValueError(f'{filename}: 标记损坏: {errors}')
    if os.path.islink(output_dir) or (os.path.isdir(output_dir) and any(os.path.islink(os.path.join(output_dir, f)) for f in os.listdir(output_dir))):
        raise ValueError('输出目录或文件不能是符号链接')
    existing = set(os.listdir(output_dir)) if os.path.isdir(output_dir) else set()
    expected = {f for f in os.listdir(input_dir) if f.endswith('.md') and not f.startswith('_prompt_')}
    stale = {f for f in existing if f.endswith('.md') and not f.startswith('_prompt_')} - expected
    if stale:
        raise ValueError('输出目录含旧 chunk；请使用新的输出目录: ' + ', '.join(sorted(stale)))
    if input_manifest(project_dir) != report['input_manifest']:
        raise ValueError('审阅后源文或译文发生变化，请重新检查')
    # From here onward use only the exact validated bytes, never reread mutable input.
    processed = process_directory(input_dir, output_dir, text_snapshot=text_snapshot)
    print(f"已清理 {processed} 个 chunk 文件，输出目录: {output_dir}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('project_dir')
    parser.add_argument('--input-dir', default='')
    parser.add_argument('--output-dir', default='')
    parser.add_argument('--mode', choices=('manual', 'auto'), default='manual')
    parser.add_argument('--approval', default='')
    args = parser.parse_args()
    try:
        main(args.project_dir, args.input_dir, args.output_dir, args.mode, args.approval)
    except (ValueError, OSError) as exc:
        parser.exit(1, f"错误：{exc}\n")
