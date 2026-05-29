"""Strip reviewed term markers from translated chunks into a clean output directory.

Usage:
    python strip_term_markers.py <project_dir> [--input-dir <dir>] [--output-dir <dir>]

Default:
    input  = source/temp/_translated_chunks
    output = source/temp/_translated_chunks_clean
"""

import os
import re
import sys

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

NEW_MARKER_RE = re.compile(r"【([^｜】]+)｜[^】]*】")
OLD_MARKER_RE = re.compile(r"【([^(】]+?)\s*\([^)]+\)[^】]*】")


def strip_term_markers_text(text):
    text = NEW_MARKER_RE.sub(lambda match: match.group(1).strip(), text)
    text = OLD_MARKER_RE.sub(lambda match: match.group(1).strip(), text)
    return text


def process_directory(input_dir, output_dir):
    if not os.path.isdir(input_dir):
        raise FileNotFoundError(f"输入目录不存在: {input_dir}")

    os.makedirs(output_dir, exist_ok=True)

    processed = 0
    for filename in sorted(os.listdir(input_dir)):
        if not filename.endswith(".md") or filename.startswith("_prompt_"):
            continue

        input_path = os.path.join(input_dir, filename)
        output_path = os.path.join(output_dir, filename)

        with open(input_path, "r", encoding="utf-8") as f:
            text = f.read()

        cleaned = strip_term_markers_text(text)

        with open(output_path, "w", encoding="utf-8") as f:
            f.write(cleaned)

        processed += 1

    return processed


def main(project_dir, input_dir="", output_dir=""):
    input_dir = input_dir or os.path.join(project_dir, "source", "temp", "_translated_chunks")
    output_dir = output_dir or os.path.join(project_dir, "source", "temp", "_translated_chunks_clean")

    processed = process_directory(input_dir, output_dir)
    print(f"已清理 {processed} 个 chunk 文件，输出目录: {output_dir}")


if __name__ == "__main__":
    args = sys.argv[1:]
    if not args:
        print("Usage: python strip_term_markers.py <project_dir> [--input-dir <dir>] [--output-dir <dir>]")
        sys.exit(1)

    project_dir = args[0]
    input_dir = ""
    output_dir = ""

    if "--input-dir" in args:
        idx = args.index("--input-dir")
        input_dir = args[idx + 1]
    if "--output-dir" in args:
        idx = args.index("--output-dir")
        output_dir = args[idx + 1]

    try:
        main(project_dir, input_dir=input_dir, output_dir=output_dir)
    except FileNotFoundError as exc:
        print(f"错误：{exc}")
        sys.exit(1)
