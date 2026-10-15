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

## 可选：显式中文名称位置绑定

默认 `check` 仍只核对原名表完整性和基础交付要求，不推断正文中哪些词是实体名称。仅在已人工确认单元父资源及名称位置时，增加 `--bindings name-bindings.json`：

```bash
python experiments/context_contract/pbres_names.py check resources.json original-names.json sources.json translations.json --bindings name-bindings.json
```

例如，已确认单元 `s` 属于资源 `r1`，该资源主名为“守护者”，`/data/特性/0/特性名称` 为“无畏”。预期的译文结构是：

```markdown
# **守护者**

**无畏 - 反应：** 这里是完整特性正文。
```

对应配置：

```json
{
  "version": "pbres-name-bindings-v1",
  "unit_parents": [{"unit_id": "s", "resource_id": "r1"}],
  "bindings": [
    {
      "unit_id": "s",
      "resource_id": "r1",
      "name_pointer": "/data/名称",
      "selector": {"kind": "heading", "block": 0, "level": 1}
    },
    {
      "unit_id": "s",
      "resource_id": "r1",
      "name_pointer": "/data/特性/0/特性名称",
      "selector": {"kind": "feature_label", "block": 1, "suffix": " - 反应"}
    }
  ]
}
```

名称身份始终是 `resource_id + name_pointer`，不按同名词面去重。每个绑定必须与该单元在 `unit_parents` 中的唯一父资源一致。`name_pointer` 必须逐字引用当前原名表的一条名称路径，不能使用原文字段、通配符或别名。同一名称可显式绑定到不同位置；同一单元同一位置的重复或冲突绑定一律拒绝。空 `unit_parents` 与空 `bindings` 可表示显式无绑定；缺少选项才是默认模式，显式 JSON `null` 是无效配置。

选择器范围刻意收窄：

- `heading`：核对指定级别的整个顶层标题。支持 ATX/Setext 标题、加粗/斜体和链接的可见文字。不会把“守护者说明”当作“守护者”。
- `feature_label`：只支持顶层段落开头的加粗或斜体标签，标签内或紧跟标签后须有 `:` / `：`。例如 `**无畏：** 描述`、`**无畏**：描述`、`*无畏*：描述`。可选 `suffix` 是人工指定、逐字核对的标签后缀；`" - 反应"` 可支持上例，未声明时不自动猜测或剥去动作类型。后缀错误或缺失也阻止通过。
- `block` 是 Pandoc CommonMark AST 的 `blocks` 数组从 0 开始的索引，不是行号或“第几个标题”。上述例子标题为 0、段落为 1。新增段落、列表、代码块等可能改变索引，须重新审阅绑定；可用 `pandoc --from=commonmark --to=json < translation.md` 查看真实结构。不递归搜索列表、引用或嵌套块，也不自动选取同名的其他位置。
- 名称的 Markdown 标记由真实解析器处理；仅去掉名称外侧空白及标签冒号/显式后缀，其他字面内容须与原名表中文名称完全一致。注释、代码、原始 HTML、图片、链接目标/标题、引用链接定义均不能充当名称证据。解析失败会阻止通过。

已有结构化译文还可以在单元中显式提供 `name_fields`，例如：

```json
{"units": [{"id": "s", "translation": "完整中文正文。", "name_fields": {"主名": "守护者"}}]}
```

此时选择器可写为 `{"kind":"field","pointer":"/name_fields/主名"}`。路径采用 RFC 6901，支持对象和规范的零起始数组下标，`~1` 表示 `/`，`~0` 表示 `~`；不支持通配符、负数、`-` 或 `00` 数组下标。只允许 `/name_fields/` 内的纯字符串，值须逐字等于表内中文名称，不按 Markdown 渲染。此检查仅核对指定字段，不证明正文出现了同名。普通 `translation` 仍必须提供，且继续经过基础交付检查。

API 为 `check(resources, sidecar, sources, translations, bindings=配置)`；结果中 `name_binding_check.configuration_errors` 区分配置/父资源/引用错误，`name_binding_check.bindings[*].findings` 报告名称不符或选择器失败。任一错误均使总 `release_allowed` 为 false，CLI 退出码为 2。无法读取的 JSON、重复 JSON 键或资源/原名表完整性错误也会非零退出。`validate_bindings(...)` 可单独校验声明与引用，失败抛出 `ValueError`，不会声称已核对译文。

