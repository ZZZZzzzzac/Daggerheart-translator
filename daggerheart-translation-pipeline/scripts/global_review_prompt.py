import argparse
import os

from loop_prompt_utils import (
    REFERENCE_PATH,
    SCHEMA_PATH,
    ensure_parent_dir,
    global_review_prompt_path,
    global_review_report_path,
    load_writing_skill,
    merged_chunk_map_path,
)


TASK = """你是 global reviewer，只负责 merged 全文的跨 chunk 一致性审查，不负责修改文件。"""


RULES = """## 审核重点

- 同一专有名词跨 chunk 译法不一致
- 同一种机制短语、资源动词、格式模板前后写法不统一
- 章节标题风格不一致
- 合并边界的重复、断裂或衔接不自然

## 严格规则

- 不要复查 chunk 内已经能独立发现的局部润色问题
- 只报告跨 chunk 或 merge 边界问题
- 不修改任何文件
- 每个 issue 必须给出 `chunk_labels`，并以 chunk map 为准路由到一个或多个 chunk
- 每个 issue 必须引用具体位置或片段，并给出修正方向
- 没问题时也必须输出合法 JSON，`issues` 为空数组
- 输出必须匹配 schema，不得夹带任何额外说明文字
"""


def build_prompt(merged_path, chunk_map_path="", output_path="", merged_terms_path="", glossary_path=""):
    merged_path = os.path.abspath(merged_path)
    chunk_map_path = os.path.abspath(chunk_map_path or merged_chunk_map_path(merged_path))
    output_path = os.path.abspath(output_path or global_review_report_path(merged_path))
    writing_skill = load_writing_skill()

    optional_refs = []
    if merged_terms_path:
        optional_refs.append(f"- merged terms: {os.path.abspath(merged_terms_path)}")
    if glossary_path:
        optional_refs.append(f"- document glossary: {os.path.abspath(glossary_path)}")
    optional_ref_block = "\n".join(optional_refs) if optional_refs else "- 无额外 glossary 文件"

    return f"""{TASK}

{RULES}

## 行文规范

{writing_skill}

---
额外参考文件，请自行 Read：
- REFERENCE.md: {REFERENCE_PATH}
- Review issue schema: {SCHEMA_PATH}
{optional_ref_block}

## 输入文件

- merged 全文：{merged_path}
- chunk map：{chunk_map_path}

请自行 Read 上述文件。chunk map 给出了 merged 全文对应的 chunk label 与行号区间，必须据此给每个 issue 标注 `chunk_labels`。

## 输出要求

- 只输出一个 JSON object，并写入：{output_path}
- 顶层 `scope` 固定为 `global_review`
- 顶层 `target_file` 固定为 `{merged_path}`
- 每个 issue 的 `chunk_labels` 必须来自 chunk map 中已有的 label
- 若无问题，写出：`{{"scope":"global_review","target_file":"{merged_path}","issues":[]}}`

完成后，只返回一行简短总结，说明写入了哪个 JSON 文件、共有几条 issue。"""


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Build global reviewer prompt for merged translated markdown")
    parser.add_argument("merged_file", help="Path to merged translated markdown")
    parser.add_argument("--chunk-map", default="", help="Optional merged chunk map JSON path")
    parser.add_argument("--output", default="", help="Optional global review JSON output path")
    parser.add_argument("--merged-terms", default="", help="Optional merged terms JSON path")
    parser.add_argument("--glossary", default="", help="Optional document glossary JSON path")
    args = parser.parse_args()

    prompt = build_prompt(
        args.merged_file,
        chunk_map_path=args.chunk_map,
        output_path=args.output,
        merged_terms_path=args.merged_terms,
        glossary_path=args.glossary,
    )
    print(prompt)

    prompt_path = global_review_prompt_path(args.merged_file)
    ensure_parent_dir(prompt_path)
    with open(prompt_path, "w", encoding="utf-8") as f:
        f.write(prompt)
    print(f"\n\n# 提示词已保存至: {prompt_path}")
