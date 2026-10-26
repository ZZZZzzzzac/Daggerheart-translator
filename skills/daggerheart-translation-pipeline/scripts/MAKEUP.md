# 规则术语规范化

`makeup.py` 只自动处理明确的资源短语，保留文档结构。`process_markdown()` 可重复运行，结果应保持不变。

```bash
python scripts/makeup.py source/_translated.md --diff
python scripts/makeup.py source/_translated.md --check
python scripts/makeup.py source/_translated.md --suffix ""
python scripts/test_makeup.py
```

- `--diff` 只显示差异；`--check` 不写文件，有变化时退出码为 1。
- CLI 默认覆盖输入；`--suffix _makeup` 另存。Python 的 `process_markdown_file()` 默认后缀仍为 `_makeup`。
- `[动词] [数量] [资源]` 统一空格、中文数字和重复量词，识别骰式、至少／至多、等量的等数量。
- 生命点用“恢复”；压力点、护甲槽用“清除”；“消耗”改为“花费”。护甲值、资源容量槽、希望骰等不按资源处理。
- “获得一种希望之光”等叙述以及共用动词的并列资源句不自动改写。
- 标题、代码、链接、图片、HTML 属性、锚点和元数据保持原样；保留强调、表格、换行。
- 正文中的 PC／GM 换成中文全称；括号、引号中的缩写定义和标识符保持原样。“重骰”统一为“重掷”。
- 默认不删除图片、链接或空 span，不给全部数字加粗，也不做全局中英空格处理。需要中英空格时使用 `--space-ascii`。

本仓库不包含网站实现 `static/js/makeup-core.mjs`，本地测试只验证 Python formatter，不证明与外部网站的规则或渲染一致。若另行维护网站副本，须在其所在仓库核对实现并运行相应共享用例和整站渲染测试。

两阶段实验的候选精修终稿不经 makeup；该承诺不因 formatter 更保守而改变。需要检查时只报告差异，由审阅者决定是否另行修订，不静默改写已审阅终稿。
