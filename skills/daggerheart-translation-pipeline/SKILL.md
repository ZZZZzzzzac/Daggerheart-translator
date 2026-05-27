---
name: daggerheart-translation-pipeline
description: End-to-end pipeline: English PDF → Chinese MD → structured JSON. Covers marker/PaddleOCR, glossary extraction, term replacement, chunked parallel translation, makeup, and JSON formatting.
---

# Daggerheart Translation Pipeline

英文 Daggerheart PDF/DOCX 输入，中文 Markdown + 结构化 JSON 输出。

## 依赖技能

| 技能 | 角色 |
|------|------|
| `daggerheart-md-converter` | PDF/DOCX → MD（marker / PaddleOCR） |
| `daggerheart-glossary-extractor` | 提取文档术语表 |
| `daggerheart-chinese-writing` | 写作规范（术语/格式/禁止用法），作为 subagent 提示词 |
| `daggerheart-json-formatter` | 译文 MD → 结构化 JSON |

## 文件路径

### 技能内部路径
`scripts/` 和 `resources/` 相对于本 skill 根目录。所有脚本通过 `__file__` 解析路径，不依赖外部目录结构。

### 项目路径
路径相对于**用户翻译项目的根目录**（如 `project/example/`）。项目目录结构见 `project/example/`：

```
project/<项目名>/
├── source/           # 原始文件（_original.md） + 最终译文（_translated.md）
│   └── temp/         # 临时产物（_tagged.md, _merged_terms*.json, _chunks/, _translated_chunks/）
├── project_scripts/  # 本项目专有的脚本（与 skill 的 scripts/ 区分）
├── data/             # 结构化 JSON 输出
└── glossary/         # 项目术语表（_glossary.json）
```

管线所有命令在项目目录下执行。

### 命令中的混合路径
下文各步骤的命令同时引用两类路径：`scripts/` 和 `resources/` 指向 skill 目录，`source/`、`source/temp/`、`glossary/` 指向项目目录。AI 执行时需将前缀不同的参数分别解析到正确的绝对路径。

## 管线

```
前置. 确认运行模式（手动 / 全自动）
0. 初始化项目结构（脚本 + 手动检查）
1. PDF/DOCX → MD（daggerheart-md-converter，含 AI 格式修复）
2. 提取文档术语表
3. 内联术语替换
4. 分块
5. 翻译（首 chunk 确认 → 并行）
6. 合并
7. makeup
8. 自动化检查 + AI 修正
9. JSON 提取
```

## 全自动模式

用户可手动开启全自动模式。此模式下总 skill 代替用户审查：
- 术语表合并若出现冲突，按默认优先级自动裁决：`terms-14448.json` > `adversaries_*.json` > `glossary/_glossary.json`
- 翻译 01 chunk 后自动对比原文检查术语和格式，无需用户确认
- 并行翻译、合并、makeup、检查、JSON 提取全自动执行
- 仅在最终报告结果

开启方式：用户明确说明"全自动模式"或"auto mode"。默认关闭。
**除非用户明确开启了全自动模式，否则每个需要用户确认的节点都必须停下来等待。**

---

## 前置步骤：确认运行模式

**在执行任何管线步骤之前，必须先用 question 工具向用户确认运行模式。**

提问：
- 标题：`运行模式`
- 选项 A：`手动模式（推荐）` — 每个确认节点暂停，等待用户审查后再继续
- 选项 B：`全自动模式` — 术语冲突自动裁决，翻译无需确认，最终只报告结果

用户选择「全自动模式」后，后续所有需用户确认的节点（术语冲突处理、chunk 01 审查、并行翻译确认等）均自动跳过，直接执行并仅在最终报告。

用户选择「手动模式」后，按默认流程：术语冲突暂停、chunk 01 翻译后展示对比并等待确认、并行翻译前再次确认。

**此提问必须在第 0 步之前完成，不得跳过。**

---

## 第 0 步：初始化项目结构

在开始翻译前，先确保项目目录结构符合标准布局。

```bash
python scripts/setup_project.py <项目目录>
```

