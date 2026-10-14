# 术语表：来源、范围与维护

## 核心表不是 ParaTranz 镜像

`terms-core.json` 的维护目标是跨项目复用的 Daggerheart 规则术语，而非收录某个翻译平台项目里的全部条目。它从本仓库已人工清洗的 `terms-14448.json` 迁移而来；旧文件名不表示今后应与 ParaTranz 项目自动同步。

本次迁移基线：提交 `89caa5449a8a3682f54df32ab55d859d517ed4a6` 的 `skills/daggerheart-translation-pipeline/resources/terms-14448.json`，共 328 条。迁移后核心表 326 条，两个框架术语表各 1 条。保留所有条目的原 `term`、`translation`、`note`、`variants`、`case_sensitive` 字段；没有引入 ParaTranz 新导出，也没有改译名。

不要使用 ParaTranz 全量导出覆盖核心表。外部术语表可以作为对照资料；新增、改译名或改匹配规则必须逐条审阅，明确规则依据和适用范围。

## SRD2 新增（2026-10-14）

经逐项核对 SRD2 原文与当前中文快照，本次新增 42 个概念：36 条进入核心表，当前核心共 **362 条**；另有 6 条写入 [语境参考](reference/srd2-context-only.json)，供翻译与语义审阅查阅，尚不参与自动匹配。来源、原译、页码、实际别名及待定语义边界见 [逐项来源](reference/srd2-additions.md)。这不是 ParaTranz 镜像同步，也未改写旧核心 326 条。

语境参考必须按所属规则上下文阅读，不得放入默认合并命令、目录通配符或 `scoped/` 框架表。Ghost 的转变／敌人特性实体消歧尚未定案；Vampire 与既有敌人表 VAMPIRE 同译“吸血鬼”，保留这项明确记录的同译复用。

## 范围边界

- 核心表：官方战役框架名称（跨项目统一译名）；通用掷骰、资源、状态、距离、伤害等机制；职业、子职业、种族、社群、领域；可跨项目复用的敌人类型、特性及规则表达。不能因为名称看起来像专名就删除这些规则分类。
- 项目表 `glossary/_glossary.json`：当前项目独有的人名、地名、组织及其他概念。官方战役框架名称保留于核心表；框架专属机制归入各自框架术语表，按项目需要选用。
- `scoped/`：从历史核心表移出的条目备份，可供相关项目选用。它们不是默认输入，不应用目录通配符加载。只把原文涉及且适用于本项目的条目加入项目表。
- `adversaries_*.json`：现有敌人专项参考，本次未重分类或改译名；独立于核心表。默认管线仍按原有顺序加载。核心表分层不等于这些参考表也已完成全量范围审计。

保留既有优先级：`terms-core.json` > `adversaries_*.json` > 项目表。手动模式的冲突仍须先审阅；自动模式仍保留高优先级译名并输出报告。

## 官方战役框架名称：保留在核心表

