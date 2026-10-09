"""
给翻译 subagent 组装提示词。

结构遵循 pipeline 第六步，复用完整行文规范：
  1. 任务说明（写死在本文件）
  2. 内联标记说明（写死在本文件）
  3. 行文规范 = daggerheart-chinese-writing/SKILL.md 全文（从文件加载）
  4. 精简源文不变量自检（与独立 QA 共用）

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
CORE_PATH = os.path.join(SKILL_DIR, "resources", "terms-core.json")
RESOURCE_GUIDE_PATH = os.path.join(SKILL_DIR, "resources", "README.md")

# Shared by translator and independent QA, not copied into multiple rule files.
SEMANTIC_CHECKS = """逐项对照源文检查：行动者、选择者、掷骰者、代价承担者、效果接受者；
肯定/否定与可选/强制、实际行动与行动意愿；触发、成功/失败分支和例外；骰式、修正、数量、单位及比较边界；
一个/另一个/所有/每个、目标范围、频率和持续时间；资源动词及其对象。
不得漏句、增规则、改变指代或将共用掷骰改为逐个掷骰。
先区分代词的语法数与语篇指向：they/them/their 可以是单数、性别中性的 TA，也可以是复数，不能自动译成“他们”。
逐一跟踪受影响角色与行动/掷骰的协助者；协助者掷骰不等于协助者承担代价或接受效果。不得机械采用“最近名词”规则。
指向已明确时，优先用“该角色”“受困角色”“协助者”等准确名词消除中文歧义；确属复数才用“这些角色”等复数表达，不擅自推定性别。
若行动者、代价承担者、效果接受者或作用范围存在会改变规则的歧义，提供的更广上下文能消歧，或有与当前源文及情境匹配的项目内用户已审定解释时，才明确化；
项目审定例只适用于其记录的源文和情境，不是所有 they 都指受困者的通则；源文显式改变行动者或效果对象时，以当前源文为准，不套用旧例。
否则保留源文歧义，并在正文外报告准确位置、短引文和具体候选解释，不得为行文流畅擅自补定主语或范围。
泛指复数不能单独证明一次发动或花费会作用于多个目标，也不能仅凭前文单数擅自添加“只限一个”；须结合触发事件、目标集合与费用作用范围判断。
普通且指向明确的代词不必报疑；不要把所有省略主语都视为歧义。"""


def resource_instructions() -> str:
    return f"""先读取以下规则资源：
- 中文语境、资源动词、状态与名称格式：{REFERENCE_PATH}
- 人工维护的核心术语表：{CORE_PATH}
- 术语范围与项目选用规则：{RESOURCE_GUIDE_PATH}
同义项优先级：核心表 > 适用的敌人专项表 > 项目表。只裁决同一含义的译名，不能把普通词强行机制化。
已有内联标记不替代语境判断；无标记处也检查术语。六个官方框架名称继续使用核心译名。
适用的术语注释模板须完整保留名称格式与机制；条件模板只用于其限定语境，不得从特性名套用于经历等不同用途。
模板与源文含义冲突时以源文为准，并报告冲突，不得静默改规则。
两个框架机制表仅在项目确属对应框架且词义适用时选用，不默认加载 scoped/。不得修改核心表。
以分配的源文版本为准，不凭记忆或新版本静默改规则；材料不足或版本冲突只记录准确位置和待决问题。"""


def reviewed_decision_instructions(path: str = "") -> str:
    """Opt-in project interpretation; unrelated reviewed examples are never auto-loaded."""
    if not path:
        return ""
    return f"""## 项目内已审定解释（显式提供）
读取：{os.path.abspath(path)}
先核对项目、完整源文/摘要及适用情境，只采用与当前材料匹配的用户已审定解释。
它不是通用术语规则或参考译文；不得将个例推广为所有代词的指向。
当前源文显式改变行动者、代价承担者或效果对象时，以当前源文为准，不套用旧例。
已有匹配裁决能消歧时直接落实，不重复报为未决问题；其余真正歧义仍按源文保真自检处理。"""


SEMANTIC_SELF_CHECK = f"""## 源文保真自检

