# 单文件逐条审阅报告

运行 `python scripts/render_report.py input.json output.html`。仅用 Python 标准库；模板、CSS、JS 从技能目录相对读取。项目数据必须留在用户项目目录，不能写回技能仓库。

## 输入 schemaVersion 1

顶层必需字段：`schemaVersion: 1`、稳定的 `reportId`、`title`、`sourceCutoff`、非空 `findings` 数组。可选 `notes`、`progressFormat`、`storagePrefix` 均为字符串。既有报告升级时保持 reportId、进度格式及存储前缀不变，才能沿用旧进度。

每项必需字段：
- `finding_id`：报告内唯一、跨版本稳定的字符串编号，不能按每次排序重编。
- `id`：原平台条目 ID，整数或字符串。
- `url`：HTTPS 原条目链接。
- `label`：所属角色、能力或装备名；`title`：具体问题标题。
- `status`：`confirmed` 或 `uncertain`；`severity`：字符串等级。
- `problem`、`suggestion`：判断及建议。
- `original`、`translation`：完整本条原文和现译；未译用空字符串。
- `original_focus`、`translation_focus`：默认展示的完整相关能力或规则段，不能只截关键词，也不能为了缩短而遗漏触发、成本、例外或限制。必须是对应全文的连续子串。
- `location`：简短位置，如正文第42条。

跨段选取时另给 `original_segments` / `translation_segments` 字符串数组，每段必须是全文连续子串；对应 focus 必须恰好为数组以两个换行连接的结果。选择范围须由语义审阅者确定，不用长度截断代替。

可选 `related_contexts` 数组：`{label,original,translation,url?}`；可选 `official_evidence`：`{text,url}`，链接只能使用 HTTPS。完整关联通则和必要官方证据通过阅读区的“关联规则与官方依据”访问。

## 阅读与分页

默认桌面1366×768和1920×1080按视口高度分为紧凑标题、并列中英、问题建议、固定操作四区。字号不随内容变小。每次用实际 DOM 字体、宽度和区域高度测量分页，完整字符按顺序保留；长段显示明确页数。完整条目和相关依据在原阅读区切换并分页，不通过裁切或省略隐藏原文。

更多菜单收纳搜索、分类、已完成管理、进度导入导出、范围和出处。默认无网络请求；来源链接一律新标签页，设置 `noopener noreferrer`。完成只记录用户审阅进度，不修改源译文。

自动保存使用每个稳定 finding ID 的独立 localStorage 键。`file://`不保证存储持久，必须在更多菜单说明并提供JSON备份。存储异常时主界面显示“保存警告”。导入先整体验证格式、报告ID、版本、日期及有效ID，失败不应用内容；成功只合并已完成项。禁止执行导入文本或将其写入HTML。

## 验证要求

运行 `python -m unittest discover -s tests`。还应对当前真实数据核对全部全文与focus来源，测试完成、撤销、刷新恢复、过滤搜索、空结果、全部完成及坏进度文件。分页测试必须确认页面拼接严格等于输入，包含Unicode和换行。

浏览器可用时，在1366×768与1920×1080测量 `document.documentElement.scrollHeight <= innerHeight`、所有当前文本区 `scrollHeight <= clientHeight`，逐页核验完整上下文可达。默认正常项不应需要滚轮。使用支持的浏览器工具；若被访问政策或环境限制阻断，不绕过，不把静态或模拟测试称作真实视觉验收，交付时明确局限。

## 精准高亮

输入可带 original_highlights / translation_highlights，元素 `{start,end,reason,text?}`。偏移是完整原文/现译的 Unicode code point 半开区间，按序且不重叠；text 若提供须与原切片一致。可用 original_focus_ranges / translation_focus_ranges（每项 `{start,end}`）明确选中哪个原文片段，逐项对应 segments 或单个 focus。重叠出现的同一字符串也属于歧义，没有明确范围时应拒绝猜测。空译文允许空 focus 锚点，但不允许空高亮。

高亮先从全文映射到选段，再与当前页求交集；不执行全文关键词替换，不改变原文。漏译允许只有英文高亮；译文缺失仅作界面说明，不能捏造中文证据。使用安全文本节点和 mark 元素绘制，reason只作为提示文字。详细数据规则见 [data-contract.md](data-contract.md)。

运行 `node tests/test_highlighting.js` 检查重复数字的特定出现位置、单侧遗漏、分段间隔、跨页范围、Unicode code point和逐字符还原；同时运行 `node tests/test_report_state.js` 保证保存/导入进度不受影响。这些模拟测试不替代真实浏览器视觉验收。