### 在新试验中启用绑定

```bash
python experiments/context_contract/pbres_names.py prepare cases.json resources.json ../translation-trial-runs/new-bound-run --bindings name-bindings.json
```

后续仍用 `pbres_names.py polish` 和 `delivery_gate.py release`。绑定及指引进入两个生成分支与精修输入；绑定文件、实现和原名表均记录哈希，并在已锁定的输入包中保存绑定文件哈希。最终 release 对实际交付 Markdown 再核对绑定，不因基础检查通过而跳过；改动、移除绑定或不一致的注册信息会阻止发布检查，并先撤销旧的通过状态。

试验生成与冻结路径只交付 Markdown，故 `prepare --bindings` **不支持 `field`**，会在创建运行目录前明确拒绝。结构化字段绑定仅供已有明确 `name_fields` 载荷的独立 `check` 使用，不会虚构字段或悄悄改写交付结构。

## 可选：显式范围内的机制数量风险

这是数量表面核对，不是语义抓虫或译错判定。只在调用者已经核对原译文对应关系、并明确选择短规则范围时启用。没有 `--quantity-scopes` 时，原有输入、结果字段和门禁行为保持不变；不会自动扫描全文数字。

例如，原文单元 `s` 是 `Mark 2 Stress.`，译文是 `标记3压力点。`：

```json
{
  "version": "mechanic-quantity-scopes-v1",
  "scopes": [
    {
      "id": "stress-cost",
      "unit_id": "s",
      "source": {"kind": "unit"},
      "translation": {"kind": "unit"}
    }
  ]
}
```

保存为 `quantity-scopes.json`，对已有译文检查：

```bash
python experiments/context_contract/delivery_gate.py scan sources.json translations.json --quantity-scopes quantity-scopes.json --output quantity-review.json
python experiments/context_contract/pbres_names.py check resources.json original-names.json sources.json translations.json --quantity-scopes quantity-scopes.json
```

上例返回 `quantity_risk_check.status: "needs_review"`、带原文 `2` / 译文 `3` 证据的 `quantity_sequence_difference`，总 `release_allowed` 为 false、CLI 退出码 2。这表示需审阅，不表示已经确认译错；不会自动改数字、替换译文或删句。`risk_count` 是风险条数，配置错误单独放在 `configuration_errors`，两者都不是语义错误计数。

### 范围与证据

- `unit`：显式选择该单元的完整 Markdown。推荐短规则单元，不能代替人工核对范围。
- `block`：`{"kind":"block","block":1}` 选择各自 CommonMark AST 的一个顶层块。原文与译文可以使用不同索引；不会自动按行或词面配对。支持普通段落、Plain 和标题，以及其中的加粗、斜体和链接可见文字。列表、引用、代码、图片、原始 HTML 等未支持结构返回范围不可核对，不能提供或隐藏数量证据。链接目标、标题、引用定义和裸 URL 不参与数量比较。可用 `pandoc --from=commonmark --to=json` 检查索引。
- `field`：已有结构化记录可用 `{"kind":"field","pointer":"/quantity_fields/cost"}` 选择纯文本字段。原文单元和译文单元分别显式提供 `quantity_fields`，例如 `{"cost":"2"}` / `{"cost":"二"}`。支持 RFC 6901 转义和规范零起始数组下标；不支持通配符、非字符串值或 `00` 数组下标。这只核对该字段，不证明正文也保留数量。两侧依旧必须提供正常 `source` / `translation` 记录。字段不按 Markdown 渲染。
- 选择器缺失、对应单元缺失/重复、解析器不可用、空文本及未找到受支持数量均需审阅，不视为相等。未知单元、配置结构错误、重复 scope ID 或同侧端点重复属于配置错误。显式空 `scopes: []` 合法，状态为 `no_scopes_configured`；显式 `null`、空文件参数、重复 JSON 键都不是省略选项。

