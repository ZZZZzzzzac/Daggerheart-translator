"""初始化翻译项目目录结构，将散落的文件移动到标准位置。

Usage:
    python scripts/setup_project.py <project_dir>

标准结构（见仓库 project/example/）：
    project/<项目名>/
    ├── source/           # 原始文件（_original.md）
    │   └── temp/         # 临时产物（_tagged.md, _chunks/, _translated_chunks/, _merged_terms.json）
    ├── project_scripts/  # 本项目专有脚本（与 skill 的 scripts/ 区分）
    ├── data/             # 结构化 JSON 输出
    └── glossary/         # 项目术语表（_glossary.json）

迁移规则：
    - _original.md 若在项目根目录 → 移至 source/
    - source/_glossary.json → glossary/_glossary.json
    - source/ 下的 _tagged.md, _merged_terms*.json → source/temp/
    - source/_chunks/, source/_translated_chunks/ → source/temp/
"""

import os
import shutil
import sys

if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')


def _makedirs(*parts):
    p = os.path.join(*parts)
    os.makedirs(p, exist_ok=True)
    return p


def _move(src, dst, project_dir):
    """移动文件或目录。返回 (src_rel, dst_rel) 或 None。"""
    if not os.path.exists(src):
        return None
    if os.path.exists(dst):
        print(f"  跳过（目标已存在）: {os.path.relpath(dst, project_dir)}")
        return None
    shutil.move(src, dst)
    src_rel = os.path.relpath(src, project_dir)
    dst_rel = os.path.relpath(dst, project_dir)
    print(f"  已移动: {src_rel} → {dst_rel}")
    return (src_rel, dst_rel)


def setup(project_dir):
    project_dir = os.path.abspath(project_dir)
    print(f"项目目录: {project_dir}")

    created = 0
    for sub in ["source", "source/temp", "project_scripts", "data", "glossary"]:
        p = os.path.join(project_dir, sub)
        if not os.path.isdir(p):
            os.makedirs(p)
            created += 1
            print(f"  创建目录: {sub}")
    if created == 0:
        print("  目录结构已完整，无需创建。")

    moved = 0

    # _original.md: 项目根 → source/
    root_orig = os.path.join(project_dir, "_original.md")
    src_orig = os.path.join(project_dir, "source", "_original.md")
    if _move(root_orig, src_orig, project_dir):
        moved += 1

    source_dir = os.path.join(project_dir, "source")
    temp_dir = os.path.join(project_dir, "source", "temp")
    glossary_dir = os.path.join(project_dir, "glossary")

    # source/_glossary.json → glossary/
    if _move(os.path.join(source_dir, "_glossary.json"),
             os.path.join(glossary_dir, "_glossary.json"), project_dir):
        moved += 1

    # source/ 下其他临时产物 → source/temp/
    for fname in ("_tagged.md", "_merged_terms.json", "_merged_terms_conflicts.json"):
        if _move(os.path.join(source_dir, fname),
                 os.path.join(temp_dir, fname), project_dir):
            moved += 1

    # _chunks/ 和 _translated_chunks/ → source/temp/
    for dname in ("_chunks", "_translated_chunks"):
        if _move(os.path.join(source_dir, dname),
                 os.path.join(temp_dir, dname), project_dir):
            moved += 1

    if moved == 0:
        print("  无需移动的文件。")

    print("完成。")
    return 0


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python scripts/setup_project.py <project_dir>")
        sys.exit(1)
    sys.exit(setup(sys.argv[1]))
