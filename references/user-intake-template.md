# 本次评估输入与证据状态

报告生成时间：{{generated_at}}

| 输入工件 | 是否提供 | 是否有效 | 支撑的指标 | 缺失影响 |
|---|---:|---|---|---|
| 规范化文献库 | 是/否 | 有效/待处理 | C–F、部分 A/B | 无库不能做正式评估 |
| A1 基准集 | 是/否 | 有稳定 ID/否 | A1 | A1 不可评估 |
| A2 Gold 集 | 是/否 | 独立于 A1 / 与 A1 复用 | A2 | A2 降低证据强度（若复用） |
| 查询日志 (run-log) | 是/否 | schema 合格/字段不全/否 | F1、A2 | 检索不可复跑 |
| 筛选决定 | 是/否 | 完整/discovery_only/否 | B | B 不可判饱和 |
| 去重日志 (dedup-log) | 是/否 | 决策完整/有候选无决策/否 | F4 | 版本处理待核验 |
| A3 多源快照 | 是/否 | 完整/部分/否 | A3 | A3 不可评估 |
| 前沿检索证据 | 是/否 | / | D3 | D3 不可评估（默认） |
| 版本核验记录 | 是/否 | / | D4 | D4 不可评估（默认） |
| Tier-1 venue 列表 | 是/否 | / | E2 | E2 不可评估 |

## 本次采用标准

| 评估项 | 编号 | 默认值 | 本次采用值 | 来源 | 用户覆盖？ |
|---|---:|---:|---:|---|---|
| 基准集召回率 | A1 | {{default_a1}} | {{applied_a1}} | {{a1_source}} | {{a1_override}} |
| 检索式灵敏度 | A2 | {{default_a2}} | {{applied_a2}} | {{a2_source}} | {{a2_override}} |
| GGR 阈值 | B1 | 0.02 | {{applied_ggr}} | {{ggr_source}} | {{ggr_override}} |
| DRR 阈值 | B2 | 0.05 | {{applied_drr}} | {{drr_source}} | {{drr_override}} |
| 主题 Top-share | C1 | ≤ 0.70 | {{applied_c1}} | {{c1_source}} | {{c1_override}} |
| 来源 Top-share | C2 | ≤ 0.80 | {{applied_c2}} | {{c2_source}} | {{c2_override}} |
| D2 近年窗口 | D2 | {{default_d2_years}} 年 / ≥ {{default_d2_share}} | {{applied_d2_years}} 年 / ≥ {{applied_d2_share}} | {{d2_source}} | {{d2_override}} |
| 来源新鲜度 | D1 | {{default_d1_days}} 天 | {{applied_d1_days}} 天 | {{d1_source}} | {{d1_override}} |
| 摘要覆盖率 | F2 | {{default_f2}} | {{applied_f2}} | {{f2_source}} | {{f2_override}} |
| 全文获取率 | F3 | {{default_f3}} | {{applied_f3}} | {{f3_source}} | {{f3_override}} |
| 来源可追溯 | F5 | {{default_f5}} | {{applied_f5}} | {{f5_source}} | {{f5_override}} |
| 核心元数据率 | F | {{default_f_meta}} | {{applied_f_meta}} | {{f_meta_source}} | {{f_meta_override}} |

> 来源说明：`profile_default` = 工程领域默认值；`review_type_default` = 综述类型默认值；`user_override` = 用户指定值。
> 完整标准说明书见 `references/user-standards-guide.md`。
