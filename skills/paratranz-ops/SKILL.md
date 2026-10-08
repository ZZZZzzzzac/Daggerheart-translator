---
name: paratranz-ops
description: 通过 ParaTranz API 操作 paratranz.cn 上的 Daggerheart 翻译项目（项目 14448）：查文件翻译进度、拉词条快照、写回译文、对账、读取术语表。Use when the user asks to 拉/回写/同步/对账 ParaTranz，问某文件线上翻了多少、还有多少没翻，或要求把本地译文直接更新到 paratranz.cn。
---

# ParaTranz 操作

线上项目：`14448` = Daggerheart-匕首之心 非官方本地化（en → zh-cn，privacy 内部）。

所有线上操作都走本技能的 `scripts/para.py`，不要另写一次性 requests 脚本。
凭证只从仓库根目录 `.env` 的 `PARATRANZ_TOKEN` 读取，脚本不回显、不落盘。

```bash
PY=.venv/Scripts/python.exe
P=.claude/skills/paratranz-ops/scripts/para.py
$PY $P files                 # 全项目文件 + 进度
$PY $P stats 3347716         # 单文件进度
$PY $P pull 3347716 --out projects/Daggerheart-Core-Rulebook/paratranz/xxx.snapshot.json
$PY $P push 3347716 updates.json            # 只出计划（dry-run）
$PY $P push 3347716 updates.json --apply    # 真写
$PY $P diff 3347716 updates.json            # 对账，有差异退出码 1
$PY $P terms --out terms.json
$PY $P issue 23387 --out issue.json         # 拉讨论主楼 + 全部楼层（翻译口径常在楼层里）
$PY $P edit-strings plan.json --apply       # 按 id 改词条，可显式设 stage（唯一能保状态的写路径）
```

**逐条写入（怕干扰别人编辑时用这个）**：每条都先 `GET /strings/{id}` 重读线上 → 校验要改的那行仍是计划里的旧值
（对不上就跳过，不覆盖别人的改动）→ 只替换这一行 → 用刚读到的 stage 写回 → 再读一次核对。
范本：`projects/Daggerheart-Core-Rulebook/scripts/apply_srd2_motive_writeback.py`、计划文件 `_motive_impulse/writeback_plan.json`。

## 铁律

1. **token 只待在 `.env`**（已被 gitignore）。用户口头给的 token 写进 `.env` 后即弃，不写进任何被跟踪的文件、不回显到聊天或日志。
2. **读随便读，写先快照**。任何写回前，`para.py push --apply` 会自动把线上全量词条存到 `projects/.paratranz_backup/<fileId>-<UTC>.snapshot.json`，并在输出里打印路径——它是这次写回的回滚基准，报告里必须带上。
3. **默认 dry-run**。`push` 不加 `--apply` 只出计划，计划要能说清「写入 N / 跳过 M / 原因」。
4. **默认 `force=false`**：只填空词条，不碰人工译文。`--force` 会覆盖人工译文，只有用户明确要求「覆盖线上」时才用，且用时要在报告里写明。
5. **要保 stage 就走按 id 的批量接口**。文件导入（`push`）即使每条带上 `stage` 也会被服务端忽略，实测 stage 3 → 1；
   要保住「已检查/已审核」，必须用 `edit-strings`（`PUT /strings`，`items[]` 带 `id` + `translation` + `stage`），
   实测能把 stage 写回原值。只有确实想让词条重新走校对（例如整段重译）时才让状态归 1，做之前必须告诉用户。
6. **写完必须回读**。`push --apply` 内置回读核对，逐 key 与本地比对；对不上就退出码 1，不要当作成功。
7. **串行、低频**。全局 480 req/min；`suggestions` 接口开销大，必须一次一条串行调用，不要并发或轮询。
8. **权限边界**：读词条数据、写文件翻译需项目成员/管理员权限，当前 token 满足；权限不足时 API 返回 403，不要靠改参数绕过。

## 回写流程

按顺序做完，每一步都有可判定的完成条件。

1. **定位文件** — `para.py files [--match 关键词]`，从文件名拿到 `fileId`，并记下 `modifiedAt`。
   完成条件：拿到线上 fileId，且 `modifiedAt` 与上次本地记录一致（不一致说明有人在动，先拉最新）。
2. **拉最新快照** — `para.py pull <fileId> --out <项目>/paratranz/<name>.snapshot.json`。
   完成条件：快照条数等于 `stats` 的 `total`。