每条范围及其风险保留两侧 `unit_id`、选择器、输入记录的 `field_pointer`、提取全文和数量引文。Markdown 还保存完整原始字段及 `ast_paths`。token 的 `start/end` 是 `extracted_text` 内 Unicode 码点的半开区间，**不是原始 Markdown 偏移**。某侧无法提取时仍保存其定位与原因，并保留另一侧已有证据。

### 有意收窄的数字支持

- 支持无符号阿拉伯整数及全角数字；中文常规整数 0–9999（含两/兩/〇的等价写法）；英文 0–99 的常见基数写法及 once/twice。
- 骰式作为一个整体：`d6` 与 `1d6`、大小写和空格等可归一化，支持一个可选整数加减修正，不把 `2d6` 拆成 `2` 和 `6`。既有交付门禁仍另行要求保留原始骰式，因此数量表面相同的 `d6` → `1d6` 仍可能被原门禁拦住，本选项不放宽旧规则。
- 多个数量按原顺序、类型和重复次数比较，不只比较集合。合法调序也可能产生待审风险；数量对应的主体、资源、单位、条件、范围与正负语义仍须实际阅读确认。
- 小数、分数、百分比、范围、符号整数、分组数字、序数、复杂骰式、额外算式和未支持的 Unicode 数字等保留为不确定线索，不把已识别的复杂形式拆成普通整数后宣称相等。`负二`、`two-thirds`、`two point five`、`1 000` 等均需审阅。`一百二` 等简写及 `一旦/一起/统一/两者` 等可能不是数量的中文词汇也不会直接认作已确认数字。
- 这不是完整自然语言数字解析器，有限词法不能识别所有数量概念、习语或特殊写法。人工范围选择、未检测到的表达和文本语义仍需复核。即使 `quantity_surface_match`、没有风险或显式空配置，报告始终 `semantic_verified: false`；相同数字绝不证明译文正确。

### 在新运行中启用

```bash
python experiments/context_contract/delivery_gate.py prepare cases.json ../translation-trial-runs/new-quantity-run --quantity-scopes quantity-scopes.json
# 或与 PBRES 名称绑定同时启用：
python experiments/context_contract/pbres_names.py prepare cases.json resources.json ../translation-trial-runs/new-quantity-run --bindings name-bindings.json --quantity-scopes quantity-scopes.json
```

后续沿用对应入口的 `polish` 以及 `delivery_gate.py release`。配置和指引进入两个生成分支、候选精修及基线审阅；release 对实际冻结交付再次核对，单独输出 `quantity_risk_checks`，不混入术语/名称 findings 或语义错误计数。任一启用范围需审阅，都会阻止作为干净成稿通过。配置、实现和输入包内的配置哈希一同锁定；删改配置或注册信息、改写已冻结输出会阻止重新通过，并先撤销旧的通过状态。

`prepare` 的最终交付结构只有 Markdown，所以任一侧 `field` 选择器都会在创建运行目录前拒绝；字段检查仅用于独立 `scan` / PBRES `check`。API 为 `scan_records(..., quantity_scopes=配置)`、`prepare(..., quantity_scopes=配置)`，PBRES 的 `prepare/check` 接受同名可选参数；省略与显式 `None` 不等价。

## 已知边界

- 校验表与资源一致、绑定与父资源一致，不代表人工资源归属正确。若调用者把同名单元的父资源和绑定一起填错，工具不能从字面证明这种错误；资源边界、父子归属、名称译法和所选位置仍须人工确认。
- 绑定只证明显式位置与表一致，不识别每个正文实体、不补全正文提及、不证明原文每个名称都已覆盖。未绑定单元及未绑定正文不会被强制加名称或标题；没有绑定配置时保持原有行为。
- 本地哈希用于发现运行输入及规则的不一致，不能抵御有人同时重写整个清单、输入包和全部哈希的恶意行为，不是签名或外部可信证明。
- 精修继续使用代码内原始政策；不包含后续实验政策、既有评审材料或效果承诺。
- 结构、字面引文及模型自述核对不证明语义正确。源文歧义、事实完整性、命名和口语自然度仍须独立审阅。
- 不宣称普遍优于原流程或节省人工审阅时间，不自动外发、推送或修改线上资源。
