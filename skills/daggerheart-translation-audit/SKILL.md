---
name: daggerheart-translation-audit
description: 审阅现有 Daggerheart 中英译文，查找规则语义、漏译、数值及源文导入错误；建立可追溯覆盖记录并输出逐条审阅报告。适用于 SRD、规则书、装备和卡牌的翻译抓虫，不替代翻译管线或授权线上修复。
---

# Daggerheart 翻译审阅

目标是让用户能判断并处理每个问题，而不是列出尽可能多的差异。默认只读，报告中的“完成”是审阅进度，绝不代表线上已修复。

## 开始前

- 确认项目、版本、文件与用户排除项。先列全项目文件，再选择审阅范围；不能凭文件名把旧版、核心书、VTT 副本全算进来。
- 审阅已有 ParaTranz 译文时，使用同仓库 `paratranz-ops` 的客户端访问 API；本 skill 的 `scripts/audit_data.py snapshot` 复用该客户端，只调用 GET，补足全分页与一致性验证。单页、翻译导出包或关键词命中不能冒充全量快照。
- 工作数据写入用户翻译项目的审阅目录或外部临时目录。不要提交凭据、完整项目快照、内部笔记或真实用户进度到 skill 仓库。
- 读取 [references/workflow.md](references/workflow.md)，按其中的范围、语义审阅、复核和回读要求执行。数据契约见 [references/data-contract.md](references/data-contract.md)。

## 工作流

1. **固定基线**：记录文件 ID、总数、版本日期、抓取起止时间、逐页记录与 SHA-256。校验条数、唯一 ID、页数；检测抓取期间变更。快照不是数据库原子事务，不能声称完全锁定线上状态。
2. **核清范围**：覆盖表为每条快照记录标注 `in_scope`、`partial` 或 `excluded`。排除需写理由和对应版本/重复项；混合条目保留精确审阅片段，不因一段重复而排除整条。
3. **逐条语义读**：按顺序通读所有纳入项，核主体、对象、触发条件、成功/失败、可选/必须、次数、范围、持续时间、费用、资源与伤害类型。骰子、数值、术语扫描仅生成候选，不能替代逐条审阅或直接判错。
4. **独立复核候选**：给复核者原文、现译、上下文、版本和证据位置，要求其自行判断，记录支持/驳回/待查及原因。不能只让复核者接受第一轮结论。无独立复核时明确披露，不将未复核候选包装为已确认。
5. **源文溯源**：遇到规则矛盾、旧版残留、错行错列，查对应版本官方文档和原始页面布局。分别保存“官方原文”“ParaTranz 导入原文”“现译”。官方版式串列错误是源文问题，不能归咎为翻译错误。不能靠猜测把 OCR 重排当成官方证据。
6. **交付前增量回读**：重新完整抓取同范围，运行 `diff`。新增、删去、原文、译文、上下文或版本变化的条目重新审阅，并检查相邻关联条目。旧发现标为 `stale`，复核后才重建；不能把“译文变了”自动判为“已修”。若回读失败，披露截止时间及未核验项。
7. **交付**：校验覆盖和发现数据，分别统计已确认、疑点、驳回、已修、过时，以及问题数和受影响条目数。报告标明版本、时间、范围排除与缺口。有待处理发现时，按照 [references/report-ui.md](references/report-ui.md) 生成一屏一项的离线报告；无发现时只交付覆盖记录与范围/截止时间说明，不伪造条目来填充界面。

## 可运行入口

命令相对于本 skill；`--out` 应在技能仓库之外。凭据配置沿用 `paratranz-ops`，不得放命令行参数或输出中。

```bash
python scripts/audit_data.py snapshot --files 123 456 --out /path/to/audit/baseline.json
python scripts/audit_data.py snapshot --files 123 456 --out /path/to/audit/latest.json
python scripts/audit_data.py diff /path/to/audit/baseline.json /path/to/audit/latest.json --out /path/to/audit/delta.json
python scripts/audit_data.py validate /path/to/audit/audit.json
python scripts/render_report.py /path/to/audit/report.json /path/to/audit/report.html
python -m unittest discover -s tests -v
```

`snapshot` 遇到重复 ID、分页矛盾、范围缺失或抓取期文件变化会失败，不发布不完整快照。排除变更原因后重新抓取；不要通过关闭校验凑齐数字。自动检查通过只证明结构与记账完整，不证明语义审阅正确。

## 边界

本 skill 不写 ParaTranz。用户另行明确批准修复后，才转入 `paratranz-ops` 的写回流程：先读最新值、限定修改项、保留 stage、冲突跳过、写后回读。报告建议、用户勾选已读、复制文字或保存进度都不构成写回授权。
