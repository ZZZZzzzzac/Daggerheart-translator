# 人工问题导出（试用）

先由 AI 完成全文源译审校、修复明确错误，并对可判定的普通措辞/术语记录具体接受理由。只有仍无法从指定材料裁决的问题进入人工卡片。不能因为排查量大而设问题上限、隐藏剩余问题，或声称未经完成审校的“零问题”。泛指复数只是一般表述，不是同一次效果作用于多个目标的证据。

旧 `_term_review_report.*` 与 `_term_decision_queue.*` 保留审计兼容；它们不是新的用户交接格式。新的人工交接必须经过下面的独立导出命令。

## 使用

从项目的当前 chunk 与当前审计重新准备，不从旧报告拼接引文：

```bash
python <skill_root>/scripts/check_terms.py <项目目录>
python <skill_root>/scripts/export_human_review.py <项目目录> --prepare
```

`source/temp/_human_review_inputs.json` 包含当前 `input_digest`、`review_digest`、必须审阅的 `required_chunks`、全部 `unresolved_decisions` 与可复制的 `available_units`。它只是准备材料，不是已完成审校的卡片。`--prepare` 不修改译文、问题文件或批准文件。

实际完成全文审校后，按下列结构填写 `source/temp/_human_review.json`。每个 `source` / `translation` 对象从准备材料的实际单元复制，不手写、概述或猜测原文。示意里的占位对象必须替换。

```json
{
  "schema_version": "contextual-human-review-v1",
  "input_digest": "当前准备材料中的值",
  "review_digest": "同一准备材料中的值",
  "semantic_review": {
    "completed": true,
    "reviewer": "AI:实际模型或审阅者",
    "reviewed_chunks": ["按 required_chunks 完整复制，实际全部审阅后填写"],
    "summary": "实际覆盖范围、已自行修复的问题和仍未决的原因"
  },
  "questions": [
    {
      "id": "q-001",
      "kind": "translation_blocker",
      "decision_ids": ["当前未决的 d-... 或 s-... ID"],
      "source": {"完整复制": "available_units 中 source 方向的对应 TARGET 单元对象"},
      "translation": {"完整复制": "available_units 中 translation 方向的当前对应单元对象"},
      "context": [{"完整复制": "消歧所需原文上下文的定位对象"}],
      "context_complete": true,
      "context_reason": "说明已核对标题、完整能力段、相邻规则或跨 chunk 延续；为何这些上下文足够",
      "problem": "一个独立疑点，以及不同解释会改变什么",
      "options": [
        {"id": "A", "text": "具体解释 A 及其候选中文"},
        {"id": "B", "text": "具体解释 B 及其候选中文"}
      ],
      "recommendation": "A",
      "reason": "依据当前原文和上下文推荐 A；仍需用户决定的原因"
    }
  ]
}
```

随后导出：

```bash
python <skill_root>/scripts/export_human_review.py <项目目录>
# 或明确指定待验证的人工问题文件
python <skill_root>/scripts/export_human_review.py <项目目录> --review-file <问题文件.json>
```

只把成功生成的 `_human_review_cards.md` / `.json` 作为本轮交接。每张卡包含完整对应原文、当前中文、精确本地位置、必要上下文、每个疑点、具体选项、建议及理由。建议引用选项 ID；选项文本必须让用户能直接选。导出失败时不产生新的有效卡片，旧文件不能视为当前结果。

同一源文单元的两个问题使用相同的 `source` 与 `translation` 定位，脚本自动输出一张卡，原文/译文各展示一次，明确写“2 个独立问题 / 1 张卡片”。同一问题可覆盖多个审计 ID，但同一个 ID 不能在多个问题中重复出现；问题 ID、同一单元的同文疑点、重复选项也会被拒绝。脚本不以关键词判断两个不同措辞是否其实是同一个疑点，AI 必须先去重。

每个问题的 `kind` 必须是 `translation_blocker`（无法忠实交付译文的阻断）或 `optional_rule_ruling`（已能忠实保留原文含义/歧义，仅供选择的源规则裁定）。分别报告这两类数量、独立问题总数和卡片数；例如“0 个交付阻断，3 个可选源规则裁定，2 张卡片”。不能把源规则自身的未定玩法一律叫译文错误或交付阻断。Markdown 的建议同时显示选项 ID 和完整选项文本。

## 定位与原文保真

每个定位对象恰有六个字段：

