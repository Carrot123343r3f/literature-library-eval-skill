# 文献库评估报告

## 本次评估输入与证据状态

| 输入工件 | 是否提供 | 是否有效 | 支撑的指标 | 缺失影响 |
| --- | --- | --- | --- | --- |
| 规范化文献库 | 是 | 有效（15 篇） | C–F、部分 A/B | 无库不能做正式评估 |
| A1 基准集 | 否 | 有稳定 ID | A1 | A1 不可评估 |
| A2 Gold 集 | 否 | — | A2 | A2 不可评估 |
| 查询日志 (run-log) | 否 | 否 | F1、A2 | 检索不可复跑 |
| 筛选决定 | 否 | 否 | B | B 不可判饱和 |
| 去重日志 (dedup-log) | 否 | 否 | F4 | 版本处理待核验 |
| A3 多源快照 | 否 | — | A3 | A3 不可评估 |
| 前沿检索证据 | 否 | — | D3 | D3 不可评估（默认） |
| 版本核验记录 | 否 | — | D4 | D4 不可评估（默认） |

## 优先级行动

1. **🟡 F3 全文获取率**：附件 0.0% | 开放链接 0.0% | 联合 0.0%。低于阈值。联合=v 附件或开放链接任一可用的记录比例，避免同一记录双渠道重复计数。
2. **🟡 F5 来源可追溯**：仅来源字段可追溯（谱系率 1.0）。未提供 decision-log——纳入/排除理由不可追溯。。未提供主题分类（taxonomy）——库的纳入决定未按主题分组，后续综述存在"逐篇流水账"风险（descriptive listing），建议引入主题框架以支撑批判性综合

## 基本信息

| 项目 | 值 |
| --- | --- |
| 生成时间 | 2026-07-21 08:13:32 |
| 评估对象 | C:\Users\Qt\.claude\skills\literature-library-eval\tests\3dgs_library.json |
| 文献库规模 | 15 篇 |
| 综述类型 | 系统综述 |
| 工程领域 | computer_ai |
| 研究范围 | 2021–2026 |
| 全域参考 | OpenAlex 候选下界 3 篇 |

## 综合判断

评估完成（2026-07-21 08:13:32）。库规模 15 篇，综述类型 系统综述，工程领域 computer_ai。 未检测到阻断项。

A1 基准集召回 100.0%（4/4），A3 多源下界 3 篇，B 饱和度 不可证明，C 主题平衡 正常，D 近年占比 60.0%，E h-core=15，F 摘要覆盖 100.0%。 各维度不合成总分；"不可评估"不是失败。

## 评估方法与过程

**检索关键词**：未记录（建库时未保留 query-plan.json，检索不可复跑）

**A1 基准集**：共 4 篇稳定标识符条目。来源未记录。
**A2 独立性**：⚠ Supply both gold set and executed query-hit snapshot.

**A3 覆盖估计**：Multi-source deduplicated lower bound; not Recall or capture-recapture.

**证据状态**：实测=可复跑记录；估计=基于假设的区间或抽样；自动初筛=规则判定未人工核验；不可评估=缺少必要输入。

## A–F 六维评估总表

