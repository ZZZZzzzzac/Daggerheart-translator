---
name: daggerheart-md-converter
description: Convert Daggerheart source files to raw Markdown. Decision-tree: plaintext → direct copy; PDF/DOCX → local tools (marker/mineru) or manual online tools (PaddleOCR). Outputs source/_raw.md.
---

# Daggerheart Markdown Converter

源文件 → `source/_raw.md`。只负责把源文件转成可编辑的原始 Markdown。

标题层级、表格、粗斜体、列表等结构修复不在本 skill 内处理，交给 `daggerheart-md-format-fixer`。

## 路径约定

`source/` 均相对于用户翻译项目的根目录（如 `project/example/`）。`scripts/` 相对于本 skill 根目录。下文命令中两者混用时，AI 需分别解析到对应绝对路径。

## 决策树

```
源文件格式？
├── 已是纯文本（.md / .txt / .rst 等）
│   → 直接拷贝或重命名为 source/_raw.md，跳过转换。
│
└── PDF / DOCX / 其他二进制格式
    └── 检查本机是否有本地转换工具？
        ├── 有（marker / mineru 等）
        │   → 使用本地工具转换 → 输出 source/_raw.md
        │
        └── 无
            → 告知用户手动使用 PaddleOCR-VL（免费）
              或 marker 等在线工具转换为 MD，
              放置到 source/_raw.md 后继续管线。
```

## 步骤 1：判断源文件格式

检查 `source/` 下的源文件扩展名：

- `.md`、`.txt`、`.rst` 等纯文本格式：直接拷贝/重命名为 `source/_raw.md`，跳到「输出约定」。
- `.pdf`、`.docx`、`.doc` 等二进制格式：进入步骤 2。

## 步骤 2：检测本地转换工具

按优先级检测以下命令行工具是否可用（`Get-Command` 或 `which`）：

| 优先级 | 工具 | 检测命令 | 适用格式 |
|--------|------|----------|----------|
| 1 | marker | `marker_single --help` | PDF |
| 2 | mineru | `mineru --help` | PDF |
| 3 | pandoc | `pandoc --version` | DOCX |

> 若用户环境有其他可用工具（如 `docling`、`markitdown`），也可使用，以实际可用为准。

## 步骤 3A：使用本地工具转换

### 方案 A1：marker（推荐，PDF）

需要 Gemini API key。使用项目 `.venv` 环境：

```bash
.venv/Scripts/marker_single "输入.pdf" --output_dir "输出目录" --use_llm --gemini_api_key %GEMINI_API_KEY%
```

将生成的 Markdown 整理为 `项目目录/source/_raw.md`。

转换完成后，手动检查输出中的图片引用，确认是否有文字被整块识别为图片而丢失（常见于图文交错的卡片区域）。如有漏字，先在 `_raw.md` 中补回缺失文本。

### 方案 A2：mineru

```bash
mineru -p "输入.pdf" -o "输出目录"
```

将生成的 Markdown 输出整理为 `项目目录/source/_raw.md`。

### 方案 A3：pandoc（DOCX）

```bash
pandoc "输入.docx" -t markdown -o "source/_raw.md"
```

## 步骤 3B：无本地工具 → 告知用户手动转换

若无可用的本地转换工具，告知用户：

> 当前环境未检测到 marker、mineru 或 pandoc。请手动使用以下在线工具将源文件转为 Markdown，放置到 `source/_raw.md` 后通知我继续管线。
>
> 推荐工具：
> - **PaddleOCR-VL**（免费）：https://aistudio.baidu.com/paddleocr
>   - 上传 PDF，等待转换完成
>   - 下载 Markdown，另存为 `source/_raw.md`
>   - PaddleOCR 输出含远程临时图片 URL 和 HTML 表格，需后处理（见下方）
> - **marker 在线版**（需 API key）：https://www.datalab.to/
>
> 其他可用在线 OCR/转换工具亦可，只要能输出 Markdown 即可。

### PaddleOCR 后处理

PaddleOCR 输出含远程临时图片 URL 和 HTML 表格，需后处理：

```bash
python scripts/paddle_postprocess.py "source/_raw.md"
```

清除 `<div>` 图片标签，HTML `<table>` 转为 Markdown 表格。

## 输出约定

本 skill 的终点是 `项目目录/source/_raw.md`。

后续若需把 `_raw.md` 修成可进入术语提取和分块流程的标准原文，调用 `daggerheart-md-format-fixer`。
