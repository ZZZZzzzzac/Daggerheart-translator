# 已有原文与译文：配对、审阅、HTML

本入口从**已经取得的原文和译文**开始，只做文本配对、实际语义审阅、审阅记录核验和 HTML 报告。没有下载、平台、凭据或远端操作。审阅者不必提供来源版本、捕获时间或维护额外的来源记录。

`paired_audit.py` 只用 Python 标准库。规范化和校验不执行语义审阅：只有人工或 AI 真正读过完整原文、译文及相关上下文后，才能填写审阅结论。

以下命令从本 skill 目录运行；输出文件名可自行选择。JSON 输出不覆盖已有文件，以免覆盖已写好的审阅意见。

## 1. 输入已有文本

逐段 JSON 输入：

```json
{
  "title": "Installation manual · English → Chinese",
  "sourceLanguage": "en",
  "targetLanguage": "zh-Hans",
  "segments": [
    {
      "id": "cleaning-power",
      "original": "Before cleaning, disconnect the power.\n",
      "translation": "清洁后，请断开电源。\n",
      "location": "Cleaning · paragraph 1",
      "alignmentNote": "同一条清洁安全提示。"
    },
    {
      "id": "child-safety",
      "original": "Keep away from children.\n",
      "translation": "",
      "alignmentNote": "此原文段落没有对应译文。"
    }
  ]
}
```

```bash
python scripts/paired_audit.py normalize --pairs pairs.json --out input.json
```

- 顶层需要 `title` 与非空 `segments`；可选 `schemaVersion` 为 1，语言字段可省略。
- 每段需要唯一、稳定、非空的字符串 `id`，以及显式的 `original`、`translation` 字符串。不要求数字 ID。
- 未匹配内容仍要纳入：缺失的一侧写 `""`，两侧不能同时为空。不要为了配平数量而丢掉段落。
- `location` 默认使用 ID；`alignmentNote` 是配对说明，不代表已确认语义或对齐无误。
- 一对多、多对一可把对应内容合为一组。内容较长时人工组织有明确对应关系的分段，不按行号盲配。
- 可选 `context`、`provenance` 只保存已给定的上下文和定位，不要求填写。可选 `url` 为无嵌入凭据的 HTTPS 链接，`provider` 为报告链接的显示名称；没有这些字段完全正常。
- 不做 trim、Unicode 标准化、换行转换、自动补译或自动改字。

也可传入两份**已经在本地的 UTF-8 文本文件**：

```bash
python scripts/paired_audit.py normalize \
  --original-file source.txt --translation-file translation.txt \
  --id installation-manual --title 'Installation manual audit' \
  --out input.json
```

两份完整文本作为一个 `whole-document` 段，不按行自动配对，也不会因行数不同而截断。可选 `--source-language en --target-language zh-Hans`。

直接文本入口可用于短段，也可以一侧文件、一侧文本：

```bash
python scripts/paired_audit.py normalize \
  --original-text 'Keep the device dry.' --translation-text '请保持设备干燥。' \
  --id storage --title 'Storage instruction audit' --out input.json
```

没有对应译文时显式使用 `--translation-text ''`。较长或敏感文本优先使用本地文件，避免进入 shell 历史。

## 2. 建立待审记录，实际逐段审阅

```bash
python scripts/paired_audit.py prepare input.json --out review.json
```

规范化输入的顶层是 `schemaVersion: 1`、`type: "paired-audit-input"`、`title`、语言字段、`inputSha256` 与 `segments`。每段保留原译文、配对信息、可选定位及内部 `segmentSha256`。这些哈希由脚本计算，仅防止审阅意见或高亮套到不同文本上；无需用户填写来源信息。

审阅记录的顶层是 `schemaVersion: 1`、`type: "paired-audit-review"`、匹配输入的 `inputSha256`、全量 `coverage` 和 `findings`。

`prepare` 为每段生成待审记录，**不会自动宣称已对齐或审过**：

```json
{
  "id": "cleaning-power",
  "segmentSha256": "由 prepare 填入",
  "status": "unreviewed",
  "alignment": "unverified",
  "reviewer": "",
  "reviewedAt": "",
  "assessment": "",
  "conclusion": "",
  "findingIds": []
}
```

实际审阅每段时：

1. 核对配对关系，读完整原文、译文和相关上下文；空侧需确认是未匹配内容。
2. 检查意思、主体／指代、条件、顺序、范围、数量、漏译／增译、术语与自然表达。不能靠关键词命中自动判错。
3. 写具体 `assessment`，说明比较了什么、为何判断有或无问题。审过才填 `status: "reviewed"`、真实 `reviewer`、含时区的 ISO-8601 `reviewedAt`，以及 `alignment: "verified"`。
4. `conclusion` 使用 `no_issue`（无发现，`findingIds: []`）、`findings`（至少一项 `confirmed`）、`uncertain`（只有 `uncertain` 问题）。一段可有多个问题；`findingIds` 必须与实际问题一致。
5. 对齐仍无法确认时，记 `alignment: "unresolved"`、`conclusion: "uncertain"` 并记录不确定问题，不能直接算成翻译错误；它会阻止覆盖完成。

