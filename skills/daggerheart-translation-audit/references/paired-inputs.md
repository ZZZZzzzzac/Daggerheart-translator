# 通用原文／译文输入与真实审阅记录

这条入口只需要原文和译文，不需要 ParaTranz、项目编号、数字 ID、在线链接或凭据。`paired_audit.py` 使用 Python 标准库，不访问网络，不调用翻译服务，也不会自动作出语义判断。

**脚本负责保存、核验与导出；审阅者负责真正逐段读懂原文和译文。** `normalize`、`prepare`、关键词搜索和成功生成 HTML 都不能代替语义审阅。`validate` 能发现错配的记录、旧哈希和错误高亮，不能证明审稿人的判断一定正确。

以下命令从本 skill 目录运行，所有输出写到自己的审阅项目目录。脚本不覆盖已有 JSON 文件；重新捕获请换版本文件名，保留旧证据。

## 1. 选择输入方式并确认边界

### 结构化配对 JSON：推荐用于逐段审阅

```json
{
  "schemaVersion": 1,
  "title": "User manual · English → Chinese",
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
      "id": "unmatched-source",
      "original": "Keep away from children.\n",
      "translation": "",
      "location": "Cleaning · paragraph 2",
      "alignmentNote": "源段落存在，译文中没有对应段落。"
    }
  ]
}
```

```bash
python scripts/paired_audit.py normalize --pairs /path/to/pairs.json --out /path/to/snapshot.json
```

- 顶层 `title` 和非空 `segments` 数组必填；`schemaVersion` 默认为 1；语言字段可省略。
- 每段必须有稳定、非空、唯一的字符串 `id`。可用用户已有的章节键／条目键；不要求数字，也不要因改字而改变 ID。
- `original` 与 `translation` 必须都显式存在且为字符串。没有对应内容的一侧写 `""`，两侧不能同时为空。切勿丢掉未匹配的段落。
- `location` 可省略，默认使用 ID；建议填写章节、页码、段落或其他可读定位。
- `alignmentNote` 描述为什么配成一组。它是配对说明，不是已经验证语义正确的声明。
- 可选 `context` 是帮助理解的邻接／章节说明；可选 `provenance` 对象可记录文件名、页码、提取工具、来源版本等。不要把与审阅无关的数据或密钥放进去。
- 可选 `url` 必须是无嵌入凭据的 HTTPS 链接；可选 `provider` 是报告上的来源按钮名称。没有链接完全正常。
- 一对多、多对一应把对应文本作为一组保存，或人工建立不会漏段的多组配对。不得为了数量相同而按行盲配。
- 输入中的文本会逐字保留，不做 trim、换行转换、Unicode 标准化或自动补译。
- PDF、DOCX、网页等先用相应工具提取可核对的文本，再组织配对；本脚本不会把二进制文档当作文本转换。核对提取是否完整，并保留页码、章节和提取依据。

### 两个 UTF-8 文本文件：整份文档先作为一对

```bash
python scripts/paired_audit.py normalize \
  --original-file /path/to/source.txt \
  --translation-file /path/to/translation.txt \
  --id installation-manual \
  --title 'Installation manual audit' \
  --source-language en --target-language zh-Hans \
  --out /path/to/snapshot.json
```

不会按行或空行自动对齐：两份完整文件作为一个 `whole-document` 段。文件长度、段数不同也不会静默截断；审阅者需核对全文是否对应。如果全文太长，先建立结构化配对 JSON，显式纳入所有原文和译文内容。

也可直接传入文本，或一侧用文件、一侧用文本：

```bash
python scripts/paired_audit.py normalize \
  --original-text 'Keep the device dry.' \
  --translation-text '请保持设备干燥。' \
  --id storage --title 'Storage instruction audit' \
  --out /path/to/snapshot.json
```

缺失一侧时要显式传入空字符串，例如 `--translation-text ''`，不能省掉该参数。较长或敏感文本优先使用本地文件，避免进入 shell 历史。

## 2. 产生待审账本，然后实际审阅

```bash
python scripts/paired_audit.py prepare /path/to/snapshot.json --out /path/to/review.json
```

Snapshot 顶层为：

