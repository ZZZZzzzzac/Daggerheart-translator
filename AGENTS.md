# Daggerheart 翻译技能合集

本仓库包含 5 个 Daggerheart TTRPG 翻译技能。技能本体在 `skills/` 目录下，彼此独立，可单独使用。

## 技能清单

| 技能 | 文件 | 用途 |
|------|------|------|
| `daggerheart-translation-pipeline` | `skills/daggerheart-translation-pipeline/SKILL.md` | 9 步翻译管线（主编排） |
| `daggerheart-chinese-writing` | `skills/daggerheart-chinese-writing/SKILL.md` | 中文行文规范 |
| `daggerheart-glossary-extractor` | `skills/daggerheart-glossary-extractor/SKILL.md` | 文档术语提取 |
| `daggerheart-json-formatter` | `skills/daggerheart-json-formatter/SKILL.md` | 译文 → JSON |
| `daggerheart-md-converter` | `skills/daggerheart-md-converter/SKILL.md` | PDF/DOCX → MD |

## 安装

将 `skills/` 目录下的 5 个子目录链接或复制到当前工具的 skill 目录。各工具路径如下：

| 工具 | skill 目录 | 安装命令（示例） |
|------|-----------|-----------------|
| Claude Code | `.claude/skills/` | 参考下方通用命令 |
| Kilo | `.kilo/skills/` | 参考下方通用命令 |
| OpenCode | `.opencode/skills/` | 参考下方通用命令 |
| Codex | `.agents/skills/` | 参考下方通用命令 |

**你（AI）收到安装请求时**：
1. 检查当前工作目录下存在哪个工具目录（`.claude/`、`.kilo/`、`.opencode/`、`.agents/` 等）
2. 在对应的 `skills/` 子目录下创建指向本仓库 `skills/*/` 的目录链接（junction/symlink）
3. 不要复制整个仓库，只链接 `skills/` 下的 5 个子目录

**通用安装命令**（用户手动执行）：
```bash
# <TOOL_SKILLS_DIR> 替换为实际路径，如 .claude/skills、.kilo/skills
# <REPO_SKILLS> 替换为本仓库 skills/ 的绝对路径
for dir in <REPO_SKILLS>/*/; do
  ln -s "$(realpath "$dir")" "<TOOL_SKILLS_DIR>/$(basename "$dir")"
done
```

## 翻译项目布局

本仓库是技能合集，不直接存放翻译内容。用户翻译时在自己的项目目录下工作：

```
project/<项目名>/
├── source/         # 原始文件（PDF/MD），管线输入
│   └── temp/       # 临时产物（_chunks/、_tagged.md 等）
├── project_scripts/        # 本项目专有的脚本（与 skill 的 scripts/ 区分）
├── data/           # 结构化 JSON 输出
└── glossary/       # 项目术语表
```

`project/example/` 是模板，展示了标准的项目目录结构。建立新翻译项目时复制此模板即可。

## 使用

用户加载 `daggerheart-translation-pipeline` skill 后按 SKILL.md 指示的 9 步管线执行。管线所有产物写入当前翻译项目的 `source/` 和 `source/temp/` 下。

技能之间通过 `__file__` 相对路径解析互相引用，不依赖安装位置。
