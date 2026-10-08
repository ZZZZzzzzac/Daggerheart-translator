#!/usr/bin/env python
"""ParaTranz API 最小客户端（paratranz-ops 技能）。

只做四件事：看进度、拉快照、写回译文、对账。所有写操作默认 dry-run。

用法（仓库根目录执行）:
    .venv/Scripts/python.exe .claude/skills/paratranz-ops/scripts/para.py files
    .venv/Scripts/python.exe .claude/skills/paratranz-ops/scripts/para.py stats 3347716
    .venv/Scripts/python.exe .claude/skills/paratranz-ops/scripts/para.py pull 3347716 --out snap.json
    .venv/Scripts/python.exe .claude/skills/paratranz-ops/scripts/para.py push 3347716 updates.json          # 只出计划
    .venv/Scripts/python.exe .claude/skills/paratranz-ops/scripts/para.py push 3347716 updates.json --apply   # 真写
    .venv/Scripts/python.exe .claude/skills/paratranz-ops/scripts/para.py diff 3347716 updates.json
    .venv/Scripts/python.exe .claude/skills/paratranz-ops/scripts/para.py strings 3347716 --page 1
    .venv/Scripts/python.exe .claude/skills/paratranz-ops/scripts/para.py terms --out terms.json
    .venv/Scripts/python.exe .claude/skills/paratranz-ops/scripts/para.py issue 23387 --out issue.json
    .venv/Scripts/python.exe .claude/skills/paratranz-ops/scripts/para.py edit-strings plan.json --apply

凭证：仓库根目录 .env 的 PARATRANZ_TOKEN（本脚本不回显、不落盘）。
updates.json 格式：[{"key": "...", "translation": "..."}, ...]（或含 id 的词条数组）。
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

import requests
from dotenv import load_dotenv

API_ROOT = "https://paratranz.cn/api"
DEFAULT_PROJECT_ID = "14448"
BATCH_NOTE = "写回会重置 Paratranz 条目的 stage（已校对/已审核记录失效）"


def find_repo_root() -> Path:
    """DaggerHeart_CN 仓库根目录：含 pipeline/ 与 .env 的那一层。

    可用环境变量 PARATRANZ_REPO 覆盖（技能被链接到别的工具目录时用）。
    """
    override = os.getenv("PARATRANZ_REPO")
    if override:
        return Path(override).expanduser().resolve()
    here = Path(__file__).resolve()
    cwd = Path.cwd().resolve()
    for candidate in (here, cwd):
        for parent in candidate.parents:
            if (parent / "pipeline").is_dir() and (parent / ".env").is_file():
                return parent
    return here.parents[4]


REPO = find_repo_root()


def session() -> requests.Session:
    load_dotenv(REPO / ".env")
    token = os.getenv("PARATRANZ_TOKEN")
    if not token:
        sys.exit(f"错误: {REPO / '.env'} 未配置 PARATRANZ_TOKEN")
    s = requests.Session()
    s.headers["Authorization"] = f"Bearer {token}"
    s.headers["User-Agent"] = "DaggerHeart_CN-paratranz-ops"
    return s


def api(path: str) -> str:
    project_id = os.getenv("PARATRANZ_PROJECT_ID", DEFAULT_PROJECT_ID)
    return f"{API_ROOT}/projects/{project_id}{path}"


def call(s, method: str, path: str, **kw):
    r = s.request(method, api(path), timeout=kw.pop("timeout", 180), **kw)
    if r.status_code >= 400:
        try:
            detail = r.json()
        except ValueError:
            detail = r.text[:500]
        sys.exit(f"HTTP {r.status_code} {method} {path}: {detail}")
    return r


def get_json(s, path: str):
    return call(s, "GET", path).json()


def load_updates(path: Path) -> list[dict]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if isinstance(data, dict):
        data = data.get("items") or data.get("strings") or []
    if not isinstance(data, list) or not data:
        sys.exit(f"错误: {path} 应为非空 JSON 数组 [{{'key','translation'}}]")
    return data


def fetch_strings(s, file_id: str) -> list[dict]:
    return get_json(s, f"/files/{file_id}/translation")


def plan_push(updates: list[dict], online: dict[str, dict], force: bool):
    """返回 (payload, 跳过原因分类)。默认只填空词条，与 API force=false 语义一致。

    updates 里若带 `stage`，会原样透传给接口：文档说「未指定 stage 时」才按译文推导状态，
    所以带上线上当前 stage 就能让已检查/已审核状态不被写回重置。
    """
    payload: list[dict] = []
    buckets = {"missing": [], "empty_translation": [], "unchanged": [], "already_translated": []}
    for item in updates:
        key = str(item.get("key", "")).strip()
        if not key:
            buckets["missing"].append("(缺 key)")
            continue
        translation = item.get("translation") or ""
        entry = online.get(key)
        if entry is None:
            buckets["missing"].append(key)
            continue
        if not translation.strip():
            buckets["empty_translation"].append(key)
            continue
        if (entry.get("translation") or "") == translation:
            buckets["unchanged"].append(key)
            continue
        if (entry.get("translation") or "").strip() and not force:
            buckets["already_translated"].append(key)
            continue
        entry_payload = {"key": key, "translation": translation}
        if item.get("stage") is not None:
            entry_payload["stage"] = item["stage"]
        payload.append(entry_payload)
    return payload, buckets


def cmd_files(s, args) -> int:
    files = get_json(s, "/files")
    rows = [f for f in files if not args.match or args.match in f["name"]]
    rows.sort(key=lambda f: f["name"])
    for f in rows:
        total = f["total"] or 1
        print(
            f"{f['id']:>9}  {f['name']:<64} {f['translated']:>5}/{f['total']:<5} "
            f"{100 * f['translated'] / total:5.1f}%  查={f.get('checked', 0):<5} 审={f.get('reviewed', 0):<4} "
            f"改={f.get('modifiedAt')}"
        )
    print(f"\n{len(rows)} 个文件（项目 {os.getenv('PARATRANZ_PROJECT_ID', DEFAULT_PROJECT_ID)}）")
    return 0


def cmd_stats(s, args) -> int:
    info = get_json(s, f"/files/{args.file_id}")
    total = info["total"] or 1
    print(json.dumps(
        {
            "id": info["id"],
            "name": info["name"],
            "format": info.get("format"),
            "total": info["total"],
            "translated": info["translated"],
            "translated_pct": round(100 * info["translated"] / total, 2),
            "checked": info.get("checked"),
            "reviewed": info.get("reviewed"),
            "disputed": info.get("disputed"),
            "modifiedAt": info.get("modifiedAt"),
        },
        ensure_ascii=False,
        indent=2,
    ))
    return 0


def cmd_pull(s, args) -> int:
    data = fetch_strings(s, args.file_id)
    out = Path(args.out) if args.out else Path(f"para_{args.file_id}.snapshot.json")
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    filled = sum(1 for e in data if (e.get("translation") or "").strip())
    print(f"已保存 {len(data)} 条 → {out}（有译文 {filled} / {len(data)}）")
    return 0


def cmd_strings(s, args) -> int:
    """分页读词条元信息。默认只读 --page 指定的一页，--all 才走完全部页码。"""
    page = args.page
    total = 0
    while True:
        body = get_json(s, f"/strings?file={args.file_id}&page={page}&pageSize={args.page_size}")
        results = body.get("results", [])
        for e in results:
            print(f"{e['id']:>10}  [{e.get('stage')}]  {e.get('key')}")
        total += len(results)
        page_count = body.get("pageCount") or 0
        print(f"  第 {page}/{page_count or '?'} 页，本页 {len(results)} 条，共 {body.get('rowCount')} 条")
        if not args.all or page >= page_count:
            break
        page += 1
    return 0


def cmd_edit_strings(s, args) -> int:
    """批量改词条（PUT /strings，op=edit）。可按 id 指定 translation 与 stage。

    用于「改译文但不要把已检查/已审核打回已翻译」：items 里显式带 stage。
    与文件导入路径不同，这条路径的 stage 作用于指定的词条 id。
    """
    plan = json.loads(Path(args.plan).read_text(encoding="utf-8"))
    if isinstance(plan, dict):
        plan = plan.get("items", [])
    items = []
    for it in plan:
        if "id" not in it:
            sys.exit("错误: edit-strings 的每项都需要 id（文件导入按 key，这条路径按 id）")
        entry = {"id": int(it["id"])}
        for field in ("translation", "stage", "context", "key", "original"):
            if field in it and it[field] is not None:
                entry[field] = it[field]
        items.append(entry)
    print(f"计划修改 {len(items)} 条（PUT /strings op=edit）")
    for it in items[:3]:
        print(f"  id={it['id']} stage={it.get('stage')} 译文前 40 字={(it.get('translation') or '')[:40]!r}")
    if not args.apply:
        print("\n[dry-run] 未提交。加 --apply 才写。")
        return 0

    result = call(s, "PUT", "/strings", json={"op": "edit", "items": items}).json()
    print(f"服务端返回: {result if not isinstance(result, list) else f'已更新 id {len(result)} 个'}")

    drift = []
    for it in items:
        cur = get_json(s, f"/strings/{it['id']}")
        for field in ("translation", "stage"):
            if field in it and cur.get(field) != it[field]:
                drift.append((it["id"], field, it[field], cur.get(field)))
    if drift:
        print(f"回读发现 {len(drift)} 处不一致（期望 → 实际）:")
        for item_id, field, want, got in drift[:10]:
            print(f"  ! id={item_id} {field}: {want} → {got}")
        return 2
    print("回读校验通过（译文与 stage 都按期望写入）。")
    return 0


def cmd_issue(s, args) -> int:
    """读取一条讨论（主楼 + 全部楼层）。楼层是翻译口径、术语裁定的常用来源。"""
    issue = get_json(s, f"/issues/{args.issue_id}")
    floors = issue.get("activities") or []
    if args.out:
        payload = {
            "id": issue["id"],
            "title": issue.get("title"),
            "uid": issue.get("uid"),
            "createdAt": issue.get("createdAt"),
            "updatedAt": issue.get("updatedAt"),
            "content": issue.get("content"),
            "floors": [
                {
                    "index": i,
                    "id": f["id"],
                    "uid": f["uid"],
                    "createdAt": f["createdAt"],
                    "content": f.get("content"),
                }
                for i, f in enumerate(floors)
            ],
        }
        path = Path(args.out)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        print(f"已保存讨论 {issue['id']}（{len(floors)} 楼）→ {path}")
    print(f"# {issue.get('title')}")
    for i, f in enumerate(floors):
        first = (f.get("content") or "").strip().split("\n")[0][:60]
        print(f"  [{i}] id={f['id']} uid={f['uid']} {f['createdAt'][:10]}  {first}")
    return 0


def cmd_terms(s, args) -> int:
    terms, page = [], 1
    while True:
        body = get_json(s, f"/terms?page={page}&pageSize=1000")
        terms.extend(body.get("results", []))
        if not body.get("pageCount") or page >= body["pageCount"]:
            break
        page += 1
    if args.out:
        path = Path(args.out)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(terms, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        print(f"已保存 {len(terms)} 条术语 → {path}")
    else:
        for t in terms:
            print(f"{t.get('term')}\t{t.get('translation')}")
    return 0


def default_snapshot_path(file_id: str) -> Path:
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
    return REPO / "projects" / ".paratranz_backup" / f"{file_id}-{stamp}.snapshot.json"


def write_snapshot(path: Path, data: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def report_buckets(buckets: dict[str, list[str]]) -> None:
    labels = {
        "missing": "线上不存在该 key（不会创建，需先上传原文）",
        "empty_translation": "本地译文为空（拒绝清空线上）",
        "unchanged": "与线上一致",
        "already_translated": "线上已有译文（需 --force 才覆盖）",
    }
    for name, keys in buckets.items():
        if not keys:
            continue
        print(f"  {labels[name]}: {len(keys)}")
        for key in keys[:10]:
            print(f"    - {key}")
        if len(keys) > 10:
            print(f"    ... 另有 {len(keys) - 10} 条")


def stage_note(payload: list[dict]) -> str:
    with_stage = sum(1 for item in payload if "stage" in item)
    if payload and with_stage == len(payload):
        return "本次 payload 全部显式带 stage，接口应保留原状态（文档如此；首次使用请在回读时确认 stage 未变）"
    if with_stage:
        return f"注意: 只有 {with_stage}/{len(payload)} 条带 stage，其余条目写回后会被重置为「已翻译」"
    return f"注意: {BATCH_NOTE}"


def cmd_push(s, args) -> int:
    updates = load_updates(Path(args.updates))
    before = fetch_strings(s, args.file_id)
    online = {str(e["key"]): e for e in before}
    payload, buckets = plan_push(updates, online, args.force)

    print(f"本地待写 {len(updates)} 条 | 线上 {len(before)} 条 | 计划写入 {len(payload)} 条")
    with_stage = sum(1 for item in payload if "stage" in item)
    if with_stage:
        print(f"  其中 {with_stage} 条显式带 stage（写回后保留原有状态，不按译文重新推导）")
    report_buckets(buckets)

    if not payload:
        print("没有需要写入的词条，未发起请求。")
        return 0

    if not args.apply:
        print(f"\n[dry-run] 未写入。确认无误后加 --apply 重跑。")
        print(stage_note(payload))
        return 0

    snap_path = Path(args.snapshot) if args.snapshot else default_snapshot_path(args.file_id)
    write_snapshot(snap_path, before)
    print(f"\n写回前快照: {snap_path}")

    info = get_json(s, f"/files/{args.file_id}")
    filename = args.filename or Path(info["name"]).name
    body = {
        "items": payload,
        "filename": filename,
        "force": bool(args.force),
    }
    result = call(s, "POST", f"/files/{args.file_id}/translation", json=body).json()
    print(f"导入结果: {json.dumps(result, ensure_ascii=False)}")
    if isinstance(result, dict) and result.get("status"):
        print(f"服务端未更新任何词条（status={result['status']}）。")

    after = {str(e["key"]): e for e in fetch_strings(s, args.file_id)}
    mismatches = [
        item for item in payload
        if (after.get(item["key"], {}).get("translation") or "") != item["translation"]
    ]
    print(f"\n回读核对: {len(payload) - len(mismatches)}/{len(payload)} 条与本地一致")
    for item in mismatches[:10]:
        print(f"  ! {item['key']}")
    if mismatches:
        print(f"核对失败: {len(mismatches)} 条未写入。快照保留在 {snap_path}")
        return 1
    stage_drift = [
        (item["key"], item["stage"], after[item["key"]].get("stage"))
        for item in payload
        if "stage" in item and after.get(item["key"], {}).get("stage") != item["stage"]
    ]
    if stage_drift:
        print(f"stage 被重置: {len(stage_drift)}/{len(payload)} 条（期望 → 实际）")
        for key, want, got in stage_drift[:10]:
            print(f"  ! {key}: {want} → {got}")
        return 2
    print("核对通过，stage 未被改动。")
    return 0


def cmd_diff(s, args) -> int:
    """本地快照 vs 线上：比对 translation，若本地带 stage 也一并比对。"""
    local = load_updates(Path(args.local))
    online = {str(e["key"]): e for e in fetch_strings(s, args.file_id)}
    missing, diff, stage_diff, same = [], [], [], 0
    for item in local:
        key = str(item.get("key", "")).strip()
        entry = online.get(key)
        if entry is None or "translation" not in item:
            missing.append(key)
            continue
        if (entry.get("translation") or "") == (item.get("translation") or ""):
            same += 1
        else:
            diff.append(key)
        if "stage" in item and entry.get("stage") != item["stage"]:
            stage_diff.append((key, item["stage"], entry.get("stage")))
    print(f"本地 {len(local)} 条 | 译文一致 {same} | 译文不一致 {len(diff)} | 线上无此项 {len(missing)} | stage 不一致 {len(stage_diff)}")
    for key in diff[:20]:
        print(f"  ~ {key}")
    for key in missing[:20]:
        print(f"  ? {key}")
    for key, want, got in stage_diff[:20]:
        print(f"  s {key}: stage {want} → {got}")
    return 1 if (diff or missing or stage_diff) else 0


def main() -> int:
    parser = argparse.ArgumentParser(description="ParaTranz API 最小客户端（默认 dry-run）")
    sub = parser.add_subparsers(dest="cmd", required=True)

    p = sub.add_parser("files", help="列出项目文件与进度")
    p.add_argument("--match", help="按文件名子串过滤")
    p.set_defaults(func=cmd_files)

    p = sub.add_parser("stats", help="单文件进度")
    p.add_argument("file_id")
    p.set_defaults(func=cmd_stats)

    p = sub.add_parser("pull", help="下载某文件全部词条快照")
    p.add_argument("file_id")
    p.add_argument("--out")
    p.set_defaults(func=cmd_pull)

    p = sub.add_parser("push", help="写回译文（默认只出计划）")
    p.add_argument("file_id")
    p.add_argument("updates")
    p.add_argument("--apply", action="store_true", help="真正提交")
    p.add_argument("--force", action="store_true", help="覆盖人工译文（慎用）")
    p.add_argument("--snapshot", help="写回前快照路径")
    p.add_argument("--filename", help="记录到文件历史的上传名（默认取线上文件名）")
    p.set_defaults(func=cmd_push)

    p = sub.add_parser("diff", help="本地译文包 vs 线上（对账，有差异退出码 1）")
    p.add_argument("file_id")
    p.add_argument("local")
    p.set_defaults(func=cmd_diff)

    p = sub.add_parser("strings", help="分页读词条")
    p.add_argument("file_id")
    p.add_argument("--page", type=int, default=1)
    p.add_argument("--page-size", type=int, default=100)
    p.add_argument("--all", action="store_true", help="从 --page 起走完所有页")
    p.set_defaults(func=cmd_strings)

    p = sub.add_parser("edit-strings", help="按 id 批量改词条（可显式设 stage，保状态用）")
    p.add_argument("plan", help="JSON: [{\"id\":…, \"translation\":…, \"stage\":…}]")
    p.add_argument("--apply", action="store_true", help="真正提交")
    p.set_defaults(func=cmd_edit_strings)

    p = sub.add_parser("terms", help="读取术语表")
    p.add_argument("--out")
    p.set_defaults(func=cmd_terms)

    p = sub.add_parser("issue", help="读取讨论主楼与全部楼层")
    p.add_argument("issue_id")
    p.add_argument("--out", help="保存为 JSON 的路径")
    p.set_defaults(func=cmd_issue)

    args = parser.parse_args()
    return args.func(session(), args)


if __name__ == "__main__":
    sys.exit(main())