- `schemaVersion: 1`, `type: "paired-audit-snapshot"`
- `capturedAt`, `title`, `sourceLanguage`, `targetLanguage`
- `inputSources`: 输入原始字节的 SHA-256、类型与文件／文本标签
- `segmentsSha256`: 顺序敏感的整批段落摘要
- `segments`: 完整原文和译文、定位、配对方法、可选来源信息、两侧文本 SHA-256 与 `segmentSha256`

Review 顶层为：

- `schemaVersion: 1`, `type: "paired-audit-review"`
- `snapshotSha256`: 对应 snapshot 的 `segmentsSha256`
- `coverage`: **每个输入 ID 都有一条**的审阅账本
- `findings`: 真正发现的问题；没有发现时是空数组 `[]`

`prepare` 的每条账本都从下面的状态开始，绝不自动标为完成：

```json
{
  "id": "cleaning-power",
  "segmentSha256": "复制自 snapshot 的该段哈希",
  "status": "unreviewed",
  "alignment": "unverified",
  "reviewer": "",
  "reviewedAt": "",
  "assessment": "",
  "conclusion": "",
  "findingIds": []
}
```

实际人工或 AI 审阅时，对每一段：

1. 核对定位与对应关系，读完整原文、完整译文及必要上下文。对缺失一侧确认它确实未匹配，而不是输入漏抓。
2. 检查意思、主体／指代、条件、顺序、范围、数量、漏译／增译、术语与自然表达。领域专有规则按需要查证，不能把领域假设强加到所有文本上。
3. 写具体 `assessment`，说明比较了哪些内容、为什么判定有／无问题。不应复制一句通用“已检查”批量盖章。
4. 审过才填 `status: "reviewed"`、真实 `reviewer` 标识、含时区的 ISO-8601 `reviewedAt`，以及 `alignment: "verified"`。
5. `conclusion` 使用：
   - `no_issue`：本段没发现问题，`findingIds: []`。
   - `findings`：至少一项独立复核支持的 `confirmed` 问题，可另含 `uncertain`。
   - `uncertain`：目前只有 `uncertain` 问题，不能声称已确认错误。
6. 对齐关系还不能确认时，用 `alignment: "unresolved"`、`conclusion: "uncertain"`，并建立描述不确定之处的 `uncertain` 发现。它仍会阻止“覆盖完成”。不要把错配自动算成翻译错误。

确实不在用户授权范围内的段落可记 `status: "excluded"`，但必须有 `reason`、`excludedBy` 与 `scopeEvidence`，明确是谁／哪条范围要求排除了它。`alignment` 保持 `unverified`，`conclusion` 为空，`findingIds` 为空。排除不等于审过；报告列出排除数量。至少审过一个范围内段落后，无待审或未解决对齐，才可宣布范围内覆盖完成。没有权限或时间不够应保留待审，不能借排除绕过。

## 3. 记录问题、原文证据和独立复核

每条 finding 的必要字段：

```json
{
  "finding_id": "cleaning-order",
  "id": "cleaning-power",
  "segmentSha256": "复制自 snapshot 的该段哈希",
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
    {"start": 2, "end": 3, "text": "后", "reason": "把原文的先后顺序反转了。"}
  ]
}
```

以上偏移只对应本页开头的示例文本，换文本后必须重新定位。

- `finding_id` 是唯一稳定的问题标识；一段可有多个问题。
- `status` 仅用 `confirmed` / `uncertain`。`confirmed` 必须有真实独立复核：`second_pass: {"reviewer":"与首审不同的标识", "decision":"support", "reason":"复核依据"}`。未做复核、复核不支持或争议未解时保留 `uncertain`，不能编造第二审稿人。
- `severity` 使用 `critical` / `high` / `medium` / `low`；按实际后果判断，不因某类词命中就自动升级。
- `category` 使用 `meaning`, `omission`, `addition`, `terminology`, `consistency`, `grammar`, `style`, `formatting`, `alignment`, `source_issue`, `other`。可用 `label` 提供更友好的显示名称。
- 每项至少有一侧的真实证据高亮。`start`/`end` 为完整未改动文本上的 Unicode 码点半开区间，`text` 必须与切片完全相等，`reason` 说明这处证据为何相关。不是 UTF-8 字节，也不是 JavaScript UTF-16 下标。
- 同侧高亮按位置排序、不能重叠。可用 Python 的 `text.index(片段)` 辅助定位，但同文多次出现必须人工确认哪一次。
- 漏译可能只有 `original_highlights`；即使译文整段非空，也不要给本来正确的中文强造错误高亮。另一侧写空数组并提供 `translation_absence_reason`。增译反过来使用 `original_absence_reason`。空侧永远不能产生非空高亮。
- 展示上下文默认保留整段；需要聚焦时可加 `original_focus_ranges` / `translation_focus_ranges`，各为 `{start,end}` 数组，必须包含本侧所有证据高亮。脚本从原文重建 focus 和 segments，不用人为重打截取文本。空侧可用 `[ {"start":0,"end":0} ]`。
- `reference_evidence: {"text":"查证内容与定位", "url":"可选 HTTPS 链接"}` 可补本地文档或网络资料依据，不强迫在线 URL。独立复核说明和查证依据会随报告导出。
- 若在 finding 里额外保存 `original` / `translation`，它们必须逐字等于快照，否则拒绝导出。