```json
{
  "side": "source",
  "chunk": "01_synthetic",
  "section": "TARGET",
  "start_line": 1,
  "end_line": 3,
  "text": "# Synthetic Lantern\n\nA visitor carries a token."
}
```

上例是自造文字，只展示格式，不是项目原文。`side` 为 `source` 或 `translation`；`section` 为 `TARGET`、`CONTEXT_PREV` 或 `CONTEXT_NEXT`；行号从相应 KILO 区段内部的第 1 行开始，为闭区间。输出同时写明实际 `_chunks/<chunk>.md` 或 `_translated_chunks/<chunk>.md` 文件，绝不猜测页码、书名或章节。

`source` 和 `translation` 必须是同一 chunk 的完整 TARGET 单元：从 Markdown `#` 标题开始，保留后面所有段落，直到下一个同级/更高级标题前；没有 `#` 标题时保留整个 TARGET。标题前的正文保留整个前导区段。脚本宁可多给上下文，不允许随手截半句、截半个多段能力。需要更细粒度时先在格式整理步骤正确设置原文/译文标题，再重新审校，不能改写引文以通过验证。

`context` 必须非空且至少包含一个真实原文引用。单元已经自足时可引用同一个完整 `source` 对象，导出会注明上下文已在上方而不再重复引文。父标题、前置规则、跨 chunk 的能力延续等另加实际定位。不要仅依赖 splitter 可能截断的 PREV/NEXT 摘录；有延续时去相邻 chunk 的 TARGET 取得完整段落并核对。`context_complete` / `context_reason` 是审阅者声明，程序不可能证明所有语义依赖都已包含。

`text` 必须等于当前真实文件指定行经以下唯一显示变换后的结果：
1. UTF-8 解码，将 CRLF 换成 LF。
2. 每个合法术语标记替换成第一槽，沿用共享解析器对第一槽首尾空白的去除；不显示推荐槽与注释槽。正文其余空白不变。
3. 若整个摘录以 LF 结束，仅去除这一个末尾 LF。

不折叠段落、不修正文法、不把模型释义放进“原文”。正文中多/少一个空格、修改中文、替换原文，都会导致验证失败。审核项自己的源/译上下文还必须能在选中的单元中找到，防止用同一 chunk 的另一能力冒充对应原文。这个匹配仅兼容旧审计的空白折叠；最终显示的引文仍由真实文件精确验证。

## 完整性和批准边界

- `input_digest` 绑定全部源/译 chunk 原始字节，`review_digest` 还绑定当前决策与语义问题。改文件、问题或规则后必须重新审阅，不能只替换哈希。
- 全部当前未决审计 ID 必须恰好被覆盖。普通措辞应先由 AI 裁决并记录接受理由；真正未决语义问题先登记到 `_term_semantic_issues.json`，再生成准备材料。不得删问题凑零。
- 全文声明必须覆盖当前全部 chunk；未完成就停止交接，如实说明缺口。空问题数组只有在没有任何未决 ID 且声明全量完成时才可导出，并仍明确标为审阅者声明。
- 导出不修改任何审批，不授予用户放行。现有逐项理由、全文语义声明、明确用户确认和手动清标记门禁全部保留。
- `kind` 只影响人工交接分类，不改变旧门禁：登记在语义审计中的可选规则项仍是一个未接受的审计 ID，直到按现有流程明确接受现有忠实译法并记录依据，或按用户选择修改并重审。接受忠实保留歧义的译法不等于代用户裁定玩法。
- 写出前再次重建报告，重新检查输入/审阅哈希及未决状态；严格问题文件拒绝重复 JSON 字段。生成文件采用临时文件加原子替换，已有输出是符号链接或硬链接时也不会沿链接改写输入。
- 哈希、字段检查、完整覆盖和重复检查都不是语义正确率、上下文充分性、人工身份或真实独立问题数的证明。

## 回归测试

```bash
python -m unittest discover -s tests -p 'test_human_review_export.py' -v
python -m unittest discover -s tests -v
```

新测试只用自造段落，覆盖 2 问题/1 卡片、0 阻断/3 可选问题/2 卡片、完整多段单元、伪造引文、过期输入/审阅、导出中途审阅变动、缺字段、遗漏/重复问题、重复 JSON 字段、完整审校声明、链接输出保护、CLI 失败不导出与 137 个问题不截断。它们验证软件契约，不评估翻译质量。
