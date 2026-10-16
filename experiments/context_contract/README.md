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

两侧都只有不确定数量表达、没有受支持 token 时，只列 `quantity_not_comparable`，不再重复列 `no_comparable_quantities`；例如 `10/17` 对 `10/17` 或 `11/18` 都仍须人工审阅并阻止通过，不能据此认为两种表达相等。两侧都没有受支持 token，且任一侧连不确定数量证据也没有时，仍保留缺少可比较数量的提示；已有受支持 token 的顺序差异也照常报告。这只减少重复说明，不减少需审范围或证明人工审阅已完成。

### 范围与证据

- `unit`：显式选择该单元的完整 Markdown。推荐短规则单元，不能代替人工核对范围。
- `block`：`{"kind":"block","block":1}` 选择各自 CommonMark AST 的一个顶层块。原文与译文可以使用不同索引；不会自动按行或词面配对。支持普通段落、Plain 和标题，以及其中的加粗、斜体和链接可见文字。列表、引用、代码、图片、原始 HTML 等未支持结构返回范围不可核对，不能提供或隐藏数量证据。链接目标、标题、引用定义和裸 URL 不参与数量比较。可用 `pandoc --from=commonmark --to=json` 检查索引。
- `field`：已有结构化记录可用 `{"kind":"field","pointer":"/quantity_fields/cost"}` 选择纯文本字段。原文单元和译文单元分别显式提供 `quantity_fields`，例如 `{"cost":"2"}` / `{"cost":"二"}`。支持 RFC 6901 转义和规范零起始数组下标；不支持通配符、非字符串值或 `00` 数组下标。这只核对该字段，不证明正文也保留数量。两侧依旧必须提供正常 `source` / `translation` 记录。字段不按 Markdown 渲染。
- 选择器缺失、对应单元缺失/重复、解析器不可用、空文本及未找到受支持数量均需审阅，不视为相等。未知单元、配置结构错误、重复 scope ID 或同侧端点重复属于配置错误。显式空 `scopes: []` 合法，状态为 `no_scopes_configured`；显式 `null`、空文件参数、重复 JSON 键都不是省略选项。

每条范围及其风险保留两侧 `unit_id`、选择器、输入记录的 `field_pointer`、提取全文和数量引文。Markdown 还保存完整原始字段及 `ast_paths`。token 的 `start/end` 是 `extracted_text` 内 Unicode 码点的半开区间，**不是原始 Markdown 偏移**。某侧无法提取时仍保存其定位与原因，并保留另一侧已有证据。

### 有意收窄的数字支持

- 支持无符号阿拉伯整数及全角数字；中文常规整数 0–9999（含两/兩/〇的等价写法）；英文 0–99 的常见基数写法及 once/twice。
- 另支持独立、符号与数字之间没有空白的带符号阿拉伯整数，例如数据块的 `Aquatic +3`、`ATK: -3`。全角数字/符号、前导零及 Unicode 减号 `−` 可归一化，但显式正负号始终保留：`+3`、`-3`、`3` 彼此不同，`+0` 与 `-0` 也不同；删号、改号、改数、漏项或重复仍须审阅。这只比较带符号字面值，不认定无符号数与加值语义等价。连续标识符、双符号、前后算符以及 `minus -3`、`negative +3`、`负 +3` 等上下文不从尾部抽出一个可比较整数；`- 3`、小数、范围、分数、文字负数仍不支持。原始引文和偏移保留不变。
- 仅额外支持一个收窄的机制写法：`clear a HP` / `clear an HP` 中的冠词按整数 1 比较，保留原冠词引文及其真实偏移。`clear` 前须为文本开头或空白，词间仅允许水平空白；`HP` 后须为文本结束，或后接空白/文本结束的句号、问号、感叹号、分号。这不会跨 Markdown 段落补全表达，也不把所有 `a/an` 都当作 1。`a target` 等普通冠词不计数；独立 `a/an HP` 不满足上述框架时（如 `a HP threshold`、`clear a HP-related effect`、逗号续句）保留为不确定线索。其他动作、资源、复数、复合词及句式不由这条规则自动推断，仍须人工审阅。
- 骰式作为一个整体：`d6` 与 `1d6`、大小写和空格等可归一化，支持一个可选整数加减修正，不把 `2d6` 拆成 `2` 和 `6`。既有交付门禁仍另行要求保留原始骰式，因此数量表面相同的 `d6` → `1d6` 仍可能被原门禁拦住，本选项不放宽旧规则。
- 多个数量按原顺序、类型和重复次数比较，不只比较集合。合法调序也可能产生待审风险；数量对应的主体、资源、单位、条件、范围与正负语义仍须实际阅读确认。
- 小数、分数、百分比、范围、分组数字、序数、复杂骰式、额外算式和未支持的 Unicode 数字等保留为不确定线索，不把已识别的复杂形式拆成普通整数后宣称相等。`负二`、`two-thirds`、`two point five`、`1 000` 等均需审阅。`一百二` 等简写及 `一旦/一起/统一/两者` 等可能不是数量的中文词汇也不会直接认作已确认数字。
- 这不是完整自然语言数字解析器，有限词法不能识别所有数量概念、习语或特殊写法。人工范围选择、未检测到的表达和文本语义仍需复核。即使 `quantity_surface_match`、没有风险或显式空配置，报告始终 `semantic_verified: false`；相同数字绝不证明译文正确。

