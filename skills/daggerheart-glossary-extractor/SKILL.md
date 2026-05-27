---
name: daggerheart-glossary-extractor
description: Extract document-specific glossary from Daggerheart project original text. Scans source/_original.md for proper nouns and recurring unique concepts, outputs glossary/_glossary.json with shortest-root terms and variants. Use during daggerheart-translation-pipeline step 2, or when user says "提取术语表" or "run step 2".
---

# Daggerheart Glossary Extractor

用 LLM 扫描项目 `source/_original.md` 全文，提取文档特有的专有名词并翻译，按最短有效词根输出含中文翻译的术语表 JSON。

## 用法

用户提供项目路径，从中读取 `source/_original.md`，写入 `glossary/_glossary.json`。



## 提取范围

- 人名、地名、组织/派系名、种族名、生物名、物品名
- 世界观设定中反复出现的独特概念
- 游戏机制：职业(class)/子职(subclass)/种族(Ancestry)/社群(community)/领域(domain)/卡牌(card)/特性(feature)名等
- 文档中反复出现（≥2 次）的专有名词
- 以及其他理论上会反复使用, 需要保持翻译一致性的术语

## 不提取

- 泛型名词（sword、potion、castle）
- 只出现一次的描述性词语

## 翻译要求

翻译时确定术语的类型，世设中的名词可以文学化发挥，游戏机制术语则需要准确无歧义。完成后确保没有未翻译的`"translation": ""`。

## 粒度原则：最短有效词根

术语替换用 `\bterm\b` 正则匹配，**不会自动处理复数/屈折变化**。优先缩小术语粒度而非提取精确多词词组：

| ❌ 不要 | ✅ 要 | 原因 |
|---------|------|------|
| `Engram Card` | `Engram` | 自然匹配 Engram / Engram Cards |
| `Transhuman - Synapse` | `Transhuman` 和 `Synapse` 分开 | 连在一起无法匹配各自单词 |
| `Power` | `Power Trait` | `Power`太泛，会大量污染原文 |


## 输出格式

```json
[
  {"term": "Terra", "translation": "泰拉"},
  {"term": "ancestries", "translation": "种族", "variants": ["Ancestry", "Ancestries", "ancestry"]},
  {"term": "The End", "translation": "终末", "note": "Pluto 称号", "case_sensitive": true}
]
```

- `note` 仅在术语有歧义、是常用词的特殊含义、或需要额外上下文时填写。
- `variants`: 可选数组。用于列出**需要映射到同一译名**的英文变体，替换时会与 `term` 一起生效，并共用同一条目的 `translation`、`note`、`case_sensitive`。
- `variants` 主要用于 `\bterm\b` 无法自然覆盖的不规则形式，例如复数、连字符差异、常见别写法。不要把它当成随意堆同义短语的字段。
- 优先遵守“最短有效词根”原则。若主词根已能自然匹配多数场景，就不要额外塞 `variants`；只有确实匹配不到时才补。
- `case_sensitive`: 默认不开启（术语替换时不区分大小写）。设为 `true` 时该条目强制区分大小写。以下情况**必须**设为 `true`：
  - 术语本身是常用英文短语，极易污染普通文本（如 `"The End"`、`"Charge"`、`"Broken"`）
  - 术语是 3 字母及以下的短词且译文与字面含义差异大
  - 术语在原文中是大写才有专名含义

## 输出路径

写入 `{用户提供的项目路径}/glossary/_glossary.json`。

## 报告

提取完成后报告：
- 提取了多少条术语
- 哪些多词术语因粒度原则被合并/精简
- 如果有基于经验的重要译名建议，列出来供用户确认
