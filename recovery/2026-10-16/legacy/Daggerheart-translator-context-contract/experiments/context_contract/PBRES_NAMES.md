# PBRES 原名表试验（可选，不替换生产默认）

## 查证范围

2026-10-15 通过 GitHub 读取 PbDH 提交
`9cfb0ec491058c07465acd92f2ac97b9fbc4f2d3`。
`pbres-name-schemas.json` 保存当前注册表的全部 14 个模板 Schema，另加实际
牛头人测试包使用的敌人 1.0.0；每份含固定提交链接和 Git blob SHA。

[当前注册表](https://github.com/ZZZZzzzzac/PbDH/blob/9cfb0ec491058c07465acd92f2ac97b9fbc4f2d3/packages/templates/src/core/index.ts)
确定版本，不能只挑目录中数字最大的版本。
[包级契约](https://github.com/ZZZZzzzzac/PbDH/blob/9cfb0ec491058c07465acd92f2ac97b9fbc4f2d3/contracts/resource-package/1.1.0/schema.json)
只定义包壳和可递归的数据值，具体原名位置由各资源模板定义。

- 主名称：除玩家卡外，13 种当前模板有 `名称/原文`。
- 敌人、环境、种族、职业、子职业、罗德岛子职：`特性[].特性名称/特性原文`。
- 职业额外有 `希望特性.特性名称/特性原文`。
- 社群特性是对象，不是数组：`特性.特性名称/特性原文`。
- 武器、护甲的 `特性名称/特性原文` 在 data 顶层。
- 自由、寻望物资：`内容[].名称/原文`，不能改写为特性字段。
- 领域卡、物品虽然有“特性描述”，却没有独立“特性原文”。
- 玩家卡没有原文字段。罗德岛子职的“希望特性”是普通字符串，不能套用职业的嵌套结构。

原文/特性原文均为可选字符串，不是必填，也不要求附在中文正文。
本试验的保全政策比 Schema 更严格：已有原名完整存表；缺失、空字符串分别记录，
不创造缺失原名。Schema 不能证明某个翻译语义正确，也不能告诉我们散文里所有应建档的专名。
固定中文机制模板、骰式、链接不因这一试验放宽。

## 使用

依赖：Python、jsonschema、现有管线所需的 Pandoc。
输入是已完成语义归属的资源对象 `{ "resources": [...] }`，不是 ZIP `.pbres`
文件，也不是未结构化英文。先按 PbDH 的转换流程明确资源和特性边界。
该工具不声称能从任意段落自动识别实体。

只导出独立表：

`python experiments/context_contract/pbres_names.py extract resources.json original-names.json`

新建管线试验：

`python experiments/context_contract/pbres_names.py prepare cases.json resources.json /absolute/new-run`

实际完成首稿后：

`python experiments/context_contract/pbres_names.py polish /absolute/new-run [--development]`

实际完成精修后仍用现有严格交付门：

`python experiments/context_contract/delivery_gate.py release /absolute/new-run [--development]`

prepare 将原名表、输入资源、Schema 和适配器哈希绑定到 manifest；现有 release
会拒绝它们被改动。两组生成提示和精修提示均有同一原名表政策。
正文仍使用空英文白名单；表中的 Guardian 不会使正文“守护者 Guardian”过关。
导出的 original-names.json 是独立交付附件，不要拼进正文。
单独核对外部表及正文可用 `pbres_names.py check resources.json original-names.json sources.json translations.json`。

工具只导出副本和检查，从不删改输入正文或 PBRES 数据；不产生可直接导入的新 PBRES，
也不改变卡面渲染器。下游 PBRES 继续使用原有原文字段。重复名称用资源 ID + JSON Pointer
分别定位，不能按英文/中文词面去重。未知版本、错误结构、重复 ID、掉行、增造原名、
换父实体、换路径、漏骰或链接，以及正文英文残留都会被拒绝。

## 已验证及边界

新增自动化回归覆盖以上结构和保全边界；另用上游真实
[牛头人破坏者测试包](https://github.com/ZZZZzzzzac/PbDH/blob/9cfb0ec491058c07465acd92f2ac97b9fbc4f2d3/contracts/conformance/resource-package/1.0.0/valid/minotaur-wrecker.pbres)
核对：牛头人破坏者 / MINOTAUR WRECKER、蓄力 / Ramp Up、蛮牛冲撞 / Charging Bull、角撞 / Gore。
这是上游既有中文的展现试验，不是新模型翻译、不构成自然度优于旧流程的证据。
历史试验文本和评分不变，不推送、合并、部署或改线上资源。