### 在新运行中启用

```bash
python experiments/context_contract/delivery_gate.py prepare cases.json ../translation-trial-runs/new-quantity-run --quantity-scopes quantity-scopes.json
# 或与 PBRES 名称绑定同时启用：
python experiments/context_contract/pbres_names.py prepare cases.json resources.json ../translation-trial-runs/new-quantity-run --bindings name-bindings.json --quantity-scopes quantity-scopes.json
```

后续沿用对应入口的 `polish` 以及 `delivery_gate.py release`。配置和指引进入两个生成分支、候选精修及基线审阅；release 对实际冻结交付再次核对，单独输出 `quantity_risk_checks`，不混入术语/名称 findings 或语义错误计数。任一启用范围需审阅，都会阻止作为干净成稿通过。配置、实现和输入包内的配置哈希一同锁定；删改配置或注册信息、改写已冻结输出会阻止重新通过，并先撤销旧的通过状态。

`prepare` 的最终交付结构只有 Markdown，所以任一侧 `field` 选择器都会在创建运行目录前拒绝；字段检查仅用于独立 `scan` / PBRES `check`。API 为 `scan_records(..., quantity_scopes=配置)`、`prepare(..., quantity_scopes=配置)`，PBRES 的 `prepare/check` 接受同名可选参数；省略与显式 `None` 不等价。

## 可选：只读配置预览与未确认草稿

`config_preview.py` 是独立、离线的辅助入口，不加入默认流程，也不运行名称核对、数量比较或语义检查。用途仅是把已有资源名称路径和两侧真实 AST 位置摆出来，减少重复填写资源/单元 ID、JSON Pointer、标题级别和选择器结构。资源与单元 ID 必须由调用者明确提供；选择它们、点击或填写索引均不代表人工已经确认归属、对齐或同名实体身份。

先预览一个显式选择的资源及单元。输入仍是上文的 `resources.json`、源文记录数组 `sources.json` 和含 `units` 的 `translations.json`，两侧须有同一个选定单元 ID：

```bash
# 输出只写 stdout；如需保存，必须用新的独立文件，不能覆盖任何输入或已有运行文件。
# Bash 的 noclobber 可防止下面的 > 覆盖已存在的普通文件。
set -C
python experiments/context_contract/config_preview.py preview resources.json sources.json translations.json --resource-id r1 --unit-id s > ../translation-trial-runs/new-config-preview.json
```

预览提供：

- `name_choices`：所选资源的真实 `resource_id + name_pointer`、中文名、原名及 absent/empty 状态。每个路径保留独立选择编号，同名特性不会合并，也不搜索或推荐另一个父资源。
- `sides.source` / `sides.translation`：各自完整原始 Markdown、记录位置、AST 哈希与顶层 `blocks`。`block` 始终是真实的零起始 AST 索引；列表、引用、代码等不支持选择的块仍保留在列表中，不会过滤后重新编号。两侧不自动配对，不能假设相同索引表示相同内容。
- 每块包含原始 AST；可用位置另列 `name_candidate` / `quantity_candidate` 与可见文本，不可用位置列出原因。这里只表示现有选择器能提取该位置，不表示它是正确名称、含数量或已核对机制。链接目标不作为可见文字；后缀不自动剥除。
- 输入的规范 JSON 哈希、解析器版本和实现哈希。哈希基于 UTF-8、键排序、紧凑分隔的 JSON，并非文件字节，因此仅改变 JSON 排版或对象键顺序不会使预览过期。正文、结构、资源、其他输入记录或相关实现变化则须重新预览。

随后只按本次预览中实际显示的编号选择，生成始终未确认的组合草稿。例如合成示例中，主名是 choice 0，某特性是 choice 2，原文规则在 block 2，译文标题在 block 0，译文特性在 block 3：

