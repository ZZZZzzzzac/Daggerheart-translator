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

`terms-14448.json` > `adversaries_*.json` > `glossary/_glossary.json`

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
python scripts/merge_terms.py --terms "resources/terms-14448.json" "resources/adversaries_features.json" "resources/adversaries_motivation.json" "resources/adversaries_name.json" "glossary/_glossary.json" --output "source/temp/_merged_terms.json" --original "source/_original.md"
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

## 第 7 步：术语审阅报告

调用 `daggerheart-term-checker` 技能，扫描 `_chunks/` 与 `_translated_chunks/`，按术语出现位置生成逐条审阅报告。

```bash
python <term_checker_skill_root>/scripts/check_terms.py <项目目录>
```

- 默认输出：
  - `source/temp/_term_review_report.md`
  - `source/temp/_term_review_report.json`
- 报告逐条列出：`chunk`、`原文`、`推荐译文`、`当前译文`、`是否采用推荐`、`原文上下文`、`译文上下文`、`注释`、`异常`
- `是否采用推荐` 仅是提示，不是硬规则；允许根据上下文保留非推荐译法
- checker 优先按 `推荐译文 + 注释` 对位，不再把局部术语换序误判成结构损坏
- 若发现标记数量不一致、标记损坏、推荐译文槽位被改坏等结构异常，必须先修复再继续

手动模式：
- 向用户展示术语审阅报告
- 用户人工审阅每条术语后，直接修改 `source/temp/_translated_chunks/` 中各标记的第一槽 `当前译文`
- 用户确认审阅通过前，不得进入下一步

全自动模式：
- AI 必须通读术语审阅报告，结合上下文与注释，自动决定每条术语是否采用推荐译文
- 若需修正，直接修改 `source/temp/_translated_chunks/` 中各标记的第一槽 `当前译文`
- 修改后重新生成一次术语审阅报告，确认结构异常已消失，并将最终报告作为继续执行依据

## 第 8 步：清除术语标记

在术语审阅完成后，批量移除所有术语标记，只保留每个标记第一槽中的最终中文译文。

```bash
python <term_checker_skill_root>/scripts/strip_term_markers.py <项目目录>
```

- 输入：`source/temp/_translated_chunks/`
- 输出：`source/temp/_translated_chunks_clean/`
- 非破坏性：保留原始带标记译文 chunk，合并阶段只使用清理后的目录

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
