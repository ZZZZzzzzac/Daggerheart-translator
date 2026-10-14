---
name: daggerheart-term-checker
description: Build a per-occurrence term review report from tagged source chunks and translated chunks, then strip approved term markers into a clean chunk directory for merge.
---

# Daggerheart Term Checker

对比 `_chunks/`（带术语标记的原文）与 `_translated_chunks/`（保留术语标记的译文），逐条生成术语审阅报告；审阅完成后，再批量清除术语标记，得到可合并的 clean chunk。

## 运行方式

可手动调用，也可作为 `daggerheart-translation-pipeline` 的标准步骤使用。

在翻译项目根目录下执行：

```bash
python <skill_root>/scripts/check_terms.py <项目目录>
python <skill_root>/scripts/strip_term_markers.py <项目目录>
```

示例：

```bash
python ../Daggerheart-translator/skills/daggerheart-term-checker/scripts/check_terms.py .
python ../Daggerheart-translator/skills/daggerheart-term-checker/scripts/strip_term_markers.py .
```

## 输入

- `source/temp/_chunks/` — 带 `【原文｜推荐译文｜注释】` 标记的原文 chunk
- `source/temp/_translated_chunks/` — 对应译文 chunk，术语标记格式为 `【当前译文｜推荐译文｜注释】`

两个目录必须都存在（即管线至少跑完第 6 步）。

## 检查规则

对每个 chunk 的 `KILO_TARGET` 区段：

1. 从原文 chunk 读取每个术语槽位的 `原文 / 推荐译文 / 注释`
2. 从译文 chunk 优先按 `推荐译文 + 注释` 对位读取对应 `当前译文`；只有无法精确匹配时才退回顺序兜底
3. 判断 `当前译文` 是否与 `推荐译文` 一致
4. 同时截取原文上下文与当前译文上下文，便于人工或 AI 审阅

这是逐条审阅报告，不会去重，也不会只展示“有问题”的项；同一术语在不同上下文中会各列一行。

## 输出

1. **stdout**：统计摘要。
2. **`source/temp/_term_review_report.html`**：默认人工审阅网页。
3. **`source/temp/_term_review_report.md`**：保留兼容的 Markdown 表格。
4. **`source/temp/_term_review_report.json`**：保留原字段的逐条 JSON 报告。

默认表格列：

| chunk | 原文 | 推荐译文 | 当前译文 | 是否采用推荐 | 原文上下文 | 译文上下文 | 注释 | 异常 |

- `是否采用推荐` 仅作提示，不强制要求为“是”
- 若发现标记数量不一致、标记损坏、槽位为空等结构异常，会在报告中明确列出
- 若译文只发生了相邻术语换序，但 `推荐译文 + 注释` 仍能对上，不再误报结构异常

可指定输出路径：

```bash
python check_terms.py <项目目录> --output <自定义路径.md>
```

也可指定 JSON 输出路径：

```bash
python check_terms.py <项目目录> --json-output <自定义路径.json>
```

## 清除术语标记

术语审阅通过后，执行：

```bash
python strip_term_markers.py <项目目录>
```

默认行为：

- 输入目录：`source/temp/_translated_chunks/`
- 输出目录：`source/temp/_translated_chunks_clean/`
- 将 `【当前译文｜推荐译文｜注释】` 替换为 `当前译文`
- 保留原始带标记译文 chunk，不覆盖原文件

## 注意

- 该报告的职责是把每个术语翻译决策显式列出来，供人工或 AI 逐条审阅。
- 若 `_chunks/` 或 `_translated_chunks/` 目录不存在，脚本会报错退出。

## HTML 人工审阅

默认用 HTML 交给用户，不以纯文字表格代替。复用同仓库 `daggerheart-translation-audit` 的通用离线渲染器；此适配器只负责 main 现有术语报告的展示，不引入试验分支的术语机制或审批文件。

- 每个术语出现位置仍独立保留，包括词面采用推荐者，不把其称为“语义正确”。
- 并排展示完整 TARGET 原文/现译，标记只显示第一槽；精准高亮对应的实际出现位置，不做全局关键词替换。重复术语和相邻换序沿用现有 checker 对位，无法由脚本证明语义对齐。
- 左右正文框独立滚动，判断区也可滚动，不做框内分页，全文保留；结构异常和缺失译文如实显示。TARGET 缺失时显示实际整个 chunk 文件，不编造上下文。
- 底栏集中上一条、下一条、完成。当前输入是本地 chunk，没有网页来源时不显示虚构链接；出处显示实际相对文件路径。
- “完成”仅记阅读进度，不修改译文，不批准术语，不代替手动模式的用户明确确认，也不触发清标记。检查与清标记的既有工作流不变。
- 进度以当前全部 chunk 字节及报告内容绑定版本。内容变化后旧进度不沿用；生成时间和项目搬家不会单独改变内容身份。更多菜单可导入/导出相同报告版本的阅读进度；file:// 或存储不可用时须导出备份。

```bash
python check_terms.py <项目目录> --html-output <自定义路径.html>
python -m unittest discover -s tests -v
python -m unittest discover -s skills/daggerheart-translation-audit/tests -v
node skills/daggerheart-translation-audit/tests/test_report_state.js
node skills/daggerheart-translation-audit/tests/test_highlighting.js
node skills/daggerheart-translation-audit/tests/test_source_action.js
node skills/daggerheart-translation-audit/tests/test_scroll_panes.js
```

HTML 输出不能覆盖源译文输入。结构异常时仍生成报告并保持原来的非零退出；没有术语不等于全文审校完成。自动化结构测试和模拟 DOM 测试不能替代真实浏览器视觉验收。
