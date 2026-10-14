# Daggerheart 翻译工具集

Daggerheart TTRPG 内容的翻译技能合集。英文 PDF/DOCX 输入，中文 Markdown + 结构化 JSON 输出。

## 目录

```
skills/                           # 技能源码
  daggerheart-translation-pipeline/  # 12 步翻译管线（主入口）
  daggerheart-md-converter/          # PDF/DOCX → 原始 Markdown
  daggerheart-md-format-fixer/       # 原始 Markdown → 标准原文 Markdown
  daggerheart-chinese-writing/      # 中文行文规范
  daggerheart-glossary-extractor/   # 文档术语提取
  daggerheart-term-checker/         # 术语审阅报告与清标记
  daggerheart-json-formatter/      # 译文 → 结构化 JSON
project/
  example/                        # 翻译项目模板（复制以新建项目）
```

## 安装

直接 clone，让你的 AI 助手完成安装（详见 `AGENTS.md`）：

```bash
git clone https://github.com/ZZZZzzzzac/Daggerheart-translator.git
```

然后告诉 AI："安装 Daggerheart-translator skills"。

## 使用

1. 复制 `project/example/` 为 `project/<你的项目名>/`
2. 将待翻译的 PDF/MD 文件放入项目的 `source/` 子目录
3. 在项目目录下告诉 AI："加载 daggerheart-translation-pipeline skill，翻译这个文件"

当前管线会在分块翻译后保留术语标记，先生成术语审阅报告，再批量清除标记并继续合并、校验、JSON 提取。

## 现有译文审阅

加载 [daggerheart-translation-audit](skills/daggerheart-translation-audit/SKILL.md)，审阅已有 SRD、规则书或卡牌译文。工作流覆盖完整分页快照、范围去重、逐条语义检查、独立复核、官方源溯源、交付前增量回读和可保存进度的逐条报告。默认只读；报告与本地勾选不修改 ParaTranz。

## 术语表分层

- `terms-core.json`：以原人工清洗表为基线，维护跨项目复用的规则术语和官方战役框架名称；不是 ParaTranz 的自动同步导出。
- `glossary/_glossary.json`：当前项目独有的人名、地名、组织及概念。官方战役框架名称统一使用核心表。
- `resources/scoped/`：按框架分别保存专属机制，保留原译名供对应项目选用，不默认加载。

详见 [术语范围与迁移说明](skills/daggerheart-translation-pipeline/resources/README.md)。

## 注意事项

1. 尽可能使用claude code或cli工具，codex会导致管线约束失效。
2. 运行前可以自行检查需要的Python库是否安装，运行过程中安装可能会导致下载慢或者额外的token消耗
3. 安装第一步所需的marker-pdf等ocr库时, 如果下载太慢或者总是出错. 建议换用线上的许多pdf转md工具, 比如paddle-ocr

## 适配其他 TTRPG

替换以下文件即可适配其他规则书：

- `skills/daggerheart-translation-pipeline/resources/terms-core.json` — 人工维护的规则核心术语表
- `skills/daggerheart-chinese-writing/REFERENCE.md` — 术语规范
- `skills/daggerheart-chinese-writing/匕语/` — 行文规范
- `skills/daggerheart-json-formatter/examples/template.md` — 输出模板

其余脚本通用，无需修改。

## License

MIT
