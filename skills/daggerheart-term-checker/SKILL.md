---
name: daggerheart-term-checker
description: Preserve a complete term audit, build a compact contextual decision queue, and gate manual marker stripping on content-bound review and explicit release.
---

# Daggerheart Term Checker

在翻译项目根目录执行。输入仍是 `source/temp/_chunks/` 与 `_translated_chunks/`；只读输入，报告与清标记产物另存。

## 1. 生成审计与决策队列

```bash
python <skill_root>/scripts/check_terms.py <项目目录>
```

输出：
- `_term_review_report.md` / `.json`：保留每个出现位置及原九列表格，JSON 新增稳定 occurrence ID、审阅分类和完整决策记录。
- `_term_decision_queue.md` / `.json`：AI 内部排查队列，保留旧格式兼容，不直接作为新的人工交接。Markdown 只展示未接受的项，JSON 保留已接受项；所有待决策项完整列出，不截断。

上下文使用完整句/行，术语标记显示为第一槽文本。同一原词、推荐、当前译法、注释及中英完整句完全相同时才合并；位置 ID 仍全部保留。结构异常和不确定对位不合并。ID 不依赖项目绝对路径或生成时间；所在 chunk/上下文/内容改变可改变 occurrence ID。相同决策 ID 可保留，但批准仍绑定整个输入哈希，不能跨版本挪用。

分类说明：
- `baseline_match`：词面符合一个推荐选项，默认不挤占队列。不是正确翻译认证，仍可能是人名误套职业名、普通词误套机制名，或主体/规则错误。
- `string_difference`：不等于错误，可能是正确的语境例外。
- `alignment_unknown`：同一元数据键在源译文中的数量不一致，不能判断缺失/新增的是哪个重复位置。正常的语境变体（如 Thresholds→伤害阈值、threshold→级）本身不构成对位失败。
- `structural` / `unknown`：必须检查。缺 chunk、包装重复、损坏标记、空槽和元数据改写均显式报出。
- `semantic_issue`：独立全文语义 QA 留下的未决问题，可指向词面一致项或无标记文本。

对位仍优先使用推荐+注释，重复相同键按各自出现次序一一对应（不按绝对标记索引贪心就近），保留不同键之间的局部换序兼容；这不能证明复杂重排下每个位置的语义对齐。无唯一原位 ID 的旧标记存在此限制。

`--output path.md` 和 `--json-output path.json` 继续支持自定义完整审计路径；队列固定写入项目 temp 目录。结构异常退出 1；词面差异不会作为错误退出。

## 2. AI 全文审阅，人工只处理真正未决项

AI 独立对照所有源文与译文（包括采用推荐、没有标记的文字），检查含义、机制、主体、条件、数量、语气与格式。能依据源文裁决的错误直接修正第一槽/正文；修正后重新跑 checker。不能判断的问题才留给用户。

普通措辞、确定的术语和明确错误先由 AI 解决。泛指复数本身不是一次效果作用于多个目标的证据；不能据此添加多目标机制。必须阅读全文和相邻规则，不能以“低人工量”为由设任意上限、漏报问题或捏造零问题。

AI 可为确定合理的例外记录接受理由，不要编造数字置信度，不要把未读全文的“零问题”当作已审校。记录不会修改翻译，也不会放行手动流程。

可选语义问题文件 `source/temp/_term_semantic_issues.json`：

```json
{
  "input_digest": "从当前报告复制输入哈希",
  "issues": [
    {
      "chunk": "01_example",
      "problem": "尚不能裁决的问题和具体选项",
      "source_context": "源句",
      "translated_context": "译句"
    }
  ]
}
```

只存当前仍未决问题，已修复问题保留在独立 QA 审计记录中。重新运行 checker 将问题加入队列；输入改变时旧语义文件会阻断检查，必须重新审阅并刷新文件（无剩余问题时写空 issues）。不能只替换哈希而跳过实际审阅。

### 人工交接必须使用完整上下文卡片

详细字段与定位规则见 [HUMAN_REVIEW.md](HUMAN_REVIEW.md)。先生成当前真实单元，再由已完成全文审校的 AI 填写 `_human_review.json`：

```bash
python <skill_root>/scripts/export_human_review.py <项目目录> --prepare
# 按准备材料与实际审校填写 source/temp/_human_review.json
python <skill_root>/scripts/export_human_review.py <项目目录>
```

每个交给用户的问题都必须附对应完整原文/能力段及标题或必要上下文、当前中文、核实的 chunk/section 行号、疑点、至少两个具体选项、推荐选项与理由。只复制当前文件的实际引文；禁止用模型概述冒充原文。同一能力的两个问题合并成一张卡，源文和译文各出现一次，独立问题数和卡片数分别统计。

