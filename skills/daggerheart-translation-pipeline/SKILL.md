---
name: daggerheart-translation-pipeline
description: Orchestrates the end-to-end Daggerheart translation flow: project setup, source-to-Markdown conversion, Markdown cleanup, glossary tagging, chunked translation with retained term markers, term review, marker stripping, validation, and JSON extraction.
---

# Daggerheart Translation Pipeline

英文 Daggerheart PDF/DOCX 输入，中文 Markdown + 结构化 JSON 输出。

这是总编排 skill。它只负责：
- 步骤顺序
- 输入输出路径
- 人工确认节点
- 跨步骤硬规则

子步骤的实现细节，交给对应子 skill 或脚本本身，不在此重复展开。

## 依赖技能

- `daggerheart-md-converter`：PDF/DOCX -> `source/_raw.md`
- `daggerheart-md-format-fixer`：`source/_raw.md` -> `source/_original.md`
- `daggerheart-glossary-extractor`：提取文档术语表
- `daggerheart-chinese-writing`：翻译 subagent 的写作规范
- `daggerheart-term-checker`：生成术语审阅报告，并在审阅后清理术语标记
- `daggerheart-json-formatter`：译文 MD -> 结构化 JSON

## 运行模式

在执行第 0 步前，必须先用 `question` 工具确认运行模式，不得跳过。

- `手动模式（推荐）`
  - 术语冲突时暂停，等用户处理
  - `chunk 01` 翻译后暂停，等用户审查
  - 并行翻译前再次确认
  - 术语审阅报告由人工审阅
- `全自动模式`
  - 术语冲突按固定优先级自动裁决
  - `chunk 01` 自动检查后直接继续
  - 术语审阅报告由 AI 自动审阅并直接回写 chunk
  - 并行翻译、术语审阅、清标记、合并、makeup、检查、JSON 提取连续执行
  - 仅在最终汇报结果

固定优先级：

`terms-core.json` > `adversaries_*.json` > `glossary/_glossary.json`

核心表是人工维护的规则术语基线，不是 ParaTranz 导出快照。六个官方战役框架名称保留于核心表以统一译名。项目独有的人名、地名、组织及概念应留在项目术语表；不得自动回填核心表。框架专属机制使用各自的框架术语表，按当前项目需要选用，不放入总表。`resources/scoped/` 仅供按项目选择条目，不参与默认合并。具体边界与迁移记录见 `resources/README.md`。

## 路径约定

所有命令在**用户翻译项目根目录**执行。

关键路径：
- `source/_raw.md`：转换后的原始 Markdown
- `source/_original.md`：修复后的原文 Markdown
- `source/temp/`：临时产物
- `source/temp/_tagged.md`：内联术语标记后的原文
- `source/temp/_translated_chunks/`：保留术语标记的译文 chunk
- `source/temp/_term_review_report.md`：术语审阅 Markdown 报告
- `source/temp/_term_review_report.json`：术语审阅 JSON 报告
- `source/temp/_translated_chunks_clean/`：清除术语标记后的译文 chunk
- `source/_translated.md`：最终译文 Markdown
- `glossary/_glossary.json`：文档术语表
- `data/`：结构化 JSON 输出

命令里的路径分两类：
- `scripts/`、`resources/`：相对于本 skill 根目录
- `source/`、`source/temp/`、`glossary/`、`data/`：相对于项目根目录

AI 执行时必须分别解析到正确绝对路径。

## 管线

```text
前置. 确认运行模式（手动审阅 / 全自动）
0. 初始化项目结构
1. PDF/DOCX -> 原始 MD
2. 修复原文格式
3. 提取文档术语表
4. 内联术语替换
5. 分块
6. 翻译（chunk 01 确认 -> 并行）
7. 术语审阅报告
8. 清除术语标记
9. 合并
10. makeup
11. 自动检查 + 修正循环
12. JSON 提取
```

## 第 0 步：初始化项目结构

```bash
python scripts/setup_project.py <项目目录>
```

目标：确保项目目录结构符合标准布局。脚本应视为幂等初始化工具。

## 第 1 步：源文档 -> 原始 Markdown

调用 `daggerheart-md-converter` 技能，将 PDF/DOCX 转为项目 `source/_raw.md`。

## 第 2 步：修复原文格式

调用 `daggerheart-md-format-fixer` 技能，将 `source/_raw.md` 修为 `source/_original.md`。