明确不在用户要求范围内的段落可以 `excluded`，但必须有 `reason`、`excludedBy`、`scopeEvidence`，说明谁或哪条范围要求排除了它。其 `alignment` 保持 `unverified`，结论为空、问题列表为空。时间不足或尚未审完应保持 `unreviewed`，不能借排除宣称完成。

## 3. 记录真实问题与精确证据

每项需要 `finding_id`、段落 `id`、对应 `segmentSha256`、`title`、`status`、`severity`、`category`、`problem`、`suggestion` 和两侧高亮数组。前文 `cleaning-power` 的问题可写：

```json
{
  "finding_id": "cleaning-order",
  "id": "cleaning-power",
  "segmentSha256": "取该段现有值",
  "title": "清洁前后顺序被颠倒",
  "status": "uncertain",
  "severity": "high",
  "category": "meaning",
  "problem": "原文要求先断电后清洁，译文却要求清洁之后断电。",
  "suggestion": "将“清洁后”改为“清洁前”。",
  "original_highlights": [
    {"start": 0, "end": 6, "text": "Before", "reason": "断电是清洁之前的先决步骤。"}
  ],
  "translation_highlights": [
    {"start": 2, "end": 3, "text": "后", "reason": "反转了原文先后顺序。"}
  ]
}
```

- `status` 只使用 `confirmed` / `uncertain`。确认问题必须有真实独立复核：`second_pass: {"reviewer":"与首审不同的标识", "decision":"support", "reason":"复核依据"}`。未复核或尚有争议时保留 `uncertain`，不能编造复核人。
- `severity` 为 `critical` / `high` / `medium` / `low`，按实际影响判断。
- `category` 为 `meaning`, `omission`, `addition`, `terminology`, `consistency`, `grammar`, `style`, `formatting`, `alignment`, `source_issue`, `other`。可选 `label` 为便于阅读的类别名称。
- 高亮使用完整原始文本上的 Unicode **码点**半开区间 `start`/`end`；不是字节或 JavaScript UTF-16 下标。`text` 必须等于该切片，`reason` 需说明证据意义，同侧按位置排序且不能重叠。重复文字必须确认实际是哪一次。
- 每项至少一侧有真实高亮。漏译可只有原文高亮，译文高亮为 `[]` 并填写 `translation_absence_reason`；增译反过来。不要把本来正确的译文硬标红来填满两侧。
- 默认展示整段。可用 `original_focus_ranges` / `translation_focus_ranges` 的 `{start,end}` 数组缩小展示上下文，但必须包含全部证据高亮。空侧可使用 `[{"start":0,"end":0}]`。脚本直接从原文本生成 focus，不重新改写摘录。
- 可选 `reference_evidence: {"text":"已提供的依据及定位", "url":"可选 HTTPS 链接"}` 保存补充依据。
- 问题中如额外保存 `original` / `translation`，必须逐字等于当前输入。

## 4. 核验、导出与查看

```bash
python scripts/paired_audit.py validate input.json review.json
python scripts/paired_audit.py export input.json review.json \
  --report-id manual-audit-v1 --out report.json
python scripts/render_report.py report.json report.html
```

`validate` 退出码：`0` 为结构有效且范围内覆盖完成；`1` 为结构有效但还有待审、未解决对齐或没有实际审过任何范围内内容；`2` 为输入、记录或证据有误。校验通过不代表机器证明了语义判断正确。

`export` 默认拒绝未完成覆盖；需要中途交付时显式加 `--allow-incomplete`。报告显示待审 ID、未解决对齐和排除理由。`coverageSummary.completeReview` 指范围内审完，`allInputReviewed` 才表示全部输入都已审过且无排除。

零发现不生成假问题卡片：完整审阅说明范围内未发现问题；不完整审阅说明目前无记录，不能当作干净审计。`reportId` 用于 HTML 本地审阅进度，同一报告保持稳定。

若修改了原文、译文或配对，应审阅当前文本后更新记录。内部哈希会阻止把旧证据套到不同输入上，不能只改哈希绕过审阅。

## 可运行的合成示例

示例为虚构消费设备说明书；已有 `consumer-review.json` 保存了真实句义比较和独立复核，不是用户数据。原文译文已经放在 `examples/consumer-pairs.json`：

```bash
mkdir -p /tmp/paired-audit-example
python scripts/paired_audit.py normalize --pairs examples/consumer-pairs.json \
  --out /tmp/paired-audit-example/input.json
# 新材料先 prepare，再实际审阅；本例直接使用已审过的示例记录。
python scripts/paired_audit.py validate /tmp/paired-audit-example/input.json examples/consumer-review.json
python scripts/paired_audit.py export /tmp/paired-audit-example/input.json examples/consumer-review.json \
  --report-id consumer-synthetic-example --out /tmp/paired-audit-example/report.json
python scripts/render_report.py /tmp/paired-audit-example/report.json /tmp/paired-audit-example/report.html
```

也可用 `consumer-original.txt` / `consumer-translation.txt` 验证本地文件入口；它们会形成一个整文段，不能套用四段 JSON 的审阅记录。新材料从自己的待审记录开始，不能复制示例结论或复核意见冒充审过。
