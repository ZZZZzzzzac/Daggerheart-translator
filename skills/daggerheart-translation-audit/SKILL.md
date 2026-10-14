---
name: daggerheart-translation-audit
description: 通用双语翻译抓虫：接收配对原文与译文文本、文件或平台导出，逐段语义审阅、记录证据与覆盖情况，生成精准高亮、可保存进度的HTML人工审阅报告。ParaTranz和Daggerheart规则仅为可选来源与项目层，不要求账号或平台ID。
---

# 通用翻译抓虫与HTML审阅

核心流程：**原文与译文 → 核对对齐 → 逐段语义审阅 → 复核问题 → HTML供人审阅**。适用于任何领域和语言组合。历史目录/技能名保留以兼容已有安装，不代表必须使用Daggerheart或ParaTranz。

脚本负责固定文本、校验覆盖/证据和生成HTML，**不自动完成语义审阅**。报告“完成”只表示用户看过该问题，不表示源文件已修改。默认只读。

## 选择输入

- **普通文本、文件、已配对JSON**：使用 `scripts/paired_audit.py`，先读 [references/paired-inputs.md](references/paired-inputs.md)。只需Python标准库，无账号、凭据、项目号或数字ID。
- **ParaTranz**：可选适配器 `scripts/audit_data.py` 继续支持既有snapshot/diff/validate命令，见 [references/data-contract.md](references/data-contract.md)。适配器复用同仓库paratranz-ops客户端，不将平台要求带入通用流程。
- **领域要求**：按实际项目读取术语表、风格指南和原始依据。只有Daggerheart项目才读 [references/domain-daggerheart.md](references/domain-daggerheart.md)。

## 必须完成的工作

1. **保留输入与对齐证据**：记录来源、读取时间、版本/内容hash和稳定段落ID。短文可以整份一对一；长文按已核实的章节/段落关系配对。漏译或增加内容用显式空侧保留，不能丢弃无法匹配的文字、盲按行号对齐或凭猜测重排。
2. **逐段实际阅读**：完整上下文核主体、指代、条件/否定/例外、事实、数值/单位、语气义务、漏译/增译及领域用语。每个纳入段落都留覆盖记录，包括无问题者。数字/词语扫描只是线索，不足以标记语义已审。
3. **记录可判断的问题**：完整原文/现译、精确证据、影响、具体建议、状态、严重度、当前文本hash；finding ID稳定，不因排序重编号。精准高亮只标当前问题涉及的范围，遗漏允许单侧，不编造另一侧证据。
4. **复核与溯源**：独立复核候选，区分确认、歧义和驳回；无复核时明确披露。源文件、抽取/导入原文、译文三层不能混为一谈。原始PDF/网页/OCR有错时保留定位依据，不把所有问题都归于译者。
5. **检查时效与覆盖**：交付前重新读取可访问来源；hash变化的段落和相关上下文重审。不把“文字变了”自动判为“已修”。完整报告必须全量覆盖；部分报告显式标注未审ID、范围与截止时间。
6. **交付HTML**：默认一屏一项，中英/双语文本、问题、建议为核心；正文长时明确分页、全文可达。底部集中上一条/下一条/完成，有链接才显示来源跳转。进度可保存、导入导出。零发现也可输出HTML覆盖说明，不能编造发现凑界面。

详细判断标准：[references/workflow.md](references/workflow.md)。展示字段和测试要求：[references/report-ui.md](references/report-ui.md)。

## 通用最短可运行路径

命令相对于本skill目录，真实工作产物放在仓库外。以下两份UTF-8文本作为一个完整pair，不自动切行对齐：

```bash
python scripts/paired_audit.py normalize --original-file /path/original.txt --translation-file /path/translation.txt --id manual --title "文档审阅" --out /path/snapshot.json
python scripts/paired_audit.py prepare /path/snapshot.json --out /path/review.json
# 审阅者实际阅读文本、核实对齐，填写review.json中的coverage和findings。
python scripts/paired_audit.py validate /path/snapshot.json /path/review.json
python scripts/paired_audit.py export /path/snapshot.json /path/review.json --report-id manual-audit-v1 --out /path/report.json
python scripts/render_report.py /path/report.json /path/report.html
```

已配对的多段输入用 `normalize --pairs pairs.json --out snapshot.json`。`prepare`只建未审账本，不填写判断；`export --allow-incomplete`仅用于明确需要的部分报告。可直接打开[合成HTML示例](examples/consumer-report.html)；配对输入、审阅记录与端到端用法见 `examples/` 和通用输入契约，不包含真实翻译项目数据。

## 验证与边界

```bash
python -m unittest discover -s tests -v
node tests/test_report_state.js
node tests/test_highlighting.js
node tests/test_source_action.js
```

结构校验不能证明语义判断正确；模拟分页也不等于真实浏览器视觉验收。保留已验证和未验证的边界。报告不授权修改原文件、写回平台或发布译文；修复需要另行明确批准并重新读取当前文本，避免覆盖他人更新。不要向技能仓库提交真实项目快照、用户审阅进度或凭据。