## 第 3 步：提取文档术语表

调用 `daggerheart-glossary-extractor` 技能，扫描 `source/_original.md`，输出 `glossary/_glossary.json`。

## 第 4 步：内联术语替换

将全局术语表与本文档术语表合并，并对原文做内联标记。

```bash
python scripts/merge_terms.py --terms "resources/terms-core.json" "resources/adversaries_features.json" "resources/adversaries_motivation.json" "resources/adversaries_name.json" "glossary/_glossary.json" --output "source/temp/_merged_terms.json" --original "source/_original.md"
python scripts/replace_terms.py "source/_original.md" "source/temp/_merged_terms.json" "source/temp/_tagged.md"
```

- 输出：`source/temp/_merged_terms.json`、`source/temp/_tagged.md`
- 标记格式：`【原文｜推荐译文｜注释】`
- `注释` 可为空；若为空则标记退化为 `【原文｜推荐译文】`
- 默认手动模式：若出现术语冲突，暂停，等待用户处理后再继续
- 全自动模式：给 `merge_terms.py` 增加 `--auto-resolve`，按固定优先级自动保留高优先级译名，并继续执行；最终汇报冲突结果

## 第 5 步：分块

```bash
python scripts/split_chunks.py "source/temp/_tagged.md" --min-chars 4000 --target-chars 5500 --max-chars 7000 --context-chars 1200
```

- 输出目录：`source/temp/_chunks/`
- 分块脚本会自动加入 `KILO_CONTEXT` / `KILO_TARGET` 包装段，后续合并时只保留 `KILO_TARGET`

## 第 6 步：翻译

### 6.0 模型选择

优先使用快速便宜模型，并关闭或尽量降低 thinking。若当前环境没有合适快速模型，先向用户说明实际将使用哪种模型执行翻译 subagent。

### 6.1 翻译 `chunk 01`

先生成该 chunk 的完整翻译 prompt：

```bash
python scripts/translation_prompt.py "<chunk_file>"
# 若本项目提供了用户已审定解释，可显式附加：
# --reviewed-decisions "<本项目的 reviewed-decisions.json>"
```

硬约束：
- 该脚本会生成 `_prompt_xxx.md`
- 必须用 `Read` 工具读取该 prompt 文件
- 必须将读取到的**完整内容原样**作为 subagent 的 prompt 传入
- 不得删减、重写、概括、改写或替换其中规则

原因：翻译 prompt 是在启动 subagent 时才提供的，这个 prompt 本身就是 pipeline 的一部分，不是可自由压缩的附属说明。

翻译 subagent 负责：
- 读取当前 chunk 文件与 `REFERENCE.md`
- 产出对应译文到 `source/temp/_translated_chunks/`
- 保留所有 `[[[KILO_...]]]` 标记行原样不变
- 将 `【原文｜推荐译文｜注释】` 改写为 `【当前译文｜推荐译文｜注释】`
- 每个术语标记必须一一对应保留，不得删除、重排、合并、拆分
- `推荐译文` 与 `注释` 仅作参考与审阅依据，默认保持原样

手动模式：
- 展示 `chunk 01` 原文与译文给用户审查
- 用户确认前，不得进入下一步

全自动模式：
- 完成 `chunk 01` 后，自动检查 KILO 结构与术语标记是否完整保留，再继续后续 chunk

### 6.2 并行翻译剩余 chunk

手动模式下，在 `chunk 01` 通过后，必须明确提示用户：

`chunk 01 已确认，是否开始并行翻译剩余 N 个 chunk？`

收到确认后，并行启动剩余 chunk 的翻译。

剩余 chunk 必须沿用 **6.1 完全相同** 的 prompt 生成与原样传递规则，不得自行编写缩略版 prompt。

全自动模式下，跳过该确认，直接并行执行。

## 第 7 步：完整审计 + 短决策队列 + 全文 QA

调用 `daggerheart-term-checker`，保留逐出现位置九列审计，同时生成完整、不截断的短决策队列：

```bash
python <term_checker_skill_root>/scripts/check_terms.py <项目目录>
```