```bash
python experiments/context_contract/config_preview.py draft resources.json sources.json translations.json ../translation-trial-runs/new-config-preview.json --name 0 0 --name-with-suffix 2 3 ' - 反应' --quantity 2 3 > ../translation-trial-runs/new-config-draft.json
```

这次只填写名称选择号、目标块号及原译文各自块号；资源/单元 ID 从预览读取，名称路径和标题级别从实际结构取得，不必再次手写完整 JSON。上面的编号只是合成示意，必须换成本次预览中的实际位置。`--name NAME TARGET_BLOCK` 可重复；`--name-with-suffix NAME TARGET_BLOCK LITERAL_SUFFIX` 只接受人工明确输入且标签实际具有的后缀；`--quantity SOURCE_BLOCK TARGET_BLOCK` 可重复。辅助入口仅提供顶层 Markdown 块，不生成 `unit` 或结构化 `field` 选择器，不把裸文本、嵌套块或不支持的标记假装成受支持名称。

草稿使用独立的 `pbres-config-draft-v1` 外壳，包含完整预览、未确认的父资源提议，以及 `proposed_name_bindings` / `proposed_quantity_scopes`。每项始终 `approval_status: "unconfirmed"`，并保留名称预期/观察文字和两侧所选内容供人查看。不存在批准、转换或导出正式配置的命令，也没有可直接取出的正式配置子对象。草稿及预览整体都不满足现有 `--bindings` / `--quantity-scopes` 格式，不能直接用于 `prepare`、独立检查或后续发布门禁；人工独立核对后，仍须按前述正式格式另外整理配置。

有效索引也可能选错父资源、同名特性或原译文段落。这样的选择仍只是未确认提议，字面相等也不会获得“已确认”状态。未知/缺失/重复 ID、越界或布尔索引、重复端点、不支持的块、重复 JSON 键、解析器不可用，以及已修改或过期的预览都会失败并返回退出码 2，不会输出半份草稿。新增段落等结构变化后，旧索引不得继续使用，须重新预览、重新查看、重新选择。哈希用于检查本地一致性，不是身份认证、审批记录或签名。

工具不修改输入，不创建或覆盖文件，不访问网络。它没有 `--out`；shell 重定向在程序启动前就可能截断文件，因此不要把输入路径、其符号链接/硬链接别名或已有运行文件放在 `>` 后。保留原输入与已有运行，仅在仓库外另存新预览和新草稿。

### 离线 HTML 高亮审阅

将上述未确认草稿渲染为单文件 HTML，直接用浏览器打开，不部署网站，也不上传数据：

```bash
python experiments/context_contract/render_config_preview.py ../translation-trial-runs/new-config-draft.json ../translation-trial-runs/new-config-draft.html
```

也可以渲染前述 `delivery_gate.py scan --output quantity-review.json` 生成的现有数量报告，或 `pbres_names.py check` 保存的完整检查 JSON。完整检查可以含名称与数量两项、只有名称、只有数量，或两项都未启用：

```bash
python experiments/context_contract/render_config_preview.py quantity-review.json ../translation-trial-runs/new-quantity-review.html
python experiments/context_contract/render_config_preview.py combined-check.json ../translation-trial-runs/new-combined-review.html
```

各类输入的高亮与证据含义不同：

- 名称草稿：只高亮人工指定的译文标题或特性名称槽位，按结构定位，不搜索第一个同名词。名称后缀和正文中的重复同名词不跟着高亮。草稿没有原文名称位置选择器，因此左侧保留完整原文并明确显示“未指定原文名称位置”，不伪造对应高亮；资源表原名只是参考。若该块正文含不支持的结构，仅显示提取的名称槽位，完整原始文本仍可访问。
- 数量草稿：两侧整块高亮只表示显式选择的未确认范围，页面明确提示未运行数字比较。它不是数量风险或正式范围配置。
- 已有数量报告：在两侧的 `extracted_text` 中，按保存的 Unicode 码点区间精确高亮每个数字/骰式证据及不确定表达，保留重复出现的位置；逐项验证引文、偏移、边界和非重叠条件。绝不把这些偏移套到原始 Markdown。显示单元 ID、各侧选择器、字段路径与 AST 位置；无法提取的一侧如实留空并说明原因，另一侧证据继续显示。数量表面相同也标为语义未核对。
- 完整检查：先列顶层 `release_allowed`、基础交付阻断项和每个可选检查是否提供，再分别显示全部名称结果/配置错误与数量结果。顶层门禁状态在静态页及交互阅读提示中保留；数量无风险不会盖掉名称失败，名称无问题也不会盖掉数量或基础交付阻断。没有启用的检查明确标为未提供，不算通过；保存的顶层状态与子项矛盾时明确提示核对，不改写输入结果。
- 实际名称检查行：保留资源 ID、名称路径、选择器、期望值、实际值及 `bound_name_mismatch` 等问题。期望值是资源表中文名，不冒充原文；`actual` 缺失与已提取的空字符串分别说明。现有检查载荷不含原文正文、完整译文及可靠字符偏移，因此只显示已保存的提取值，不借用数量上下文或搜索同名词补造高亮。此证据缺口不影响显示名称失败。

