# 参考运行样本

主题：Gaussian Splatting 支持实时 SLAM，重点关注低光照和噪声传感条件。

本目录是供维护者、评审者和回归检查使用的完整可复现参考运行样本，不是新手入口。新用户应先运行 `python scripts/autopilot.py --question "..." --out first-pass`，获得简洁的 `onboarding.html`，再决定是否确认范围并进行完整审计。

本示例使用本地快照，不需要联网或 API key。它展示：

- 输入与联网权限确认
- 文献库元数据补齐模块及失败/缺口报告
- A1–A3 覆盖
- B1–B3 饱和度与路径证据
- C1–C3 主题/来源平衡
- D1–D4 时效与版本
- E1–E2 影响信号
- F1–F6 可用性
- `next-actions.json` 恢复行动清单
- 单文章证据评价
- 外部候选发现与人工筛选边界
- Markdown、HTML、JSON、manifest 和输入快照

建议先看：

1. [A–F 审计报告](audit/audit.html)
2. [单文章评价报告](paper-evaluation/paper-evaluation.html)
3. [下一步行动](actions/next-actions.json)
4. [元数据补齐状态](enrichment/metadata-enrichment.json)

说明：示例中的 `enrichment` 报告刻意展示了没有 API key 时的可恢复降级；它保留原始文献库，不伪造引用数或 DOI。
