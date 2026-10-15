# 原名表与中文交付检查：可选本地试用

本分支提供源文保留、两阶段翻译输入、中文交付检查和 PBRES 独立原名表适配器。所有入口均须显式运行，不改变现有主流程默认。此处仅包含实现、合成回归测试和使用文档，不包含真实翻译运行、诊断输出或评审材料。

## 依赖与测试

需要 Python、jsonschema 和 Pandoc。已验证环境为 Python 3.12.14、jsonschema 4.26.0、Pandoc 3.1.11.1；其他版本未验证。

```bash
python -m unittest discover -s tests -v
```

## 独立原名表

`resources.json` 顶层为 `resources` 数组；各资源具有唯一 `id`、`template.id`、`template.version` 和 `data`。资源边界、父子归属、中文译名须预先确认。支持范围由固定 Schema 快照决定，不猜测其他版本。

```bash
python experiments/context_contract/pbres_names.py extract resources.json original-names.json
```

主名与特性名按资源 ID 和 JSON Pointer 分别保存。可选原文字段缺失与空字符串分开保留；不造原名、不按词面合并实体。主名与特性字段的结构因模板而异，Schema 快照中的来源链接可逐项核对。此工具不会读取 PBRES ZIP、自动识别英文实体或生成可导入的新资源包。

## 新建候选翻译试验

准备完整英文上下文和准确项目术语；`cases.json` 是包含 `id`、`source` 和可选 `context` 的数组。若源段依赖完整文档，将必要上下文完整放入输入。原名表不能代替上下文。

```bash
python experiments/context_contract/pbres_names.py prepare cases.json resources.json ../translation-trial-runs/new-run
```

执行生成的 `phase1-generate.txt`，完成实际 `candidate-draft.json`。本工具不自带模型调用，也不生成模拟译文。

```bash
python experiments/context_contract/pbres_names.py polish ../translation-trial-runs/new-run --development
```

由独立审阅者执行 `phase2-polish.txt`，回查完整英文后完成 `candidate-final.json`，再运行：

```bash
python experiments/context_contract/delivery_gate.py release ../translation-trial-runs/new-run --development
```

通过仅表示基础交付检查通过，仍需语义与自然度审阅。退出码 2 或 `BLOCKED` 必须处理；不要直接运行 `two_pass.py freeze` 绕过包装门禁。每次使用仓库外的新目录（示例为 ../translation-trial-runs/new-run）；不要覆盖已冻结运行，也不要把生成输出加入版本控制。以上 development 流程只运行候选，不构成对照评估。

## 检查已有译文

`sources.json` 为源文记录数组；`translations.json` 含 `units` 数组，各项具有 `id` 和 `translation`。

```bash
python experiments/context_contract/pbres_names.py check resources.json original-names.json sources.json translations.json
```

原名表英文不属于正文白名单。骰式、链接和中文结构仍受检查。输入资源与原名表不得篡改，工具不删改输入正文。

## 已知边界

- 校验表与资源一致，不代表人工资源归属正确；目前也不自动检查正文每个中文名称是否与表一致。
- 名称绑定检查尚未实现，未作为本分支功能交付。无需重复名称的正文不被强制加标题。
- 精修继续使用代码内原始政策；不包含后续实验政策、既有评审材料或效果承诺。
- 结构、字面引文及模型自述核对不证明语义正确。源文歧义、事实完整性、命名和口语自然度仍须独立审阅。
- 不宣称普遍优于原流程或节省人工审阅时间，不自动外发、推送或修改线上资源。
