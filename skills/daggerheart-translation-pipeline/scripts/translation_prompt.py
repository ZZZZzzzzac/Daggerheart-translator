"""
给翻译 subagent 组装提示词。

结构严格按 pipeline 第六步的三段：
  1. 任务说明（写死在本文件）
  2. 内联标记说明（写死在本文件）
  3. 行文规范 = daggerheart-chinese-writing/SKILL.md 全文（从文件加载）

大体积内容通过文件路径引用，由 subagent 自行 Read：
  - REFERENCE.md -> 给路径让 subagent 读
  - 待翻译 chunk -> 给路径让 subagent 读

修改提示词 = 修改对应的源文件：
  - 任务说明 / 标记规则 -> 改本文件
  - 行文规范 -> 改 daggerheart-chinese-writing/SKILL.md
  - 术语参考 -> 改 daggerheart-chinese-writing/REFERENCE.md
"""

import os
import re

SKILL_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
WRITING_SKILL_DIR = os.path.join(os.path.dirname(SKILL_DIR), "daggerheart-chinese-writing")

# 预计算的绝对路径，注入提示词让 subagent 自行 Read
REFERENCE_PATH = os.path.join(WRITING_SKILL_DIR, "REFERENCE.md")


def _strip_frontmatter(text: str) -> str:
    """去掉 YAML frontmatter（--- ... ---）"""
    return re.sub(r"^---\n.*?\n---\n*", "", text, count=1, flags=re.DOTALL)


def _load_skill_md() -> str:
    """加载 daggerheart-chinese-writing/SKILL.md（行文规范本体）"""
    path = os.path.join(WRITING_SKILL_DIR, "SKILL.md")
    with open(path, "r", encoding="utf-8") as f:
        return _strip_frontmatter(f.read()).strip()


PART1_TASK = """这是一份 Daggerheart TTRPG 游戏文本的英译中工作。全文已被分块，你负责翻译其中一块。保持原始 Markdown 格式，并保留术语审阅标记。"""


PART2_MARKUP = """## 内联标记说明

原文中的部分术语已被标记，格式为：`【原文｜推荐译文｜注释】`

各部分含义：
- `原文` — 被替换的英文原词
- `推荐译文` — 术语表提供的推荐翻译，多个以 `/` 分隔时表示多义词
- `注释` — 对该词的用法说明、上下文提示或固定写法指引

翻译时：
- 多义词必须通读段落上下文，选择符合当前含义的译法
- 如果推荐译文都不适合当前上下文，可以自行翻译
- 如果 `注释` 中出现“在……时译作…… / 形容……时译作…… / 仅在……时使用……”这类限定语境，它是**硬约束**，优先级高于推荐译文表面字形
- 当前句子不满足注释限定语境时，**禁止**机械采用该推荐译文；必须按当前句义自行翻译
- 例如：`running -> 运作` 只在 `running game/session/campaign/NPC` 这类语境成立；若句子是在说“迟到 / 延展 / 流动”，就不能硬译成“运作”
- 例如：`turn/turns -> 轮次` 只在 GM / PC 轮次语境成立；若句子是在说“转身 / 转向 / 变化”，就不能硬译成“轮次”
- **不要删除术语标记。必须把每个 `【原文｜推荐译文｜注释】` 改写成 `【当前译文｜推荐译文｜注释】`**
- `当前译文` 是你结合上下文后的最终中文选择；可以等于推荐译文，也可以是你自行翻译的版本
- `推荐译文` 与 `注释` 默认保持原样，供后续术语审阅使用
- 每个术语标记都必须一一对应保留；不得删除、重排、合并、拆分，也不得把原文英文留在第一槽
"""


def _build_part3() -> str:
    skill_md = _load_skill_md()
    return f"""## 行文规范

以下是完整的行文规范，所有翻译必须严格遵守。

{skill_md}

---
术语详细参考表在以下文件中，请自行 Read 查阅：
{REFERENCE_PATH}

翻译游戏机制相关文本时（资源动词、掷骰修正、伤害修正、状态等），请先查阅该文件中的对应表格，确保用词一致。"""


_TAIL_WITH_PATH = """## 输入内容

待翻译的 chunk 文件路径：
{chunk_path}

请用 Read 工具读取该文件，获取完整原文，然后翻译。

chunk 文件中已包含特殊标记包装的相邻块上下文：

- `[[[KILO_CONTEXT_PREV_START]]] ... [[[KILO_CONTEXT_PREV_END]]]`
- `[[[KILO_TARGET_START]]] ... [[[KILO_TARGET_END]]]`
- `[[[KILO_CONTEXT_NEXT_START]]] ... [[[KILO_CONTEXT_NEXT_END]]]`

注意：
- 所有 `[[[KILO_...]]]` 标记行必须逐字原样保留，不得翻译、删除或改写
- 可以翻译三个区段中的正文内容；后续合并脚本只会保留 `[[[KILO_TARGET_START]]]` 与 `[[[KILO_TARGET_END]]]` 之间的内容
- 当前输出里必须继续保留这三段完整结构，否则后续无法自动合并

## 输出要求

将上面的输入内容翻译为中文，并保留术语审阅标记。

规则：
- 所有术语标记都必须保留为 `【当前译文｜推荐译文｜注释】` 或 `【当前译文｜推荐译文】`
- 不在术语标记外额外补英文括号备注
- 保留所有 Markdown 格式（标题层级、代码块、表格、粗体/斜体）
- 保留图片链接 `![…](_… )` 原样
- 保留作者名、作品名、URL 等专有名词原文
- 保留数据块缩写（ATK、HP、Stress、mag、phy）
- 保留骰子表达式（如 **1d10+6**）
- 保留代词标记（如 (she/her)、(he/him)）

将翻译结果写入文件：
{output_path}"""


def build_prompt(chunk_path: str, output_path: str = "", chunk_notes: str = "") -> str:
    """生成翻译 subagent 的完整提示词。"""
    if not output_path:
        chunk_dir = os.path.dirname(chunk_path)
        chunk_name = os.path.basename(chunk_path)
        output_dir = chunk_dir.replace("_chunks", "_translated_chunks")
        output_path = os.path.join(output_dir, chunk_name)

    parts = [
        PART1_TASK,
        PART2_MARKUP,
        _build_part3(),
    ]

    if chunk_notes.strip():
        parts.append("## 本块特别注意\n\n" + chunk_notes.strip())

    parts.append(
        _TAIL_WITH_PATH.format(
            chunk_path=chunk_path,
            output_path=output_path,
        )
    )

    return "\n\n".join(parts)


if __name__ == "__main__":
    import sys

    args = sys.argv[1:]

    chunk_notes = ""
    if "--notes" in args:
        idx = args.index("--notes")
        chunk_notes = args[idx + 1]
        args = args[:idx] + args[idx + 2 :]

    if not args:
        print("Usage: python translation_prompt.py <chunk_file.md> [--notes \"...\"]")
        sys.exit(1)

    chunk_path = os.path.abspath(args[0])
    prompt = build_prompt(chunk_path, chunk_notes=chunk_notes)
    print(prompt)

    out_dir = os.path.dirname(chunk_path) or "."
    basename = os.path.splitext(os.path.basename(chunk_path))[0]
    prompt_path = os.path.join(out_dir, f"_prompt_{basename}.md")
    with open(prompt_path, "w", encoding="utf-8") as f:
        f.write(prompt)
    print(f"\n\n# 提示词已保存至: {prompt_path}")