渲染器不扩大数量词法或将风险自动改判为通过。上面的收窄 `clear a/an HP` 规则只由数量扫描器应用；渲染器如实显示已保存的冠词引文与数值。旧报告不会被重新计算或追改；其他未支持的冠词句式仍可能留下需要人工核对的风险，即使两侧语义相同。

所有条目的原译文、精确高亮、待核对说明和完整原始 Markdown 都在生成时写入静态 HTML；关闭或无法启动 JavaScript 时仍可完整阅读。高亮同时使用背景色、加粗和下划线，低功能渲染器也可辨认。文本逐片段安全转义，CR/CRLF 的回车使用字符引用保留，避免 HTML 换行规范化破坏原始码点位置；显示文本若含 HTML 无法无损保存的 NUL 字符则拒绝生成，不静默替换。

JavaScript 仅在首次成功绘制后接管为 `daggerheart-translation-audit` 的逐条审阅页面、精准高亮和独立滚动框；初始化失败时静态全文继续可见，不显示失效控件，也不重复展示两套界面。交互模式下完整原始 Markdown 保留在“关联上下文与依据”；“完成”只保存阅读进度，不批准配置、不改变待核实性质、不修改输入或证明翻译正确。`file://` 下浏览器持久存储不保证可靠，可导出进度 JSON 备份。空范围、空队列和配置错误不会显示成审阅通过。

渲染器只读保存的快照，不重新比对当前项目文件、不运行扫描或自动对齐。草稿要求未确认状态并校验内嵌预览哈希与所选证据；数量报告验证引文对应关系，但两者都不是签名或人工审批记录。生成页使用安全文本节点，不执行输入中的 HTML，不引入外部链接、脚本、字体或图片；CSP 仅允许内嵌的固定审阅脚本与样式，禁止网络请求。输出必须是尚不存在的新文件，已有文件及输入路径一律拒绝覆盖。预览清单本身不能直接渲染，需先显式选择形成草稿；渲染不提供批准或导出正式配置功能。

回归检查：

```bash
python -m unittest discover -s tests -p test_render_config_preview.py -v
node skills/daggerheart-translation-audit/tests/test_highlighting.js
node skills/daggerheart-translation-audit/tests/test_report_state.js
node skills/daggerheart-translation-audit/tests/test_scroll_panes.js
```

测试包含静态全文与码点高亮还原、无脚本/XSS、初始化成功/失败及交互状态；安装了可选 `lxml` 时另跑 HTML 分词器的 CRLF/CR 保真回归。结构与模拟 DOM 测试不等于真实浏览器视觉验收；静态 PDF/PNG 栅格检查也不证明浏览器交互。交付时应分别记录静态像素、实际浏览器是否成功渲染、两侧滚动与完成/撤销/刷新是否验证。

## 已知边界

- 校验表与资源一致、绑定与父资源一致，不代表人工资源归属正确。若调用者把同名单元的父资源和绑定一起填错，工具不能从字面证明这种错误；资源边界、父子归属、名称译法和所选位置仍须人工确认。
- 绑定只证明显式位置与表一致，不识别每个正文实体、不补全正文提及、不证明原文每个名称都已覆盖。未绑定单元及未绑定正文不会被强制加名称或标题；没有绑定配置时保持原有行为。
- 本地哈希用于发现运行输入及规则的不一致，不能抵御有人同时重写整个清单、输入包和全部哈希的恶意行为，不是签名或外部可信证明。
- 精修继续使用代码内原始政策；不包含后续实验政策、既有评审材料或效果承诺。
- 结构、字面引文及模型自述核对不证明语义正确。源文歧义、事实完整性、命名和口语自然度仍须独立审阅。
- 不宣称普遍优于原流程或节省人工审阅时间，不自动外发、推送或修改线上资源。
