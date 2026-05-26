import argparse
import os

from loop_prompt_utils import (
    REFERENCE_PATH,
    SCHEMA_PATH,
    chunk_label_from_path,
    ensure_parent_dir,
    fixer_prompt_path,
    review_report_path,
    sibling_source_chunk_path,
    validator_report_path,
)


TASK = """你是 chunk fixer，不是 translator，也不是 reviewer。你的职责是根据 reviewer issue JSON 与 validator JSON，在原地修正译文 chunk。"""


RULES = """## 严格规则

- 只修改 `[[[KILO_TARGET_START]]] ... [[[KILO_TARGET_END]]]` 之间的正文
- 不得修改任何 `[[[KILO_...]]]` 标记行
- 不得修改元数据行
- 不得修改 `KILO_CONTEXT_PREV` / `KILO_CONTEXT_NEXT` 段
- 只修 issue JSON 中点名的问题，以及 validator JSON 中的硬错误
- 如果 issue JSON 是 global review 结果，只处理其中 `chunk_labels` 包含当前 chunk 的条目
- 不准顺手重写整段、全文润色、统一文风到 issue 之外的内容
- 不准保留 `【】` 术语标记
- 修改后将结果写回原译文 chunk 文件
"""


def build_prompt(translated_chunk_path, source_chunk_path="", review_json_path="", validator_json_path=""):
    translated_chunk_path = os.path.abspath(translated_chunk_path)
    source_chunk_path = os.path.abspath(source_chunk_path or sibling_source_chunk_path(translated_chunk_path))
    review_json_path = os.path.abspath(review_json_path or review_report_path(translated_chunk_path))
    validator_json_path = os.path.abspath(validator_json_path or validator_report_path(translated_chunk_path))
    chunk_label = chunk_label_from_path(translated_chunk_path)

    return f"""{TASK}

{RULES}

额外参考文件，请自行 Read：
- REFERENCE.md: {REFERENCE_PATH}
- Review issue schema: {SCHEMA_PATH}

## 输入文件

- 源 chunk：{source_chunk_path}
- 当前译文 chunk：{translated_chunk_path}
- reviewer / global-review issue JSON：{review_json_path}
- validator JSON：{validator_json_path}

请自行 Read 上述文件。

## 当前 chunk 标识

- 当前 chunk label：`{chunk_label}`

## 输出要求

- 直接原地修改：{translated_chunk_path}
- 仅处理 `chunk_labels` 包含 `{chunk_label}` 的 issue
- 若 issue JSON 中没有当前 chunk 的问题，但 validator JSON 有硬错误，则只修 validator 错误
- 修改完成后，只返回一行简短总结，说明修了哪些问题、是否写回成功
"""


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Build fixer prompt for a translated chunk")
    parser.add_argument("translated_chunk", help="Path to translated chunk file")
    parser.add_argument("--source", default="", help="Optional source chunk path")
    parser.add_argument("--review-json", default="", help="Optional reviewer/global-review issue JSON path")
    parser.add_argument("--validator-report", default="", help="Optional validator JSON report path")
    args = parser.parse_args()

    prompt = build_prompt(
        args.translated_chunk,
        source_chunk_path=args.source,
        review_json_path=args.review_json,
        validator_json_path=args.validator_report,
    )
    print(prompt)

    prompt_path = fixer_prompt_path(args.translated_chunk)
    ensure_parent_dir(prompt_path)
    with open(prompt_path, "w", encoding="utf-8") as f:
        f.write(prompt)
    print(f"\n\n# 提示词已保存至: {prompt_path}")