每个问题显式标注 `kind`：`translation_blocker` 是阻碍忠实译文交付的问题，`optional_rule_ruling` 是译文已可忠实保留、仅需选择玩法时才裁定的源规则问题；两类分别计数，不能把全部源规则疑点都称作交付阻断。这个分类不改动旧审批门禁，具体边界见手册。

导出验证当前输入/审阅哈希、引文及定位、完整单元、必填字段和全部未决 ID；任一缺失、伪造、过期或遗漏就失败，不降级成无上下文的问题。没有问题上限或静默截断。全文审阅与上下文充分性仍是审阅者实际核对后的声明，脚本不认证语义正确或人的身份，也不会自动批准或放行。

## 3. 记录接受与放行

从实际读过的队列复制 `review_digest`。一次可接受一个或多个 ID，也可分次记录；必须写实际审阅者和理由。

```bash
python <skill_root>/scripts/approve_term_review.py <项目目录> \
  --review-digest <审阅哈希> --reviewer AI:model \
  --approve <决策ID> --reason '此句 clear 的对象是 HP，恢复符合资源用法'
```

AI 审阅大量决策时优先一次批量导入逐项理由，避免每个 ID 重建报告：

```json
{
  "review_digest": "当前实际审阅过的队列审阅哈希",
  "input_digest": "同一报告中的输入哈希",
  "decisions": [
    {"id": "d-实际决策ID", "reason": "该项具体上下文依据"},
    {"id": "d-另一个决策ID", "reason": "另一项具体上下文依据"}
  ]
}
```

```bash
python <skill_root>/scripts/approve_term_review.py <项目目录> \
  --reviewer AI:model --batch <逐项审阅结果.json>
```

批量文件必须仅包含上述三个字段，每项仅包含 `id`、`reason`。脚本重建报告一次，全部验证后原子写入：过期/缺失哈希、未知 ID、重复 ID（含相同理由的重复）、空理由、与已记录理由冲突都会拒绝整个批次，已有文件不变。相同理由的重导入保留原审阅者。批量接受可以是部分决策，不是 `--approve-all`；不能与单项接受、全文声明或 `--release` 混用，也不隐含这些授权。全文声明和用户放行仍分别执行。

对当前输入完成全文语义 QA 后记录声明；这不是脚本自行验证语义正确：

```bash
python <skill_root>/scripts/approve_term_review.py <项目目录> \
  --review-digest <审阅哈希> --reviewer AI:model \
  --accept-baseline --semantic-reviewed
python <skill_root>/scripts/check_terms.py <项目目录>
```

未决数量完整保留。需要用户选择的项，取得选择后修改译文（重新审阅生成新哈希），或在确实接受现有译法时记录该 ID 和理由。`--approve-all --reason '具体共同依据'` 仅适用于已实际审阅并明确接受整个当前队列的情形，不是跳过审阅的捷径。

手动模式下，全部决策已接受、全文语义审阅已声明，并且用户明确确认继续后，才记录放行：

```bash
python <skill_root>/scripts/approve_term_review.py <项目目录> \
  --review-digest <审阅哈希> --reviewer human:<确认者> --release
python <skill_root>/scripts/strip_term_markers.py <项目目录>
```

批准文件 `_term_review_approval.json` 绑定规范化项目路径、源文、译文全部 chunk 字节哈希及当前决策/语义输入/规则版本。部分批准可以保存，但无法清标记；结构异常不能批准绕过。改源文、译文、chunk 集合、问题内容或分组后旧批准失效。脚本重新计算而不信任可编辑的报告。记录含逐项理由、审阅者及全文审阅者，但本地文件不是身份认证或语义保证。

## 4. 有意选择的全自动模式

```bash
python <skill_root>/scripts/strip_term_markers.py <项目目录> --mode auto
```

仅用于用户已选全自动流程：独立 AI QA 后不需要人工放行。结构损坏仍阻断；有效旧输入的清理内容保持原行为。不得为了绕过手动模式待确认而临时改为 auto。

默认输出 `_translated_chunks_clean/`，保留带标记原件。支持 `--output-dir`；禁止覆盖源文/译文目录或写入带符号链接/旧 chunk 的输出。审批仅绑定默认译文目录；自定义 `--input-dir` 若指向其他目录，需另建项目并重新审阅。默认 CLI 现在安全地要求手动批准，旧自动调用必须显式添加 `--mode auto`。

## 检查

```bash
python -m unittest discover -s tests -v
```

完整审计兼容不等于语义校验完备。短队列的条目数衡量词面排查负担，不能宣称是翻译准确率或最终人工决策量。