- `_term_review_report.md/.json` 保留所有出现位置。
- `_term_decision_queue.md/.json` 汇总字符串差异、结构/对位未知和独立语义 QA 的未决项；仅相同双语完整句及同一决策才合并。
- 词面采用推荐不代表语义正确；不得遗漏人名/普通词误标、主体与规则错误或无标记文字。
- 可用 `python scripts/semantic_qa_prompt.py <项目目录>` 生成全文独立 QA 提示词。若翻译时显式提供项目内已审定解释，QA 同样传入 `--reviewed-decisions <同一文件>`；必须匹配项目、完整源文/摘要及情境，不能自动套用其他项目裁决或覆盖源文明确改变的角色。
- AI 必须独立对照全部源译文做语义 QA，先自行修复有充分依据的问题；修改后重跑检查。只有真实未决项请用户决定，不要求用户逐词审阅完整审计。
- 使用 checker 技能规定的 hash-bound `_term_semantic_issues.json` 汇入尚未解决的语义问题，已修复项单独留审计记录。
- 向用户提交任何未决问题前，必须走 term-checker 的严格上下文导出：提供可定位的完整原文能力/段落与必要上下文、当前对应译文、明确问题、具体选项、推荐及理由。原文和译文须与当前实际文件对应，不得把概述标作原文。
- 同一能力有多个问题时合为一张问题卡展示共同材料，独立问题仍分别计数；不得删减问题来压低数量。翻译交付阻塞、可保留原文的玩法裁定和源文缺项分开说明。
- 确定合理的例外用 `approve_term_review.py --review-digest <当前审阅哈希> --reviewer AI:model --approve <ID> --reason <依据>` 逐项记录。完成全文 QA 后记录 `--accept-baseline --semantic-reviewed`。声明不等于脚本验证了语义。
- 结构异常必须先修复，不能批准绕过；所有未决计数都保留，不使用未经验证的置信度分数隐藏问题。

手动模式：
- 展示剩余决策队列与 AI 修复摘要，取得用户仍未裁决问题的选择。
- 全部问题处理后，用户明确确认继续，才记录 `approve_term_review.py <项目目录> --review-digest <当前审阅哈希> --reviewer human:<确认者> --release`。
- 任一源文/译文或分组输入改变都会使旧批准失效；重新生成报告并审阅当前版本。部分批准不能放行。

全自动模式：
- AI 仍须完成全文语义 QA、修复确定问题并披露未能裁决的限制；不把推荐词面一致当作审阅结果。
- 用户已明确选全自动时，下一步显式使用 `--mode auto`，不需要人工放行；不能临时用此选项绕过手动确认。

## 第 8 步：带可执行门禁的清标记

```bash
# 手动模式：要求当前内容哈希对应的完整审阅与用户放行记录
python <term_checker_skill_root>/scripts/strip_term_markers.py <项目目录>
# 已获用户选择的全自动模式
python <term_checker_skill_root>/scripts/strip_term_markers.py <项目目录> --mode auto
```

- 输入：`source/temp/_translated_chunks/`；输出：`source/temp/_translated_chunks_clean/`。
- 保留原件；合并仅用 clean 目录。清标记前重新校验结构和实际文件，不信任手工改过的报告。
- 具体接受 ID、语义问题 schema、批准理由和失效规则见 `daggerheart-term-checker/SKILL.md`。

## 第 9 步：合并

```bash
python scripts/split_chunks.py "source/temp/_translated_chunks_clean" --merge --output "source/_translated.md"
```

输出：`source/_translated.md`

## 第 10 步：makeup 后处理

```bash
python scripts/makeup.py "source/_translated.md" --suffix ""
```

## 第 11 步：自动检查 + AI 修正循环

```bash
python scripts/validate_translation.py "source/_translated.md"
```

若检查不通过：
1. 根据脚本输出直接修改 `source/_translated.md`
2. 重新运行检查脚本
3. 重复直到检查通过

规则性错误可批量修正，不规则错误逐行修正。

若需要在清标记前对单个带标记 chunk 做结构检查，可使用：

```bash
python scripts/validate_translation.py "<chunk_file>" --allow-term-markers
```

## 第 12 步：JSON 提取

调用 `daggerheart-json-formatter` 技能，扫描 `source/_translated.md`，按内容类型提取为对应 JSON，输出到 `data/`。

## 结束条件

以下条件全部满足后，管线才算完成：
- `source/_translated.md` 已生成
- 术语审阅报告已生成
- `source/temp/_translated_chunks_clean/` 已生成
- 校验脚本已通过
- JSON 已提取完成
