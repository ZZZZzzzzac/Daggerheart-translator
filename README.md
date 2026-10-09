# Daggerheart 翻译工具集

Daggerheart TTRPG 内容的翻译技能合集。英文 PDF/DOCX 输入，中文 Markdown + 结构化 JSON 输出。

## 试用分支

本分支增加 AI 全文审校、语境例外审计、内容绑定审批和带完整原文/译文上下文的问题卡。先读 [试用说明](docs/TRIAL.md)，再运行 `python -m unittest discover -s tests -v`。AI 先修复确定问题；机器检查通过不等于翻译语义已被证明正确。

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
  paratranz-ops/                   # 已有平台操作技能，非本地流程的必需依赖
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

## 术语表分层

- `terms-core.json`：以原人工清洗表为基线，维护跨项目复用的规则术语和官方战役框架名称；不是 ParaTranz 的自动同步导出。
- `glossary/_glossary.json`：当前项目独有的人名、地名、组织及概念。官方战役框架名称统一使用核心表。
- `resources/scoped/`：按框架分别保存专属机制，保留原译名供对应项目选用，不默认加载。

详见 [术语范围与迁移说明](skills/daggerheart-translation-pipeline/resources/README.md)。

## 注意事项

1. AI 工具需要能读取完整提示词、访问项目文件并运行 Python。不要压缩或改写管线生成的翻译提示词；是否遵守仍须通过源译审校确认。
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
