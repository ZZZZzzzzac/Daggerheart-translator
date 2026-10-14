---
name: daggerheart-translation-audit
description: 对已经取得的原文与译文做通用翻译抓虫：规范配对输入、逐段语义审阅、复核证据，生成精准高亮且可保存进度的HTML供人审阅。适用于各类文档与语言组合；不负责取得原译文。
---

# 通用翻译抓虫

输入是**已经取得的原文与译文**。本skill只做：**格式化输入 → 核对对齐 → 语义抓虫 → 复核 → HTML审阅**。历史技能名保留兼容，不限制题材。

取得文本属于外部任务：ParaTranz交给 `paratranz-ops`，飞书交给飞书CLI，本地现成文件直接使用；不要把这些来源的操作流程带进本skill。

**若内容属于Daggerheart，必须先调用 `daggerheart-chinese-writing` skill，以其语言与术语规范指导审阅和建议译文。** 不在这里另抄一套规则。其他领域使用用户给定的术语表或风格要求。

## 输入与工作流

1. **规范配对**：将已有材料整理为带稳定ID的原文/译文段落对，保留字序、标点、换行和必要上下文。明确一对多/多对一关系；未匹配内容保留空侧，不能丢段或盲按行号配对。格式见 [references/paired-inputs.md](references/paired-inputs.md)。
2. **逐段实际读**：核主体、指代、条件、否定、例外、事实、数值/单位、义务语气、漏译/增译及术语。每个纳入段落都留审阅记录，包括无问题者；机械差异与数字扫描只能给线索，不能替代语义判断。
3. **记录可处理的问题**：保存问题ID、精确证据、影响、具体建议和严重度，区分确认与待核实。完整原文/现译始终保留；高亮只标与当前问题相关的片段，漏译允许只亮原文，不伪造另一侧内容。
4. **独立复核**：复核者先读原译文和上下文，再判断候选是否成立。没有独立支持时保留待核实，不编造确认。已有材料中的对齐/抽取错误与翻译错误应分开说明，不把无根据的推测算成译错。
5. **核验覆盖与证据**：检查所有输入段落都有记录，问题与当前文本一致。输入改动后重新判断相关段落；本地内容hash只用于拦住错位/过时证据。部分结果明确未审ID，不宣称完整完成。
6. **形成HTML**：默认一屏一项，原文、现译、问题、建议最醒目。上一条/下一条/完成集中在底栏；输入自带有效链接时才显示跳转。长文明确分页，全文可达，精准高亮与进度保存/导入导出保留。无发现也如实显示覆盖情况，不制造假问题。

详细判断标准：[references/workflow.md](references/workflow.md)。报告界面约定：[references/report-ui.md](references/report-ui.md)。

## 本地规范化与报告

以下 `pairs.json` 是已准备好的配对内容，不包含来源操作。

```bash
python scripts/paired_audit.py normalize --pairs /path/pairs.json --out /path/input.json
python scripts/paired_audit.py prepare /path/input.json --out /path/review.json
# 审阅者实际逐段阅读、核对对齐，填写review.json。
python scripts/paired_audit.py validate /path/input.json /path/review.json
python scripts/paired_audit.py export /path/input.json /path/review.json --report-id document-audit-v1 --out /path/report.json
python scripts/render_report.py /path/report.json /path/report.html
```

`prepare`只建立未审记录，不进行自动语义审阅。需要交付部分结果时显式使用 `--allow-incomplete`。数据格式和合成示例见输入契约；可直接打开[合成HTML](examples/consumer-report.html)。

## 边界与验证

脚本只规范输入、校验证据/覆盖和渲染报告，不自动证明翻译正确。HTML中的“完成”只记录用户审阅进度，不修改原译文。结构测试和分页模拟不能替代真实浏览器视觉验收。

```bash
python -m unittest discover -s tests -v
node tests/test_report_state.js
node tests/test_highlighting.js
node tests/test_source_action.js
```