## 4. 校验并导出 HTML

```bash
python scripts/paired_audit.py validate /path/to/snapshot.json /path/to/review.json
python scripts/paired_audit.py export /path/to/snapshot.json /path/to/review.json \
  --report-id manual-audit-v1 --out /path/to/report.json
python scripts/render_report.py /path/to/report.json /path/to/report.html
```

- `validate` 退出码 `0`：结构有效，范围内覆盖完成；`1`：结构有效但仍有待审、未解决对齐，或没有任何范围内段落实际审过；`2`：数据、哈希、对齐账本、证据或参数有误。
- `export` 默认拒绝不完整覆盖。确实要交付中途结果时，显式加 `--allow-incomplete`；HTML 的 `notes`、`coverageSummary` 和零发现提示都会标明尚不完整。
- `coverageSummary.completeReview` 表示范围内覆盖完成；`allInputReviewed` 才表示没有排除、全部输入都已实际审过并确认对齐。覆盖不能扩展为对未提供的文件的承诺。
- 输出使用 renderer 的 `schemaVersion: 1`、稳定 `reportId`、`title`、`sourceCutoff` 和 `findings`；来源按钮是可选项。
- 零发现是正常结果，不造“没有错误”假条目。完整审阅时说明“范围内审过但未发现问题”；不完整时说明“目前没有记录，不能视作干净审计”。
- 稳定 `reportId` 供 HTML 本地进度保存使用；换一轮独立审计时请给新 ID，避免混淆操作记录与语义覆盖。

## 5. 文本变更后重新核对

```bash
python scripts/paired_audit.py diff /path/to/old-snapshot.json /path/to/new-snapshot.json \
  --out /path/to/delta.json
```

会列出新增、删除、字段变更及顺序变动；没有任何自动“已修复”结论。旧 review 与新 snapshot 的哈希不同，必须显式核对变更和相关上下文后生成新账本；不要只替换哈希来绕过复审。变更后的字面差异、译文更短或某个词消失，都不是修复验证。

## 可直接运行的完整合成示例

可直接打开 [consumer-report.html](../examples/consumer-report.html) 查看最终离线样例。

`examples/consumer-pairs.json` 与 `examples/consumer-review.json` 是虚构消费设备说明书，包含：顺序倒置、漏译一句、无问题的一句、显式未匹配的增译承诺。它们不是任何真实用户审计的数据。

```bash
mkdir -p /tmp/paired-audit-example
python scripts/paired_audit.py normalize --pairs examples/consumer-pairs.json \
  --out /tmp/paired-audit-example/snapshot.json
python scripts/paired_audit.py validate /tmp/paired-audit-example/snapshot.json examples/consumer-review.json
python scripts/paired_audit.py export /tmp/paired-audit-example/snapshot.json examples/consumer-review.json \
  --report-id consumer-synthetic-example --out /tmp/paired-audit-example/report.json
python scripts/render_report.py /tmp/paired-audit-example/report.json /tmp/paired-audit-example/report.html
```

示例 review 是已实际比较句义的教学记录。你的新材料必须从自己的待审账本开始，不能复制示例的结论、审稿人或独立复核来冒充审过。`consumer-original.txt` / `consumer-translation.txt` 也可用于验证整文文件入口；它们会产生一个整文段，因此不能直接套用四段 JSON 示例的 review。
