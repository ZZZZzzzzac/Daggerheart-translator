# ParaTranz API 参考

来源：<https://paratranz.cn/api-docs/?format=json>（OpenAPI 3.0.3，v0.5.5，2026-09-19）。
本文件只保留本仓库会用到的部分；字段有疑问时以线上文档为准。

## 基础

- Base URL：`https://paratranz.cn/api`，所有路径前缀 `/projects/{projectId}`（本项目 `14448`）。
- 认证：请求头 `Authorization: Bearer {TOKEN}`，token 来自个人资料 → 设置 → API Token，**等同账号权限**。
- 限流：**每用户 480 请求/分钟**，超出返回 429。`suggestions`（翻译记忆）与机器翻译接口开销大，**必须串行**，不要并发或轮询，也不要用 `force` 反复刷缓存。
- 错误体：`{"message": "ERROR MESSAGE", "code": 10000}`（code 为 5 位业务码，部分接口不返回）。

| HTTP | 含义 |
|---|---|
| 400 | 参数错误 |
| 401 | token 错误或过期 |
| 403 | 权限不足（未登录、非成员、或权限等级不够） |
| 404 | 资源不存在（私密项目对非成员也返回 404） |
| 405 | HTTP 方法用错 |
| 423 | 文件正被其他用户更新/回滚，稍后重试 |
| 429 | 触发限流 |
| 5xx | 服务端问题；502 常见于网络受限 |

## 枚举

- `stage`（词条状态）：`0` 未翻译 / `1` 已翻译 / `2` 有疑问 / `3` 已检查 / `5` 已审核 / `9` 已锁定（仅管理员可解锁，强制按译文导出）/ `-1` 已隐藏（强制按原文导出）。
- `permission`（成员权限）：`1` 翻译者 / `2` 校对者 / `3` 管理员 / `10` 所有者。
- `Project.download`（导出包下载权限）：`0` 私密（仅管理员）/ `1` 内部（成员）/ `2` 公开。

## 词条读写（本仓库主路径）

### `GET /projects/{projectId}/files`
文件列表，含每个文件的 `id / name / format / total / translated / disputed / checked / reviewed / hidden / locked / words / hash / modifiedAt`。
用它定位 fileId 与进度；`modifiedAt` 变化 = 有人改过词条。

### `GET /projects/{projectId}/files/{fileId}`
单文件信息，字段同上。

### `GET /projects/{projectId}/files/{fileId}/translation` — 全量词条
语义：导出该文件**全部**词条（不分页），返回 `TinyString[]`：`id / key / original / translation / stage / context`。
注意：
- 响应以附件形式下载（`Content-Disposition`），`requests` 里 `.json()` 可直接解析。
- 需项目成员权限（v0.5.3 起收紧）。

### `POST /projects/{projectId}/files/{fileId}/translation` — 写回译文
只改译文，不动原文；原文/上下文一律沿用库中现值。

**匹配规则**：按 `key` 匹配；`yml`/`rimtxt`/`krtxt` 格式忽略 key 末尾的 `:N`。**导入内容中新出现的 key 不会被创建**——新词条必须先上传原文文件。

**跳过规则**（未指定 `force` 时）：译文为空、译文与原文相同、译文与现有译文相同且词条状态不是未翻译、以及已由人工翻译过的词条，都会被跳过。

请求体两种：

```jsonc
// application/json
{
  "items": [{"key": "unique_key", "translation": "译文", "stage": 1}],  // stage 可省，按译文是否为空推导
  "filename": "DH_SRD_2_2026_08_25.md.json",   // 必填，需带扩展名以识别格式
  "hash": "…",    // 可选，与上次导入 hash 相同则返回 hashMatched
  "force": false, // 可选，强制覆盖人工译文
  "skip": false   // 可选，跳过哈希校验
}
```

**stage 会在导入时被重推**：文件导入路径即使 `items[].stage` 传了线上当前值，服务端也**忽略它**，
实测把 stage 3 的条目写成 stage 1（2026-09-22，file 3347716 / SRD2_SECTION_415）。
历史上的「写回重置 stage」就是这个原因（文件上传路径连 stage 字段都没有）。

**要保住状态就走按 id 的批量接口**（见下方 `PUT /projects/{projectId}/strings`）：`items[]` 带 `id` + `translation` + `stage`，
实测能把 stage 写回原值（同一条 415：1 → 3 成功）。保状态的逐条写入流程见技能正文。

```bash
# multipart/form-data：file + filename? + path? + force? + skip?
curl -H "Authorization: Bearer $PARATRANZ_TOKEN" \
  -F "file=@out.json;filename=DH_SRD_2_2026_08_25.md.json" -F "force=false" \
  https://paratranz.cn/api/projects/14448/files/3347716/translation
```

响应：成功返回 `{revision, file}`；以下情形返回 `{"status": ...}` —— `hashMatched`（内容无变化）、`unchanged`（无需更新）、`empty`（不含词条）。
权限：**写译文需管理员以上**；文件被占用返回 423。

### `POST /projects/{projectId}/files` — 上传新文件
`multipart/form-data`：`file`（文件名决定线上名）+ `path`（目录，如 `SRD/`）。文件名不能与 `path` 下已有文件冲突。返回 `{file, revision}`。
上传后必须 `GET .../translation` 回读逐 key 校验；重名时**不要**重建文件，先 `GET /files` 查证。

### `POST /projects/{projectId}/files/{fileId}` — 更新原文
仅更新原文，不动译文（改译文用上面的接口）。`skip` 跳过哈希校验，`incremental` 增量更新（默认 `false`：新文件中不存在的词条会被删除）。内容无变化返回 `{"status": "hashMatched"}`。