{SEMANTIC_CHECKS}
再连读中文，检查规则能否直接执行、叙事视角和人物口吻是否保留。改写后复核改动句的含义。
先自行修复可由源文决定的错误；只有提供材料无法决定的问题才交人确认，附位置、短引文和暂用译法。
不要输出逐句推理或未经验证的数字置信度；格式/术语检查通过不等于语义正确。"""


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
- `原文` — 术语关键字匹配上的英文原词
- `推荐译文` — 术语表提供的推荐翻译，多个以 `/` 分隔时表示多义词
- `注释` — 对该词的用法说明、上下文提示或固定写法指引

翻译时：
- 多义词必须通读段落上下文，选择符合当前含义的译法
- 如果推荐译文都不适合当前上下文，可以自行翻译
- 如果 `注释` 中出现“在……时译作…… / 形容……时译作…… / 仅在……时使用……”这类限定语境，它是**硬约束**，优先级高于推荐译文表面字形
- 当前句子不满足注释限定语境时，**禁止**机械采用该推荐译文；必须按当前句义自行翻译
- 例如：`running -> 运作` 只在 `running game/session/campaign/NPC` 这类语境成立；若句子是在说“奔跑”，就不能硬译成“运作”
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
{resource_instructions()}

翻译游戏机制相关文本时（资源动词、掷骰修正、伤害修正、状态等），请先查阅 REFERENCE.md 中的对应表格，确保用词一致。"""


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
- 作者署名和 URL 保留原文；作品名按 REFERENCE 的“已有译名的作品”规则处理
- 世界内的人物、地名、组织和称号应译为中文，优先复用项目译名；不可把“保留作者署名”扩大为所有专名不译
- 先区分名称角色与普通用词。例如 NPC 名 “Mira” 应用项目中文译名或拟定中文名；作者署名 “Mira” 保留原文；普通 broken 不因同形就套用名为 Broken 的专名译法
- 正式机制名按 REFERENCE 的“名称原文标注”段处理；普通用法不附英文，后续简称按该段规则处理
- 保留骰子表达式（如 **1d10+6**）
- 保留代词标记（如 (she/her)、(he/him)）

将翻译结果写入文件：
{output_path}"""


def build_prompt(chunk_path: str, output_path: str = "", chunk_notes: str = "", reviewed_decisions_path: str = "") -> str:
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
        SEMANTIC_SELF_CHECK,
    ]

    if reviewed_decisions_path:
        parts.append(reviewed_decision_instructions(reviewed_decisions_path))

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

    reviewed_decisions_path = ""
    if "--reviewed-decisions" in args:
        idx = args.index("--reviewed-decisions")
        reviewed_decisions_path = args[idx + 1]
        args = args[:idx] + args[idx + 2 :]

    chunk_notes = ""
    if "--notes" in args:
        idx = args.index("--notes")
        chunk_notes = args[idx + 1]
        args = args[:idx] + args[idx + 2 :]

    if not args:
        print("Usage: python translation_prompt.py <chunk_file.md> [--notes \"...\"] [--reviewed-decisions <project-decisions.json>]")
        sys.exit(1)

    chunk_path = os.path.abspath(args[0])
    prompt = build_prompt(chunk_path, chunk_notes=chunk_notes, reviewed_decisions_path=reviewed_decisions_path)
    print(prompt)

    out_dir = os.path.dirname(chunk_path) or "."
    basename = os.path.splitext(os.path.basename(chunk_path))[0]
    prompt_path = os.path.join(out_dir, f"_prompt_{basename}.md")
    with open(prompt_path, "w", encoding="utf-8") as f:
        f.write(prompt)
    print(f"\n\n# 提示词已保存至: {prompt_path}")