脚本行为：
- 创建缺失的子目录（`source/`、`source/temp/`、`project_scripts/`、`data/`、`glossary/`）
- 若 `_original.md` 在项目根目录，移至 `source/`
- 若 `source/` 下已有临时产物，移至 `source/temp/`（`_tagged.md`、`_merged_terms*.json`、`_chunks/`、`_translated_chunks/`）
- 若 `source/` 下已有 `_glossary.json`，移至 `glossary/`
- 幂等：再次运行不覆盖已存在的目标文件

---

## 第 1 步：源文档 → Markdown

调用 `daggerheart-md-converter` 技能。将 PDF/DOCX 转为项目 `source/_original.md`。详见该技能文档。

该技能支持两种方案：marker（本地自动化，需 Gemini API key）和 PaddleOCR-VL（网页手动上传，免费）。

---

## 第 2 步：提取文档术语表

调用 `daggerheart-glossary-extractor` 技能，扫描项目 `source/_original.md` 提取本文档特有专有名词，输出 `glossary/_glossary.json`。

详见 [daggerheart-glossary-extractor](../daggerheart-glossary-extractor/SKILL.md)

---

## 第 3 步：内联术语替换

将游戏术语表 + 文档术语表合并，对原文做内联标记。

优先级固定为：

`terms-14448.json` > `adversaries_*.json` > `glossary/_glossary.json`

原因：文档术语抽取时可能会把已有固定术语重新翻译一遍，此时必须以全局通用术语表为准。

```bash
python scripts/merge_terms.py --terms "resources/terms-14448.json" "resources/adversaries_features.json" "resources/adversaries_motivation.json" "resources/adversaries_name.json" "glossary/_glossary.json" --output "source/temp/_merged_terms.json" --original "source/_original.md"
python scripts/replace_terms.py "source/_original.md" "source/temp/_merged_terms.json" "source/temp/_tagged.md"
```

`merge_terms.py` 行为：

- 按 `--terms` 提供顺序决定优先级，越靠前优先级越高
- 若出现不同译名冲突，会写出 `source/temp/_merged_terms_conflicts.json`
- 默认模式下，发现冲突后**停止**，由用户处理冲突后再继续
- 全自动模式下，给 `merge_terms.py` 增加 `--auto-resolve`，并按上述优先级自动保留高优先级译名，同时继续输出冲突报告供最终审阅



`source/temp/_tagged.md` 中术语已被标记为 `【中文 (English) - 注释】`。

### 术语表 JSON 格式

```json
{
  "term": "The End",
  "translation": "终末",
  "note": "Pluto 称号",
  "variants": ["The-End"],
  "case_sensitive": true
}
```

- `term` / `translation` 必填。`note` / `case_sensitive` / `variants` 可选。
- `case_sensitive`: 默认不区分大小写。设为 `true` 时该条目强制区分大小写匹配，适合极短且易与其他短语混淆的术语（如 "The End"）。

---

## 第 4 步：分块

```bash
python scripts/split_chunks.py "source/temp/_tagged.md" --min-chars 4000 --target-chars 5500 --max-chars 7000 --context-chars 1200
```

按 block 感知切分：表格整体保留、大小按非空白字符数估算、在 `min/target/max` 窗口内寻找最佳边界。标题只作为弱提示，不再作为硬切点。chunk 输出到 `source/temp/_chunks/`。

每个 chunk 文件会被包装为三段：

- `[[[KILO_CONTEXT_PREV_START]]] ... [[[KILO_CONTEXT_PREV_END]]]`：上一块末尾上下文
- `[[[KILO_TARGET_START]]] ... [[[KILO_TARGET_END]]]`：当前真正需要翻译并在合并时保留的正文
- `[[[KILO_CONTEXT_NEXT_START]]] ... [[[KILO_CONTEXT_NEXT_END]]]`：下一块开头上下文

这样即使一个完整信息块被边界切开，翻译时也能看到前后文；合并时再自动只保留 `KILO_TARGET` 段。

---

## 第 5 步：翻译

### 5.0 检查快速模型

翻译无需很强的智力与思考，检查当前环境是否有快速便宜的模型可用（如 Haiku / flash / mini），并关闭/调低思考等级。如果没有，提醒用户，确认具体执行翻译的subagent使用哪一个模型。