| 维度 | 编号 | 评估项 | 标准 | 判定 | 当前值 | 证据状态 | 说明与行动 |
| --- | --- | --- | --- | --- | --- | --- | --- |
| A 覆盖 | A1 | 基准集召回率 | 阈值 ≥ 0.9 | pass | 100.0%（4/4） | measured | A1 高只说明找回了锚点，不等于主题无遗漏。实测 4/4（100.0%）。无稳定 ID 漏项。 |
| A 覆盖 | A2 | 检索式灵敏度 | 阈值 ≥ 0.85 | not_assessable | —（—/—） | not_assessable | A2 高只说明检索式能找回 Gold，不等于 Gold 足够代表问题。实测 —。 |
| A 覆盖 | A3 | 多源候选下界 | 至少两完整来源去重后的不重复候选数；只报告下界 | screening | 至少 3 篇不重复候选（openalex, crossref） | estimated | 至少 3 篇——'至少有多少篇相关文献存在于这些来源中'。不是 Recall，也不是'漏了多少'。来源完整。 |
| B 饱和度 | B1 | 核心库增长率 (GGR) | / | not_assessable | — | not_assessable | B 趋稳仅在筛选决策真实、路径独立且多轮完成时才成立。GGR=需要至少两轮 search round。高置信新增/核心库。 |
| B 饱和度 | B2 | 新增路径发现率 (DRR) | / | not_assessable | 0 条路径 | not_assessable | DRR 只有在筛选确认后才有意义——发现候选不等于纳入项。边际收益：[]。新路径高置信文献/候选量。 |
| B 饱和度 | B3 | 饱和过程证据 | / | not_assessable | 路径 — ／ 独立验证 — | not_assessable | 结论：**不可证明**。仅低 GGR/DRR 不够——需路径完成+独立验证+筛选真实同时成立。 |
| C 平衡 | C1 | 主题覆盖与偏斜 | 无空主题；Top≤0.70；CV≤0.80；Gini≤0.50；Shannon≥0.55 | not_assessable | 0 主题 ／ 无空主题 | not_assessable | 。各主题均有文献。 |
| C 平衡 | C2 | 来源集中度 | Top≤0.80；CV≤1.00；Gini≤0.60；Shannon≥0.45 | pass | Top=46.7% ／ CV=0.432 ／ Gini=0.222 ／ Hn=0.902 | measured | 最大来源占比 46.7%。来源分布合理。 单一作者 'Martin R. Oswald' 占文献库 27.3%——可能存在课题组偏倚，建议检查是否过度依赖单一研究群体的视角。 |
| C 平衡 | C3 | 主题-来源交叉 | 每主题 ≥2 来源；单一来源 ≤0.80 | not_assessable | — | not_assessable | 未提供 topic_source_counts。 |
| D 时效 | D1 | 来源新鲜度 | 各来源距检索 ≤ 30 天 | not_assessable | — | not_assessable | 0 个来源有日期。来源在新鲜度窗口内。 |
| D 时效 | D2 | 近年文献比例 | 近 3 年占比 ≥ 0.4 | pass | 60.0%（9/15 有日期） | measured | 近 3 年占比 60.0%。阈值按 profile：AI/通信 3年40%、常规 5年35%、基础设施 7年30%。达标。年份字段完整率 100.0%；<50% 时 D2 自动降级为 warning。 |
| D 时效 | D3 | 前沿覆盖 | / | not_assessable | — | measured | 前沿覆盖需 context.frontier_coverage_verdict。近期发表不等于前沿覆盖。 |
| D 时效 | D4 | 版本区分 | / | not_assessable | 预印本 5 条 | measured | 5 条预印本。未核验版本关系。 |
| E 学术影响 | E1 | h-core | 报告 h-index；仅背景信号 | screening | h=15（15 条引用） | measured | h-core=15。仅背景信号——高被引不等于高质量，新论文拉低 h-core。真正的研究质量评估应使用与研究设计匹配的批判性评价工具。 |
| E 学术影响 | E2 | Tier-1 覆盖 | 按 profile 配置 venue 映射 | not_assessable | —（—/0 venue） | measured | 已配置 0 个 venue。未配置 tier1_venues。 |
| F 可用性 | F1 | 检索可复跑 | / | not_assessable | run log 缺失 | not_assessable | 建库时查询未保留——唯一过程阻断项。 |
| F 可用性 | F2 | 摘要覆盖率 | ≥ 0.85 | pass | 100.0% | measured | 摘要率 100.0%。达标。 |
| F 可用性 | F3 | 全文获取率 | ≥ 0.8 | warning | 0.0% | measured | 附件 0.0% ／ 开放链接 0.0% ／ 联合 0.0%。低于阈值。联合=v 附件或开放链接任一可用的记录比例，避免同一记录双渠道重复计数。 |
| F 可用性 | F4 | 去重与版本 | DOI 精确重复=0；版本候选有决定 | not_assessable | DOI 重复 0 组 ／ 题名候选 0 组 ／ 深度 missing | measured | DOI 重复 0 组。无精确重复。题名相似候选 0 组（未提供结构化 dedup-log，版本候选待核验。） |
| F 可用性 | F5 | 来源可追溯 | ≥ 0.95 | warning | 100.0% | measured | 仅来源字段可追溯（谱系率 1.0）。未提供 decision-log——纳入/排除理由不可追溯。。未提供主题分类（taxonomy）——库的纳入决定未按主题分组，后续综述存在"逐篇流水账"风险（descriptive listing），建议引入主题框架以支撑批判性综合 |
| F 可用性 | F6 | 撤稿更正核查 | / | not_assessable | 标记 0 条 | measured | 0 条标记。未经专门来源核验。 |