### `GET /projects/{projectId}/strings` — 分页词条
查询参数：`page`（默认 1）、`pageSize`（默认 50，最大 800）、`file`（文件 ID）、`stage`、`detailed`。
返回：`{results, page, pageSize, rowCount, pageCount}`。

### `PUT /projects/{projectId}/strings` — 批量改/删词条
`op=edit` 配合 `items`（每项含 `id`，可选 `key/original/translation/stage/context`），返回被更新的 id 数组；`op=delete` 配合 `id` 数组，仅管理员。
权限：改 key/原文/上下文、隐藏或锁定词条仅管理员；标记已审核或修改已审核词条需校对以上；**翻译者只能改未审核词条的译文/状态**。

### `GET /projects/{projectId}/strings/{stringId}` / `PUT` / `DELETE`
单条读取、更新、删除（删除仅管理员）。单词条用 `PUT` 时直接提交 `StringItem`。

### `GET /projects/{projectId}/strings/{stringId}/suggestions` — 翻译记忆
参数：`scope`（`self` 当前项目 / `my` 我加入的项目 / `all` 关联项目）、`rate`（最低匹配率，默认 70，`0` 表示不过滤）、`ignore`（忽略的项目 ID）、`force`（跳缓存，仅排障）。
最多返回 30 条，含 `matching`（0~1）、`contains`、`others`（同文多译）。
**串行调用**：这是全 API 里最容易被限流/超时的接口。

## 导出与术语

### Artifacts — 整包工件
- `GET /projects/{projectId}/artifacts`：历史导出结果列表。
- `POST /projects/{projectId}/artifacts`：触发导出（异步任务）。
- `GET /projects/{projectId}/artifacts/latest`：最近一次导出结果。
- `GET /projects/{projectId}/artifacts/download`：下载 zip。包内是 `utf8/<线上目录结构>/<文件>`，`pipeline/download_paratranz.py` 依赖这一结构做目录映射。

### Terms — 术语表
- `GET /projects/{projectId}/terms`：分页；`pageSize` 可放大（本仓库用 1000 一次拉完）。
- `POST /terms`：新建；`PUT /terms`：批量导入。
- `GET | PUT | DELETE /projects/{projectId}/terms/{termId}`：单条。
- `GET /projects/{projectId}/terms/{termId}/history`：术语改动历史。

## 其余端点（57 个的完整清单）

| 方法 | 路径 | 说明 |
|---|---|---|
| GET / POST | `/projects` | 项目列表 / 创建项目 |
| GET / PUT / DELETE | `/projects/{projectId}` | 项目信息 / 更新 / 删除 |
| GET | `/projects/{projectId}/files` | 文件列表 |
| POST | `/projects/{projectId}/files` | 上传文件 |
| GET / POST / PUT / DELETE | `/projects/{projectId}/files/{fileId}` | 文件信息 / 更新原文 / 改文件名 / 删除 |
| GET | `/projects/{projectId}/files/{fileId}/content` | 原文内容与归档（`rev` 指定历史，`tid` 取词条所属原文版本并附 `highlight`，`dl` 直接下载） |
| GET / POST | `/projects/{projectId}/files/{fileId}/translation` | 词条数据 / 更新译文 |
| GET | `/projects/{projectId}/files/revisions` | 文件上传、更新、删除历史 |
| GET | `/projects/{projectId}/history` | 项目历史（`uid`/`tid`/`type`=translate,edit,check,review,term,import,comment/`begin`/`end`/`keyword`；**指定 `tid` 后分页失效**） |
| GET | `/projects/{projectId}/strings` | 词条列表 |
| POST | `/projects/{projectId}/strings` | 创建词条（管理员） |
| PUT | `/projects/{projectId}/strings` | 批量修改 / 删除 |
| GET / PUT / DELETE | `/projects/{projectId}/strings/{stringId}` | 单条词条 |
| GET | `/projects/{projectId}/strings/{stringId}/suggestions` | 翻译建议（串行） |
| GET / POST / PUT | `/projects/{projectId}/terms` | 术语列表 / 创建 / 批量导入 |
| GET / PUT / DELETE | `/projects/{projectId}/terms/{termId}` | 单条术语 |
| GET | `/projects/{projectId}/terms/{termId}/history` | 术语历史 |
| GET | `/projects/{projectId}/artifacts` | 导出结果列表 |
| POST | `/projects/{projectId}/artifacts` | 触发导出 |
| GET | `/projects/{projectId}/artifacts/latest` | 最近导出结果 |
| GET | `/projects/{projectId}/artifacts/download` | 下载导出包 |
| GET / POST | `/projects/{projectId}/members` | 成员列表 / 添加成员 |
| PUT / DELETE | `/projects/{projectId}/members/{memberId}` | 改成员权限 / 移除 |
| GET | `/projects/{projectId}/scores` | 成员贡献（PP）：翻译 1、编辑 0.5、审核 0.2，乘数 `1+(词数-1)*0.1` |
| GET / POST | `/projects/{projectId}/issues` | 讨论列表 / 发起讨论 |
| GET / PUT / POST / DELETE | `/projects/{projectId}/issues/{issueId}` | 讨论详情 / 修改 / 操作（回复、关闭）/ 删除 |
| GET / POST | `/projects/{projectId}/announcements` | 公告列表 / 发布 |
| GET / PUT / DELETE | `/projects/{projectId}/announcements/{announcementId}` | 公告详情 / 更新 / 删除 |
| GET / POST | `/mails` | 私信列表 / 发送 |
| GET | `/mails/conversations/{userId}` | 与某用户的对话 |
| GET / PUT | `/users/{userId}` | 用户信息 / 更新 |
| GET | `/users/{userId}/activities` | 用户近期词条相关动态 |
| GET | `/users/{userId}/projects` | 用户参与的项目 |
