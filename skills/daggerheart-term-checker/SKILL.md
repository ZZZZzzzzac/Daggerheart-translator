---
name: daggerheart-term-checker
description: Build a per-occurrence term review report from tagged source chunks and translated chunks, then strip approved term markers into a clean chunk directory for merge.
---

# Daggerheart Term Checker

对比 `_chunks/`（带术语标记的原文）与 `_translated_chunks/`（保留术语标记的译文），逐条生成术语审阅报告；审阅完成后，再批量清除术语标记，得到可合并的 clean chunk。

## 运行方式

可手动调用，也可作为 `daggerheart-translation-pipeline` 的标准步骤使用。

在翻译项目根目录下执行：

```bash
python <skill_root>/scripts/check_terms.py <项目目录>
python <skill_root>/scripts/strip_term_markers.py <项目目录>
```

示例：

```bash
python ../Daggerheart-translator/skills/daggerheart-term-checker/scripts/check_terms.py .
python ../Daggerheart-translator/skills/daggerheart-term-checker/scripts/strip_term_markers.py .
```

## 输入

- `source/temp/_chunks/` — 带 `【原文｜推荐译文｜注释】` 标记的原文 chunk
- `source/temp/_translated_chunks/` — 对应译文 chunk，术语标记格式为 `【当前译文｜推荐译文｜注释】`

两个目录必须都存在（即管线至少跑完第 6 步）。

## 检查规则

对每个 chunk 的 `KILO_TARGET` 区段：

1. 从原文 chunk 读取每个术语槽位的 `原文 / 推荐译文 / 注释`
2. 从译文 chunk 优先按 `推荐译文 + 注释` 对位读取对应 `当前译文`；只有无法精确匹配时才退回顺序兜底
3. 判断 `当前译文` 是否与 `推荐译文` 一致
4. 同时截取原文上下文与当前译文上下文，便于人工或 AI 审阅

这是逐条审阅报告，不会去重，也不会只展示“有问题”的项；同一术语在不同上下文中会各列一行。

## 输出

1. **stdout**：统计摘要。
2. **`source/temp/_term_review_report.md`**：Markdown 表格。
3. **`source/temp/_term_review_report.json`**：逐条 JSON 报告。

默认表格列：

| chunk | 原文 | 推荐译文 | 当前译文 | 是否采用推荐 | 原文上下文 | 译文上下文 | 注释 | 异常 |

- `是否采用推荐` 仅作提示，不强制要求为“是”
- 若发现标记数量不一致、标记损坏、槽位为空等结构异常，会在报告中明确列出
- 若译文只发生了相邻术语换序，但 `推荐译文 + 注释` 仍能对上，不再误报结构异常

可指定输出路径：

```bash
python check_terms.py <项目目录> --output <自定义路径.md>
```

也可指定 JSON 输出路径：

```bash
python check_terms.py <项目目录> --json-output <自定义路径.json>
```

## 清除术语标记

术语审阅通过后，执行：

```bash
python strip_term_markers.py <项目目录>
```

默认行为：

- 输入目录：`source/temp/_translated_chunks/`
- 输出目录：`source/temp/_translated_chunks_clean/`
- 将 `【当前译文｜推荐译文｜注释】` 替换为 `当前译文`
- 保留原始带标记译文 chunk，不覆盖原文件

## 注意

- 该报告的职责是把每个术语翻译决策显式列出来，供人工或 AI 逐条审阅。
- 若 `_chunks/` 或 `_translated_chunks/` 目录不存在，脚本会报错退出。