## 各维度分析

**A 覆盖**：基准集召回 100.0%（4/4），多源候选下界至少 3 篇——'至少有多少篇相关文献存在'，不是漏了多少。

**B 饱和度**：最后两轮 GGR=缺数据（阈值<0.02）；不可证明。

**C 平衡**：0 个预期主题，全部有文献；来源集中度 0.467（CV=0.432 Gini=0.222）。 作者集中度：top-author 0.273（）。

**D 时效**：近 3 年占比 60.0%（9/15 标有日期）；预印本 5 条。

**E 学术影响**：h-core=15（15 条引用）；Tier-1 —（0 venue）。仅作背景信号，不等于研究质量——真正的研究质量评估应使用与研究设计匹配的批判性评价工具。

**F 可用性**：核心元数据 100.0%；摘要 100.0%；DOI 100.0%；全文获取率 0.0%（附件 0.0% / OA 0.0%）；谱系率 100.0%。

## 改进建议

### 建议改进

- F3 全文获取率：附件 0.0% | 开放链接 0.0% | 联合 0.0%。低于阈值。联合=v 附件或开放链接任一可用的记录比例，避免同一记录双渠道重复计数。
- F5 来源可追溯：仅来源字段可追溯（谱系率 1.0）。未提供 decision-log——纳入/排除理由不可追溯。。未提供主题分类（taxonomy）——库的纳入决定未按主题分组，后续综述存在"逐篇流水账"风险（descriptive listing），建议引入主题框架以支撑批判性综合

## 局限与声明

- 本报告中的各项阈值均为基于工程文献计量经验的参考值，旨在辅助识别可能的风险信号，不等于文献库质量的绝对标准。pass/warning/fail 是自动化诊断提示，不是质量裁决，所有结论均应结合具体研究问题和领域惯例做人工判断。
- A3 下界不是 Recall；区间需另行声明模型假设。
- 主题平衡、版本等价性、研究设计和更正状态需人工或专门来源核验。
- h-core 和 Tier-1 仅作诊断背景，不等于综述质量。
- 未提供的运行产物会明确标为缺失。

## 本次采用标准

| 评估项 | 编号 | 默认值 | 本次采用值 | 来源 | 用户覆盖？ |
| --- | --- | --- | --- | --- | --- |
| 基准集召回率 | a1_min_recall | 90.0% | 90.0% | review_type_default | 否 |
| 检索式灵敏度 | a2_min_recall | 85.0% | 85.0% | review_type_default | 否 |
| GGR 阈值 | b_ggr_threshold | 0.02 | 0.02 | profile_default | 否 |
| DRR 阈值 | b_drr_threshold | 0.05 | 0.05 | profile_default | 否 |
| 主题 Top-share | topic_top_share_warning | 0.7 | 0.7 | profile_default | 否 |
| 来源 Top-share | balance_top_share_warning | 0.8 | 0.8 | profile_default | 否 |
| D2 近年窗口 | recency_years | — 年 / ≥ — | — 年 / ≥ — | profile_default | 否 |
| 来源新鲜度 | d_freshness_days | 30 天 | 30 天 | profile_default | 否 |
| 摘要覆盖率 | f_abstract_rate | 85.0% | 85.0% | review_type_default | 否 |
| 全文获取率 | f_access_rate | 80.0% | 80.0% | review_type_default | 否 |
| 来源可追溯 | f_provenance_rate | 95.0% | 95.0% | review_type_default | 否 |
| 核心元数据率 | f_core_metadata_rate | 95.0% | 95.0% | review_type_default | 否 |

> 来源说明：`profile_default` = 工程领域默认值；`review_type_default` = 综述类型默认值；`user_override` = 用户指定值。
> 完整标准说明书见 `references/user-standards-guide.md`。

