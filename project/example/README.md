# 项目结构

```
project/<项目名>/
├── source/         # 原始文件（PDF/MD），管线的输入
│   └── temp/       # 临时文件，下划线开头（_merged_terms.json、_chunks/ 等）
├── project_scripts/        # 本项目专有的脚本（与 skill 的 scripts/ 区分）
├── data/           # json-formatter 从文档抽取的结构化 JSON
└── glossary/       # 术语表（_glossary.json 等）
```

## 使用

1. 将待翻译的 PDF 或 MD 文件放入 `source/`
2. 在项目根目录告诉 AI："加载 daggerheart-translation-pipeline skill，翻译 `source/<文件名>`"
3. 管线产物全部在 `source/` 和 `source/temp/` 下
