# 文献库评估全模块示例

## 示例结论

本示例库共有 4 篇记录。A1 基准集召回为 66.7%，A2 查询命中为 100%，A3 给出两个来源去重后的候选下界。B1–B3 因缺少足够的正式筛选轮次而保持 `not_assessable`；这展示了“发现候选”不能直接冒充“检索趋稳”。

单文章模块将目标论文列为核心证据候选，并单独展示方法学、可复核性、完整性、影响信号和库内贡献；外部文章仍标为 `candidate_discovery`，不能直接计入正式库。

## 模块导航

| 模块 | 输出 |
|---|---|
| 输入与权限 | [run-config.json](run-config.json) |
| 文献库 | [library.json](library.json) |
| 元数据补齐 | [metadata-enrichment.json](enrichment/metadata-enrichment.json) |
| A–F 审计（HTML） | [audit.html](audit/audit.html) |
| A–F 审计（Markdown） | [audit.md](audit/audit.md) |
| A–F 审计（JSON） | [audit.json](audit/audit.json) |
| 可恢复行动 | [next-actions.json](actions/next-actions.json) |
| 单文章评价（HTML） | [paper-evaluation.html](paper-evaluation/paper-evaluation.html) |
| 单文章评价（Markdown） | [paper-evaluation.md](paper-evaluation/paper-evaluation.md) |
| 单文章评价（JSON） | [paper-evaluation.json](paper-evaluation/paper-evaluation.json) |
| 输入/运行哈希 | [audit manifest](audit/manifest.json) / [paper manifest](paper-evaluation/manifest.json) |

## 阅读顺序

先看本页，再打开 A–F HTML 报告；随后查看 `next-actions.json` 了解缺口；最后打开单文章评价报告查看单篇证据与补库候选。
