# ParaTranz适配器数据契约（兼容既有流程）

普通文本/文件输入请先使用 [paired-inputs.md](paired-inputs.md) 的通用入口；本文件仅适用于可选ParaTranz来源。以下旧命令、字段与审阅包继续兼容。

所有示例 ID 仅作接口说明。真实工作数据不提交仓库。所有 JSON 为 UTF-8。

## 依赖与快照

离线 `diff` / `validate` 和测试只用 Python 标准库。线上 `snapshot` 导入相邻 `paratranz-ops/scripts/para.py`，需要它已有的 requests、python-dotenv 和可用凭证。不要复制/修改认证逻辑来绕过现有配置。可用 `PARATRANZ_REPO` 指向用户已有配置的项目根目录，`PARATRANZ_PROJECT_ID` 选择项目；不把 token 作为命令行参数。

`snapshot` 返回对象字段：schema_version=1、project_id、started_at、completed_at、files（选择的完整文件元数据）、project_files（项目全部文件元数据，便于复核其他版本排除）、pages（file_id/page/rows/rowCount/pageCount/sha256）、record_count、records_sha256、atomic=false、records（全量原始词条元数据）。保留 id/fileId/key/original/translation/context/version/updatedAt/stage；内容 SHA-256 基于 JSON 的 sort_keys=true、ensure_ascii=false、紧凑分隔符 UTF-8 编码。

分页的 page/pageCount/rowCount 必须一致，每条 string ID 唯一，实际数必须等于文件 total。文件列表抓取前后比较 id/name/total/modifiedAt；不一致时失败。相同修改时间也不提供事务隔离保证，故仍需交付前增量回读。脚本只在完整成功后创建输出，已存在输出会拒绝覆盖。HTTP失败或权限失败应停止并报告，不能产出成功 manifest。不得把没有原文/元信息的翻译导出当成审阅快照。

## 审阅总包 audit.json

顶层：schema_version=1、snapshot（上面的完整快照）、coverage（每个快照 ID 一条）、findings（发现数组）。

coverage 必填：id、scope（in_scope/partial/excluded）、reviewed（boolean）。已审项另填 reviewer、reviewed_at（ISO 8601 UTC）、snapshot_version、record_sha256（该完整快照record按同一canonical JSON规则哈希，避免version未变但内容已变时误算已审）。partial/excluded 填 reason；partial 另填 included_context，说明精确纳入的段落。excluded 可补 duplicate_of/related_file_id。未审项明确 reviewed=false，不伪造审阅者。

findings 必填：finding_id（跨报告版本稳定且唯一）、id（string ID）、title、status、severity、kind、problem、suggestion、original（完整导入原文）、translation（完整现译，可为空）、url、snapshot_version、record_sha256（完整record哈希，除stale外需匹配当前快照）。

- status：confirmed / uncertain / dismissed / resolved / stale
- severity：critical / high / medium / low
- kind：translation / source_import / mixed
- confirmed：second_pass 对象必须包含独立 reviewer、decision=support、reason。coverage 也须在当前版本已审。
- 已确认的 source_import/mixed：official_evidence 对象含 text（官方原文）、url、version、location（页码/节名），可加图像证据路径和源文重建说明。
- resolved：resolution_evidence（回读及重新判断的证据）、verified_at。不能把“点击完成”转换成 resolved。
- stale：保留旧发现，重新审阅前不计入当前已确认问题。若词条已从最新快照删除，添加 removal_evidence，含 removed_id、baseline_sha256、latest_sha256（来自增量diff），保留旧文本和版本；不再要求该ID出现在当前覆盖表中。

建议保留 original_excerpt、translation_excerpt、original_focus、translation_focus（完整相关能力段）、location（标题层级）、related_contexts、first_pass、second_pass、created_at、verified_at。切勿把 focus 写成脱离条件的孤立半句。

校验器拒绝缺失覆盖、重复ID、纳入范围以外的问题、非独立确认、过时文本和没有官方证据的已确认源文问题。返回问题数、不同受影响词条数、未审ID；有未审项时 CLI 退出码1。该校验只在条目级拒绝范围外问题；partial的精确段落归属、证据是否足以支持结论，以及审阅者是否真的通读，仍由人工/AI语义复核确认。

## 精准高亮（可选，兼容既有报告）

每个发现可带 `original_highlights`、`translation_highlights`，数组元素为 `{start,end,reason}`。偏移基于该发现完整 `original` / `translation` 的 Unicode code point，范围为半开区间 `[start,end)`；不是UTF-8字节、JavaScript UTF-16单元、focus或分页内偏移。reason写该片段为何属于本问题的证据。可选text字段必须严格等于全文[start:end]切片，用于防止证据定位错位。数组按start升序、无重叠，start/end必须为整数且0≤start<end≤全文字符数。

高亮只标该发现有问题的具体片段，不能对同一关键词或数字在全文全局染色。先定位完整能力段和问题证据，再选最小但足以表达差异的范围。数字错误应只覆盖相关数值及必要单位/条件；与本问题无关的同名术语保持不亮。源文导入错误亮实际串列/缺失对应位置，同时通过official_evidence解释。

漏译可能只有英文存在证据：英文标遗漏内容，中文数组留空，问题说明明确“译文缺失对应内容”；不能在中文捏造文本或随意高亮邻句来凑双侧。译文多加内容同理，不强求每侧都有范围。没有自动可定位的证据就人工核对，不用整段高亮掩盖不确定性。

全文和focus必须保持原字序及文本；focus及分段展示用对应全文位置映射，再与每页字符范围求交集绘制高亮。展示包可带original_focus_ranges / translation_focus_ranges，数组元素{start,end}使用同一全文code point坐标，按全文顺序且无重叠；每个范围依序对应original_segments / translation_segments的一个segment；若无segments，则只对应单个focus。空segment的focus锚点允许start==end（如未译侧[{start:0,end:0}]）；高亮范围仍不允许空区间。各切片用两个换行拼接必须严格等于对应focus。重复相同段落时必须提供此范围，不能默认匹配第一次。未提供范围时，renderer只允许每个focus segment在全文唯一出现，否则报错。分页后的全部文本拼接应严格还原输入，高亮跨页应保留两侧交集。数据校验器能查范围合法性，不能判断高亮选得是否准确，这仍需语义复核。

## 增量

`diff baseline.json latest.json --out delta.json` 要求相同项目和相同选定文件集合，验证快照hash后输出 added、removed、changed（字段列表）。版本、时间、stage 等变化也要评估，不能只比较译文。变更是待复核线索，不自动给出已修结论。关联条目/邻段的影响由审阅者判断。

## 展示总包

展示用JSON与审阅总包分开，映射到 [report-ui.md](report-ui.md) 所述schema。默认队列只放 confirmed/uncertain；历史 dismissed/resolved/stale 留在审阅总包，避免干扰待处理列表。reportId 在同一项目/版本/审阅范围的报告迭代中保持稳定，finding_id 不因排序或严重度变化而重编号；不同审阅项目必须隔离存储。展示的原文/现译仍保留全文，focus只是默认阅读区域。

可在工具收起区提供只读范围说明、统计与校验结果；不能把每项证据、统计、过滤器全部默认铺在屏幕上。进度 JSON 只表达本地审阅状态，不写入审阅总包的 resolved 状态。