### 5.1 翻译 01 chunk

用 `scripts/translation_prompt.py` 生成 subagent 系统提示词。脚本将完整提示词写入 `_prompt_xxx.md` 文件。

```bash
python scripts/translation_prompt.py "<chunk_file>"
```

启动翻译 subagent：
1. **用 Read 工具读取生成的 `_prompt_xxx.md` 文件**
2. **将读取到的完整内容作为 subagent 的 prompt 原样传入，不得删减、重写、或替换**
3. 禁止 AI 自己概括翻译规则——提示词的完整性由脚本保证，AI 只需要原样转发
- 模型：快速便宜模型（Haiku 级），关掉 extended thinking
- subagent 将根据提示词自行 Read 当前 chunk 文件和 REFERENCE.md，翻译后写入 `source/temp/_translated_chunks/`

chunk 文件内部已经包含前后文包装段。翻译时允许把这三段正文都译成中文，但**所有 `[[[KILO_...]]]` 标记行必须原样保留**，以便后续自动合并。

提交给用户对比01块的原文和译文。用户确认前**不进行下一步**。

### 5.2 并行翻译

用户确认后，**必须明确提示用户**："chunk 01 已确认，是否开始并行翻译剩余 N 个 chunk？"

收到用户确认后，并行启动其余 chunk 翻译。

**⚠️ 必须遵循以下流程，不得自行编写缩略版 prompt：**

1. 对每个 chunk，先用 `translation_prompt.py` 生成完整提示词（已保存在 `_prompt_xxx.md`）
2. **用 Read 工具读取对应的 `_prompt_xxx.md` 文件**
3. **将读取到的完整内容作为 subagent 的 prompt 原样传入，不得删减、重写、或替换**
4. 禁止 AI 自己概括翻译规则——提示词的完整性由脚本保证，AI 只需要原样转发

---

## 第 6 步：合并

用同一个脚本抽取并按编号顺序合并 `KILO_TARGET` 段：

```bash
python scripts/split_chunks.py "source/temp/_translated_chunks" --merge --output "source/_translated.md"
```

合并时会自动忽略前后文包装段，只保留每个 chunk 中 `[[[KILO_TARGET_START]]]` 与 `[[[KILO_TARGET_END]]]` 之间的译文正文。

---

## 第 7 步：makeup 后处理

```bash
python scripts/makeup.py "source/_translated.md" --suffix ""
```

处理：资源短语加粗、数字/骰子加粗、斜体间距、PC/GM 替换、图片链接清理。

---

## 第 8 步：自动化检查 + AI 修正循环

```bash
python scripts/validate_translation.py "source/_translated.md"
```

脚本输出每个错误的行号、错误描述、前后上下文。

当前策略：

- 只检查已经在真实翻译中出现过、且能稳定判断的问题
- KILO 包装 chunk 优先检查 KILO 结构完整性与 `KILO_TARGET` 正文
- 图片链接/表格结构/标题数量等对照检查，**先不预加**；遇到真实问题再补规则

如果检查不通过：
1. 将脚本输出给 AI，AI 直接修改 `source/_translated.md` 修正
2. 重新运行检查脚本
3. 重复直到检查通过

常见错误可直接用正则替换批量修正（如 `生命值` → `生命点`），不规则错误由 AI 逐行修正。

### 后续计划（暂不实现）

后续如需把自动修正做得更稳，计划改为双环：

- chunk 内环：`translator -> validator -> reviewer -> fixer -> validator`
- 全文外环：合并后只做跨 chunk 一致性检查，再把问题路由回具体 chunk 修复

原因：主修复循环放在单个 chunk 上更容易收敛，也不容易被整篇长文稀释上下文；全文只负责查跨 chunk 术语与风格一致性。

这部分属于结构升级，当前先不实现，等真实痛点出现后再推进。

---

## 第 9 步：JSON 提取

调用 `daggerheart-json-formatter` 技能。自动扫描译文 MD，识别内容类型（敌人/环境/领域卡/职业等），提取为对应 JSON。

---

## 环境变量

API key等敏感信息储存在`.env`中。