3. **造写回包** — JSON 数组 `[{"key": "...", "translation": "..."}]`；用快照的 `key` 对齐，只放真正要改的条目。
   完成条件：每个 key 都能在快照里找到，译文非空。
4. **预演** — `para.py push <fileId> <updates.json>`。
   完成条件：计划里「线上不存在该 key」「本地译文为空」两项都是 0；「线上已有译文」若非空，就是需要用户点头的部分。
5. **写回** — 用户确认后 `para.py push <fileId> <updates.json> --apply`。
   完成条件：脚本回读核对 100% 一致，退出码 0；报告里带上快照路径与 stage 重置提醒。
6. **收尾** — 需要时把写回的译文同步回仓库工件（`.md.json`、`data/`、卡包），别让线上和仓库分叉。

批量写多个文件时逐文件 `push`，一个文件一次提交；不要把不同文件的词条混在一个包。

## 提取类任务：先落原文，再手工归一化

要从词条里**抽字段**（动机与战术、趋向、特性、数值块……）时，走三步，不要在正则上反复挣扎：

1. **dump** — 把标签行连着折行原样倒进一个可读文本（如 `raw_fields.md`）+ 一份机械归一化的 TSV。
   dump 只允许一条笨规则判断「下一行是不是新字段」（如：去掉前导 `*` 后前 16 字符内有冒号）。
2. **手工归一化 TSV** — 凡是 dump 标记 `!` 的行（中英条数不符、缺译文、值被吞），直接在 TSV 里改字：
   重新断句、补 `;` 分隔、或标 `!manual` 排除并写清原因。人/AI 改文本比写正则便宜得多。
3. **解析** — 解析器只做两件事：按 `\t` 拆列、按 `;` 拆条目。格式怪异的行全部在前面被改掉了，
   解析器里不该再出现针对格式变体的正则分支。

现成范例：`projects/Daggerheart-Core-Rulebook/scripts/dump_srd2_fields.py`（dump，默认不覆盖已手工改过的 TSV）
→ `.../_motive_impulse/fields.tsv`（手工归一化）
→ `projects/Daggerheart-Core-Rulebook/scripts/build_srd2_motive_impulse_table.py`（只读 TSV）。

## 常见任务 → 动作

| 用户说 | 动作 |
|---|---|
| 「线上翻到哪了 / 还剩多少」 | `para.py files`、`para.py stats <fileId>` |
| 「拉最新译文下来加工」 | `para.py pull <fileId>`，再走 `pipeline/converter.py` 等本地流程 |
| 「把本地这批译文写回 para」 | 上面的回写流程（steps 1–6） |
| 「核对线上和本地是否一致」 | `para.py diff <fileId> <local.json>`，退出码 0 才算一致 |
| 「更新/导出术语表」 | `para.py terms --out ...`；`daggerheart-translation-pipeline/resources/terms-14448.json` 是上一版快照 |
| 「看某条讨论里的翻译口径」 | `para.py issue <id> --out issue.json`，楼层在 `floors[]` |
| 「下载整包工件」 | 不走本技能：`python pipeline/00_download_and_convert.py` 或 `pipeline/download_paratranz.py`（artifacts 接口，按目录映射落到 `projects/`） |
| 「在 para 上新建/上传文件」 | `para.py` 未覆盖；参考 `projects/Daggerheart-Core-Rulebook/scripts/srd2_equipment_sync.py`（先 `GET /files` 查重名，`POST /files`，再回读逐 key 校验） |

## 已知 fileId

仓库文档里被反复引用的三个：

| fileId | 文件 |
|---:|---|
| 2219845 | `SRD/DH-SRD-1.0-June-26-2025.md.json`（SRD 1.0） |
| 3347716 | `SRD/DH_SRD_2_2026_08_25.md.json`（SRD 2.0，回写记录见 `projects/Daggerheart-Core-Rulebook/source/SRD/_srd_compare/SRD2_重译清单.md`） |
| 3409913 | `SRD/DH_SRD_2_Equipment_Items.json`（装备/物品） |

规则书 CH0–CH6、`DH_FVTT/*`、`the_void/*` 等其余 60 个文件的 id 一律现查：
`para.py files --match CH4`、`--match FVTT`、`--match the_void`。

## 参考

- 接口全表、字段语义、限流与错误码：[reference/api.md](reference/api.md)
- 线上文档：<https://paratranz.cn/api-docs/>（JSON：`https://paratranz.cn/api-docs/?format=json`，OpenAPI 3.0.3，v0.5.5）
