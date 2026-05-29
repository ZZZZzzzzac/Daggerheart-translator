---
name: daggerheart-term-checker
description: Check whether tagged terms were correctly adopted in the translated output. Compares _chunks/ (term-tagged) against _translated_chunks/ (translated) chunk by chunk, prints a summary to stdout, and writes a full Markdown report. Manual invocation only.
---

# Daggerheart Term Checker

检查术语表中的推荐译法在翻译结果中是否被正确使用。按 chunk 逐一对比 `_chunks/`（带 `【】` 标记的原文）与 `_translated_chunks/`（译文），找出英文残留和未采用推荐译法的情况。

## 运行方式

**仅限手动调用，不会被管线自动触发。**

在翻译项目根目录下执行：

```bash
python <skill_root>/scripts/check_terms.py <项目目录>
```

示例：

```bash
python ../Daggerheart-translator/skills/daggerheart-term-checker/scripts/check_terms.py .
```

## 输入

- `source/temp/_chunks/` — 带 `【译文 (原文) — 注释】` 标记的原文 chunk
- `source/temp/_translated_chunks/` — 对应译文 chunk

两个目录必须都存在（即管线至少跑完第 6 步）。

## 检查规则

对每个 chunk 的 `KILO_TARGET` 区段：

1. **英文残留**：术语的英文原文仍出现在译文中 → 漏翻
2. **未使用推荐译法**：推荐的中文译法在译文中找不到 → 可能被替换为其他词

只报告有问题的情况，检查通过的术语不展示。

## 输出

1. **stdout**：统计摘要 + 按 chunk 分列的完整表格。
2. **`source/temp/_term_check_report.md`**：去重合并后的 Markdown 表格，含四列：

| 原文 | 推荐译法 | 当前译法 | 问题 |

- **当前译法**：从译文对应位置截取的上下文片段，帮助定位实际使用的措辞。
- 跨 chunk 重复的偏差合并为一行，取首次出现的上下文片段。

可指定输出路径：

```bash
python check_terms.py <项目目录> --output <自定义路径.md>
```

## 注意

- 该检查只能发现"推荐译法未出现"，无法判断替换后的译法是否正确。用户需自行审核每一条。
- 若 `_chunks/` 或 `_translated_chunks/` 目录不存在，脚本会报错退出。
