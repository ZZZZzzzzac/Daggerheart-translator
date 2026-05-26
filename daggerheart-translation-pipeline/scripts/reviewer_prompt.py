import argparse
import os

from loop_prompt_utils import (
    REFERENCE_PATH,
    SCHEMA_PATH,
    chunk_label_from_path,
    ensure_parent_dir,
    load_writing_skill,
    review_report_path,
    reviewer_prompt_path,
    sibling_source_chunk_path,
    validator_report_path,
)


TASK = """你是 chunk reviewer，不是 translator，也不是 fixer。你的职责是比较源 chunk 与译文 chunk 的 KILO_TARGET 内容，找出需要修的真实问题，并输出结构化 JSON。不得修改任何文件，除了把最终 JSON 写到指定输出路径。"""


RULES = """## 审核重点

- 机制术语应查 REFERENCE 却没查，自创译名
- 不应套术语表的普通文本被强行套了固定术语
- 机制文本未按 REFERENCE 的句式/加粗/格式执行
- 文学与叙述句子保留英文骨架，读起来像翻译稿
- 对话生硬、不像人话
- markdown 结构损坏或信息块断裂
- 跨句风格不一致、称谓不统一

## 严格规则

- 只报告问题，不修改译文
- 只检查当前 chunk 的 `KILO_TARGET`，不要评论全文
- 不要重复 validator 已经能确定判出的纯硬错误，除非它同时体现了写作/术语/格式问题
- 每个 issue 必须引用具体位置，优先用 `Lxx` 行号，并附上必要片段
- 每个 issue 必须引用具体规范来源，如 `REFERENCE.md: 资源变动` 或 `SKILL.md: 核心写法`
- 没问题时也必须输出合法 JSON，`issues` 为空数组
- 输出必须匹配 schema，不得夹带任何额外说明文字

## 分类

- `term_miss`
- `term_overuse`
- `mechanics_form`
- `translationese`
- `dialogue_stiff`
- `description_flat`
- `feels_translated`
- `term_wrong`
- `markdown`
- `style`
"""


def build_prompt(translated_chunk_path, source_chunk_path="", validator_json_path="", output_path=""):
    translated_chunk_path = os.path.abspath(translated_chunk_path)
    source_chunk_path = os.path.abspath(source_chunk_path or sibling_source_chunk_path(translated_chunk_path))
    validator_json_path = os.path.abspath(validator_json_path or validator_report_path(translated_chunk_path))
    output_path = os.path.abspath(output_path or review_report_path(translated_chunk_path))
    chunk_label = chunk_label_from_path(translated_chunk_path)
    writing_skill = load_writing_skill()

    return f"""{TASK}

{RULES}

## 行文规范

{writing_skill}

---
额外参考文件，请自行 Read：
- REFERENCE.md: {REFERENCE_PATH}
- Review issue schema: {SCHEMA_PATH}

## 输入文件

- 源 chunk：{source_chunk_path}
- 译文 chunk：{translated_chunk_path}
- validator JSON：{validator_json_path}

请自行 Read 上述文件。重点比较源/译两个 chunk 的 `[[[KILO_TARGET_START]]] ... [[[KILO_TARGET_END]]]` 段；上下文段只用于辅助理解。

## 输出要求

- 只输出一个 JSON object，并写入：{output_path}
- JSON 顶层必须是：
  - `scope`: 固定为 `chunk_review`
  - `target_file`: 固定为 `{translated_chunk_path}`
  - `issues`: issue 数组
- 每个 issue 的 `chunk_labels` 必须只包含当前 chunk label：`{chunk_label}`
- 若无问题，写出：`{{"scope":"chunk_review","target_file":"{translated_chunk_path}","issues":[]}}`

完成后，只返回一行简短总结，说明写入了哪个 JSON 文件、共有几条 issue。"""


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Build reviewer prompt for a translated chunk")
    parser.add_argument("translated_chunk", help="Path to translated chunk file")
    parser.add_argument("--source", default="", help="Optional source chunk path")
    parser.add_argument("--validator-report", default="", help="Optional validator JSON report path")
    parser.add_argument("--output", default="", help="Optional reviewer JSON output path")
    args = parser.parse_args()

    prompt = build_prompt(
        args.translated_chunk,
        source_chunk_path=args.source,
        validator_json_path=args.validator_report,
        output_path=args.output,
    )
    print(prompt)

    prompt_path = reviewer_prompt_path(args.translated_chunk)
    ensure_parent_dir(prompt_path)
    with open(prompt_path, "w", encoding="utf-8") as f:
        f.write(prompt)
    print(f"\n\n# 提示词已保存至: {prompt_path}")
