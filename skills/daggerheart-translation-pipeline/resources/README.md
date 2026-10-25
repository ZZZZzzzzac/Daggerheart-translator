# 术语分组与维护

默认按 `term-groups.json` 的顺序加载 `default: true` 的分组，再加载项目术语。核心表沿用远端的 `terms-core.json` 名称；它不是 Paratranz 导出镜像。

| 分组 | 文件 | 条数 | 默认加载 |
| --- | --- | ---: | --- |
| 游戏性与规则机制 | `terms-core.json` | 287 | 是 |
| 敌人特性 | `adversaries_features.json` | 12 | 是 |
| 装备特性 | `equipment_features.json` | 19 | 是 |
| 敌人名字 | `adversaries_name.json` | 152 | 是 |
| 敌人动机、战术与经历 | `adversaries_motivation.json` | 112 | 是 |
| 世界设定 | `worldbuilding.json` | 234 | 是 |
| 玩家资源名称 | `player_resources.json` | 100 | 是 |
| 玩家特性与能力 | `player_features.json` | 1 | 是 |
| 环境名字 | `environments_name.json` | 15 | 是 |
| 环境特性 | `environments_features.json` | 2 | 是 |
| 装备与物品名字 | `equipment_names.json` | 5 | 是 |
| 翻译固定用语 | `translation_phrases.json` | 33 | 否 |

每条 JSON 对象独占一行。特性、动机、趋向和经历按 SRD 2.0 的独立资源定义计数，至少出现两次；不把数值变体、拆卡或中英重复展示算成重复定义。专名不套用这项频次限制。

同词头的规则区分、词形变体及大小写边界沿用已审定结果：Support 为“辅助”，Dazed 为“恍惚”，Stunned 为“眩晕”。Ghost、Cloaked 的不同实体含义仍按上下文判断，不进入默认敌人特性表。

按本轮要求，七个既有 OCR 词头并入核心组；规范拼写同时保留。官方战役框架名称随世界设定组加载，框架专属机制从 `scoped/` 按项目选择；`reference/` 中的语境说明不参与自动合并。

固定用语组默认不自动替换；已明确固定的“每长休一次”仍在核心组。术语备注只说明含义、规则效果与匹配范围，不加入“保留作参考”、审定日期或整理过程。