以下名称由官方 [Downloads 的 Campaign Frame Materials (Core)](https://www.daggerheart.com/downloads/) 列为战役框架。按维护者要求，以下六条保留在 `terms-core.json`，以统一官方框架译名：

| 原文 | 原译名 |
|---|---|
| Age of Umbra | 暗影纪元 |
| Beast Feast | 野兽饭 |
| Colossus of the Drylands | 旱土巨像 |
| Five Banners Burning | 五旗成焰 |
| Motherboard | 主板 |
| Witherwild | 秽野之息 |

## 两条框架机制：分别归入各自框架术语表

以下两条不属于总表，按维护者确认分别存入各自框架的术语表；保持原字段，不混入一个共用机制表：

| 原文 | 原译名 | 框架术语表 | 范围与依据 |
|---|---|---|---|
| Colossal Power | 巨像之力 | `scoped/colossus-of-the-drylands.json` | Colossus of the Drylands 巨像特性；官方[勘误](https://www.daggerheart.com/wp-content/uploads/2025/09/Daggerheart-Errata-September9th2025.pdf)在核心书第 322 页 Daktadae the Cleaver 下列出此特性。 |
| flavor profile | 风味组合 | `scoped/beast-feast.json` | Beast Feast 的料理规则；[Demiplane 官方功能公告](https://forums.demiplane.com/t/lets-feast-daggerheart-beast-feast-campaign-frame-support-now-available/5343)将 Flavor Profile 列在该框架的食谱功能中。 |

两条机制均完整保留，没有丢弃。翻译 Colossus of the Drylands 时，仅选用 `scoped/colossus-of-the-drylands.json` 的相关条目；翻译 Beast Feast 时，仅选用 `scoped/beast-feast.json` 的相关条目。将所需条目保留原字段加入项目 `glossary/_glossary.json` 后执行正常合并。不默认加载任何框架表，也不把两个框架表一起批量导入无关项目。六个官方框架名称仍默认可用。

## 暂不改动，留待审阅

本次是保守的范围整理，不宣称核心表已经完成全部语义校订：

- `kohd`：疑似 Motherboard 专属语言。尚未补齐官方原文证据，本次保留待核实。
- `Segment`、`Weak Point`：可能涉及框架巨像机制，但尚未确认是否存在通用用法，本次保留。
- `core realms`、`realms`、`the Astral Realm` 等世界观用语：需结合通用规则中的用途判断，不能仅因是地点概念就删除。
- `CHAOS REALM`、`CIRCLES BELOW`、`Phase Change`：在[官方 SRD](https://www.daggerheart.com/wp-content/uploads/2025/09/Daggerheart-SRD-9-09-25.pdf)中分别涉及环境、Infernis/恶魔背景和通用敌人数据块，本次保留。
- `Dazed` 与 `stunned` 当前同译为“眩晕”，未擅自采用外部表中的另一译名。
- `Cloaked` 已存在，译为“隐匿”；`Hidden` 为“隐藏”，`Shrouded` 为“幽影”。本次未添加或重写三者的语境说明。
- 原表存在大小写或变体之间可能冲突的映射（如 `Support` / `Supports`、`spotlight` / `SPOTLIGHT`、`advance` / `ADVANCEMENTS`）。现有合并脚本只按完全相同的主词条检测冲突；本次不改变匹配与裁决逻辑，也不把译名分歧自动当作重复项删除。

## 迁移已有项目

1. 把自有命令中的 `resources/terms-14448.json` 改为 `resources/terms-core.json`。
2. 检查项目术语表，只选择该项目实际需要的限定范围条目。
3. 在继续翻译前重新执行第 4 步，生成新的 `_merged_terms.json` 和术语标记；已有临时合并表不会因文件改名自动更新。已翻译的文件应先另存或用版本控制保留，再按项目进度决定是否重跑后续步骤。

## 验证

在仓库根目录运行：

```bash
python -m unittest discover -s tests -v
```

测试覆盖资源结构、官方框架名称保留与专属机制按框架分层、规则分类保留、默认命令引用、显式项目选用、变体标记，以及手动/自动冲突行为。脚本原先没有硬编码旧文件名，因此无需为此次改名修改运行逻辑。


## 2026-10-14 语境与重复项清理

维护者随后要求由译者结合ParaTranz通常译法自行处理术语，不再提交逐条审阅队列。本次已只读刷新项目术语、SRD2正文/装备及相关讨论；未修改线上译文。

- 当前固定词条338项；首轮SRD2新增36项仍在其中。六项SRD2语境参考、原有两项框架分表仍各自独立。
- 原39项非一对一词义/截断模板移入`reference/contextual-usage.json`；7项重复主词合并。原25项其他候选中22项成为固定词条，3项成为语境规则。
- 统一项目已明确的辅助、聚焦、恍惚/眩晕、光荣就义。Cloaked与Ghost的不同实体不再由默认敌人表覆盖核心/转变文本，而由语境参考给出各自译法。
- 两条reduce裸前缀退出直接表；完整数值减伤、阈值降级及少标生命点句式见中文写作REFERENCE。没有新增匹配机制，也不把字面X当变量。
- `reference/`下JSON为带用途声明的对象，**不是自动合并输入**；中文写作REFERENCE显式要求读它们。只按SKILL中的明确文件列表加载，不能使用目录通配符。
- 变体补齐和大小写只能修已知词面问题，不具备语义识别能力。行内标记、漏标及词面一致仍不能替代全文审校。

逐词去向、来源和44张旧审阅卡的处理结果均在`reference/glossary-cleanup-decisions.json`。历史首轮新增的冻结快照用于追溯，不应被当作当前338项表的“保持旧表不变”约束。
